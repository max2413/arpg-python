"""
player.py — Stick figure geometry, BulletCharacterController, WASD movement.
"""

import math
from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    TransparencyAttrib,
    Vec3,
    BitMask32,
    KeyboardButton,
)
from panda3d.bullet import BulletCharacterControllerNode, BulletCapsuleShape, ZUp
from game.entities.models import (
    CHARACTER_FOOT_Z,
    HumanoidModel,
    build_equipment_model,
)
from game.systems.combat import TargetedProjectile, in_attack_range, make_combat_profile, resolve_attack
from game.systems.inventory import get_item_def
from game.systems.stats import StatManager


MOVE_SPEED   = 12.0
SPRINT_MULT  = 5.0   # speed multiplier while shift is held
JUMP_SPEED   = 12.0
TURN_SPEED   = 180.0
SPRINT_TURN_MULT = 1.6
BACKPEDAL_MULT = 0.75
PLAYER_CAPSULE_RADIUS = 0.5
PLAYER_CAPSULE_HEIGHT = 3.0
MAX_HEALTH   = 100
HEALTH_REGEN_DELAY = 6.0
HEALTH_REGEN_RATE  = 4.0
DEBUG_COMBAT_LOGS = False
UNARMED_MELEE_PROFILE = make_combat_profile("Fists", 3.1, 2.0, 18, projectile=False)
UNARMED_RANGED_PROFILE = make_combat_profile(
    "Thrown",
    54.0,
    2.4,
    14,
    projectile=True,
    projectile_speed=30.0,
    projectile_radius=0.2,
    projectile_color=(0.95, 0.78, 0.22, 1),
)

# Animation
WALK_FREQ   = 3.5   # cycles per second at walk speed
WALK_AMP    = 35.0  # max swing angle in degrees
ATTACK_ANIM_DURATION = 0.3
MELEE_ABILITY_RANGE = 3.1
RANGED_ABILITY_RANGE = 54.0
MELEE_ABILITY_DAMAGE = 18
RANGED_ABILITY_DAMAGE = 14
# The shared character model is already grounded at its feet; the player-only
# controller still needs a slightly deeper visual offset to line the feet up
# with the Bullet character capsule in practice.
PLAYER_VISUAL_OFFSET_Z = -(PLAYER_CAPSULE_HEIGHT * 0.5 + PLAYER_CAPSULE_RADIUS) - 0.5
GROUND_MARKER_OUTER = (0.02, 0.02, 0.02, 0.42)
GROUND_MARKER_INNER = (0.92, 0.36, 0.12, 0.18)


def _make_ground_marker(outer_rx=0.72, outer_ry=0.46, inner_rx=0.48, inner_ry=0.28, segments=24):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("player_ground_marker", fmt, Geom.UHStatic)
    vdata.setNumRows(segments * 4)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)

    for i in range(segments):
        a0 = math.radians((i / segments) * 360.0)
        a1 = math.radians(((i + 1) / segments) * 360.0)
        ring = [
            (math.cos(a0) * outer_rx, math.sin(a0) * outer_ry, 0.0, GROUND_MARKER_OUTER),
            (math.cos(a1) * outer_rx, math.sin(a1) * outer_ry, 0.0, GROUND_MARKER_OUTER),
            (math.cos(a1) * inner_rx, math.sin(a1) * inner_ry, 0.0, GROUND_MARKER_INNER),
            (math.cos(a0) * inner_rx, math.sin(a0) * inner_ry, 0.0, GROUND_MARKER_INNER),
        ]
        base = i * 4
        for x, y, z, color in ring:
            vertex.addData3(x, y, z)
            normal.addData3(0, 0, 1)
            color_w.addData4(*color)
        tris.addVertices(base, base + 1, base + 2)
        tris.addVertices(base, base + 2, base + 3)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("player_ground_marker")
    node.addGeom(geom)
    return node


class Player:
    def __init__(self, render, bullet_world, inventory, terrain=None):
        self.render = render
        self.bullet_world = bullet_world
        self.inventory = inventory
        self.terrain = terrain

        # Visual
        self.model = HumanoidModel(
            render,
            skin_color=(0.9, 0.85, 0.75, 1.0),
            tunic_color=(0.68, 0.24, 0.12, 1.0),
        )
        self.figure = self.model.root
        self._ground_marker = self.figure.attachNewNode(_make_ground_marker())
        self._ground_marker.setPos(0, 0, 0.04)
        self._ground_marker.setTransparency(TransparencyAttrib.MAlpha)
        self._ground_marker.setLightOff()
        self._ground_marker.setDepthWrite(False)
        self._ground_marker.setBin("fixed", 13)

        # Physics — capsule covers the stick figure height (~4 units)
        shape = BulletCapsuleShape(PLAYER_CAPSULE_RADIUS, PLAYER_CAPSULE_HEIGHT, ZUp)
        self.char_node = BulletCharacterControllerNode(shape, 0.4, "player")
        self.char_np = render.attachNewNode(self.char_node)
        self.char_np.setPos(0, 0, PLAYER_CAPSULE_HEIGHT * 0.5 + PLAYER_CAPSULE_RADIUS + 1.0)
        self.char_np.setCollideMask(BitMask32.allOn())
        bullet_world.attachCharacter(self.char_node)

        # Key state
        self._keys = {"w": False, "s": False, "a": False, "d": False}
        self._sprinting = False
        self._space_down = False
        self._space_was_down = False
        self._app = None
        self._mouse_watcher = None
        self._setup_keys()
        self._jump_pending = False
        
        # We temporarily pass None for skills since they're attached to Game,
        # but we can pass them in later or fetch from app.
        self.stats = StatManager(self, inventory=self.inventory)
        
        self.max_health = self.stats.get("max_health")
        self.health = float(self.max_health)
        self.dead = False
        self._time_since_damage = HEALTH_REGEN_DELAY
        self.melee_ability_range = UNARMED_MELEE_PROFILE["range"]
        self.ranged_ability_range = UNARMED_RANGED_PROFILE["range"]
        self.projectiles = []
        self._auto_attack_style = None
        self._auto_attack_timer = 0.0

    def _setup_keys(self):
        import builtins
        app = builtins.__dict__.get("base")
        if app is None:
            return
        self._app = app
        self._mouse_watcher = app.mouseWatcherNode

    def refresh_equipment_models(self):
        """Update visible equipment models based on inventory dynamically."""
        for slot_name in ["weapon", "offhand", "ranged", "head", "chest", "legs"]:
            stack = self.inventory.equipment.get_slot(slot_name)
            if stack:
                model_np = build_equipment_model(stack["id"])
                self.model.set_equipment(slot_name, model_np)
            else:
                self.model.set_equipment(slot_name, None)
        
        self.stats.recalculate()
        self.max_health = self.stats.get("max_health")

    def take_damage(self, amount, hud=None, attacker=None):
        if self.dead or amount <= 0:
            return False
            
        # Award defense XP
        if hasattr(self, "stats") and self.stats.skills:
            self.stats.skills.add_xp("Defense", amount * 0.5)
            
        self.health = max(0, self.health - amount)
        self._time_since_damage = 0.0
        if self.health == 0:
            self.dead = True
            self._jump_pending = False
            return True
        return False

    def heal_full(self):
        self.health = float(self.max_health)
        self._time_since_damage = HEALTH_REGEN_DELAY

    def respawn(self, pos=(0, 0, 0)):
        self.dead = False
        self.heal_full()
        self._jump_pending = False
        self.clear_auto_attack()
        self._clear_projectiles()
        self.char_np.setPos(*pos)
        self.char_node.setLinearMovement(Vec3(0, 0, 0), False)
        self.char_np.setH(0)
        self.figure.setColorScale(1, 1, 1, 1)
        self.figure.setPos(pos[0], pos[1], pos[2] + PLAYER_VISUAL_OFFSET_Z)
        self.figure.setH(0)

    def update(self, dt):
        if self.dead:
            self.char_node.setLinearMovement(Vec3(0, 0, 0), False)
            pos = self.char_np.getPos()
            self.figure.setPos(pos.x, pos.y, pos.z + PLAYER_VISUAL_OFFSET_Z)
            self.figure.setH(self.char_np.getH())
            self.model.set_color_scale(0.45, 0.2, 0.2, 1)
            self.model.animate(dt, False)
            return

        self._time_since_damage += dt
        if self._time_since_damage >= HEALTH_REGEN_DELAY and self.health < self.max_health:
            self.health = min(self.max_health, self.health + HEALTH_REGEN_RATE * dt)

        self._poll_input()
        jump_pressed = self._space_down and not self._space_was_down
        self._space_was_down = self._space_down
        if jump_pressed:
            self._jump_pending = True

        heading = self.char_np.getH()
        turn_speed = TURN_SPEED * (SPRINT_TURN_MULT if self._sprinting else 1.0)
        if self._keys["a"]:
            heading += turn_speed * dt
        if self._keys["d"]:
            heading -= turn_speed * dt
        self.char_np.setH(heading)

        heading_rad = math.radians(self.char_np.getH())
        forward = Vec3(-math.sin(heading_rad), math.cos(heading_rad), 0)

        move = Vec3(0, 0, 0)
        if self._keys["w"]:
            move += forward
        if self._keys["s"]:
            move -= forward

        moving = move.lengthSquared() > 0
        sprinting = self._sprinting and self._keys["w"]
        if moving:
            move.normalize()
            speed = MOVE_SPEED
            if self._keys["s"] and not self._keys["w"]:
                speed *= BACKPEDAL_MULT
            if sprinting:
                speed *= SPRINT_MULT
            velocity = move * speed
        else:
            velocity = Vec3(0, 0, 0)

        self.char_node.setLinearMovement(velocity, False)

        if self._jump_pending and self.char_node.isOnGround():
            self.char_node.setMaxJumpHeight(6.0)
            self.char_node.setJumpSpeed(JUMP_SPEED)
            self.char_node.doJump()
            self._jump_pending = False

        self.refresh_equipment_models()
        self.model.animate(dt, moving, speed_mult=(SPRINT_MULT if sprinting else 1.0))

        # Sync visual to physics.
        pos = self.char_np.getPos()
        self.figure.setPos(pos.x, pos.y, pos.z + PLAYER_VISUAL_OFFSET_Z)
        self.figure.setH(self.char_np.getH())
        self.model.set_color_scale(1, 1, 1, 1)

    def get_pos(self):
        pos = self.char_np.getPos()
        return Vec3(pos.x, pos.y, pos.z + PLAYER_VISUAL_OFFSET_Z)

    def get_health_display(self):
        return int(math.ceil(self.health))

    def is_targetable(self):
        return not self.dead

    def get_target_point(self):
        return self.get_pos() + Vec3(0, 0, 2.2)

    def get_target_name(self):
        return "Player"

    def is_moving(self):
        return self._keys["w"] or self._keys["s"]

    def is_advancing(self):
        return self._keys["w"]

    def is_turning(self):
        return self._keys["a"] or self._keys["d"]

    def get_heading(self):
        return self.char_np.getH()

    def get_combat_profile(self, style):
        profile = None
        if style == "melee":
            profile = dict(UNARMED_MELEE_PROFILE)
            profile["damage"] = self.stats.get("melee_damage")
            profile["xp_style"] = "melee"
        elif style == "ranged":
            ranged_item = self.inventory.equipment.get_slot("ranged")
            if ranged_item is None:
                return None
            profile = dict(UNARMED_RANGED_PROFILE)
            item_def = get_item_def(ranged_item["id"])
            subtype = item_def.get("subtype") if item_def else None
            if subtype in ("wand", "staff"):
                profile["damage"] = self.stats.get("magic_damage")
                profile["name"] = item_def["name"] if item_def else "Magic"
                profile["projectile_color"] = tuple(item_def.get("accent_color", (0.35, 0.75, 1.0, 1.0))) if item_def else (0.35, 0.75, 1.0, 1.0)
                profile["xp_style"] = "magic"
            else:
                profile["damage"] = self.stats.get("ranged_damage")
                profile["name"] = item_def["name"] if item_def else profile["name"]
                profile["xp_style"] = "ranged"
        return profile

    def grant_combat_xp(self, style, amount):
        if amount <= 0 or not hasattr(self, "stats") or not self.stats.skills:
            return
        skill_name = {
            "melee": "Melee",
            "ranged": "Ranged",
            "magic": "Magic",
        }.get(style)
        if skill_name is None:
            return
        levels = self.stats.skills.add_xp(skill_name, amount)
        if levels > 0 and self._app and hasattr(self._app, "hud"):
            self._app.hud.refresh_skills()
            self._app.hud.show_prompt(f"{skill_name} level up! Level {self.stats.skills.get_level(skill_name)}")
            self._app.hud.add_log(f"{skill_name} level up! Level {self.stats.skills.get_level(skill_name)}")
        elif self._app and hasattr(self._app, "hud"):
            self._app.hud.refresh_skills()

    def start_auto_attack(self, style):
        if style not in ("melee", "ranged"):
            return
        if self._auto_attack_style != style:
            self._auto_attack_style = style
            self._auto_attack_timer = 0.0
            _log_combat(f"player auto-attack started style={style}")

    def clear_auto_attack(self):
        if self._auto_attack_style is not None:
            _log_combat(f"player auto-attack cleared style={self._auto_attack_style}")
        self._auto_attack_style = None
        self._auto_attack_timer = 0.0

    def combat_tick(self, tick_dt, target, hud):
        if self.dead:
            self.clear_auto_attack()
            return
        if self._auto_attack_style is None:
            return
        if target is None or not target.is_targetable():
            self.clear_auto_attack()
            return

        profile = self.get_combat_profile(self._auto_attack_style)
        if profile is None:
            self.clear_auto_attack()
            return

        self._auto_attack_timer = max(0.0, self._auto_attack_timer - tick_dt)
        if self._auto_attack_timer > 0.0:
            return

        target_point = target.get_target_point()
        if not in_attack_range(self.get_pos(), target_point, profile):
            return

        self.face_target(target_point)
        self.model.play_attack(self._auto_attack_style)

        if profile["projectile"]:
            self.fire_target_projectile(target, profile)
        else:
            xp_style = profile.get("xp_style", self._auto_attack_style)
            outcome = resolve_attack(self, target, xp_style, profile["damage"])
            _log_combat(f"player melee {outcome['type']} target={target.get_target_name()} damage={outcome['damage']}")
            if outcome["type"] != "miss" and outcome["type"] != "parry":
                if target.take_damage(outcome["damage"], hud, attacker=self, attack_style=xp_style):
                    # Target died, maybe bonus XP?
                    pass
                self.grant_combat_xp(xp_style, outcome["damage"])
        self._auto_attack_timer = profile["speed"]

    def _poll_input(self):
        if self._mouse_watcher is None:
            return
        watcher = self._mouse_watcher
        self._keys["w"] = watcher.isButtonDown(KeyboardButton.ascii_key("w"))
        self._keys["s"] = watcher.isButtonDown(KeyboardButton.ascii_key("s"))
        self._keys["a"] = watcher.isButtonDown(KeyboardButton.ascii_key("a"))
        self._keys["d"] = watcher.isButtonDown(KeyboardButton.ascii_key("d"))
        self._space_down = watcher.isButtonDown(KeyboardButton.space())
        self._sprinting = (
            watcher.isButtonDown(KeyboardButton.shift()) or
            watcher.isButtonDown(KeyboardButton.lshift()) or
            watcher.isButtonDown(KeyboardButton.rshift())
        )

    def face_target(self, target_pos):
        delta = target_pos - self.get_pos()
        delta.z = 0
        if delta.lengthSquared() > 0:
            self.char_np.setH(math.degrees(math.atan2(-delta.x, delta.y)))

    def distance_to(self, target_pos):
        delta = target_pos - self.get_pos()
        delta.z = 0
        return delta.length()

    def fire_target_projectile(self, target, profile):
        self._clear_expired_target_projectiles()
        origin = self.get_pos() + Vec3(0, 0, 2.2)
        _log_combat(f"player projectile fired target={target.get_target_name()} base_damage={profile['damage']}")
        self.projectiles.append(
            TargetedProjectile(self.render, origin, target, profile["damage"], profile, self._on_projectile_hit)
        )

    def update_projectiles(self, dt, hud):
        active = []
        for projectile in self.projectiles:
            if projectile.update(dt, hud):
                continue
            active.append(projectile)
        self.projectiles = active

    def _clear_projectiles(self):
        for projectile in self.projectiles:
            projectile.remove()
        self.projectiles = []

    def _clear_expired_target_projectiles(self):
        active = []
        for projectile in self.projectiles:
            if projectile.expired:
                projectile.remove()
            else:
                active.append(projectile)
        self.projectiles = active

    def _on_projectile_hit(self, target, base_damage, hud):
        profile = self.get_combat_profile("ranged")
        xp_style = profile.get("xp_style", "ranged") if profile else "ranged"
        outcome = resolve_attack(self, target, xp_style, base_damage)
        _log_combat(f"player ranged {outcome['type']} target={target.get_target_name()} damage={outcome['damage']}")
        if outcome["type"] != "miss" and outcome["type"] != "parry":
            target.take_damage(outcome["damage"], hud, attacker=self, attack_style=xp_style)
            self.grant_combat_xp(xp_style, outcome["damage"])


def _log_combat(message):
    import builtins
    app = getattr(builtins, "base", None)
    if app is not None and hasattr(app, "hud"):
        app.hud.add_combat_log(message)
    if DEBUG_COMBAT_LOGS:
        print(f"[combat] {message}")
