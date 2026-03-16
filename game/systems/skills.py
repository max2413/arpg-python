"""Skill XP and leveling state."""

SKILLS = [
    "Melee", "Ranged", "Magic", "Defense",
    "Woodcutting", "Mining", "Fishing", "Skinning", "Foraging",
    "Blacksmithing", "Tailoring", "Cooking", "Alchemy"
]

def xp_to_level(xp):
    if xp < 100:
        return 1
    # Exponential curve: Level = (XP / 100) ^ (1/1.5)
    # Plus 1 so 0 xp = lvl 1, 100 xp = lvl 2.
    # We want 100 xp to get you to level 2.
    # Level 2 -> 100 * (1^1.5) = 100
    # Level 3 -> 100 * (2^1.5) = ~282
    # Level 10 -> 100 * (9^1.5) = 2700
    return int((xp / 100.0) ** (1.0 / 1.5)) + 1


def level_to_xp(level):
    if level <= 1:
        return 0
    return int(100.0 * ((level - 1) ** 1.5))


def xp_into_level(xp):
    current_lvl = xp_to_level(xp)
    base_xp = level_to_xp(current_lvl)
    return max(0, xp - base_xp)


def xp_for_next_level(xp):
    current_lvl = xp_to_level(xp)
    next_level_xp = level_to_xp(current_lvl + 1)
    base_xp = level_to_xp(current_lvl)
    return next_level_xp - base_xp


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
