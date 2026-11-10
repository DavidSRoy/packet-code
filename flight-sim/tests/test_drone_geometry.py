import json
from pathlib import Path

import lid_camera_sim as oracle
import numpy as np

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


def test_mesh_has_outward_faces_and_the_cuboid_bounds():
    import numpy as np

    cuboids = dg.camera_frame_cuboids()
    points, counts, indices, normals = dg.cuboids_mesh(cuboids)
    assert len(points) == 24 * len(cuboids) == len(normals) and (counts == 4).all() and len(indices) == len(points)
    for i, c in enumerate(cuboids):
        p = points[24 * i:24 * (i + 1)]
        np.testing.assert_allclose(p.max(0) - p.min(0), c.size_m, atol=1e-12)
        np.testing.assert_allclose((p.max(0) + p.min(0)) / 2, c.centre_m, atol=1e-12)
        for f in range(6):  # winding matches the stored normal and points away from the centre
            quad = p[4 * f:4 * f + 4]
            wound = np.cross(quad[1] - quad[0], quad[2] - quad[1])
            assert wound @ normals[24 * i + 4 * f] > 0
            assert (quad.mean(0) - np.array(c.centre_m)) @ normals[24 * i + 4 * f] > 0


MODEL = Path(__file__).resolve().parents[2] / "backend" / "tools" / "sim" / "hover" / "model.json"


def test_mount_from_the_physics_model_is_the_drone_frame_lens_position():
    # model.json camera.cam_pos is body FRD (x nose, y right, z down); the oracle frame is x nose, y left, z up
    assert dg.mount_mm_from_cam_pos((0.127, -0.001, 0.101)) == (127.0, 1.0, -101.0)
    fwd, right, down = json.loads(MODEL.read_text())["camera"]["cam_pos"]
    assert dg.mount_mm_from_model(MODEL) == (fwd * 1000.0, -right * 1000.0, -down * 1000.0)


def test_occluders_sit_where_the_oracle_draws_them_for_the_physics_model_mount():
    mount = dg.mount_mm_from_model(MODEL)
    bounds = dg.drone_bounds_mm(mount)
    cuboids = {c.name: c for c in dg.camera_frame_cuboids(mount)}
    assert set(bounds) == set(cuboids)
    r_cd = oracle.CAM_IN_DRONE                       # oracle camera axes (x right, y down, z forward) in the drone frame
    usd = np.diag([1.0, -1.0, -1.0])                 # oracle camera frame -> USD camera frame (x right, y up, z back)
    for name, (x0, x1, y0, y1, z0, z1) in bounds.items():
        corners = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
        in_usd = (usd @ (r_cd.T @ (corners - np.array(mount)).T)).T / 1000.0
        c = cuboids[name]
        np.testing.assert_allclose(in_usd.max(0) - in_usd.min(0), c.size_m, atol=1e-9)
        np.testing.assert_allclose((in_usd.max(0) + in_usd.min(0)) / 2, c.centre_m, atol=1e-9)
    # the jaws that block the lens at this mount are the oracle's, cut off 3 mm below it
    assert max(b[5] for b in bounds.values()) == mount[2] - dg.LENS_CLEARANCE_MM
