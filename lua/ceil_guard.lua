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
-- The pilot gets a message to descend.
--
-- Reports to ground control (NAMED_VALUE_FLOAT, 1 Hz): CEIL_FC = fence now,
-- CEIL_ST = 0 following ground control, 1 link-loss fallback, 2 holding above
-- the ceiling (descend), -1 off.

local TABLE_KEY = 78
assert(param:add_table(TABLE_KEY, "CEIL_", 5), "CEIL_ param table failed")
assert(param:add_param(TABLE_KEY, 1, "ENABLE", 1), "CEIL_ENABLE")
assert(param:add_param(TABLE_KEY, 2, "DEF_M", 100), "CEIL_DEF_M")     -- no data since boot: 400 ft - 22 m margin
assert(param:add_param(TABLE_KEY, 3, "TOUT_S", 5), "CEIL_TOUT_S")
assert(param:add_param(TABLE_KEY, 4, "MARGIN", 6), "CEIL_MARGIN")     -- m between the drone and a held fence
assert(param:add_param(TABLE_KEY, 5, "GCS", 254), "CEIL_GCS")         -- system id of ground control

local P_ENABLE = Parameter("CEIL_ENABLE")
local P_DEF = Parameter("CEIL_DEF_M")
local P_TOUT = Parameter("CEIL_TOUT_S")
local P_MARGIN = Parameter("CEIL_MARGIN")
local P_GCS = Parameter("CEIL_GCS")
local P_FENCE = Parameter("FENCE_ALT_MAX")

local NVF_ID = 251                 -- NAMED_VALUE_FLOAT
local FENCE_MIN, FENCE_MAX = 10, 1000
local PERIOD_MS = 100

mavlink:init(8, 1)
mavlink:register_rx_msgid(NVF_ID)

local target, fallback = nil, nil
local last_set = nil               -- millis of the last CEIL_SET
local lost_cap = nil               -- last CEIL_SET when the link was lost
local was_fresh = false
local next_report, next_tip = 0, 0
local state = -1

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
  if arming:is_armed() then
    local d = ahrs:get_relative_position_D_home()
    if d then
      local h = -d                  -- metres down from home -> height
      -- room for height noise and for the climb that is still going on (3 s of climb rate)
      local margin = P_MARGIN:get()
      local v = ahrs:get_velocity_NED()
      if v then margin = margin + math.max(0, -v:z()) * 3 end
      if h + margin > goal then
        new = math.max(goal, math.min(cur, h + margin))
        over = h - goal
        state = 2
      end
    end
  end
  new = math.max(FENCE_MIN, math.min(FENCE_MAX, new))
  if math.abs(new - cur) > 0.25 then
    param:set("FENCE_ALT_MAX", new)
  end
  if over and over > 0 and now >= next_tip then
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
