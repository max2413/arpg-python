"""Reusable level teleporter interactable."""

import math

from panda3d.core import TransparencyAttrib
from panda3d.bullet import BulletGhostNode, BulletSphereShape

from game.entities.npc import attach_billboard_label
from game.world.geometry import make_box_geom, make_cylinder


TELEPORTER_PROXIMITY = 4.5


class Teleporter:
    def __init__(self, render, bullet_world, pos, prompt_text, destination_level_id, destination_entry_key, label):
        self.render = render
        self.bullet_world = bullet_world
        self.pos = pos
        self.prompt_text = prompt_text
        self.destination_level_id = destination_level_id
        self.destination_entry_key = destination_entry_key
        self.label = label
        self._in_range = False
        self._prompt_shown = False

        self.root = render.attachNewNode("teleporter")
        self.root.setPos(*pos)
        self._build_visual()
        self._build_ghost()

    def _build_visual(self):
        ring_color = (0.18, 0.7, 0.92, 0.85)
        post_color = (0.2, 0.24, 0.3, 1.0)
        glow_color = (0.38, 0.86, 1.0, 0.35)

        pad = self.root.attachNewNode(make_box_geom(2.8, 2.8, 0.18, (0.2, 0.22, 0.28, 1.0)))
        pad.setZ(0.09)
        for x, y in ((-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0)):
            post = self.root.attachNewNode(make_cylinder(0.12, 2.6, post_color))
            post.setPos(x, y, 0.1)
        beam = self.root.attachNewNode(make_box_geom(2.1, 0.22, 0.22, ring_color))
        beam.setPos(0, 0, 2.65)
        glow = self.root.attachNewNode(make_box_geom(2.1, 2.1, 2.2, glow_color))
        glow.setPos(0, 0, 1.3)
        glow.setTransparency(TransparencyAttrib.MAlpha)
        glow.setLightOff()
        glow.setDepthWrite(False)
        glow.setBin("fixed", 14)
        attach_billboard_label(self.root, self.label, (0, 0, 3.45), 0.8, (0.88, 1.0, 1.0, 1.0))

    def _build_ghost(self):
        shape = BulletSphereShape(TELEPORTER_PROXIMITY)
        ghost = BulletGhostNode("teleporter_ghost")
        ghost.addShape(shape)
        self._ghost_np = self.render.attachNewNode(ghost)
        self._ghost_np.setPos(self.pos[0], self.pos[1], self.pos[2] + 1.2)
        self.bullet_world.attachGhost(ghost)

    def update(self, player_pos, hud):
        dx = player_pos.x - self.pos[0]
        dy = player_pos.y - self.pos[1]
        self._in_range = math.sqrt(dx * dx + dy * dy) <= TELEPORTER_PROXIMITY
        if self._in_range:
            hud.show_prompt(self.prompt_text)
            self._prompt_shown = True
        elif self._prompt_shown:
            hud.clear_prompt_if(self.prompt_text)
            self._prompt_shown = False

    def try_interact(self):
        return self._in_range

    def remove_from_world(self, hud=None):
        if self._prompt_shown and hud is not None:
            hud.clear_prompt_if(self.prompt_text)
        if self._ghost_np is not None and not self._ghost_np.isEmpty():
            self.bullet_world.removeGhost(self._ghost_np.node())
            self._ghost_np.removeNode()
        if self.root is not None and not self.root.isEmpty():
            self.root.removeNode()
