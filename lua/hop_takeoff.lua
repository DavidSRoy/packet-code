-- hop_takeoff.lua: the ground phase of the hold-to-hover takeoff (ArduCopter 4.7)
--
-- Why: in a normal takeoff ArduCopter keeps the attitude integrators drained and the
-- position controller off until it decides it is flying. On the skids the nose-heavy
-- torque then goes uncorrected and nothing resists a slide: the drone skidded 10-17 cm
-- before it lifted (2026-11-02). This script flies that phase itself.
--
-- How: GUIDED angle control with a thrust from this script. A positive thrust makes
-- GUIDED clear "landed" as soon as the motors reach full range (MOT_SPOOL_TIME), and from
-- then on the full attitude controller runs, integrators included, on the ground
-- (mode_guided.cpp angle_control_run, 4.7.2).
--
-- Physics (thrust in T/W = thrust / MOT_THST_HOVER, the learned hover thrust):
--  * On the skids the horizontal force is W*(T/W)*tan(tilt), held by friction
--    mu*W*(1 - T/W). Below T/W 0.6 the legs carry 40 %: with mu about 0.3 that holds
--    up to about 7 deg of tilt, so the first part goes fast (HTO_TW_FAST, at 0.6 /s).
--  * Near T/W 1 the friction is gone and each 0.1 deg of tilt is 0.017 m/s^2 of
--    drift: from HTO_TW_FAST on the thrust rises slowly (HTO_RAMP per second).
--    Past liftoff the height grows as g*r*t^3/6 until it is seen: at r = 0.2 /s the
--    1 cm liftoff mark comes 0.31 s after T/W 1, at about 0.10 m/s and T/W 1.06.
--  * The slide is held with the same law as ArduPilot's position controller,
--    a = -PSC_NE_POS_P*PSC_NE_VEL_P*e - PSC_NE_VEL_P*v (wn 1.4 rad/s, zeta 0.71 by
--    default), tilt = atan(a/g), at most HTO_TILT deg, so the handover is smooth.
--  * Commanding a tilt the legs do not let it reach only winds up the integrators:
--    the tilt target goes from the resting attitude (legs) to level plus the hold
--    as the weight moves off the legs (T/W from HTO_TW_FAST to 1).
--  * After liftoff it keeps the liftoff thrust (+2 %): ground effect lifts it below
--    the learned hover thrust. No climb in 1.5 s: the ramp goes on at half rate.
--  * At HTO_HAND_M above the start it hands over: a position target over the start
--    point, and ArduPilot's position controller (and ground control) fly on.
--
-- It runs when armed in GUIDED with HOP_CH high (the hold-to-hover button; hop_guard.lua
-- stays the dead-man) and HTO_ENABLE = 1. It disarms on: T/W HTO_TW_MAX with no liftoff,
-- a tilt over HTO_ABT_TILT, a slide over HTO_ABT_M. It reports HOPT (NAMED_VALUE_FLOAT):
-- 0 idle, 1 spool, 2 on the skids, 3 lifted, 4 handed over, 9 aborted.

local TABLE_KEY = 80
assert(param:add_table(TABLE_KEY, "HTO_", 9), "HTO_ param table failed")
assert(param:add_param(TABLE_KEY, 1, "ENABLE", 1), "HTO_ENABLE")
assert(param:add_param(TABLE_KEY, 2, "TW_FAST", 0.6), "HTO_TW_FAST")   -- T/W reached quickly (legs still hold)
assert(param:add_param(TABLE_KEY, 3, "RAMP", 0.2), "HTO_RAMP")         -- T/W per second from TW_FAST on
assert(param:add_param(TABLE_KEY, 4, "TW_MAX", 1.3), "HTO_TW_MAX")     -- no liftoff by this T/W = abort
assert(param:add_param(TABLE_KEY, 5, "LIFT_M", 0.01), "HTO_LIFT_M")    -- height rise that counts as liftoff
assert(param:add_param(TABLE_KEY, 6, "HAND_M", 0.03), "HTO_HAND_M")    -- height to hand over to position control
assert(param:add_param(TABLE_KEY, 7, "TILT", 5), "HTO_TILT")           -- hold tilt limit, deg
assert(param:add_param(TABLE_KEY, 8, "ABT_TILT", 10), "HTO_ABT_TILT")  -- actual tilt that aborts, deg
assert(param:add_param(TABLE_KEY, 9, "ABT_M", 0.15), "HTO_ABT_M")      -- slide that aborts, m

local P_ENABLE = Parameter("HTO_ENABLE")
local P_TW_FAST = Parameter("HTO_TW_FAST")
local P_RAMP = Parameter("HTO_RAMP")
local P_TW_MAX = Parameter("HTO_TW_MAX")
local P_LIFT = Parameter("HTO_LIFT_M")
local P_HAND = Parameter("HTO_HAND_M")
local P_TILT = Parameter("HTO_TILT")
local P_ABT_TILT = Parameter("HTO_ABT_TILT")
local P_ABT_M = Parameter("HTO_ABT_M")
local P_HOP_CH = Parameter("HOP_CH")
local P_HOVER = Parameter("MOT_THST_HOVER")
local P_POS_P = Parameter("PSC_NE_POS_P")
local P_VEL_P = Parameter("PSC_NE_VEL_P")
local P_SPOOL = Parameter("MOT_SPOOL_TIME")

local MODE_GUIDED = 4
local SPOOL_UNLIMITED = 3      -- AP_Motors::SpoolState::THROTTLE_UNLIMITED
local HIGH_PWM = 1700
local G = 9.80665
local PERIOD_MS = 20           -- 50 Hz
local TW_START = 0.3           -- first T/W once the motors are at full range
local FAST_RATE = 0.6          -- T/W per second up to HTO_TW_FAST
local REST_S = 0.2             -- resting attitude averaged this long after arming
local AIR_WAIT_S = 1.5         -- lifted but not at HTO_HAND_M this long: ramp on at half rate

local IDLE, REST, SPOOL, SKIDS, AIR, DONE = 0, 1, 2, 3, 4, 5
local REPORT = { [IDLE] = 0, [REST] = 1, [SPOOL] = 1, [SKIDS] = 2, [AIR] = 3, [DONE] = 4 }

local state = IDLE
local t_state, t_report = 0, 0
local start, yaw_deg = nil, 0
local rest_r, rest_p, rest_n = 0, 0, 0
local tw, tw_lift, ramp = 0, 0, 0
local aborted_until = 0

local function now_s() return millis():tofloat() * 0.001 end
local function clamp(x, lo, hi) return math.max(lo, math.min(hi, x)) end

local function set_state(s, t) state, t_state = s, t end

local function report(t, force)
  local code = (aborted_until > t) and 9 or REPORT[state]
  if force or t - t_report >= ((state == IDLE and aborted_until <= t) and 1.0 or 0.1) then
    gcs:send_named_float("HOPT", code)
    t_report = t
  end
end

local function abort(t, why)
  arming:disarm()
  gcs:send_text(2, "HTO: MOTORS OFF (" .. why .. ")")
  aborted_until = t + 3.0
  set_state(IDLE, t)
  report(t, true)
end

-- position and velocity relative to the start (NED, m and m/s), or nil
local function rel()
  local p = ahrs:get_relative_position_NED_origin()
  local v = ahrs:get_velocity_NED()
  if not p or not v or not start then return nil end
  return p:x() - start:x(), p:y() - start:y(), start:z() - p:z(), v:x(), v:y(), -v:z()
end

-- tilt (deg) that holds the start point, blended from the resting attitude by w
local function tilt_target(en, ee, vn, ve, w)
  local kv = P_VEL_P:get()
  local kp = P_POS_P:get() * kv
  local an = -kp * en - kv * vn
  local ae = -kp * ee - kv * ve
  local amax = G * math.tan(math.rad(P_TILT:get()))
  local a = math.sqrt(an * an + ae * ae)
  if a > amax then an, ae = an * amax / a, ae * amax / a end
  local yaw = math.rad(yaw_deg)
  local af = an * math.cos(yaw) + ae * math.sin(yaw)       -- forward
  local ar = -an * math.sin(yaw) + ae * math.cos(yaw)      -- right
  local pitch = -math.deg(math.atan(af / G))               -- nose down to go forward
  local roll = math.deg(math.atan(ar / G))
  return (1 - w) * rest_r + w * roll, (1 - w) * rest_p + w * pitch
end

local function command(roll, pitch, t_w)
  return vehicle:set_target_angle_and_rate_and_throttle(roll, pitch, yaw_deg, 0, 0, 0, t_w * P_HOVER:get())
end

local function update()
  local t = now_s()
  local held = rc:get_pwm(math.floor(P_HOP_CH:get()))
  local active = P_ENABLE:get() >= 1 and arming:is_armed() and vehicle:get_mode() == MODE_GUIDED
                 and held ~= nil and held >= HIGH_PWM
  if not active then
    if state ~= IDLE then set_state(IDLE, t) end
    report(t)
    return update, PERIOD_MS
  end

  if state == IDLE then
    if aborted_until > t then report(t) return update, PERIOD_MS end
    local p = ahrs:get_relative_position_NED_origin()
    if not p then report(t) return update, PERIOD_MS end
    start, yaw_deg = p, math.deg(ahrs:get_yaw_rad())
    rest_r, rest_p, rest_n = 0, 0, 0
    set_state(REST, t)
    gcs:send_text(6, "HTO: takeoff, holding the start point")
  end

  local en, ee, up, vn, ve, vup = rel()
  if not en then abort(t, "no position") return update, PERIOD_MS end
  local slide = math.sqrt(en * en + ee * ee)
  local tilt = math.max(math.abs(math.deg(ahrs:get_roll_rad())), math.abs(math.deg(ahrs:get_pitch_rad())))
  if state >= SKIDS and state <= AIR then
    if tilt > P_ABT_TILT:get() then abort(t, string.format("tilt %.0f deg", tilt)) return update, PERIOD_MS end
    if slide > P_ABT_M:get() then abort(t, string.format("slid %.0f cm", slide * 100)) return update, PERIOD_MS end
  end

  local tw_fast = P_TW_FAST:get()
  if state == REST then
    -- the attitude it rests at on its legs (the tilt target starts there)
    rest_r = rest_r + math.deg(ahrs:get_roll_rad())
    rest_p = rest_p + math.deg(ahrs:get_pitch_rad())
    rest_n = rest_n + 1
    if t - t_state >= REST_S then
      rest_r, rest_p = rest_r / rest_n, rest_p / rest_n
      tw = TW_START
      set_state(SPOOL, t)
    end
    command(math.deg(ahrs:get_roll_rad()), math.deg(ahrs:get_pitch_rad()), TW_START)
  elseif state == SPOOL then
    -- GUIDED spools the motors up and clears "landed" itself; the ramp starts at full range
    command(rest_r, rest_p, TW_START)
    local spooled
    if motors and motors.get_spool_state then
      spooled = motors:get_spool_state() == SPOOL_UNLIMITED
    else                                        -- build without the motors binding: wait out the spool
      spooled = t - t_state >= P_SPOOL:get() + 0.3
    end
    if spooled then set_state(SKIDS, t) end
  elseif state == SKIDS then
    local dt = PERIOD_MS * 0.001
    tw = tw + ((tw < tw_fast) and FAST_RATE or P_RAMP:get()) * dt
    if tw > P_TW_MAX:get() then
      abort(t, string.format("no liftoff by T/W %.2f", tw))
      return update, PERIOD_MS
    end
    local w = clamp((tw - tw_fast) / (1 - tw_fast), 0, 1)
    local r, p = tilt_target(en, ee, vn, ve, w)
    command(r, p, tw)
    if up >= P_LIFT:get() or (vup >= 0.05 and up >= 0.004) then
      tw_lift = tw
      ramp = 0
      set_state(AIR, t)
      gcs:send_text(6, string.format("HTO: liftoff at T/W %.2f, slid %.1f cm", tw, slide * 100))
    end
  elseif state == AIR then
    if t - t_state > AIR_WAIT_S then ramp = 0.5 * P_RAMP:get() end
    tw_lift = tw_lift + ramp * PERIOD_MS * 0.001
    if tw_lift > P_TW_MAX:get() then
      abort(t, string.format("no climb by T/W %.2f", tw_lift))
      return update, PERIOD_MS
    end
    local r, p = tilt_target(en, ee, vn, ve, 1)
    command(r, p, tw_lift * 1.02)
    if up >= P_HAND:get() then
      -- position control over the start point, at the current height: ArduPilot flies on
      local target = Vector3f()
      target:x(start:x())
      target:y(start:y())
      target:z(start:z() - up)
      if vehicle:set_target_pos_NED(target, true, yaw_deg, false, 0, false, false) then
        set_state(DONE, t)
        gcs:send_text(6, string.format("HTO: handed over at %.1f cm, slid %.1f cm, T/W %.2f",
                                       up * 100, slide * 100, tw_lift * 1.02))
        report(t, true)
      end
    end
  end
  -- DONE: nothing more until it disarms or the button is released
  report(t)
  return update, PERIOD_MS
end

gcs:send_text(6, "HTO: hover takeoff script on")
return update, 1000
