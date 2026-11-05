-- sd_guard.lua: height-gated SD motor kill for Packet V0 (ArduCopter 4.7)
--
-- Set RC8_OPTION = 0. This script then owns the SD switch and runs the
-- built-in Motor Emergency Stop (aux function 31) itself.
--
-- SD to stop cuts the motors when ANY of these is true:
--   * the drone is disarmed (SD on stop then blocks arming, as before)
--   * height above home is under SDG_ALT (takeoff, landing, ground)
--   * tilt is over SDG_TILT (out of control, e.g. a flip)
--   * SE is also on (channel SDG_SE_CH): the two-switch kill at any height
-- Otherwise SD is BLOCKED: motors keep running and a warning is sent.
-- A blocked SD does not fire later when the drone comes down. Put SD back
-- to run, then to stop again. Tilt and SE still work while SD is blocked.
--
-- If this script hits an error, it sets RC8_OPTION back to 31, so SD
-- becomes the plain, always-on kill switch again.

local TABLE_KEY = 74
assert(param:add_table(TABLE_KEY, "SDG_", 5), "SDG_ param table failed")
assert(param:add_param(TABLE_KEY, 1, "ENABLE", 1), "SDG_ENABLE")
assert(param:add_param(TABLE_KEY, 2, "ALT", 2.0), "SDG_ALT")    -- m
assert(param:add_param(TABLE_KEY, 3, "TILT", 60), "SDG_TILT")   -- deg
assert(param:add_param(TABLE_KEY, 4, "SE_CH", 9), "SDG_SE_CH")  -- SE is CH9 on the Boxer; 0 = no SE combo
assert(param:add_param(TABLE_KEY, 5, "SD_CH", 8), "SDG_SD_CH")

local P_ENABLE = Parameter("SDG_ENABLE")
local P_ALT = Parameter("SDG_ALT")
local P_TILT = Parameter("SDG_TILT")
local P_SE_CH = Parameter("SDG_SE_CH")
local P_SD_CH = Parameter("SDG_SD_CH")

local AUX_MOTOR_ESTOP = 31
local HIGH, LOW = 2, 0
local SWITCH_ON_PWM = 1700
local PERIOD_MS = 20

local estop = nil        -- last state sent to the E-stop function
local blocked = false    -- SD went to stop while not allowed by height
local last_warn = -1e9   -- first warning goes out at once

local function switch_on(chan)
  if chan <= 0 then return false end
  local pwm = rc:get_pwm(chan)
  return pwm ~= nil and pwm > SWITCH_ON_PWM
end

local function set_estop(on)
  if estop == on then return end
  rc:run_aux_function(AUX_MOTOR_ESTOP, on and HIGH or LOW)
  estop = on
end

local function update()
  if P_ENABLE:get() < 1 then
    param:set("RC8_OPTION", 31)
    gcs:send_text(4, "SD guard off: SD is the plain kill switch")
    return false  -- stop the script; RC8_OPTION=31 handles SD from now on
  end

  local sd = switch_on(math.floor(P_SD_CH:get()))
  if not sd then
    blocked = false
    set_estop(false)
    return true
  end

  if not arming:is_armed() then
    set_estop(true)  -- arming lock, same as the plain E-stop
    return true
  end

  local d = ahrs:get_relative_position_D_home()
  local height = d and -d or 0  -- no home yet: treat as on the ground
  local tilt = math.deg(math.max(math.abs(ahrs:get_roll_rad()), math.abs(ahrs:get_pitch_rad())))
  local se = switch_on(math.floor(P_SE_CH:get()))

  local low = height < P_ALT:get()
  local wild = tilt > P_TILT:get()

  if estop then
    return true  -- already cut; stays cut until SD goes to run
  end
  if wild or se or (low and not blocked) then
    set_estop(true)
    gcs:send_text(2, string.format("SD KILL: h %.1f m tilt %.0f%s", height, tilt, se and " +SE" or ""))
    return true
  end

  blocked = true
  local now = millis():tofloat()
  if now - last_warn > 2000 then
    last_warn = now
    gcs:send_text(2, string.format("SD blocked at %.1f m: SD to run, or SE+SD to kill", height))
  end
  return true
end

local function protected()
  local ok, result = pcall(update)
  if ok then
    if result then
      return protected, PERIOD_MS
    end
    return
  end
  param:set("RC8_OPTION", 31)
  gcs:send_text(0, "SD guard ERROR, SD is plain kill switch: " .. tostring(result))
  return  -- stop; RC8_OPTION=31 keeps SD working
end

gcs:send_text(6, string.format("SD guard on: SD kills below %.1f m or over %.0f deg", P_ALT:get(), P_TILT:get()))
return protected, 1000
