"""Shared combat helpers for profiles, range checks, targeted projectiles, and attack resolution."""

import random
from panda3d.core import Vec3
from game.world.geometry import make_sphere_approx
from game.systems.balance import damage_reduction


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


def resolve_attack(attacker, defender, attack_style, base_damage):
    """
    Resolves combat math: Hit -> Parry -> Block -> Crit -> Armor Mitigation -> Damage.
    Returns a dict with the outcome: {"type": "hit"|"miss"|"parry"|"block"|"crit", "damage": float}
    """
    rng = random.Random()
    
    # Base stats access (with safe fallbacks)
    att_acc = attacker.stats.get("accuracy") if hasattr(attacker, "stats") else 1.0
    def_eva = defender.stats.get("evasion") if hasattr(defender, "stats") else 0.05
    
    # 1. Hit Roll
    hit_chance = max(0.05, min(0.95, att_acc - def_eva))
    if rng.random() > hit_chance:
        return {
            "type": "miss",
            "damage": 0.0,
            "base_damage": base_damage,
            "mitigated": 0.0,
            "attack_style": attack_style,
            "hit_chance": hit_chance,
        }
        
    # 2. Parry Roll (Melee Only)
    if attack_style == "melee":
        def_parry = defender.stats.get("parry_chance") if hasattr(defender, "stats") else 0.0
        if def_parry > 0 and rng.random() < def_parry:
            return {
                "type": "parry",
                "damage": 0.0,
                "base_damage": base_damage,
                "mitigated": base_damage,
                "attack_style": attack_style,
                "hit_chance": hit_chance,
            }
            
    # 3. Block Roll
    def_block = defender.stats.get("block_chance") if hasattr(defender, "stats") else 0.0
    if def_block > 0 and rng.random() < def_block:
        # Block mitigates 70% of damage
        mitigated_damage = base_damage * 0.3
        final_damage = max(1.0, mitigated_damage)
        return {
            "type": "block",
            "damage": final_damage,
            "base_damage": base_damage,
            "mitigated": max(0.0, base_damage - final_damage),
            "attack_style": attack_style,
            "hit_chance": hit_chance,
        }
        
    # 4. Crit Roll
    att_crit = attacker.stats.get("crit_chance") if hasattr(attacker, "stats") else 0.05
    is_crit = rng.random() < att_crit
    if is_crit:
        crit_mult = attacker.stats.get("crit_mult") if hasattr(attacker, "stats") else 1.5
        base_damage *= crit_mult
        
    # 5. Armor Mitigation
    def_armor = defender.stats.get("armor") if hasattr(defender, "stats") else 0.0
    reduction = damage_reduction(def_armor)
    final_damage = max(1.0, base_damage * (1.0 - reduction))
    
    return {
        "type": "crit" if is_crit else "hit",
        "damage": final_damage,
        "base_damage": base_damage,
        "mitigated": max(0.0, base_damage - final_damage),
        "armor_reduction": reduction,
        "attack_style": attack_style,
        "hit_chance": hit_chance,
    }


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
