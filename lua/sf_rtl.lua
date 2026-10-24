-- sf_rtl.lua: SF button = return to home and land (ArduCopter 4.7)
--
-- Hold SF (a spring button on the Boxer, CH10) for SFR_HOLD ms while armed:
-- the drone changes to RTL. It climbs to RTL_ALT, flies back to home (the pad
-- where it armed) and lands. Release the button before the next press.
--
-- The built-in RTL switch (RCx_OPTION = 4) does not work with a button: it
-- leaves RTL again when the button goes back up. This script latches RTL.
-- To take control back during RTL, move the mode switch (SC).

local TABLE_KEY = 77
assert(param:add_table(TABLE_KEY, "SFR_", 3), "SFR_ param table failed")
assert(param:add_param(TABLE_KEY, 1, "ENABLE", 1), "SFR_ENABLE")
assert(param:add_param(TABLE_KEY, 2, "CH", 10), "SFR_CH")        -- SF is CH10 on the Boxer
assert(param:add_param(TABLE_KEY, 3, "HOLD", 500), "SFR_HOLD")   -- ms the button must be held

local P_ENABLE = Parameter("SFR_ENABLE")
local P_CH = Parameter("SFR_CH")
local P_HOLD = Parameter("SFR_HOLD")

local MODE_RTL, MODE_LAND = 6, 9
local PRESS_PWM = 1700
local PERIOD_MS = 50

local pressed_at = nil   -- time the button went down
local fired = false      -- already acted on this press

local function update()
  local chan = math.floor(P_CH:get())
  if P_ENABLE:get() < 1 or chan < 1 or not rc:has_valid_input() then
    pressed_at, fired = nil, false
    return update, 200
  end
  local pwm = rc:get_pwm(chan)
  local down = pwm ~= nil and pwm > PRESS_PWM
  local now = millis():tofloat()
  if not down then
    pressed_at, fired = nil, false
    return update, PERIOD_MS
  end
  if pressed_at == nil then pressed_at = now end
  if not fired and now - pressed_at >= P_HOLD:get() then
    fired = true
    if not arming:is_armed() then
      gcs:send_text(6, "SF: not armed, no RTL")
    else
      local mode = vehicle:get_mode()
      if mode == MODE_RTL or mode == MODE_LAND then
        gcs:send_text(6, "SF: already returning or landing")
      elseif vehicle:set_mode(MODE_RTL) then
        gcs:send_text(4, "SF: RTL, return home and land")
      else
        vehicle:set_mode(MODE_LAND)
        gcs:send_text(2, "SF: RTL refused, LAND here")
      end
    end
  end
  return update, PERIOD_MS
end

local function protected()
  local ok, a, b = pcall(update)
  if not ok then
    gcs:send_text(3, "SF RTL error: " .. tostring(a))
    return protected, 1000
  end
  return protected, b
end

gcs:send_text(6, "SF RTL button loaded")
return protected, 1000
