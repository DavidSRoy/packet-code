-- hop_guard.lua: dead-man for the ground control "hold to hop" button (ArduCopter 4.7)
--
-- The hover flies in GUIDED on the camera position (EKF source set 2). While the
-- button is held, the laptop holds RC channel HOP_CH high with an RC override (2000).
-- The guard LATCHES ON when HOP_CH goes high while armed, and stays on until the
-- drone disarms, in any mode. While on, the motors stop at once (disarm) when:
--   - HOP_CH is not high: the button was released (the laptop sends 1000), or the
--     laptop, the page or the radio is gone (the override times out after
--     RC_OVERRIDE_TIME and the channel falls back to the receiver),
--   - the height above home is over HOP_MAX_M (the EKF height: the camera on source set 2),
--   - the tilt is over HOP_TILT degrees.
-- A flight that never holds HOP_CH high (fly-to, trips, the Boxer) never latches it,
-- so every other flight is untouched.
-- It sends HOPG (NAMED_VALUE_FLOAT) once a second: the laptop allows a hop only
-- while it hears it.
--
-- Setup: RC_OVERRIDE_TIME 0.3 (s) so a lost link stops the motors within about
-- 0.3 s. HOP_CH must be a channel the Boxer does not use (default 12).

local TABLE_KEY = 79
assert(param:add_table(TABLE_KEY, "HOP_", 4), "HOP_ param table failed")
assert(param:add_param(TABLE_KEY, 1, "ENABLE", 1), "HOP_ENABLE")
assert(param:add_param(TABLE_KEY, 2, "CH", 12), "HOP_CH")        -- RC channel the laptop holds high
assert(param:add_param(TABLE_KEY, 3, "MAX_M", 0.6), "HOP_MAX_M") -- height limit above home, m
assert(param:add_param(TABLE_KEY, 4, "TILT", 25), "HOP_TILT")    -- tilt limit, deg

local P_ENABLE = Parameter("HOP_ENABLE")
local P_CH = Parameter("HOP_CH")
local P_MAX = Parameter("HOP_MAX_M")
local P_TILT = Parameter("HOP_TILT")

local HIGH_PWM = 1700
local PERIOD_MS = 10
local last_beat = 0
local latched = false       -- a hover is on: HOP_CH went high while armed

local function kill(why)
  arming:disarm()
  gcs:send_text(2, "Hop: MOTORS OFF (" .. why .. ")")
end

local function update()
  local now = millis():tofloat()
  if now - last_beat >= 1000 then
    gcs:send_named_float("HOPG", P_ENABLE:get())
    last_beat = now
  end
  if P_ENABLE:get() < 1 or not arming:is_armed() then
    latched = false
    return update, PERIOD_MS
  end
  local pwm = rc:get_pwm(math.floor(P_CH:get()))
  if not latched then
    if pwm ~= nil and pwm >= HIGH_PWM then
      latched = true
      gcs:send_text(6, "Hop guard: hover on")
    end
    return update, PERIOD_MS
  end
  if pwm == nil or pwm < HIGH_PWM then
    kill("button released or link lost")
    return update, PERIOD_MS
  end
  local d = ahrs:get_relative_position_D_home()     -- m, down is positive
  if d ~= nil and -d > P_MAX:get() then
    kill(string.format("height %.2f m over %.2f m", -d, P_MAX:get()))
    return update, PERIOD_MS
  end
  local tilt = math.max(math.abs(math.deg(ahrs:get_roll_rad())), math.abs(math.deg(ahrs:get_pitch_rad())))
  if tilt > P_TILT:get() then
    kill(string.format("tilt %.0f deg", tilt))
  end
  return update, PERIOD_MS
end

gcs:send_text(6, "Hop guard on (HOP_CH " .. math.floor(P_CH:get()) .. ")")
return update, 1000
