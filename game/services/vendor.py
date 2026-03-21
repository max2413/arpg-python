"""Vendor NPC and Ursina-native shop UI."""

import json
import math
import os
import random

from panda3d.core import Vec3
from ursina import Entity, Text as UText, color

from game.entities.npc import ServiceNpc
from game.runtime import get_runtime
from game.systems.inventory import build_item_tooltip, clone_stack, get_item_def, get_item_name, is_stackable
from game.systems.paths import data_path
from game.ui.ursina_widgets import FlatButton, UiWindow

VENDOR_PROXIMITY = 5.0
VENDOR_PATROL_RADIUS = 12.0
VENDOR_PATROL_SPEED = 2.5
VENDOR_WAIT_TIME = 4.0
VENDOR_DATA_PATH = data_path("vendors.json")
ROWS_PER_PAGE = 6

VENDOR_CATALOGS = {}
BUYBACK_QUEUE = []

PANEL = color.rgba32(18, 26, 38)
PANEL_ALT = color.rgba32(26, 36, 52)
TEXT = color.rgba32(235, 242, 255)
TEXT_DIM = color.rgba32(170, 186, 210)
ACCENT = color.rgba32(255, 220, 90)
BTN = color.rgba32(44, 66, 94)
BTN_HI = color.rgba32(62, 88, 120)
BTN_PRESS = color.rgba32(34, 50, 72)
GOOD = color.rgba32(52, 166, 92)
BAD = color.rgba32(182, 72, 72)


def _wrap_text(text, width):
    if not text:
        return ""
    lines = []
    for raw_line in str(text).splitlines():
        words = raw_line.split()
        if not words:
            lines.append("")
            continue
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


def load_vendor_catalogs():
    global VENDOR_CATALOGS
    if not os.path.exists(VENDOR_DATA_PATH):
        VENDOR_CATALOGS = {}
        return
    try:
        with open(VENDOR_DATA_PATH, "r", encoding="utf-8") as handle:
            VENDOR_CATALOGS = json.load(handle)
    except Exception as exc:
        print(f"[vendor] failed to load catalogs: {exc}")
        VENDOR_CATALOGS = {}


def get_vendor_catalog(vendor_id):
    return VENDOR_CATALOGS.get(vendor_id, {})


class Vendor(ServiceNpc):
    def __init__(self, render, bullet_world, pos, player_inventory, vendor_id="materials_supplier", static_idle=False):
        self.player_inv = player_inventory
        self.vendor_id = vendor_id
        self.vendor_data = get_vendor_catalog(vendor_id)
        self.static_idle = static_idle
        self.ui_open = False
        self._window = None
        self._active_tab = "buy"
        self._page = 0
        self._row_entries = []
        self._selected_entry = None
        self._gold_label = None

        self.patrol_center = Vec3(*pos)
        self._target_pos = Vec3(*pos)
        self._patrol_wait = 0.0
        self._state = "idle"

        super().__init__(
            render,
            bullet_world,
            pos,
            VENDOR_PROXIMITY,
            services=["shop"],
            palette=self.vendor_data.get("palette", {}),
            label=self.vendor_data.get("label", "Vendor"),
        )
        self.prompt_text = f"Press E to browse {self.vendor_data.get('name', 'wares')}"

    @property
    def stock(self):
        return self.vendor_data.get("stock", {})

    def update(self, dt, player_pos, hud):
        moving = False
        if not self.ui_open and not self.static_idle:
            if self._state == "idle":
                self._patrol_wait -= dt
                if self._patrol_wait <= 0:
                    self._state = "patrol"
                    angle = random.uniform(0, 2 * math.pi)
                    dist = random.uniform(2.0, VENDOR_PATROL_RADIUS)
                    self._target_pos = self.patrol_center + Vec3(math.cos(angle) * dist, 0, math.sin(angle) * dist)
            elif self._state == "patrol":
                diff = self._target_pos - self.pos
                diff.y = 0
                dist = diff.length()
                if dist < 0.2:
                    self._state = "idle"
                    self._patrol_wait = random.uniform(1.0, VENDOR_WAIT_TIME)
                else:
                    moving = True
                    step = VENDOR_PATROL_SPEED * dt
                    self.pos += diff / dist * min(step, dist)
                    self.root.setPos(self.pos)
                    if self._ghost_np is not None and not self._ghost_np.isEmpty():
                        self._ghost_np.setPos(self.pos.x, self.pos.y + 1.5, self.pos.z)
                    self.root.setH(math.degrees(math.atan2(-diff.x, diff.z)))

        self._animate(dt, moving=moving)
        self.update_prompt(player_pos, hud, ui_open=self.ui_open)
        if self.ui_open and not self._in_range:
            self.close_ui()

    def open_ui(self):
        self.ui_open = True
        if self._window is None:
            self._build_ui()
        self._gold_label.text = f"Gold: {self._gold_count()}"
        self.refresh_ui()
        self._window.show()
        self._window.focus()

    def close_ui(self):
        self.ui_open = False
        if self._window is not None:
            self._window.hide()

    def _gold_count(self):
        return self.player_inv.count_item("gold")

    def _build_ui(self):
        runtime = get_runtime()
        parent = runtime.hud._ui_layer if runtime is not None and runtime.hud is not None else None
        title = self.vendor_data.get("name", "Vendor Shop")
        self._window = UiWindow(
            title=title,
            parent=parent,
            position=(0.04, 0.0, 0),
            scale=(1.10, 0.86),
            panel_color=PANEL,
            header_color=PANEL_ALT,
            close_callback=self.close_ui,
        )
        body = self._window.content

        self._gold_label = UText(parent=body, text="Gold: 0", origin=(-0.5, 0.5), position=(-0.50, 0.31, -0.02), scale=0.88, color=ACCENT)

        self._tab_buy_btn = FlatButton(parent=body, text="Buy", position=(-0.18, 0.31, -0.02), scale=(0.12, 0.04), color_value=GOOD, highlight_color=GOOD.tint(.1), pressed_color=GOOD.tint(-.1), text_color=TEXT, text_scale=0.62, on_click=lambda: self._set_tab("buy"))
        self._tab_sell_btn = FlatButton(parent=body, text="Sell", position=(-0.03, 0.31, -0.02), scale=(0.12, 0.04), color_value=BTN, highlight_color=BTN_HI, pressed_color=BTN_PRESS, text_color=TEXT, text_scale=0.62, on_click=lambda: self._set_tab("sell"))
        self._tab_buyback_btn = FlatButton(parent=body, text="Buyback", position=(0.14, 0.31, -0.02), scale=(0.14, 0.04), color_value=BTN, highlight_color=BTN_HI, pressed_color=BTN_PRESS, text_color=TEXT, text_scale=0.58, on_click=lambda: self._set_tab("buyback"))

        self._page_text = UText(parent=body, text="", origin=(0, 0.5), position=(0.38, 0.31, -0.02), scale=0.56, color=TEXT_DIM)
        self._prev_btn = FlatButton(parent=body, text="Prev", position=(0.28, 0.31, -0.02), scale=(0.09, 0.036), color_value=BTN, highlight_color=BTN_HI, pressed_color=BTN_PRESS, text_color=TEXT, text_scale=0.52, on_click=lambda: self._change_page(-1))
        self._next_btn = FlatButton(parent=body, text="Next", position=(0.48, 0.31, -0.02), scale=(0.09, 0.036), color_value=BTN, highlight_color=BTN_HI, pressed_color=BTN_PRESS, text_color=TEXT, text_scale=0.52, on_click=lambda: self._change_page(1))

        y_positions = [0.20, 0.10, 0.00, -0.10, -0.20, -0.30]
        for y in y_positions:
            row_root = Entity(parent=body, position=(0, y, -0.02))
            bg = Entity(parent=row_root, model="quad", color=PANEL_ALT, scale=(0.92, 0.082))
            title_text = UText(parent=row_root, text="", origin=(-0.5, 0.5), position=(-0.43, 0.015, -0.02), scale=0.56, color=TEXT)
            subtitle = UText(parent=row_root, text="", origin=(-0.5, 0.5), position=(-0.43, -0.017, -0.02), scale=0.36, color=TEXT_DIM)
            price = UText(parent=row_root, text="", origin=(0.5, 0.5), position=(0.42, 0.001, -0.02), scale=0.46, color=ACCENT)
            select_btn = FlatButton(parent=row_root, text="Select", position=(0.31, 0.0, -0.02), scale=(0.12, 0.038), color_value=BTN, highlight_color=BTN_HI, pressed_color=BTN_PRESS, text_color=TEXT, text_scale=0.52)
            self._row_entries.append({"root": row_root, "bg": bg, "title": title_text, "subtitle": subtitle, "price": price, "select": select_btn, "payload": None})

        Entity(parent=body, model="quad", color=PANEL_ALT, scale=(0.94, 0.20), position=(0, -0.49, -0.01))
        self._detail_header = UText(parent=body, text="Selected Item", origin=(-0.5, 0.5), position=(-0.50, -0.41, -0.02), scale=0.66, color=ACCENT)
        self._detail_title = UText(parent=body, text="Select an item", origin=(-0.5, 0.5), position=(-0.50, -0.46, -0.02), scale=0.66, color=TEXT)
        self._detail_text = UText(parent=body, text="", origin=(-0.5, 0.5), position=(-0.50, -0.51, -0.02), scale=0.34, color=TEXT_DIM)
        self._action_1 = FlatButton(parent=body, text="Action 1", position=(0.24, -0.44, -0.02), scale=(0.18, 0.038), color_value=BTN, highlight_color=BTN_HI, pressed_color=BTN_PRESS, text_color=TEXT, text_scale=0.54)
        self._action_10 = FlatButton(parent=body, text="Action 10", position=(0.24, -0.50, -0.02), scale=(0.18, 0.038), color_value=BTN, highlight_color=BTN_HI, pressed_color=BTN_PRESS, text_color=TEXT, text_scale=0.54)
        self._action_all = FlatButton(parent=body, text="Action All", position=(0.24, -0.56, -0.02), scale=(0.18, 0.038), color_value=GOOD, highlight_color=GOOD.tint(.1), pressed_color=GOOD.tint(-.1), text_color=TEXT, text_scale=0.54)

        self._set_tab("buy")

    def _set_tab(self, tab_name):
        self._active_tab = tab_name
        self._page = 0
        self._selected_entry = None
        self.refresh_ui()

    def _change_page(self, delta):
        entries = self._tab_entries()
        max_page = max(0, (len(entries) - 1) // ROWS_PER_PAGE) if entries else 0
        self._page = max(0, min(max_page, self._page + delta))
        self.refresh_ui()

    def _iter_sell_entries(self):
        entries = []
        item_ids = {slot["id"] for slot in self.player_inv.slots if slot}
        for item_id, item_def in sorted(
            ((item_id, get_item_def(item_id)) for item_id in item_ids),
            key=lambda pair: pair[1]["name"] if pair[1] else pair[0],
        ):
            if item_def is None or item_id == "gold":
                continue
            qty_owned = self.player_inv.count_item(item_id)
            if qty_owned <= 0:
                continue
            entries.append({"item_id": item_id, "price": item_def["value"], "qty": qty_owned, "subtitle": f"Owned: {qty_owned}"})
        return entries

    def _visible_buyback_entries(self):
        visible = []
        for idx, entry in enumerate(BUYBACK_QUEUE):
            if entry.get("quantity", 0) > 0 and get_item_def(entry.get("item_id")):
                visible.append({"index": idx, "item_id": entry["item_id"], "price": entry["price"], "qty": entry["quantity"], "subtitle": f"Buy back qty: {entry['quantity']}"})
        return visible

    def _buy_entries(self):
        return [
            {"item_id": item_id, "price": price, "qty": None, "subtitle": "Buy from stock"}
            for item_id, price in self.stock.items()
            if get_item_def(item_id)
        ]

    def _tab_entries(self):
        if self._active_tab == "buy":
            return self._buy_entries()
        if self._active_tab == "sell":
            return self._iter_sell_entries()
        return self._visible_buyback_entries()

    def _refresh_tabs(self):
        tab_colors = {
            "buy": GOOD if self._active_tab == "buy" else BTN,
            "sell": GOOD if self._active_tab == "sell" else BTN,
            "buyback": GOOD if self._active_tab == "buyback" else BTN,
        }
        for btn, tint in ((self._tab_buy_btn, tab_colors["buy"]), (self._tab_sell_btn, tab_colors["sell"]), (self._tab_buyback_btn, tab_colors["buyback"])):
            btn.base_color = tint
            btn.color = tint
            btn.setColorScale(tint)

    def refresh_ui(self):
        if self._window is None:
            return
        self._refresh_tabs()
        self._gold_label.text = f"Gold: {self._gold_count()}"
        entries = self._tab_entries()
        max_page = max(0, (len(entries) - 1) // ROWS_PER_PAGE) if entries else 0
        self._page = max(0, min(max_page, self._page))
        self._prev_btn.visible = self._page > 0
        self._next_btn.visible = self._page < max_page
        self._page_text.text = f"Page {self._page + 1}/{max_page + 1}" if entries else "No items"

        start = self._page * ROWS_PER_PAGE
        visible = entries[start:start + ROWS_PER_PAGE]
        for row, payload in zip(self._row_entries, visible + [None] * (len(self._row_entries) - len(visible))):
            if payload is None:
                row["root"].enabled = False
                row["payload"] = None
                continue
            row["root"].enabled = True
            row["payload"] = payload
            row["title"].text = get_item_name(payload["item_id"])
            row["subtitle"].text = payload["subtitle"]
            row["price"].text = f"{payload['price']}g"
            tint = GOOD if self._selected_entry == payload else BTN
            row["select"].base_color = tint
            row["select"].color = tint
            row["select"].setColorScale(tint)
            row["select"]._click_callback = lambda entry=payload: self._select_entry(entry)

        self._refresh_detail()

    def _select_entry(self, payload):
        self._selected_entry = payload
        self.refresh_ui()

    def _refresh_detail(self):
        entry = self._selected_entry
        if entry is None:
            self._detail_header.text = "Selected Item"
            self._detail_title.text = "Select an item"
            self._detail_text.text = _wrap_text("Choose an item from the active tab to trade.", 44)
            self._set_action_buttons(None, None, None)
            return

        item_id = entry["item_id"]
        self._detail_title.text = get_item_name(item_id)
        self._detail_text.text = _wrap_text(build_item_tooltip(item_id, quantity=entry["qty"]), 46)

        if self._active_tab == "buy":
            self._detail_header.text = "Buy Item"
            max_affordable = self._gold_count() // entry["price"] if entry["price"] > 0 else 0
            max_qty = self._max_receivable_qty(item_id, max_affordable)
            self._set_action_buttons(
                ("Buy 1", lambda: self.buy_from_stock(item_id, entry["price"], 1)) if max_qty > 0 else None,
                ("Buy 10", lambda: self.buy_from_stock(item_id, entry["price"], min(10, max_qty))) if max_qty > 0 else None,
                ("Buy All", lambda: self.buy_from_stock(item_id, entry["price"], max_qty)) if max_qty > 0 else None,
            )
        elif self._active_tab == "sell":
            self._detail_header.text = "Sell Item"
            max_qty = max(0, int(entry["qty"]))
            self._set_action_buttons(
                ("Sell 1", lambda: self.sell_item_by_id(item_id, entry["price"], 1)) if max_qty > 0 else None,
                ("Sell 10", lambda: self.sell_item_by_id(item_id, entry["price"], min(10, max_qty))) if max_qty > 0 else None,
                ("Sell All", lambda: self.sell_item_by_id(item_id, entry["price"], max_qty)) if max_qty > 0 else None,
            )
        else:
            self._detail_header.text = "Buy Back Item"
            max_qty = max(0, int(entry["qty"]))
            self._set_action_buttons(
                ("Buy Back 1", lambda: self.buyback_item(entry["index"], 1)) if max_qty > 0 else None,
                ("Buy Back 10", lambda: self.buyback_item(entry["index"], min(10, max_qty))) if max_qty > 0 else None,
                ("Buy Back All", lambda: self.buyback_item(entry["index"], max_qty)) if max_qty > 0 else None,
            )

    def _set_action_buttons(self, primary, secondary, tertiary):
        for btn, spec, base in (
            (self._action_1, primary, BTN),
            (self._action_10, secondary, BTN),
            (self._action_all, tertiary, GOOD),
        ):
            if spec is None:
                btn.enabled = False
                btn.visible = True
                btn.label.text = "-"
                btn.color = BTN
                btn.setColorScale(BTN)
                btn._click_callback = None
                continue
            text, callback = spec
            btn.enabled = True
            btn.visible = True
            btn.label.text = text
            btn.base_color = base
            btn.color = base
            btn.setColorScale(base)
            btn._click_callback = callback

    def _refresh_after_transaction(self):
        runtime = get_runtime()
        if runtime is not None and runtime.hud is not None:
            runtime.hud.refresh_inventory()
        current_item = self._selected_entry["item_id"] if self._selected_entry else None
        self.refresh_ui()
        if current_item is not None:
            for entry in self._tab_entries():
                if entry["item_id"] == current_item:
                    self._selected_entry = entry
                    break
            else:
                self._selected_entry = None
        self.refresh_ui()

    def _max_receivable_qty(self, item_id, requested_qty):
        requested_qty = max(0, int(requested_qty))
        if requested_qty <= 0:
            return 0
        if is_stackable(item_id):
            if self.player_inv.count_item(item_id) > 0 or self.player_inv.get_free_slots() > 0:
                return requested_qty
            return 0
        return min(requested_qty, self.player_inv.get_free_slots())

    def _add_buyback_record(self, item_id, quantity, price):
        if quantity <= 0:
            return
        BUYBACK_QUEUE.insert(0, {"item_id": item_id, "quantity": int(quantity), "price": int(price)})
        del BUYBACK_QUEUE[5:]

    def buy_from_stock(self, item_id, price, qty):
        qty = int(qty)
        if qty <= 0:
            return False
        affordable = self._gold_count() // price if price > 0 else qty
        qty = min(qty, affordable)
        qty = self._max_receivable_qty(item_id, qty)
        if qty <= 0:
            return False
        total_cost = price * qty
        if not self.player_inv.remove_item("gold", total_cost):
            return False
        added = 0
        for _ in range(qty):
            if self.player_inv.add_item(item_id, 1):
                added += 1
            else:
                break
        if added < qty:
            self.player_inv.add_item("gold", price * (qty - added))
        if added <= 0:
            return False
        self._refresh_after_transaction()
        return True

    def sell_item_by_id(self, item_id, price, qty):
        if item_id == "gold" or get_item_def(item_id) is None:
            return False
        available = self.player_inv.count_item(item_id)
        sell_qty = min(int(qty), available)
        if sell_qty <= 0:
            return False
        self.player_inv.remove_item(item_id, sell_qty)
        self.player_inv.add_item("gold", sell_qty * price)
        self._add_buyback_record(item_id, sell_qty, price)
        self._refresh_after_transaction()
        return True

    def sell_from_inventory(self, slot_key, qty):
        stack = self.player_inv.get_slot(slot_key)
        if stack is None:
            return False
        item_def = get_item_def(stack["id"])
        if item_def is None:
            return False
        return self.sell_item_by_id(stack["id"], item_def["value"], min(int(qty), stack["quantity"]))

    def sell_from_equipment(self, slot_key, qty):
        equipment = self.player_inv.equipment
        stack = equipment.get_slot(slot_key)
        if stack is None:
            return False
        item_def = get_item_def(stack["id"])
        if item_def is None:
            return False
        sell_qty = min(int(qty), stack["quantity"])
        if sell_qty <= 0:
            return False
        current = clone_stack(stack)
        if current["quantity"] == sell_qty:
            equipment.set_slot(slot_key, None)
        else:
            current["quantity"] -= sell_qty
            equipment.set_slot(slot_key, current)
        self.player_inv.add_item("gold", sell_qty * item_def["value"])
        self._add_buyback_record(stack["id"], sell_qty, item_def["value"])
        self._refresh_after_transaction()
        return True

    def buyback_item(self, entry_index, qty):
        entries = self._visible_buyback_entries()
        if not (0 <= entry_index < len(entries)):
            return False
        entry = entries[entry_index]
        qty = min(int(qty), int(entry["qty"]))
        qty = min(qty, self._gold_count() // entry["price"] if entry["price"] > 0 else qty)
        qty = self._max_receivable_qty(entry["item_id"], qty)
        if qty <= 0:
            return False
        total_cost = entry["price"] * qty
        if not self.player_inv.remove_item("gold", total_cost):
            return False
        added = 0
        for _ in range(qty):
            if self.player_inv.add_item(entry["item_id"], 1):
                added += 1
            else:
                break
        if added < qty:
            self.player_inv.add_item("gold", entry["price"] * (qty - added))
        if added <= 0:
            return False
        BUYBACK_QUEUE[entry["index"]]["quantity"] -= added
        self._refresh_after_transaction()
        return True

    def remove_from_world(self, hud=None):
        if self._window is not None:
            self._window.destroy()
            self._window = None
        super().remove_from_world(hud)


load_vendor_catalogs()
