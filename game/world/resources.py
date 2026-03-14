"""
resources.py — Tree, Rock, FishingSpot node classes with harvest logic.
State machine: IDLE → HARVESTING → DEPLETED → RESPAWNING → IDLE
"""

import math
from panda3d.core import Vec3, NodePath, TransparencyAttrib
from panda3d.bullet import BulletGhostNode, BulletSphereShape

from game.world.geometry import make_box_geom, make_cylinder, make_sphere_approx

# State constants
IDLE = "idle"
HARVESTING = "harvesting"
DEPLETED = "depleted"
RESPAWNING = "respawning"

PROXIMITY_RADIUS = 3.5
RESPAWN_TIME = 15.0


class ResourceNode:
    def __init__(self, render, bullet_world, pos, item_id, skill, harvest_time, xp_reward):
        self.render = render
        self.bullet_world = bullet_world
        self.pos = Vec3(*pos)
        self.item_id = item_id
        self.skill = skill
        self.harvest_time = harvest_time
        self.xp_reward = xp_reward

        self.state = IDLE
        self.harvest_timer = 0.0
        self.respawn_timer = 0.0
        self.in_range = False

        self.root = NodePath("resource_root")
        self.root.reparentTo(render)
        self.root.setPos(self.pos)

        # Ghost node for proximity
        ghost_shape = BulletSphereShape(PROXIMITY_RADIUS)
        self.ghost = BulletGhostNode("resource_ghost")
        self.ghost.addShape(ghost_shape)
        self.ghost_np = render.attachNewNode(self.ghost)
        self.ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 1.5)
        bullet_world.attachGhost(self.ghost)

        self._build_visuals()
        self._setup_input()

    def _setup_input(self):
        # E key handled centrally in main.py; just track state here
        self._e_held = False

    def _on_e_pressed(self):
        self._e_held = True

    def _on_e_released(self):
        self._e_held = False
        if self.state == HARVESTING:
            self.state = IDLE
            self.harvest_timer = 0.0

    def _build_visuals(self):
        pass  # Overridden by subclasses

    def _set_depleted_look(self):
        pass  # Overridden

    def _reset_look(self):
        pass  # Overridden

    def _check_proximity(self, player_pos):
        dx = player_pos.x - self.pos.x
        dy = player_pos.y - self.pos.y
        dist = math.sqrt(dx * dx + dy * dy)
        return dist <= PROXIMITY_RADIUS

    def update(self, dt, player_pos, player, inventory, skills, hud):
        self.in_range = self._check_proximity(player_pos)

        if self.state == IDLE:
            if self.in_range:
                hud.show_prompt(f"Hold E to harvest {self.item_id}")
                if self._e_held:
                    self.state = HARVESTING
                    self.harvest_timer = 0.0
            else:
                hud.clear_prompt_if(f"Hold E to harvest {self.item_id}")

        elif self.state == HARVESTING:
            if not self.in_range or not self._e_held:
                self.state = IDLE
                self.harvest_timer = 0.0
                hud.clear_prompt_if(f"Hold E to harvest {self.item_id}")
                return

            self.harvest_timer += dt
            hud.show_prompt(f"Harvesting... {self.harvest_timer:.1f}/{self.harvest_time:.1f}s")

            if self.harvest_timer >= self.harvest_time:
                if inventory.is_full():
                    hud.show_prompt("Inventory full!")
                    self.state = IDLE
                    self.harvest_timer = 0.0
                else:
                    inventory.add_item(self.item_id)
                    levels = skills.add_xp(self.skill, self.xp_reward)
                    hud.refresh_inventory()
                    hud.refresh_skills()
                    if levels > 0:
                        hud.show_prompt(f"{self.skill} level up! Level {skills.get_level(self.skill)}")
                    self.state = DEPLETED
                    self.respawn_timer = 0.0
                    self._set_depleted_look()

        elif self.state == DEPLETED:
            hud.clear_prompt_if(f"Hold E to harvest {self.item_id}")

        elif self.state == RESPAWNING:
            self.respawn_timer += dt
            if self.respawn_timer >= RESPAWN_TIME:
                self.state = IDLE
                self._reset_look()

        # Transition depleted → respawning after a short pause
        if self.state == DEPLETED:
            self.respawn_timer += dt
            if self.respawn_timer >= 2.0:
                self.state = RESPAWNING


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------

class Tree(ResourceNode):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos,
                         item_id="wood", skill="Woodcutting",
                         harvest_time=2.5, xp_reward=25)

    def _build_visuals(self):
        # Trunk
        trunk = self.root.attachNewNode(make_cylinder(0.3, 3.0, (0.4, 0.25, 0.1, 1)))
        # Foliage (sphere on top)
        foliage = self.root.attachNewNode(make_sphere_approx(1.5, (0.15, 0.55, 0.1, 1)))
        foliage.setPos(0, 0, 3.5)
        self._trunk = trunk
        self._foliage = foliage
        self._depleted_color = (0.4, 0.35, 0.3, 1)
        self._active_foliage_color = (0.15, 0.55, 0.1, 1)

    def _set_depleted_look(self):
        self._foliage.setColorScale(0.5, 0.5, 0.5, 1)
        self._trunk.setColorScale(0.5, 0.5, 0.5, 1)

    def _reset_look(self):
        self._foliage.setColorScale(1, 1, 1, 1)
        self._trunk.setColorScale(1, 1, 1, 1)


# ---------------------------------------------------------------------------
# Rock
# ---------------------------------------------------------------------------

class Rock(ResourceNode):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos,
                         item_id="ore", skill="Mining",
                         harvest_time=3.5, xp_reward=35)

    def _build_visuals(self):
        # Cluster of two offset boxes
        c = (0.45, 0.45, 0.45, 1)
        b1 = self.root.attachNewNode(make_box_geom(1.5, 1.5, 1.2, c))
        b1.setPos(-0.3, 0, 0)
        b2 = self.root.attachNewNode(make_box_geom(1.0, 1.0, 1.5, c))
        b2.setPos(0.6, 0.2, 0.1)
        self._parts = [b1, b2]

    def _set_depleted_look(self):
        for p in self._parts:
            p.setColorScale(0.3, 0.3, 0.3, 1)

    def _reset_look(self):
        for p in self._parts:
            p.setColorScale(1, 1, 1, 1)


# ---------------------------------------------------------------------------
# FishingSpot
# ---------------------------------------------------------------------------

class FishingSpot(ResourceNode):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos,
                         item_id="fish", skill="Fishing",
                         harvest_time=4.0, xp_reward=30)
        self._anim_timer = 0.0

    def _build_visuals(self):
        # Animated blue plane (we animate color/scale each frame)
        from panda3d.core import CardMaker
        cm = CardMaker("fishing_spot")
        cm.setFrame(-1.5, 1.5, -1.5, 1.5)
        self._plane = self.root.attachNewNode(cm.generate())
        self._plane.setP(-90)  # lay flat
        self._plane.setColor(0.2, 0.5, 0.8, 0.8)
        self._plane.setTransparency(TransparencyAttrib.MAlpha)

    def update(self, dt, player_pos, player, inventory, skills, hud):
        # Animate the water shimmer
        self._anim_timer += dt
        scale = 1.0 + 0.08 * math.sin(self._anim_timer * 3.0)
        self._plane.setScale(scale, scale, 1)
        super().update(dt, player_pos, player, inventory, skills, hud)

    def _set_depleted_look(self):
        self._plane.setColor(0.5, 0.5, 0.5, 0.5)

    def _reset_look(self):
        self._plane.setColor(0.2, 0.5, 0.8, 0.8)
