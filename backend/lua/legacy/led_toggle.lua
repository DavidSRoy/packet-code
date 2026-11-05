-- Arm lights on/off from a momentary RC button.
-- Each press (channel goes high) toggles the lights. Lights start on at boot.
local CHANNEL = 10
local ON_BRIGHT = 3   -- NTF_LED_BRIGHT: 0 off, 1 low, 2 medium, 3 high
local lights_on = true
local was_pressed = false

param:set('NTF_LED_BRIGHT', ON_BRIGHT)

local function update()
  local pwm = rc:get_pwm(CHANNEL)
  local pressed = pwm ~= nil and pwm > 1700
  if pressed and not was_pressed then
    lights_on = not lights_on
    param:set('NTF_LED_BRIGHT', lights_on and ON_BRIGHT or 0)
    gcs:send_text(6, string.format('Lights %s', lights_on and 'ON' or 'OFF'))
  end
  was_pressed = pressed
  return update, 100
end

return update, 1000
