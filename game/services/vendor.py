"""Vendor NPC and draggable shop UI."""

import builtins
import json
import math
import os
import random

from panda3d.core import TextNode, Vec3
from direct.gui.DirectGui import DGG, DirectFrame, DirectScrolledFrame, OnscreenText

from game.entities.npc import ServiceNpc
from game.systems.inventory import build_item_tooltip, clone_stack, get_item_def, is_stackable
from game.systems.paths import data_path
from game.ui.widgets import (
    CONTEXT_MENU_MANAGER,
    QUANTITY_PROMPT_MANAGER,
    TOOLTIP_MANAGER,
    DraggableWindow,
    create_item_icon,
    create_text_button,
)

VENDOR_PROXIMITY = 5.0
VENDOR_PATROL_RADIUS = 12.0
VENDOR_PATROL_SPEED = 2.5
VENDOR_WAIT_TIME = 4.0
VENDOR_DATA_PATH = data_path("vendors.json")

VENDOR_CATALOGS = {}
BUYBACK_QUEUE = []


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
        self._tab_widgets = []
        self._tab_scroll = None
        self._tab_canvas = None
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
                    self._target_pos = self.patrol_center + Vec3(math.cos(angle) * dist, math.sin(angle) * dist, 0)
            elif self._state == "patrol":
                diff = self._target_pos - self.pos
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
                        self._ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 1.5)
                    self.root.setH(math.degrees(math.atan2(-diff.x, diff.y)))

        self._animate(dt, moving=moving)
        self.update_prompt(player_pos, hud, ui_open=self.ui_open)
        if self.ui_open and not self._in_range:
            self.close_ui()

    def open_ui(self):
        self.ui_open = True
        self._build_ui()

    def close_ui(self):
        self.ui_open = False
        CONTEXT_MENU_MANAGER.hide()
        QUANTITY_PROMPT_MANAGER.hide()
        if self._window:
            self._window.destroy()
            self._window = None
            self._tab_widgets = []
            self._tab_scroll = None
            self._tab_canvas = None
            self._gold_label = None

    def _gold_count(self):
        return self.player_inv.count_item("gold")

    def _build_ui(self):
        title = self.vendor_data.get("name", "Vendor Shop")
        self._window = DraggableWindow(title, (-0.7, 0.7, -0.65, 0.65), (0, 0, 0), self.close_ui)
        body = self._window.body
        self._gold_label = OnscreenText(
            text=f"Gold: {self._gold_count()}",
            parent=body,
            pos=(0, 0.52),
            scale=0.04,
            fg=(1, 0.8, 0, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )
        self._tab_buy_btn = create_text_button(
            body,
            "Buy",
            (-0.24, 0, 0.42),
            self._show_buy_tab,
            scale=0.05,
            min_half_width=1.0,
            max_half_width=None,
            padding=0.45,
            frame_color=(0.3, 0.5, 0.3, 1),
        )
        self._tab_sell_btn = create_text_button(
            body,
            "Sell",
            (0.0, 0, 0.42),
            self._show_sell_tab,
            scale=0.05,
            min_half_width=1.0,
            max_half_width=None,
            padding=0.45,
            frame_color=(0.3, 0.3, 0.5, 1),
        )
        self._tab_buyback_btn = create_text_button(
            body,
            "Buyback",
            (0.28, 0, 0.42),
            self._show_buyback_tab,
            scale=0.05,
            min_half_width=1.1,
            max_half_width=None,
            padding=0.45,
            frame_color=(0.5, 0.36, 0.2, 1),
        )
        self._tab_scroll = DirectScrolledFrame(
            parent=body,
            canvasSize=(-0.65, 0.65, -0.6, 0.0),
            frameSize=(-0.65, 0.65, -0.6, 0.35),
            frameColor=(0.08, 0.08, 0.08, 0.65),
            scrollBarWidth=0.04,
            pos=(0, 0, -0.08),
        )
        self._tab_canvas = self._tab_scroll.getCanvas()
        self._show_buy_tab()

    def _clear_tab(self):
        CONTEXT_MENU_MANAGER.hide()
        for widget in self._tab_widgets:
            widget.destroy()
        self._tab_widgets = []

    def _set_tab_canvas_size(self, bottom_y):
        if self._tab_scroll is not None:
            self._tab_scroll["canvasSize"] = (-0.65, 0.65, min(-0.6, bottom_y), 0.0)

    def _build_item_icon(self, item_id, x, y):
        item_def = get_item_def(item_id)
        icon_root = DirectFrame(
            parent=self._tab_canvas,
            frameColor=(0, 0, 0, 0),
            frameSize=(0, 1, 0, 1),
            pos=(x, 0, y - 0.055),
            scale=0.11,
        )
        self._tab_widgets.append(icon_root)
        if item_def:
            create_item_icon(icon_root, item_def)

    def _build_row(self, item_id, y, price_text, right_click_builder, subtitle_text=None):
        item_def = get_item_def(item_id)
        row = DirectFrame(
            parent=self._tab_canvas,
            frameColor=(0.16, 0.16, 0.19, 0.9),
            frameSize=(-0.62, 0.62, -0.055, 0.035),
            pos=(0, 0, y),
            relief=DGG.FLAT,
        )
        row.bind(DGG.B3PRESS, lambda _event, builder=right_click_builder: self._open_row_menu(builder))
        TOOLTIP_MANAGER.bind(row, lambda item=item_id: build_item_tooltip(item))
        self._tab_widgets.append(row)

        self._build_item_icon(item_id, -0.59, y + 0.035)
        self._tab_widgets.append(OnscreenText(
            text=item_def["name"] if item_def else item_id,
            parent=self._tab_canvas,
            pos=(-0.45, y - 0.005),
            scale=0.038,
            fg=(0.94, 0.94, 0.94, 1),
            align=TextNode.ALeft,
        ))
        if subtitle_text:
            self._tab_widgets.append(OnscreenText(
                text=subtitle_text,
                parent=self._tab_canvas,
                pos=(-0.45, y - 0.04),
                scale=0.026,
                fg=(0.67, 0.67, 0.72, 1),
                align=TextNode.ALeft,
            ))
        self._tab_widgets.append(OnscreenText(
            text=price_text,
            parent=self._tab_canvas,
            pos=(0.42, y - 0.005),
            scale=0.035,
            fg=(1, 0.82, 0.15, 1),
            align=TextNode.ARight,
        ))

    def _open_row_menu(self, action_builder):
        actions = action_builder() or []
        if actions:
            CONTEXT_MENU_MANAGER.show_at_mouse(actions)
        else:
            CONTEXT_MENU_MANAGER.hide()

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
            entries.append((item_id, item_def, qty_owned))
        return entries

    def _visible_buyback_entries(self):
        return [entry for entry in BUYBACK_QUEUE if entry.get("quantity", 0) > 0 and get_item_def(entry.get("item_id"))]

    def _show_buy_tab(self):
        self._active_tab = "buy"
        self._clear_tab()
        visible_stock = [(item_id, price) for item_id, price in self.stock.items() if get_item_def(item_id)]
        bottom_y = 0.0
        for idx, (item_id, buy_price) in enumerate(visible_stock):
            y = 0.28 - idx * 0.12
            bottom_y = y - 0.1
            self._build_row(
                item_id,
                y,
                f"{buy_price} gold",
                lambda item=item_id, price=buy_price: self._build_buy_actions(item, price),
                subtitle_text="Right-click to buy",
            )
        self._set_tab_canvas_size(bottom_y)

    def _show_sell_tab(self):
        self._active_tab = "sell"
        self._clear_tab()
        y = 0.28
        entries = self._iter_sell_entries()
        bottom_y = 0.0
        for item_id, item_def, qty_owned in entries:
            sell_price = item_def["value"]
            bottom_y = y - 0.1
            self._build_row(
                item_id,
                y,
                f"{sell_price} gold ea.",
                lambda item=item_id, price=sell_price, qty=qty_owned: self._build_sell_entry_actions(item, price, qty),
                subtitle_text=f"Owned: {qty_owned} | Right-click to sell",
            )
            y -= 0.12
        if not entries:
            self._tab_widgets.append(OnscreenText(
                text="Nothing to sell.\nYou can also right-click items in inventory while the vendor is open.",
                parent=self._tab_canvas,
                pos=(0, 0.1),
                scale=0.04,
                fg=(0.6, 0.6, 0.6, 1),
                align=TextNode.ACenter,
            ))
        self._set_tab_canvas_size(bottom_y)

    def _show_buyback_tab(self):
        self._active_tab = "buyback"
        self._clear_tab()
        entries = self._visible_buyback_entries()
        y = 0.28
        bottom_y = 0.0
        for idx, entry in enumerate(entries):
            bottom_y = y - 0.1
            self._build_row(
                entry["item_id"],
                y,
                f"{entry['price']} gold ea.",
                lambda index=idx, item=entry["item_id"], qty=entry["quantity"]: self._build_buyback_actions(index, item, qty),
                subtitle_text=f"Buy back qty: {entry['quantity']} | Right-click to repurchase",
            )
            y -= 0.12
        if not entries:
            self._tab_widgets.append(OnscreenText(
                text="No recent sales to buy back.",
                parent=self._tab_canvas,
                pos=(0, 0.1),
                scale=0.04,
                fg=(0.6, 0.6, 0.6, 1),
                align=TextNode.ACenter,
            ))
        self._set_tab_canvas_size(bottom_y)

    def _refresh_after_transaction(self):
        if self._gold_label is not None:
            self._gold_label.setText(f"Gold: {self._gold_count()}")
        app = getattr(builtins, "base", None)
        if app is not None and hasattr(app, "hud"):
            app.hud.refresh_inventory()
        if self._active_tab == "buy":
            self._show_buy_tab()
        elif self._active_tab == "sell":
            self._show_sell_tab()
        else:
            self._show_buyback_tab()

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
        qty = min(int(qty), int(entry["quantity"]))
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
        entry["quantity"] -= added
        self._refresh_after_transaction()
        return True

    def _build_buy_actions(self, item_id, price):
        max_affordable = self._gold_count() // price if price > 0 else 0
        max_qty = self._max_receivable_qty(item_id, max_affordable)
        if max_qty <= 0:
            return []
        return [
            {"label": "Buy 1", "callback": lambda item=item_id, unit_price=price: self.buy_from_stock(item, unit_price, 1)},
            {
                "label": "Buy 10",
                "callback": lambda item=item_id, unit_price=price, qty=max_qty: self.buy_from_stock(item, unit_price, min(10, qty)),
            },
            {
                "label": "Buy X",
                "callback": lambda item=item_id, unit_price=price, qty=max_qty: QUANTITY_PROMPT_MANAGER.ask(
                    f"Buy {item}",
                    qty,
                    lambda amount: self.buy_from_stock(item, unit_price, amount),
                    min(10, qty),
                ),
            },
        ]

    def _build_sell_entry_actions(self, item_id, price, qty_owned):
        max_qty = max(0, int(qty_owned))
        if max_qty <= 0:
            return []
        return [
            {"label": "Sell 1", "callback": lambda item=item_id, unit_price=price: self.sell_item_by_id(item, unit_price, 1)},
            {
                "label": "Sell 10",
                "callback": lambda item=item_id, unit_price=price, qty=max_qty: self.sell_item_by_id(item, unit_price, min(10, qty)),
            },
            {
                "label": "Sell X",
                "callback": lambda item=item_id, unit_price=price, qty=max_qty: QUANTITY_PROMPT_MANAGER.ask(
                    f"Sell {item}",
                    qty,
                    lambda amount: self.sell_item_by_id(item, unit_price, amount),
                    min(10, qty),
                ),
            },
        ]

    def _build_buyback_actions(self, entry_index, item_id, max_qty):
        if max_qty <= 0:
            return []
        entries = self._visible_buyback_entries()
        if not (0 <= entry_index < len(entries)):
            return []
        return [
            {"label": "Buy Back 1", "callback": lambda index=entry_index: self.buyback_item(index, 1)},
            {
                "label": "Buy Back 10",
                "callback": lambda index=entry_index, qty=max_qty: self.buyback_item(index, min(10, qty)),
            },
            {
                "label": "Buy Back X",
                "callback": lambda index=entry_index, qty=max_qty, item=item_id: QUANTITY_PROMPT_MANAGER.ask(
                    f"Buy Back {item}",
                    qty,
                    lambda amount: self.buyback_item(index, amount),
                    min(10, qty),
                ),
            },
        ]


load_vendor_catalogs()
