"""
bank.py — Bank building, proximity trigger, deposit/withdraw UI, save/load.
"""

import os
import json
from panda3d.core import TextNode
from direct.gui.DirectGui import DirectFrame, DirectButton, OnscreenText

from inventory import Inventory, ITEMS
from npc import InteractableNpc, build_humanoid_npc, attach_billboard_label
from resources import _make_box_geom, _make_cylinder

BANK_PROXIMITY = 5.0
BANK_SLOTS = 80
BANK_COLS = 8
BANK_ROWS = 10
SLOT_SIZE = 0.075
SLOT_GAP = 0.004
SAVE_PATH = os.path.join(os.path.dirname(__file__), "data", "save.json")


class Bank(InteractableNpc):
    def __init__(self, render, bullet_world, pos, player_inventory):
        self.player_inv = player_inventory
        self.bank_inv = Inventory(size=BANK_SLOTS)
        self.ui_open = False
        self._ui = None

        self._load()
        super().__init__(render, bullet_world, pos, BANK_PROXIMITY, "Press E to talk to Banker")

    # ------------------------------------------------------------------
    # Building geometry
    # ------------------------------------------------------------------

    def _build_visual(self):
        floor_color = (0.56, 0.48, 0.36, 1)
        wall_color = (0.72, 0.66, 0.54, 1)
        trim_color = (0.33, 0.22, 0.14, 1)
        roof_color = (0.24, 0.14, 0.1, 1)
        counter_color = (0.42, 0.27, 0.17, 1)
        pillar_color = (0.62, 0.56, 0.44, 1)

        floor = self.root.attachNewNode(_make_box_geom(10.5, 8.5, 0.35, floor_color))
        floor.setPos(0, 0, 0.18)

        back_wall = self.root.attachNewNode(_make_box_geom(10.0, 0.4, 4.8, wall_color))
        back_wall.setPos(0, 3.95, 2.6)

        left_wall = self.root.attachNewNode(_make_box_geom(0.4, 7.2, 4.8, wall_color))
        left_wall.setPos(-4.8, 0.35, 2.6)

        right_wall = self.root.attachNewNode(_make_box_geom(0.4, 7.2, 4.8, wall_color))
        right_wall.setPos(4.8, 0.35, 2.6)

        rear_gable = self.root.attachNewNode(_make_box_geom(10.0, 0.35, 1.7, wall_color))
        rear_gable.setPos(0, 3.9, 5.4)

        front_beam = self.root.attachNewNode(_make_box_geom(10.0, 0.35, 0.55, trim_color))
        front_beam.setPos(0, -3.6, 4.95)

        for x in (-4.1, -1.4, 1.4, 4.1):
            pillar = self.root.attachNewNode(_make_cylinder(0.22, 4.5, pillar_color))
            pillar.setPos(x, -3.25, 0.35)

        roof_main = self.root.attachNewNode(_make_box_geom(11.4, 9.4, 0.35, roof_color))
        roof_main.setPos(0, 0.1, 5.15)
        roof_main.setP(-8)

        roof_cap = self.root.attachNewNode(_make_box_geom(10.4, 8.4, 0.25, (0.44, 0.29, 0.18, 1)))
        roof_cap.setPos(0, 0.18, 5.62)
        roof_cap.setP(-8)

        counter = self.root.attachNewNode(_make_box_geom(7.4, 1.2, 1.3, counter_color))
        counter.setPos(0, 1.4, 0.95)

        desk_top = self.root.attachNewNode(_make_box_geom(7.8, 1.45, 0.18, trim_color))
        desk_top.setPos(0, 1.25, 1.58)

        ledger = self.root.attachNewNode(_make_box_geom(1.3, 0.9, 0.18, (0.16, 0.24, 0.22, 1)))
        ledger.setPos(-1.7, 1.0, 1.77)

        chest = self.root.attachNewNode(_make_box_geom(1.2, 0.9, 1.0, (0.5, 0.38, 0.18, 1)))
        chest.setPos(2.6, 1.05, 0.72)

        sign_board = self.root.attachNewNode(_make_box_geom(3.6, 0.18, 1.1, (0.2, 0.12, 0.08, 1)))
        sign_board.setPos(0, -3.55, 4.0)
        attach_billboard_label(sign_board, "BANK", (0, -0.15, -0.18), 1.2, (1, 0.9, 0.55, 1))

        banker_spot = self.root.attachNewNode("banker_spot")
        banker_spot.setPos(0, 2.2, 0.35)
        build_humanoid_npc(
            banker_spot,
            body_color=(0.22, 0.46, 0.34, 1),
            head_color=(0.87, 0.73, 0.6, 1),
            accent_color=(0.9, 0.82, 0.45, 1),
            label="Banker",
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

    def _build_ui(self):
        self._ui = DirectFrame(
            frameColor=(0.1, 0.1, 0.1, 0.95),
            frameSize=(-0.85, 0.85, -0.75, 0.75),
            pos=(0, 0, 0),
        )

        OnscreenText(
            text="Bank",
            parent=self._ui,
            pos=(0, 0.68),
            scale=0.06,
            fg=(1, 0.85, 0.2, 1),
            align=TextNode.ACenter,
        )

        # Close button
        DirectButton(
            parent=self._ui,
            text="X",
            scale=0.05,
            pos=(0.78, 0, 0.68),
            command=self.close_ui,
            frameColor=(0.6, 0.1, 0.1, 1),
            text_fg=(1, 1, 1, 1),
        )

        # Bank grid (left)
        OnscreenText(text="Bank", parent=self._ui, pos=(-0.45, 0.6), scale=0.04,
                     fg=(0.8, 0.8, 0.8, 1), align=TextNode.ACenter)
        self._bank_slot_frames = self._build_grid(
            self._ui, self.bank_inv, BANK_COLS, BANK_ROWS, -0.82, 0.55,
            on_click=self._withdraw
        )

        # Inventory grid (right)
        OnscreenText(text="Inventory", parent=self._ui, pos=(0.55, 0.6), scale=0.04,
                     fg=(0.8, 0.8, 0.8, 1), align=TextNode.ACenter)
        self._inv_slot_frames = self._build_grid(
            self._ui, self.player_inv, 4, 7, 0.32, 0.55,
            on_click=self._deposit
        )

    def _build_grid(self, parent, inv, cols, rows, origin_x, origin_y, on_click):
        frames = []
        for i in range(cols * rows):
            col = i % cols
            row = i // cols
            x = origin_x + col * (SLOT_SIZE + SLOT_GAP)
            y = origin_y - row * (SLOT_SIZE + SLOT_GAP)

            slot = DirectButton(
                parent=parent,
                frameColor=(0.25, 0.25, 0.25, 1),
                frameSize=(0, SLOT_SIZE, -SLOT_SIZE, 0),
                pos=(x, 0, y),
                relief=1,
                command=on_click,
                extraArgs=[i],
            )
            item_frame = DirectFrame(
                parent=slot,
                frameColor=(0, 0, 0, 0),
                frameSize=(0.005, SLOT_SIZE - 0.005, -(SLOT_SIZE - 0.005), -0.005),
            )
            qty_lbl = OnscreenText(
                text="",
                parent=slot,
                pos=(SLOT_SIZE - 0.005, -(SLOT_SIZE - 0.01)),
                scale=0.022,
                fg=(1, 1, 1, 1),
                align=TextNode.ARight,
                mayChange=True,
            )
            frames.append((slot, item_frame, qty_lbl))

        self._refresh_grid(frames, inv)
        return frames

    def _refresh_grid(self, frames, inv):
        for i, (slot, item_frame, qty_lbl) in enumerate(frames):
            data = inv.slots[i] if i < len(inv.slots) else None
            if data:
                item_def = ITEMS.get(data["id"])
                item_frame["frameColor"] = item_def["color"] if item_def else (0.5, 0.5, 0.5, 1)
                qty = data["quantity"]
                qty_lbl.setText(str(qty) if qty > 1 else "")
            else:
                item_frame["frameColor"] = (0, 0, 0, 0)
                qty_lbl.setText("")

    def _deposit(self, slot_index):
        """Move item from player inventory slot → bank."""
        if slot_index >= len(self.player_inv.slots):
            return
        data = self.player_inv.slots[slot_index]
        if not data:
            return
        item_id = data["id"]
        qty = data["quantity"]
        if self.bank_inv.add_item(item_id, qty):
            self.player_inv.slots[slot_index] = None
            self._save()
            self._refresh_grid(self._bank_slot_frames, self.bank_inv)
            self._refresh_grid(self._inv_slot_frames, self.player_inv)

    def _withdraw(self, slot_index):
        """Move item from bank slot → player inventory."""
        if slot_index >= len(self.bank_inv.slots):
            return
        data = self.bank_inv.slots[slot_index]
        if not data:
            return
        item_id = data["id"]
        qty = data["quantity"]
        if self.player_inv.add_item(item_id, qty):
            self.bank_inv.slots[slot_index] = None
            self._save()
            self._refresh_grid(self._bank_slot_frames, self.bank_inv)
            self._refresh_grid(self._inv_slot_frames, self.player_inv)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self):
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        with open(SAVE_PATH, "w") as f:
            json.dump(self.bank_inv.to_dict(), f)

    def _load(self):
        if os.path.exists(SAVE_PATH):
            try:
                with open(SAVE_PATH) as f:
                    self.bank_inv.from_dict(json.load(f))
            except Exception:
                pass
