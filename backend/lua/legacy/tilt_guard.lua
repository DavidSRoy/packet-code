-- Bench-test tilt guard. Only active while SCR_USER1 = 1.
-- While armed, disarms the instant roll or pitch exceeds SCR_USER2 degrees (default 4).
local active_last = false

local function update()
  local active = param:get('SCR_USER1') == 1
  if active ~= active_last then
    gcs:send_text(6, active and 'Tilt guard ACTIVE' or 'Tilt guard off')
    active_last = active
  end
  if active and arming:is_armed() then
    local limit = param:get('SCR_USER2')
    if not limit or limit <= 0 then
      limit = 4
    end
    local roll = math.abs(math.deg(ahrs:get_roll_rad()))
    local pitch = math.abs(math.deg(ahrs:get_pitch_rad()))
    if roll > limit or pitch > limit then
      arming:disarm()
      gcs:send_text(2, string.format('Tilt guard KILL roll %.1f pitch %.1f', math.deg(ahrs:get_roll_rad()), math.deg(ahrs:get_pitch_rad())))
    end
  end
  return update, 10
end

return update, 1000
