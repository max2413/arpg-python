"""
player.py — Stick figure geometry, BulletCharacterController, WASD movement.
"""

import math
from panda3d.core import Vec3, LineSegs, NodePath, BitMask32, KeyboardButton
from panda3d.bullet import BulletCharacterControllerNode, BulletCapsuleShape, ZUp
from game.world.geometry import make_sphere_approx


MOVE_SPEED   = 12.0
SPRINT_MULT  = 5.0   # speed multiplier while shift is held
JUMP_SPEED   = 12.0
TURN_SPEED   = 180.0
SPRINT_TURN_MULT = 1.6
MAX_HEALTH   = 100
HEALTH_REGEN_DELAY = 6.0
HEALTH_REGEN_RATE  = 4.0
TARGET_PROJECTILE_SPEED = 30.0
TARGET_PROJECTILE_RADIUS = 0.2

# Animation
WALK_FREQ   = 3.5   # cycles per second at walk speed
WALK_AMP    = 35.0  # max swing angle in degrees
TORSO_THICKNESS = 4.0
LIMB_THICKNESS = 3.4
HEAD_Z = 3.8
HEAD_RADIUS = 0.48
MELEE_ABILITY_RANGE = 3.1
RANGED_ABILITY_RANGE = 54.0
MELEE_ABILITY_DAMAGE = 18
RANGED_ABILITY_DAMAGE = 14


def _seg(thickness, r, g, b):
    s = LineSegs()
    s.setThickness(thickness)
    s.setColor(r, g, b, 1)
    return s


def _make_stick_figure():
    """
    Build a stick figure and return (root, left_leg_np, right_leg_np,
    left_arm_np, right_arm_np).

    Legs pivot at the hip (Z=2.0) around the X axis (swing forward/back).
    Arms pivot at the shoulder (Z=3.2) around the X axis (counter-swing).
    Each limb NodePath has its geometry drawn with the pivot at the origin.
    """
    skin_rgb = (0.9, 0.85, 0.75)
    skin_rgba = (0.9, 0.85, 0.75, 1.0)
    debug_arrow = (1.0, 0.3, 0.1)

    root = NodePath("stick_figure")

    # --- Static body parts (head, torso) ---
    body = _seg(TORSO_THICKNESS, *skin_rgb)
    # Torso
    body.moveTo(0, 0, HEAD_Z - HEAD_RADIUS)
    body.drawTo(0, 0, 2.0)
    root.attachNewNode(body.create())

    head = root.attachNewNode(make_sphere_approx(HEAD_RADIUS, skin_rgba))
    head.setPos(0, 0, HEAD_Z)

    # --- Direction arrow (static, above head, points local +Y) ---
    arrow = _seg(LIMB_THICKNESS, *debug_arrow)
    arrow_base_z = HEAD_Z + 0.9
    arrow_tip_y = 0.9
    arrow.moveTo(0, 0, arrow_base_z)
    arrow.drawTo(0, arrow_tip_y, arrow_base_z)
    arrow.moveTo(0, arrow_tip_y, arrow_base_z)
    arrow.drawTo(-0.22, arrow_tip_y - 0.28, arrow_base_z)
    arrow.moveTo(0, arrow_tip_y, arrow_base_z)
    arrow.drawTo(0.22, arrow_tip_y - 0.28, arrow_base_z)
    root.attachNewNode(arrow.create())

    # --- Left arm pivot at shoulder (Z=3.2) ---
    l_arm_pivot = root.attachNewNode("l_arm_pivot")
    l_arm_pivot.setPos(0, 0, 3.2)
    la = _seg(LIMB_THICKNESS, *skin_rgb)
    la.moveTo(0, 0, 0)
    la.drawTo(-0.95, 0, -0.85)
    l_arm_pivot.attachNewNode(la.create())

    # --- Right arm pivot at shoulder (Z=3.2) ---
    r_arm_pivot = root.attachNewNode("r_arm_pivot")
    r_arm_pivot.setPos(0, 0, 3.2)
    ra = _seg(LIMB_THICKNESS, *skin_rgb)
    ra.moveTo(0, 0, 0)
    ra.drawTo(0.95, 0, -0.85)
    r_arm_pivot.attachNewNode(ra.create())

    # --- Left leg pivot at hip (Z=2.0) ---
    l_leg_pivot = root.attachNewNode("l_leg_pivot")
    l_leg_pivot.setPos(0, 0, 2.0)
    ll = _seg(LIMB_THICKNESS, *skin_rgb)
    ll.moveTo(0, 0, 0)
    ll.drawTo(-0.58, 0, -1.7)
    l_leg_pivot.attachNewNode(ll.create())

    # --- Right leg pivot at hip (Z=2.0) ---
    r_leg_pivot = root.attachNewNode("r_leg_pivot")
    r_leg_pivot.setPos(0, 0, 2.0)
    rl = _seg(LIMB_THICKNESS, *skin_rgb)
    rl.moveTo(0, 0, 0)
    rl.drawTo(0.58, 0, -1.7)
    r_leg_pivot.attachNewNode(rl.create())

    return root, l_leg_pivot, r_leg_pivot, l_arm_pivot, r_arm_pivot


class Player:
    def __init__(self, render, bullet_world, inventory):
        self.render = render
        self.bullet_world = bullet_world
        self.inventory = inventory

        # Visual
        (self.figure,
         self._l_leg, self._r_leg,
         self._l_arm, self._r_arm) = _make_stick_figure()
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
        self._app = None
        self._mouse_watcher = None
        self._setup_keys()
        self._jump_pending = False
        self.max_health = MAX_HEALTH
        self.health = float(self.max_health)
        self.dead = False
        self._time_since_damage = HEALTH_REGEN_DELAY
        self.melee_ability_range = MELEE_ABILITY_RANGE
        self.ranged_ability_range = RANGED_ABILITY_RANGE
        self.melee_ability_damage = MELEE_ABILITY_DAMAGE
        self.ranged_ability_damage = RANGED_ABILITY_DAMAGE
        self.projectiles = []

    def _setup_keys(self):
        import builtins
        app = builtins.__dict__.get("base")
        if app is None:
            return
        self._app = app
        self._mouse_watcher = app.mouseWatcherNode

        app.accept("space", self._on_jump)

    def _on_jump(self):
        if not self.dead and self.char_node.isOnGround():
            self._jump_pending = True

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
        self._clear_projectiles()
        self.char_np.setPos(*pos)
        self.char_node.setLinearMovement(Vec3(0, 0, 0), False)
        self.char_np.setH(0)
        self.figure.setColorScale(1, 1, 1, 1)
        self.figure.setPos(pos[0], pos[1], pos[2] - 2.0)
        self.figure.setH(0)

    def update(self, dt, cam_pivot):
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
        sprinting = moving and self._sprinting
        if moving:
            move.normalize()
            speed = MOVE_SPEED * (SPRINT_MULT if sprinting else 1.0)
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

    def is_moving(self):
        return self._keys["w"] or self._keys["s"]

    def is_advancing(self):
        return self._keys["w"]

    def _poll_input(self):
        if self._mouse_watcher is None:
            return
        watcher = self._mouse_watcher
        self._keys["w"] = watcher.isButtonDown(KeyboardButton.ascii_key("w"))
        self._keys["s"] = watcher.isButtonDown(KeyboardButton.ascii_key("s"))
        self._keys["a"] = watcher.isButtonDown(KeyboardButton.ascii_key("a"))
        self._keys["d"] = watcher.isButtonDown(KeyboardButton.ascii_key("d"))
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
        self.projectiles.append(TargetProjectile(self.render, origin, target, damage))

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


class TargetProjectile:
    def __init__(self, render, origin, target, damage):
        self.render = render
        self.pos = Vec3(origin)
        self.target = target
        self.damage = damage
        self.expired = False

        self.root = render.attachNewNode("target_projectile")
        self.root.setPos(self.pos)
        orb = self.root.attachNewNode(make_sphere_approx(TARGET_PROJECTILE_RADIUS, (0.95, 0.78, 0.22, 1)))
        orb.setPos(0, 0, 0)

    def update(self, dt, hud):
        if self.target is None or not self.target.is_targetable():
            self.remove()
            self.expired = True
            return True

        target_pos = self.target.get_target_point()
        delta = target_pos - self.pos
        dist = delta.length()
        if dist <= 0.35:
            self.target.take_damage(self.damage, hud)
            self.remove()
            self.expired = True
            return True

        delta.normalize()
        self.pos += delta * min(dist, TARGET_PROJECTILE_SPEED * dt)
        self.root.setPos(self.pos)
        return False

    def remove(self):
        if not self.root.isEmpty():
            self.root.removeNode()
