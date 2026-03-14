"""
vendor.py — NPC vendor, shop stock, buy/sell UI with Buy/Sell tabs.
"""

from panda3d.core import TextNode
from direct.gui.DirectGui import DirectFrame, DirectButton, OnscreenText

from game.entities.npc import InteractableNpc, build_humanoid_npc
from game.systems.inventory import ITEMS

VENDOR_PROXIMITY = 5.0

# Shop stock: item_id → buy price (in gold)
SHOP_STOCK = {
    "wood": 8,
    "ore":  12,
    "fish": 10,
}

SLOT_SIZE = 0.08
SLOT_GAP = 0.005


class Vendor(InteractableNpc):
    def __init__(self, render, bullet_world, pos, player_inventory):
        self.player_inv = player_inventory
        self.ui_open = False
        self._ui = None
        self._active_tab = "buy"

        super().__init__(render, bullet_world, pos, VENDOR_PROXIMITY, "Press E to talk to Vendor")

    # ------------------------------------------------------------------
    # NPC geometry
    # ------------------------------------------------------------------

    def _build_visual(self):
        build_humanoid_npc(
            self.root,
            body_color=(0.2, 0.4, 0.8, 1),
            head_color=(0.85, 0.7, 0.5, 1),
            accent_color=(0.95, 0.75, 0.2, 1),
            label="Vendor",
        )

    # ------------------------------------------------------------------
    # Proximity update
    # ------------------------------------------------------------------

    def update(self, dt, player_pos, hud):
        self.update_prompt(player_pos, hud, ui_open=self.ui_open)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def open_ui(self):
        self.ui_open = True
        self._build_ui()

    def close_ui(self):
        self.ui_open = False
        if self._ui:
            self._ui.destroy()
            self._ui = None

    def _gold_count(self):
        return self.player_inv.count_item("gold")

    def _build_ui(self):
        self._ui = DirectFrame(
            frameColor=(0.1, 0.1, 0.1, 0.95),
            frameSize=(-0.7, 0.7, -0.65, 0.65),
            pos=(0, 0, 0),
        )

        OnscreenText(
            text="Vendor Shop",
            parent=self._ui,
            pos=(0, 0.58),
            scale=0.055,
            fg=(1, 0.85, 0.2, 1),
            align=TextNode.ACenter,
        )

        self._gold_label = OnscreenText(
            text=f"Gold: {self._gold_count()}",
            parent=self._ui,
            pos=(0, 0.50),
            scale=0.04,
            fg=(1, 0.8, 0, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )

        # Close
        DirectButton(
            parent=self._ui,
            text="X",
            scale=0.05,
            pos=(0.63, 0, 0.58),
            command=self.close_ui,
            frameColor=(0.6, 0.1, 0.1, 1),
            text_fg=(1, 1, 1, 1),
        )

        # Tab buttons
        self._tab_buy_btn = DirectButton(
            parent=self._ui,
            text="Buy",
            scale=0.05,
            pos=(-0.15, 0, 0.42),
            command=self._show_buy_tab,
            frameColor=(0.3, 0.5, 0.3, 1),
            text_fg=(1, 1, 1, 1),
        )
        self._tab_sell_btn = DirectButton(
            parent=self._ui,
            text="Sell",
            scale=0.05,
            pos=(0.15, 0, 0.42),
            command=self._show_sell_tab,
            frameColor=(0.3, 0.3, 0.5, 1),
            text_fg=(1, 1, 1, 1),
        )

        self._tab_content = DirectFrame(
            parent=self._ui,
            frameColor=(0, 0, 0, 0),
            frameSize=(-0.65, 0.65, -0.6, 0.35),
            pos=(0, 0, 0),
        )

        self._show_buy_tab()

    def _clear_tab(self):
        for child in self._tab_content.getChildren():
            child.removeNode()

    def _show_buy_tab(self):
        self._active_tab = "buy"
        self._clear_tab()

        items_list = list(SHOP_STOCK.items())
        for idx, (item_id, buy_price) in enumerate(items_list):
            y = 0.28 - idx * 0.14
            item_def = ITEMS[item_id]

            # Color swatch
            DirectFrame(
                parent=self._tab_content,
                frameColor=item_def["color"],
                frameSize=(0, 0.06, -0.06, 0),
                pos=(-0.55, 0, y),
            )

            OnscreenText(
                text=f"{item_def['name']}",
                parent=self._tab_content,
                pos=(-0.45, y - 0.015),
                scale=0.038,
                fg=(0.9, 0.9, 0.9, 1),
                align=TextNode.ALeft,
            )

            OnscreenText(
                text=f"{buy_price} gold",
                parent=self._tab_content,
                pos=(0.1, y - 0.015),
                scale=0.035,
                fg=(1, 0.8, 0, 1),
                align=TextNode.ALeft,
            )

            # Quantity buttons
            for qi, qty in enumerate([1, 5, 10]):
                DirectButton(
                    parent=self._tab_content,
                    text=f"Buy {qty}",
                    scale=0.032,
                    pos=(0.35 + qi * 0.12, 0, y - 0.015),
                    command=self._buy,
                    extraArgs=[item_id, buy_price, qty],
                    frameColor=(0.2, 0.5, 0.2, 1),
                    text_fg=(1, 1, 1, 1),
                )

    def _show_sell_tab(self):
        self._active_tab = "sell"
        self._clear_tab()

        # Show items in player inventory that have a sell value
        y = 0.28
        seen = set()
        for slot in self.player_inv.slots:
            if slot and slot["id"] not in seen:
                seen.add(slot["id"])
                item_id = slot["id"]
                item_def = ITEMS.get(item_id)
                if not item_def:
                    continue
                sell_price = item_def["value"]
                qty = self.player_inv.count_item(item_id)

                DirectFrame(
                    parent=self._tab_content,
                    frameColor=item_def["color"],
                    frameSize=(0, 0.06, -0.06, 0),
                    pos=(-0.55, 0, y),
                )
                OnscreenText(
                    text=f"{item_def['name']} x{qty}",
                    parent=self._tab_content,
                    pos=(-0.45, y - 0.015),
                    scale=0.038,
                    fg=(0.9, 0.9, 0.9, 1),
                    align=TextNode.ALeft,
                )
                OnscreenText(
                    text=f"{sell_price} gold ea.",
                    parent=self._tab_content,
                    pos=(0.1, y - 0.015),
                    scale=0.035,
                    fg=(1, 0.8, 0, 1),
                    align=TextNode.ALeft,
                )

                for qi, sell_qty in enumerate([1, 5, 10]):
                    DirectButton(
                        parent=self._tab_content,
                        text=f"Sell {sell_qty}",
                        scale=0.032,
                        pos=(0.35 + qi * 0.12, 0, y - 0.015),
                        command=self._sell,
                        extraArgs=[item_id, sell_price, sell_qty],
                        frameColor=(0.2, 0.2, 0.5, 1),
                        text_fg=(1, 1, 1, 1),
                    )

                y -= 0.14
                if y < -0.55:
                    break

        if not seen:
            OnscreenText(
                text="Nothing to sell.",
                parent=self._tab_content,
                pos=(0, 0.1),
                scale=0.04,
                fg=(0.6, 0.6, 0.6, 1),
                align=TextNode.ACenter,
            )

    def _buy(self, item_id, price, qty):
        gold = self._gold_count()
        total_cost = price * qty
        if gold < total_cost:
            return
        if self.player_inv.is_full():
            return
        self.player_inv.remove_item("gold", total_cost)
        self.player_inv.add_item(item_id, qty)
        self._gold_label.setText(f"Gold: {self._gold_count()}")
        # Refresh active tab
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
        # Refresh sell tab
        self._show_sell_tab()
