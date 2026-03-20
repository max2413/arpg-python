"""Crafting station interactables."""

import json
import os
from panda3d.core import Vec3, NodePath, BillboardEffect, TextNode
from panda3d.bullet import BulletGhostNode, BulletSphereShape

from game.runtime import get_runtime
from game.systems.paths import data_path
from game.world.geometry import make_box_geom, make_cylinder, make_sphere_approx

RECIPES_PATH = data_path("recipes.json")
STATION_PROXIMITY = 5.0

RECIPES = {}

STATION_VISUALS = {
    "anvil": {
        "label": "Anvil",
        "prompt": "Press E to use Anvil",
        "text_color": (0.8, 0.8, 0.9, 1),
        "build": "anvil",
        "label_z": 1.3,
        "label_scale": 0.6,
    },
    "campfire": {
        "label": "Campfire",
        "prompt": "Press E to cook at Campfire",
        "text_color": (1.0, 0.6, 0.2, 1),
        "build": "campfire",
        "label_z": 1.3,
        "label_scale": 0.6,
    },
    "forge": {
        "label": "Forge",
        "prompt": "Press E to use Forge",
        "text_color": (1.0, 0.7, 0.3, 1),
        "build": "forge",
        "label_z": 1.7,
        "label_scale": 0.72,
    },
    "tanning_rack": {
        "label": "Tanning Rack",
        "prompt": "Press E to use Tanning Rack",
        "text_color": (0.86, 0.72, 0.5, 1),
        "build": "rack",
        "label_z": 2.85,
        "label_scale": 1.0,
    },
    "loom": {
        "label": "Loom",
        "prompt": "Press E to use Loom",
        "text_color": (0.86, 0.82, 0.72, 1),
        "build": "loom",
        "label_z": 2.85,
        "label_scale": 1.0,
    },
    "fletching_bench": {
        "label": "Fletching Bench",
        "prompt": "Press E to use Fletching Bench",
        "text_color": (0.72, 0.86, 0.54, 1),
        "build": "bench",
        "label_z": 2.85,
        "label_scale": 1.0,
    },
    "alchemy_table": {
        "label": "Alchemy Table",
        "prompt": "Press E to use Alchemy Table",
        "text_color": (0.72, 0.6, 0.96, 1),
        "build": "alchemy",
        "label_z": 2.85,
        "label_scale": 1.0,
    },
    "enchanting_table": {
        "label": "Enchanting Table",
        "prompt": "Press E to use Enchanting Table",
        "text_color": (0.48, 0.88, 1.0, 1),
        "build": "enchanting",
        "label_z": 2.85,
        "label_scale": 1.0,
    },
}


def load_recipes():
    global RECIPES
    if not os.path.exists(RECIPES_PATH):
        return
    try:
        with open(RECIPES_PATH, "r", encoding="utf-8") as f:
            RECIPES = json.load(f)
    except Exception as e:
        print(f"[crafting] failed to load recipes: {e}")


class CraftingStation:
    def __init__(self, render, bullet_world, pos, station_type):
        self.render = render
        self.bullet_world = bullet_world
        self.pos = Vec3(*pos)
        self.station_type = station_type
        station_meta = STATION_VISUALS[station_type]
        self.prompt_text = station_meta["prompt"]
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
        build_key = STATION_VISUALS[self.station_type]["build"]
        if build_key == "anvil":
            self._build_anvil()
        elif build_key == "campfire":
            self._build_campfire()
        elif build_key == "forge":
            self._build_forge()
        elif build_key == "rack":
            self._build_tanning_rack()
        elif build_key == "loom":
            self._build_loom()
        elif build_key == "bench":
            self._build_fletching_bench()
        elif build_key == "alchemy":
            self._build_alchemy_table()
        elif build_key == "enchanting":
            self._build_enchanting_table()
        self._build_label()

    def _build_ghost(self):
        shape = BulletSphereShape(STATION_PROXIMITY)
        ghost = BulletGhostNode(f"ghost_{self.station_type}")
        ghost.addShape(shape)
        self._ghost_np = self.render.attachNewNode(ghost)
        self._ghost_np.setPos(self.pos.x, self.pos.y + 1.0, self.pos.z)
        self.bullet_world.attachGhost(ghost)

    def update(self, dt, player_pos, hud):
        dx = player_pos.x - self.pos.x
        dz = player_pos.z - self.pos.z
        self._in_range = (dx * dx + dz * dz) <= STATION_PROXIMITY ** 2

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
        runtime = get_runtime()
        crafting_ui = None
        if runtime is not None:
            crafting_ui = runtime.crafting_ui or getattr(runtime.game, "crafting_ui", None)
        if crafting_ui is None:
            return
        self.ui_open = True
        crafting_ui.open(self.station_type, self)

    def close_ui(self):
        runtime = get_runtime()
        crafting_ui = None
        if runtime is not None:
            crafting_ui = runtime.crafting_ui or getattr(runtime.game, "crafting_ui", None)
        self.ui_open = False
        if crafting_ui is not None:
            crafting_ui.hide()

    def remove_from_world(self, hud=None):
        self.close_ui()
        if self._prompt_shown and hud:
            hud.clear_prompt_if(self.prompt_text)
        if self._ghost_np and not self._ghost_np.isEmpty():
            self.bullet_world.removeGhost(self._ghost_np.node())
            self._ghost_np.removeNode()
        self.root.removeNode()

    def _build_label(self):
        station_meta = STATION_VISUALS[self.station_type]
        lbl_node = TextNode(f"{self.station_type}_label")
        lbl_node.setText(station_meta["label"])
        lbl_node.setAlign(TextNode.ACenter)
        lbl_node.setTextColor(*station_meta["text_color"])
        lbl_np = self.root.attachNewNode(lbl_node)
        lbl_np.setPos(0, station_meta["label_z"], 0)
        lbl_np.setScale(station_meta["label_scale"])
        lbl_np.setEffect(BillboardEffect.makePointEye())

    def _build_anvil(self):
        c = (0.2, 0.2, 0.22, 1)
        base = self.root.attachNewNode(make_box_geom(2.4, 1.2, 0.8, c))
        base.setY(0.4)
        top = self.root.attachNewNode(make_box_geom(2.8, 1.0, 0.6, c))
        top.setY(1.1)

    def _build_campfire(self):
        log_c = (0.3, 0.2, 0.1, 1)
        for i in range(4):
            log = self.root.attachNewNode(make_box_geom(1.6, 0.4, 0.4, log_c))
            log.setH(i * 45)
        fire = self.root.attachNewNode(make_sphere_approx(0.4, (1, 0.5, 0, 0.8)))
        fire.setY(0.3)
        fire.setTransparency(True)

    def _build_forge(self):
        body = self.root.attachNewNode(make_box_geom(1.92, 1.44, 1.2, (0.2, 0.18, 0.18, 1)))
        body.setY(0.6)
        lip = self.root.attachNewNode(make_box_geom(1.68, 1.2, 0.24, (0.32, 0.26, 0.24, 1)))
        lip.setY(1.26)
        fire = self.root.attachNewNode(make_sphere_approx(0.42, (1.0, 0.4, 0.1, 0.8)))
        fire.setPos(0, 1.14, 0)

    def _build_tanning_rack(self):
        for x in (-0.45, 0.45):
            post = self.root.attachNewNode(make_cylinder(0.14, 2.4, (0.48, 0.32, 0.18, 1)))
            post.setPos(x, 0, 0)
        beam = self.root.attachNewNode(make_box_geom(2.2, 0.16, 0.16, (0.5, 0.34, 0.2, 1)))
        beam.setPos(0, 2.3, 0)
        hide = self.root.attachNewNode(make_box_geom(1.7, 0.06, 1.5, (0.62, 0.44, 0.28, 1)))
        hide.setPos(0, 1.36, 0.05)

    def _build_loom(self):
        frame_color = (0.56, 0.38, 0.2, 1)
        for x in (-0.55, 0.55):
            post = self.root.attachNewNode(make_box_geom(0.16, 0.16, 2.7, frame_color))
            post.setPos(x, 1.35, 0)
        top = self.root.attachNewNode(make_box_geom(2.4, 0.16, 0.16, frame_color))
        top.setPos(0, 2.64, 0)
        cloth = self.root.attachNewNode(make_box_geom(1.8, 0.06, 1.7, (0.86, 0.82, 0.72, 1)))
        cloth.setPos(0, 1.6, 0.05)

    def _build_worktable_base(self, top_color, leg_color, accent_color=None):
        table = self.root.attachNewNode(make_box_geom(3.2, 1.6, 0.32, top_color))
        table.setY(1.6)
        for x in (-0.65, 0.65):
            for z in (-0.25, 0.25):
                leg = self.root.attachNewNode(make_box_geom(0.16, 0.16, 1.6, leg_color))
                leg.setPos(x * 2.0, 0.8, z * 2.0)
        if accent_color is not None:
            runner = self.root.attachNewNode(make_box_geom(2.3, 0.64, 0.04, accent_color))
            runner.setPos(0, 1.79, 0)

    def _add_fletching_tools(self):
        arrow = self.root.attachNewNode(make_box_geom(1.8, 0.08, 0.08, (0.8, 0.72, 0.46, 1)))
        arrow.setPos(0, 1.84, 0)
        feather = self.root.attachNewNode(make_box_geom(0.36, 0.04, 0.16, (0.9, 0.9, 0.9, 1)))
        feather.setPos(0.7, 1.84, 0)

    def _build_fletching_bench(self):
        self._build_worktable_base((0.46, 0.3, 0.18, 1), (0.36, 0.22, 0.12, 1), accent_color=(0.58, 0.46, 0.24, 1))
        self._add_fletching_tools()

    def _build_alchemy_table(self):
        self._build_worktable_base((0.34, 0.28, 0.24, 1), (0.24, 0.18, 0.14, 1), accent_color=(0.18, 0.20, 0.24, 1))
        flask = self.root.attachNewNode(make_sphere_approx(0.16, (0.2, 0.7, 0.9, 0.85)))
        flask.setPos(-0.7, 1.92, -0.2)
        flask.setTransparency(True)
        flask2 = self.root.attachNewNode(make_sphere_approx(0.12, (0.8, 0.3, 0.9, 0.85)))
        flask2.setPos(0.45, 1.88, 0.15)
        flask2.setTransparency(True)
        burner = self.root.attachNewNode(make_box_geom(0.36, 0.36, 0.12, (0.16, 0.16, 0.18, 1)))
        burner.setPos(0.0, 1.74, -0.25)
        vial = self.root.attachNewNode(make_box_geom(0.18, 0.18, 0.42, (0.28, 0.86, 0.56, 0.9)))
        vial.setPos(0.78, 1.88, -0.05)
        vial.setTransparency(True)
        notes = self.root.attachNewNode(make_box_geom(0.52, 0.32, 0.03, (0.86, 0.82, 0.64, 1.0)))
        notes.setPos(-0.1, 1.82, 0.28)

    def _build_enchanting_table(self):
        self._build_worktable_base((0.24, 0.24, 0.32, 1), (0.2, 0.18, 0.28, 1), accent_color=(0.14, 0.18, 0.32, 1))
        crystal = self.root.attachNewNode(make_sphere_approx(0.18, (0.48, 0.92, 1.0, 0.9)))
        crystal.setPos(0, 1.98, 0)
        crystal.setTransparency(True)
        book = self.root.attachNewNode(make_box_geom(0.45, 0.25, 0.08, (0.34, 0.22, 0.52, 1)))
        book.setPos(-0.72, 1.84, 0.08)
        rune = self.root.attachNewNode(make_box_geom(0.42, 0.42, 0.04, (0.28, 0.74, 0.96, 0.85)))
        rune.setPos(0.62, 1.78, -0.1)
        rune.setTransparency(True)
        candles = self.root.attachNewNode(make_box_geom(0.14, 0.14, 0.26, (0.90, 0.88, 0.68, 1.0)))
        candles.setPos(-0.2, 1.93, -0.3)


class Anvil(CraftingStation):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos, "anvil")


class Campfire(CraftingStation):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos, "campfire")


class Forge(CraftingStation):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos, "forge")


class TanningRack(CraftingStation):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos, "tanning_rack")


class Loom(CraftingStation):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos, "loom")


class FletchingBench(CraftingStation):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos, "fletching_bench")


class AlchemyTable(CraftingStation):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos, "alchemy_table")


class EnchantingTable(CraftingStation):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos, "enchanting_table")
