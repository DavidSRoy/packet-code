-- lights.lua: arm LED strips on the SB switch (ArduCopter 4.7)
--
--   SB top    (low PWM):  ArduPilot status lights (the normal notify colours)
--   SB middle:            aviation lights, to see where the drone is and
--                         where it points at night:
--                           front-left arm  red   (left side, like an aircraft)
--                           front-right arm green (right side)
--                           rear arms       white (tail light)
--                           all arms: white double flash each second (anti-collision)
--   SB bottom (high PWM): off
--   800..969 (ground control only, CH6 override 900): below the 988..2012 us
--   CRSF range, so the Boxer cannot send it (unless EdgeTX extended limits are on
--   for this model; the FC logs show the SB at 999 / 1503 / 2000 us). Landing light for the box camera at night: all arms
--   steady white at LIT_BRT. White gives the white sticker paper the most
--   brightness and leaves the black tag cells dark, and the detector uses only
--   brightness (the camera Y plane). Steady, because a flash makes moving
--   bright bands in the camera picture (rolling shutter, seen 2026-10-25).
--
-- Setup: SERVO9..12_FUNCTION = 94..97 (Script1..4), one LED strip each.
-- LIT_FL/FR/RL/RR say which Script output is on which arm (1..4).
-- NTF_LED_TYPES must include Scripting (bit 10) for the status colours.

local TABLE_KEY = 76
assert(param:add_table(TABLE_KEY, "LIT_", 8), "LIT_ param table failed")
assert(param:add_param(TABLE_KEY, 1, "CH", 6), "LIT_CH")       -- SB is CH6 on the Boxer
assert(param:add_param(TABLE_KEY, 2, "LEN", 8), "LIT_LEN")     -- LEDs on each strip
assert(param:add_param(TABLE_KEY, 3, "BRT", 255), "LIT_BRT")   -- aviation light brightness 0..255
assert(param:add_param(TABLE_KEY, 4, "FL", 2), "LIT_FL")       -- Script output on the front-left arm (Packet V0 wiring)
assert(param:add_param(TABLE_KEY, 5, "FR", 4), "LIT_FR")
assert(param:add_param(TABLE_KEY, 6, "RL", 3), "LIT_RL")
assert(param:add_param(TABLE_KEY, 7, "RR", 1), "LIT_RR")
assert(param:add_param(TABLE_KEY, 8, "TEST", 0), "LIT_TEST")   -- 1 = identify: 1 red, 2 green, 3 blue, 4 white

local P = {}
for _, n in ipairs({ "CH", "LEN", "BRT", "FL", "FR", "RL", "RR", "TEST" }) do P[n] = Parameter("LIT_" .. n) end

local SCRIPT_FN = { 94, 95, 96, 97 }   -- Script1..4
local PERIOD_MS = 50

-- output channel (1..16) for each Script output, or nil
local chans = {}
local len = math.floor(P.LEN:get())
for i, fn in ipairs(SCRIPT_FN) do
  local c = SRV_Channels:find_channel(fn)
  if c then
    chans[i] = c + 1
    assert(serialLED:set_num_neopixel(chans[i], len), "LED setup failed on output " .. tostring(c + 1))
  end
end

local last_mode = nil

local function fill(i, r, g, b)
  local c = chans[i]
  if c then serialLED:set_RGB(c, -1, r, g, b) end
end

local function send_all()
  for i = 1, 4 do
    if chans[i] then serialLED:send(chans[i]) end
  end
end

local function sb_mode()
  local pwm = rc:get_pwm(math.floor(P.CH:get()))
  if pwm == nil or pwm < 800 then return "status" end   -- no RC: keep the safe default
  if pwm < 970 then return "landing" end                -- ground control only (below the CRSF range)
  if pwm < 1300 then return "status" end
  if pwm < 1700 then return "aviation" end
  return "off"
end

local function arm_index(name)
  local v = math.floor(P[name]:get())
  if v >= 1 and v <= 4 then return v end
  return nil
end

local function aviation(now)
  local br = math.max(0, math.min(255, math.floor(P.BRT:get())))
  local t = now % 1000
  local flash = (t < 50) or (t >= 150 and t < 200)   -- double flash each second
  local fl, fr, rl, rr = arm_index("FL"), arm_index("FR"), arm_index("RL"), arm_index("RR")
  local w = math.floor(br * 0.6)
  if fl then fill(fl, br, 0, 0) end
  if fr then fill(fr, 0, br, 0) end
  if rl then fill(rl, w, w, w) end
  if rr then fill(rr, w, w, w) end
  if flash then
    for i = 1, 4 do fill(i, 255, 255, 255) end
  end
end

local function update()
  local now = millis():tofloat()
  if P.TEST:get() >= 1 then
    fill(1, 255, 0, 0); fill(2, 0, 255, 0); fill(3, 0, 0, 255); fill(4, 255, 255, 255)
    send_all()
    return update, 200
  end
  local mode = sb_mode()
  if mode ~= last_mode then
    gcs:send_text(6, "Lights: " .. mode)
    last_mode = mode
  end
  if mode == "status" then
    local r, g, b = LED:get_rgb()
    for i = 1, 4 do fill(i, r or 0, g or 0, b or 0) end
  elseif mode == "aviation" then
    aviation(now)
  elseif mode == "landing" then
    local br = math.max(0, math.min(255, math.floor(P.BRT:get())))
    for i = 1, 4 do fill(i, br, br, br) end
  else
    for i = 1, 4 do fill(i, 0, 0, 0) end
  end
  send_all()
  return update, PERIOD_MS
end

local function protected()
  local ok, a, b = pcall(update)
  if not ok then
    gcs:send_text(3, "Lights error: " .. tostring(a))
    return protected, 1000
  end
  return protected, b
end

local n = 0
for i = 1, 4 do if chans[i] then n = n + 1 end end
gcs:send_text(6, string.format("Lights loaded: %d strips", n))
return protected, 500
