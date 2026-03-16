"""Stat calculation and aggregation for entities."""

from game.systems.inventory import get_item_def

class StatManager:
    def __init__(self, entity, skills=None, inventory=None):
        self.entity = entity
        self.skills = skills
        self.inventory = inventory
        
        # Base stats
        self._base_stats = {
            "max_health": 100.0,
            "health_regen": 0.0,
            "melee_damage": 18.0,
            "ranged_damage": 14.0,
            "magic_damage": 10.0,
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

            flat_mods["melee_damage"] += (melee_lvl - 1) * 1.5
            flat_mods["parry_chance"] += (melee_lvl - 1) * 0.005
            
            flat_mods["ranged_damage"] += (ranged_lvl - 1) * 1.2
            flat_mods["crit_chance"] += (ranged_lvl - 1) * 0.005
            
            flat_mods["magic_damage"] += (magic_lvl - 1) * 1.8
            
            flat_mods["max_health"] += (def_lvl - 1) * 10.0
            flat_mods["armor"] += (def_lvl - 1) * 0.5
            flat_mods["block_chance"] += (def_lvl - 1) * 0.005

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

        # Handle health capping if max_health drops
        if hasattr(self.entity, "health") and self.entity.health > self.stats["max_health"]:
            self.entity.health = self.stats["max_health"]
