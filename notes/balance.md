# Game Balance Strategy

## Design Intent

Fast early levels, gradual mid-game, meaningful late-game grind. Combat feels
snappy at all levels — fights last 8–15 seconds against even-level enemies.
Gear matters more at high levels. Defense never makes a character invincible.
Enemies have a fixed level assigned by the designer — no zone scaling.

---

## Central Tuning Factors

All formulas derive from these constants. Change here, everything updates.

```python
# balance.py — single source of truth

# XP curve
XP_BASE       = 200    # base XP cost at level 1
XP_EXPONENT   = 1.5    # steepness of late-game grind (1.2 casual → 2.0 hardcore)
XP_EARLY_BOOST = 0     # flat XP removed from low levels (tapers off at level 8)
                       # set 100-200 for RuneScape-style fast early levels

# Player stats
HP_BASE       = 50     # HP at level 1
HP_PER_LEVEL  = 10     # linear HP gain per level

# Enemy stats
ENEMY_HP_BASE = 30     # enemy HP at level 1
ENEMY_HP_EXP  = 1.8    # enemy HP scaling per level (quadratic-ish, pulls ahead of player)

# Damage
DMG_BASE      = 5      # base damage coefficient
DMG_LVL_EXP  = 0.7    # player level contribution to damage (sub-linear)
DMG_TIER_EXP = 1.4    # weapon tier contribution to damage (super-linear)
                       # gear gap widens at high levels by design

# Defense
DEF_SCALE     = 3      # defense stat gained per level (used in reduction formula)
                       # reduction = (def) / (def + 100) — never reaches 100%

# Combat
ATTACKS_PER_SEC = 1.5  # base attack speed
WEAPON_TIER_SIZE = 5   # levels per weapon tier (tier = ceil(level / WEAPON_TIER_SIZE))
```

---

## Derived Formulas

```python
import math

def xp_for_level(level):
    raw = int(XP_BASE * (level ** XP_EXPONENT))
    boost = int(XP_EARLY_BOOST * max(0, 1 - (level - 1) / 8))
    return max(10, raw - boost)

def player_max_hp(level):
    return HP_BASE + level * HP_PER_LEVEL

def enemy_max_hp(enemy_level):
    return int(ENEMY_HP_BASE * (enemy_level ** ENEMY_HP_EXP))

def weapon_tier(level):
    return math.ceil(level / WEAPON_TIER_SIZE)

def base_damage(level):
    tier = weapon_tier(level)
    return int(DMG_BASE * (level ** DMG_LVL_EXP) * (tier ** DMG_TIER_EXP))

def defense_stat(level):
    return level * DEF_SCALE

def damage_reduction(defense):
    return defense / (defense + 100)          # logistic, asymptotes below 1.0

def effective_damage(level):
    dr = damage_reduction(defense_stat(level))
    return base_damage(level) * (1 - dr)

def time_to_kill(player_level, enemy_level):
    return enemy_max_hp(enemy_level) / (effective_damage(player_level) * ATTACKS_PER_SEC)
```

---

## Target Benchmarks

Use these to validate tuning against an even-level fight (player level == enemy level).
If TTK drifts outside range, adjust `ENEMY_HP_EXP` or `DMG_LVL_EXP` before touching anything else.

| Level | XP required | Player HP | Enemy HP | TTK target |
|-------|-------------|-----------|----------|------------|
| 1     | 200         | 60        | 30       | 8–12s      |
| 5     | 1,789       | 100       | 506      | 8–15s      |
| 10    | 6,325       | 150       | 1,896    | 8–15s      |
| 20    | 22,627      | 250       | 6,736    | 10–18s     |

---

## Preset Reference

| Feel | `XP_EXPONENT` | `XP_BASE` | `XP_EARLY_BOOST` |
|------|---------------|-----------|------------------|
| Casual | 1.2 | 100 | 80 |
| Classic JRPG | 1.5 | 200 | 0 |
| RuneScape-style | 2.0 | 100 | 150 |
| Late-game grind | 2.2 | 300 | 0 |

---

## Skill XP (Gathering)

Gathering skills (Woodcutting, Mining, Fishing) use the same formula with their
own constants. Import and override as needed.

```python
SKILL_XP_BASE      = 100   # lower than combat — skills level faster early
SKILL_XP_EXPONENT  = 1.4
SKILL_XP_PER_NODE  = {
    "wood": 25,
    "ore":  40,
    "fish": 30,
}
```

Skill level gates resource nodes — e.g. level 1 for basic trees, level 10 for
better ore — giving the XP curve a natural content drip without zone scaling.

---

## Rebalancing Checklist

When something feels off, adjust in this order — do not change multiple
constants at once or the interaction effects become hard to read.

1. **Fight too short/long?** → adjust `ENEMY_HP_EXP` first
2. **Player too squishy/tanky?** → adjust `HP_PER_LEVEL`
3. **Gear not mattering enough?** → raise `DMG_TIER_EXP`
4. **Early levels too slow?** → raise `XP_EARLY_BOOST`
5. **Late game not grindy enough?** → raise `XP_EXPONENT`
6. **Defense feels like god mode?** → lower `DEF_SCALE`

Always re-run the TTK check at even level (player == enemy) across levels 1, 5, 10, 20 after any change.