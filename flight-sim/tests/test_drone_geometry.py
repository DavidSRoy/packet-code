import lid_camera_sim as oracle

from flightsim import drone_geometry as dg


def test_dimensions_match_the_oracle():
    assert dg.BOXES_MM == oracle.BOXES
    assert dg.LID_TOP_Z_MM == oracle.LID_TOP_Z
    assert dg.LID_SIZE_MM == (oracle.LID_W, oracle.LID_H)
    assert dg.LEG_R_MM == oracle.LEG_R
    assert dg.CAMERA_MOUNT_MM == (70.0, 95.0, -100.0)
    assert oracle.MOUNTS["D side-out (70,95,-100)"] == dg.CAMERA_MOUNT_MM


def test_nothing_is_above_the_lens_and_the_plate_is_dropped():
    bounds = dg.drone_bounds_mm()
    assert all(b[5] <= -103.0 for b in bounds.values())
    assert "FR-004 battery plate" not in bounds
    assert sum(n.startswith("leg left") for n in bounds) == sum(n.startswith("leg right") for n in bounds) == 16


def test_camera_frame_puts_the_left_jaw_edge_right_of_the_lens_and_ahead():
    jaw = next(c for c in dg.camera_frame_cuboids() if c.name == "RP-019 jaw 2")
    # drone x 'nose' range -65..126.8 around mount x 70 -> camera y -0.135..0.0568 m, size 0.1918
    assert abs(jaw.centre_m[1] - (-65.0 + 126.8 - 140.0) / 2000.0) < 1e-12
    assert abs(jaw.size_m[1] - 0.1918) < 1e-12
    # drone y -34.9..60 with the lens at y 95: image right = drone right = -y, so x_c = 95 - y -> 35..129.9 mm
    assert abs(jaw.centre_m[0] - (0.035 + 0.1299) / 2) < 1e-9
