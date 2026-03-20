"""Centralized render bootstrap for the game scene."""

from ursina import Sky, scene
from panda3d.core import AmbientLight, DirectionalLight, Vec3, Vec4


def configure_scene_lighting():
    sky = Sky()

    # Use Panda3D light nodes directly so procedurally generated GeomNode content
    # attached to the scene graph receives the same lighting state as Ursina entities.
    ambient_node = AmbientLight("scene_ambient")
    ambient_node.setColor(Vec4(0.68, 0.69, 0.74, 1.0))
    ambient = scene.attachNewNode(ambient_node)
    scene.setLight(ambient)

    sun_node = DirectionalLight("scene_sun")
    sun_node.setColor(Vec4(0.95, 0.93, 0.88, 1.0))
    sun = scene.attachNewNode(sun_node)
    sun.lookAt(Vec3(0.85, -1.0, 0.45))
    scene.setLight(sun)

    fill_node = DirectionalLight("scene_fill")
    fill_node.setColor(Vec4(0.42, 0.45, 0.52, 1.0))
    fill = scene.attachNewNode(fill_node)
    fill.lookAt(Vec3(-0.55, -0.45, -0.75))
    scene.setLight(fill)

    scene.setShaderAuto()

    return {
        "sky": sky,
        "ambient": ambient,
        "sun": sun,
        "fill": fill,
    }
