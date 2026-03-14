"""Skill XP and leveling state."""

SKILLS = ["Woodcutting", "Mining", "Fishing"]
XP_PER_LEVEL = 100


def xp_to_level(xp):
    return int(xp / XP_PER_LEVEL) + 1


def xp_into_level(xp):
    return xp % XP_PER_LEVEL


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
        return xp_into_level(xp), XP_PER_LEVEL
