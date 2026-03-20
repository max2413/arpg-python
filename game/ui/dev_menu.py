"""
dev_menu.py - Tabbed developer tools for spawning, tuning, and cleanup.
"""

import math

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import (
    DirectButton,
    DirectEntry,
    DirectFrame,
    DirectOptionMenu,
    DirectScrolledFrame,
    OnscreenText,
)
from panda3d.core import TextNode, Vec3

from game.entities.creatures import CREATURE_DEFS, Creature
from game.services.vendor import Vendor
from game.systems.balance import COMBAT_SKILLS, recommended_combat_preset
from game.systems.inventory import ITEMS
from game.ui.widgets import DraggableWindow, create_item_icon, create_text_button


class DevMenu(DraggableWindow):
    TAB_NAMES = ("Progression", "Spawns", "Items", "Utilities")
    TAB_Y = 0.64
    CONTENT_TOP = 0.52
    CONTENT_BOTTOM = -0.76

    def __init__(self, app):
        self.app = app
        self._tab_frames = {}
        self._tab_buttons = {}
        self._active_tab = None
        self._player_summary_label = None

        # Custom spawn state
        self._spawn_creature_id = "scout"
        self._spawn_role_override = None
        self._spawn_level = 1
        self._spawn_creature_btns = {}
        self._spawn_role_btns = {}
        self._level_entry = None
        self._item_category_filter = "All"
        self._item_subtype_filter = "All"
        self._item_search = ""
        self._item_scroll = None
        self._item_canvas = None
        self._item_widgets = []
        self._item_search_entry = None
        self._item_category_menu = None
        self._item_subtype_menu = None

        super().__init__(
            "Developer Menu (F1)",
            frame_size=(-0.8, 0.8, -0.84, 0.84),
            pos=(0, 0, 0),
            close_command=self.hide,
        )
        self._build_content()
        self.hide()

    def _build_content(self):
        tab_x = -0.56
        for idx, name in enumerate(self.TAB_NAMES):
            btn = create_text_button(
                self.body,
                name,
                (tab_x + idx * 0.36, 0, self.TAB_Y),
                self._show_tab,
                scale=0.042,
                min_half_width=1.35,
                max_half_width=None,
                padding=0.45,
                frame_color=(0.24, 0.24, 0.26, 1),
                extra_args=[name],
            )
            self._tab_buttons[name] = btn

        for name in self.TAB_NAMES:
            frame = DirectFrame(
                parent=self.body,
                frameColor=(0.08, 0.08, 0.08, 0.95),
                frameSize=(-0.76, 0.76, self.CONTENT_BOTTOM, self.CONTENT_TOP),
                pos=(0, 0, 0),
            )
            frame.hide()
            self._tab_frames[name] = frame

        self._build_progression_tab(self._tab_frames["Progression"])
        self._build_spawns_tab(self._tab_frames["Spawns"])
        self._build_items_tab(self._tab_frames["Items"])
        self._build_utilities_tab(self._tab_frames["Utilities"])
        self._show_tab("Progression")

    def _build_progression_tab(self, parent):
        self._player_summary_label = OnscreenText(
            text="",
            parent=parent,
            pos=(-0.7, self.CONTENT_TOP - 0.08),
            scale=0.04,
            fg=(1, 0.9, 0.55, 1),
            align=TextNode.ALeft,
            mayChange=True,
        )

        preset_specs = [
            ("Melee 5", lambda: self._apply_preset(5, "Melee"), -0.62, self.CONTENT_TOP - 0.28),
            ("Melee 10", lambda: self._apply_preset(10, "Melee"), -0.24, self.CONTENT_TOP - 0.28),
            ("Ranged 10", lambda: self._apply_preset(10, "Ranged"), 0.14, self.CONTENT_TOP - 0.28),
            ("Magic 10", lambda: self._apply_preset(10, "Magic"), 0.52, self.CONTENT_TOP - 0.28),
            ("All 5", lambda: self._set_all_combat_levels(5), -0.62, self.CONTENT_TOP - 0.40),
            ("Reset", self._reset_combat_skills, -0.24, self.CONTENT_TOP - 0.40),
        ]
        for text, command, x, z in preset_specs:
            self._button(parent, text, x, z, command, width=2.4)

        for row, skill in enumerate(COMBAT_SKILLS):
            row_z = self.CONTENT_TOP - 0.58 - row * 0.15
            OnscreenText(
                text=skill,
                parent=parent,
                pos=(-0.7, row_z),
                scale=0.035,
                fg=(0.85, 0.85, 0.88, 1),
                align=TextNode.ALeft,
            )
            self._button(parent, "-", -0.2, row_z + 0.01, lambda s=skill: self._adjust_skill_level(s, -1), width=1.0)
            self._button(parent, "+", -0.04, row_z + 0.01, lambda s=skill: self._adjust_skill_level(s, 1), width=1.0)
            self._button(parent, "Set 10", 0.18, row_z + 0.01, lambda s=skill: self._set_skill_level(s, 10), width=1.6)

    def _build_spawns_tab(self, parent):
        OnscreenText(
            text="Benchmark Spawns",
            parent=parent,
            pos=(-0.7, self.CONTENT_TOP - 0.08),
            scale=0.045,
            fg=(1, 0.8, 0.2, 1),
            align=TextNode.ALeft,
        )
        self._button(parent, "Spawn Even", -0.56, self.CONTENT_TOP - 0.20, lambda: self._spawn_benchmark(0), width=2.4)
        self._button(parent, "Spawn +3", -0.18, self.CONTENT_TOP - 0.20, lambda: self._spawn_benchmark(3), width=2.1)
        self._button(parent, "Spawn -3", 0.16, self.CONTENT_TOP - 0.20, lambda: self._spawn_benchmark(-3), width=2.1)
        self._button(parent, "Remove Selected", 0.56, self.CONTENT_TOP - 0.20, self._remove_selected_entity, width=2.7)

        OnscreenText(
            text="Custom Spawner",
            parent=parent,
            pos=(-0.7, self.CONTENT_TOP - 0.36),
            scale=0.045,
            fg=(1, 0.8, 0.2, 1),
            align=TextNode.ALeft,
        )

        # Creature selection
        OnscreenText(
            text="Creature:",
            parent=parent,
            pos=(-0.7, self.CONTENT_TOP - 0.46),
            scale=0.035,
            fg=(0.85, 0.85, 0.88, 1),
            align=TextNode.ALeft,
        )

        creatures = sorted(CREATURE_DEFS.keys())
        for i, cid in enumerate(creatures):
            col = i % 4
            row = i // 4
            x = -0.45 + col * 0.32
            z = self.CONTENT_TOP - 0.46 - row * 0.10
            btn = self._button(parent, cid.title(), x, z, lambda c=cid: self._select_creature(c), width=2.5)
            self._spawn_creature_btns[cid] = btn

        # Role selection
        role_z = self.CONTENT_TOP - 0.72
        OnscreenText(
            text="Role Override:",
            parent=parent,
            pos=(-0.7, role_z),
            scale=0.035,
            fg=(0.85, 0.85, 0.88, 1),
            align=TextNode.ALeft,
        )

        roles = [(None, "None"), ("critter", "Critter"), ("normal", "Normal"), ("elite", "Elite"), ("boss", "Boss")]
        for i, (role_val, label) in enumerate(roles):
            x = -0.45 + i * 0.28
            btn = self._button(parent, label, x, role_z, lambda r=role_val: self._select_role(r), width=2.2)
            self._spawn_role_btns[role_val] = btn

        # Level selection
        level_z = role_z - 0.14
        OnscreenText(
            text="Level:",
            parent=parent,
            pos=(-0.7, level_z),
            scale=0.035,
            fg=(0.85, 0.85, 0.88, 1),
            align=TextNode.ALeft,
        )

        self._level_entry = DirectEntry(
            parent=parent,
            scale=0.04,
            pos=(-0.5, 0, level_z - 0.01),
            initialText="1",
            numLines=1,
            focus=0,
            frameColor=(0.15, 0.15, 0.15, 1),
            text_fg=(1, 1, 1, 1),
            width=4,
        )

        # Spawn button
        self._button(parent, "SPAWN ENTITY", 0.4, level_z, self._spawn_custom, width=4.0)

        # Update UI colors
        self._update_spawn_ui()

    def _build_items_tab(self, parent):
        categories = ["All"] + sorted({item_def.get("category", "unknown") for item_def in ITEMS.values()})
        subtypes = ["All"] + sorted({item_def.get("subtype", "unknown") for item_def in ITEMS.values()})

        OnscreenText(
            text="Category",
            parent=parent,
            pos=(-0.72, self.CONTENT_TOP - 0.08),
            scale=0.03,
            fg=(0.85, 0.85, 0.88, 1),
            align=TextNode.ALeft,
        )
        self._item_category_menu = DirectOptionMenu(
            parent=parent,
            items=categories,
            initialitem=0,
            scale=0.04,
            pos=(-0.56, 0, self.CONTENT_TOP - 0.10),
            command=self._set_item_category_filter,
            highlightColor=(0.30, 0.28, 0.18, 1),
            frameColor=(0.18, 0.18, 0.20, 1),
            text_fg=(1, 1, 1, 1),
            popupMarker_pos=(5.2, 0, 0.15),
        )

        OnscreenText(
            text="Subtype",
            parent=parent,
            pos=(-0.10, self.CONTENT_TOP - 0.08),
            scale=0.03,
            fg=(0.85, 0.85, 0.88, 1),
            align=TextNode.ALeft,
        )
        self._item_subtype_menu = DirectOptionMenu(
            parent=parent,
            items=subtypes,
            initialitem=0,
            scale=0.04,
            pos=(0.02, 0, self.CONTENT_TOP - 0.10),
            command=self._set_item_subtype_filter,
            highlightColor=(0.30, 0.28, 0.18, 1),
            frameColor=(0.18, 0.18, 0.20, 1),
            text_fg=(1, 1, 1, 1),
            popupMarker_pos=(5.2, 0, 0.15),
        )

        OnscreenText(
            text="Search",
            parent=parent,
            pos=(0.44, self.CONTENT_TOP - 0.08),
            scale=0.03,
            fg=(0.85, 0.85, 0.88, 1),
            align=TextNode.ALeft,
        )
        self._item_search_entry = DirectEntry(
            parent=parent,
            scale=0.038,
            pos=(0.53, 0, self.CONTENT_TOP - 0.11),
            initialText="",
            numLines=1,
            focus=0,
            frameColor=(0.15, 0.15, 0.15, 1),
            text_fg=(1, 1, 1, 1),
            width=8,
            command=self._set_item_search,
        )
        create_text_button(
            parent,
            "Apply",
            (0.67, 0, self.CONTENT_TOP - 0.10),
            self._apply_item_search,
            scale=0.034,
            min_half_width=1.0,
            max_half_width=None,
            padding=0.4,
            frame_color=(0.24, 0.32, 0.24, 1),
        )
        create_text_button(
            parent,
            "Reset",
            (0.67, 0, self.CONTENT_TOP - 0.18),
            self._reset_item_filters,
            scale=0.034,
            min_half_width=1.0,
            max_half_width=None,
            padding=0.4,
            frame_color=(0.28, 0.22, 0.22, 1),
        )

        self._item_scroll = DirectScrolledFrame(
            parent=parent,
            canvasSize=(-0.72, 0.72, -1.0, 0.0),
            frameSize=(-0.74, 0.74, self.CONTENT_BOTTOM + 0.04, self.CONTENT_TOP - 0.24),
            frameColor=(0.04, 0.04, 0.04, 0.65),
            scrollBarWidth=0.04,
            pos=(0, 0, -0.08),
        )
        self._item_canvas = self._item_scroll.getCanvas()
        self._refresh_items_tab()

    def _clear_items_tab(self):
        for widget in self._item_widgets:
            widget.destroy()
        self._item_widgets = []

    def _filtered_item_entries(self):
        search = self._item_search.strip().lower()
        entries = []
        for item_id, item_def in ITEMS.items():
            category = item_def.get("category", "unknown")
            subtype = item_def.get("subtype", "unknown")
            if self._item_category_filter != "All" and category != self._item_category_filter:
                continue
            if self._item_subtype_filter != "All" and subtype != self._item_subtype_filter:
                continue
            if search:
                haystack = " ".join(
                    [
                        item_id,
                        item_def.get("name", ""),
                        category,
                        subtype,
                        item_def.get("equipment_slot", ""),
                    ]
                ).lower()
                if search not in haystack:
                    continue
            entries.append((item_id, item_def))
        return sorted(
            entries,
            key=lambda pair: (
                pair[1].get("category", ""),
                pair[1].get("subtype", ""),
                pair[1].get("name", pair[0]),
            ),
        )

    def _refresh_items_tab(self):
        if self._item_canvas is None or self._item_scroll is None:
            return
        self._clear_items_tab()

        entries = self._filtered_item_entries()
        cols = 5
        slot_size = 0.16
        row_pitch = 0.27
        top_z = -0.10
        for i, (item_id, item_def) in enumerate(entries):
            col = i % cols
            row = i // cols
            x = -0.68 + col * 0.29
            z = top_z - row * row_pitch
            btn = DirectButton(
                parent=self._item_canvas,
                frameSize=(0, slot_size, -slot_size, 0),
                pos=(x, 0, z),
                frameColor=(0.2, 0.2, 0.2, 1),
                relief=DGG.FLAT,
                command=self._spawn_item,
                extraArgs=[item_id],
            )
            self._item_widgets.append(btn)
            icon_root = DirectFrame(
                parent=btn,
                frameColor=(0, 0, 0, 0),
                pos=(0.01, 0, -slot_size + 0.01),
                scale=slot_size - 0.02,
            )
            self._item_widgets.append(icon_root)
            create_item_icon(icon_root, item_def)
            self._item_widgets.append(OnscreenText(
                text=item_def.get("name", item_id),
                parent=btn,
                pos=(slot_size * 0.5, -slot_size - 0.03),
                scale=0.017,
                fg=(0.8, 0.8, 0.8, 1),
                align=TextNode.ACenter,
            ))
            meta = f"{item_def.get('category', '?')} / {item_def.get('subtype', '?')}"
            self._item_widgets.append(OnscreenText(
                text=meta,
                parent=btn,
                pos=(slot_size * 0.5, -slot_size - 0.075),
                scale=0.013,
                fg=(0.62, 0.64, 0.68, 1),
                align=TextNode.ACenter,
            ))

        if not entries:
            self._item_widgets.append(OnscreenText(
                text="No items match the current filters.",
                parent=self._item_canvas,
                pos=(0, -0.18),
                scale=0.04,
                fg=(0.68, 0.68, 0.72, 1),
                align=TextNode.ACenter,
            ))
            bottom = -0.6
        else:
            total_rows = (len(entries) + cols - 1) // cols
            bottom = min(-0.6, top_z - max(0, total_rows - 1) * row_pitch - 0.28)
        self._item_scroll["canvasSize"] = (-0.72, 0.72, bottom, 0.0)

    def _set_item_category_filter(self, value):
        self._item_category_filter = value
        self._refresh_items_tab()

    def _set_item_subtype_filter(self, value):
        self._item_subtype_filter = value
        self._refresh_items_tab()

    def _set_item_search(self, value):
        self._item_search = value
        self._refresh_items_tab()

    def _apply_item_search(self):
        if self._item_search_entry is not None:
            self._item_search = self._item_search_entry.get()
        self._refresh_items_tab()

    def _reset_item_filters(self):
        self._item_category_filter = "All"
        self._item_subtype_filter = "All"
        self._item_search = ""
        if self._item_category_menu is not None:
            self._item_category_menu.set("All")
        if self._item_subtype_menu is not None:
            self._item_subtype_menu.set("All")
        if self._item_search_entry is not None:
            self._item_search_entry.enterText("")
        self._refresh_items_tab()

    def _build_utilities_tab(self, parent):
        utility_specs = [
            ("Heal Full", self._heal_player, -0.5, -0.16, 2.5),
            ("+1000 Gold", self._add_gold, -0.08, -0.16, 2.5),
            ("Toggle Combat Debugger", self.app.hud.toggle_combat_debug, 0.44, -0.16, 4.0),
            ("Spawn Vendor", lambda: self._spawn_entity(Vendor), -0.5, -0.34, 2.5),
            ("Save Game", self._save_game, -0.08, -0.34, 2.5),
        ]
        for text, command, x, z, width in utility_specs:
            self._button(parent, text, x, z, command, width=width)

        OnscreenText(
            text="Use the Spawns tab to benchmark and remove selected entities.",
            parent=parent,
            pos=(-0.7, self.CONTENT_TOP - 0.48),
            scale=0.032,
            fg=(0.75, 0.76, 0.8, 1),
            align=TextNode.ALeft,
        )

    def _button(self, parent, text, x, z, command, width=2.0):
        return create_text_button(
            parent,
            text,
            (x, 0, z),
            command,
            scale=0.04,
            min_half_width=max(1.2, width * 0.6),
            max_half_width=None,
            padding=0.55,
            frame_color=(0.24, 0.24, 0.26, 1),
        )

    def _show_tab(self, name):
        self._active_tab = name
        for tab_name, frame in self._tab_frames.items():
            if tab_name == name:
                frame.show()
                self._tab_buttons[tab_name]["frameColor"] = (0.38, 0.34, 0.18, 1)
            else:
                frame.hide()
                self._tab_buttons[tab_name]["frameColor"] = (0.24, 0.24, 0.26, 1)
        self.refresh_player_summary()

    def toggle(self):
        if self.root.isHidden():
            self.refresh_player_summary()
            self.show()
            self.app.hud.show_prompt("Dev Menu Open")
        else:
            self.hide()

    def refresh_player_summary(self):
        if self._player_summary_label is None:
            return
        combat_level = self.app.skills.get_combat_level()
        self._player_summary_label.setText(
            f"Player Combat Level: {combat_level}\n"
            f"Melee {self.app.skills.get_level('Melee')}  "
            f"Ranged {self.app.skills.get_level('Ranged')}  "
            f"Magic {self.app.skills.get_level('Magic')}  "
            f"Defense {self.app.skills.get_level('Defense')}"
        )

    def _spawn_item(self, item_id):
        if self.app.player.inventory.add_item(item_id, 1):
            self.app.hud.refresh_inventory()
            self.app.hud.show_prompt(f"Spawned 1 {item_id}")
        else:
            self.app.hud.show_prompt("Inventory Full!")

    def _spawn_entity(self, target, level=None, role=None):
        active_level = self.app._active_level
        if active_level is None:
            self.app.hud.show_prompt("No active level!")
            return None

        pos = self.app.player.get_pos()
        heading_rad = math.radians(self.app.player.char_np.getH())
        offset = Vec3(-math.sin(heading_rad) * 5, math.cos(heading_rad) * 5, 0)
        spawn_pos = pos + offset

        if target == Vendor:
            entity = target(self.app.render, self.app.bullet_world, spawn_pos, self.app.player.inventory)
            entity._dev_spawned = True
            active_level.interactables.append(entity)
            name = "Vendor"
        else:
            entity = Creature(
                self.app.render,
                spawn_pos,
                creature_id=target,
                level=level,
                role=role,
                patrol_center=spawn_pos,
                terrain=self.app.player.terrain,
                bullet_world=self.app.bullet_world,
            )
            entity._dev_spawned = True
            entity._disable_respawn = True
            active_level.hostiles.append(entity)
            name = f"{entity.get_target_name()} Lv {entity.get_level()}"

        self.app.hud.show_prompt(f"Spawned {name}")
        return entity

    def _update_spawn_ui(self):
        # Update creature buttons
        for cid, btn in self._spawn_creature_btns.items():
            btn["frameColor"] = (0.38, 0.34, 0.18, 1) if cid == self._spawn_creature_id else (0.24, 0.24, 0.26, 1)
        
        # Update role buttons
        for role, btn in self._spawn_role_btns.items():
            btn["frameColor"] = (0.38, 0.34, 0.18, 1) if role == self._spawn_role_override else (0.24, 0.24, 0.26, 1)

    def _select_creature(self, creature_id):
        self._spawn_creature_id = creature_id
        self._update_spawn_ui()

    def _select_role(self, role):
        self._spawn_role_override = role
        self._update_spawn_ui()

    def _spawn_custom(self):
        try:
            level_str = self._level_entry.get()
            level = int(level_str)
        except ValueError:
            level = 1
        
        self._spawn_entity(self._spawn_creature_id, level=level, role=self._spawn_role_override)

    def _spawn_benchmark(self, offset):
        target_level = max(1, self.app.skills.get_combat_level() + offset)
        creature_id = self._closest_creature_for_level(target_level)
        if creature_id is None:
            self.app.hud.show_prompt("No creatures configured")
            return
        self._heal_player()
        entity = self._spawn_entity(creature_id)
        if entity is not None and hasattr(self.app, "start_benchmark"):
            self.app.start_benchmark(entity, target_level)
            self.app.selection_manager.set_selected_target(entity)
            self.app.hud.set_benchmark_summary(
                f"Benchmark running vs {entity.get_target_name()} Lv {entity.get_level()} "
                f"(target band {target_level})"
            )

    def _closest_creature_for_level(self, level):
        best_id = None
        best_delta = None
        for creature_id, data in CREATURE_DEFS.items():
            c_level = int(data.get("level", 1))
            delta = abs(c_level - level)
            if best_delta is None or delta < best_delta:
                best_id = creature_id
                best_delta = delta
        return best_id

    def _remove_selected_entity(self):
        target = self.app.selection_manager.selected_target
        if target is None:
            self.app.hud.show_prompt("No selected entity")
            return
        active_level = self.app._active_level
        if active_level is None:
            self.app.hud.show_prompt("No active level!")
            return
        self.app.selection_manager.set_selected_target(None)
        if target in active_level.hostiles:
            active_level.hostiles.remove(target)
        if target in active_level.interactables:
            active_level.interactables.remove(target)
        if hasattr(target, "remove_from_world"):
            target.remove_from_world(self.app.hud)
        elif hasattr(target, "close_ui"):
            target.close_ui()
        if hasattr(target, "destroy"):
            target.destroy()
        self.app.hud.show_prompt("Selected entity removed")

    def _heal_player(self):
        self.app.player.heal_full()
        self.app.hud.show_prompt("Player Healed")

    def _add_gold(self):
        self.app.player.inventory.add_item("gold", 1000)
        self.app.hud.refresh_inventory()
        self.app.hud.show_prompt("Added 1000 Gold")

    def _save_game(self):
        if hasattr(self.app, "_save_current_game"):
            self.app._save_current_game()

    def _set_skill_level(self, skill, level):
        self.app.skills.set_level(skill, level)
        self.app.player.stats.recalculate()
        self.app.player.heal_full()
        self.app.hud.refresh_skills()
        self.app.hud.refresh_inventory()
        self.refresh_player_summary()
        self.app.hud.show_prompt(f"{skill} set to {self.app.skills.get_level(skill)}")

    def _adjust_skill_level(self, skill, delta):
        current = self.app.skills.get_level(skill)
        self._set_skill_level(skill, max(1, current + delta))

    def _set_all_combat_levels(self, level):
        self.app.skills.set_levels({skill: level for skill in COMBAT_SKILLS})
        self.app.player.stats.recalculate()
        self.app.player.heal_full()
        self.app.hud.refresh_skills()
        self.app.hud.refresh_inventory()
        self.refresh_player_summary()
        self.app.hud.show_prompt(f"All combat skills set to {level}")

    def _apply_preset(self, level, style):
        preset = recommended_combat_preset(level, style)
        self.app.skills.set_levels(preset)
        self.app.player.stats.recalculate()
        self.app.player.heal_full()
        self.app.hud.refresh_skills()
        self.app.hud.refresh_inventory()
        self.refresh_player_summary()
        self.app.hud.show_prompt(f"{style} preset applied for combat level {level}")

    def _reset_combat_skills(self):
        self.app.skills.reset_combat_skills()
        self.app.player.stats.recalculate()
        self.app.player.heal_full()
        self.app.hud.refresh_skills()
        self.app.hud.refresh_inventory()
        self.refresh_player_summary()
        self.app.hud.show_prompt("Combat skills reset")
