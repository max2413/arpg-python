"""HUD panels, prompts, and draggable inventory windows."""

from datetime import datetime
import math
import game.services.crafting as crafting_svc

from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText, DirectScrolledFrame
from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import TextNode
from ursina import Entity, Text as UText, camera, color, destroy
from ursina.shaders.unlit_shader import unlit_shader

from game.systems.inventory import (
    EQUIPMENT_SLOTS,
    STAT_LABELS,
    build_item_tooltip,
    get_equipment_slot,
    get_item_def,
    get_item_name,
    move_item,
)
from game.systems.skills import SKILLS
from game.ui.widgets import (
    CONTEXT_MENU_MANAGER,
    DraggableWindow,
    ItemSlotCollection,
    QUANTITY_PROMPT_MANAGER,
    TOOLTIP_MANAGER,
    build_equipment_slot_defs,
    build_grid_slot_defs,
    create_text_button,
)
from game.ui.ursina_widgets import FlatButton, UiWindow


INV_COLS = 4
INV_ROWS = 7
SLOT_SIZE = 0.09
SLOT_GAP = 0.005
BAR_WIDTH = 0.3
BAR_HEIGHT = 0.04
ACTION_BAR_Y = -0.88
LOG_WINDOW_MAX = 200
PANEL_BG = (0.08, 0.09, 0.11, 0.88)
PANEL_BORDER = (0.18, 0.20, 0.24, 0.96)
HP_BG = (0.16, 0.05, 0.05, 1)
HP_FILL = (0.86, 0.10, 0.10, 1)
CAST_FILL = (0.82, 0.62, 0.18, 1)
READY_COLOR = (0.22, 0.56, 0.26, 1)
FAR_COLOR = (0.56, 0.20, 0.20, 1)
IDLE_COLOR = (0.20, 0.21, 0.24, 1)
DBG_PANEL = color.rgba32(26, 36, 52)
DBG_PANEL_ALT = color.rgba32(18, 26, 38)
DBG_BAR_BG = color.rgba32(70, 24, 24)
DBG_BAR_FILL = color.rgba32(214, 52, 52)
DBG_TEXT = color.rgba32(235, 242, 255)
DBG_TEXT_DIM = color.rgba32(170, 186, 210)
DBG_ACCENT = color.rgba32(255, 220, 90)
DBG_GOOD = color.rgba32(52, 166, 92)
DBG_BAD = color.rgba32(182, 72, 72)
DBG_MENU = color.rgba32(44, 66, 94)
DBG_MENU_HI = color.rgba32(62, 88, 120)
DBG_MENU_PRESS = color.rgba32(34, 50, 72)


class HUD:
    def __init__(self, inventory, skills, player=None, app=None):
        self.inventory = inventory
        self.skills = skills
        self.player = player
        self.app = app
        self._prompt_msg = ""
        self._inv_visible = False
        self._skill_visible = False
        self._equip_visible = False
        self._inventory_slots = None
        self._equipment_slots = None
        self._inventory_buttons = {}
        self._equipment_buttons = {}
        self._selected_inventory_slot = None
        self._selected_equipment_slot = None
        self._skill_bars = {}
        self._skill_meta_labels = {}
        self._stat_labels = {}
        self._quest_labels = []
        self._game_log_entries = []
        self._combat_log_entries = []
        self._game_log_visible = False
        self._combat_log_visible = False
        self._combat_debug_visible = False
        self._menu_popup_visible = False
        self._last_combat_event = None
        self._benchmark_summary = "No benchmark run yet."
        self._ui_root = self.app.aspect2d if self.app is not None else None

        self._build_prompt()
        self._build_player_panel()
        self._build_target_panel()
        self._build_action_bar()
        self._build_cast_bar()
        self._build_menu_buttons()
        self._build_ursina_overlay()
        self._build_quest_tracker()
        self._build_inventory_window()
        self._build_equipment_window()
        self._build_skill_window()
        self._build_game_log_window()
        self._build_combat_log_window()
        self._build_combat_debug_window()
        self._layout_screen_widgets()
        self.inventory.add_listener(self.refresh_inventory)

    def _build_ursina_overlay(self):
        self._ui_layer = Entity(parent=camera.ui, shader=unlit_shader, unlit=True)

        self._prompt_chip = Entity(parent=self._ui_layer, position=(0, 0.42, 0))
        self._make_ui_quad(parent=self._prompt_chip, color_value=DBG_PANEL, scale=(0.44, 0.055))
        self._prompt_chip_text = UText(parent=self._prompt_chip, text="", origin=(0, 0), position=(0, 0.01, -0.02), scale=1.15, color=DBG_ACCENT)
        self._prompt_chip.enabled = False

        self._player_card = self._build_status_card(position=(-0.66, 0.42), title="Player")
        self._target_card = self._build_status_card(position=(0.66, 0.42), title="")
        self._target_card["root"].enabled = False

        self._action_shell = Entity(parent=self._ui_layer, position=(0, -0.43, 0))
        self._make_ui_quad(parent=self._action_shell, color_value=DBG_PANEL_ALT, scale=(0.28, 0.105))
        self._action_title = UText(parent=self._action_shell, text="Combat Actions", origin=(0, 0), position=(0, 0.047, -0.02), scale=1.0, color=DBG_TEXT)
        self._melee_box = self._build_action_box(self._action_shell, (-0.07, 0.01), "1", "Melee")
        self._ranged_box = self._build_action_box(self._action_shell, (0.07, 0.01), "2", "Ranged")

        self._cast_shell = Entity(parent=self._ui_layer, position=(0, -0.34, 0))
        self._make_ui_quad(parent=self._cast_shell, color_value=DBG_PANEL_ALT, scale=(0.24, 0.05))
        self._cast_label = UText(parent=self._cast_shell, text="", origin=(0, 0), position=(0, 0.02, -0.02), scale=0.9, color=DBG_TEXT)
        self._cast_track = self._make_ui_quad(parent=self._cast_shell, color_value=DBG_BAR_BG, scale=(0.20, 0.012), y=-0.01)
        self._cast_fill = self._make_ui_quad(parent=self._cast_track, color_value=DBG_ACCENT, origin=(-0.5, 0), position=(-0.5, 0, 0), scale=(0, 1, 1))
        self._cast_shell.enabled = False

        self._death_overlay = UText(parent=self._ui_layer, text="", origin=(0, 0), position=(0, 0.1, -0.02), scale=2.0, color=DBG_BAD)

        self._quest_text = UText(parent=self._ui_layer, text="", origin=(-0.5, 0.5), position=(-0.86, 0.32, -0.02), scale=0.82, color=DBG_ACCENT)

        self._menu_button = self._make_ui_button(
            parent=self._ui_layer,
            text="Menu",
            scale=(0.11, 0.045),
            position=(0.77, 0.43, 0),
        )
        self._menu_button.on_click = self.toggle_menu_popup
        self._menu_popup_root = Entity(parent=self._ui_layer, enabled=False)
        self._menu_popup_panel = self._make_ui_quad(parent=self._menu_popup_root, color_value=DBG_PANEL, scale=(0.24, 0.28), position=(0.70, 0.24, 0))
        self._menu_popup_buttons = []
        for idx, (label, callback) in enumerate([
            ("Inventory", self.toggle_inventory),
            ("Equipment", self.toggle_equipment),
            ("Skills", self.toggle_skills),
            ("Game Log", self.toggle_game_log),
            ("Combat Log", self.toggle_combat_log),
            ("Combat Debug", self.toggle_combat_debug),
            ("Dev Menu", self._on_dev_clicked),
        ]):
            btn = self._make_ui_button(
                parent=self._menu_popup_root,
                text=label,
                scale=(0.18, 0.035),
                position=(0.70, 0.34 - idx * 0.045, -0.01),
                text_scale=0.9,
            )
            btn.on_click = lambda cb=callback: self._run_menu_command(cb)
            self._menu_popup_buttons.append(btn)

        self._destroy_legacy_shell()

    def _destroy_legacy_shell(self):
        for widget_name in ("_prompt_panel", "_player_panel", "_target_panel", "_action_bar", "_cast_bar_panel", "_quest_panel", "_menu_popup", "_menu_toggle"):
            widget = getattr(self, widget_name, None)
            if widget is None:
                continue
            try:
                widget.destroy()
            except Exception:
                try:
                    widget.hide()
                except Exception:
                    pass
            setattr(self, widget_name, None)

    def _build_status_card(self, position, title):
        root = Entity(parent=self._ui_layer, position=(position[0], position[1], 0))
        panel = self._make_ui_quad(parent=root, color_value=DBG_PANEL, scale=(0.29, 0.09))
        title_text = UText(parent=root, text=title, origin=(-0.5, 0.5), position=(-0.138, 0.030, -0.02), scale=1.0, color=DBG_TEXT)
        level_text = UText(parent=root, text="", origin=(0.5, 0.5), position=(0.138, 0.030, -0.02), scale=0.86, color=DBG_ACCENT)
        bar_bg = self._make_ui_quad(parent=root, color_value=DBG_BAR_BG, scale=(0.25, 0.018), position=(0, -0.014, 0))
        bar_fill = self._make_ui_quad(parent=bar_bg, color_value=DBG_BAR_FILL, origin=(-0.5, 0), position=(-0.5, 0, 0), scale=(1, 1, 1))
        value_text = UText(parent=root, text="", origin=(0, 0), position=(0, -0.024, -0.02), scale=0.8, color=DBG_TEXT)
        return {"root": root, "panel": panel, "title": title_text, "level": level_text, "bar_fill": bar_fill, "value": value_text}

    def _build_action_box(self, parent, position, hotkey, label):
        box = self._make_ui_quad(parent=parent, color_value=DBG_MENU, scale=(0.06, 0.06), position=(position[0], position[1], 0))
        key_text = UText(parent=parent, text=hotkey, origin=(0, 0), position=(position[0], position[1] - 0.007, -0.02), scale=1.35, color=DBG_TEXT)
        label_text = UText(parent=parent, text=label, origin=(0, 0), position=(position[0], -0.035, -0.02), scale=0.72, color=DBG_TEXT)
        state_text = UText(parent=parent, text="No target", origin=(0, 0), position=(position[0], -0.055, -0.02), scale=0.58, color=DBG_TEXT_DIM)
        return {"box": box, "key": key_text, "label": label_text, "state": state_text}

    def _make_ui_quad(self, parent, color_value, **kwargs):
        quad = Entity(
            parent=parent,
            model="quad",
            shader=unlit_shader,
            unlit=True,
            texture=None,
            color=color_value,
            **kwargs,
        )
        quad.color = color_value
        quad.setColorScale(color_value)
        quad.setLightOff(True)
        quad.clearTexture()
        return quad

    def _make_ui_button(self, parent, text, scale, position, text_scale=1.0):
        btn = FlatButton(
            parent=parent,
            text=text,
            scale=scale,
            position=position,
            color_value=DBG_MENU,
            highlight_color=DBG_MENU_HI,
            pressed_color=DBG_MENU_PRESS,
            text_color=DBG_TEXT,
            text_scale=text_scale,
        )
        btn.setColorScale(DBG_MENU)
        btn.setLightOff(True)
        btn.clearTexture()
        return btn

    def _screen_bounds(self):
        if self.app is None:
            return (-1.25, 1.25, 1.0, -1.0)
        left = getattr(self.app, "a2dLeft", -1.25)
        right = getattr(self.app, "a2dRight", 1.25)
        top = getattr(self.app, "a2dTop", 1.0)
        bottom = getattr(self.app, "a2dBottom", -1.0)
        return (left, right, top, bottom)

    def _layout_screen_widgets(self):
        left, right, top, bottom = self._screen_bounds()
        if self._prompt_panel is not None:
            self._prompt_panel.setPos(0, 0, top - 0.14)
        if self._player_panel is not None:
            self._player_panel.setPos(left + 0.06, 0, top - 0.07)
        if self._target_panel is not None:
            self._target_panel.setPos(right - 0.06, 0, top - 0.07)
        if self._action_bar is not None:
            self._action_bar.setPos(0, 0, bottom + 0.22)
        if self._cast_bar_panel is not None:
            self._cast_bar_panel.setPos(0, 0, bottom + 0.38)
        if self._quest_panel is not None:
            self._quest_panel.setPos(left + 0.06, 0, top - 0.28)
        if self._menu_toggle is not None:
            self._menu_toggle.setPos(right - 0.26, 0, top - 0.08)
        if self._menu_popup is not None:
            self._menu_popup.setPos(right - 0.36, 0, top - 0.18)

    def _build_prompt(self):
        self._prompt_panel = DirectFrame(
            parent=self._ui_root,
            frameColor=(0.04, 0.04, 0.05, 0.84),
            frameSize=(-0.46, 0.46, -0.05, 0.05),
            pos=(0, 0, 0),
        )
        self._prompt_text = OnscreenText(
            text="",
            parent=self._prompt_panel,
            pos=(0, 0.6),
            scale=0.05,
            fg=(1, 1, 0.3, 1),
            shadow=(0, 0, 0, 0.8),
            align=TextNode.ACenter,
            mayChange=True,
        )
        self._prompt_panel.hide()
        self._prompt_text.setPos(0, -0.018)

    def show_prompt(self, msg):
        self._prompt_msg = msg
        self._prompt_chip_text.text = msg
        self._prompt_chip.enabled = True

    def clear_prompt_if(self, msg):
        if self._prompt_msg == msg:
            self.clear_prompt()

    def clear_prompt(self):
        self._prompt_msg = ""
        self._prompt_chip_text.text = ""
        self._prompt_chip.enabled = False

    def _build_player_panel(self):
        self._player_panel = DirectFrame(
            parent=self._ui_root,
            frameColor=PANEL_BG,
            frameSize=(0, 0.52, -0.15, 0.03),
            pos=(0, 0, 0),
        )
        DirectFrame(
            parent=self._player_panel,
            frameColor=PANEL_BORDER,
            frameSize=(0, 0.52, -0.004, 0.03),
            relief=DGG.FLAT,
        )
        self._player_name = OnscreenText(
            text="Player",
            parent=self._player_panel,
            pos=(0.03, -0.048),
            scale=0.044,
            fg=(1, 1, 1, 1),
            align=TextNode.ALeft,
        )
        self._player_level = OnscreenText(
            text="CLv 1",
            parent=self._player_panel,
            pos=(0.47, -0.048),
            scale=0.034,
            fg=(0.85, 0.85, 0.55, 1),
            align=TextNode.ARight,
            mayChange=True,
        )
        DirectFrame(
            parent=self._player_panel,
            frameColor=HP_BG,
            frameSize=(0.03, 0.49, -0.125, -0.075),
            relief=DGG.FLAT,
        )
        self._health_fill = DirectFrame(
            parent=self._player_panel,
            frameColor=HP_FILL,
            frameSize=(0.03, 0.49, -0.125, -0.075),
            relief=DGG.FLAT,
        )
        self._health_label = OnscreenText(
            text="HP 100/100",
            parent=self._player_panel,
            pos=(0.26, -0.114),
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
        self._player_card["bar_fill"].scale_x = ratio
        self._player_card["value"].text = f"{int(math.ceil(health))}/{int(max_health)}"

    def refresh_player_level(self, combat_level):
        self._player_card["level"].text = f"CLv {int(combat_level)}"

    def show_death(self, respawn_time):
        self._death_overlay.text = f"You died\nRespawning in {respawn_time:.1f}s"

    def clear_death(self):
        self._death_overlay.text = ""

    def _build_target_panel(self):
        self._target_panel = DirectFrame(
            parent=self._ui_root,
            frameColor=PANEL_BG,
            frameSize=(-0.52, 0, -0.15, 0.03),
            pos=(0, 0, 0),
        )
        DirectFrame(
            parent=self._target_panel,
            frameColor=PANEL_BORDER,
            frameSize=(-0.52, 0, -0.004, 0.03),
            relief=DGG.FLAT,
        )
        self._target_name = OnscreenText(
            text="",
            parent=self._target_panel,
            pos=(-0.12, -0.048),
            scale=0.044,
            fg=(1, 0.85, 0.3, 1),
            align=TextNode.ARight,
            mayChange=True,
        )
        self._target_level = OnscreenText(
            text="",
            parent=self._target_panel,
            pos=(-0.03, -0.048),
            scale=0.034,
            fg=(1, 1, 0.6, 1),
            align=TextNode.ARight,
            mayChange=True,
        )
        DirectFrame(
            parent=self._target_panel,
            frameColor=HP_BG,
            frameSize=(-0.49, -0.03, -0.125, -0.075),
            relief=DGG.FLAT,
        )
        self._target_health_fill = DirectFrame(
            parent=self._target_panel,
            frameColor=HP_FILL,
            frameSize=(-0.49, -0.03, -0.125, -0.075),
            relief=DGG.FLAT,
        )
        self._target_health_label = OnscreenText(
            text="0/0",
            parent=self._target_panel,
            pos=(-0.26, -0.114),
            scale=0.03,
            fg=(1, 1, 1, 1),
            align=TextNode.ACenter,
            mayChange=True,
            sort=1,
        )
        self._target_panel.hide()

    def refresh_target(self, name, health, max_health, target_level=None, player_level=None, target_role="normal"):
        self._target_card["root"].enabled = True

        display_name = name
        name_color = DBG_ACCENT
        if target_role == "elite":
            display_name = f"* {name} *"
            name_color = color.rgba32(255, 232, 120)
        elif target_role == "boss":
            display_name = f"!!! {name} !!!"
            name_color = color.rgba32(255, 88, 88)

        ratio = 0.0 if max_health <= 0 else max(0.0, min(1.0, health / max_health))
        self._target_card["title"].text = display_name
        self._target_card["title"].color = name_color
        self._target_card["level"].text = "" if target_level is None else f"Lv {int(target_level)}"
        self._target_card["bar_fill"].scale_x = ratio
        self._target_card["value"].text = f"{int(math.ceil(health))}/{int(max_health)}"

    def clear_target(self):
        self._target_card["root"].enabled = False

    def _target_level_color(self, target_level, player_level):
        if player_level is None:
            return (1, 1, 0.6, 1)
        delta = int(target_level) - int(player_level)
        if delta <= -3:
            return (0.35, 1.0, 0.35, 1)
        if delta >= 3:
            return (1.0, 0.35, 0.35, 1)
        return (1.0, 0.92, 0.45, 1)

    def _build_action_bar(self):
        self._action_bar = DirectFrame(
            parent=self._ui_root,
            frameColor=(0.05, 0.06, 0.07, 0.80),
            frameSize=(-0.44, 0.44, -0.11, 0.10),
            pos=(0, 0, ACTION_BAR_Y)
        )
        DirectFrame(
            parent=self._action_bar,
            frameColor=PANEL_BORDER,
            frameSize=(-0.44, 0.44, 0.066, 0.10),
            relief=DGG.FLAT,
        )
        OnscreenText(
            text="Combat Actions",
            parent=self._action_bar,
            pos=(0, 0.074),
            scale=0.028,
            fg=(0.92, 0.92, 0.95, 1),
            align=TextNode.ACenter,
        )
        self._melee_range_bg = DirectFrame(
            parent=self._action_bar,
            text="1",
            text_scale=0.05,
            text_pos=(0, -0.014),
            text_fg=(1,1,1,1),
            frameColor=IDLE_COLOR,
            frameSize=(-0.08, 0.08, -0.07, 0.07),
            pos=(-0.13, 0, -0.002),
            relief=DGG.FLAT,
        )
        OnscreenText(text="Melee", parent=self._melee_range_bg, pos=(0, -0.102), scale=0.024, fg=(0.8,0.8,0.8,1))
        self._melee_range_state = OnscreenText(
            text="No target",
            parent=self._melee_range_bg,
            pos=(0, -0.134),
            scale=0.018,
            fg=(0.65, 0.67, 0.70, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )
        TOOLTIP_MANAGER.bind(self._melee_range_bg, "Melee auto-attack range indicator.\nGreen means your current target is in range.")

        self._ranged_range_bg = DirectFrame(
            parent=self._action_bar,
            text="2",
            text_scale=0.05,
            text_pos=(0, -0.014),
            text_fg=(1,1,1,1),
            frameColor=IDLE_COLOR,
            frameSize=(-0.08, 0.08, -0.07, 0.07),
            pos=(0.13, 0, -0.002),
            relief=DGG.FLAT,
        )
        OnscreenText(text="Ranged", parent=self._ranged_range_bg, pos=(0, -0.102), scale=0.024, fg=(0.8,0.8,0.8,1))
        self._ranged_range_state = OnscreenText(
            text="No target",
            parent=self._ranged_range_bg,
            pos=(0, -0.134),
            scale=0.018,
            fg=(0.65, 0.67, 0.70, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )
        TOOLTIP_MANAGER.bind(self._ranged_range_bg, "Ranged auto-attack range indicator.\nGreen means your current target is in range.")

    def refresh_range_indicators(self, melee_in, ranged_in):
        self._melee_box["box"].color = color.rgba32(56, 142, 72) if melee_in else color.rgba32(148, 58, 58)
        self._ranged_box["box"].color = color.rgba32(56, 142, 72) if ranged_in else color.rgba32(148, 58, 58)
        self._melee_box["key"].color = DBG_TEXT
        self._ranged_box["key"].color = DBG_TEXT
        self._melee_box["state"].text = "Ready" if melee_in else "Too far"
        self._ranged_box["state"].text = "Ready" if ranged_in else "Too far"
        self._melee_box["state"].color = DBG_TEXT if melee_in else DBG_TEXT_DIM
        self._ranged_box["state"].color = DBG_TEXT if ranged_in else DBG_TEXT_DIM

    def clear_range_indicators(self):
        self._melee_box["box"].color = DBG_MENU
        self._ranged_box["box"].color = DBG_MENU
        self._melee_box["state"].text = "No target"
        self._ranged_box["state"].text = "No target"
        self._melee_box["state"].color = DBG_TEXT_DIM
        self._ranged_box["state"].color = DBG_TEXT_DIM

    def _build_cast_bar(self):
        self._cast_bar_panel = DirectFrame(
            parent=self._ui_root,
            frameColor=(0.05, 0.05, 0.05, 0.86),
            frameSize=(-0.27, 0.27, -0.06, 0.06),
            pos=(0, 0, -0.72),
        )
        self._cast_bar_label = OnscreenText(
            text="",
            parent=self._cast_bar_panel,
            pos=(0, 0.012),
            scale=0.03,
            fg=(1, 1, 1, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )
        DirectFrame(
            parent=self._cast_bar_panel,
            frameColor=(0.12, 0.12, 0.12, 1),
            frameSize=(-0.22, 0.22, -0.04, -0.016),
        )
        self._cast_bar_fill = DirectFrame(
            parent=self._cast_bar_panel,
            frameColor=CAST_FILL,
            frameSize=(-0.22, -0.22, -0.04, -0.016),
        )
        self._cast_bar_panel.hide()

    def _build_game_log_window(self):
        self._game_log_window = DraggableWindow(
            "Game Log",
            (0, 0.66, -0.72, 0.06),
            (-1.1, 0, -0.1),
            self._close_game_log,
            resize_callback=self._layout_game_log_window,
            resizable=True,
        )
        self._game_log_scroll = DirectScrolledFrame(
            parent=self._game_log_window.body,
            canvasSize=(0, 0.6, -0.1, 0),
            frameSize=(0.02, 0.64, -0.68, -0.02),
            frameColor=(0.06, 0.06, 0.06, 0.7),
            scrollBarWidth=0.03,
            pos=(0, 0, -0.02),
        )
        self._layout_game_log_window(self._game_log_window._frame_size)
        self._game_log_window.hide()
        self._game_log_labels = []

    def _build_combat_log_window(self):
        self._combat_log_window = DraggableWindow(
            "Combat Log",
            (0, 0.66, -0.72, 0.06),
            (-0.35, 0, -0.1),
            self._close_combat_log,
            resize_callback=self._layout_combat_log_window,
            resizable=True,
        )
        self._combat_log_scroll = DirectScrolledFrame(
            parent=self._combat_log_window.body,
            canvasSize=(0, 0.6, -0.1, 0),
            frameSize=(0.02, 0.64, -0.68, -0.02),
            frameColor=(0.06, 0.06, 0.06, 0.7),
            scrollBarWidth=0.03,
            pos=(0, 0, -0.02),
        )
        self._layout_combat_log_window(self._combat_log_window._frame_size)
        self._combat_log_window.hide()
        self._combat_log_labels = []

    def _build_combat_debug_window(self):
        self._combat_debug_window = DraggableWindow(
            "Combat Debugger",
            (0, 0.72, -0.66, 0.06),
            (0.35, 0, 0.2),
            self._close_combat_debug,
        )
        body = self._combat_debug_window.body
        self._combat_debug_label = OnscreenText(
            text="",
            parent=body,
            pos=(0.02, -0.06),
            scale=0.03,
            fg=(0.9, 0.9, 0.92, 1),
            align=TextNode.ALeft,
            mayChange=True,
        )
        self._combat_debug_window.hide()

    def _timestamp(self):
        return datetime.now().strftime("[%H:%M:%S]")

    def _layout_game_log_window(self, frame_size):
        left, right, bottom, _top = frame_size
        width = max(0.2, right - left - 0.04)
        height = max(0.2, (_top - bottom) - 0.16)
        self._game_log_scroll.setPos(left + 0.02, 0, bottom + 0.05)
        self._game_log_scroll["frameSize"] = (0, width, 0, height)

    def _layout_combat_log_window(self, frame_size):
        left, right, bottom, _top = frame_size
        width = max(0.2, right - left - 0.04)
        height = max(0.2, (_top - bottom) - 0.16)
        self._combat_log_scroll.setPos(left + 0.02, 0, bottom + 0.05)
        self._combat_log_scroll["frameSize"] = (0, width, 0, height)

    def add_log(self, msg):
        self._append_log_entry(self._game_log_entries, self._game_log_labels, self._game_log_scroll, msg)

    def add_combat_log(self, msg):
        self._append_log_entry(self._combat_log_entries, self._combat_log_labels, self._combat_log_scroll, msg)

    def record_combat_event(self, event):
        self._last_combat_event = dict(event)
        if self._combat_debug_visible and self.player is not None:
            app = getattr(self.player, "_app", None)
            target = app.selection_manager.selected_target if app and hasattr(app, "selection_manager") else None
            self.refresh_combat_debug(self.player, target)

    def set_benchmark_summary(self, summary):
        self._benchmark_summary = summary or "No benchmark run yet."
        if self._combat_debug_visible and self.player is not None:
            app = getattr(self.player, "_app", None)
            target = app.selection_manager.selected_target if app and hasattr(app, "selection_manager") else None
            self.refresh_combat_debug(self.player, target)

    def _append_log_entry(self, entries, labels, scroll, msg):
        if not msg:
            return
        entries.append(f"{self._timestamp()} {msg}")
        if len(entries) > LOG_WINDOW_MAX:
            del entries[:-LOG_WINDOW_MAX]
        self._refresh_log_labels(entries, labels, scroll)

    def _refresh_log_labels(self, entries, labels, scroll):
        for label in labels:
            label.destroy()
        labels[:] = []
        canvas = scroll.getCanvas()
        y = -0.05
        for entry in entries:
            label = OnscreenText(
                text=entry,
                parent=canvas,
                pos=(0.01, y),
                scale=0.028,
                fg=(0.88, 0.88, 0.9, 1),
                align=TextNode.ALeft,
                wordwrap=max(16, (scroll["frameSize"][1] - scroll["frameSize"][0]) * 26),
            )
            labels.append(label)
            y -= 0.05
        width = max(0.2, scroll["frameSize"][1] - scroll["frameSize"][0])
        scroll["canvasSize"] = (0, width, min(-0.1, y - 0.02), 0)

    def show_cast_progress(self, label, progress, total):
        total = max(total, 0.001)
        ratio = max(0.0, min(1.0, progress / total))
        self._cast_label.text = f"{label} {progress:.1f}/{total:.1f}s"
        self._cast_fill.scale_x = ratio
        self._cast_shell.enabled = True

    def hide_cast_progress(self):
        self._cast_shell.enabled = False

    def _build_menu_buttons(self):
        self.menu_buttons = []
        buttons = [
            ("Inventory (I)", self.toggle_inventory, (0.2, 0.3, 0.5, 1)),
            ("Equipment (C)", self.toggle_equipment, (0.3, 0.5, 0.2, 1)),
            ("Skills (K)", self.toggle_skills, (0.5, 0.2, 0.2, 1)),
            ("Game Log (L)", self.toggle_game_log, (0.35, 0.35, 0.35, 1)),
            ("Combat Log (J)", self.toggle_combat_log, (0.45, 0.28, 0.18, 1)),
            ("Combat Debugger (F4)", self.toggle_combat_debug, (0.18, 0.35, 0.35, 1)),
            ("Developer Menu (F1)", self._on_dev_clicked, (0.4, 0.4, 0.4, 1)),
        ]

        self._menu_toggle = create_text_button(
            self.app.aspect2d if self.app is not None else None,
            "Menu",
            (0, 0, 0),
            self.toggle_menu_popup,
            scale=0.05,
            min_half_width=1.4,
            max_half_width=1.8,
            padding=0.45,
            frame_color=(0.2, 0.2, 0.24, 1),
        )
        TOOLTIP_MANAGER.bind(self._menu_toggle, "Open the quick menu.")

        self._menu_popup = DirectFrame(
            parent=self._ui_root,
            frameColor=(0.08, 0.08, 0.08, 0.92),
            frameSize=(-0.34, 0.34, -0.56, 0.04),
            pos=(0, 0, 0),
        )
        self._menu_popup.hide()

        for i, (text, cmd, color) in enumerate(buttons):
            btn = create_text_button(
                self._menu_popup,
                text,
                (0, 0, -0.06 - i * 0.075),
                self._run_menu_command,
                scale=0.04,
                min_half_width=1.6,
                max_half_width=None,
                padding=0.55,
                frame_color=color,
                extra_args=[cmd],
            )
            # Add simple hover effect
            btn.bind(DGG.ENTER, lambda e, b=btn: b.setColorScale(1.2, 1.2, 1.2, 1))
            btn.bind(DGG.EXIT, lambda e, b=btn: b.setColorScale(1, 1, 1, 1))
            TOOLTIP_MANAGER.bind(btn, self._menu_tooltip(text))
            self.menu_buttons.append(btn)

    def toggle_menu_popup(self):
        self._menu_popup_visible = not self._menu_popup_visible
        if self._menu_popup_visible:
            self._menu_popup_root.enabled = True
        else:
            self._menu_popup_root.enabled = False

    def _run_menu_command(self, command):
        self._menu_popup_visible = False
        self._menu_popup_root.enabled = False
        command()

    def _on_dev_clicked(self):
        if hasattr(self.player, "_app") and self.player._app:
            self.player._app.dev_menu.toggle()

    def _build_quest_tracker(self):
        self._quest_panel = DirectFrame(
            parent=self._ui_root,
            frameColor=(0.05, 0.05, 0.06, 0.38),
            frameSize=(0, 0.54, -0.62, 0.02),
            pos=(0, 0, 0)
        )
        self.refresh_quests()

    def refresh_quests(self):
        for lbl in self._quest_labels:
            lbl.destroy()
        self._quest_labels = []
        
        if not hasattr(self.player, "_app") or not self.player._app:
            if hasattr(self, "_quest_text"):
                self._quest_text.text = ""
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
        lines = []
        for quest in qm.active_quests[:3]:
            lines.append(quest.name)
            for obj in quest.objectives[:3]:
                lines.append(f"- {obj['text']}: {obj['count']}/{obj['target']}")
        if self._quest_labels:
            if hasattr(self, "_quest_text"):
                self._quest_text.text = "\n".join(lines)
        else:
            if hasattr(self, "_quest_text"):
                self._quest_text.text = ""

    def _build_inventory_window(self):
        self._inv_window = UiWindow(
            title="Inventory",
            parent=self._ui_layer,
            position=(0.52, -0.02, 0),
            scale=(0.78, 0.84),
            panel_color=DBG_PANEL_ALT,
            header_color=DBG_PANEL,
            close_callback=self._close_inventory,
        )
        body = self._inv_window.content
        start_x = -0.30
        start_y = 0.24
        step = 0.088
        for idx in range(self.inventory.slot_count()):
            col = idx % INV_COLS
            row = idx // INV_COLS
            btn = self._build_slot_button(
                parent=body,
                position=(start_x + col * step, start_y - row * step, -0.02),
                scale=(0.072, 0.072),
                on_click=lambda slot_key=idx: self._select_inventory_slot(slot_key),
            )
            self._inventory_buttons[idx] = btn

        self._inventory_detail_title = UText(
            parent=body,
            text="Select an item",
            origin=(-0.5, 0.5),
            position=(0.08, 0.27, -0.02),
            scale=0.95,
            color=DBG_ACCENT,
        )
        self._inventory_detail_text = UText(
            parent=body,
            text="",
            origin=(-0.5, 0.5),
            position=(0.08, 0.22, -0.02),
            scale=0.62,
            color=DBG_TEXT,
        )
        self._inventory_action_button = FlatButton(
            parent=body,
            text="Equip",
            position=(0.22, -0.25, -0.02),
            scale=(0.16, 0.05),
            color_value=DBG_MENU,
            highlight_color=DBG_MENU_HI,
            pressed_color=DBG_MENU_PRESS,
            text_color=DBG_TEXT,
            text_scale=0.72,
            on_click=self._inventory_primary_action,
        )
        self._inventory_action_button.visible = False
        self._inv_window.hide()
        self._refresh_inventory_window()

    def _build_equipment_window(self):
        self._equip_window = UiWindow(
            title="Equipment",
            parent=self._ui_layer,
            position=(-0.08, -0.02, 0),
            scale=(0.84, 0.78),
            panel_color=DBG_PANEL_ALT,
            header_color=DBG_PANEL,
            close_callback=self._close_equipment,
        )
        body = self._equip_window.content

        UText(parent=body, text="Equipment", origin=(0, 0.5), position=(-0.18, 0.29, -0.02), scale=0.9, color=DBG_ACCENT)
        positions = {
            "head": (-0.28, 0.19),
            "necklace": (-0.18, 0.19),
            "weapon": (-0.38, 0.09),
            "chest": (-0.28, 0.09),
            "offhand": (-0.18, 0.09),
            "hands": (-0.38, -0.01),
            "legs": (-0.28, -0.01),
            "ring": (-0.18, -0.01),
            "ranged": (-0.38, -0.11),
            "feet": (-0.28, -0.11),
        }
        for slot_name, meta in EQUIPMENT_SLOTS.items():
            if slot_name not in positions:
                continue
            x, y = positions[slot_name]
            btn = self._build_slot_button(
                parent=body,
                position=(x, y, -0.02),
                scale=(0.082, 0.082),
                on_click=lambda key=slot_name: self._select_equipment_slot(key),
            )
            btn["empty"].text = meta["label"]
            self._equipment_buttons[slot_name] = btn

        UText(parent=body, text="Item Details", origin=(-0.5, 0.5), position=(-0.06, 0.29, -0.02), scale=0.84, color=DBG_ACCENT)
        self._equipment_detail_title = UText(
            parent=body,
            text="Select equipped item",
            origin=(-0.5, 0.5),
            position=(-0.06, 0.22, -0.02),
            scale=0.88,
            color=DBG_TEXT,
        )
        self._equipment_detail_text = UText(
            parent=body,
            text="",
            origin=(-0.5, 0.5),
            position=(-0.06, 0.17, -0.02),
            scale=0.58,
            color=DBG_TEXT_DIM,
        )
        self._equipment_action_button = FlatButton(
            parent=body,
            text="Unequip",
            position=(0.10, -0.22, -0.02),
            scale=(0.17, 0.05),
            color_value=DBG_MENU,
            highlight_color=DBG_MENU_HI,
            pressed_color=DBG_MENU_PRESS,
            text_color=DBG_TEXT,
            text_scale=0.72,
            on_click=self._equipment_primary_action,
        )
        self._equipment_action_button.visible = False

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

        UText(parent=body, text="Combat Stats", origin=(-0.5, 0.5), position=(0.24, 0.29, -0.02), scale=0.84, color=DBG_ACCENT)
        self._stat_labels = {}
        for i, (stat_key, label_text) in enumerate(stats_to_show):
            y = 0.20 - i * 0.055
            UText(
                parent=body,
                text=label_text,
                origin=(-0.5, 0.5),
                position=(0.24, y, -0.02),
                scale=0.56,
                color=DBG_TEXT_DIM,
            )
            val_lbl = UText(
                parent=body,
                text="0",
                origin=(0.5, 0.5),
                position=(0.41, y, -0.02),
                scale=0.56,
                color=DBG_TEXT,
            )
            self._stat_labels[stat_key] = val_lbl
        self._equip_window.hide()
        self._refresh_equipment_window()

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
            if hasattr(label, "text"):
                label.text = text
            else:
                label.setText(text)

    def _build_skill_window(self):
        self._skill_window = UiWindow(
            title="Skills",
            parent=self._ui_layer,
            position=(-0.66, 0.05, 0),
            scale=(0.66, 0.84),
            panel_color=DBG_PANEL_ALT,
            header_color=DBG_PANEL,
            close_callback=self._close_skills,
        )
        body = self._skill_window.content
        self._skill_combat_label = UText(
            parent=body,
            text="Combat Level 1",
            origin=(-0.5, 0.5),
            position=(-0.27, 0.31, -0.02),
            scale=1.0,
            color=DBG_ACCENT,
        )

        self._skill_bars = {}
        self._skill_meta_labels = {}
        rows_per_col = math.ceil(len(SKILLS) / 2)
        for idx, skill in enumerate(SKILLS):
            col = idx // rows_per_col
            row = idx % rows_per_col
            base_x = -0.28 if col == 0 else 0.03
            base_y = 0.25 - row * 0.078
            lbl = UText(
                parent=body,
                text=f"{skill}  Lv 1",
                origin=(-0.5, 0.5),
                position=(base_x, base_y, -0.02),
                scale=0.76,
                color=DBG_TEXT,
            )
            meta = UText(
                parent=body,
                text="0 / 100 XP",
                origin=(-0.5, 0.5),
                position=(base_x, base_y - 0.022, -0.02),
                scale=0.54,
                color=DBG_TEXT_DIM,
            )
            bar_bg = self._make_ui_quad(
                parent=body,
                color_value=DBG_BAR_BG,
                scale=(0.17, 0.010),
                position=(base_x + 0.085, base_y - 0.045, -0.02),
            )
            bar_fill = self._make_ui_quad(
                parent=bar_bg,
                color_value=DBG_GOOD,
                origin=(-0.5, 0),
                position=(-0.5, 0, -0.001),
                scale=(0, 1, 1),
            )
            if any(recipe["skill"] == skill for recipe in crafting_svc.RECIPES.values()):
                recipe_button = FlatButton(
                    parent=body,
                    text="Recipes",
                    position=(base_x + 0.21, base_y - 0.010, -0.02),
                    scale=(0.068, 0.022),
                    color_value=DBG_MENU,
                    highlight_color=DBG_MENU_HI,
                    pressed_color=DBG_MENU_PRESS,
                    text_color=DBG_TEXT,
                    text_scale=0.40,
                    on_click=lambda skill_name=skill: self._open_skill_recipes(skill_name),
                )
            self._skill_bars[skill] = (lbl, bar_fill)
            self._skill_meta_labels[skill] = meta
        self.refresh_skills()
        self._skill_window.hide()

    def refresh_inventory(self):
        if self._inventory_slots is not None:
            self._inventory_slots.refresh()
        if self._equipment_slots is not None:
            self._equipment_slots.refresh()
        self._refresh_inventory_window()
        self._refresh_equipment_window()
        self.refresh_stats()

    def _on_inventory_changed(self):
        self.refresh_inventory()

    def refresh_skills(self):
        if hasattr(self._skill_combat_label, "text"):
            self._skill_combat_label.text = f"Combat Level {self.skills.get_combat_level()}"
        else:
            self._skill_combat_label.setText(f"Combat Level {self.skills.get_combat_level()}")
        for skill, (label, bar_fill) in self._skill_bars.items():
            level = self.skills.get_level(skill)
            xp_in, xp_max = self.skills.get_xp_progress(skill)
            text_value = f"{skill}  Lv {level}"
            meta_value = f"{xp_in:.0f} / {xp_max:.0f} XP"
            if hasattr(label, "text"):
                label.text = text_value
                self._skill_meta_labels[skill].text = meta_value
                bar_fill.scale_x = max(0.001, xp_in / xp_max)
            else:
                label.setText(text_value)
                self._skill_meta_labels[skill].setText(meta_value)
                fill_w = BAR_WIDTH * (xp_in / xp_max)
                bar_fill["frameSize"] = (0, max(0.001, fill_w), 0, BAR_HEIGHT)

    def is_any_window_open(self):
        crafting_open = bool(getattr(getattr(self, "app", None), "crafting_ui", None) and self.app.crafting_ui.is_open())
        return self._inv_visible or self._skill_visible or self._equip_visible or crafting_open

    def toggle_inventory(self):
        self._set_inventory_visible(not self._inv_visible)

    def toggle_equipment(self):
        self._set_equipment_visible(not self._equip_visible)

    def toggle_skills(self):
        self._set_skills_visible(not self._skill_visible)

    def toggle_game_log(self):
        self._set_game_log_visible(not self._game_log_visible)

    def toggle_combat_log(self):
        self._set_combat_log_visible(not self._combat_log_visible)

    def toggle_combat_debug(self):
        self._set_combat_debug_visible(not self._combat_debug_visible)

    def _close_inventory(self):
        CONTEXT_MENU_MANAGER.hide()
        QUANTITY_PROMPT_MANAGER.hide()
        self._set_inventory_visible(False)

    def _close_equipment(self):
        CONTEXT_MENU_MANAGER.hide()
        QUANTITY_PROMPT_MANAGER.hide()
        self._set_equipment_visible(False)

    def _close_skills(self):
        self._set_skills_visible(False)

    def _close_game_log(self):
        self._set_game_log_visible(False)

    def _close_combat_log(self):
        self._set_combat_log_visible(False)

    def _close_combat_debug(self):
        self._set_combat_debug_visible(False)

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

    def _set_game_log_visible(self, visible):
        self._game_log_visible = visible
        if visible:
            self._refresh_log_labels(self._game_log_entries, self._game_log_labels, self._game_log_scroll)
            self._game_log_window.show()
        else:
            self._game_log_window.hide()

    def _set_combat_log_visible(self, visible):
        self._combat_log_visible = visible
        if visible:
            self._refresh_log_labels(self._combat_log_entries, self._combat_log_labels, self._combat_log_scroll)
            self._combat_log_window.show()
        else:
            self._combat_log_window.hide()

    def _set_combat_debug_visible(self, visible):
        self._combat_debug_visible = visible
        if visible:
            app = getattr(self.player, "_app", None) if self.player else None
            target = app.selection_manager.selected_target if app and hasattr(app, "selection_manager") else None
            self.refresh_combat_debug(self.player, target)
            self._combat_debug_window.show()
        else:
            self._combat_debug_window.hide()

    def _build_range_indicators(self):
        # Deprecated in favor of action bar
        pass

    def _open_skill_recipes(self, skill):
        game_app = self._active_app()
        app = game_app if game_app is not None and hasattr(game_app, "crafting_ui") else getattr(self, "app", None)
        if app is not None and hasattr(app, "crafting_ui"):
            app.crafting_ui.open_skill(skill)

    def _active_app(self):
        return getattr(self.player, "_app", None) if self.player is not None else None

    def _build_slot_button(self, parent, position, scale, on_click):
        btn = FlatButton(
            parent=parent,
            text="",
            position=position,
            scale=scale,
            color_value=DBG_MENU,
            highlight_color=DBG_MENU_HI,
            pressed_color=DBG_MENU_PRESS,
            text_color=DBG_TEXT,
            text_scale=0.42,
            on_click=on_click,
        )
        icon = self._make_ui_quad(parent=btn, color_value=DBG_PANEL, scale=(0.024, 0.024), position=(0, 0.012, -0.02))
        qty = UText(parent=btn, text="", origin=(0.5, -0.5), position=(0.026, -0.018, -0.02), scale=0.44, color=DBG_TEXT)
        empty = UText(parent=btn, text="", origin=(0, 0), position=(0, -0.028, -0.02), scale=0.30, color=DBG_TEXT_DIM)
        return {"button": btn, "icon": icon, "qty": qty, "empty": empty}

    def _slot_button_text(self, stack):
        if stack is None:
            return ""
        item_name = get_item_name(stack["id"])
        parts = [word[0] for word in item_name.split()[:2] if word]
        return "".join(parts)[:2].upper()

    def _set_slot_button_state(self, entry, stack, selected=False, empty_label=""):
        btn = entry["button"]
        base = DBG_GOOD if selected else DBG_MENU
        btn.base_color = base
        btn.highlight_color = DBG_MENU_HI if not selected else DBG_GOOD
        btn.pressed_color = DBG_MENU_PRESS if not selected else DBG_MENU
        btn.color = base
        btn.setColorScale(base)
        if stack is None:
            entry["icon"].color = DBG_PANEL
            entry["icon"].setColorScale(DBG_PANEL)
            btn.label.text = ""
            entry["qty"].text = ""
            entry["empty"].text = empty_label
            return
        item_def = get_item_def(stack["id"]) or {}
        item_color = tuple(item_def.get("color", (0.8, 0.8, 0.8, 1.0)))
        if max(item_color[:3]) > 1.0:
            item_color = tuple(channel / 255.0 for channel in item_color[:3]) + (item_color[3],)
        entry["icon"].color = item_color
        entry["icon"].setColorScale(item_color)
        btn.label.text = self._slot_button_text(stack)
        entry["qty"].text = str(stack["quantity"]) if stack["quantity"] > 1 else ""
        entry["empty"].text = ""

    def _refresh_inventory_window(self):
        if not self._inventory_buttons:
            return
        for slot_key, entry in self._inventory_buttons.items():
            stack = self.inventory.get_slot(slot_key)
            self._set_slot_button_state(entry, stack, selected=(slot_key == self._selected_inventory_slot))
        self._refresh_inventory_detail()

    def _refresh_equipment_window(self):
        if not self._equipment_buttons:
            return
        for slot_name, entry in self._equipment_buttons.items():
            stack = self.inventory.equipment.get_slot(slot_name)
            label = EQUIPMENT_SLOTS[slot_name]["label"]
            self._set_slot_button_state(entry, stack, selected=(slot_name == self._selected_equipment_slot), empty_label=label)
        self._refresh_equipment_detail()

    def _select_inventory_slot(self, slot_key):
        self._selected_inventory_slot = slot_key
        self._refresh_inventory_window()

    def _select_equipment_slot(self, slot_name):
        self._selected_equipment_slot = slot_name
        self._refresh_equipment_window()

    def _refresh_inventory_detail(self):
        if not hasattr(self, "_inventory_detail_title"):
            return
        stack = self.inventory.get_slot(self._selected_inventory_slot) if self._selected_inventory_slot is not None else None
        if stack is None:
            self._inventory_detail_title.text = "Select an item"
            self._inventory_detail_text.text = ""
            self._inventory_action_button.visible = False
            return
        self._inventory_detail_title.text = get_item_name(stack["id"])
        self._inventory_detail_text.text = build_item_tooltip(stack["id"], quantity=stack["quantity"])
        self._inventory_action_button.visible = get_equipment_slot(stack["id"]) is not None
        self._inventory_action_button.label.text = "Equip"

    def _refresh_equipment_detail(self):
        if not hasattr(self, "_equipment_detail_title"):
            return
        stack = self.inventory.equipment.get_slot(self._selected_equipment_slot) if self._selected_equipment_slot is not None else None
        if stack is None:
            self._equipment_detail_title.text = "Select equipped item"
            self._equipment_detail_text.text = ""
            self._equipment_action_button.visible = False
            return
        self._equipment_detail_title.text = get_item_name(stack["id"])
        self._equipment_detail_text.text = build_item_tooltip(stack["id"], quantity=stack["quantity"])
        self._equipment_action_button.visible = True
        self._equipment_action_button.label.text = "Unequip"

    def _inventory_primary_action(self):
        if self._selected_inventory_slot is None:
            return
        self._equip_from_inventory(self._selected_inventory_slot)

    def _equipment_primary_action(self):
        if self._selected_equipment_slot is None:
            return
        self._unequip_to_inventory(self._selected_equipment_slot)

    def _open_bank_ui(self):
        app = self._active_app()
        if app is None:
            return None
        for interactable in app._level_interactables():
            if getattr(interactable, "ui_open", False) and hasattr(interactable, "bank_inv"):
                return interactable
        return None

    def _open_vendor_ui(self):
        app = self._active_app()
        if app is None:
            return None
        for interactable in app._level_interactables():
            if getattr(interactable, "ui_open", False) and hasattr(interactable, "stock"):
                return interactable
        return None

    def _equip_from_inventory(self, slot_key):
        stack = self.inventory.get_slot(slot_key)
        if stack is None:
            return False
        slot_name = get_equipment_slot(stack["id"])
        if slot_name is None:
            return False
        equipped = self.inventory.equipment.get_slot(slot_name)
        if equipped is not None:
            free_slot = self.inventory.find_first_free_slot()
            if free_slot is None:
                self.show_prompt("Inventory full!")
                return False
            if not move_item(self.inventory.equipment, slot_name, self.inventory, free_slot):
                return False
        moved = move_item(self.inventory, slot_key, self.inventory.equipment, slot_name)
        if moved:
            self.refresh_inventory()
            self.show_prompt("Equipped")
        return moved

    def _unequip_to_inventory(self, slot_key):
        free_slot = self.inventory.find_first_free_slot()
        if free_slot is None:
            self.show_prompt("Inventory full!")
            return False
        moved = move_item(self.inventory.equipment, slot_key, self.inventory, free_slot)
        if moved:
            self.refresh_inventory()
            self.show_prompt("Unequipped")
        return moved

    def _build_inventory_actions(self, _collection, slot_key, stack):
        actions = []
        if get_equipment_slot(stack["id"]) is not None:
            actions.append({"label": "Equip", "callback": lambda key=slot_key: self._equip_from_inventory(key)})

        bank = self._open_bank_ui()
        if bank is not None:
            max_qty = stack["quantity"]
            actions.extend(
                [
                    {"label": "Deposit 1", "callback": lambda key=slot_key: bank.deposit_from_inventory(key, 1)},
                    {"label": "Deposit 10", "callback": lambda key=slot_key, qty=max_qty: bank.deposit_from_inventory(key, min(10, qty))},
                    {
                        "label": "Deposit X",
                        "callback": lambda key=slot_key, qty=max_qty: QUANTITY_PROMPT_MANAGER.ask(
                            f"Deposit {stack['id']}", qty, lambda amount: bank.deposit_from_inventory(key, amount), min(10, qty)
                        ),
                    },
                ]
            )

        vendor = self._open_vendor_ui()
        if vendor is not None and stack["id"] != "gold":
            max_qty = stack["quantity"]
            actions.extend(
                [
                    {"label": "Sell 1", "callback": lambda key=slot_key: vendor.sell_from_inventory(key, 1)},
                    {"label": "Sell 10", "callback": lambda key=slot_key, qty=max_qty: vendor.sell_from_inventory(key, min(10, qty))},
                    {
                        "label": "Sell X",
                        "callback": lambda key=slot_key, qty=max_qty: QUANTITY_PROMPT_MANAGER.ask(
                            f"Sell {stack['id']}", qty, lambda amount: vendor.sell_from_inventory(key, amount), min(10, qty)
                        ),
                    },
                ]
            )
        return actions

    def _build_equipment_actions(self, _collection, slot_key, stack):
        actions = [{"label": "Unequip", "callback": lambda key=slot_key: self._unequip_to_inventory(key)}]
        vendor = self._open_vendor_ui()
        if vendor is not None and stack["id"] != "gold":
            actions.append({"label": "Sell 1", "callback": lambda key=slot_key: vendor.sell_from_equipment(key, 1)})
        return actions

    def _menu_tooltip(self, button_text):
        tips = {
            "Inventory (I)": "Open the inventory window.",
            "Equipment (C)": "Open the equipment and combat stats window.",
            "Skills (K)": "Open the skills progression window.",
            "Game Log (L)": "Open the game event log.",
            "Combat Log (J)": "Open the combat log.",
            "Combat Debugger (F4)": "Open the combat debugger.",
            "Developer Menu (F1)": "Open the developer tools panel.",
        }
        return tips.get(button_text, button_text)

    def _stat_tooltip(self, stat_key, label_text):
        tips = {
            "melee_damage": "Base damage used by melee auto-attacks.",
            "ranged_damage": "Base damage used by ranged auto-attacks.",
            "magic_damage": "Reserved for spell or magic-based attacks.",
            "armor": "Reduces incoming damage through combat resolution.",
            "accuracy": "Improves chance to land attacks.",
            "evasion": "Chance to avoid incoming attacks.",
            "crit_chance": "Chance for attacks to critically strike.",
            "block_chance": "Chance to block with shields or defensive gear.",
            "parry_chance": "Chance to parry weapon attacks.",
        }
        return f"{label_text}\n{tips.get(stat_key, 'Current derived combat stat.')}"

    def refresh_combat_debug(self, player, target):
        if player is None:
            return
        p_level = player.get_combat_level() if hasattr(player, "get_combat_level") else self.skills.get_combat_level()
        p_lines = [
            f"Player CLv {p_level}",
            f"HP {player.health:.1f}/{player.max_health:.1f}",
            (
                "Stats "
                f"M:{player.stats.get('melee_damage'):.1f} "
                f"R:{player.stats.get('ranged_damage'):.1f} "
                f"Ma:{player.stats.get('magic_damage'):.1f} "
                f"Arm:{player.stats.get('armor'):.1f}"
            ),
        ]
        t_lines = ["Target: None"]
        if target is not None:
            target_level = target.get_level() if hasattr(target, "get_level") else 1
            t_lines = [
                f"Target {target.get_target_name()} Lv {target_level}",
                f"HP {target.health:.1f}/{target.max_health:.1f}",
                (
                    "Stats "
                    f"M:{target.stats.get('melee_damage'):.1f} "
                    f"R:{target.stats.get('ranged_damage'):.1f} "
                    f"Arm:{target.stats.get('armor'):.1f} "
                    f"Eva:{target.stats.get('evasion'):.2f}"
                ),
            ]
        event = self._last_combat_event or {}
        event_lines = [
            "Last Event",
            (
                f"{event.get('attacker', '-')} -> {event.get('defender', '-')} "
                f"[{event.get('style', '-')}] {event.get('result', '-')}"
            ),
            (
                f"Base {event.get('base_damage', 0.0):.1f} | "
                f"Final {event.get('damage', 0.0):.1f} | "
                f"Mitigated {event.get('mitigated', 0.0):.1f}"
            ),
            f"Benchmark: {self._benchmark_summary}",
        ]
        self._combat_debug_label.setText("\n".join(p_lines + [""] + t_lines + [""] + event_lines))
