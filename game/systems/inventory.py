"""Inventory containers and item registry."""

import copy
import json
import os


ITEM_CATEGORY_RAW = "raw_material"
ITEM_CATEGORY_CURRENCY = "currency"
ITEM_CATEGORY_EQUIPMENT = "equipment"

EQUIPMENT_SLOTS = {
    "head": {"label": "Head"},
    "chest": {"label": "Chest"},
    "legs": {"label": "Legs"},
    "weapon": {"label": "Weapon"},
    "offhand": {"label": "Offhand"},
}

ITEMS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "items.json",
)


def _normalize_item_defs(raw_items):
    items = {}
    for item_id, item_def in raw_items.items():
        normalized = dict(item_def)
        normalized["color"] = tuple(normalized["color"])
        items[item_id] = normalized
    return items


def _load_items():
    with open(ITEMS_PATH) as handle:
        return _normalize_item_defs(json.load(handle))


ITEMS = _load_items()

def get_item_def(item_id):
    return ITEMS.get(item_id)


def get_item_name(item_id):
    item_def = get_item_def(item_id)
    return item_def["name"] if item_def else item_id


def is_stackable(item_id):
    item_def = get_item_def(item_id)
    return bool(item_def and item_def.get("stackable"))


def is_equipment_item(item_id):
    item_def = get_item_def(item_id)
    return bool(item_def and item_def.get("category") == ITEM_CATEGORY_EQUIPMENT)


def get_equipment_slot(item_id):
    item_def = get_item_def(item_id)
    if item_def is None:
        return None
    return item_def.get("equipment_slot")


def clone_stack(stack):
    if stack is None:
        return None
    return {"id": stack["id"], "quantity": int(stack["quantity"])}


class Inventory:
    def __init__(self, size=28):
        self.slots = [None] * size
        self.equipment = EquipmentInventory()

    def slot_count(self):
        return len(self.slots)

    def iter_slot_keys(self):
        return list(range(len(self.slots)))

    def get_slot(self, slot_index):
        if 0 <= slot_index < len(self.slots):
            return self.slots[slot_index]
        return None

    def set_slot(self, slot_index, stack):
        if 0 <= slot_index < len(self.slots):
            self.slots[slot_index] = clone_stack(stack)
            return True
        return False

    def find_first_free_slot(self):
        for i, slot in enumerate(self.slots):
            if slot is None:
                return i
        return None

    def can_place(self, slot_index, stack):
        if stack is None:
            return False
        if not 0 <= slot_index < len(self.slots):
            return False
        target = self.slots[slot_index]
        if target is None:
            return True
        return target["id"] == stack["id"] and is_stackable(stack["id"])

    def place_slot(self, slot_index, stack):
        if not self.can_place(slot_index, stack):
            return False
        target = self.slots[slot_index]
        incoming = clone_stack(stack)
        if target is None:
            self.slots[slot_index] = incoming
        else:
            target["quantity"] += incoming["quantity"]
        return True

    def take_slot(self, slot_index):
        if not 0 <= slot_index < len(self.slots):
            return None
        stack = self.slots[slot_index]
        self.slots[slot_index] = None
        return clone_stack(stack)

    def swap_slot(self, a, b):
        if not (0 <= a < len(self.slots) and 0 <= b < len(self.slots)):
            return False
        self.slots[a], self.slots[b] = self.slots[b], self.slots[a]
        return True

    def move_slot(self, a, b):
        return move_item(self, a, self, b)

    def add_item(self, item_id, qty=1):
        item_def = get_item_def(item_id)
        if item_def is None or qty <= 0:
            return False

        if item_def["stackable"]:
            for slot in self.slots:
                if slot and slot["id"] == item_id:
                    slot["quantity"] += qty
                    return True

        free_slot = self.find_first_free_slot()
        if free_slot is None:
            return False
        self.slots[free_slot] = {"id": item_id, "quantity": qty}
        return True

    def remove_item(self, item_id, qty=1):
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
        return sum(slot["quantity"] for slot in self.slots if slot and slot["id"] == item_id)

    def get_free_slots(self):
        return sum(1 for slot in self.slots if slot is None)

    def is_full(self):
        return self.get_free_slots() == 0

    def to_dict(self):
        return {
            "slots": copy.deepcopy(self.slots),
            "equipment": self.equipment.to_dict()
        }

    def from_dict(self, data):
        self.slots = [None] * len(self.slots)
        slots = data.get("slots", [])
        for i, stack in enumerate(slots):
            if i < len(self.slots):
                self.slots[i] = clone_stack(stack)
        
        if "equipment" in data:
            self.equipment.from_dict(data["equipment"])


class EquipmentInventory:
    def __init__(self):
        self.slots = {slot_name: None for slot_name in EQUIPMENT_SLOTS}

    def to_dict(self):
        return {"slots": copy.deepcopy(self.slots)}

    def from_dict(self, data):
        slots_data = data.get("slots", {})
        for slot_name in self.slots:
            self.slots[slot_name] = clone_stack(slots_data.get(slot_name))

    def iter_slot_keys(self):
        return list(EQUIPMENT_SLOTS.keys())

    def get_slot(self, slot_name):
        return self.slots.get(slot_name)

    def set_slot(self, slot_name, stack):
        if slot_name not in self.slots:
            return False
        self.slots[slot_name] = clone_stack(stack)
        return True

    def can_place(self, slot_name, stack):
        if stack is None or slot_name not in self.slots:
            return False
        return get_equipment_slot(stack["id"]) == slot_name

    def place_slot(self, slot_name, stack):
        if not self.can_place(slot_name, stack):
            return False
        self.slots[slot_name] = clone_stack(stack)
        return True

    def take_slot(self, slot_name):
        if slot_name not in self.slots:
            return None
        stack = self.slots[slot_name]
        self.slots[slot_name] = None
        return clone_stack(stack)

    def swap_slot(self, a, b):
        if a not in self.slots or b not in self.slots:
            return False
        stack_a = self.slots[a]
        stack_b = self.slots[b]
        if stack_b and not self.can_place(a, stack_b):
            return False
        if stack_a and not self.can_place(b, stack_a):
            return False
        self.slots[a], self.slots[b] = stack_b, stack_a
        return True

    def move_slot(self, a, b):
        return move_item(self, a, self, b)


def move_item(source_container, source_slot, target_container, target_slot):
    source_stack = source_container.get_slot(source_slot)
    if source_stack is None:
        return False

    if source_container is target_container and source_slot == target_slot:
        return True

    source_stack = clone_stack(source_stack)
    target_stack = clone_stack(target_container.get_slot(target_slot))

    if target_stack and target_stack["id"] == source_stack["id"] and is_stackable(source_stack["id"]):
        if not target_container.can_place(target_slot, source_stack):
            return False
        source_container.take_slot(source_slot)
        target_container.place_slot(target_slot, source_stack)
        return True

    if not target_container.can_place(target_slot, source_stack) and target_stack is None:
        return False

    if target_stack is None:
        source_container.take_slot(source_slot)
        target_container.set_slot(target_slot, source_stack)
        return True

    if not source_container.can_place(source_slot, target_stack):
        return False
    if not target_container.can_place(target_slot, source_stack):
        return False

    source_container.set_slot(source_slot, target_stack)
    target_container.set_slot(target_slot, source_stack)
    return True
