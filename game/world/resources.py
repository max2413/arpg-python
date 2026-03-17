"""Resource nodes with harvest logic and world collision."""

import math

from panda3d.bullet import BulletGhostNode, BulletSphereShape
from panda3d.core import NodePath, TransparencyAttrib, Vec3

from game.systems.inventory import get_item_def, get_item_name
from game.world.collision import attach_static_box_collider, remove_static_collider
from game.world.geometry import make_box_geom, make_cylinder, make_sphere_approx

IDLE = "idle"
HARVESTING = "harvesting"
DEPLETED = "depleted"
RESPAWNING = "respawning"

PROXIMITY_RADIUS = 3.5
RESPAWN_TIME = 15.0
DEPLETED_DELAY = 2.0


TREE_VARIANTS = {
    "pine_log": {"label": "Pine Tree", "trunk": (0.40, 0.25, 0.10, 1.0), "foliage": (0.15, 0.55, 0.10, 1.0)},
    "ash_log": {"label": "Ash Tree", "trunk": (0.46, 0.30, 0.12, 1.0), "foliage": (0.22, 0.58, 0.20, 1.0)},
    "yew_log": {"label": "Yew Tree", "trunk": (0.34, 0.20, 0.10, 1.0), "foliage": (0.10, 0.34, 0.12, 1.0)},
    "magic_log": {"label": "Magic Tree", "trunk": (0.30, 0.22, 0.18, 1.0), "foliage": (0.26, 0.24, 0.60, 1.0)},
    "elder_log": {"label": "Elder Tree", "trunk": (0.22, 0.16, 0.10, 1.0), "foliage": (0.26, 0.22, 0.16, 1.0)},
}

ROCK_VARIANTS = {
    "copper_ore": {"label": "Copper Vein", "color": (0.54, 0.42, 0.36, 1.0)},
    "iron_ore": {"label": "Iron Vein", "color": (0.48, 0.48, 0.52, 1.0)},
    "coal": {"label": "Coal Vein", "color": (0.20, 0.20, 0.24, 1.0)},
    "mithril_ore": {"label": "Mithril Vein", "color": (0.28, 0.62, 0.70, 1.0)},
    "adamant_ore": {"label": "Adamant Vein", "color": (0.20, 0.58, 0.34, 1.0)},
}

CARCASS_VARIANTS = {
    "deer": {"label": "Deer Carcass", "item_id": "scrappy_hide", "bonus_drops": {"raw_meat": 1}, "color": (0.46, 0.30, 0.18, 1.0)},
    "wolf": {"label": "Wolf Carcass", "item_id": "cured_leather", "bonus_drops": {"raw_meat": 1}, "color": (0.34, 0.24, 0.18, 1.0)},
}

HERB_COLORS = {
    "marigold": (1.0, 0.60, 0.0, 1.0),
    "belladonna": (0.40, 0.10, 0.60, 1.0),
    "bloodmoss": (0.58, 0.10, 0.14, 1.0),
    "dragons_tongue": (0.96, 0.28, 0.18, 1.0),
    "starbloom": (0.62, 0.84, 1.0, 1.0),
    "void_spore": (0.30, 0.20, 0.46, 1.0),
}


class ResourceNode:
    def __init__(
        self,
        render,
        bullet_world,
        pos,
        item_id,
        skill,
        harvest_time,
        xp_reward,
        *,
        verb="gather",
        resource_name=None,
        respawn_time=RESPAWN_TIME,
    ):
        self.render = render
        self.bullet_world = bullet_world
        self.pos = Vec3(*pos)
        self.item_id = item_id
        self.skill = skill
        self.harvest_time = harvest_time
        self.xp_reward = xp_reward
        self.verb = verb
        self.resource_name = resource_name or get_item_name(item_id)
        self.respawn_time = respawn_time
        self.depleted_delay = DEPLETED_DELAY

        self.state = IDLE
        self.harvest_timer = 0.0
        self.respawn_timer = 0.0
        self.in_range = False
        self.blocker_np = None
        self._prompt_shown = False
        self._prompt_text = ""
        self._showing_cast_progress = False
        self._e_held = False

        self.root = NodePath("resource_root")
        self.root.reparentTo(render)
        self.root.setPos(self.pos)

        ghost_shape = BulletSphereShape(PROXIMITY_RADIUS)
        self.ghost = BulletGhostNode("resource_ghost")
        self.ghost.addShape(ghost_shape)
        self.ghost_np = render.attachNewNode(self.ghost)
        self.ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 1.5)
        bullet_world.attachGhost(self.ghost)

        self._build_visuals()
        self._setup_input()

    def _setup_input(self):
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
        pass

    def _set_depleted_look(self):
        pass

    def _reset_look(self):
        pass

    def _grant_rewards(self, inventory, hud):
        if not inventory.add_item(self.item_id):
            return False
        return True

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
        return math.sqrt(dx * dx + dy * dy) <= PROXIMITY_RADIUS

    def update(self, dt, player_pos, player, inventory, skills, hud):
        self.in_range = self._check_proximity(player_pos)

        if self.state == IDLE:
            if self.in_range:
                self._show_prompt(hud, f"Hold E to {self.verb} {self.resource_name}")
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
            if player is not None and hasattr(player, "play_work_animation"):
                player.play_work_animation()
            self._show_cast_progress(hud, self.verb.capitalize(), self.harvest_timer, self.harvest_time)

            if self.harvest_timer >= self.harvest_time:
                self._hide_cast_progress(hud)
                if not self._grant_rewards(inventory, hud):
                    hud.show_prompt("Inventory full!")
                    hud.add_log("Inventory full")
                    self.state = IDLE
                    self.harvest_timer = 0.0
                else:
                    levels = skills.add_xp(self.skill, self.xp_reward)
                    hud.refresh_inventory()
                    hud.refresh_skills()
                    hud.add_log(f"+1 {get_item_name(self.item_id)} | +{self.xp_reward} {self.skill} XP")
                    if levels > 0:
                        hud.show_prompt(f"{self.skill} level up! Level {skills.get_level(self.skill)}")
                        hud.add_log(f"{self.skill} level up! Level {skills.get_level(self.skill)}")
                    if hasattr(player, "_app") and player._app:
                        player._app.quest_manager.notify_action("gather", "any")
                        if self.verb == "skin":
                            player._app.quest_manager.notify_action("skin", self.item_id)
                    self.state = DEPLETED
                    self.respawn_timer = 0.0
                    self._set_depleted_look()
                    self._clear_prompt(hud)

        elif self.state == DEPLETED:
            self._clear_prompt(hud)
            self._hide_cast_progress(hud)
            if self.respawn_time is not None:
                self.respawn_timer += dt
                if self.respawn_timer >= self.depleted_delay:
                    self.state = RESPAWNING
                    self.respawn_timer = 0.0

        elif self.state == RESPAWNING:
            self.respawn_timer += dt
            if self.respawn_timer >= self.respawn_time:
                self.state = IDLE
                self.respawn_timer = 0.0
                self._reset_look()


class Tree(ResourceNode):
    def __init__(self, render, bullet_world, pos, scale=1.0, item_id="pine_log"):
        self.scale = scale
        variant = TREE_VARIANTS.get(item_id, TREE_VARIANTS["pine_log"])
        self.variant = variant
        super().__init__(
            render,
            bullet_world,
            pos,
            item_id=item_id,
            skill="Woodcutting",
            harvest_time=2.5,
            xp_reward=25,
            verb="chop",
            resource_name=variant["label"],
        )

    def _build_visuals(self):
        trunk_radius = 0.6 if self.item_id == "yew_log" else 0.3
        self._trunk = self.root.attachNewNode(make_cylinder(trunk_radius, 3.0, self.variant["trunk"]))
        self._foliage_parts = []
        if self.item_id == "pine_log":
            cone_specs = [
                (1.15, 2.75),
                (0.90, 3.55),
                (0.62, 4.20),
            ]
            for radius, z in cone_specs:
                part = self.root.attachNewNode(make_sphere_approx(radius, self.variant["foliage"]))
                part.setPos(0, 0, z)
                self._foliage_parts.append(part)
            self._foliage = self._foliage_parts[0]
        else:
            self._foliage = self.root.attachNewNode(make_sphere_approx(1.5, self.variant["foliage"]))
            self._foliage.setPos(0, 0, 3.5)
            self._foliage_parts.append(self._foliage)
        self.root.setScale(self.scale)
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
        for part in getattr(self, "_foliage_parts", [self._foliage]):
            part.setColorScale(0.5, 0.5, 0.5, 1)
        self._trunk.setColorScale(0.5, 0.5, 0.5, 1)

    def _reset_look(self):
        for part in getattr(self, "_foliage_parts", [self._foliage]):
            part.setColorScale(1, 1, 1, 1)
        self._trunk.setColorScale(1, 1, 1, 1)


class Rock(ResourceNode):
    def __init__(self, render, bullet_world, pos, scale=1.0, item_id="copper_ore"):
        self.scale = scale
        self.variant = ROCK_VARIANTS.get(item_id, ROCK_VARIANTS["copper_ore"])
        super().__init__(
            render,
            bullet_world,
            pos,
            item_id=item_id,
            skill="Mining",
            harvest_time=3.5,
            xp_reward=35,
            verb="mine",
            resource_name=self.variant["label"],
        )

    def _build_visuals(self):
        c = self.variant["color"]
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
            (self.pos.x + 0.1 * self.scale, self.pos.y + 0.05 * self.scale, self.pos.z + 0.55 * self.scale),
            (1.1 * self.scale, 0.95 * self.scale, 1.1 * self.scale),
        )

    def _set_depleted_look(self):
        for part in self._parts:
            part.setColorScale(0.3, 0.3, 0.3, 1)

    def _reset_look(self):
        for part in self._parts:
            part.setColorScale(1, 1, 1, 1)


class FishingSpot(ResourceNode):
    def __init__(self, render, bullet_world, pos):
        super().__init__(
            render,
            bullet_world,
            pos,
            item_id="fish",
            skill="Fishing",
            harvest_time=4.0,
            xp_reward=30,
            verb="fish",
            resource_name="Fishing Spot",
        )
        self._anim_timer = 0.0

    def _build_visuals(self):
        from panda3d.core import CardMaker

        cm = CardMaker("fishing_spot")
        cm.setFrame(-1.5, 1.5, -1.5, 1.5)
        self._plane = self.root.attachNewNode(cm.generate())
        self._plane.setP(-90)
        self._plane.setColor(0.2, 0.5, 0.8, 0.8)
        self._plane.setTransparency(TransparencyAttrib.MAlpha)
        self._plane.setBin("fixed", 16)
        self._plane.setDepthWrite(False)
        self._plane.setDepthOffset(10)

    def update(self, dt, player_pos, player, inventory, skills, hud):
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


class HerbPatch(ResourceNode):
    def __init__(self, render, bullet_world, pos, herb_type="marigold"):
        self.color = HERB_COLORS.get(herb_type)
        if self.color is None:
            idef = get_item_def(herb_type)
            self.color = tuple(idef["color"]) if idef else (1, 1, 1, 1)
        super().__init__(
            render,
            bullet_world,
            pos,
            item_id=herb_type,
            skill="Foraging",
            harvest_time=1.5,
            xp_reward=15,
            verb="forage",
            resource_name=get_item_name(herb_type),
        )

    def _build_visuals(self):
        for i in range(3):
            angle = (i / 3.0) * math.pi * 2
            petal = self.root.attachNewNode(make_sphere_approx(0.2, self.color))
            petal.setPos(math.cos(angle) * 0.25, math.sin(angle) * 0.25, 0.1)
        self._stem = self.root.attachNewNode(make_cylinder(0.05, 0.4, (0.2, 0.5, 0.1, 1)))

    def _set_depleted_look(self):
        self.root.hide()

    def _reset_look(self):
        self.root.show()

    def _build_blocker(self):
        pass


class WaterSource(ResourceNode):
    def __init__(self, render, bullet_world, pos):
        super().__init__(
            render,
            bullet_world,
            pos,
            item_id="clean_water",
            skill="Foraging",
            harvest_time=1.6,
            xp_reward=10,
            verb="collect",
            resource_name="Water Basin",
        )
        self._anim_timer = 0.0

    def _build_visuals(self):
        basin = self.root.attachNewNode(make_box_geom(2.0, 2.0, 0.24, (0.26, 0.26, 0.30, 1.0)))
        basin.setPos(0, 0, 0.12)
        water = self.root.attachNewNode(make_box_geom(1.7, 1.7, 0.08, (0.26, 0.62, 0.90, 0.85)))
        water.setPos(0, 0, 0.22)
        water.setTransparency(TransparencyAttrib.MAlpha)
        self._water = water
        self._build_blocker()

    def _build_blocker(self):
        self.blocker_np = attach_static_box_collider(
            self.render,
            self.bullet_world,
            "water_basin",
            (self.pos.x, self.pos.y, self.pos.z + 0.12),
            (2.0, 2.0, 0.24),
        )

    def update(self, dt, player_pos, player, inventory, skills, hud):
        self._anim_timer += dt
        self._water.setColorScale(1.0, 1.0, 1.0, 0.8 + 0.08 * math.sin(self._anim_timer * 2.2))
        super().update(dt, player_pos, player, inventory, skills, hud)

    def _set_depleted_look(self):
        self._water.setColorScale(0.7, 0.7, 0.7, 0.45)

    def _reset_look(self):
        self._water.setColorScale(1, 1, 1, 1)


class AnimalCarcass(ResourceNode):
    def __init__(self, render, bullet_world, pos, animal_type="wolf", respawn_time=None):
        self.animal_type = animal_type
        self.variant = CARCASS_VARIANTS.get(animal_type, CARCASS_VARIANTS["wolf"])
        self._lifetime = 60.0
        super().__init__(
            render,
            bullet_world,
            pos,
            item_id=self.variant["item_id"],
            skill="Skinning",
            harvest_time=3.0,
            xp_reward=40,
            verb="skin",
            resource_name=self.variant["label"],
            respawn_time=respawn_time,
        )

    def _build_visuals(self):
        self._body = self.root.attachNewNode(make_box_geom(1.2, 0.8, 0.4, self.variant["color"]))

    def _grant_rewards(self, inventory, hud):
        if not inventory.add_item(self.item_id):
            return False
        for extra_id, qty in self.variant.get("bonus_drops", {}).items():
            inventory.add_item(extra_id, qty)
        for extra_id, qty in self.variant.get("bonus_drops", {}).items():
            hud.add_log(f"+{qty} {get_item_name(extra_id)}")
        return True

    def _build_blocker(self):
        pass

    def update(self, dt, player_pos, player, inventory, skills, hud):
        if self.state in (DEPLETED, RESPAWNING):
            super().update(dt, player_pos, player, inventory, skills, hud)
            return
        self._lifetime -= dt
        if self._lifetime <= 0:
            if self.respawn_time is None:
                self.remove_from_world()
            else:
                self.state = DEPLETED
                self.respawn_timer = 0.0
                self._set_depleted_look()
            return
        super().update(dt, player_pos, player, inventory, skills, hud)

    def _reset_look(self):
        if self.root is None or self.root.isEmpty():
            return
        self.root.show()
        if hasattr(self, "_body") and self._body is not None and not self._body.isEmpty():
            self._body.setColorScale(1, 1, 1, 1)
        self._lifetime = 60.0

    def _set_depleted_look(self):
        if self.respawn_time is None:
            self.remove_from_world()
            return
        if self.root is not None and not self.root.isEmpty():
            self.root.hide()
