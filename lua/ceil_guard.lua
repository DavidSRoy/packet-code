-- ceil_guard.lua: automatic legal ceiling (max altitude fence) for ArduCopter 4.7
--
-- Ground control (ground_control/ceiling.py) sends two NAMED_VALUE_FLOAT
-- messages, 2 per second, from system id CEIL_GCS:
--   CEIL_SET  the fence for the drone's position, m above home (FENCE_ALT_MAX_TP = 1)
--   CEIL_FB   the fallback for a lost link, m above home: 400 ft above the
--             lowest ground within 3 km, under any Class B floor
--
-- The script sets FENCE_ALT_MAX in RAM (param:set, not saved), so the flash
-- memory is not written again and again.
--
-- Link lost (no CEIL_SET for CEIL_TOUT_S): it uses the lower of CEIL_FB and the
-- last CEIL_SET. With no data since boot it uses CEIL_DEF_M (400 ft minus margin).
--
-- It never puts the fence below the drone: when the drone is above the new
-- value, the fence stays CEIL_MARGIN (6 m) above the drone and comes down as the drone
-- descends, so a lower ceiling does not cause a sudden fence breach (and RTL).
-- The gap is CEIL_MARGIN plus 3 s of the climb rate when the hold starts.
--
-- Automatic descent (CEIL_DESCEND = 1): when the drone is more than 1 m above
-- the ceiling in flight, the script changes to GUIDED, holds the position and
-- descends to 2 m under the ceiling, then holds there in GUIDED. This replaces
-- the RTL that a fence breach would cause:
--   - modes it takes over: STABILIZE, ALT_HOLD, AUTO, GUIDED, LOITER, POSHOLD, BRAKE,
--     and an RTL that the altitude fence started;
--   - it does not interrupt a failsafe RTL, SMART_RTL or LAND;
--   - when the pilot changes the mode during the descent, the script stops
--     for 30 s (the pilot flies; the fence still stops a climb).
--
-- Reports to ground control (NAMED_VALUE_FLOAT, 1 Hz): CEIL_FC = fence now,
-- CEIL_ST = 0 following ground control, 1 link-loss fallback, 2 holding above
-- the ceiling (descend), -1 off.

local TABLE_KEY = 78
assert(param:add_table(TABLE_KEY, "CEIL_", 6), "CEIL_ param table failed")
assert(param:add_param(TABLE_KEY, 1, "ENABLE", 1), "CEIL_ENABLE")
assert(param:add_param(TABLE_KEY, 2, "DEF_M", 100), "CEIL_DEF_M")     -- no data since boot: 400 ft - 22 m margin
assert(param:add_param(TABLE_KEY, 3, "TOUT_S", 5), "CEIL_TOUT_S")
assert(param:add_param(TABLE_KEY, 4, "MARGIN", 6), "CEIL_MARGIN")     -- m between the drone and a held fence
assert(param:add_param(TABLE_KEY, 5, "GCS", 254), "CEIL_GCS")         -- system id of ground control
assert(param:add_param(TABLE_KEY, 6, "DESCEND", 1), "CEIL_DESCEND")   -- 1 = descend to the ceiling, not RTL

local P_ENABLE = Parameter("CEIL_ENABLE")
local P_DEF = Parameter("CEIL_DEF_M")
local P_TOUT = Parameter("CEIL_TOUT_S")
local P_MARGIN = Parameter("CEIL_MARGIN")
local P_GCS = Parameter("CEIL_GCS")
local P_DESCEND = Parameter("CEIL_DESCEND")
local P_FENCE = Parameter("FENCE_ALT_MAX")

local NVF_ID = 251                 -- NAMED_VALUE_FLOAT
local FENCE_MIN, FENCE_MAX = 10, 1000
local PERIOD_MS = 100
local MODE_GUIDED, MODE_RTL = 4, 6
-- STABILIZE, ALT_HOLD, AUTO, GUIDED, LOITER, POSHOLD, BRAKE
local TAKE_OVER = { [0] = true, [2] = true, [3] = true, [4] = true, [5] = true, [16] = true, [17] = true }
local FENCE_ALT_BIT = 1            -- AC_FENCE_TYPE_ALT_MAX
local BELOW_M = 2                  -- descend to this far under the ceiling
local PAUSE_MS = 30000             -- after a pilot mode change

mavlink:init(8, 1)
mavlink:register_rx_msgid(NVF_ID)

local target, fallback = nil, nil
local last_set = nil               -- millis of the last CEIL_SET
local lost_cap = nil               -- last CEIL_SET when the link was lost
local was_fresh = false
local next_report, next_tip = 0, 0
local state = -1
local descending = false
local pause_until = 0
local next_target = 0

-- The binding gives the C struct mavlink_message_t: checksum(2) magic(1) len(1)
-- incompat(1) compat(1) seq(1) sysid(1) compid(1) msgid(3), then the payload.
-- MAVLink2 cuts trailing zero bytes, so pad the payload back to full size.
local function decode_nvf(msg)
  if #msg < 13 then return nil end
  local len = string.byte(msg, 4)
  local sysid = string.byte(msg, 8)
  local msgid = string.unpack("<I3", msg, 10)
  if msgid ~= NVF_ID then return nil end
  local payload = string.sub(msg, 13, 12 + len) .. string.rep("\0", 18)
  local _, value, name = string.unpack("<I4fc10", payload)
  return sysid, (string.gsub(name, "\0", "")), value
end

local function read_messages()
  local gcs_id = math.floor(P_GCS:get())
  for _ = 1, 8 do
    local msg = mavlink:receive_chan()
    if not msg then return end
    local sysid, name, value = decode_nvf(msg)
    if sysid == gcs_id and value == value then        -- value == value: not NaN
      if name == "CEIL_SET" then
        target = value
        last_set = millis():tofloat()
      elseif name == "CEIL_FB" then
        fallback = value
      end
    end
  end
end

-- GUIDED descent to the ceiling (replaces the fence RTL)
local function descend(now, goal, h, over)
  if not descending and (over == nil or over <= 1) then return end
  if descending and (over == nil or over <= 0.5) then
    descending = false
    gcs:send_text(5, string.format("CEIL: at the legal height (%.0f m), holding", goal - BELOW_M))
    return
  end
  if P_DESCEND:get() < 1 or not vehicle:get_likely_flying() or now < pause_until then return end
  local mode = vehicle:get_mode()
  local fence_rtl = mode == MODE_RTL and (fence:get_breaches() & FENCE_ALT_BIT) ~= 0
  if descending and mode ~= MODE_GUIDED and not fence_rtl then
    descending = false                     -- the pilot (or a failsafe) chose a mode: do not fight it
    pause_until = now + PAUSE_MS
    gcs:send_text(4, "CEIL: mode changed, auto descent paused 30 s")
    return
  end
  if not (TAKE_OVER[mode] or fence_rtl) then return end
  if mode ~= MODE_GUIDED and not vehicle:set_mode(MODE_GUIDED) then return end
  if not descending then
    descending = true
    next_target = 0
    gcs:send_text(4, string.format("CEIL: %.0f m too high, descend to %.0f m", over, goal - BELOW_M))
  end
  if now >= next_target then
    next_target = now + 1000
    local loc = ahrs:get_location()
    if loc and loc:change_alt_frame(1) then          -- 1 = above home
      loc:alt(math.floor((goal - BELOW_M) * 100))
      vehicle:set_target_location(loc)
    end
  end
end

local function update()
  read_messages()
  if P_ENABLE:get() < 1 then
    state = -1
    return update, 1000
  end
  local now = millis():tofloat()
  local fresh = last_set ~= nil and now - last_set < P_TOUT:get() * 1000
  local goal
  if fresh then
    goal, state, lost_cap = target, 0, nil
    if not was_fresh then gcs:send_text(6, string.format("CEIL: ground control ceiling %.0f m", goal)) end
  else
    local fb = fallback
    if fb == nil or fb <= 0 then fb = P_DEF:get() end
    if lost_cap == nil then lost_cap = target or fb end
    goal, state = math.min(fb, lost_cap), 1
    if was_fresh then gcs:send_text(4, string.format("CEIL: link lost, fallback ceiling %.0f m", goal)) end
  end
  was_fresh = fresh
  goal = math.max(FENCE_MIN, math.min(FENCE_MAX, goal))

  local cur = P_FENCE:get()
  local new = goal
  local over = nil
  local h = nil
  if arming:is_armed() then
    local d = ahrs:get_relative_position_D_home()
    if d then
      h = -d                        -- metres down from home -> height
      -- room for height noise and for the climb that is still going on (3 s of climb rate)
      local margin = P_MARGIN:get()
      local v = ahrs:get_velocity_NED()
      if v then margin = margin + math.max(0, -v:z()) * 3 end
      if h + margin > goal then
        if descending then
          new = math.max(goal, h + margin)    -- follow the drone down; no breach during the descent
        else
          new = math.max(goal, math.min(cur, h + margin))
        end
        over = h - goal
        state = 2
      end
    end
  else
    descending = false
  end
  descend(now, goal, h, over)
  new = math.max(FENCE_MIN, math.min(FENCE_MAX, new))
  if math.abs(new - cur) > 0.25 then
    param:set("FENCE_ALT_MAX", new)
  end
  if over and over > 1 and not descending and now >= next_tip then
    next_tip = now + 10000
    gcs:send_text(4, string.format("CEIL: %.0f m above the legal ceiling, descend", over))
  end
  if now >= next_report then
    next_report = now + 1000
    gcs:send_named_float("CEIL_FC", new)
    gcs:send_named_float("CEIL_ST", state)
  end
  return update, PERIOD_MS
end

local function protected()
  local ok, a, b = pcall(update)
  if not ok then
    gcs:send_text(3, "CEIL guard error: " .. tostring(a))
    return protected, 1000
  end
  return protected, b
end

gcs:send_text(6, "CEIL guard loaded")
return protected, 1000
