"""Resource nodes with harvest logic and world collision."""

import math
from panda3d.core import Vec3, NodePath, TransparencyAttrib
from panda3d.bullet import BulletGhostNode, BulletSphereShape

from game.world.collision import attach_static_box_collider, remove_static_collider
from game.world.geometry import make_box_geom, make_cylinder, make_sphere_approx

# State constants
IDLE = "idle"
HARVESTING = "harvesting"
DEPLETED = "depleted"
RESPAWNING = "respawning"

PROXIMITY_RADIUS = 3.5
RESPAWN_TIME = 15.0


class ResourceNode:
    def __init__(self, render, bullet_world, pos, item_id, skill, harvest_time, xp_reward, verb="harvest"):
        self.render = render
        self.bullet_world = bullet_world
        self.pos = Vec3(*pos)
        self.item_id = item_id
        self.skill = skill
        self.harvest_time = harvest_time
        self.xp_reward = xp_reward
        self.verb = verb

        self.state = IDLE
        self.harvest_timer = 0.0
        self.respawn_timer = 0.0
        self.in_range = False
        self.blocker_np = None
        self._prompt_shown = False
        self._prompt_text = ""
        self._showing_cast_progress = False

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

    def _show_prompt(self, hud, text):
        self._prompt_shown = True
        self._prompt_text = text
        hud.show_prompt(text)

    def _clear_prompt(self, hud):
        if self._prompt_shown:
            hud.clear_prompt_if(self._prompt_text)
        self._prompt_shown = False
        self._prompt_text = ""

    def _show_cast_progress(self, hud, label, progress, total):
        self._showing_cast_progress = True
        hud.show_cast_progress(label, progress, total)

    def _hide_cast_progress(self, hud):
        if self._showing_cast_progress:
            hud.hide_cast_progress()
        self._showing_cast_progress = False

    def _build_visuals(self):
        pass  # Overridden by subclasses

    def _set_depleted_look(self):
        pass  # Overridden

    def _reset_look(self):
        pass  # Overridden

    def remove_from_world(self):
        if self.ghost_np and not self.ghost_np.isEmpty():
            self.bullet_world.removeGhost(self.ghost)
            self.ghost_np.removeNode()
        remove_static_collider(self.bullet_world, self.blocker_np)
        if self.root and not self.root.isEmpty():
            self.root.removeNode()

    def set_ground_pos(self, pos):
        self.pos = Vec3(*pos)
        self.root.setPos(self.pos)
        if self.ghost_np and not self.ghost_np.isEmpty():
            self.ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 1.5)
        remove_static_collider(self.bullet_world, self.blocker_np)
        self.blocker_np = None
        self._build_blocker()

    def _check_proximity(self, player_pos):
        dx = player_pos.x - self.pos.x
        dy = player_pos.y - self.pos.y
        dist = math.sqrt(dx * dx + dy * dy)
        return dist <= PROXIMITY_RADIUS

    def update(self, dt, player_pos, player, inventory, skills, hud):
        self.in_range = self._check_proximity(player_pos)

        if self.state == IDLE:
            if self.in_range:
                self._show_prompt(hud, f"Hold E to {self.verb} {self.item_id}")
                if self._e_held:
                    self.state = HARVESTING
                    self.harvest_timer = 0.0
                    self._show_cast_progress(hud, self.verb.capitalize(), 0.0, self.harvest_time)
            else:
                self._clear_prompt(hud)

        elif self.state == HARVESTING:
            if not self.in_range or not self._e_held:
                self.state = IDLE
                self.harvest_timer = 0.0
                self._clear_prompt(hud)
                self._hide_cast_progress(hud)
                return

            self.harvest_timer += dt
            self._show_cast_progress(hud, self.verb.capitalize(), self.harvest_timer, self.harvest_time)

            if self.harvest_timer >= self.harvest_time:
                self._hide_cast_progress(hud)
                if inventory.is_full():
                    hud.show_prompt("Inventory full!")
                    hud.add_log("Inventory full")
                    self.state = IDLE
                    self.harvest_timer = 0.0
                else:
                    inventory.add_item(self.item_id)
                    levels = skills.add_xp(self.skill, self.xp_reward)
                    hud.refresh_inventory()
                    hud.refresh_skills()
                    hud.add_log(f"+1 {self.item_id} | +{self.xp_reward} {self.skill} XP")
                    if levels > 0:
                        hud.show_prompt(f"{self.skill} level up! Level {skills.get_level(self.skill)}")
                        hud.add_log(f"{self.skill} level up! Level {skills.get_level(self.skill)}")
                    
                    # Notify QuestManager
                    if hasattr(player, "_app") and player._app:
                        player._app.quest_manager.notify_action("gather", "any") # Tutorial uses "any" for gather
                        if self.verb == "skin":
                            player._app.quest_manager.notify_action("skin", self.item_id)
                            
                    self.state = DEPLETED
                    self.respawn_timer = 0.0
                    self._set_depleted_look()
                    self._clear_prompt(hud)

        elif self.state == DEPLETED:
            self._clear_prompt(hud)
            self._hide_cast_progress(hud)

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
    def __init__(self, render, bullet_world, pos, scale=1.0):
        self.scale = scale
        super().__init__(render, bullet_world, pos,
                         item_id="wood", skill="Woodcutting",
                         harvest_time=2.5, xp_reward=25)

    def _build_visuals(self):
        # Trunk
        trunk = self.root.attachNewNode(make_cylinder(0.3, 3.0, (0.4, 0.25, 0.1, 1)))
        # Foliage (sphere on top)
        foliage = self.root.attachNewNode(make_sphere_approx(1.5, (0.15, 0.55, 0.1, 1)))
        foliage.setPos(0, 0, 3.5)
        self.root.setScale(self.scale)
        self._trunk = trunk
        self._foliage = foliage
        self._depleted_color = (0.4, 0.35, 0.3, 1)
        self._active_foliage_color = (0.15, 0.55, 0.1, 1)
        self._build_blocker()

    def _build_blocker(self):
        self.blocker_np = attach_static_box_collider(
            self.render,
            self.bullet_world,
            "tree_blocker",
            (self.pos.x, self.pos.y, self.pos.z + 0.9 * self.scale),
            (0.45 * self.scale, 0.45 * self.scale, 1.8 * self.scale),
        )

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
    def __init__(self, render, bullet_world, pos, scale=1.0):
        self.scale = scale
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
        self.root.setScale(self.scale)
        self._parts = [b1, b2]
        self._build_blocker()

    def _build_blocker(self):
        self.blocker_np = attach_static_box_collider(
            self.render,
            self.bullet_world,
            "rock_blocker",
            (
                self.pos.x + 0.1 * self.scale,
                self.pos.y + 0.05 * self.scale,
                self.pos.z + 0.55 * self.scale,
            ),
            (1.1 * self.scale, 0.95 * self.scale, 1.1 * self.scale),
        )

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
                         harvest_time=4.0, xp_reward=30, verb="fish")
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
        self._plane.setBin("fixed", 16)
        self._plane.setDepthWrite(False)
        self._plane.setDepthOffset(10)

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

    def _build_blocker(self):
        pass


# ---------------------------------------------------------------------------
# HerbPatch
# ---------------------------------------------------------------------------

class HerbPatch(ResourceNode):
    def __init__(self, render, bullet_world, pos, herb_type="marigold"):
        # Fetch color from items registry if possible
        from game.systems.inventory import get_item_def
        idef = get_item_def(herb_type)
        self.color = idef["color"] if idef else (1, 1, 1, 1)
        
        super().__init__(render, bullet_world, pos,
                         item_id=herb_type, skill="Foraging",
                         harvest_time=1.5, xp_reward=15, verb="forage")

    def _build_visuals(self):
        # Small flower cluster
        for i in range(3):
            angle = (i / 3.0) * math.pi * 2
            petal = self.root.attachNewNode(make_sphere_approx(0.2, self.color))
            petal.setPos(math.cos(angle) * 0.25, math.sin(angle) * 0.25, 0.1)
        
        stem = self.root.attachNewNode(make_cylinder(0.05, 0.4, (0.2, 0.5, 0.1, 1)))
        self._stem = stem

    def _set_depleted_look(self):
        self.root.hide()

    def _reset_look(self):
        self.root.show()

    def _build_blocker(self):
        pass # No blocker for herbs


# ---------------------------------------------------------------------------
# AnimalCarcass
# ---------------------------------------------------------------------------

class AnimalCarcass(ResourceNode):
    def __init__(self, render, bullet_world, pos, animal_type="wolf"):
        self.animal_type = animal_type
        # Wolf carcass yields leather and meat (we pick leather as primary item_id)
        super().__init__(render, bullet_world, pos,
                         item_id="leather", skill="Skinning",
                         harvest_time=3.0, xp_reward=40, verb="skin")
        # Override respawn to never respawn (it's a one-off from a mob)
        self.state = IDLE
        self._lifetime = 60.0

    def _build_visuals(self):
        # Flattened brown box
        body = self.root.attachNewNode(make_box_geom(1.2, 0.8, 0.4, (0.4, 0.25, 0.15, 1)))
        self._body = body

    def _set_depleted_look(self):
        self.remove_from_world()

    def _reset_look(self):
        pass

    def _build_blocker(self):
        pass

    def update(self, dt, player_pos, player, inventory, skills, hud):
        # Carcasses don't respawn, they just wait to be skinned or time out
        if self.state == DEPLETED:
            return
            
        self._lifetime -= dt
        if self._lifetime <= 0:
            self.remove_from_world()
            self.state = DEPLETED
            return

        super().update(dt, player_pos, player, inventory, skills, hud)
        
        # Override reward to also give meat
        if self.state == DEPLETED:
            if not inventory.is_full():
                inventory.add_item("raw_meat", 1)
                hud.refresh_inventory()
