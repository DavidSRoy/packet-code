#!/usr/bin/env python3
"""Write the control/EKF/vision parameters flown in a dataflash log as a .parm for the simulator.
  python tools/sim/hover/extract_parm.py LOG.BIN OUT.parm
Calibration offsets, sensor IDs and hardware-only settings are left out."""
import sys
from pymavlink import mavutil

KEEP = ("ATC_", "PSC_", "INS_", "EK3_", "VISO_", "MOT_", "WPNAV_", "LOIT_", "GUID_", "LAND_", "HTO_", "HOP_",
        "ANGLE_MAX", "FRAME_", "RC_OVERRIDE_TIME", "DISARM_DELAY", "SCHED_LOOP_RATE", "LOG_BITMASK",
        "LOG_DISARMED", "LOG_FILE_DSRMROT", "ARMING_", "FS_", "AHRS_EKF_TYPE", "EK2_ENABLE", "COMPASS_USE")
DROP = ("INS_ACC1OFFS", "INS_ACC2OFFS", "INS_ACC3OFFS", "INS_ACCOFFS", "INS_ACC2SCAL", "INS_ACC3SCAL",
        "INS_ACCSCAL", "INS_ACC1SCAL", "INS_GYROFFS", "INS_GYR2OFFS", "INS_GYR3OFFS", "INS_GYR1OFFS",
        "INS_ACC_ID", "INS_ACC2_ID", "INS_ACC3_ID", "INS_GYR_ID", "INS_GYR2_ID", "INS_GYR3_ID", "INS_TCAL",
        "INS_ACC1_CALTEMP", "INS_ACC2_CALTEMP", "INS_ACC3_CALTEMP", "INS_GYR1_CALTEMP", "INS_GYR2_CALTEMP",
        "INS_GYR3_CALTEMP", "INS_ACC_CALTEMP", "INS_GYR_CALTEMP", "MOT_PWM_TYPE", "FS_THR", "INS_ACC4",
        "INS_GYR4", "INS_ACC5", "INS_GYR5")
m = mavutil.mavlink_connection(sys.argv[1])
P = {}
while True:
    x = m.recv_match(type="PARM")
    if x is None:
        break
    P[x.Name] = x.Value
rows = sorted((k, v) for k, v in P.items() if k.startswith(KEEP) and not k.startswith(DROP))
with open(sys.argv[2], "w") as f:
    f.write(f"# Parameters flown in {sys.argv[1].split('/')[-1]}, filtered to control/EKF/vision.\n")
    f.writelines(f"{k},{v:.7g}\n" for k, v in rows)
print(len(rows), "params ->", sys.argv[2])
