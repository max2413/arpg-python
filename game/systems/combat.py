"""Shared combat helpers for profiles, range checks, and targeted projectiles."""

from panda3d.core import Vec3

from game.world.geometry import make_sphere_approx


def make_combat_profile(
    name,
    max_range,
    speed,
    damage,
    projectile=False,
    min_range=0.0,
    preferred_range=None,
    projectile_speed=0.0,
    projectile_radius=0.2,
    projectile_color=(1, 1, 1, 1),
):
    return {
        "name": name,
        "range": max_range,
        "speed": speed,
        "damage": damage,
        "projectile": projectile,
        "min_range": min_range,
        "preferred_range": preferred_range,
        "projectile_speed": projectile_speed,
        "projectile_radius": projectile_radius,
        "projectile_color": projectile_color,
    }


def planar_distance(a, b):
    delta = Vec3(b - a)
    delta.z = 0
    return delta.length()


def in_attack_range(attacker_pos, target_pos, profile):
    distance = planar_distance(attacker_pos, target_pos)
    return profile["min_range"] <= distance <= profile["range"]


def stop_distance_for(profile):
    preferred = profile.get("preferred_range")
    if preferred is None:
        preferred = profile["range"] if profile["projectile"] else max(0.0, profile["range"] - 0.4)
    return max(profile["min_range"], min(preferred, profile["range"]))


class TargetedProjectile:
    def __init__(self, render, origin, target, damage, profile, on_hit):
        self.pos = Vec3(origin)
        self.target = target
        self.damage = damage
        self.profile = profile
        self.on_hit = on_hit
        self.expired = False

        self.root = render.attachNewNode("targeted_projectile")
        self.root.setPos(self.pos)
        orb = self.root.attachNewNode(
            make_sphere_approx(profile["projectile_radius"], profile["projectile_color"])
        )
        orb.setPos(0, 0, 0)

    def update(self, dt, hit_context=None):
        if self.target is None or not self.target.is_targetable():
            self.remove()
            self.expired = True
            return True

        target_pos = self.target.get_target_point()
        delta = target_pos - self.pos
        dist = delta.length()
        if dist <= max(0.35, self.profile["projectile_radius"] + 0.15):
            self.on_hit(self.target, self.damage, hit_context)
            self.remove()
            self.expired = True
            return True

        if dist > 0:
            delta.normalize()
        self.pos += delta * min(dist, self.profile["projectile_speed"] * dt)
        self.root.setPos(self.pos)
        return False

    def remove(self):
        if not self.root.isEmpty():
            self.root.removeNode()
