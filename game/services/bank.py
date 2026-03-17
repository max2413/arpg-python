"""Bank building, proximity trigger, and draggable bank UI."""

import json
import os

from panda3d.core import TextNode
from direct.gui.DirectGui import OnscreenText

from game.entities.npc import InteractableNpc, attach_billboard_label, build_humanoid_npc
from game.systems.inventory import Inventory, sanitize_inventory_payload
from game.systems.paths import data_path, save_path
from game.ui.widgets import DraggableWindow, ItemSlotCollection, build_grid_slot_defs
from game.world.structures import build_structure_shell

BANK_PROXIMITY = 7.0
BANK_SLOTS = 80
BANK_COLS = 8
BANK_ROWS = 10
SLOT_SIZE = 0.075
SLOT_GAP = 0.004
SAVE_PATH = save_path("bank.json")
LEGACY_BANK_PATH = data_path("bank.json")
LEGACY_SAVE_PATH = data_path("save.json")
BANK_SCALE = 2.0


class Bank(InteractableNpc):
    def __init__(self, render, bullet_world, pos, player_inventory):
        self.player_inv = player_inventory
        self.bank_inv = Inventory(size=BANK_SLOTS)
        self.ui_open = False
        self._window = None
        self._bank_slots = None
        self._player_slots = None
        self._load()
        super().__init__(render, bullet_world, pos, BANK_PROXIMITY, "Press E to talk to Banker")

    def _build_visual(self):
        self.root.setScale(BANK_SCALE)
        shell = build_structure_shell(
            "bank",
            self.root,
            self.render,
            self.bullet_world,
            (self.pos.x, self.pos.y, self.pos.z),
            scale=BANK_SCALE,
        )
        self._collision_nodes = shell["collision_nodes"]
        sign_x, sign_y, sign_z = shell["anchors"]["sign"]
        sign_board = self.root.attachNewNode("bank_sign_anchor")
        sign_board.setPos(sign_x, sign_y, sign_z)
        attach_billboard_label(sign_board, "BANK", (0, -0.15, -0.18), 1.2, (1, 0.9, 0.55, 1))

        banker_spot = self.root.attachNewNode("banker_spot")
        banker_x, banker_y, banker_z = shell["anchors"]["npc"]
        banker_spot.setPos(banker_x, banker_y, banker_z)
        banker_spot.setScale(1.0 / BANK_SCALE)
        self.model = build_humanoid_npc(
            banker_spot,
            body_color=(0.22, 0.46, 0.34, 1),
            head_color=(0.87, 0.73, 0.6, 1),
            accent_color=(0.9, 0.82, 0.45, 1),
            label="Banker",
        )

    def update(self, dt, player_pos, hud):
        self._animate(dt)
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
            self._bank_slots = None
            self._player_slots = None

    def _build_ui(self):
        self._window = DraggableWindow("Bank", (-0.85, 0.85, -0.75, 0.75), (0, 0, 0), self.close_ui)
        body = self._window.body
        OnscreenText(
            text="Drag items between bank and inventory.",
            parent=body,
            pos=(0, 0.6),
            scale=0.04,
            fg=(1, 0.85, 0.2, 1),
            align=TextNode.ACenter,
        )
        OnscreenText(text="Bank", parent=body, pos=(-0.45, 0.52), scale=0.04, fg=(0.8, 0.8, 0.8, 1), align=TextNode.ACenter)
        OnscreenText(text="Inventory", parent=body, pos=(0.55, 0.52), scale=0.04, fg=(0.8, 0.8, 0.8, 1), align=TextNode.ACenter)

        self._bank_slots = ItemSlotCollection(
            body,
            self.bank_inv,
            build_grid_slot_defs(BANK_COLS, BANK_ROWS, SLOT_SIZE, SLOT_GAP, -0.82, 0.46),
            SLOT_SIZE,
            on_change=self._on_inventory_changed,
        )
        self._player_slots = ItemSlotCollection(
            body,
            self.player_inv,
            build_grid_slot_defs(4, 7, SLOT_SIZE, SLOT_GAP, 0.32, 0.46),
            SLOT_SIZE,
            on_change=self._on_inventory_changed,
        )
        self._bank_slots.transfer_targets = [self._player_slots]
        self._player_slots.transfer_targets = [self._bank_slots]

    def _on_inventory_changed(self):
        self._save()
        if self._bank_slots:
            self._bank_slots.refresh()
        if self._player_slots:
            self._player_slots.refresh()

    def _save(self):
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        with open(SAVE_PATH, "w") as handle:
            json.dump(self.bank_inv.to_dict(), handle)

    def _load(self):
        if os.path.exists(SAVE_PATH):
            try:
                with open(SAVE_PATH) as handle:
                    self.bank_inv.from_dict(sanitize_inventory_payload(json.load(handle)))
            except Exception:
                pass
            return
        if os.path.exists(LEGACY_BANK_PATH):
            try:
                with open(LEGACY_BANK_PATH) as handle:
                    self.bank_inv.from_dict(sanitize_inventory_payload(json.load(handle)))
            except Exception:
                pass
            return
        if os.path.exists(LEGACY_SAVE_PATH):
            try:
                with open(LEGACY_SAVE_PATH) as handle:
                    data = json.load(handle)
                if "slots" in data and "inventory" not in data:
                    self.bank_inv.from_dict(sanitize_inventory_payload(data))
            except Exception:
                pass

    def remove_from_world(self, hud=None):
        for node in getattr(self, "_collision_nodes", []):
            if node is not None and not node.isEmpty():
                self.bullet_world.removeRigidBody(node.node())
                node.removeNode()
        self._collision_nodes = []
        super().remove_from_world(hud)
