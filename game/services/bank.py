"""Bank building, proximity trigger, and draggable bank UI."""

import json
import os

from panda3d.core import TextNode
from direct.gui.DirectGui import OnscreenText

from game.entities.npc import InteractableNpc, attach_billboard_label, build_humanoid_npc
from game.systems.inventory import Inventory
from game.ui.widgets import DraggableWindow, ItemSlotCollection, build_grid_slot_defs
from game.world.geometry import make_box_geom, make_cylinder

BANK_PROXIMITY = 5.0
BANK_SLOTS = 80
BANK_COLS = 8
BANK_ROWS = 10
SLOT_SIZE = 0.075
SLOT_GAP = 0.004
SAVE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "save.json",
)


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
        floor_color = (0.56, 0.48, 0.36, 1)
        wall_color = (0.72, 0.66, 0.54, 1)
        trim_color = (0.33, 0.22, 0.14, 1)
        roof_color = (0.24, 0.14, 0.1, 1)
        counter_color = (0.42, 0.27, 0.17, 1)
        pillar_color = (0.62, 0.56, 0.44, 1)

        floor = self.root.attachNewNode(make_box_geom(10.5, 8.5, 0.35, floor_color))
        floor.setPos(0, 0, 0.18)
        back_wall = self.root.attachNewNode(make_box_geom(10.0, 0.4, 4.8, wall_color))
        back_wall.setPos(0, 3.95, 2.6)
        left_wall = self.root.attachNewNode(make_box_geom(0.4, 7.2, 4.8, wall_color))
        left_wall.setPos(-4.8, 0.35, 2.6)
        right_wall = self.root.attachNewNode(make_box_geom(0.4, 7.2, 4.8, wall_color))
        right_wall.setPos(4.8, 0.35, 2.6)
        rear_gable = self.root.attachNewNode(make_box_geom(10.0, 0.35, 1.7, wall_color))
        rear_gable.setPos(0, 3.9, 5.4)
        front_beam = self.root.attachNewNode(make_box_geom(10.0, 0.35, 0.55, trim_color))
        front_beam.setPos(0, -3.6, 4.95)

        for x in (-4.1, -1.4, 1.4, 4.1):
            pillar = self.root.attachNewNode(make_cylinder(0.22, 4.5, pillar_color))
            pillar.setPos(x, -3.25, 0.35)

        roof_main = self.root.attachNewNode(make_box_geom(11.4, 9.4, 0.35, roof_color))
        roof_main.setPos(0, 0.1, 5.15)
        roof_main.setP(-8)
        roof_cap = self.root.attachNewNode(make_box_geom(10.4, 8.4, 0.25, (0.44, 0.29, 0.18, 1)))
        roof_cap.setPos(0, 0.18, 5.62)
        roof_cap.setP(-8)
        counter = self.root.attachNewNode(make_box_geom(7.4, 1.2, 1.3, counter_color))
        counter.setPos(0, 1.4, 0.95)
        desk_top = self.root.attachNewNode(make_box_geom(7.8, 1.45, 0.18, trim_color))
        desk_top.setPos(0, 1.25, 1.58)
        ledger = self.root.attachNewNode(make_box_geom(1.3, 0.9, 0.18, (0.16, 0.24, 0.22, 1)))
        ledger.setPos(-1.7, 1.0, 1.77)
        chest = self.root.attachNewNode(make_box_geom(1.2, 0.9, 1.0, (0.5, 0.38, 0.18, 1)))
        chest.setPos(2.6, 1.05, 0.72)
        sign_board = self.root.attachNewNode(make_box_geom(3.6, 0.18, 1.1, (0.2, 0.12, 0.08, 1)))
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

    def update(self, dt, player_pos, hud):
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
                    self.bank_inv.from_dict(json.load(handle))
            except Exception:
                pass
