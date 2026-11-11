"""Provisional absolute-motion gate, not a validated human perception model."""
import math

def meets_target(position_ptp_mm, angle_ptp_deg, hold_s):
    """At least 20 s; every XYZ axis <2 mm and roll/pitch/yaw axis <0.1 deg."""
    if len(position_ptp_mm) != 3 or len(angle_ptp_deg) != 3:
        return False
    values = [*position_ptp_mm, *angle_ptp_deg, hold_s]
    if not all(isinstance(x, (int, float)) and math.isfinite(x) and x >= 0 for x in values):
        return False
    return hold_s >= 20 and max(position_ptp_mm) < 2 and max(angle_ptp_deg) < .1
