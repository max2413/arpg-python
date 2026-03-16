"""
crafting.py - Crafting station interactables.
"""

import json
import os
from panda3d.core import Vec3, NodePath, BillboardEffect, TextNode
from panda3d.bullet import BulletGhostNode, BulletSphereShape

from game.world.geometry import make_box_geom, make_cylinder, make_sphere_approx
from game.ui.widgets import DraggableWindow, create_item_icon
from game.systems.inventory import get_item_def

RECIPES_PATH = "data/recipes.json"
STATION_PROXIMITY = 5.0

RECIPES = {}

def load_recipes():
    global RECIPES
    if not os.path.exists(RECIPES_PATH):
        return
    try:
        with open(RECIPES_PATH) as f:
            RECIPES = json.load(f)
    except Exception as e:
        print(f"[crafting] failed to load recipes: {e}")

class CraftingStation:
    def __init__(self, render, bullet_world, pos, station_type, prompt_text):
        self.render = render
        self.bullet_world = bullet_world
        self.pos = Vec3(*pos)
        self.station_type = station_type
        self.prompt_text = prompt_text
        self._in_range = False
        self._prompt_shown = False
        self.ui_open = False
        self._window = None

        self.root = NodePath(f"station_{station_type}")
        self.root.reparentTo(render)
        self.root.setPos(self.pos)

        self._build_visual()
        self._build_ghost()

    def _build_visual(self):
        raise NotImplementedError

    def _build_ghost(self):
        shape = BulletSphereShape(STATION_PROXIMITY)
        ghost = BulletGhostNode(f"ghost_{self.station_type}")
        ghost.addShape(shape)
        self._ghost_np = self.render.attachNewNode(ghost)
        self._ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 1.0)
        self.bullet_world.attachGhost(ghost)

    def update(self, dt, player_pos, hud):
        dx = player_pos.x - self.pos.x
        dy = player_pos.y - self.pos.y
        self._in_range = (dx*dx + dy*dy) <= STATION_PROXIMITY**2

        if self.ui_open:
            if self._prompt_shown:
                hud.clear_prompt_if(self.prompt_text)
                self._prompt_shown = False
            return

        if self._in_range:
            hud.show_prompt(self.prompt_text)
            self._prompt_shown = True
        elif self._prompt_shown:
            hud.clear_prompt_if(self.prompt_text)
            self._prompt_shown = False

        if self.ui_open and not self._in_range:
            self.close_ui()

    def open_ui(self):
        self.ui_open = True
        # UI building will be delegated to a common CraftingUI class later
        # for now, let's just use a stub hook.
        import builtins
        app = builtins.base
        if hasattr(app, "crafting_ui"):
            app.crafting_ui.open(self.station_type, self)

    def close_ui(self):
        self.ui_open = False
        import builtins
        app = builtins.base
        if hasattr(app, "crafting_ui"):
            app.crafting_ui.hide()

    def remove_from_world(self, hud=None):
        self.close_ui()
        if self._prompt_shown and hud:
            hud.clear_prompt_if(self.prompt_text)
        if self._ghost_np and not self._ghost_np.isEmpty():
            self.bullet_world.removeGhost(self._ghost_np.node())
            self._ghost_np.removeNode()
        self.root.removeNode()

class Anvil(CraftingStation):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos, "anvil", "Press E to use Anvil")

    def _build_visual(self):
        # Heavy metal block
        c = (0.2, 0.2, 0.22, 1)
        base = self.root.attachNewNode(make_box_geom(1.2, 0.6, 0.4, c))
        base.setZ(0.2)
        top = self.root.attachNewNode(make_box_geom(1.4, 0.5, 0.3, c))
        top.setZ(0.55)
        
        # Label
        lbl_node = TextNode("anvil_label")
        lbl_node.setText("Anvil")
        lbl_node.setAlign(TextNode.ACenter)
        lbl_node.setTextColor(0.8, 0.8, 0.9, 1)
        lbl_np = self.root.attachNewNode(lbl_node)
        lbl_np.setPos(0, 0, 1.2)
        lbl_np.setScale(0.6)
        lbl_np.setEffect(BillboardEffect.makePointEye())

class Campfire(CraftingStation):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos, "campfire", "Press E to cook at Campfire")

    def _build_visual(self):
        # Logs and a small fire (orange sphere)
        log_c = (0.3, 0.2, 0.1, 1)
        for i in range(4):
            log = self.root.attachNewNode(make_box_geom(0.8, 0.2, 0.2, log_c))
            log.setH(i * 45)
        
        fire = self.root.attachNewNode(make_sphere_approx(0.4, (1, 0.5, 0, 0.8)))
        fire.setZ(0.3)
        fire.setTransparency(True)
        
        # Label
        lbl_node = TextNode("campfire_label")
        lbl_node.setText("Campfire")
        lbl_node.setAlign(TextNode.ACenter)
        lbl_node.setTextColor(1, 0.6, 0.2, 1)
        lbl_np = self.root.attachNewNode(lbl_node)
        lbl_np.setPos(0, 0, 1.0)
        lbl_np.setScale(0.6)
        lbl_np.setEffect(BillboardEffect.makePointEye())
