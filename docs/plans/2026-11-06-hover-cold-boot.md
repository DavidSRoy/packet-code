# Box-camera hover controls and cold-boot origin

Replace the timed hover panel with Start hover, Land, immediate Emergency stop,
and bounded 1 cm X/Y/Z target adjustments. Preserve camera, drift, and link guards.

Restore and read back the EKF origin from a persisted box-test reference when a
fresh indoor boot has no GPS position. Do not mix coordinate pairs or treat the
reference as a current GPS fix. Preserve an existing FC origin. Remove the
simulator's pre-seeded origin so the actual startup path is tested.

Validate control contracts, missing/stale/wrong origin responses, Python and
browser syntax, the rendered panel, and a full cold-boot SITL hover. Verify only
origin setup on the physical FC while disarmed. No physical flight is authorized
by this maintenance task.
