"""HUD panels, prompts, and draggable inventory windows."""

import math

from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from game.systems.skills import SKILLS
from game.ui.widgets import (
    DraggableWindow,
    ItemSlotCollection,
    build_equipment_slot_defs,
    build_grid_slot_defs,
)


INV_COLS = 4
INV_ROWS = 7
SLOT_SIZE = 0.09
SLOT_GAP = 0.005
BAR_WIDTH = 0.3
BAR_HEIGHT = 0.04
HUD_BUTTON_X = -1.08
HUD_BUTTON_Y = 0.06


class HUD:
    def __init__(self, inventory, skills):
        self.inventory = inventory
        self.skills = skills
        self._prompt_msg = ""
        self._inv_visible = False
        self._skill_visible = False
        self._equip_visible = False
        self._inventory_slots = None
        self._equipment_slots = None
        self._skill_bars = {}

        self._build_prompt()
        self._build_health_panel()
        self._build_target_panel()
        self._build_range_indicators()
        self._build_menu_buttons()
        self._build_inventory_window()
        self._build_equipment_window()
        self._build_skill_window()

    def _build_prompt(self):
        self._prompt_text = OnscreenText(
            text="",
            pos=(0, 0.85),
            scale=0.05,
            fg=(1, 1, 0.3, 1),
            shadow=(0, 0, 0, 0.8),
            align=TextNode.ACenter,
            mayChange=True,
        )

    def show_prompt(self, msg):
        self._prompt_msg = msg
        self._prompt_text.setText(msg)

    def clear_prompt_if(self, msg):
        if self._prompt_msg == msg:
            self.clear_prompt()

    def clear_prompt(self):
        self._prompt_msg = ""
        self._prompt_text.setText("")

    def _build_health_panel(self):
        self._health_panel = DirectFrame(
            frameColor=(0.15, 0.15, 0.15, 0.9),
            frameSize=(0, 0.42, -0.1, 0.06),
            pos=(-1.18, 0, 0.9),
        )
        self._health_label = OnscreenText(
            text="HP 100/100",
            parent=self._health_panel,
            pos=(0.21, -0.01),
            scale=0.04,
            fg=(1, 1, 1, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )
        DirectFrame(
            parent=self._health_panel,
            frameColor=(0.1, 0.1, 0.1, 1),
            frameSize=(0.02, 0.4, -0.08, -0.04),
            pos=(0, 0, 0),
        )
        self._health_fill = DirectFrame(
            parent=self._health_panel,
            frameColor=(0.8, 0.15, 0.15, 1),
            frameSize=(0.02, 0.4, -0.08, -0.04),
            pos=(0, 0, 0),
        )
        self._death_text = OnscreenText(
            text="",
            pos=(0, 0.1),
            scale=0.09,
            fg=(1, 0.3, 0.3, 1),
            shadow=(0, 0, 0, 0.9),
            align=TextNode.ACenter,
            mayChange=True,
        )

    def refresh_health(self, health, max_health):
        ratio = 0.0 if max_health <= 0 else max(0.0, min(1.0, health / max_health))
        fill_right = 0.02 + 0.38 * ratio
        self._health_fill["frameSize"] = (0.02, max(0.02, fill_right), -0.08, -0.04)
        self._health_label.setText(f"HP {int(math.ceil(health))}/{max_health}")

    def show_death(self, respawn_time):
        self._death_text.setText(f"You died\nRespawning in {respawn_time:.1f}s")

    def clear_death(self):
        self._death_text.setText("")

    def _build_target_panel(self):
        self._target_panel = DirectFrame(
            frameColor=(0.12, 0.12, 0.12, 0.88),
            frameSize=(-0.24, 0.24, -0.11, 0.07),
            pos=(0, 0, 0.82),
        )
        self._target_name = OnscreenText(
            text="",
            parent=self._target_panel,
            pos=(0, 0.015),
            scale=0.045,
            fg=(1, 0.88, 0.35, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )
        self._target_health = OnscreenText(
            text="",
            parent=self._target_panel,
            pos=(0, -0.04),
            scale=0.032,
            fg=(0.95, 0.95, 0.95, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )
        DirectFrame(
            parent=self._target_panel,
            frameColor=(0.08, 0.08, 0.08, 1),
            frameSize=(-0.19, 0.19, -0.095, -0.065),
        )
        self._target_fill = DirectFrame(
            parent=self._target_panel,
            frameColor=(0.78, 0.18, 0.12, 1),
            frameSize=(-0.19, 0.19, -0.095, -0.065),
        )
        self._target_panel.hide()

    def refresh_target(self, name, health, max_health):
        ratio = 0.0 if max_health <= 0 else max(0.0, min(1.0, health / max_health))
        right = -0.19 + 0.38 * ratio
        self._target_fill["frameSize"] = (-0.19, max(-0.19, right), -0.095, -0.065)
        self._target_name.setText(name)
        self._target_health.setText(f"{int(math.ceil(health))}/{max_health}")
        self._target_panel.show()

    def clear_target(self):
        self._target_name.setText("")
        self._target_health.setText("")
        self._target_panel.hide()

    def _build_range_indicators(self):
        self._range_panel = DirectFrame(
            frameColor=(0.08, 0.08, 0.08, 0.78),
            frameSize=(-0.22, 0.22, -0.06, 0.06),
            pos=(0, 0, -0.92),
        )
        self._melee_indicator = OnscreenText(
            text="Melee: --",
            parent=self._range_panel,
            pos=(-0.11, -0.015),
            scale=0.038,
            fg=(0.75, 0.75, 0.75, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )
        self._range_indicator = OnscreenText(
            text="Range: --",
            parent=self._range_panel,
            pos=(0.11, -0.015),
            scale=0.038,
            fg=(0.75, 0.75, 0.75, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )

    def refresh_range_indicators(self, melee_ok, ranged_ok):
        self._melee_indicator.setText("Melee: OK" if melee_ok else "Melee: Far")
        self._melee_indicator["fg"] = (0.35, 0.9, 0.35, 1) if melee_ok else (0.9, 0.35, 0.35, 1)
        self._range_indicator.setText("Range: OK" if ranged_ok else "Range: Far")
        self._range_indicator["fg"] = (0.35, 0.9, 0.35, 1) if ranged_ok else (0.9, 0.35, 0.35, 1)

    def clear_range_indicators(self):
        self._melee_indicator.setText("Melee: --")
        self._melee_indicator["fg"] = (0.75, 0.75, 0.75, 1)
        self._range_indicator.setText("Range: --")
        self._range_indicator["fg"] = (0.75, 0.75, 0.75, 1)

    def _build_menu_buttons(self):
        self._menu_bar = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-0.4, 0.4, -0.05, 0.05),
            pos=(HUD_BUTTON_X, 0, HUD_BUTTON_Y),
        )
        buttons = [
            ("Inventory", 0.12, self.toggle_inventory),
            ("Equipment", 0.0, self.toggle_equipment),
            ("Skills", -0.12, self.toggle_skills),
        ]
        for text, z, command in buttons:
            DirectButton(
                parent=self._menu_bar,
                text=text,
                scale=0.045,
                pos=(0, 0, z),
                command=command,
                frameColor=(0.18, 0.18, 0.18, 0.95),
                text_fg=(1, 1, 1, 1),
            )

    def _build_inventory_window(self):
        self._inv_window = DraggableWindow("Inventory", (-0.03, 0.43, -0.78, 0.06), (0.55, 0, -0.34), self._close_inventory)
        body = self._inv_window.body
        OnscreenText(
            text="Drag items to move, swap, or equip.",
            parent=body,
            pos=(0.2, -0.04),
            scale=0.028,
            fg=(0.82, 0.82, 0.82, 1),
            align=TextNode.ACenter,
        )
        slot_defs = build_grid_slot_defs(INV_COLS, INV_ROWS, SLOT_SIZE, SLOT_GAP, 0.02, -0.12)
        self._inventory_slots = ItemSlotCollection(
            body,
            self.inventory,
            slot_defs,
            SLOT_SIZE,
            on_change=self._on_inventory_changed,
        )
        self._inv_window.hide()

    def _build_equipment_window(self):
        self._equip_window = DraggableWindow("Equipment", (-0.03, 0.38, -0.46, 0.06), (0.15, 0, -0.18), self._close_equipment)
        body = self._equip_window.body
        OnscreenText(
            text="Place matching equipment items here.",
            parent=body,
            pos=(0.17, -0.04),
            scale=0.028,
            fg=(0.82, 0.82, 0.82, 1),
            align=TextNode.ACenter,
        )
        slot_defs = build_equipment_slot_defs(SLOT_SIZE, 0.03, -0.14)
        self._equipment_slots = ItemSlotCollection(
            body,
            self.inventory.equipment,
            slot_defs,
            SLOT_SIZE,
            on_change=self._on_inventory_changed,
        )
        self._equip_window.hide()

    def _build_skill_window(self):
        self._skill_window = DraggableWindow("Skills", (0, 0.44, -0.48, 0.06), (-1.05, 0, -0.18), self._close_skills)
        body = self._skill_window.body
        self._skill_bars = {}
        for idx, skill in enumerate(SKILLS):
            y = -0.08 - idx * 0.12
            lbl = OnscreenText(
                text=f"{skill}  Lv 1",
                parent=body,
                pos=(0.01, y),
                scale=0.032,
                fg=(0.9, 0.9, 0.9, 1),
                align=TextNode.ALeft,
                mayChange=True,
            )
            DirectFrame(
                parent=body,
                frameColor=(0.1, 0.1, 0.1, 1),
                frameSize=(0, BAR_WIDTH, 0, BAR_HEIGHT),
                pos=(0.01, 0, y - 0.045),
            )
            bar_fill = DirectFrame(
                parent=body,
                frameColor=(0.2, 0.7, 0.2, 1),
                frameSize=(0, 0.001, 0, BAR_HEIGHT),
                pos=(0.01, 0, y - 0.045),
            )
            self._skill_bars[skill] = (lbl, bar_fill)
        self.refresh_skills()
        self._skill_window.hide()

    def refresh_inventory(self):
        self._inventory_slots.refresh()
        self._equipment_slots.refresh()

    def _on_inventory_changed(self):
        self.refresh_inventory()

    def refresh_skills(self):
        for skill, (label, bar_fill) in self._skill_bars.items():
            level = self.skills.get_level(skill)
            xp_in, xp_max = self.skills.get_xp_progress(skill)
            label.setText(f"{skill}  Lv {level}")
            fill_w = BAR_WIDTH * (xp_in / xp_max)
            bar_fill["frameSize"] = (0, max(0.001, fill_w), 0, BAR_HEIGHT)

    def is_any_window_open(self):
        return self._inv_visible or self._skill_visible or self._equip_visible

    def toggle_inventory(self):
        self._set_inventory_visible(not self._inv_visible)

    def toggle_equipment(self):
        self._set_equipment_visible(not self._equip_visible)

    def toggle_skills(self):
        self._set_skills_visible(not self._skill_visible)

    def _close_inventory(self):
        self._set_inventory_visible(False)

    def _close_equipment(self):
        self._set_equipment_visible(False)

    def _close_skills(self):
        self._set_skills_visible(False)

    def _set_inventory_visible(self, visible):
        self._inv_visible = visible
        if visible:
            self.refresh_inventory()
            self._inv_window.show()
        else:
            self._inv_window.hide()

    def _set_equipment_visible(self, visible):
        self._equip_visible = visible
        if visible:
            self.refresh_inventory()
            self._equip_window.show()
        else:
            self._equip_window.hide()

    def _set_skills_visible(self, visible):
        self._skill_visible = visible
        if visible:
            self.refresh_skills()
            self._skill_window.show()
        else:
            self._skill_window.hide()
