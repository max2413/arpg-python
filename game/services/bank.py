"""Banker NPC and Ursina-native bank UI."""

import json
import os

from ursina import Entity, Text as UText, color

from game.entities.npc import InteractableNpc, build_humanoid_npc
from game.runtime import get_runtime
from game.systems.inventory import (
    Inventory,
    build_item_tooltip,
    get_item_def,
    get_item_name,
    sanitize_inventory_payload,
    transfer_item_quantity,
)
from game.systems.paths import data_path, save_path
from game.ui.ursina_widgets import FlatButton, UiWindow

BANK_PROXIMITY = 7.0
BANK_SLOTS = 80
BANK_COLS = 8
BANK_ROWS = 10
SAVE_PATH = save_path("bank.json")
LEGACY_BANK_PATH = data_path("bank.json")
LEGACY_SAVE_PATH = data_path("save.json")

PANEL = color.rgba32(18, 26, 38)
PANEL_ALT = color.rgba32(26, 36, 52)
TEXT = color.rgba32(235, 242, 255)
TEXT_DIM = color.rgba32(170, 186, 210)
ACCENT = color.rgba32(255, 220, 90)
BTN = color.rgba32(44, 66, 94)
BTN_HI = color.rgba32(62, 88, 120)
BTN_PRESS = color.rgba32(34, 50, 72)
GOOD = color.rgba32(52, 166, 92)


def _wrap_text(text, width):
    if not text:
        return ""
    words = text.split()
    lines = []
    current = []
    current_len = 0
    for word in words:
        projected = len(word) if not current else current_len + 1 + len(word)
        if projected > width and current:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len = projected
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


class Bank(InteractableNpc):
    def __init__(self, render, bullet_world, pos, player_inventory):
        self.player_inv = player_inventory
        self.bank_inv = Inventory(size=BANK_SLOTS)
        self.ui_open = False
        self._window = None
        self._bank_buttons = {}
        self._player_buttons = {}
        self._selected_bank_slot = None
        self._selected_player_slot = None
        self._load()
        super().__init__(render, bullet_world, pos, BANK_PROXIMITY, "Press E to talk to Banker")

    def _build_visual(self):
        self.model = build_humanoid_npc(
            self.root,
            body_color=(0.22, 0.46, 0.34, 1.0),
            head_color=(0.87, 0.73, 0.6, 1.0),
            accent_color=(0.9, 0.82, 0.45, 1.0),
            label="Banker",
        )

    def update(self, dt, player_pos, hud):
        self._animate(dt)
        self.update_prompt(player_pos, hud, ui_open=self.ui_open)
        if self.ui_open and not self._in_range:
            self.close_ui()

    def open_ui(self):
        self.ui_open = True
        if self._window is None:
            self._build_ui()
        self._auto_select_defaults()
        self.refresh_ui()
        self._window.show()
        self._window.focus()

    def close_ui(self):
        self.ui_open = False
        if self._window:
            self._window.hide()

    def _build_ui(self):
        runtime = get_runtime()
        parent = runtime.hud._ui_layer if runtime is not None and runtime.hud is not None else None
        self._window = UiWindow(
            title="Bank",
            parent=parent,
            position=(0.08, -0.02, 0),
            scale=(1.24, 0.90),
            panel_color=PANEL,
            header_color=PANEL_ALT,
            close_callback=self.close_ui,
        )
        body = self._window.content

        UText(parent=body, text="Bank", origin=(-0.5, 0.5), position=(-0.56, 0.31, -0.02), scale=0.92, color=ACCENT)
        UText(parent=body, text="Inventory", origin=(-0.5, 0.5), position=(0.12, 0.31, -0.02), scale=0.92, color=ACCENT)
        UText(parent=body, text="Select items to move between storage and inventory.", origin=(0, 0.5), position=(0, 0.31, -0.02), scale=0.52, color=TEXT_DIM)

        bank_start_x, bank_start_y = -0.55, 0.24
        bank_step_x, bank_step_y = 0.07, 0.049
        for row in range(BANK_ROWS):
            for col in range(BANK_COLS):
                slot_key = row * BANK_COLS + col
                entry = self._build_slot_button(
                    body,
                    position=(bank_start_x + col * bank_step_x, bank_start_y - row * bank_step_y, -0.02),
                    scale=(0.058, 0.040),
                    on_click=lambda key=slot_key: self._select_bank_slot(key),
                )
                self._bank_buttons[slot_key] = entry

        inv_start_x, inv_start_y = 0.12, 0.24
        inv_step_x, inv_step_y = 0.08, 0.060
        for row in range(7):
            for col in range(4):
                slot_key = row * 4 + col
                entry = self._build_slot_button(
                    body,
                    position=(inv_start_x + col * inv_step_x, inv_start_y - row * inv_step_y, -0.02),
                    scale=(0.068, 0.046),
                    on_click=lambda key=slot_key: self._select_player_slot(key),
                )
                self._player_buttons[slot_key] = entry

        Entity(parent=body, model="quad", color=PANEL_ALT, scale=(0.56, 0.22), position=(-0.33, -0.33, -0.01))
        Entity(parent=body, model="quad", color=PANEL_ALT, scale=(0.56, 0.22), position=(0.33, -0.33, -0.01))

        UText(parent=body, text="Selected Bank Item", origin=(-0.5, 0.5), position=(-0.58, -0.24, -0.02), scale=0.62, color=ACCENT)
        self._bank_detail_title = UText(parent=body, text="Select a bank item", origin=(-0.5, 0.5), position=(-0.58, -0.29, -0.02), scale=0.60, color=TEXT)
        self._bank_detail_text = UText(parent=body, text="", origin=(-0.5, 0.5), position=(-0.58, -0.34, -0.02), scale=0.33, color=TEXT_DIM)
        self._bank_withdraw_1 = FlatButton(parent=body, text="Withdraw 1", position=(-0.52, -0.42, -0.02), scale=(0.18, 0.038), color_value=BTN, highlight_color=BTN_HI, pressed_color=BTN_PRESS, text_color=TEXT, text_scale=0.54, on_click=lambda: self._withdraw_selected(1))
        self._bank_withdraw_10 = FlatButton(parent=body, text="Withdraw 10", position=(-0.52, -0.48, -0.02), scale=(0.18, 0.038), color_value=BTN, highlight_color=BTN_HI, pressed_color=BTN_PRESS, text_color=TEXT, text_scale=0.54, on_click=lambda: self._withdraw_selected(10))
        self._bank_withdraw_all = FlatButton(parent=body, text="Withdraw All", position=(-0.52, -0.54, -0.02), scale=(0.18, 0.038), color_value=GOOD, highlight_color=GOOD.tint(.1), pressed_color=GOOD.tint(-.1), text_color=TEXT, text_scale=0.54, on_click=lambda: self._withdraw_selected(None))

        UText(parent=body, text="Selected Inventory Item", origin=(-0.5, 0.5), position=(0.08, -0.24, -0.02), scale=0.62, color=ACCENT)
        self._player_detail_title = UText(parent=body, text="Select an inventory item", origin=(-0.5, 0.5), position=(0.08, -0.29, -0.02), scale=0.60, color=TEXT)
        self._player_detail_text = UText(parent=body, text="", origin=(-0.5, 0.5), position=(0.08, -0.34, -0.02), scale=0.33, color=TEXT_DIM)
        self._player_deposit_1 = FlatButton(parent=body, text="Deposit 1", position=(0.58, -0.42, -0.02), scale=(0.18, 0.038), color_value=BTN, highlight_color=BTN_HI, pressed_color=BTN_PRESS, text_color=TEXT, text_scale=0.54, on_click=lambda: self._deposit_selected(1))
        self._player_deposit_10 = FlatButton(parent=body, text="Deposit 10", position=(0.58, -0.48, -0.02), scale=(0.18, 0.038), color_value=BTN, highlight_color=BTN_HI, pressed_color=BTN_PRESS, text_color=TEXT, text_scale=0.54, on_click=lambda: self._deposit_selected(10))
        self._player_deposit_all = FlatButton(parent=body, text="Deposit All", position=(0.58, -0.54, -0.02), scale=(0.18, 0.038), color_value=GOOD, highlight_color=GOOD.tint(.1), pressed_color=GOOD.tint(-.1), text_color=TEXT, text_scale=0.54, on_click=lambda: self._deposit_selected(None))

        self.refresh_ui()

    def _build_slot_button(self, parent, position, scale, on_click):
        btn = FlatButton(
            parent=parent,
            text="",
            position=position,
            scale=scale,
            color_value=BTN,
            highlight_color=BTN_HI,
            pressed_color=BTN_PRESS,
            text_color=TEXT,
            text_scale=0.40,
            on_click=on_click,
        )
        icon = Entity(parent=btn, model="quad", color=PANEL_ALT, scale=(0.028, 0.024), position=(0, 0.010, -0.02))
        qty = UText(parent=btn, text="", origin=(0.5, -0.5), position=(0.024, -0.018, -0.02), scale=0.40, color=TEXT)
        return {"button": btn, "icon": icon, "qty": qty}

    def _slot_text(self, stack):
        if stack is None:
            return ""
        item_name = get_item_name(stack["id"])
        parts = [word[0] for word in item_name.split()[:2] if word]
        return "".join(parts)[:2].upper()

    def _set_slot_entry(self, entry, stack, selected=False):
        btn = entry["button"]
        base = GOOD if selected else BTN
        btn.base_color = base
        btn.color = base
        btn.setColorScale(base)
        if stack is None:
            entry["icon"].color = PANEL_ALT
            entry["icon"].setColorScale(PANEL_ALT)
            btn.label.text = ""
            entry["qty"].text = ""
            return
        item_def = get_item_def(stack["id"]) or {}
        item_color = tuple(item_def.get("color", (0.8, 0.8, 0.8, 1.0)))
        if max(item_color[:3]) > 1.0:
            item_color = tuple(channel / 255.0 for channel in item_color[:3]) + (item_color[3],)
        entry["icon"].color = item_color
        entry["icon"].setColorScale(item_color)
        btn.label.text = self._slot_text(stack)
        entry["qty"].text = str(stack["quantity"]) if stack["quantity"] > 1 else ""

    def _select_bank_slot(self, slot_key):
        self._selected_bank_slot = slot_key
        self.refresh_ui()

    def _select_player_slot(self, slot_key):
        self._selected_player_slot = slot_key
        self.refresh_ui()

    def _refresh_bank_detail(self):
        stack = self.bank_inv.get_slot(self._selected_bank_slot) if self._selected_bank_slot is not None else None
        if stack is None:
            self._bank_detail_title.text = "Select a bank item"
            self._bank_detail_text.text = _wrap_text("Choose a stored item to withdraw it.", 26)
            for btn in (self._bank_withdraw_1, self._bank_withdraw_10, self._bank_withdraw_all):
                btn.enabled = False
                btn.visible = True
                btn.color = BTN
                btn.setColorScale(BTN)
            return
        self._bank_detail_title.text = get_item_name(stack["id"])
        self._bank_detail_text.text = _wrap_text(build_item_tooltip(stack["id"], quantity=stack["quantity"]), 28)
        for btn in (self._bank_withdraw_1, self._bank_withdraw_10, self._bank_withdraw_all):
            btn.enabled = True
            btn.visible = True
            btn.color = btn.base_color
            btn.setColorScale(btn.base_color)

    def _refresh_player_detail(self):
        stack = self.player_inv.get_slot(self._selected_player_slot) if self._selected_player_slot is not None else None
        if stack is None:
            self._player_detail_title.text = "Select an inventory item"
            self._player_detail_text.text = _wrap_text("Choose an inventory item to deposit it into the bank.", 26)
            for btn in (self._player_deposit_1, self._player_deposit_10, self._player_deposit_all):
                btn.enabled = False
                btn.visible = True
                btn.color = BTN
                btn.setColorScale(BTN)
            return
        self._player_detail_title.text = get_item_name(stack["id"])
        self._player_detail_text.text = _wrap_text(build_item_tooltip(stack["id"], quantity=stack["quantity"]), 28)
        for btn in (self._player_deposit_1, self._player_deposit_10, self._player_deposit_all):
            btn.enabled = True
            btn.visible = True
            btn.color = btn.base_color
            btn.setColorScale(btn.base_color)

    def _auto_select_defaults(self):
        if self._selected_player_slot is None or self.player_inv.get_slot(self._selected_player_slot) is None:
            self._selected_player_slot = next((i for i in self.player_inv.iter_slot_keys() if self.player_inv.get_slot(i) is not None), None)
        if self._selected_bank_slot is None or self.bank_inv.get_slot(self._selected_bank_slot) is None:
            self._selected_bank_slot = next((i for i in self.bank_inv.iter_slot_keys() if self.bank_inv.get_slot(i) is not None), None)

    def refresh_ui(self):
        if not self._window:
            return
        for slot_key, entry in self._bank_buttons.items():
            self._set_slot_entry(entry, self.bank_inv.get_slot(slot_key), selected=(slot_key == self._selected_bank_slot))
        for slot_key, entry in self._player_buttons.items():
            self._set_slot_entry(entry, self.player_inv.get_slot(slot_key), selected=(slot_key == self._selected_player_slot))
        self._refresh_bank_detail()
        self._refresh_player_detail()

    def _on_inventory_changed(self):
        self._save()
        self.refresh_ui()
        runtime = get_runtime()
        if runtime is not None and runtime.hud is not None:
            runtime.hud.refresh_inventory()

    def _save(self):
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        with open(SAVE_PATH, "w", encoding="utf-8") as handle:
            json.dump(self.bank_inv.to_dict(), handle)

    def deposit_from_inventory(self, slot_key, quantity):
        moved = transfer_item_quantity(self.player_inv, slot_key, self.bank_inv, quantity=quantity)
        if moved <= 0:
            return False
        self._on_inventory_changed()
        return True

    def withdraw_to_inventory(self, slot_key, quantity):
        moved = transfer_item_quantity(self.bank_inv, slot_key, self.player_inv, quantity=quantity)
        if moved <= 0:
            return False
        self._on_inventory_changed()
        return True

    def _deposit_selected(self, quantity):
        if self._selected_player_slot is None:
            return False
        stack = self.player_inv.get_slot(self._selected_player_slot)
        if stack is None:
            return False
        amount = stack["quantity"] if quantity is None else min(int(quantity), stack["quantity"])
        moved = self.deposit_from_inventory(self._selected_player_slot, amount)
        if moved and self.player_inv.get_slot(self._selected_player_slot) is None:
            self._selected_player_slot = None
            self.refresh_ui()
        return moved

    def _withdraw_selected(self, quantity):
        if self._selected_bank_slot is None:
            return False
        stack = self.bank_inv.get_slot(self._selected_bank_slot)
        if stack is None:
            return False
        amount = stack["quantity"] if quantity is None else min(int(quantity), stack["quantity"])
        moved = self.withdraw_to_inventory(self._selected_bank_slot, amount)
        if moved and self.bank_inv.get_slot(self._selected_bank_slot) is None:
            self._selected_bank_slot = None
            self.refresh_ui()
        return moved

    def _load(self):
        if os.path.exists(SAVE_PATH):
            try:
                with open(SAVE_PATH, encoding="utf-8") as handle:
                    self.bank_inv.from_dict(sanitize_inventory_payload(json.load(handle)))
            except Exception:
                pass
            return
        if os.path.exists(LEGACY_BANK_PATH):
            try:
                with open(LEGACY_BANK_PATH, encoding="utf-8") as handle:
                    self.bank_inv.from_dict(sanitize_inventory_payload(json.load(handle)))
            except Exception:
                pass
            return
        if os.path.exists(LEGACY_SAVE_PATH):
            try:
                with open(LEGACY_SAVE_PATH, encoding="utf-8") as handle:
                    data = json.load(handle)
                if "slots" in data and "inventory" not in data:
                    self.bank_inv.from_dict(sanitize_inventory_payload(data))
            except Exception:
                pass

    def remove_from_world(self, hud=None):
        if self._window is not None:
            self._window.destroy()
            self._window = None
        super().remove_from_world(hud)
