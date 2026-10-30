-- sa_guard.lua: SA switch = permission for backend control (ArduCopter 4.7)
--
-- SA on  (channel SAG_CH high): the laptop/backend may fly pad-to-pad trips.
-- SA off (turned off while flying in AUTO, GUIDED or RTL): the drone stops
--   at once in BRAKE, which holds position and height and ignores the sticks.
--   When the pilot centers the throttle stick, the script changes to LOITER
--   and the pilot flies. (LOITER at once would follow the throttle stick,
--   which is often at the bottom during an automatic flight: the drone would
--   descend.)
--
-- It acts on the change from on to off, not on the switch position. A lost
-- radio link (failsafe) cannot look like "SA turned off", so failsafe
-- actions are not overridden. It works without the laptop, because it runs
-- on the Pixhawk.
--
-- The mode switch (SC) is off (tools/perma_loiter.parm): SA off is the radio takeover.

local TABLE_KEY = 75
assert(param:add_table(TABLE_KEY, "SAG_", 2), "SAG_ param table failed")
assert(param:add_param(TABLE_KEY, 1, "ENABLE", 1), "SAG_ENABLE")
assert(param:add_param(TABLE_KEY, 2, "CH", 5), "SAG_CH")  -- SA is CH5 on the Boxer; 0 = off

local P_ENABLE = Parameter("SAG_ENABLE")
local P_CH = Parameter("SAG_CH")

local MODE_AUTO, MODE_GUIDED, MODE_LOITER, MODE_RTL, MODE_LAND, MODE_BRAKE = 3, 4, 5, 6, 9, 17
local THR_MID_LO, THR_MID_HI = 1420, 1580   -- throttle stick "centered" (inside the LOITER deadzone)
local ON_PWM, OFF_PWM = 1700, 1300   -- hysteresis: between the two = no change
local PERIOD_MS = 50

local was_on = nil
local braking = false    -- we put the drone in BRAKE; waiting for a centered throttle
local last_tip = -1e9
local thr_ch = math.floor(param:get("RCMAP_THROTTLE") or 3)

local function throttle_centered()
  local pwm = rc:get_pwm(thr_ch)
  return pwm ~= nil and pwm >= THR_MID_LO and pwm <= THR_MID_HI
end

local function handover()
  -- called while braking: LOITER once the throttle is centered
  if not arming:is_armed() or vehicle:get_mode() ~= MODE_BRAKE then
    braking = false   -- landed, or the pilot already chose a mode
    return
  end
  if throttle_centered() then
    if vehicle:set_mode(MODE_LOITER) then
      gcs:send_text(4, "SA off: LOITER. Pilot has control")
      braking = false
    end
  elseif millis():tofloat() - last_tip > 3000 then
    last_tip = millis():tofloat()
    gcs:send_text(4, "SA off: BRAKE. Center throttle for LOITER")
  end
end

local function sa_state(chan)
  local pwm = rc:get_pwm(chan)
  if pwm == nil or pwm < 800 then return nil end
  if pwm > ON_PWM then return true end
  if pwm < OFF_PWM then return false end
  return was_on
end

local function update()
  local chan = math.floor(P_CH:get())
  if P_ENABLE:get() < 1 or chan < 1 or not rc:has_valid_input() then
    was_on = nil
    return update, 200
  end
  local on = sa_state(chan)
  if on == nil then return update, PERIOD_MS end
  if was_on == true and on == false and arming:is_armed() then
    local mode = vehicle:get_mode()
    if mode == MODE_AUTO or mode == MODE_GUIDED or mode == MODE_RTL or mode == MODE_BRAKE then
      if vehicle:set_mode(MODE_BRAKE) then
        braking = true
        last_tip = -1e9
        gcs:send_text(4, "SA off: backend control stopped, BRAKE")
      else
        vehicle:set_mode(MODE_LAND)
        gcs:send_text(2, "SA off: BRAKE refused, LAND")
      end
    end
  end
  if braking then handover() end
  if was_on ~= on then
    gcs:send_text(6, on and "SA on: backend control allowed" or "SA off: pilot only")
  end
  was_on = on
  return update, PERIOD_MS
end

local function protected()
  local ok, a, b = pcall(update)
  if not ok then
    gcs:send_text(3, "SA guard error: " .. tostring(a))
    return protected, 1000
  end
  return protected, b
end

gcs:send_text(6, "SA guard loaded")
return protected, 1000
