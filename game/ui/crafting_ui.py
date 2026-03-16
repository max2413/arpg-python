"""
crafting_ui.py - Draggable window for the crafting system.
"""

from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText, DirectScrolledFrame
from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import TextNode

from game.ui.widgets import DraggableWindow, create_item_icon
from game.systems.inventory import get_item_def
import game.services.crafting as crafting_svc

class CraftingUI(DraggableWindow):
    def __init__(self, app):
        self.app = app
        super().__init__(
            "Crafting",
            frame_size=(-0.7, 0.7, -0.65, 0.65),
            pos=(0, 0, 0),
            close_command=self.hide
        )
        self._station_type = None
        self._station_obj = None
        self._widgets = []
        
        self.hide()

    def open(self, station_type, station_obj):
        self._station_type = station_type
        self._station_obj = station_obj
        self.title_label.setText(f"Crafting - {station_type.capitalize()}")
        self.show()
        self.refresh()

    def refresh(self):
        for w in self._widgets:
            w.destroy()
        self._widgets = []

        # Header
        self._widgets.append(OnscreenText(
            text=f"Available Recipes",
            parent=self.body,
            pos=(0, 0.52),
            scale=0.045,
            fg=(1, 0.8, 0.2, 1),
            align=TextNode.ACenter
        ))

        # Scrolled list of recipes
        scroll = DirectScrolledFrame(
            parent=self.body,
            canvasSize=(-0.6, 0.6, -1.0, 0),
            frameSize=(-0.65, 0.65, -0.6, 0.45),
            frameColor=(0.1, 0.1, 0.1, 1),
            scrollBarWidth=0.04,
            pos=(0, 0, 0)
        )
        self._widgets.append(scroll)
        canvas = scroll.getCanvas()

        y = -0.08
        count = 0
        for rid, recipe in crafting_svc.RECIPES.items():
            if recipe["station"] != self._station_type:
                continue
            
            self._build_recipe_row(canvas, rid, recipe, y)
            y -= 0.18
            count += 1
        
        scroll["canvasSize"] = (-0.6, 0.6, min(-0.1, y), 0)

    def _build_recipe_row(self, parent, rid, recipe, y):
        item_def = get_item_def(recipe["output"]["id"])
        if not item_def: return

        # Icon
        icon_root = DirectFrame(
            parent=parent,
            frameColor=(0, 0, 0, 0),
            pos=(-0.58, 0, y),
            scale=0.12
        )
        create_item_icon(icon_root, item_def)

        # Name and Skill level
        skill_lvl = self.app.skills.get_level(recipe["skill"])
        can_craft_lvl = skill_lvl >= recipe["level"]
        color = (1, 1, 1, 1) if can_craft_lvl else (0.8, 0.3, 0.3, 1)
        
        OnscreenText(
            text=f"{recipe['name']} (Lv {recipe['level']} {recipe['skill']})",
            parent=parent,
            pos=(-0.44, y + 0.02),
            scale=0.035,
            fg=color,
            align=TextNode.ALeft
        )

        # Inputs
        input_text = "Requires: " + ", ".join([f"{qty} {k}" for k, qty in recipe["inputs"].items()])
        has_mats = True
        for item_id, qty in recipe["inputs"].items():
            if self.app.inventory.count_item(item_id) < qty:
                has_mats = False
                break
        
        input_color = (0.7, 0.7, 0.7, 1) if has_mats else (0.8, 0.4, 0.2, 1)
        OnscreenText(
            text=input_text,
            parent=parent,
            pos=(-0.44, y - 0.03),
            scale=0.028,
            fg=input_color,
            align=TextNode.ALeft
        )

        # Craft Button
        can_craft = can_craft_lvl and has_mats
        DirectButton(
            parent=parent,
            text="Craft",
            scale=0.04,
            pos=(0.45, 0, y),
            frameSize=(-2, 2, -0.6, 1.2),
            frameColor=(0.2, 0.5, 0.2, 1) if can_craft else (0.3, 0.3, 0.3, 1),
            text_fg=(1, 1, 1, 1) if can_craft else (0.6, 0.6, 0.6, 1),
            command=self._do_craft,
            extraArgs=[rid, recipe],
            state=DGG.NORMAL if can_craft else DGG.DISABLED
        )

    def _do_craft(self, rid, recipe):
        # Double check mats
        for item_id, qty in recipe["inputs"].items():
            if self.app.inventory.count_item(item_id) < qty:
                return

        # Consume inputs
        for item_id, qty in recipe["inputs"].items():
            self.app.inventory.remove_item(item_id, qty)
        
        # Add output
        out = recipe["output"]
        self.app.inventory.add_item(out["id"], out["qty"])
        
        # Award XP
        lvl_up = self.app.skills.add_xp(recipe["skill"], recipe["xp"])
        
        # Notify QuestManager
        if hasattr(self.app, "quest_manager"):
            self.app.quest_manager.notify_action("craft", out["id"])
        
        # Feedback
        self.app.hud.show_prompt(f"Crafted {recipe['name']}! (+{recipe['xp']} {recipe['skill']} XP)")
        if lvl_up > 0:
            self.app.hud.show_prompt(f"{recipe['skill']} level up! Level {self.app.skills.get_level(recipe['skill'])}")
        
        self.app.hud.refresh_inventory()
        self.app.hud.refresh_skills()
        self.refresh()
