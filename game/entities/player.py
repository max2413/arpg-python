"""
player.py — Stick figure geometry, BulletCharacterController, WASD movement.
"""

import math
from panda3d.core import Vec3, BitMask32, KeyboardButton
from panda3d.bullet import BulletCharacterControllerNode, BulletCapsuleShape, ZUp
from game.entities.npc import build_character_model
from game.systems.combat import TargetedProjectile, in_attack_range, make_combat_profile


MOVE_SPEED   = 12.0
SPRINT_MULT  = 5.0   # speed multiplier while shift is held
JUMP_SPEED   = 12.0
TURN_SPEED   = 180.0
SPRINT_TURN_MULT = 1.6
BACKPEDAL_MULT = 0.75
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
MELEE_ABILITY_RANGE = 3.1
RANGED_ABILITY_RANGE = 54.0
MELEE_ABILITY_DAMAGE = 18
RANGED_ABILITY_DAMAGE = 14


class Player:
    def __init__(self, render, bullet_world, inventory):
        self.render = render
        self.bullet_world = bullet_world
        self.inventory = inventory

        # Visual
        (self.figure,
         self._l_leg, self._r_leg,
         self._l_arm, self._r_arm) = build_character_model(
            render,
            skin_color=(0.9, 0.85, 0.75, 1.0),
            tunic_color=(0.68, 0.24, 0.12, 1.0),
        )
        self.figure.reparentTo(render)

        # Animation state
        self._walk_t = 0.0

        # Physics — capsule covers the stick figure height (~4 units)
        shape = BulletCapsuleShape(0.5, 3.0, ZUp)
        self.char_node = BulletCharacterControllerNode(shape, 0.4, "player")
        self.char_np = render.attachNewNode(self.char_node)
        self.char_np.setPos(0, 0, 0)
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
        self.max_health = MAX_HEALTH
        self.health = float(self.max_health)
        self.dead = False
        self._time_since_damage = HEALTH_REGEN_DELAY
        self.melee_ability_range = UNARMED_MELEE_PROFILE["range"]
        self.ranged_ability_range = UNARMED_RANGED_PROFILE["range"]
        self.melee_ability_damage = UNARMED_MELEE_PROFILE["damage"]
        self.ranged_ability_damage = UNARMED_RANGED_PROFILE["damage"]
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

    def _animate(self, dt, moving, sprinting):
        if moving:
            freq = WALK_FREQ * (SPRINT_MULT if sprinting else 1.0)
            self._walk_t += dt * freq * 2 * math.pi
        else:
            self._walk_t = 0.0

        swing = math.sin(self._walk_t) * WALK_AMP if moving else 0.0

        # Legs swing opposite each other (P = pitch = rotation around X)
        self._l_leg.setP(swing)
        self._r_leg.setP(-swing)
        # Arms counter-swing relative to legs
        self._l_arm.setP(-swing * 0.6)
        self._r_arm.setP(swing * 0.6)

    def take_damage(self, amount):
        if self.dead or amount <= 0:
            return False
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
        self.figure.setPos(pos[0], pos[1], pos[2] - 2.0)
        self.figure.setH(0)

    def update(self, dt):
        if self.dead:
            self.char_node.setLinearMovement(Vec3(0, 0, 0), False)
            pos = self.char_np.getPos()
            self.figure.setPos(pos.x, pos.y, pos.z - 2.0)
            self.figure.setH(self.char_np.getH())
            self.figure.setColorScale(0.45, 0.2, 0.2, 1)
            self._animate(dt, False, False)
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

        self._animate(dt, moving, sprinting)

        # Sync visual to physics.
        pos = self.char_np.getPos()
        self.figure.setPos(pos.x, pos.y, pos.z - 2.0)
        self.figure.setH(self.char_np.getH())
        self.figure.setColorScale(1, 1, 1, 1)

    def get_pos(self):
        pos = self.char_np.getPos()
        return Vec3(pos.x, pos.y, pos.z - 2.0)

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
        if style == "melee":
            return dict(UNARMED_MELEE_PROFILE)
        if style == "ranged":
            return dict(UNARMED_RANGED_PROFILE)
        return None

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
        _log_combat(
            f"player swing style={self._auto_attack_style} "
            f"target={target.get_target_name()} damage={profile['damage']}"
        )
        if profile["projectile"]:
            self.fire_target_projectile(target, profile["damage"])
        else:
            target.take_damage(profile["damage"], hud, attacker=self)
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

    def fire_target_projectile(self, target, damage):
        self._clear_expired_target_projectiles()
        origin = self.get_pos() + Vec3(0, 0, 2.2)
        profile = self.get_combat_profile("ranged")
        if profile is None:
            return
        _log_combat(f"player projectile fired target={target.get_target_name()} damage={damage}")
        self.projectiles.append(
            TargetedProjectile(self.render, origin, target, damage, profile, self._on_projectile_hit)
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

    def _on_projectile_hit(self, target, damage, hud):
        _log_combat(f"player projectile hit target={target.get_target_name()} damage={damage}")
        target.take_damage(damage, hud, attacker=self)


def _log_combat(message):
    if DEBUG_COMBAT_LOGS:
        print(f"[combat] {message}")
