"""
bank.py — Bank building, proximity trigger, deposit/withdraw UI, save/load.
"""

import os
import json
import math
from panda3d.core import Vec3, NodePath, TextNode
from panda3d.bullet import BulletGhostNode, BulletSphereShape
from direct.gui.DirectGui import DirectFrame, DirectButton, OnscreenText

from inventory import Inventory, ITEMS
from resources import _make_box_geom

BANK_PROXIMITY = 5.0
BANK_SLOTS = 80
BANK_COLS = 8
BANK_ROWS = 10
SLOT_SIZE = 0.075
SLOT_GAP = 0.004
SAVE_PATH = os.path.join(os.path.dirname(__file__), "data", "save.json")


class Bank:
    def __init__(self, render, bullet_world, pos, player_inventory):
        self.render = render
        self.bullet_world = bullet_world
        self.pos = Vec3(*pos)
        self.player_inv = player_inventory
        self.bank_inv = Inventory(size=BANK_SLOTS)
        self.ui_open = False
        self._in_range = False
        self._prompt_shown = False
        self._ui = None

        self._load()
        self._build_building()
        self._build_ghost()
        self._setup_input()

    # ------------------------------------------------------------------
    # Building geometry
    # ------------------------------------------------------------------

    def _build_building(self):
        root = NodePath("bank_building")
        root.reparentTo(self.render)
        root.setPos(self.pos)

        # Main structure
        wall_color = (0.75, 0.7, 0.55, 1)
        roof_color = (0.5, 0.2, 0.1, 1)

        walls = root.attachNewNode(_make_box_geom(6, 5, 5, wall_color))
        walls.setPos(0, 0, 2.5)

        roof = root.attachNewNode(_make_box_geom(7, 6, 0.5, roof_color))
        roof.setPos(0, 0, 5.25)

        # Sign label
        OnscreenText(
            text="BANK",
            pos=(self.pos.x * 0.065, self.pos.z * 0.065 + 0.35),
            scale=0.04,
            fg=(1, 0.9, 0.2, 1),
            shadow=(0, 0, 0, 1),
            align=TextNode.ACenter,
        )

    def _build_ghost(self):
        shape = BulletSphereShape(BANK_PROXIMITY)
        ghost = BulletGhostNode("bank_ghost")
        ghost.addShape(shape)
        self._ghost_np = self.render.attachNewNode(ghost)
        self._ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 2)
        self.bullet_world.attachGhost(ghost)

    def _setup_input(self):
        pass  # E key handled centrally in main.py

    # ------------------------------------------------------------------
    # Proximity update
    # ------------------------------------------------------------------

    def update(self, dt, player_pos, hud):
        dx = player_pos.x - self.pos.x
        dy = player_pos.y - self.pos.y
        dist = math.sqrt(dx * dx + dy * dy)
        self._in_range = dist <= BANK_PROXIMITY

        if not self.ui_open:
            if self._in_range:
                hud.show_prompt("Press E to open Bank")
                self._prompt_shown = True
            elif self._prompt_shown:
                hud.clear_prompt_if("Press E to open Bank")
                self._prompt_shown = False

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
