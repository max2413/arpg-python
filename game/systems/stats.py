"""Stat calculation and aggregation for entities."""

from game.systems.inventory import get_item_def
from game.systems.balance import (
    HP_BASE,
    block_bonus,
    crit_bonus,
    damage_reduction,
    defense_stat,
    parry_bonus,
    player_max_hp,
    style_damage_bonus,
)

class StatManager:
    def __init__(self, entity, skills=None, inventory=None):
        self.entity = entity
        self.skills = skills
        self.inventory = inventory
        
        # Base stats
        self._base_stats = {
            "max_health": float(HP_BASE),
            "health_regen": 0.0,
            "melee_damage": 5.0,
            "ranged_damage": 5.0,
            "magic_damage": 5.0,
            "armor": 0.0,
            "evasion": 0.05,
            "accuracy": 1.0,
            "crit_chance": 0.05,
            "crit_mult": 1.5,
            "block_chance": 0.0,
            "parry_chance": 0.0,
            "movement_speed": 12.0
        }
        
        # Current calculated stats
        self.stats = dict(self._base_stats)
        self.recalculate()

    def set_base_stat(self, stat_name, value):
        self._base_stats[stat_name] = float(value)
        self.recalculate()

    def get(self, stat_name):
        return self.stats.get(stat_name, 0.0)

    def recalculate(self):
        """Recompute all stats based on base values, skill levels, and equipped gear."""
        # 1. Start with base
        flat_mods = {k: 0.0 for k in self._base_stats}
        mult_mods = {k: 1.0 for k in self._base_stats}

        # 2. Apply Skill Bonuses
        if self.skills is not None:
            melee_lvl = self.skills.get_level("Melee")
            ranged_lvl = self.skills.get_level("Ranged")
            magic_lvl = self.skills.get_level("Magic")
            def_lvl = self.skills.get_level("Defense")

            flat_mods["melee_damage"] += style_damage_bonus(melee_lvl, "melee") - self._base_stats["melee_damage"]
            flat_mods["parry_chance"] += parry_bonus(melee_lvl)

            flat_mods["ranged_damage"] += style_damage_bonus(ranged_lvl, "ranged") - self._base_stats["ranged_damage"]
            flat_mods["crit_chance"] += crit_bonus(ranged_lvl)

            flat_mods["magic_damage"] += style_damage_bonus(magic_lvl, "magic") - self._base_stats["magic_damage"]

            flat_mods["max_health"] += player_max_hp(def_lvl) - self._base_stats["max_health"]
            flat_mods["armor"] += defense_stat(def_lvl)
            flat_mods["block_chance"] += block_bonus(def_lvl)

        # 3. Apply Gear Bonuses
        if self.inventory is not None and hasattr(self.inventory, "equipment"):
            for slot_key in self.inventory.equipment.iter_slot_keys():
                stack = self.inventory.equipment.get_slot(slot_key)
                if stack:
                    item_def = get_item_def(stack["id"])
                    if item_def and "stats" in item_def:
                        gear_stats = item_def["stats"]
                        for k, v in gear_stats.items():
                            if k in flat_mods:
                                flat_mods[k] += v
                            elif k.endswith("_mult"):
                                base_k = k.replace("_mult", "")
                                if base_k in mult_mods:
                                    mult_mods[base_k] += v

        # 4. Final Calculation
        for k in self._base_stats:
            val = (self._base_stats[k] + flat_mods[k]) * mult_mods[k]
            self.stats[k] = val

        armor = self.stats.get("armor", 0.0)
        self.stats["damage_reduction"] = damage_reduction(armor)

        # Handle health capping if max_health drops
        if hasattr(self.entity, "health") and self.entity.health > self.stats["max_health"]:
            self.entity.health = self.stats["max_health"]
