"""Inventory containers and item registry."""

import copy
import json

from game.systems.paths import data_path


ITEM_CATEGORY_RAW = "raw_material"
ITEM_CATEGORY_CURRENCY = "currency"
ITEM_CATEGORY_EQUIPMENT = "equipment"
ITEM_CATEGORY_CONSUMABLE = "consumable"
ITEM_CATEGORY_ENHANCEMENT = "enhancement"

EQUIPMENT_SLOTS = {
    "head": {"label": "Head"},
    "chest": {"label": "Chest"},
    "legs": {"label": "Legs"},
    "hands": {"label": "Hands"},
    "feet": {"label": "Feet"},
    "weapon": {"label": "Weapon"},
    "ranged": {"label": "Ranged"},
    "offhand": {"label": "Offhand"},
    "ring": {"label": "Ring"},
    "necklace": {"label": "Necklace"},
}

ITEMS_PATH = data_path("items.json")


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

STAT_LABELS = {
    "max_health": "Max Health",
    "health_regen": "Health Regen",
    "melee_damage": "Melee Damage",
    "ranged_damage": "Ranged Damage",
    "magic_damage": "Magic Damage",
    "armor": "Armor",
    "evasion": "Evasion",
    "accuracy": "Accuracy",
    "crit_chance": "Crit Chance",
    "crit_mult": "Crit Damage",
    "block_chance": "Block Chance",
    "parry_chance": "Parry Chance",
    "movement_speed": "Move Speed",
}

CATEGORY_LABELS = {
    ITEM_CATEGORY_RAW: "Raw Material",
    ITEM_CATEGORY_CURRENCY: "Currency",
    ITEM_CATEGORY_EQUIPMENT: "Equipment",
    ITEM_CATEGORY_CONSUMABLE: "Consumable",
    ITEM_CATEGORY_ENHANCEMENT: "Enhancement",
}

RANGED_SLOT_SUBTYPES = {"bow", "crossbow", "wand", "staff"}

def get_item_def(item_id):
    return ITEMS.get(item_id)


def has_item_def(item_id):
    return item_id in ITEMS


def get_item_name(item_id):
    item_def = get_item_def(item_id)
    return item_def["name"] if item_def else item_id


def get_item_category_label(item_id):
    item_def = get_item_def(item_id)
    if item_def is None:
        return "Unknown"
    return CATEGORY_LABELS.get(item_def.get("category"), item_def.get("category", "Unknown").replace("_", " ").title())


def format_item_stat(stat_name, value):
    label = STAT_LABELS.get(stat_name, stat_name.replace("_", " ").title())
    if stat_name.endswith("_chance") or stat_name == "evasion":
        amount = value * 100.0
        return f"{label}: {amount:+.1f}%"
    if stat_name == "accuracy":
        return f"{label}: {value:+.2f}"
    if stat_name == "crit_mult":
        return f"{label}: +{value:.2f}x"
    return f"{label}: {value:+.1f}"


def build_item_tooltip(item_id, quantity=None):
    item_def = get_item_def(item_id)
    if item_def is None:
        return item_id

    lines = [item_def["name"]]
    lines.append(get_item_category_label(item_id))

    if quantity is not None and quantity > 1:
        lines.append(f"Stack: {quantity}")

    equipment_slot = item_def.get("equipment_slot")
    if equipment_slot:
        lines.append(f"Slot: {equipment_slot.title()}")

    value = item_def.get("value")
    if value is not None:
        lines.append(f"Value: {value} gold")

    stats = item_def.get("stats") or {}
    if stats:
        lines.append("")
        for stat_name, stat_value in stats.items():
            lines.append(format_item_stat(stat_name, stat_value))

    return "\n".join(lines)


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


def is_ranged_slot_item(item_id):
    item_def = get_item_def(item_id)
    return bool(item_def and item_def.get("subtype") in RANGED_SLOT_SUBTYPES)


def clone_stack(stack):
    if stack is None:
        return None
    return {"id": stack["id"], "quantity": int(stack["quantity"])}


def available_stack_quantity(container, slot_key):
    stack = container.get_slot(slot_key)
    return 0 if stack is None else int(stack["quantity"])


def find_best_target_slot(container, item_id, quantity=1):
    stack = {"id": item_id, "quantity": int(quantity)}
    for slot_key in container.iter_slot_keys():
        target_stack = container.get_slot(slot_key)
        if target_stack and target_stack["id"] == item_id and container.can_place(slot_key, stack):
            return slot_key
    for slot_key in container.iter_slot_keys():
        if container.get_slot(slot_key) is None and container.can_place(slot_key, stack):
            return slot_key
    return None


def transfer_item_quantity(source_container, source_slot, target_container, quantity=1, target_slot=None):
    source_stack = source_container.get_slot(source_slot)
    if source_stack is None or quantity <= 0:
        return 0

    moved_qty = min(int(quantity), int(source_stack["quantity"]))
    if moved_qty <= 0:
        return 0

    incoming = {"id": source_stack["id"], "quantity": moved_qty}
    target_slot = target_slot if target_slot is not None else find_best_target_slot(target_container, incoming["id"], moved_qty)
    if target_slot is None or not target_container.can_place(target_slot, incoming):
        return 0

    target_stack = target_container.get_slot(target_slot)
    if target_stack is None:
        if hasattr(target_container, "slots"):
            target_container.slots[target_slot] = clone_stack(incoming)
        else:
            return 0
    else:
        target_stack["quantity"] += moved_qty

    source_stack["quantity"] -= moved_qty
    if source_stack["quantity"] <= 0:
        if hasattr(source_container, "slots"):
            source_container.slots[source_slot] = None
        else:
            return 0

    if source_container is target_container:
        source_container._notify_changed()
    else:
        source_container._notify_changed()
        target_container._notify_changed()
    return moved_qty


class Inventory:
    def __init__(self, size=28):
        self.slots = [None] * size
        self._listeners = []
        self.equipment = EquipmentInventory(on_change=self._notify_changed)

    def add_listener(self, callback):
        if callback is not None and callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_changed(self):
        for callback in list(self._listeners):
            callback()

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
            self._notify_changed()
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
        self._notify_changed()
        return True

    def take_slot(self, slot_index):
        if not 0 <= slot_index < len(self.slots):
            return None
        stack = self.slots[slot_index]
        self.slots[slot_index] = None
        self._notify_changed()
        return clone_stack(stack)

    def swap_slot(self, a, b):
        if not (0 <= a < len(self.slots) and 0 <= b < len(self.slots)):
            return False
        self.slots[a], self.slots[b] = self.slots[b], self.slots[a]
        self._notify_changed()
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
                    self._notify_changed()
                    return True

        free_slot = self.find_first_free_slot()
        if free_slot is None:
            return False
        self.slots[free_slot] = {"id": item_id, "quantity": qty}
        self._notify_changed()
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
                    self._notify_changed()
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
                if stack and has_item_def(stack.get("id")):
                    self.slots[i] = clone_stack(stack)
        
        if "equipment" in data:
            self.equipment.from_dict(data["equipment"])
        self._notify_changed()


class EquipmentInventory:
    def __init__(self, on_change=None):
        self.slots = {slot_name: None for slot_name in EQUIPMENT_SLOTS}
        self._listeners = []
        if on_change is not None:
            self._listeners.append(on_change)

    def add_listener(self, callback):
        if callback is not None and callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_changed(self):
        for callback in list(self._listeners):
            callback()

    def to_dict(self):
        return {"slots": copy.deepcopy(self.slots)}

    def from_dict(self, data):
        slots_data = data.get("slots", {})
        for slot_name in self.slots:
            stack = slots_data.get(slot_name)
            self.slots[slot_name] = clone_stack(stack) if stack and has_item_def(stack.get("id")) else None
        if "ranged" in self.slots and self.slots["ranged"] is None:
            weapon_stack = self.slots.get("weapon")
            if weapon_stack and is_ranged_slot_item(weapon_stack["id"]):
                self.slots["ranged"] = weapon_stack
                self.slots["weapon"] = None
        self._notify_changed()

    def iter_slot_keys(self):
        return list(EQUIPMENT_SLOTS.keys())

    def get_slot(self, slot_name):
        return self.slots.get(slot_name)

    def set_slot(self, slot_name, stack):
        if slot_name not in self.slots:
            return False
        self.slots[slot_name] = clone_stack(stack)
        self._notify_changed()
        return True

    def can_place(self, slot_name, stack):
        if stack is None or slot_name not in self.slots:
            return False
        return get_equipment_slot(stack["id"]) == slot_name

    def place_slot(self, slot_name, stack):
        if not self.can_place(slot_name, stack):
            return False
        self.slots[slot_name] = clone_stack(stack)
        self._notify_changed()
        return True

    def take_slot(self, slot_name):
        if slot_name not in self.slots:
            return None
        stack = self.slots[slot_name]
        self.slots[slot_name] = None
        self._notify_changed()
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
        self._notify_changed()
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


def sanitize_inventory_payload(data):
    payload = copy.deepcopy(data or {})
    valid_slots = []
    for stack in payload.get("slots", []):
        valid_slots.append(clone_stack(stack) if stack and has_item_def(stack.get("id")) else None)
    payload["slots"] = valid_slots

    equipment = payload.get("equipment", {})
    equipment_slots = equipment.get("slots", {})
    clean_equipment = {}
    for slot_name, stack in equipment_slots.items():
        clean_equipment[slot_name] = clone_stack(stack) if stack and has_item_def(stack.get("id")) else None
    payload["equipment"] = {"slots": clean_equipment}
    return payload
