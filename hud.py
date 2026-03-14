"""
hud.py — All DirectGUI: inventory grid, skill bars, context prompts.
"""

from direct.gui.DirectGui import (
    DirectFrame, DirectButton, OnscreenText
)
from panda3d.core import TextNode, Vec4
from inventory import ITEMS, SKILLS, XP_PER_LEVEL, xp_to_level, xp_into_level


# Layout constants
INV_COLS = 4
INV_ROWS = 7
SLOT_SIZE = 0.09       # in aspect2d units
SLOT_GAP = 0.005
INV_ORIGIN_X = 0.55   # right side
INV_ORIGIN_Y = -0.55  # bottom area

SKILL_PANEL_X = -1.3
SKILL_PANEL_Y = -0.4
BAR_WIDTH = 0.3
BAR_HEIGHT = 0.04


class HUD:
    def __init__(self, inventory):
        self.inventory = inventory
        self._prompt_text = None
        self._prompt_msg = ""
        self._inv_visible = True
        self._skill_visible = True
        self._tooltip = None
        self._slot_buttons = []
        self._skill_bars = {}  # skill -> (bg_frame, fill_frame, label)

        self._build_prompt()
        self._build_inventory_panel()
        self._build_skill_panel()

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

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
            self._prompt_msg = ""
            self._prompt_text.setText("")

    def clear_prompt(self):
        self._prompt_msg = ""
        self._prompt_text.setText("")

    # ------------------------------------------------------------------
    # Inventory panel
    # ------------------------------------------------------------------

    def _build_inventory_panel(self):
        panel_w = INV_COLS * (SLOT_SIZE + SLOT_GAP) + SLOT_GAP + 0.06
        panel_h = INV_ROWS * (SLOT_SIZE + SLOT_GAP) + SLOT_GAP + 0.1

        self._inv_panel = DirectFrame(
            frameColor=(0.15, 0.15, 0.15, 0.9),
            frameSize=(-0.03, panel_w, -panel_h, 0.06),
            pos=(INV_ORIGIN_X, 0, INV_ORIGIN_Y),
        )
        OnscreenText(
            text="Inventory",
            parent=self._inv_panel,
            pos=(panel_w / 2 - 0.03, 0.01),
            scale=0.04,
            fg=(1, 1, 1, 1),
            align=TextNode.ACenter,
        )

        self._slot_buttons = []
        for i in range(INV_COLS * INV_ROWS):
            col = i % INV_COLS
            row = i // INV_COLS
            x = SLOT_GAP + col * (SLOT_SIZE + SLOT_GAP)
            y = -(SLOT_GAP + row * (SLOT_SIZE + SLOT_GAP) + SLOT_SIZE)

            slot_frame = DirectFrame(
                parent=self._inv_panel,
                frameColor=(0.25, 0.25, 0.25, 1),
                frameSize=(0, SLOT_SIZE, 0, SLOT_SIZE),
                pos=(x, 0, y),
            )
            # Item color block (hidden by default)
            item_frame = DirectFrame(
                parent=slot_frame,
                frameColor=(0, 0, 0, 0),
                frameSize=(0.005, SLOT_SIZE - 0.005, 0.005, SLOT_SIZE - 0.005),
                pos=(0, 0, 0),
            )
            qty_label = OnscreenText(
                text="",
                parent=slot_frame,
                pos=(SLOT_SIZE - 0.005, 0.005),
                scale=0.025,
                fg=(1, 1, 1, 1),
                align=TextNode.ARight,
                mayChange=True,
            )
            self._slot_buttons.append((slot_frame, item_frame, qty_label))

        self.refresh_inventory()

    def refresh_inventory(self):
        for i, (slot_frame, item_frame, qty_label) in enumerate(self._slot_buttons):
            data = self.inventory.slots[i] if i < len(self.inventory.slots) else None
            if data:
                item_def = ITEMS.get(data["id"])
                if item_def:
                    c = item_def["color"]
                    item_frame["frameColor"] = c
                else:
                    item_frame["frameColor"] = (0.5, 0.5, 0.5, 1)
                qty = data["quantity"]
                qty_label.setText(str(qty) if qty > 1 else "")
            else:
                item_frame["frameColor"] = (0, 0, 0, 0)
                qty_label.setText("")

    def toggle_inventory(self):
        self._inv_visible = not self._inv_visible
        if self._inv_visible:
            self._inv_panel.show()
        else:
            self._inv_panel.hide()

    # ------------------------------------------------------------------
    # Skill panel
    # ------------------------------------------------------------------

    def _build_skill_panel(self):
        panel_h = len(SKILLS) * 0.12 + 0.08
        self._skill_panel = DirectFrame(
            frameColor=(0.15, 0.15, 0.15, 0.9),
            frameSize=(0, 0.42, -panel_h, 0.06),
            pos=(SKILL_PANEL_X, 0, SKILL_PANEL_Y),
        )
        OnscreenText(
            text="Skills",
            parent=self._skill_panel,
            pos=(0.21, 0.01),
            scale=0.04,
            fg=(1, 1, 1, 1),
            align=TextNode.ACenter,
        )

        self._skill_bars = {}
        for idx, skill in enumerate(SKILLS):
            y = -0.05 - idx * 0.12

            lbl = OnscreenText(
                text=f"{skill}  Lv 1",
                parent=self._skill_panel,
                pos=(0.01, y),
                scale=0.032,
                fg=(0.9, 0.9, 0.9, 1),
                align=TextNode.ALeft,
                mayChange=True,
            )

            bar_bg = DirectFrame(
                parent=self._skill_panel,
                frameColor=(0.1, 0.1, 0.1, 1),
                frameSize=(0, BAR_WIDTH, 0, BAR_HEIGHT),
                pos=(0.01, 0, y - 0.045),
            )
            bar_fill = DirectFrame(
                parent=self._skill_panel,
                frameColor=(0.2, 0.7, 0.2, 1),
                frameSize=(0, 0.001, 0, BAR_HEIGHT),
                pos=(0.01, 0, y - 0.045),
            )
            self._skill_bars[skill] = (lbl, bar_bg, bar_fill)

        self.refresh_skills()

    def refresh_skills(self):
        for skill, (lbl, bar_bg, bar_fill) in self._skill_bars.items():
            level = self.inventory.get_level(skill)
            xp_in, xp_max = self.inventory.get_xp_progress(skill)
            lbl.setText(f"{skill}  Lv {level}")
            fill_w = BAR_WIDTH * (xp_in / xp_max)
            bar_fill["frameSize"] = (0, max(0.001, fill_w), 0, BAR_HEIGHT)

    def toggle_skills(self):
        self._skill_visible = not self._skill_visible
        if self._skill_visible:
            self._skill_panel.show()
        else:
            self._skill_panel.hide()
