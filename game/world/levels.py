"""Level builders and active level management."""

from dataclasses import dataclass, field
import json
import os

from game.services.bank import Bank
from game.services.vendor import Vendor
from game.services.crafting import Anvil, Campfire
from game.world.collision import attach_static_box_collider, remove_static_collider
from game.world.geometry import make_box_geom
from game.world.structures import build_structure_shell
from game.world.teleporter import Teleporter
from game.world.world import World
from game.world.worldgen import generate_world

OVERWORLD_SAVE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "overworld_level.json",
)


@dataclass
class LevelInstance:
    world: object
    resources: list
    hostiles: list
    interactables: list
    teleporters: list
    spawn_points: dict
    extras: list = field(default_factory=list)

    def destroy(self, hud=None):
        for teleporter in self.teleporters:
            teleporter.remove_from_world(hud)
        for interactable in self.interactables:
            interactable.remove_from_world(hud)
        for hostile in self.hostiles:
            hostile.remove_from_world(hud)
        for resource in self.resources:
            resource.remove_from_world()
        for extra in self.extras:
            if hasattr(extra, "remove_from_world"):
                extra.remove_from_world()
            elif hasattr(extra, "destroy"):
                extra.destroy()
            elif hasattr(extra, "isEmpty") and not extra.isEmpty():
                extra.removeNode()
        if self.world is not None:
            self.world.destroy()


class CobblestoneField:
    def __init__(self, render, bullet_world, terrain, center=(0, 0), radius=42.0, tile_size=3.0, gap=0.18):
        self.render = render
        self.bullet_world = bullet_world
        self.terrain = terrain
        self.center = center
        self.radius = radius
        self.tile_size = tile_size
        self.gap = gap
        self.root = render.attachNewNode("cobblestone_field")
        self._colliders = []
        self._build()

    def _build(self):
        cx, cy = self.center
        flat_z = self.terrain.height_at(cx, cy)
        step = self.tile_size + self.gap
        tiles_per_side = int((self.radius * 2) / step)
        start_x = cx - (tiles_per_side * step) * 0.5 + step * 0.5
        start_y = cy - (tiles_per_side * step) * 0.5 + step * 0.5

        grout = self.root.attachNewNode(
            make_box_geom(
                tiles_per_side * step + self.gap,
                tiles_per_side * step + self.gap,
                0.08,
                (0.24, 0.24, 0.26, 1.0),
            )
        )
        grout.setPos(cx, cy, flat_z + 0.02)
        self._colliders.append(
            attach_static_box_collider(
                self.render,
                self.bullet_world,
                "cobble_pad",
                (cx, cy, flat_z + 0.04),
                (tiles_per_side * step + self.gap, tiles_per_side * step + self.gap, 0.08),
            )
        )

        for gy in range(tiles_per_side):
            for gx in range(tiles_per_side):
                x = start_x + gx * step
                y = start_y + gy * step
                z = flat_z + 0.10
                tone = (gx * 37 + gy * 19) % 5
                shade = 0.52 + tone * 0.03
                tile = self.root.attachNewNode(
                    make_box_geom(
                        self.tile_size,
                        self.tile_size,
                        0.16,
                        (shade, shade, shade + 0.02, 1.0),
                    )
                )
                tile.setPos(x, y, z)

    def remove_from_world(self):
        for collider in self._colliders:
            remove_static_collider(self.bullet_world, collider)
        self._colliders = []
        if self.root is not None and not self.root.isEmpty():
            self.root.removeNode()


class StructureShellInstance:
    def __init__(self, render, bullet_world, kind, pos, scale=1.0):
        self.render = render
        self.bullet_world = bullet_world
        self.root = render.attachNewNode(f"{kind}_shell")
        shell = build_structure_shell(kind, self.root, render, bullet_world, pos, scale=scale)
        self.anchors = shell["anchors"]
        self._colliders = shell["collision_nodes"]
        self.root.setPos(*pos)

    def remove_from_world(self):
        for collider in self._colliders:
            remove_static_collider(self.bullet_world, collider)
        self._colliders = []
        if self.root is not None and not self.root.isEmpty():
            self.root.removeNode()


class LevelManager:
    def __init__(self, render, bullet_world, inventory, seed=42):
        self.render = render
        self.bullet_world = bullet_world
        self.inventory = inventory
        self.seed = seed
        self._active_level = None
        self._registry = {
            "overworld": self._build_overworld,
            "test_structure": self._build_test_structure,
        }

    def load_level(self, level_id, entry_key="default", hud=None, force_regenerate=False):
        if self._active_level is not None:
            self._active_level.destroy(hud)
        builder = self._registry[level_id]
        self._active_level = builder(force_regenerate=force_regenerate)
        return self._active_level.spawn_points.get(entry_key, self._active_level.spawn_points["default"])

    def get_active_level(self):
        return self._active_level

    def clear_saved_overworld(self):
        if os.path.exists(OVERWORLD_SAVE_PATH):
            os.remove(OVERWORLD_SAVE_PATH)
            print(f"[level-cache] removed overworld cache: {OVERWORLD_SAVE_PATH}")
        else:
            print(f"[level-cache] no overworld cache to remove: {OVERWORLD_SAVE_PATH}")

    def _load_saved_overworld_layout(self):
        if not os.path.exists(OVERWORLD_SAVE_PATH):
            print(f"[level-cache] overworld cache missing: {OVERWORLD_SAVE_PATH}")
            return None
        try:
            with open(OVERWORLD_SAVE_PATH) as handle:
                layout = json.load(handle)
        except Exception as exc:
            print(f"[level-cache] failed to read overworld cache: {exc}")
            return None
        if layout.get("seed") != self.seed:
            print(
                f"[level-cache] overworld cache seed mismatch: "
                f"cached={layout.get('seed')} current={self.seed}"
            )
            return None
        print(f"[level-cache] loaded overworld cache: {OVERWORLD_SAVE_PATH}")
        return layout

    def _save_overworld_layout(self, layout):
        os.makedirs(os.path.dirname(OVERWORLD_SAVE_PATH), exist_ok=True)
        try:
            with open(OVERWORLD_SAVE_PATH, "w") as handle:
                json.dump(layout, handle)
            print(f"[level-cache] saved overworld cache: {OVERWORLD_SAVE_PATH}")
        except Exception as exc:
            print(f"[level-cache] failed to save overworld cache: {exc}")

    def _build_overworld(self, force_regenerate=False):
        world = World(self.render, self.bullet_world, seed=self.seed, world_half=500)
        saved_layout = None if force_regenerate else self._load_saved_overworld_layout()
        if force_regenerate:
            print("[level] regenerating overworld (forced)")
        elif saved_layout is None:
            print("[level] regenerating overworld (no saved layout or seed mismatch)")
        else:
            print("[level] loading overworld from cached layout")
        resources, hostiles, decor_root, layout = generate_world(
            self.render,
            self.bullet_world,
            world.terrain,
            seed=self.seed,
            layout=saved_layout,
        )
        world.refresh_terrain()
        if force_regenerate or saved_layout is None:
            self._save_overworld_layout(layout)

        bank = Bank(self.render, self.bullet_world, (20, 0, 0), self.inventory)
        vendor = Vendor(self.render, self.bullet_world, (-20, 0, 0), self.inventory)
        anvil = Anvil(self.render, self.bullet_world, (10, 10, world.terrain.height_at(10, 10)))
        campfire = Campfire(self.render, self.bullet_world, (-10, 10, world.terrain.height_at(-10, 10)))
        teleporter_pos = (0, 32, world.terrain.height_at(0, 32))
        teleporter = Teleporter(
            self.render,
            self.bullet_world,
            teleporter_pos,
            "Press E to enter Test Structure",
            "test_structure",
            "from_overworld",
            "Test Gate",
        )
        spawn_points = {
            "default": (0, 0, world.terrain.height_at(0, 0) + 14.0),
            "return_from_test": (0, 24, world.terrain.height_at(0, 24) + 14.0),
        }
        return LevelInstance(
            world=world,
            resources=resources,
            hostiles=hostiles,
            interactables=[bank, vendor, anvil, campfire],
            teleporters=[teleporter],
            spawn_points=spawn_points,
            extras=[decor_root],
        )

    def _build_test_structure(self, force_regenerate=False):
        world = World(self.render, self.bullet_world, seed=self.seed ^ 0xABC, world_half=90)
        world.terrain.spawn_flat_radius = 68.0
        world.terrain.spawn_blend_radius = 88.0
        world.refresh_terrain()

        cobbles = CobblestoneField(self.render, self.bullet_world, world.terrain, center=(0, 0), radius=44.0)
        structure_pos = (0, 0, world.terrain.height_at(0, 0))
        hall = StructureShellInstance(
            self.render,
            self.bullet_world,
            "open_stone_hall",
            structure_pos,
            scale=1.0,
        )
        teleporter_pos = (0, 28, world.terrain.height_at(0, 28))
        teleporter = Teleporter(
            self.render,
            self.bullet_world,
            teleporter_pos,
            "Press E to return to Overworld",
            "overworld",
            "return_from_test",
            "Return Gate",
        )
        spawn_points = {
            "default": (0, -18, world.terrain.height_at(0, -18) + 14.0),
            "from_overworld": (0, -18, world.terrain.height_at(0, -18) + 14.0),
        }
        return LevelInstance(
            world=world,
            resources=[],
            hostiles=[],
            interactables=[],
            teleporters=[teleporter],
            spawn_points=spawn_points,
            extras=[cobbles, hall],
        )
