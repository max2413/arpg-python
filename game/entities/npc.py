"""
npc.py - Shared helpers for interactable NPCs and simple procedural buildings.
"""

import math

from panda3d.core import (
    Vec3,
    NodePath,
    TextNode,
    BillboardEffect,
    GeomVertexFormat,
    GeomVertexData,
    GeomVertexWriter,
    GeomTriangles,
    Geom,
    GeomNode,
    TransparencyAttrib,
)
from panda3d.bullet import BulletGhostNode, BulletSphereShape

from game.world.geometry import make_box_geom, make_sphere_approx


HEAD_Z = 3.8
HEAD_RADIUS = 0.48
TORSO_SIZE = (0.34, 0.34, 1.32)
ARM_SIZE = (0.18, 0.18, 1.12)
LEG_SIZE = (0.2, 0.2, 1.58)
TUNIC_BASE = 0.62
TUNIC_BOTTOM_Z = 2.02
TUNIC_HEAD_GAP = 0.08
DEFAULT_TUNIC_COLOR = (0.68, 0.24, 0.12, 1.0)
DEFAULT_ARROW_COLOR = (1.0, 0.3, 0.1)
ARROW_SHAFT_SIZE = (0.12, 0.82, 0.12)
ARROW_HEAD_SIZE = (0.12, 0.3, 0.12)
SHADOW_RADIUS_X = 0.62
SHADOW_RADIUS_Y = 0.42
SHADOW_ALPHA = 0.18
ARM_REST_ANGLE = 10.0


def _make_shadow_disc(radius_x, radius_y, color, segments=20):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("shadow_disc", fmt, Geom.UHStatic)
    vdata.setNumRows(segments + 1)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")

    vertex.addData3(0, 0, 0)
    normal.addData3(0, 0, 1)
    color_w.addData4(*color)

    for i in range(segments):
        angle = math.radians((i / segments) * 360.0)
        vertex.addData3(math.cos(angle) * radius_x, math.sin(angle) * radius_y, 0)
        normal.addData3(0, 0, 1)
        color_w.addData4(*color)

    tris = GeomTriangles(Geom.UHStatic)
    for i in range(segments):
        tris.addVertices(0, i + 1, (i + 1) % segments + 1)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("shadow_disc")
    node.addGeom(geom)
    return node


def attach_billboard_label(parent, text, pos, scale, color, shadow=(0, 0, 0, 0.8)):
    label_node = TextNode(f"{text.lower()}_label")
    label_node.setText(text)
    label_node.setAlign(TextNode.ACenter)
    label_node.setTextColor(*color)
    label_node.setShadow(0.04, 0.04)
    label_node.setShadowColor(*shadow)
    label_np = parent.attachNewNode(label_node)
    label_np.setPos(*pos)
    label_np.setScale(scale)
    label_np.setEffect(BillboardEffect.makePointEye())
    return label_np


def build_character_model(parent, skin_color, tunic_color=DEFAULT_TUNIC_COLOR,
                          arrow_color=DEFAULT_ARROW_COLOR):
    root = parent.attachNewNode("character_actor")
    tunic_top_z = HEAD_Z - HEAD_RADIUS - TUNIC_HEAD_GAP
    tunic_height = tunic_top_z - TUNIC_BOTTOM_Z

    shadow = root.attachNewNode(_make_shadow_disc(SHADOW_RADIUS_X, SHADOW_RADIUS_Y, (0, 0, 0, SHADOW_ALPHA)))
    shadow.setPos(0, 0, 0.03)
    shadow.setTransparency(TransparencyAttrib.MAlpha)
    shadow.setLightOff()
    shadow.setDepthWrite(False)
    shadow.setBin("fixed", 12)

    torso = root.attachNewNode(make_box_geom(*TORSO_SIZE, skin_color))
    torso.setPos(0, 0, 2.66)

    tunic = root.attachNewNode(make_box_geom(TUNIC_BASE, TUNIC_BASE, tunic_height, tunic_color))
    tunic.setPos(0, 0, TUNIC_BOTTOM_Z + tunic_height * 0.5)

    head = root.attachNewNode(make_sphere_approx(HEAD_RADIUS, skin_color))
    head.setPos(0, 0, HEAD_Z)

    arrow_root = root.attachNewNode("direction_arrow")
    arrow_root.setPos(0, 0, HEAD_Z + 0.9)
    arrow_shaft = arrow_root.attachNewNode(make_box_geom(*ARROW_SHAFT_SIZE, (*arrow_color, 1.0)))
    arrow_shaft.setPos(0, 0.41, 0)
    arrow_left = arrow_root.attachNewNode(make_box_geom(*ARROW_HEAD_SIZE, (*arrow_color, 1.0)))
    arrow_left.setPos(-0.1, 0.74, 0)
    arrow_left.setH(40)
    arrow_right = arrow_root.attachNewNode(make_box_geom(*ARROW_HEAD_SIZE, (*arrow_color, 1.0)))
    arrow_right.setPos(0.1, 0.74, 0)
    arrow_right.setH(-40)

    l_arm = root.attachNewNode("l_arm_pivot")
    l_arm.setPos(0, 0, 3.2)
    l_arm_geom = l_arm.attachNewNode(make_box_geom(*ARM_SIZE, skin_color))
    l_arm_geom.setPos(-0.32, 0, -0.58)
    l_arm_geom.setR(ARM_REST_ANGLE)

    r_arm = root.attachNewNode("r_arm_pivot")
    r_arm.setPos(0, 0, 3.2)
    r_arm_geom = r_arm.attachNewNode(make_box_geom(*ARM_SIZE, skin_color))
    r_arm_geom.setPos(0.32, 0, -0.58)
    r_arm_geom.setR(-ARM_REST_ANGLE)

    l_leg = root.attachNewNode("l_leg_pivot")
    l_leg.setPos(0, 0, 2.0)
    l_leg_geom = l_leg.attachNewNode(make_box_geom(*LEG_SIZE, skin_color))
    l_leg_geom.setPos(-0.14, 0, -0.79)

    r_leg = root.attachNewNode("r_leg_pivot")
    r_leg.setPos(0, 0, 2.0)
    r_leg_geom = r_leg.attachNewNode(make_box_geom(*LEG_SIZE, skin_color))
    r_leg_geom.setPos(0.14, 0, -0.79)

    return root, l_leg, r_leg, l_arm, r_arm


def build_humanoid_npc(parent, body_color, head_color, accent_color=None, label=None):
    tunic_color = accent_color if accent_color is not None else body_color
    root = build_character_model(parent, skin_color=head_color, tunic_color=tunic_color)[0]
    if label:
        attach_billboard_label(root, label, (0, 0, 4.2), 1.0, (1, 0.95, 0.75, 1))
    return root


class InteractableNpc:
    def __init__(self, render, bullet_world, pos, proximity, prompt_text):
        self.render = render
        self.bullet_world = bullet_world
        self.pos = Vec3(*pos)
        self.proximity = proximity
        self.prompt_text = prompt_text
        self._in_range = False
        self._prompt_shown = False

        self.root = NodePath(self.__class__.__name__.lower())
        self.root.reparentTo(render)
        self.root.setPos(self.pos)

        self._build_visual()
        self._build_ghost()

    def _build_visual(self):
        raise NotImplementedError

    def _build_ghost(self):
        shape = BulletSphereShape(self.proximity)
        ghost = BulletGhostNode(f"{self.__class__.__name__.lower()}_ghost")
        ghost.addShape(shape)
        self._ghost_np = self.render.attachNewNode(ghost)
        self._ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 1.5)
        self.bullet_world.attachGhost(ghost)

    def update_prompt(self, player_pos, hud, ui_open=False):
        dx = player_pos.x - self.pos.x
        dy = player_pos.y - self.pos.y
        self._in_range = math.sqrt(dx * dx + dy * dy) <= self.proximity

        if ui_open:
            if self._prompt_shown:
                hud.clear_prompt_if(self.prompt_text)
                self._prompt_shown = False
            return

        if self._in_range:
            hud.show_prompt(self.prompt_text)
            self._prompt_shown = True
        elif self._prompt_shown:
            hud.clear_prompt_if(self.prompt_text)
            self._prompt_shown = False
