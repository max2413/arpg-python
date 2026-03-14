"""
npc.py - Shared helpers for interactable NPCs and simple procedural buildings.
"""

import math

from panda3d.core import Vec3, NodePath, TextNode, BillboardEffect
from panda3d.bullet import BulletGhostNode, BulletSphereShape

from game.world.geometry import make_box_geom, make_cylinder, make_sphere_approx


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


def build_humanoid_npc(parent, body_color, head_color, accent_color=None, label=None):
    root = parent.attachNewNode("npc_actor")

    torso = root.attachNewNode(make_cylinder(0.42, 2.6, body_color))
    torso.setPos(0, 0, 0)

    head = root.attachNewNode(make_sphere_approx(0.48, head_color))
    head.setPos(0, 0, 3.1)

    if accent_color is not None:
        sash = root.attachNewNode(make_box_geom(1.0, 0.18, 0.35, accent_color))
        sash.setPos(0, -0.38, 1.55)

    if label:
        attach_billboard_label(root, label, (0, 0, 4.0), 1.0, (1, 0.95, 0.75, 1))

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
