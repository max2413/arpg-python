"""
player.py — Stick figure geometry, BulletCharacterController, WASD movement.
"""

import math
from panda3d.core import Vec3, LineSegs, NodePath, BitMask32
from panda3d.bullet import BulletCharacterControllerNode, BulletCapsuleShape, ZUp


MOVE_SPEED   = 12.0
SPRINT_MULT  = 5.0   # speed multiplier while shift is held
JUMP_SPEED   = 12.0

# Animation
WALK_FREQ   = 3.5   # cycles per second at walk speed
WALK_AMP    = 35.0  # max swing angle in degrees


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
    skin = (0.9, 0.85, 0.75)

    root = NodePath("stick_figure")

    # --- Static body parts (head, torso) ---
    body = _seg(2.5, *skin)

    # Head circle
    head_r, head_z = 0.4, 3.8
    steps = 16
    first = True
    for i in range(steps + 1):
        angle = math.radians(i * 360 / steps)
        x = head_r * math.cos(angle)
        y = head_r * math.sin(angle)
        if first:
            body.moveTo(x, y, head_z)
            first = False
        else:
            body.drawTo(x, y, head_z)

    # Torso
    body.moveTo(0, 0, head_z - head_r)
    body.drawTo(0, 0, 2.0)

    root.attachNewNode(body.create())

    # --- Direction arrow (static, points local +Y) ---
    arrow = _seg(2.5, 1.0, 0.3, 0.1)
    tip_y = head_r + 0.9
    arrow.moveTo(0, head_r, head_z)
    arrow.drawTo(0, tip_y, head_z)
    arrow.moveTo(0, tip_y, head_z)
    arrow.drawTo(-0.25, tip_y - 0.35, head_z)
    arrow.moveTo(0, tip_y, head_z)
    arrow.drawTo(0.25, tip_y - 0.35, head_z)
    root.attachNewNode(arrow.create())

    # --- Left arm pivot at shoulder (Z=3.2) ---
    l_arm_pivot = root.attachNewNode("l_arm_pivot")
    l_arm_pivot.setPos(0, 0, 3.2)
    la = _seg(2.5, *skin)
    la.moveTo(0, 0, 0)
    la.drawTo(-0.8, 0, -0.7)
    l_arm_pivot.attachNewNode(la.create())

    # --- Right arm pivot at shoulder (Z=3.2) ---
    r_arm_pivot = root.attachNewNode("r_arm_pivot")
    r_arm_pivot.setPos(0, 0, 3.2)
    ra = _seg(2.5, *skin)
    ra.moveTo(0, 0, 0)
    ra.drawTo(0.8, 0, -0.7)
    r_arm_pivot.attachNewNode(ra.create())

    # --- Left leg pivot at hip (Z=2.0) ---
    l_leg_pivot = root.attachNewNode("l_leg_pivot")
    l_leg_pivot.setPos(0, 0, 2.0)
    ll = _seg(2.5, *skin)
    ll.moveTo(0, 0, 0)
    ll.drawTo(-0.5, 0, -1.5)
    l_leg_pivot.attachNewNode(ll.create())

    # --- Right leg pivot at hip (Z=2.0) ---
    r_leg_pivot = root.attachNewNode("r_leg_pivot")
    r_leg_pivot.setPos(0, 0, 2.0)
    rl = _seg(2.5, *skin)
    rl.moveTo(0, 0, 0)
    rl.drawTo(0.5, 0, -1.5)
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
        self._setup_keys()
        self._jump_pending = False

    def _setup_keys(self):
        import builtins
        app = builtins.__dict__.get("base")
        if app is None:
            return

        for key in ("w", "s", "a", "d"):
            app.accept(key, self._set_key, [key, True])
            app.accept(key + "-up", self._set_key, [key, False])

        app.accept("shift",    self._set_sprint, [True])
        app.accept("shift-up", self._set_sprint, [False])
        app.accept("space", self._on_jump)

    def _set_key(self, key, val):
        self._keys[key] = val

    def _set_sprint(self, val):
        self._sprinting = val

    def _on_jump(self):
        if self.char_node.isOnGround():
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

    def update(self, dt, cam_pivot):
        # Extract camera forward and right directly from the pivot's matrix.
        mat = cam_pivot.getMat()
        forward = mat.getRow3(1)
        right = mat.getRow3(0)

        # Flatten to XY plane
        forward.z = 0
        right.z = 0
        if forward.lengthSquared() > 0:
            forward.normalize()
        if right.lengthSquared() > 0:
            right.normalize()

        move = Vec3(0, 0, 0)
        if self._keys["w"]:
            move += forward
        if self._keys["s"]:
            move -= forward
        if self._keys["a"]:
            move -= right
        if self._keys["d"]:
            move += right

        moving = move.lengthSquared() > 0
        sprinting = moving and self._sprinting
        if moving:
            move.normalize()
            self.char_np.setH(math.degrees(math.atan2(-move.x, move.y)))
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

    def get_pos(self):
        pos = self.char_np.getPos()
        return Vec3(pos.x, pos.y, pos.z - 2.0)
