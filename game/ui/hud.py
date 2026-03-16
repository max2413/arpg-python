"""HUD panels, prompts, and draggable inventory windows."""

import math

from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText, DirectScrolledFrame
from direct.gui import DirectGuiGlobals as DGG
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
MENU_BTN_WIDTH = 0.18
MENU_BTN_HEIGHT = 0.06
ACTION_BAR_Y = -0.88


class HUD:
    def __init__(self, inventory, skills, player=None):
        self.inventory = inventory
        self.skills = skills
        self.player = player
        self._prompt_msg = ""
        self._inv_visible = False
        self._skill_visible = False
        self._equip_visible = False
        self._inventory_slots = None
        self._equipment_slots = None
        self._skill_bars = {}
        self._stat_labels = {}
        self._quest_labels = []

        self._build_prompt()
        self._build_player_panel()
        self._build_target_panel()
        self._build_action_bar()
        self._build_menu_buttons()
        self._build_quest_tracker()
        self._build_inventory_window()
        self._build_equipment_window()
        self._build_skill_window()

    def _build_prompt(self):
        self._prompt_text = OnscreenText(
            text="",
            pos=(0, 0.6),
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

    def _build_player_panel(self):
        # Positioned at top-left
        self._player_panel = DirectFrame(
            frameColor=(0.1, 0.1, 0.1, 0.85),
            frameSize=(0, 0.45, -0.12, 0.02),
            pos=(-1.28, 0, 0.92),
        )
        self._player_name = OnscreenText(
            text="Player",
            parent=self._player_panel,
            pos=(0.02, -0.04),
            scale=0.04,
            fg=(1, 1, 1, 1),
            align=TextNode.ALeft,
        )
        # HP Bar Fill
        self._health_fill = DirectFrame(
            parent=self._player_panel,
            frameColor=(0.8, 0.1, 0.1, 1),
            frameSize=(0.02, 0.43, -0.1, -0.06),
        )
        self._health_label = OnscreenText(
            text="HP 100/100",
            parent=self._player_panel,
            pos=(0.22, -0.095),
            scale=0.03,
            fg=(1, 1, 1, 1),
            align=TextNode.ACenter,
            mayChange=True,
            sort=1,
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
        fill_w = 0.41 * ratio
        self._health_fill["frameSize"] = (0.02, 0.02 + fill_w, -0.1, -0.06)
        self._health_label.setText(f"{int(math.ceil(health))}/{int(max_health)}")

    def show_death(self, respawn_time):
        self._death_text.setText(f"You died\nRespawning in {respawn_time:.1f}s")

    def clear_death(self):
        self._death_text.setText("")

    def _build_target_panel(self):
        # Symmetrical to player panel, at top-right
        self._target_panel = DirectFrame(
            frameColor=(0.1, 0.1, 0.1, 0.85),
            frameSize=(-0.45, 0, -0.12, 0.02),
            pos=(1.28, 0, 0.92),
        )
        self._target_name = OnscreenText(
            text="",
            parent=self._target_panel,
            pos=(-0.02, -0.04),
            scale=0.04,
            fg=(1, 0.85, 0.3, 1),
            align=TextNode.ARight,
            mayChange=True,
        )
        # Target HP Bar Fill
        self._target_health_fill = DirectFrame(
            parent=self._target_panel,
            frameColor=(0.8, 0.1, 0.1, 1),
            frameSize=(-0.43, -0.02, -0.1, -0.06),
        )
        self._target_health_label = OnscreenText(
            text="0/0",
            parent=self._target_panel,
            pos=(-0.22, -0.095),
            scale=0.03,
            fg=(1, 1, 1, 1),
            align=TextNode.ACenter,
            mayChange=True,
            sort=1,
        )
        self._target_panel.hide()

    def refresh_target(self, name, health, max_health):
        self._target_panel.show()
        self._target_name.setText(name)
        ratio = 0.0 if max_health <= 0 else max(0.0, min(1.0, health / max_health))
        fill_w = 0.41 * ratio
        # Fill from left to right for consistency
        self._target_health_fill["frameSize"] = (-0.43, -0.43 + fill_w, -0.1, -0.06)
        self._target_health_label.setText(f"{int(math.ceil(health))}/{int(max_health)}")

    def clear_target(self):
        self._target_panel.hide()

    def _build_action_bar(self):
        # Bottom center action bar area
        self._action_bar = DirectFrame(
            frameColor=(0.05, 0.05, 0.05, 0.7),
            frameSize=(-0.4, 0.4, -0.08, 0.08),
            pos=(0, 0, ACTION_BAR_Y)
        )
        
        # Ranges
        self._melee_range_bg = DirectFrame(
            parent=self._action_bar,
            text="1", text_scale=0.05, text_pos=(0, -0.015), text_fg=(1,1,1,1),
            frameColor=(0.2, 0.2, 0.2, 1),
            frameSize=(-0.06, 0.06, -0.06, 0.06),
            pos=(-0.1, 0, 0)
        )
        OnscreenText(text="Melee", parent=self._melee_range_bg, pos=(0, -0.09), scale=0.025, fg=(0.8,0.8,0.8,1))
        
        self._ranged_range_bg = DirectFrame(
            parent=self._action_bar,
            text="2", text_scale=0.05, text_pos=(0, -0.015), text_fg=(1,1,1,1),
            frameColor=(0.2, 0.2, 0.2, 1),
            frameSize=(-0.06, 0.06, -0.06, 0.06),
            pos=(0.1, 0, 0)
        )
        OnscreenText(text="Ranged", parent=self._ranged_range_bg, pos=(0, -0.09), scale=0.025, fg=(0.8,0.8,0.8,1))

    def refresh_range_indicators(self, melee_in, ranged_in):
        self._melee_range_bg["frameColor"] = (0.2, 0.6, 0.2, 1) if melee_in else (0.6, 0.2, 0.2, 1)
        self._ranged_range_bg["frameColor"] = (0.2, 0.6, 0.2, 1) if ranged_in else (0.6, 0.2, 0.2, 1)

    def clear_range_indicators(self):
        self._melee_range_bg["frameColor"] = (0.2, 0.2, 0.2, 1)
        self._ranged_range_bg["frameColor"] = (0.2, 0.2, 0.2, 1)

    def _build_menu_buttons(self):
        # Redesigned menu buttons at bottom right
        start_x = 0.65
        btn_y = -0.92
        spacing = 0.21
        
        self.menu_buttons = []
        buttons = [
            ("Inv (I)", self.toggle_inventory, (0.2, 0.3, 0.5, 1)),
            ("Equip (C)", self.toggle_equipment, (0.3, 0.5, 0.2, 1)),
            ("Skills (K)", self.toggle_skills, (0.5, 0.2, 0.2, 1)),
            ("Dev (F1)", self._on_dev_clicked, (0.4, 0.4, 0.4, 1)),
        ]
        
        for i, (text, cmd, color) in enumerate(buttons):
            btn = DirectButton(
                text=text,
                scale=0.045,
                pos=(start_x + i * spacing, 0, btn_y),
                frameSize=(-2.0, 2.0, -0.6, 1.2),
                frameColor=color,
                text_fg=(1, 1, 1, 1),
                command=cmd,
                relief=DGG.RAISED,
                borderWidth=(0.01, 0.01)
            )
            # Add simple hover effect
            btn.bind(DGG.ENTER, lambda e, b=btn: b.setColorScale(1.2, 1.2, 1.2, 1))
            btn.bind(DGG.EXIT, lambda e, b=btn: b.setColorScale(1, 1, 1, 1))
            self.menu_buttons.append(btn)

    def _on_dev_clicked(self):
        if hasattr(self.player, "_app") and self.player._app:
            self.player._app.dev_menu.toggle()

    def _build_quest_tracker(self):
        self._quest_panel = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(0, 0.5, -0.6, 0),
            pos=(-1.28, 0, 0.75)
        )
        self.refresh_quests()

    def refresh_quests(self):
        for lbl in self._quest_labels:
            lbl.destroy()
        self._quest_labels = []
        
        if not hasattr(self.player, "_app") or not self.player._app:
            return
        
        qm = self.player._app.quest_manager
        y = 0.0
        for quest in qm.active_quests:
            title = OnscreenText(
                text=quest.name,
                parent=self._quest_panel,
                pos=(0, y),
                scale=0.04,
                fg=(1, 0.8, 0.2, 1),
                align=TextNode.ALeft,
                shadow=(0,0,0,0.8)
            )
            self._quest_labels.append(title)
            y -= 0.05
            
            for obj in quest.objectives:
                color = (0.2, 1, 0.2, 1) if obj["count"] >= obj["target"] else (0.9, 0.9, 0.9, 1)
                obj_lbl = OnscreenText(
                    text=f"- {obj['text']}: {obj['count']}/{obj['target']}",
                    parent=self._quest_panel,
                    pos=(0.02, y),
                    scale=0.03,
                    fg=color,
                    align=TextNode.ALeft,
                    shadow=(0,0,0,0.8)
                )
                self._quest_labels.append(obj_lbl)
                y -= 0.04
            y -= 0.02

    def _build_inventory_window(self):
        self._inv_window = DraggableWindow("Inventory", (0, 0.44, -0.85, 0.06), (0.6, 0, -0.18), self._close_inventory)
        body = self._inv_window.body
        slot_defs = build_grid_slot_defs(INV_COLS, INV_ROWS, SLOT_SIZE, SLOT_GAP, 0.03, -0.08)
        self._inventory_slots = ItemSlotCollection(
            body,
            self.inventory,
            slot_defs,
            SLOT_SIZE,
            on_change=self._on_inventory_changed,
        )
        self._inv_window.hide()

    def _build_equipment_window(self):
        # Increased size to fit stats
        self._equip_window = DraggableWindow("Equipment", (-0.03, 0.72, -0.55, 0.06), (0.15, 0, -0.18), self._close_equipment)
        body = self._equip_window.body
        
        # Left side: Slots
        OnscreenText(
            text="Equipment",
            parent=body,
            pos=(0.17, -0.04),
            scale=0.032,
            fg=(1, 0.8, 0.2, 1),
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

        # Right side: Stats
        stat_start_x = 0.38
        OnscreenText(
            text="Combat Stats",
            parent=body,
            pos=(stat_start_x + 0.15, -0.04),
            scale=0.032,
            fg=(1, 0.8, 0.2, 1),
            align=TextNode.ACenter,
        )
        
        stats_to_show = [
            ("melee_damage", "Melee Dmg"),
            ("ranged_damage", "Ranged Dmg"),
            ("magic_damage", "Magic Dmg"),
            ("armor", "Armor"),
            ("accuracy", "Accuracy"),
            ("evasion", "Evasion"),
            ("crit_chance", "Crit %"),
            ("block_chance", "Block %"),
            ("parry_chance", "Parry %"),
        ]
        
        self._stat_labels = {}
        for i, (stat_key, label_text) in enumerate(stats_to_show):
            y = -0.12 - i * 0.045
            OnscreenText(
                text=label_text,
                parent=body,
                pos=(stat_start_x, y),
                scale=0.028,
                fg=(0.8, 0.8, 0.8, 1),
                align=TextNode.ALeft
            )
            val_lbl = OnscreenText(
                text="0",
                parent=body,
                pos=(stat_start_x + 0.3, y),
                scale=0.028,
                fg=(1, 1, 1, 1),
                align=TextNode.ARight,
                mayChange=True
            )
            self._stat_labels[stat_key] = val_lbl
            
        self._equip_window.hide()

    def refresh_stats(self):
        if not self.player or not hasattr(self.player, "stats"):
            return
            
        for stat_key, label in self._stat_labels.items():
            val = self.player.stats.get(stat_key)
            # Format percentages
            if stat_key.endswith("_chance") or stat_key == "evasion":
                text = f"{val*100:.1f}%"
            elif stat_key == "accuracy":
                text = f"{val:.2f}"
            else:
                text = f"{val:.1f}"
            label.setText(text)

    def _build_skill_window(self):
        # Increased height to fit more skills
        self._skill_window = DraggableWindow("Skills", (0, 0.44, -0.85, 0.06), (-1.05, 0, -0.18), self._close_skills)
        body = self._skill_window.body
        
        # Use a ScrolledFrame
        scroll = DirectScrolledFrame(
            parent=body,
            canvasSize=(0, 0.4, -len(SKILLS) * 0.12 - 0.05, 0),
            frameSize=(0.01, 0.43, -0.8, 0),
            frameColor=(0, 0, 0, 0),
            scrollBarWidth=0.03,
            pos=(0, 0, -0.02)
        )
        canvas = scroll.getCanvas()
        
        self._skill_bars = {}
        for idx, skill in enumerate(SKILLS):
            y = -0.06 - idx * 0.12
            lbl = OnscreenText(
                text=f"{skill}  Lv 1",
                parent=canvas,
                pos=(0.01, y),
                scale=0.032,
                fg=(0.9, 0.9, 0.9, 1),
                align=TextNode.ALeft,
                mayChange=True,
            )
            DirectFrame(
                parent=canvas,
                frameColor=(0.1, 0.1, 0.1, 1),
                frameSize=(0, BAR_WIDTH, 0, BAR_HEIGHT),
                pos=(0.01, 0, y - 0.045),
            )
            bar_fill = DirectFrame(
                parent=canvas,
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
        self.refresh_stats()

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
            self.refresh_stats()
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

    def _build_range_indicators(self):
        # Deprecated in favor of action bar
        pass
