"""Ursina-native crafting and recipe browser."""

from ursina import Entity, Text as UText, color

from game.systems.inventory import get_item_name
from game.ui.ursina_widgets import FlatButton, UiWindow
import game.services.crafting as crafting_svc


PANEL = color.rgba32(18, 26, 38)
PANEL_ALT = color.rgba32(26, 36, 52)
TEXT = color.rgba32(235, 242, 255)
TEXT_DIM = color.rgba32(170, 186, 210)
ACCENT = color.rgba32(255, 220, 90)
GOOD = color.rgba32(52, 166, 92)
BAD = color.rgba32(182, 72, 72)
BTN = color.rgba32(44, 66, 94)
BTN_HI = color.rgba32(62, 88, 120)
BTN_PRESS = color.rgba32(34, 50, 72)

RECIPES_PER_PAGE = 5


def _wrap_text(text, width):
    if not text:
        return ""
    words = text.split()
    lines = []
    current = []
    current_len = 0
    for word in words:
        projected = len(word) if not current else current_len + 1 + len(word)
        if projected > width and current:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len = projected
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


class CraftingUI:
    def __init__(self, app):
        self.app = app
        self._active_craft = None
        self._station_type = None
        self._station_obj = None
        self._skill_filter = None
        self._page = 0
        self._recipe_rows = []
        self._window = None
        self._visible = False
        self._build_ui()

    def _build_ui(self):
        parent = self.app.hud._ui_layer if hasattr(self.app, "hud") else None
        self._window = UiWindow(
            title="Crafting",
            parent=parent,
            position=(0.54, 0.05, 0),
            scale=(0.72, 0.82),
            panel_color=PANEL,
            header_color=PANEL_ALT,
            close_callback=self.hide,
        )
        body = self._window.content

        self._header_text = UText(
            parent=body,
            text="Available Recipes",
            origin=(-0.5, 0.5),
            position=(-0.30, 0.29, -0.02),
            scale=0.92,
            color=ACCENT,
        )
        self._subheader_text = UText(
            parent=body,
            text="",
            origin=(-0.5, 0.5),
            position=(-0.30, 0.24, -0.02),
            scale=0.46,
            color=TEXT_DIM,
        )
        self._page_text = UText(
            parent=body,
            text="",
            origin=(0, 0.5),
            position=(0, -0.33, -0.02),
            scale=0.52,
            color=TEXT_DIM,
        )
        self._prev_button = FlatButton(
            parent=body,
            text="Prev",
            position=(-0.11, -0.33, -0.02),
            scale=(0.09, 0.036),
            color_value=BTN,
            highlight_color=BTN_HI,
            pressed_color=BTN_PRESS,
            text_color=TEXT,
            text_scale=0.5,
            on_click=lambda: self._change_page(-1),
        )
        self._next_button = FlatButton(
            parent=body,
            text="Next",
            position=(0.11, -0.33, -0.02),
            scale=(0.09, 0.036),
            color_value=BTN,
            highlight_color=BTN_HI,
            pressed_color=BTN_PRESS,
            text_color=TEXT,
            text_scale=0.5,
            on_click=lambda: self._change_page(1),
        )

        y_positions = [0.14, 0.03, -0.08, -0.19, -0.30]
        for y in y_positions:
            row_root = Entity(parent=body, position=(0, y, -0.02))
            bg = Entity(parent=row_root, model="quad", color=PANEL_ALT, scale=(0.68, 0.088))
            title = UText(parent=row_root, text="", origin=(-0.5, 0.5), position=(-0.32, 0.022, -0.02), scale=0.54, color=TEXT)
            meta = UText(parent=row_root, text="", origin=(-0.5, 0.5), position=(-0.32, -0.002, -0.02), scale=0.38, color=TEXT_DIM)
            inputs = UText(parent=row_root, text="", origin=(-0.5, 0.5), position=(-0.32, -0.026, -0.02), scale=0.36, color=TEXT_DIM)
            craft = FlatButton(
                parent=row_root,
                text="Craft",
                position=(0.23, 0.0, -0.02),
                scale=(0.12, 0.042),
                color_value=GOOD,
                highlight_color=GOOD.tint(.1),
                pressed_color=GOOD.tint(-.1),
                text_color=TEXT,
                text_scale=0.54,
            )
            self._recipe_rows.append(
                {
                    "root": row_root,
                    "bg": bg,
                    "title": title,
                    "meta": meta,
                    "inputs": inputs,
                    "craft": craft,
                    "rid": None,
                    "recipe": None,
                }
            )

        self.hide()

    def _visible_recipes(self):
        recipes = []
        for rid, recipe in crafting_svc.RECIPES.items():
            if self._skill_filter and recipe["skill"] != self._skill_filter:
                continue
            if self._station_type and recipe["station"] != self._station_type:
                continue
            recipes.append((rid, recipe))
        return recipes

    def _change_page(self, delta):
        recipes = self._visible_recipes()
        if not recipes:
            self._page = 0
            self.refresh()
            return
        max_page = max(0, (len(recipes) - 1) // RECIPES_PER_PAGE)
        self._page = max(0, min(max_page, self._page + delta))
        self.refresh()

    def open(self, station_type, station_obj):
        self._station_type = station_type
        self._station_obj = station_obj
        self._skill_filter = None
        self._page = 0
        self._window.title.text = f"Crafting - {station_type.capitalize()}"
        self.show()
        self.refresh()

    def open_skill(self, skill_name):
        self._station_type = None
        self._station_obj = None
        self._skill_filter = skill_name
        self._page = 0
        self._window.title.text = f"Recipes - {skill_name}"
        self.show()
        self.refresh()

    def show(self):
        self._visible = True
        self._window.show()

    def hide(self):
        self.cancel_active_craft()
        self._visible = False
        if self._station_obj is not None:
            self._station_obj.ui_open = False
        self._station_type = None
        self._station_obj = None
        self._skill_filter = None
        self._page = 0
        self._window.hide()

    def is_open(self):
        return self._visible

    def refresh(self):
        header_text = "Available Recipes"
        subheader = ""
        if self._skill_filter:
            header_text = f"{self._skill_filter} Recipes"
            subheader = _wrap_text(
                "Browse recipes anywhere. Crafting still requires the listed station unless marked Anywhere.",
                42,
            )
        elif self._station_type:
            header_text = f"{self._station_type.capitalize()} Recipes"
        self._header_text.text = header_text
        self._subheader_text.text = subheader

        recipes = self._visible_recipes()
        max_page = max(0, (len(recipes) - 1) // RECIPES_PER_PAGE) if recipes else 0
        self._page = max(0, min(max_page, self._page))
        start = self._page * RECIPES_PER_PAGE
        page_recipes = recipes[start:start + RECIPES_PER_PAGE]
        self._page_text.text = f"Page {self._page + 1}/{max_page + 1}" if recipes else "No recipes"
        self._prev_button.visible = self._page > 0
        self._next_button.visible = self._page < max_page

        for row, payload in zip(self._recipe_rows, page_recipes + [None] * (len(self._recipe_rows) - len(page_recipes))):
            if payload is None:
                row["root"].enabled = False
                row["rid"] = None
                row["recipe"] = None
                continue
            rid, recipe = payload
            row["root"].enabled = True
            row["rid"] = rid
            row["recipe"] = recipe
            skill_lvl = self.app.skills.get_level(recipe["skill"])
            can_craft_lvl = skill_lvl >= recipe["level"]
            has_mats = all(self.app.inventory.count_item(item_id) >= qty for item_id, qty in recipe["inputs"].items())
            can_use_station = self._can_access_recipe(recipe)
            can_craft = can_craft_lvl and has_mats and can_use_station and self._active_craft is None
            station_name = "Anywhere" if recipe["station"] == "any" else recipe["station"].capitalize()
            craft_time = float(recipe.get("craft_time", 1.5))

            row["title"].text = _wrap_text(f"{recipe['name']}  Lv {recipe['level']} {recipe['skill']}", 28)
            row["title"].color = TEXT if can_craft_lvl else BAD
            row["meta"].text = _wrap_text(f"Station: {station_name} | Time: {craft_time:.1f}s | XP: {recipe['xp']}", 34)
            row["inputs"].text = _wrap_text(
                "Requires: " + ", ".join(f"{qty} {get_item_name(item_id)}" for item_id, qty in recipe["inputs"].items()),
                34,
            )
            row["inputs"].color = TEXT_DIM if has_mats else BAD
            row["craft"].label.text = "Craft" if can_use_station else "Need Station"
            tint = GOOD if can_craft else BTN
            row["craft"].base_color = tint
            row["craft"].color = tint
            row["craft"].setColorScale(tint)
            row["craft"].visible = True
            row["craft"]._click_callback = (lambda recipe_id=rid, recipe_data=recipe: self._start_craft(recipe_id, recipe_data)) if can_craft else None

    def update(self, dt):
        if self._active_craft is None:
            return
        player = getattr(self.app, "player", None)
        if player is None:
            self.cancel_active_craft()
            return
        if player.is_action_interrupting():
            self.cancel_active_craft("Crafting interrupted")
            return
        recipe = self._active_craft["recipe"]
        self._active_craft["elapsed"] += dt
        player.play_work_animation()
        self.app.hud.show_cast_progress(
            f"Crafting {recipe['name']}",
            self._active_craft["elapsed"],
            self._active_craft["total"],
        )
        if self._active_craft["elapsed"] >= self._active_craft["total"]:
            self._complete_craft()

    def _start_craft(self, rid, recipe):
        if self._active_craft is not None:
            return
        if hasattr(self.app, "player") and self.app.player.is_action_interrupting():
            self.app.hud.show_prompt("Stand still to craft")
            return
        if not self._can_access_recipe(recipe):
            self.app.hud.show_prompt("Need correct station")
            return
        for item_id, qty in recipe["inputs"].items():
            if self.app.inventory.count_item(item_id) < qty:
                self.app.hud.show_prompt("Missing materials")
                return
        self._active_craft = {
            "rid": rid,
            "recipe": recipe,
            "elapsed": 0.0,
            "total": float(recipe.get("craft_time", 1.5)),
        }
        self.app.hud.show_cast_progress(f"Crafting {recipe['name']}", 0.0, self._active_craft["total"])
        self.refresh()

    def cancel_active_craft(self, message=None):
        if self._active_craft is None:
            return
        self._active_craft = None
        self.app.hud.hide_cast_progress()
        if message:
            self.app.hud.show_prompt(message)
            self.app.hud.add_log(message)
        self.refresh()

    def _complete_craft(self):
        if self._active_craft is None:
            return
        recipe = self._active_craft["recipe"]

        for item_id, qty in recipe["inputs"].items():
            if self.app.inventory.count_item(item_id) < qty:
                self.cancel_active_craft("Missing materials")
                return

        for item_id, qty in recipe["inputs"].items():
            self.app.inventory.remove_item(item_id, qty)

        out = recipe["output"]
        self.app.inventory.add_item(out["id"], out["qty"])
        lvl_up = self.app.skills.add_xp(recipe["skill"], recipe["xp"])

        if hasattr(self.app, "quest_manager"):
            self.app.quest_manager.notify_action("craft", out["id"])

        self.app.hud.show_prompt(f"Crafted {recipe['name']}! (+{recipe['xp']} {recipe['skill']} XP)")
        self.app.hud.add_log(f"Crafted {recipe['name']} | +{recipe['xp']} {recipe['skill']} XP")
        if lvl_up > 0:
            self.app.hud.show_prompt(f"{recipe['skill']} level up! Level {self.app.skills.get_level(recipe['skill'])}")
            self.app.hud.add_log(f"{recipe['skill']} level up! Level {self.app.skills.get_level(recipe['skill'])}")

        self._active_craft = None
        self.app.hud.hide_cast_progress()
        self.app.hud.refresh_inventory()
        self.app.hud.refresh_skills()
        self.refresh()

    def _can_access_recipe(self, recipe):
        if recipe["station"] == "any":
            return True
        return self._station_type == recipe["station"]
