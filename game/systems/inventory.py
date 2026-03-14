"""
inventory.py — Inventory class, item registry, skill/XP data.
"""

ITEMS = {
    "wood": {"name": "Logs",     "stackable": True, "color": (0.4, 0.2, 0.1, 1), "value": 5},
    "ore":  {"name": "Ore",      "stackable": True, "color": (0.5, 0.5, 0.5, 1), "value": 8},
    "fish": {"name": "Raw Fish", "stackable": True, "color": (0.2, 0.5, 0.8, 1), "value": 6},
    "gold": {"name": "Gold",     "stackable": True, "color": (1.0, 0.8, 0.0, 1), "value": 1},
}

SKILLS = ["Woodcutting", "Mining", "Fishing"]

XP_PER_LEVEL = 100


def xp_to_level(xp):
    return int(xp / XP_PER_LEVEL) + 1


def xp_into_level(xp):
    return xp % XP_PER_LEVEL


class Inventory:
    def __init__(self, size=28):
        self.slots = [None] * size
        self.skill_xp = {s: 0 for s in SKILLS}

    # ------------------------------------------------------------------
    # Item methods
    # ------------------------------------------------------------------

    def add_item(self, item_id, qty=1):
        """Stack onto existing slot if stackable, else find free slot.
        Returns True on success, False if full."""
        item = ITEMS.get(item_id)
        if item is None:
            return False

        if item["stackable"]:
            for slot in self.slots:
                if slot and slot["id"] == item_id:
                    slot["quantity"] += qty
                    return True

        # Find first free slot
        for i, slot in enumerate(self.slots):
            if slot is None:
                self.slots[i] = {"id": item_id, "quantity": qty}
                return True

        return False  # inventory full

    def remove_item(self, item_id, qty=1):
        """Decrement quantity; clear slot if reaches 0.
        Returns True if removed, False if not enough."""
        total = self.count_item(item_id)
        if total < qty:
            return False

        remaining = qty
        for i, slot in enumerate(self.slots):
            if slot and slot["id"] == item_id:
                take = min(slot["quantity"], remaining)
                slot["quantity"] -= take
                remaining -= take
                if slot["quantity"] == 0:
                    self.slots[i] = None
                if remaining == 0:
                    return True
        return True

    def count_item(self, item_id):
        return sum(
            s["quantity"] for s in self.slots if s and s["id"] == item_id
        )

    def move_slot(self, a, b):
        self.slots[a], self.slots[b] = self.slots[b], self.slots[a]

    def get_free_slots(self):
        return sum(1 for s in self.slots if s is None)

    def is_full(self):
        return self.get_free_slots() == 0

    # ------------------------------------------------------------------
    # Skill methods
    # ------------------------------------------------------------------

    def add_xp(self, skill, amount):
        if skill in self.skill_xp:
            old_level = xp_to_level(self.skill_xp[skill])
            self.skill_xp[skill] += amount
            new_level = xp_to_level(self.skill_xp[skill])
            return new_level - old_level  # levels gained
        return 0

    def get_level(self, skill):
        return xp_to_level(self.skill_xp.get(skill, 0))

    def get_xp_progress(self, skill):
        """Returns (xp_into_level, XP_PER_LEVEL)."""
        xp = self.skill_xp.get(skill, 0)
        return xp_into_level(xp), XP_PER_LEVEL

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self):
        return {"slots": self.slots[:]}

    def from_dict(self, data):
        slots = data.get("slots", [])
        for i, s in enumerate(slots):
            if i < len(self.slots):
                self.slots[i] = s
