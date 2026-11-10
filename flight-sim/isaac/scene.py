"""The lid scene for the render server: ground, box with the sticker on its lid, lights, and a
camera rig carrying the parts of the drone that sit in the camera's view.

World is north-west-up metres with the lid frame as the world frame: lid origin at the sticker
centre, +x north (sticker right), +y west (sticker top), +z up. Imports pxr, so it only works
inside Isaac's Python after SimulationApp has started.
"""
import math
from dataclasses import dataclass
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade, Vt

from flightsim.drone_geometry import LID_SIZE_MM, camera_frame_cuboids, cuboids_mesh
from flightsim.profiles import CameraProfile

BOX_HEIGHT_M = 0.15  # GUESS: not in the CAD notes the oracle uses; only sets how far the ground is below the lid
# GUESSES, chosen by looking at frames (white sticker about 195/255, ground about 135 before the grey conversion);
# none is measured. Albedos are linear reflectance.
_DOME_INTENSITY = 80.0
_SUN_INTENSITY = 500.0
_GROUND_ALBEDO = 0.37
_LID_ALBEDO = 0.59
_DRONE_ALBEDO = 0.08
_APERTURE_MM = 20.955
_STICKER_LIFT_M = 0.0001


@dataclass(frozen=True)
class CameraRig:
    translate: UsdGeom.XformOp
    orient: UsdGeom.XformOp

    def set_pose(self, pos: tuple[float, float, float], quat_wxyz: tuple[float, float, float, float]) -> None:
        self.translate.Set(Gf.Vec3d(*pos))
        w, x, y, z = quat_wxyz
        self.orient.Set(Gf.Quatd(w, Gf.Vec3d(x, y, z)))


def _matte(stage: Usd.Stage, grey: float) -> UsdShade.Material:
    """Fully rough grey surface: the default material has a specular highlight (a bright blob in the frame)."""
    name = f"/World/Looks/Matte{round(grey * 100):03d}"
    existing = stage.GetPrimAtPath(name)
    if existing.IsValid():
        return UsdShade.Material(existing)
    material = UsdShade.Material.Define(stage, name)
    surface = UsdShade.Shader.Define(stage, f"{name}/Surface")
    surface.CreateIdAttr("UsdPreviewSurface")
    surface.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(grey, grey, grey))
    surface.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
    surface.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput().ConnectToSource(surface.ConnectableAPI(), "surface")
    return material


def _cuboid(stage: Usd.Stage, path: str, centre: tuple[float, float, float],
            size: tuple[float, float, float], grey: float) -> None:
    cube = UsdGeom.Cube.Define(stage, path)
    cube.GetSizeAttr().Set(1.0)
    cube.AddTranslateOp().Set(Gf.Vec3d(*centre))
    cube.AddScaleOp().Set(Gf.Vec3d(*size))
    UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(_matte(stage, grey))


def _sticker(stage: Usd.Stage, png: Path, size_m: tuple[float, float]) -> None:
    half_w, half_h = size_m[0] / 2, size_m[1] / 2
    # Not under /World/Box: a child of that cube would inherit its scale.
    mesh = UsdGeom.Mesh.Define(stage, "/World/Sticker")
    mesh.GetPointsAttr().Set(Vt.Vec3fArray([
        Gf.Vec3f(-half_w, -half_h, _STICKER_LIFT_M), Gf.Vec3f(half_w, -half_h, _STICKER_LIFT_M),
        Gf.Vec3f(half_w, half_h, _STICKER_LIFT_M), Gf.Vec3f(-half_w, half_h, _STICKER_LIFT_M)]))
    mesh.GetFaceVertexCountsAttr().Set([4])
    mesh.GetFaceVertexIndicesAttr().Set([0, 1, 2, 3])
    mesh.GetNormalsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0, 0, 1)] * 4))
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    # USD texture coordinates start at the image's bottom-left; the png's first row is the sticker top (+y).
    st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
    st.Set(Vt.Vec2fArray([Gf.Vec2f(0, 0), Gf.Vec2f(1, 0), Gf.Vec2f(1, 1), Gf.Vec2f(0, 1)]))

    material = UsdShade.Material.Define(stage, "/World/Looks/Sticker")
    surface = UsdShade.Shader.Define(stage, "/World/Looks/Sticker/Surface")
    surface.CreateIdAttr("UsdPreviewSurface")
    reader = UsdShade.Shader.Define(stage, "/World/Looks/Sticker/St")
    reader.CreateIdAttr("UsdPrimvarReader_float2")
    reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
    texture = UsdShade.Shader.Define(stage, "/World/Looks/Sticker/Texture")
    texture.CreateIdAttr("UsdUVTexture")
    texture.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(str(png))
    texture.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB")
    texture.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(), "result")
    texture.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
    surface.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(texture.ConnectableAPI(), "rgb")
    surface.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
    surface.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput().ConnectToSource(surface.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)


def _lights(stage: Usd.Stage, sun_elevation_deg: float) -> None:
    UsdLux.DomeLight.Define(stage, "/World/Dome").CreateIntensityAttr(_DOME_INTENSITY)
    sun = UsdLux.DistantLight.Define(stage, "/World/Sun")
    sun.CreateIntensityAttr(_SUN_INTENSITY)
    # A distant light shines along its local -Z; tip it from straight down by (90 - elevation).
    UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(-(90.0 - sun_elevation_deg), 0.0, 0.0))


def _camera_rig(stage: Usd.Stage, camera: CameraProfile) -> CameraRig:
    rig = UsdGeom.Xform.Define(stage, "/World/Rig")
    translate = rig.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble)
    orient = rig.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)
    cam = UsdGeom.Camera.Define(stage, "/World/Rig/Camera")
    cam.GetHorizontalApertureAttr().Set(_APERTURE_MM)
    cam.GetVerticalApertureAttr().Set(_APERTURE_MM * camera.height / camera.width)  # square pixels
    cam.GetFocalLengthAttr().Set(_APERTURE_MM / (2.0 * math.tan(math.radians(camera.hfov_deg) / 2.0)))
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
    points, counts, indices, normals = cuboids_mesh(camera_frame_cuboids())
    drone = UsdGeom.Mesh.Define(stage, "/World/Rig/Drone/Parts")
    drone.GetPointsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*map(float, p)) for p in points]))
    drone.GetFaceVertexCountsAttr().Set(Vt.IntArray([int(c) for c in counts]))
    drone.GetFaceVertexIndicesAttr().Set(Vt.IntArray([int(i) for i in indices]))
    drone.GetNormalsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*map(float, n)) for n in normals]))
    drone.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    drone.GetSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
    UsdShade.MaterialBindingAPI.Apply(drone.GetPrim()).Bind(_matte(stage, _DRONE_ALBEDO))
    # Only the pieces of the drone below the lens are modelled; the rest would shade the lid too, so
    # the sun shadows of these parts are not physical. Keep them out of the shadow pass.
    UsdGeom.PrimvarsAPI(drone.GetPrim()).CreatePrimvar("doNotCastShadows", Sdf.ValueTypeNames.Bool).Set(True)
    return CameraRig(translate, orient)


def build_scene(
    stage: Usd.Stage, camera: CameraProfile, lid_png: Path,
    lid_size_m: tuple[float, float], sun_elevation_deg: float,
) -> CameraRig:
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, "/World/Rig/Drone")
    lid_w, lid_h = LID_SIZE_MM[0] / 1000.0, LID_SIZE_MM[1] / 1000.0
    _cuboid(stage, "/World/Ground", (0.0, 0.0, -BOX_HEIGHT_M - 0.01), (40.0, 40.0, 0.02), _GROUND_ALBEDO)
    _cuboid(stage, "/World/Box", (0.0, 0.0, -BOX_HEIGHT_M / 2), (lid_w, lid_h, BOX_HEIGHT_M), _LID_ALBEDO)
    _sticker(stage, lid_png, lid_size_m)
    _lights(stage, sun_elevation_deg)
    return _camera_rig(stage, camera)
