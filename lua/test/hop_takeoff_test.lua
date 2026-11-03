-- Host test for hop_takeoff.lua: the real script against a mock of the ArduPilot scripting
-- API and a takeoff physics model. Run from the packethw folder: lua lua/test/hop_takeoff_test.lua
--
-- Model (SI units, W = m*g):
--  vertical    thrust with angle boost: vertical part = T/W * W * ground effect; the legs
--              carry the rest until liftoff. Ground effect 1 + GE0*exp(-h/0.05).
--  horizontal  on the ground: (T/W)*W*tan(tilt) against friction mu*N (static, then sliding);
--              in the air: g*(T/W)*tan(tilt).
--  attitude    follows the target with a 0.25 s lag, plus a nose-down bias from the load
--              (BIAS deg at T/W 1, in proportion to thrust) that the attitude integrator
--              learns away with a 0.4 s time constant once GUIDED runs it (after the spool).
--              On the legs the actual tilt stays at the resting attitude until the weight
--              comes off them (blended over T/W 0.6..1).
--  GUIDED      zero thrust until the motors spooled MOT_SPOOL_TIME, then the script's thrust;
--              after the handover a PD position controller like ArduPilot's (wn 1.4).
--  EKF         position and velocity 30 ms late with 2 mm / 1 cm/s noise.

local G = 9.80665

local function run_case(name, c)
  -- ---- mock API -----------------------------------------------------------
  local params = { HOP_CH = 12, MOT_THST_HOVER = 0.275, PSC_NE_POS_P = 1.0, PSC_NE_VEL_P = 2.0, MOT_SPOOL_TIME = 0.5 }
  local clock_ms = 0
  local armed, mode = true, 4
  local pwm12 = 2000
  local cmd = nil            -- last angle/thrust command {roll, pitch, yaw, thr}
  local pos_target = nil
  local texts, hopt = {}, {}
  local spool_t = nil

  -- physical state
  local x, y, z, vx, vy, vz = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
  local roll, pitch = c.rest_r or 0.4, c.rest_p or 0.9      -- deg, resting on the legs
  local roll_f, pitch_f = roll, pitch                         -- free-flying attitude (lagged target)
  local integ = 0.0                                            -- learned nose-down bias, deg
  local hist = {}                                              -- for the EKF delay

  _G.param = {
    add_table = function() return true end,
    add_param = function(_, _, _, n, d) params["HTO_" .. n] = d; return true end,
  }
  _G.Parameter = function(n) return { get = function() return params[n] end } end
  _G.millis = function() return { tofloat = function() return clock_ms end } end
  _G.rc = { get_pwm = function(_, ch) return ch == 12 and pwm12 or 1000 end }
  _G.arming = { is_armed = function() return armed end, disarm = function() armed = false; return true end }
  _G.gcs = {
    send_text = function(_, _, t) table.insert(texts, t) end,
    send_named_float = function(_, n, v) if n == "HOPT" then hopt[#hopt + 1] = v end end,
  }
  local function V(a, b, cc)
    local v = { _x = a or 0, _y = b or 0, _z = cc or 0 }
    function v:x(s) if s then self._x = s end return self._x end
    function v:y(s) if s then self._y = s end return self._y end
    function v:z(s) if s then self._z = s end return self._z end
    return v
  end
  _G.Vector3f = function() return V() end
  local function ekf()
    local d = hist[math.max(1, #hist - 30)]                    -- 30 ms late (1 ms steps)
    return d
  end
  _G.ahrs = {
    get_relative_position_NED_origin = function()
      local d = ekf(); if not d then return nil end
      return V(d.x + (math.random() - 0.5) * 0.004, d.y + (math.random() - 0.5) * 0.004, -0.24 - d.z + (math.random() - 0.5) * 0.004)
    end,
    get_velocity_NED = function()
      local d = ekf(); if not d then return nil end
      return V(d.vx + (math.random() - 0.5) * 0.02, d.vy + (math.random() - 0.5) * 0.02, -d.vz + (math.random() - 0.5) * 0.02)
    end,
    get_roll_rad = function() return math.rad(roll) end,
    get_pitch_rad = function() return math.rad(pitch) end,
    get_yaw_rad = function() return math.rad(c.yaw or 30) end,
  }
  _G.motors = { get_spool_state = function()
    return (spool_t and clock_ms - spool_t >= params.MOT_SPOOL_TIME * 1000) and 3 or 2
  end }
  _G.vehicle = {
    get_mode = function() return mode end,
    set_target_angle_and_rate_and_throttle = function(_, r, p, yw, _, _, _, thr)
      cmd = { r, p, yw, thr }; if not spool_t then spool_t = clock_ms end; return true
    end,
    set_target_pos_NED = function(_, tgt) pos_target = { tgt:x(), tgt:y(), tgt:z() }; return true end,
  }

  local step = dofile("lua/hop_takeoff.lua")
  local next_ms = 1000                                          -- the script's first call is after 1 s
  hist[1] = { x = x, y = y, z = z, vx = vx, vy = vy, vz = vz }

  local hover_true = params.MOT_THST_HOVER * (c.weight or 1.0)  -- the real hover thrust (load)
  local mu = c.mu or 0.3
  local ge0 = c.ge or 0.04
  local yaw = math.rad(c.yaw or 30)
  local res = { max_slide_ground = 0, liftoff_t = nil, hand_t = nil, hand_vz = nil, hand_slide = nil, aborted = false, max_tilt = 0 }
  local t_end = (c.t_end or 12) * 1000

  while clock_ms < t_end do
    clock_ms = clock_ms + 1
    if clock_ms >= next_ms then
      local fn, period = step()
      step = fn or step
      next_ms = clock_ms + (period or 20)
    end
    local dt = 0.001
    -- thrust (GUIDED: zero during the spool, then the script's; after the handover a PD controller)
    local tw = 0.0
    local tr, tp = c.rest_r or 0.4, c.rest_p or 0.9
    if armed and cmd and spool_t and clock_ms - spool_t >= params.MOT_SPOOL_TIME * 1000 then
      if pos_target then
        local ex, ey, ez = x - pos_target[1], y - pos_target[2], (-0.24 - z) - pos_target[3]
        local an, ae = -2 * ex - 2 * vx, -2 * ey - 2 * vy
        local af = an * math.cos(yaw) + ae * math.sin(yaw)
        local ar = -an * math.sin(yaw) + ae * math.cos(yaw)
        tp, tr = -math.deg(math.atan(af / G)), math.deg(math.atan(ar / G))
        tw = 1.0 + (5 * ez - 3 * vz) / G                          -- height PD (ez in NED: + = below the target)
        tw = math.max(0.5, math.min(1.5, tw))
      else
        tr, tp = cmd[1], cmd[2]
        tw = cmd[4] / hover_true                                  -- actual T/W from the commanded thrust
      end
      -- the attitude integrator learns the load bias once the controller runs, and only as
      -- far as the drone can rotate (on the legs there is no attitude error to learn from)
      local u_learn = (z <= 0.0) and math.max(0, math.min(1, (tw - 0.6) / 0.4)) or 1
      local bias_raw = (c.bias or 3.0) * tw
      integ = integ + (bias_raw - integ) * dt / 0.4 * u_learn
    end
    local bias = ((c.bias or 3.0) * tw) - integ                     -- nose-down error not yet learned
    -- free attitude: lagged target, minus the nose-down bias
    roll_f = roll_f + (tr - roll_f) * dt / 0.25
    pitch_f = pitch_f + (tp - pitch_f) * dt / 0.25
    local free_p = pitch_f - bias
    local on_ground = z <= 0.0 and vz <= 0.0
    local u = on_ground and math.max(0, math.min(1, (tw - 0.6) / 0.4)) or 1
    roll = (1 - u) * (c.rest_r or 0.4) + u * roll_f
    pitch = (1 - u) * (c.rest_p or 0.9) + u * free_p
    res.max_tilt = math.max(res.max_tilt, math.abs(pitch), math.abs(roll))

    -- forces: body forward/right accel per unit weight from the tilt
    local ge = 1 + ge0 * math.exp(-z / 0.05)
    local af_b = -math.tan(math.rad(pitch)) * tw * G               -- nose down = forward
    local ar_b = math.tan(math.rad(roll)) * tw * G
    local an = af_b * math.cos(yaw) - ar_b * math.sin(yaw)
    local ae = af_b * math.sin(yaw) + ar_b * math.cos(yaw)
    local lift = tw * ge                                            -- vertical thrust / weight
    if on_ground and lift <= 1.0 then
      local nfrac = 1.0 - lift                                      -- legs carry this share
      local fmax = mu * nfrac * G
      local sp = math.sqrt(vx * vx + vy * vy)
      local ah = math.sqrt(an * an + ae * ae)
      if sp < 1e-4 and ah <= fmax then
        vx, vy, an, ae = 0, 0, 0, 0
      elseif sp >= 1e-4 then
        an, ae = an - fmax * vx / sp, ae - fmax * vy / sp
      else
        an, ae = an - fmax * an / ah, ae - fmax * ae / ah
      end
      vz, z = 0, 0
    else
      vz = vz + (lift - 1.0) * G * dt
      z = math.max(0, z + vz * dt)
      if z == 0 and vz < 0 then vz = 0 end
    end
    vx, vy = vx + an * dt, vy + ae * dt
    x, y = x + vx * dt, y + vy * dt
    hist[#hist + 1] = { x = x, y = y, z = z, vx = vx, vy = vy, vz = vz }

    local slide = math.sqrt(x * x + y * y)
    if not res.liftoff_t and z > 0.002 then res.liftoff_t = clock_ms / 1000; res.liftoff_tw = tw end
    if not res.liftoff_t then res.max_slide_ground = math.max(res.max_slide_ground, slide) end
    if pos_target and not res.hand_t then res.hand_t = clock_ms / 1000; res.hand_vz = vz; res.hand_slide = slide; res.hand_z = z end
    if not armed then res.aborted = true; break end
    if res.hand_t and clock_ms / 1000 > res.hand_t + 2 then res.final_slide = slide; res.final_z = z; break end
  end
  local last = texts[#texts] or ""
  print(string.format("%-34s %s", name, res.aborted and ("ABORT: " .. last) or ""))
  if not res.aborted then
    print(string.format("   ground slide max %.1f cm | liftoff %.2f s at T/W %.2f | handover %.2f s at %.1f cm, %.2f m/s up, slid %.1f cm | 2 s later %.1f cm off, %.1f cm up | max tilt %.1f deg",
      res.max_slide_ground * 100, res.liftoff_t or -1, res.liftoff_tw or -1, res.hand_t or -1, (res.hand_z or 0) * 100,
      res.hand_vz or 0, (res.hand_slide or 0) * 100, (res.final_slide or 0) * 100, (res.final_z or 0) * 100, res.max_tilt))
  end
  for _, t in ipairs(texts) do print("     FC: " .. t) end
  return res
end

math.randomseed(1)
local fails = 0
local function expect(cond, what) if not cond then print("   FAIL: " .. what); fails = fails + 1 end end

local r = run_case("nominal (3 deg nose-heavy)", {})
expect(not r.aborted and r.max_slide_ground < 0.02, "ground slide under 2 cm")
expect(r.hand_vz and r.hand_vz < 0.25, "handover climb under 0.25 m/s")
expect(r.final_slide and r.final_slide < 0.03, "within 3 cm 2 s after handover")

r = run_case("heavy package, 6 deg nose-heavy", { bias = 6.0, weight = 1.15 })
expect(not r.aborted and r.max_slide_ground < 0.03, "ground slide under 3 cm")
expect(r.final_slide and r.final_slide < 0.04, "within 4 cm 2 s after handover")

r = run_case("light, slippery floor (mu 0.15)", { weight = 0.9, mu = 0.15 })
expect(not r.aborted and r.max_slide_ground < 0.03, "ground slide under 3 cm")

r = run_case("no ground effect, hover learned low", { ge = 0.0, weight = 1.1 })
expect(not r.aborted, "lifts off")

r = run_case("load too heavy (needs T/W 1.45)", { weight = 1.45 })
expect(r.aborted, "aborts with no liftoff")

r = run_case("tail-heavy 4 deg, 90 deg heading", { bias = -4.0, yaw = 90 })
expect(not r.aborted and r.max_slide_ground < 0.03, "ground slide under 3 cm")

print(fails == 0 and "ALL PASS" or (fails .. " FAILED"))
os.exit(fails == 0 and 0 or 1)
