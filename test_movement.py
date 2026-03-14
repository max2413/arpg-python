"""
test_movement.py — Legacy movement math scratchpad.

Run with: ppython test_movement.py

Note: the live game currently uses heading-based movement rather than the
camera-relative model explored in this file. Keep it only as a reference
for future control experiments.

Panda3D heading convention (setH, CCW around Z):
  H=0   → pivot +Y faces world +Y (north).  forward=( 0, 1), right=(1, 0)
  H=-90 → pivot +Y faces world +X (east).   forward=( 1, 0), right=(0,-1)  ← wait...

Actually from the debug output:
  HPR=(17.4,...) → fwd=(-0.30,0.95) = (-sin H, cos H)
                   row0=(0.95,0.30) = ( cos H, sin H)

row0 = (cos H, sin H). At H=0: row0=(1,0) = world +X = camera RIGHT. ✓
  D should go +X → move += right = move += row0  (original code)
  A should go -X → move -= right = move -= row0  (original code)

So original A/D was correct. The problem must be elsewhere.
Let's verify W/S with the same formula:
  forward = (-sin H, cos H). At H=0: forward=(0,1) = world +Y. ✓
  W → move += forward → (+Y). ✓
  S → move -= forward → (-Y). ✓

Everything is geometrically correct! The test just needs correct expected values.
"""

import math
from panda3d.core import Vec3, LMatrix4, LVecBase3


def make_pivot_mat(heading_deg):
    """Return a 4x4 matrix representing a pivot with the given heading (Z-up rotation)."""
    mat = LMatrix4()
    mat.setRotateMat(heading_deg, LVecBase3(0, 0, 1))
    return mat


def compute_velocity(mat, keys, speed=1.0):
    """Replicate the player.py movement logic exactly.
    Note: player.py passes -velocity to setLinearMovement due to Panda3D
    Bullet world-space inversion in this version. The facing/arrow direction
    is computed from the un-negated move vector (correct), while the physics
    velocity is negated. Tests here verify the move vector direction only."""
    forward = mat.getRow3(1)
    right = mat.getRow3(0)

    forward.z = 0
    right.z = 0
    if forward.lengthSquared() > 0:
        forward.normalize()
    if right.lengthSquared() > 0:
        right.normalize()

    move = Vec3(0, 0, 0)
    if keys.get("w"):
        move += forward
    if keys.get("s"):
        move -= forward
    if keys.get("a"):
        move -= right
    if keys.get("d"):
        move += right

    if move.lengthSquared() > 0:
        move.normalize()
        return move * speed
    return Vec3(0, 0, 0)


def approx(a, b, tol=0.001):
    return abs(a - b) < tol


def check(label, vel, ex, ey):
    ok = approx(vel.x, ex) and approx(vel.y, ey)
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}: got ({vel.x:+.3f}, {vel.y:+.3f})  expected ({ex:+.3f}, {ey:+.3f})")
    return ok


def run_tests():
    failures = 0
    total = 0

    # Derived from Panda3D CCW heading convention:
    #   forward = (-sin H, cos H)   [getRow3(1)]
    #   right   = ( cos H, sin H)   [getRow3(0)]
    #
    # D → move += right   A → move -= right

    s = 1 / math.sqrt(2)

    print("=" * 60)
    print("H=0° — camera faces +Y (north).  fwd=(0,1)  right=(1,0)")
    print("=" * 60)
    mat = make_pivot_mat(0)
    # forward=(0,1), right=(1,0)
    cases = [
        ("W",   {"w": True},  0.0,  1.0),
        ("S",   {"s": True},  0.0, -1.0),
        ("D",   {"d": True},  1.0,  0.0),   # +right = (1,0) = east ✓
        ("A",   {"a": True}, -1.0,  0.0),   # -right = (-1,0) = west ✓
        ("W+D", {"w": True, "d": True},  s,  s),
        ("W+A", {"w": True, "a": True}, -s,  s),
    ]
    for label, keys, ex, ey in cases:
        total += 1
        v = compute_velocity(mat, keys)
        if not check(label, v, ex, ey):
            failures += 1

    print()
    print("=" * 60)
    print("H=-90° — camera faces +X (east).  fwd=(1,0)  right=(0,-1)")
    print("=" * 60)
    mat = make_pivot_mat(-90)
    # forward=(1,0), right=(0,-1)
    cases = [
        ("W",  {"w": True},  1.0,  0.0),
        ("S",  {"s": True}, -1.0,  0.0),
        ("D",  {"d": True},  0.0, -1.0),   # +right = (0,-1) = south ✓
        ("A",  {"a": True},  0.0,  1.0),   # -right = (0,1)  = north ✓
    ]
    for label, keys, ex, ey in cases:
        total += 1
        v = compute_velocity(mat, keys)
        if not check(label, v, ex, ey):
            failures += 1

    print()
    print("=" * 60)
    print("H=90° — camera faces -X (west).  fwd=(-1,0)  right=(0,1)")
    print("=" * 60)
    mat = make_pivot_mat(90)
    # forward=(-1,0), right=(0,1)
    cases = [
        ("W",  {"w": True}, -1.0,  0.0),
        ("S",  {"s": True},  1.0,  0.0),
        ("D",  {"d": True},  0.0,  1.0),   # +right = (0,1) = north ✓
        ("A",  {"a": True},  0.0, -1.0),   # -right = (0,-1) = south ✓
    ]
    for label, keys, ex, ey in cases:
        total += 1
        v = compute_velocity(mat, keys)
        if not check(label, v, ex, ey):
            failures += 1

    print()
    print("=" * 60)
    print("H=180° — camera faces -Y (south).  fwd=(0,-1)  right=(-1,0)")
    print("=" * 60)
    mat = make_pivot_mat(180)
    # forward=(0,-1), right=(-1,0)
    cases = [
        ("W",  {"w": True},  0.0, -1.0),
        ("S",  {"s": True},  0.0,  1.0),
        ("D",  {"d": True}, -1.0,  0.0),   # +right = (-1,0) = west ✓
        ("A",  {"a": True},  1.0,  0.0),   # -right = (1,0)  = east ✓
    ]
    for label, keys, ex, ey in cases:
        total += 1
        v = compute_velocity(mat, keys)
        if not check(label, v, ex, ey):
            failures += 1

    print()
    print("=" * 60)
    print(f"Results: {total - failures}/{total} passed")
    print("=" * 60)
    return failures


if __name__ == "__main__":
    failures = run_tests()
    raise SystemExit(0 if failures == 0 else 1)
