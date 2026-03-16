"""Skill XP, combat level, and leveling state."""

from game.systems.balance import (
    COMBAT_SKILLS,
    combat_level_from_skill_levels,
    level_to_xp,
    xp_for_next_level,
    xp_into_level,
    xp_to_level,
)


SKILLS = [
    "Melee", "Ranged", "Magic", "Defense",
    "Woodcutting", "Mining", "Fishing", "Skinning", "Foraging",
    "Blacksmithing", "Tailoring", "Cooking", "Alchemy"
]


class Skills:
    def __init__(self):
        self.skill_xp = {skill: 0 for skill in SKILLS}

    def add_xp(self, skill, amount):
        if skill not in self.skill_xp:
            return 0
        old_level = xp_to_level(self.skill_xp[skill])
        self.skill_xp[skill] += amount
        new_level = xp_to_level(self.skill_xp[skill])
        return new_level - old_level

    def get_level(self, skill):
        return xp_to_level(self.skill_xp.get(skill, 0))

    def set_level(self, skill, level):
        if skill not in self.skill_xp:
            return False
        self.skill_xp[skill] = level_to_xp(max(1, int(level)))
        return True

    def set_levels(self, level_map):
        changed = False
        for skill, level in level_map.items():
            changed = self.set_level(skill, level) or changed
        return changed

    def reset_combat_skills(self):
        for skill in COMBAT_SKILLS:
            self.skill_xp[skill] = 0

    def get_combat_level(self):
        return combat_level_from_skill_levels(
            self.get_level("Melee"),
            self.get_level("Ranged"),
            self.get_level("Magic"),
            self.get_level("Defense"),
        )

    def get_xp_progress(self, skill):
        xp = self.skill_xp.get(skill, 0)
        return xp_into_level(xp), xp_for_next_level(xp)

    def to_dict(self):
        return {"skill_xp": self.skill_xp.copy()}

    def from_dict(self, data):
        xp_data = data.get("skill_xp", {})
        for skill in SKILLS:
            if skill in xp_data:
                self.skill_xp[skill] = int(xp_data[skill])
