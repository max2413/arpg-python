"""Shared balance constants and progression helpers."""

from __future__ import annotations

import math

# XP curve
XP_BASE = 200
XP_EXPONENT = 1.5
XP_EARLY_BOOST = 0

# Player stats
HP_BASE = 50
HP_PER_LEVEL = 10

# Enemy reference helpers
ENEMY_HP_BASE = 30
ENEMY_HP_EXP = 1.55

# Damage
DMG_BASE = 5
DMG_LVL_EXP = 0.7
DMG_TIER_EXP = 1.4

# Defense
DEF_SCALE = 3

# Combat
ATTACKS_PER_SEC = 1.5
WEAPON_TIER_SIZE = 5

# Combat level display weights
COMBAT_LEVEL_OFFENSE_WEIGHT = 0.65
COMBAT_LEVEL_DEFENSE_WEIGHT = 0.35

COMBAT_SKILLS = ("Melee", "Ranged", "Magic", "Defense")
OFFENSIVE_SKILLS = ("Melee", "Ranged", "Magic")
CREATURE_SCALING_KEYS = (
    "health_factor",
    "armor_factor",
    "damage_factor",
    "evasion_factor",
    "accuracy_factor",
    "crit_factor",
    "block_factor",
    "parry_factor",
)
CREATURE_ROLE_FACTORS = {
    "critter": {
        "health_factor": 0.3,
        "armor_factor": 0.5,
        "damage_factor": 0.4,
        "evasion_factor": 1.2,
        "accuracy_factor": 0.9,
        "crit_factor": 0.5,
        "block_factor": 0.0,
        "parry_factor": 0.0,
        "xp_multiplier": 0.5,
    },
    "normal": {
        "health_factor": 1.0,
        "armor_factor": 1.0,
        "damage_factor": 1.0,
        "evasion_factor": 1.0,
        "accuracy_factor": 1.0,
        "crit_factor": 1.0,
        "block_factor": 1.0,
        "parry_factor": 1.0,
        "xp_multiplier": 1.0,
    },
    "elite": {
        "health_factor": 2.5,
        "armor_factor": 1.2,
        "damage_factor": 1.4,
        "evasion_factor": 1.1,
        "accuracy_factor": 1.05,
        "crit_factor": 1.2,
        "block_factor": 1.2,
        "parry_factor": 1.2,
        "xp_multiplier": 3.0,
    },
    "boss": {
        "health_factor": 8.0,
        "armor_factor": 1.5,
        "damage_factor": 2.0,
        "evasion_factor": 1.2,
        "accuracy_factor": 1.1,
        "crit_factor": 1.5,
        "block_factor": 1.5,
        "parry_factor": 1.5,
        "xp_multiplier": 10.0,
    },
}


def xp_boost_for_level(level):
    if level <= 1:
        return XP_EARLY_BOOST
    taper = max(0.0, 1.0 - ((level - 1) / 8.0))
    return int(XP_EARLY_BOOST * taper)


def level_to_xp(level):
    """Total XP required to reach the given level."""
    if level <= 1:
        return 0
    rank = level - 1
    raw = int(XP_BASE * (rank ** XP_EXPONENT))
    return max(10, raw - xp_boost_for_level(level))


def xp_to_level(xp):
    if xp <= 0:
        return 1
    level = 1
    while level_to_xp(level + 1) <= xp:
        level += 1
    return level


def xp_into_level(xp):
    current_level = xp_to_level(xp)
    return max(0, xp - level_to_xp(current_level))


def xp_for_next_level(xp):
    current_level = xp_to_level(xp)
    return max(1, level_to_xp(current_level + 1) - level_to_xp(current_level))


def player_max_hp(level):
    return HP_BASE + (max(1, level) * HP_PER_LEVEL)


def enemy_max_hp(level):
    return int(ENEMY_HP_BASE * (max(1, level) ** ENEMY_HP_EXP))


def creature_max_hp_for_level(level):
    """Default creature durability derived directly from the shared enemy curve."""
    return float(enemy_max_hp(level))


def creature_base_damage(level):
    """Creature damage scales by level only; gear tiers are a player-only source of spikes."""
    return float(max(1, int(DMG_BASE * (max(1, level) ** DMG_LVL_EXP))))


def weapon_tier(level):
    return max(1, math.ceil(max(1, level) / WEAPON_TIER_SIZE))


def base_damage(level):
    tier = weapon_tier(level)
    return int(DMG_BASE * (max(1, level) ** DMG_LVL_EXP) * (tier ** DMG_TIER_EXP))


def defense_stat(level):
    return max(1, level) * DEF_SCALE


def creature_armor_for_level(level):
    return max(0.0, defense_stat(level) * 0.6)


def creature_evasion_for_level(level):
    level = max(1, int(level))
    return min(0.35, 0.03 + ((level - 1) * 0.005))


def creature_accuracy_for_level(level):
    level = max(1, int(level))
    return min(1.2, 0.95 + ((level - 1) * 0.008))


def creature_crit_for_level(level):
    level = max(1, int(level))
    return min(0.25, 0.03 + ((level - 1) * 0.003))


def creature_block_for_level(level):
    level = max(1, int(level))
    return min(0.18, (level - 1) * 0.0025)


def creature_parry_for_level(level):
    level = max(1, int(level))
    return min(0.18, (level - 1) * 0.0025)


def creature_style_damage(level, style):
    damage = creature_base_damage(level)
    if style == "ranged":
        return damage * 0.95
    if style == "magic":
        return damage * 1.05
    return damage


def creature_scaling_factors(role="normal", scaling=None):
    role_key = str(role or "normal").lower()
    factors = dict(CREATURE_ROLE_FACTORS.get(role_key, CREATURE_ROLE_FACTORS["normal"]))
    for key in CREATURE_SCALING_KEYS:
        factors[key] *= float((scaling or {}).get(key, 1.0))
    return factors


def creature_scaled_stats(level, style="melee", role="normal", scaling=None):
    factors = creature_scaling_factors(role, scaling)
    style_key = str(style or "melee").lower()
    stats = {
        "max_health": creature_max_hp_for_level(level) * factors["health_factor"],
        "armor": creature_armor_for_level(level) * factors["armor_factor"],
        "evasion": creature_evasion_for_level(level) * factors["evasion_factor"],
        "accuracy": creature_accuracy_for_level(level) * factors["accuracy_factor"],
        "crit_chance": creature_crit_for_level(level) * factors["crit_factor"],
        "block_chance": creature_block_for_level(level) * factors["block_factor"],
        "parry_chance": creature_parry_for_level(level) * factors["parry_factor"],
    }
    damage = creature_style_damage(level, style_key) * factors["damage_factor"]
    stats[f"{style_key}_damage"] = damage
    return {
        key: max(0.0, float(value))
        for key, value in stats.items()
    }


def creature_runtime_stats(creature_def):
    creature_def = creature_def or {}
    level = int(creature_def.get("level", 1))
    combat = creature_def.get("combat", {})
    style = combat.get("style", "melee")
    role = creature_def.get("role", "normal")
    scaling = creature_def.get("scaling", {})
    stats = creature_scaled_stats(level, style=style, role=role, scaling=scaling)
    stats.update(creature_def.get("stats", {}))
    return stats


def damage_reduction(defense):
    defense = max(0.0, float(defense))
    return defense / (defense + 100.0)


def effective_damage(level):
    reduction = damage_reduction(defense_stat(level))
    return base_damage(level) * (1.0 - reduction)


def time_to_kill(player_level, enemy_level):
    return enemy_max_hp(enemy_level) / max(1.0, effective_damage(player_level) * ATTACKS_PER_SEC)


def style_damage_bonus(level, style):
    level = max(1, int(level))
    value = base_damage(level)
    if style == "melee":
        return float(value)
    if style == "ranged":
        return float(max(1, int(value * 0.92)))
    if style == "magic":
        return float(max(1, int(value * 1.05)))
    raise ValueError(f"Unknown combat style: {style}")


def parry_bonus(level):
    return max(0.0, (max(1, level) - 1) * 0.004)


def crit_bonus(level):
    return max(0.0, (max(1, level) - 1) * 0.004)


def block_bonus(level):
    return max(0.0, (max(1, level) - 1) * 0.003)


def combat_level_from_skill_levels(melee, ranged, magic, defense):
    top_offense = max(int(melee), int(ranged), int(magic))
    combat_level = math.floor(
        (top_offense * COMBAT_LEVEL_OFFENSE_WEIGHT) +
        (int(defense) * COMBAT_LEVEL_DEFENSE_WEIGHT)
    )
    return max(1, combat_level)


def recommended_combat_preset(target_level, primary_style="Melee"):
    target_level = max(1, int(target_level))
    primary_style = primary_style.title()
    preset = {skill: 1 for skill in COMBAT_SKILLS}
    if primary_style not in OFFENSIVE_SKILLS:
        primary_style = "Melee"
    preset[primary_style] = target_level
    preset["Defense"] = max(1, target_level)
    return preset


def benchmark_rows(levels=(1, 5, 10, 20)):
    rows = []
    for level in levels:
        rows.append(
            {
                "level": level,
                "xp_required": level_to_xp(level + 1),
                "player_hp": player_max_hp(level),
                "enemy_hp": enemy_max_hp(level),
                "ttk": time_to_kill(level, level),
            }
        )
    return rows
