-- Host test for sd_guard.lua with a mock of the ArduPilot scripting API.
-- Run from the packethw folder:  lua lua/test/sd_guard_test.lua
local params = { RC8_OPTION = 0 }
local pwm = { [8] = 1000, [9] = 1000 }
local armed, down, roll, pitch, clock = false, 0.0, 0.0, 0.0, 0
local estop_calls, texts = {}, {}

param = {
  add_table = function() return true end,
  add_param = function(_, _, _, name, default) params["SDG_" .. name] = default; return true end,
  set = function(_, name, v) params[name] = v; return true end,
}
function Parameter(name) return { get = function() return params[name] end } end
rc = {
  get_pwm = function(_, ch) return pwm[ch] end,
  run_aux_function = function(_, fn, flag) table.insert(estop_calls, { fn, flag }) end,
}
arming = { is_armed = function() return armed end }
ahrs = {
  get_relative_position_D_home = function() return down end,
  get_roll_rad = function() return math.rad(roll) end,
  get_pitch_rad = function() return math.rad(pitch) end,
}
gcs = { send_text = function(_, sev, t) table.insert(texts, t) end }
function millis() return { tofloat = function() return clock end } end

local step = dofile("lua/sd_guard.lua")
local function tick(n)
  for _ = 1, (n or 1) do clock = clock + 20; step = step() or step end
end
local function last_estop() local c = estop_calls[#estop_calls]; return c and c[2] end

local fails = 0
local function check(name, cond)
  print((cond and "PASS " or "FAIL ") .. name)
  if not cond then fails = fails + 1 end
end

-- 1. Disarmed, SD stop -> E-stop on (arming lock); SD run -> off
pwm[8] = 2000; tick()
check("disarmed: SD stop sets E-stop", last_estop() == 2)
pwm[8] = 1000; tick()
check("disarmed: SD run clears E-stop", last_estop() == 0)

-- 2. Armed at 1 m: SD kills
armed, down = true, -1.0
pwm[8] = 2000; tick()
check("armed 1 m: SD kills", last_estop() == 2)
pwm[8] = 1000; tick()

-- 3. Armed at 10 m, level: SD blocked, warning sent
down = -10.0; local n = #estop_calls
pwm[8] = 2000; tick(5)
check("10 m level: SD blocked (no E-stop)", #estop_calls == n)
check("10 m: warning text sent", texts[#texts]:find("blocked") ~= nil)

-- 4. Blocked SD must not fire when the drone descends below 2 m
down = -1.0; tick(5)
check("blocked SD does not fire on descent", #estop_calls == n)

-- 5. Cycling SD at 1 m kills
pwm[8] = 1000; tick(); pwm[8] = 2000; tick()
check("SD cycled at 1 m kills", last_estop() == 2)
pwm[8] = 1000; tick()

-- 6. At 10 m, SD + tilt 70 deg kills
down, roll = -10.0, 70; pwm[8] = 2000; tick()
check("10 m tilt 70: SD kills", last_estop() == 2)
pwm[8] = 1000; roll = 0; tick()

-- 7. At 10 m, SE combo (SE on CH9) kills; SE alone does nothing
params.SDG_SE_CH = 9; n = #estop_calls
pwm[9] = 2000; tick(3)
check("SE alone does nothing", #estop_calls == n)
pwm[8] = 2000; tick()
check("10 m SE+SD kills", last_estop() == 2)
pwm[8], pwm[9] = 1000, 1000; tick()

-- 8. Blocked SD, then SE pressed -> kills
pwm[8] = 2000; tick(3); n = #estop_calls
pwm[9] = 2000; tick()
check("blocked SD then SE kills", last_estop() == 2 and #estop_calls == n + 1)
pwm[8], pwm[9] = 1000, 1000; tick()

-- 9. SDG_ENABLE = 0 restores RC8_OPTION = 31 and stops
params.SDG_ENABLE = 0; tick()
check("disable restores RC8_OPTION=31", params.RC8_OPTION == 31)

print(fails == 0 and "ALL PASS" or (fails .. " FAILED"))
os.exit(fails == 0 and 0 or 1)
