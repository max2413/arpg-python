"""Vendor NPC and draggable shop UI."""

import builtins
import math
import random

from panda3d.core import TextNode, Vec3
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText

from game.entities.npc import InteractableNpc, build_humanoid_npc
from game.systems.inventory import get_item_def
from game.ui.widgets import DraggableWindow, create_item_icon

VENDOR_PROXIMITY = 5.0
VENDOR_PATROL_RADIUS = 12.0
VENDOR_PATROL_SPEED = 2.5
VENDOR_WAIT_TIME = 4.0

SHOP_STOCK = {
    "wood": 8,
    "ore": 12,
    "fish": 10,
    "cloth_hood": 20,
    "traveler_tunic": 28,
    "canvas_pants": 22,
    "bronze_sword": 35,
    "oak_shield": 30,
}


class Vendor(InteractableNpc):
    def __init__(self, render, bullet_world, pos, player_inventory):
        self.player_inv = player_inventory
        self.ui_open = False
        self._window = None
        self._active_tab = "buy"
        self._tab_widgets = []
        
        self.patrol_center = Vec3(*pos)
        self._target_pos = Vec3(*pos)
        self._patrol_wait = 0.0
        self._state = "idle"
        
        super().__init__(render, bullet_world, pos, VENDOR_PROXIMITY, "Press E to talk to Vendor")

    def _build_visual(self):
        self.model = build_humanoid_npc(
            self.root,
            body_color=(0.2, 0.4, 0.8, 1),
            head_color=(0.85, 0.7, 0.5, 1),
            accent_color=(0.95, 0.75, 0.2, 1),
            label="Vendor",
        )

    def update(self, dt, player_pos, hud):
        moving = False
        if not self.ui_open:
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
                    # Turn to face target
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
        if self._window:
            self._window.destroy()
            self._window = None
            self._tab_widgets = []

    def _gold_count(self):
        return self.player_inv.count_item("gold")

    def _build_ui(self):
        self._window = DraggableWindow("Vendor Shop", (-0.7, 0.7, -0.65, 0.65), (0, 0, 0), self.close_ui)
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
        self._tab_buy_btn = DirectButton(
            parent=body,
            text="Buy",
            scale=0.05,
            pos=(-0.15, 0, 0.42),
            command=self._show_buy_tab,
            frameColor=(0.3, 0.5, 0.3, 1),
            text_fg=(1, 1, 1, 1),
        )
        self._tab_sell_btn = DirectButton(
            parent=body,
            text="Sell",
            scale=0.05,
            pos=(0.15, 0, 0.42),
            command=self._show_sell_tab,
            frameColor=(0.3, 0.3, 0.5, 1),
            text_fg=(1, 1, 1, 1),
        )
        self._tab_content = DirectFrame(
            parent=body,
            frameColor=(0, 0, 0, 0),
            frameSize=(-0.65, 0.65, -0.6, 0.35),
        )
        self._show_buy_tab()

    def _clear_tab(self):
        for widget in self._tab_widgets:
            widget.destroy()
        self._tab_widgets = []

    def _build_item_icon(self, item_id, x, y):
        item_def = get_item_def(item_id)
        icon_root = DirectFrame(
            parent=self._tab_content,
            frameColor=(0, 0, 0, 0),
            frameSize=(0, 1, 0, 1),
            pos=(x, 0, y - 0.055),
            scale=0.11,
        )
        self._tab_widgets.append(icon_root)
        if item_def:
            create_item_icon(icon_root, item_def)

    def _show_buy_tab(self):
        self._active_tab = "buy"
        self._clear_tab()
        for idx, (item_id, buy_price) in enumerate(SHOP_STOCK.items()):
            item_def = get_item_def(item_id)
            if item_def is None:
                continue
            y = 0.28 - idx * 0.1
            if y < -0.56:
                break
            self._build_item_icon(item_id, -0.59, y)
            self._tab_widgets.append(OnscreenText(
                text=item_def["name"],
                parent=self._tab_content,
                pos=(-0.45, y - 0.015),
                scale=0.038,
                fg=(0.9, 0.9, 0.9, 1),
                align=TextNode.ALeft,
            ))
            self._tab_widgets.append(OnscreenText(
                text=f"{buy_price} gold",
                parent=self._tab_content,
                pos=(0.08, y - 0.015),
                scale=0.035,
                fg=(1, 0.8, 0, 1),
                align=TextNode.ALeft,
            ))
            for qi, qty in enumerate((1, 5, 10)):
                self._tab_widgets.append(DirectButton(
                    parent=self._tab_content,
                    text=f"Buy {qty}",
                    scale=0.032,
                    pos=(0.34 + qi * 0.12, 0, y - 0.015),
                    command=self._buy,
                    extraArgs=[item_id, buy_price, qty],
                    frameColor=(0.2, 0.5, 0.2, 1),
                    text_fg=(1, 1, 1, 1),
                ))

    def _show_sell_tab(self):
        self._active_tab = "sell"
        self._clear_tab()
        y = 0.28
        seen = set()
        for slot in self.player_inv.slots:
            if not slot or slot["id"] in seen:
                continue
            seen.add(slot["id"])
            item_def = get_item_def(slot["id"])
            if item_def is None:
                continue
            self._build_item_icon(slot["id"], -0.59, y)
            sell_price = item_def["value"]
            qty_owned = self.player_inv.count_item(slot["id"])
            self._tab_widgets.append(OnscreenText(
                text=f"{item_def['name']} x{qty_owned}",
                parent=self._tab_content,
                pos=(-0.45, y - 0.015),
                scale=0.038,
                fg=(0.9, 0.9, 0.9, 1),
                align=TextNode.ALeft,
            ))
            self._tab_widgets.append(OnscreenText(
                text=f"{sell_price} gold ea.",
                parent=self._tab_content,
                pos=(0.08, y - 0.015),
                scale=0.035,
                fg=(1, 0.8, 0, 1),
                align=TextNode.ALeft,
            ))
            for qi, sell_qty in enumerate((1, 5, 10)):
                self._tab_widgets.append(DirectButton(
                    parent=self._tab_content,
                    text=f"Sell {sell_qty}",
                    scale=0.032,
                    pos=(0.34 + qi * 0.12, 0, y - 0.015),
                    command=self._sell,
                    extraArgs=[slot["id"], sell_price, sell_qty],
                    frameColor=(0.2, 0.2, 0.5, 1),
                    text_fg=(1, 1, 1, 1),
                ))
            y -= 0.1
            if y < -0.56:
                break
        if not seen:
            self._tab_widgets.append(OnscreenText(
                text="Nothing to sell.",
                parent=self._tab_content,
                pos=(0, 0.1),
                scale=0.04,
                fg=(0.6, 0.6, 0.6, 1),
                align=TextNode.ACenter,
            ))

    def _buy(self, item_id, price, qty):
        total_cost = price * qty
        if self._gold_count() < total_cost:
            return
        if not self.player_inv.remove_item("gold", total_cost):
            return
        added = 0
        for _ in range(qty):
            if self.player_inv.add_item(item_id, 1):
                added += 1
            else:
                break
        if added < qty:
            self.player_inv.add_item("gold", price * (qty - added))
        self._gold_label.setText(f"Gold: {self._gold_count()}")
        app = getattr(builtins, "base", None)
        if app is not None and hasattr(app, "hud"):
            app.hud.refresh_inventory()
        if self._active_tab == "buy":
            self._show_buy_tab()
        else:
            self._show_sell_tab()

    def _sell(self, item_id, price, qty):
        available = self.player_inv.count_item(item_id)
        sell_qty = min(qty, available)
        if sell_qty <= 0:
            return
        self.player_inv.remove_item(item_id, sell_qty)
        self.player_inv.add_item("gold", sell_qty * price)
        self._gold_label.setText(f"Gold: {self._gold_count()}")
        app = getattr(builtins, "base", None)
        if app is not None and hasattr(app, "hud"):
            app.hud.refresh_inventory()
        self._show_sell_tab()
