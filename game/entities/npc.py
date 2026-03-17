"""
npc.py - Shared helpers for interactable NPCs and simple procedural buildings.
"""

import math

from panda3d.core import (
    Vec3,
    NodePath,
    TextNode,
    BillboardEffect,
)
from panda3d.bullet import BulletGhostNode, BulletSphereShape

from game.entities.models import HumanoidModel


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
    tunic_color = accent_color if accent_color is not None else body_color
    model = HumanoidModel(parent, skin_color=head_color, tunic_color=tunic_color)
    if label:
        attach_billboard_label(model.root, label, (0, 0, 4.2), 1.0, (1, 0.95, 0.75, 1))
    return model


def default_prompt_for_service(service_name):
    prompts = {
        "shop": "Press E to browse wares",
        "bank": "Press E to access bank",
        "quests": "Press E to talk",
        "dialogue": "Press E to talk",
    }
    return prompts.get(service_name, "Press E to interact")


class InteractableNpc:
    def __init__(self, render, bullet_world, pos, proximity, prompt_text):
        self.render = render
        self.bullet_world = bullet_world
        self.pos = Vec3(*pos)
        self.proximity = proximity
        self.prompt_text = prompt_text
        self._in_range = False
        self._prompt_shown = False
        self.model = None

        self.root = NodePath(self.__class__.__name__.lower())
        self.root.reparentTo(render)
        self.root.setPos(self.pos)

        self._build_visual()
        self._build_ghost()

    def _animate(self, dt, moving=False):
        if self.model is not None:
            self.model.animate(dt, moving)

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

    def remove_from_world(self, hud=None):
        if hasattr(self, "close_ui"):
            self.close_ui()
        if self._prompt_shown and hud is not None:
            hud.clear_prompt_if(self.prompt_text)
        if hasattr(self, "_ghost_np") and self._ghost_np is not None and not self._ghost_np.isEmpty():
            self.bullet_world.removeGhost(self._ghost_np.node())
            self._ghost_np.removeNode()
        if self.root is not None and not self.root.isEmpty():
            self.root.removeNode()


class ServiceNpc(InteractableNpc):
    def __init__(self, render, bullet_world, pos, proximity, services, palette, label):
        self.services = list(services or [])
        self.palette = dict(palette or {})
        self.label = label
        prompt = default_prompt_for_service(self.services[0] if self.services else None)
        super().__init__(render, bullet_world, pos, proximity, prompt)

    def has_service(self, service_name):
        return service_name in self.services

    def _build_visual(self):
        self.model = build_humanoid_npc(
            self.root,
            body_color=tuple(self.palette.get("body", (0.4, 0.4, 0.6, 1.0))),
            head_color=tuple(self.palette.get("head", (0.86, 0.74, 0.62, 1.0))),
            accent_color=tuple(self.palette.get("accent", (0.8, 0.8, 0.4, 1.0))),
            label=self.label,
        )
