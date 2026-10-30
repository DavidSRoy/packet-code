-- Host test for the lights.lua delivery show with a mock of the ArduPilot scripting API.
-- Run from the packethw folder:  lua lua/test/lights_test.lua
local params = {}
local pwm = { [6] = 1000 }   -- SB top: status
local armed, clock = false, 0
local texts = {}
local px = {}                -- px[chan][led] = {r, g, b}

param = {
  add_table = function() return true end,
  add_param = function(_, _, _, name, default) params["LIT_" .. name] = default; return true end,
}
function Parameter(name)
  return { get = function() return params[name] end, set = function(_, v) params[name] = v end }
end
SRV_Channels = { find_channel = function(_, fn) return fn - 94 end }   -- Script1..4 on outputs 1..4
serialLED = {
  set_num_neopixel = function(_, c, n) px[c] = {}; for j = 0, n - 1 do px[c][j] = { 0, 0, 0 } end; return true end,
  set_RGB = function(_, c, j, r, g, b)
    if j < 0 then for k in pairs(px[c]) do px[c][k] = { r, g, b } end else px[c][j] = { r, g, b } end
  end,
  send = function() end,
}
rc = { get_pwm = function(_, ch) return pwm[ch] end }
LED = { get_rgb = function() return 0, 0, 40 end }   -- status: dim blue
arming = { is_armed = function() return armed end }
gcs = { send_text = function(_, _, t) table.insert(texts, t) end }
function millis() return { tofloat = function() return clock end } end

local step = dofile("lua/lights.lua")
local function tick(n) for _ = 1, (n or 1) do clock = clock + 50; step = step() or step end end
local function at(ms) clock = ms - 50; tick() end   -- one update at this show time
local function arm(c) local p = px[c][0]; return p[1], p[2], p[3] end
local function last_text() return texts[#texts] end

local fails = 0
local function check(name, cond)
  print((cond and "PASS " or "FAIL ") .. name)
  if not cond then fails = fails + 1 end
end

-- 1. No show: the SB mode (status colours)
tick(2)
check("SB top: status colours", last_text() == "Lights: status" and select(3, arm(1)) == 40)

-- 2. Show set while disarmed: plays right away
params.LIT_SHOW = 1
at(60000 + 1000)                                        -- rainbow spin
check("disarmed + LIT_SHOW: show", last_text() == "Lights: show")
local a = { arm(1) }; local b = { arm(2) }
check("spin: arms differ", a[1] ~= b[1] or a[2] ~= b[2] or a[3] ~= b[3])
at(60000 + 3500)                                        -- ripple: part of each arm lit
local hub, tip = px[1][0], px[1][7]
check("ripple: hub lit, tip dark", (hub[1] + hub[2] + hub[3]) > 0 and (tip[1] + tip[2] + tip[3]) == 0)
at(60000 + 4750)                                        -- green pulse peak
local r, g, bl = arm(3)
check("pulse: green only", r == 0 and bl == 0 and g > 200)
tick(200)
check("show loops (still on after 10 s)", last_text() == "Lights: show" and params.LIT_SHOW == 1)

-- 3. Arming (stick right) ends it and clears LIT_SHOW
armed = true; tick()
check("armed: back to SB mode", last_text() == "Lights: status")
check("armed: LIT_SHOW cleared", params.LIT_SHOW == 0)

-- 4. Set in flight: waits, never shows while armed, landing light stays steady
params.LIT_SHOW = 1; pwm[6] = 900; tick(40)
check("armed + LIT_SHOW: not cleared in flight", params.LIT_SHOW == 1)
r, g, bl = arm(2)
check("armed + landing: steady white, no show", last_text() == "Lights: landing" and r == 255 and g == 255 and bl == 255)

-- 5. Landing disarm (dl stick / auto LAND): show starts
armed = false; tick()
check("disarm after landing: show", last_text() == "Lights: show")

-- 6. Tap to stop from ground control
params.LIT_SHOW = 0; tick()
check("LIT_SHOW 0: back to SB mode", last_text() == "Lights: landing")

print(fails == 0 and "ALL PASS" or (fails .. " FAILED"))
os.exit(fails == 0 and 0 or 1)
