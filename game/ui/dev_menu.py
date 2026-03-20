"""Ursina-native developer tools window."""

import math

from ursina import Text as UText, color

from game.entities.creatures import CREATURE_DEFS, Creature
from game.services.vendor import Vendor
from game.systems.balance import COMBAT_SKILLS, recommended_combat_preset
from game.systems.inventory import ITEMS
from game.ui.ursina_widgets import FlatButton, UiWindow


TAB_PROGRESSION = "Progression"
TAB_SPAWNS = "Spawns"
TAB_ITEMS = "Items"
TAB_UTILITIES = "Utilities"
TAB_ORDER = [TAB_PROGRESSION, TAB_SPAWNS, TAB_ITEMS, TAB_UTILITIES]

PANEL = color.rgba32(18, 26, 38)
PANEL_ALT = color.rgba32(26, 36, 52)
TEXT = color.rgba32(235, 242, 255)
TEXT_DIM = color.rgba32(170, 186, 210)
ACCENT = color.rgba32(255, 220, 90)
BTN = color.rgba32(44, 66, 94)
BTN_HI = color.rgba32(62, 88, 120)
BTN_PRESS = color.rgba32(34, 50, 72)
GOOD = color.rgba32(52, 166, 92)
BAD = color.rgba32(182, 72, 72)


class DevMenu:
    def __init__(self, app):
        self.app = app
        self._visible = False
        self._active_tab = TAB_PROGRESSION

        self._spawn_creature_id = "scout"
        self._spawn_role_override = None
        self._spawn_level = 1

        self._item_category_filter = "All"
        self._item_subtype_filter = "All"
        self._item_entries = sorted(ITEMS.items(), key=lambda x: x[1].get("name", x[0]))
        self._item_index = 0

        self._categories = ["All"] + sorted({item_def.get("category", "unknown") for item_def in ITEMS.values()})
        self._subtypes = ["All"] + sorted({item_def.get("subtype", "unknown") for item_def in ITEMS.values()})

        self._window = None
        self._tab_buttons = {}
        self._tab_roots = {}
        self._build_ui()

    def _build_ui(self):
        self._window = UiWindow(
            title="Developer Tools",
            parent=self.app.hud._ui_layer if hasattr(self.app, "hud") else None,
            position=(0.0, 0.0, 0),
            scale=(0.96, 0.84),
            panel_color=PANEL,
            header_color=PANEL_ALT,
            close_callback=self.hide,
        )
        body = self._window.content

        x = -0.30
        for tab in TAB_ORDER:
            button = FlatButton(
                parent=body,
                text=tab,
                position=(x, 0.31, -0.02),
                scale=(0.18, 0.05),
                color_value=BTN,
                highlight_color=BTN_HI,
                pressed_color=BTN_PRESS,
                text_color=TEXT,
                text_scale=0.7,
                on_click=lambda value=tab: self._show_tab(value),
            )
            self._tab_buttons[tab] = button
            x += 0.21

        self._tab_roots = {tab: self._make_tab_root(body) for tab in TAB_ORDER}
        self._build_progression_tab(self._tab_roots[TAB_PROGRESSION])
        self._build_spawns_tab(self._tab_roots[TAB_SPAWNS])
        self._build_items_tab(self._tab_roots[TAB_ITEMS])
        self._build_utilities_tab(self._tab_roots[TAB_UTILITIES])
        self._show_tab(TAB_PROGRESSION)
        self._window.hide()

    def _make_tab_root(self, parent):
        from ursina import Entity
        return Entity(parent=parent, position=(0, 0, -0.02))

    def _label(self, parent, text, pos, *, scale=0.62, tint=TEXT, origin=(-0.5, 0.5)):
        return UText(parent=parent, text=text, origin=origin, position=(pos[0], pos[1], -0.02), scale=scale, color=tint)

    def _button(self, parent, text, pos, cb, *, scale=(0.18, 0.045), tint=BTN, text_scale=0.65):
        return FlatButton(
            parent=parent,
            text=text,
            position=(pos[0], pos[1], -0.02),
            scale=scale,
            color_value=tint,
            highlight_color=BTN_HI,
            pressed_color=BTN_PRESS if tint == BTN else tint.tint(-0.1),
            text_color=TEXT,
            text_scale=text_scale,
            on_click=cb,
        )

    def is_visible(self):
        return self._visible

    def toggle(self):
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self):
        self._visible = True
        self.refresh()
        self._window.show()
        self.app.hud.show_prompt("Dev Menu Open")

    def hide(self):
        self._visible = False
        self._window.hide()
        self.app.hud.show_prompt("Dev Menu Closed")

    def refresh(self):
        self._refresh_progression()
        self._refresh_spawn_text()
        self._refresh_item_text()
        self._refresh_utility_text()

    def _show_tab(self, tab):
        self._active_tab = tab
        for name, root in self._tab_roots.items():
            root.enabled = name == tab
        for name, button in self._tab_buttons.items():
            active = name == tab
            tint = GOOD if active else BTN
            button.base_color = tint
            button.color = tint
            button.setColorScale(tint)

    def _build_progression_tab(self, root):
        self._prog_summary = self._label(root, "", (-0.40, 0.22), scale=0.78, tint=ACCENT)
        self._button(root, "Melee 5", (-0.38, 0.12), lambda: self._apply_preset(5, "Melee"))
        self._button(root, "Melee 10", (-0.16, 0.12), lambda: self._apply_preset(10, "Melee"))
        self._button(root, "Ranged 10", (0.06, 0.12), lambda: self._apply_preset(10, "Ranged"))
        self._button(root, "Magic 10", (0.28, 0.12), lambda: self._apply_preset(10, "Magic"))
        self._button(root, "All 5", (-0.38, 0.05), lambda: self._set_all_combat_levels(5))
        self._button(root, "Reset Combat", (-0.16, 0.05), self._reset_combat_skills, scale=(0.21, 0.045), tint=BAD)

        self._skill_value_labels = {}
        y = -0.02
        for skill in COMBAT_SKILLS:
            self._label(root, skill, (-0.40, y), scale=0.58)
            value = self._label(root, "1", (-0.16, y), scale=0.58, tint=ACCENT)
            self._skill_value_labels[skill] = value
            self._button(root, "-", (-0.02, y - 0.005), lambda s=skill: self._adjust_skill_level(s, -1), scale=(0.05, 0.04), text_scale=0.8)
            self._button(root, "+", (0.06, y - 0.005), lambda s=skill: self._adjust_skill_level(s, 1), scale=(0.05, 0.04), text_scale=0.8)
            self._button(root, "Set 10", (0.19, y - 0.005), lambda s=skill: self._set_skill_level(s, 10), scale=(0.13, 0.04), text_scale=0.55)
            y -= 0.07

    def _refresh_progression(self):
        self._prog_summary.text = (
            f"Combat Level {self.app.skills.get_combat_level()}\n"
            f"Melee {self.app.skills.get_level('Melee')} | "
            f"Ranged {self.app.skills.get_level('Ranged')} | "
            f"Magic {self.app.skills.get_level('Magic')} | "
            f"Defense {self.app.skills.get_level('Defense')}"
        )
        for skill, label in self._skill_value_labels.items():
            label.text = str(self.app.skills.get_level(skill))

    def _build_spawns_tab(self, root):
        self._spawn_summary = self._label(root, "", (-0.40, 0.24), scale=0.66, tint=ACCENT)
        self._button(root, "Spawn Even", (-0.38, 0.14), lambda: self._spawn_benchmark(0))
        self._button(root, "Spawn +3", (-0.16, 0.14), lambda: self._spawn_benchmark(3))
        self._button(root, "Spawn -3", (0.06, 0.14), lambda: self._spawn_benchmark(-3))
        self._button(root, "Remove Selected", (0.31, 0.14), self._remove_selected_entity, scale=(0.22, 0.045), tint=BAD)

        self._spawn_creature_text = self._label(root, "", (-0.40, 0.02), scale=0.62)
        self._button(root, "Prev", (-0.10, 0.01), lambda: self._cycle_creature(-1), scale=(0.08, 0.04), text_scale=0.6)
        self._button(root, "Next", (0.00, 0.01), lambda: self._cycle_creature(1), scale=(0.08, 0.04), text_scale=0.6)

        self._spawn_role_text = self._label(root, "", (-0.40, -0.06), scale=0.62)
        self._button(root, "Prev", (-0.10, -0.07), lambda: self._cycle_role(-1), scale=(0.08, 0.04), text_scale=0.6)
        self._button(root, "Next", (0.00, -0.07), lambda: self._cycle_role(1), scale=(0.08, 0.04), text_scale=0.6)

        self._spawn_level_text = self._label(root, "", (-0.40, -0.14), scale=0.62)
        self._button(root, "Lower", (-0.10, -0.15), lambda: self._adjust_spawn_level(-1), scale=(0.08, 0.04), text_scale=0.54)
        self._button(root, "Raise", (0.00, -0.15), lambda: self._adjust_spawn_level(1), scale=(0.08, 0.04), text_scale=0.54)

        self._button(root, "Spawn Entity", (-0.22, -0.26), self._spawn_custom, scale=(0.22, 0.05), tint=GOOD)

    def _refresh_spawn_text(self):
        role_text = self._spawn_role_override or "Default"
        self._spawn_summary.text = "Benchmark and custom spawns"
        self._spawn_creature_text.text = f"Creature: {self._spawn_creature_id.title()}"
        self._spawn_role_text.text = f"Role: {role_text}"
        self._spawn_level_text.text = f"Level: {self._spawn_level}"

    def _build_items_tab(self, root):
        self._item_summary = self._label(root, "", (-0.40, 0.24), scale=0.66, tint=ACCENT)
        self._item_name_text = self._label(root, "", (-0.40, 0.12), scale=0.64)
        self._item_meta_text = self._label(root, "", (-0.40, 0.05), scale=0.54, tint=TEXT_DIM)
        self._button(root, "Prev", (-0.10, 0.11), lambda: self._cycle_item(-1), scale=(0.08, 0.04), text_scale=0.6)
        self._button(root, "Next", (0.00, 0.11), lambda: self._cycle_item(1), scale=(0.08, 0.04), text_scale=0.6)
        self._button(root, "Spawn Item", (-0.20, -0.02), self._spawn_selected_item, scale=(0.20, 0.05), tint=GOOD)
        self._button(root, "+1000 Gold", (0.05, -0.02), self._add_gold, scale=(0.20, 0.05))

    def _refresh_item_text(self):
        item_id, item_def = self._item_entries[self._item_index]
        self._item_summary.text = "Item spawner"
        self._item_name_text.text = item_def.get("name", item_id)
        self._item_meta_text.text = f"{item_id}\n{item_def.get('category', 'unknown')} / {item_def.get('subtype', 'unknown')}"

    def _build_utilities_tab(self, root):
        self._utility_summary = self._label(root, "", (-0.40, 0.24), scale=0.66, tint=ACCENT)
        self._button(root, "Heal Full", (-0.30, 0.14), self._heal_player, scale=(0.18, 0.05), tint=GOOD)
        self._button(root, "Toggle Combat Debug", (-0.04, 0.14), self.app.hud.toggle_combat_debug, scale=(0.28, 0.05))
        self._button(root, "Spawn Vendor", (-0.30, 0.06), lambda: self._spawn_entity(Vendor), scale=(0.18, 0.05))
        self._button(root, "Save Game", (-0.04, 0.06), self._save_game, scale=(0.18, 0.05))

    def _refresh_utility_text(self):
        self._utility_summary.text = "Utility actions"

    def _cycle_creature(self, direction):
        ids = sorted(CREATURE_DEFS.keys())
        idx = ids.index(self._spawn_creature_id)
        self._spawn_creature_id = ids[(idx + direction) % len(ids)]
        self._refresh_spawn_text()

    def _cycle_role(self, direction):
        roles = [None, "critter", "normal", "elite", "boss"]
        idx = roles.index(self._spawn_role_override)
        self._spawn_role_override = roles[(idx + direction) % len(roles)]
        self._refresh_spawn_text()

    def _adjust_spawn_level(self, delta):
        self._spawn_level = max(1, self._spawn_level + delta)
        self._refresh_spawn_text()

    def _cycle_item(self, direction):
        self._item_index = (self._item_index + direction) % len(self._item_entries)
        self._refresh_item_text()

    def _spawn_selected_item(self):
        item_id, _ = self._item_entries[self._item_index]
        self._spawn_item(item_id)

    def _spawn_item(self, item_id):
        if self.app.player.inventory.add_item(item_id, 1):
            self.app.hud.refresh_inventory()
            self.app.hud.show_prompt(f"Spawned 1 {item_id}")
        else:
            self.app.hud.show_prompt("Inventory Full!")

    def _spawn_entity(self, target, level=None, role=None):
        active_level = self.app._active_level
        if active_level is None:
            return None

        pos = self.app.player.get_pos()
        heading_rad = math.radians(self.app.player.char_np.getH())
        offset = Vec3(-math.sin(heading_rad) * 5, math.cos(heading_rad) * 5, 0)
        spawn_pos = pos + offset

        if target == Vendor:
            entity = target(self.app.render, self.app.bullet_world, spawn_pos, self.app.player.inventory)
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

    def _spawn_custom(self):
        self._spawn_entity(self._spawn_creature_id, level=self._spawn_level, role=self._spawn_role_override)

    def _spawn_benchmark(self, offset):
        target_level = max(1, self.app.skills.get_combat_level() + offset)
        creature_id = self._closest_creature_for_level(target_level)
        if creature_id:
            self._heal_player()
            entity = self._spawn_entity(creature_id)
            if entity and hasattr(self.app, "start_benchmark"):
                self.app.start_benchmark(entity, target_level)
                self.app.selection_manager.set_selected_target(entity)

    def _closest_creature_for_level(self, level):
        best_id, best_delta = None, None
        for cid, data in CREATURE_DEFS.items():
            delta = abs(int(data.get("level", 1)) - level)
            if best_delta is None or delta < best_delta:
                best_id, best_delta = cid, delta
        return best_id

    def _remove_selected_entity(self):
        target = self.app.selection_manager.selected_target
        if not target:
            return
        active_level = self.app._active_level
        if not active_level:
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

    def _heal_player(self):
        self.app.player.heal_full()
        self.app.hud.show_prompt("Player Healed")

    def _add_gold(self):
        self.app.player.inventory.add_item("gold", 1000)
        self.app.hud.refresh_inventory()
        self.app.hud.show_prompt("Added 1000 gold")

    def _save_game(self):
        if hasattr(self.app, "_save_current_game"):
            self.app._save_current_game()

    def _set_skill_level(self, skill, level):
        self.app.skills.set_level(skill, level)
        self.app.player.stats.recalculate()
        self.app.player.heal_full()
        self.app.hud.refresh_skills()
        self.app.hud.refresh_inventory()
        self.refresh()

    def _adjust_skill_level(self, skill, delta):
        self._set_skill_level(skill, max(1, self.app.skills.get_level(skill) + delta))

    def _set_all_combat_levels(self, level):
        self.app.skills.set_levels({skill: level for skill in COMBAT_SKILLS})
        self.app.player.stats.recalculate()
        self.app.player.heal_full()
        self.app.hud.refresh_skills()
        self.app.hud.refresh_inventory()
        self.refresh()

    def _apply_preset(self, level, style):
        self.app.skills.set_levels(recommended_combat_preset(level, style))
        self.app.player.stats.recalculate()
        self.app.player.heal_full()
        self.app.hud.refresh_skills()
        self.app.hud.refresh_inventory()
        self.refresh()

    def _reset_combat_skills(self):
        self.app.skills.reset_combat_skills()
        self.app.player.stats.recalculate()
        self.app.player.heal_full()
        self.app.hud.refresh_skills()
        self.refresh()
