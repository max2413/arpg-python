"""Level builders and active level management."""

from dataclasses import dataclass, field
import json
import os

from game.services.bank import Bank
from game.services.crafting import (
    AlchemyTable,
    Anvil,
    Campfire,
    EnchantingTable,
    FletchingBench,
    Forge,
    Loom,
    TanningRack,
)
from game.services.vendor import Vendor
from game.systems.paths import cache_path
from game.world.collision import attach_static_box_collider, remove_static_collider
from game.world.geometry import make_box_geom
from game.world.resources import FishingSpot, HerbPatch, Rock, Tree, WaterSource
from game.world.teleporter import Teleporter
from game.world.world import World
from game.world.worldgen import generate_world

OVERWORLD_SAVE_PATH = cache_path("overworld_level.json")

COBBLE_GROUT_Z = 0.07
COBBLE_COLLIDER_Z = 0.09
COBBLE_TILE_Z = 0.16

DEV_ZONE_RESOURCE_ROWS = [
    {
        "y": 26.0,
        "z_offset": 0.12,
        "entries": [
            ("tree", {"scale": 1.5, "item_id": "pine_log"}),
            ("tree", {"scale": 1.5, "item_id": "ash_log"}),
            ("tree", {"scale": 1.5, "item_id": "yew_log"}),
            ("tree", {"scale": 1.5, "item_id": "magic_log"}),
            ("tree", {"scale": 1.5, "item_id": "elder_log"}),
        ],
    },
    {
        "y": 10.0,
        "z_offset": 0.12,
        "entries": [
            ("rock", {"scale": 1.1, "item_id": "copper_ore"}),
            ("rock", {"scale": 1.1, "item_id": "iron_ore"}),
            ("rock", {"scale": 1.1, "item_id": "coal"}),
            ("rock", {"scale": 1.1, "item_id": "mithril_ore"}),
            ("rock", {"scale": 1.1, "item_id": "adamant_ore"}),
        ],
    },
    {
        "y": -6.0,
        "z_offset": 0.12,
        "entries": [
            ("herb", {"herb_type": "marigold"}),
            ("herb", {"herb_type": "belladonna"}),
            ("herb", {"herb_type": "bloodmoss"}),
            ("herb", {"herb_type": "dragons_tongue"}),
            ("herb", {"herb_type": "starbloom"}),
            ("herb", {"herb_type": "void_spore"}),
        ],
    },
    {
        "y": -22.0,
        "z_offset": 0.12,
        "entries": [
            ("water", {}),
            ("fishing", {"z_lift": 0.34}),
        ],
    },
]

DEV_ZONE_STATIONS = [
    (Anvil, -42.0, -44.0),
    (Forge, -28.0, -44.0),
    (Campfire, -14.0, -44.0),
    (TanningRack, 0.0, -44.0),
    (Loom, 14.0, -44.0),
    (FletchingBench, 28.0, -44.0),
    (AlchemyTable, 42.0, -44.0),
    (EnchantingTable, 56.0, -44.0),
]

DEV_ZONE_VENDORS = [
    ("materials_supplier", -8.0, -62.0, "crate_stack", 1.95),
    ("smith_supplier", 10.0, -62.0, "chair", 0.75),
    ("ranger_supplier", 28.0, -62.0, "crate_stack", 1.95),
    ("alchemist_supplier", 46.0, -62.0, "chair", 0.75),
]


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

        pad_size = tiles_per_side * step + self.gap + 0.8
        grout = self.root.attachNewNode(
            make_box_geom(
                pad_size,
                pad_size,
                0.14,
                (0.24, 0.24, 0.26, 1.0),
            )
        )
        grout.setPos(cx, cy, flat_z + COBBLE_GROUT_Z)
        tile_z = flat_z + COBBLE_TILE_Z
        self._colliders.append(
            attach_static_box_collider(
                self.render,
                self.bullet_world,
                "cobble_pad",
                (cx, cy, flat_z + COBBLE_COLLIDER_Z),
                (pad_size, pad_size, 0.24),
            )
        )

        for gy in range(tiles_per_side):
            for gx in range(tiles_per_side):
                x = start_x + gx * step
                y = start_y + gy * step
                tone = (gx * 37 + gy * 19) % 5
                shade = 0.52 + tone * 0.03
                tile = self.root.attachNewNode(
                    make_box_geom(self.tile_size, self.tile_size, 0.12, (shade, shade, shade + 0.02, 1.0))
                )
                tile.setPos(x, y, tile_z)

    def remove_from_world(self):
        for collider in self._colliders:
            remove_static_collider(self.bullet_world, collider)
        self._colliders = []
        if self.root is not None and not self.root.isEmpty():
            self.root.removeNode()


class DevPropCluster:
    def __init__(self, render, pos, kind="crate"):
        self.root = render.attachNewNode(f"dev_prop_{kind}")
        self.root.setPos(*pos)
        if kind == "crate_stack":
            lower = self.root.attachNewNode(make_box_geom(1.2, 1.2, 1.0, (0.42, 0.28, 0.14, 1.0)))
            lower.setZ(0.5)
            upper = self.root.attachNewNode(make_box_geom(1.0, 1.0, 0.9, (0.48, 0.32, 0.16, 1.0)))
            upper.setPos(0.0, 0.0, 1.45)
        elif kind == "chair":
            seat = self.root.attachNewNode(make_box_geom(1.0, 1.0, 0.16, (0.38, 0.24, 0.14, 1.0)))
            seat.setZ(0.6)
            back = self.root.attachNewNode(make_box_geom(1.0, 0.14, 1.2, (0.34, 0.22, 0.12, 1.0)))
            back.setPos(0.0, -0.42, 1.18)
            for x in (-0.34, 0.34):
                for y in (-0.34, 0.34):
                    leg = self.root.attachNewNode(make_box_geom(0.14, 0.14, 0.6, (0.28, 0.18, 0.10, 1.0)))
                    leg.setPos(x, y, 0.3)

    def remove_from_world(self):
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
            "dev_zone": self._build_dev_zone,
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
            print(f"[level-cache] overworld cache seed mismatch: cached={layout.get('seed')} current={self.seed}")
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
        vendor = Vendor(self.render, self.bullet_world, (-20, 0, 0), self.inventory, vendor_id="materials_supplier")
        anvil = Anvil(self.render, self.bullet_world, (10, 10, world.terrain.height_at(10, 10)))
        campfire = Campfire(self.render, self.bullet_world, (-10, 10, world.terrain.height_at(-10, 10)))
        teleporter_pos = (0, 32, world.terrain.height_at(0, 32))
        teleporter = Teleporter(
            self.render,
            self.bullet_world,
            teleporter_pos,
            "Press E to enter Dev Zone",
            "dev_zone",
            "from_overworld",
            "Dev Gate",
        )
        spawn_points = {
            "default": (0, 0, world.terrain.height_at(0, 0) + 14.0),
            "return_from_dev": (0, 24, world.terrain.height_at(0, 24) + 14.0),
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

    def _build_resource(self, descriptor, pos):
        kind, kwargs = descriptor
        if kind == "tree":
            return Tree(self.render, self.bullet_world, pos, **kwargs)
        if kind == "rock":
            return Rock(self.render, self.bullet_world, pos, **kwargs)
        if kind == "herb":
            return HerbPatch(self.render, self.bullet_world, pos, **kwargs)
        if kind == "water":
            return WaterSource(self.render, self.bullet_world, pos)
        if kind == "fishing":
            z_lift = kwargs.get("z_lift", 0.0)
            return FishingSpot(self.render, self.bullet_world, (pos[0], pos[1], pos[2] + z_lift))
        raise ValueError(f"Unknown dev-zone resource kind: {kind}")

    def _spawn_resource_row(self, resources, world, y, entries, z_offset=0.0):
        x = -40.0
        for descriptor in entries:
            z = world.terrain.height_at(x, y) + z_offset
            resources.append(self._build_resource(descriptor, (x, y, z)))
            x += 10.0

    def _build_dev_zone(self, force_regenerate=False):
        world = World(self.render, self.bullet_world, seed=self.seed ^ 0xABC, world_half=120)
        world.terrain.spawn_flat_radius = 105.0
        world.terrain.spawn_blend_radius = 118.0
        world.refresh_terrain()

        resources = []
        interactables = []
        extras = []

        cobbles = CobblestoneField(self.render, self.bullet_world, world.terrain, center=(0, 0), radius=58.0)
        extras.append(cobbles)

        teleporter_pos = (0, 52, world.terrain.height_at(0, 52))
        teleporter = Teleporter(
            self.render,
            self.bullet_world,
            teleporter_pos,
            "Press E to return to Overworld",
            "overworld",
            "return_from_dev",
            "Return Gate",
        )

        for row in DEV_ZONE_RESOURCE_ROWS:
            self._spawn_resource_row(resources, world, row["y"], row["entries"], z_offset=row["z_offset"])

        for station_cls, x, y in DEV_ZONE_STATIONS:
            interactables.append(station_cls(self.render, self.bullet_world, (x, y, world.terrain.height_at(x, y))))

        bank_x, bank_y = -30.0, -62.0
        interactables.append(Bank(self.render, self.bullet_world, (bank_x, bank_y, world.terrain.height_at(bank_x, bank_y)), self.inventory))

        for vendor_id, x, y, prop_kind, height in DEV_ZONE_VENDORS:
            z = world.terrain.height_at(x, y)
            extras.append(DevPropCluster(self.render, (x, y, z), kind=prop_kind))
            interactables.append(
                Vendor(
                    self.render,
                    self.bullet_world,
                    (x, y, z + height),
                    self.inventory,
                    vendor_id=vendor_id,
                    static_idle=True,
                )
            )

        spawn_points = {
            "default": (0, 44, world.terrain.height_at(0, 44) + 14.0),
            "from_overworld": (0, 44, world.terrain.height_at(0, 44) + 14.0),
        }
        return LevelInstance(
            world=world,
            resources=resources,
            hostiles=[],
            interactables=interactables,
            teleporters=[teleporter],
            spawn_points=spawn_points,
            extras=extras,
        )
