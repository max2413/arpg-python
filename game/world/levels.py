"""Level builders and active level management.
URSINA Y-UP VERSION
"""

from dataclasses import dataclass, field
import json
import os

from game.services.bank import Bank
from game.services.crafting import (
    AlchemyTable, Anvil, Campfire, EnchantingTable, FletchingBench, Forge, Loom, TanningRack
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

# URSINA Y-UP Vertical offsets
COBBLE_GROUT_Y = 0.07
COBBLE_COLLIDER_Y = 0.09
COBBLE_TILE_Y = 0.16

DEV_ZONE_RESOURCE_ROWS = [
    {
        "z": 26.0,
        "y_offset": 0.12,
        "entries": [
            ("tree", {"scale": 1.5, "item_id": "pine_log"}),
            ("tree", {"scale": 1.5, "item_id": "ash_log"}),
            ("tree", {"scale": 1.5, "item_id": "yew_log"}),
        ],
    },
    {
        "z": 10.0,
        "y_offset": 0.12,
        "entries": [
            ("rock", {"scale": 1.1, "item_id": "copper_ore"}),
            ("rock", {"scale": 1.1, "item_id": "iron_ore"}),
            ("rock", {"scale": 1.1, "item_id": "coal"}),
        ],
    },
    {
        "z": -6.0,
        "y_offset": 0.12,
        "entries": [
            ("herb", {"herb_type": "marigold"}),
            ("herb", {"herb_type": "belladonna"}),
            ("herb", {"herb_type": "bloodmoss"}),
        ],
    },
    {
        "z": -22.0,
        "y_offset": 0.12,
        "entries": [
            ("water", {}),
            ("fishing", {"y_lift": 0.34}),
        ],
    },
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
        for t in self.teleporters: t.remove_from_world(hud)
        for i in self.interactables: i.remove_from_world(hud)
        for h in self.hostiles: h.remove_from_world(hud)
        for r in self.resources: r.remove_from_world()
        for e in self.extras:
            if hasattr(e, "remove_from_world"): e.remove_from_world()
            elif hasattr(e, "destroy"): e.destroy()
            elif hasattr(e, "isEmpty") and not e.isEmpty(): e.removeNode()
        if self.world: self.world.destroy()

class CobblestoneField:
    def __init__(self, render, bullet_world, terrain, center=(0, 0), radius=42.0, tile_size=3.0, gap=0.18):
        self.render = render; self.bullet_world = bullet_world; self.terrain = terrain
        self.center = center; self.radius = radius; self.tile_size = tile_size; self.gap = gap
        self.root = self.render.attachNewNode("cobblestone_field")
        self._colliders = []; self._build()

    def _build(self):
        cx, cz = self.center; flat_y = self.terrain.height_at(cx, cz)
        step = self.tile_size + self.gap; tiles = int((self.radius * 2) / step)
        start_x = cx - (tiles * step) * 0.5 + step * 0.5
        start_z = cz - (tiles * step) * 0.5 + step * 0.5
        pad = tiles * step + self.gap + 0.8
        
        # URSINA Y-UP: Grout on XZ floor
        grout = self.root.attachNewNode(make_box_geom(pad, 0.14, pad, (0.24, 0.24, 0.26, 1.0)))
        grout.setPos(cx, flat_y + COBBLE_GROUT_Y, cz)
        
        self._colliders.append(attach_static_box_collider(self.render, self.bullet_world, "cobble_pad", 
            (cx, flat_y + COBBLE_COLLIDER_Y, cz), (pad, 0.24, pad)))

        for gz in range(tiles):
            for gx in range(tiles):
                x = start_x + gx * step; z = start_z + gz * step
                shade = 0.52 + ((gx * 37 + gz * 19) % 5) * 0.03
                tile = self.root.attachNewNode(make_box_geom(self.tile_size, 0.12, self.tile_size, (shade, shade, shade + 0.02, 1.0)))
                tile.setPos(x, flat_y + COBBLE_TILE_Y, z)

    def remove_from_world(self):
        for c in self._colliders: remove_static_collider(self.bullet_world, c)
        if self.root and not self.root.isEmpty(): self.root.removeNode()

class DevPropCluster:
    def __init__(self, render, pos, kind="crate"):
        self.root = render.attachNewNode(f"dev_prop_{kind}")
        self.root.setPos(*pos)
        if kind == "crate_stack":
            lower = self.root.attachNewNode(make_box_geom(1.2, 1.0, 1.2, (0.42, 0.28, 0.14, 1.0)))
            lower.setY(0.5)
            upper = self.root.attachNewNode(make_box_geom(1.0, 0.9, 1.0, (0.48, 0.32, 0.16, 1.0)))
            upper.setPos(0.0, 1.45, 0.0)
        elif kind == "chair":
            seat = self.root.attachNewNode(make_box_geom(1.0, 0.16, 1.0, (0.38, 0.24, 0.14, 1.0)))
            seat.setY(0.6)
            back = self.root.attachNewNode(make_box_geom(1.0, 1.2, 0.14, (0.34, 0.22, 0.12, 1.0)))
            back.setPos(0.0, 1.18, -0.42)
            for x, z in [(-0.34, -0.34), (0.34, -0.34), (-0.34, 0.34), (0.34, 0.34)]:
                leg = self.root.attachNewNode(make_box_geom(0.14, 0.6, 0.14, (0.28, 0.18, 0.10, 1.0)))
                leg.setPos(x, 0.3, z)

    def remove_from_world(self):
        if self.root and not self.root.isEmpty(): self.root.removeNode()

class LevelManager:
    def __init__(self, render, bullet_world, inventory, seed=42):
        self.render = render; self.bullet_world = bullet_world; self.inventory = inventory; self.seed = seed
        self._active_level = None
        self._registry = {"overworld": self._build_overworld, "dev_zone": self._build_dev_zone}

    def load_level(self, level_id, entry_key="default", hud=None, force_regenerate=False):
        if self._active_level: self._active_level.destroy(hud)
        self._active_level = self._registry[level_id](force_regenerate=force_regenerate)
        return self._active_level.spawn_points.get(entry_key, self._active_level.spawn_points["default"])

    def get_active_level(self): return self._active_level
    def clear_saved_overworld(self):
        if os.path.exists(OVERWORLD_SAVE_PATH): os.remove(OVERWORLD_SAVE_PATH)

    def _load_saved_overworld_layout(self):
        if not os.path.exists(OVERWORLD_SAVE_PATH): return None
        try:
            with open(OVERWORLD_SAVE_PATH) as f: layout = json.load(f)
            return layout if layout.get("seed") == self.seed else None
        except: return None

    def _save_overworld_layout(self, layout):
        os.makedirs(os.path.dirname(OVERWORLD_SAVE_PATH), exist_ok=True)
        try:
            with open(OVERWORLD_SAVE_PATH, "w") as f: json.dump(layout, f)
        except: pass

    def _build_overworld(self, force_regenerate=False):
        world = World(self.render, self.bullet_world, seed=self.seed, world_half=500)
        saved = None if force_regenerate else self._load_saved_overworld_layout()
        resources, hostiles, decor, layout = generate_world(self.render, self.bullet_world, world.terrain, seed=self.seed, layout=saved)
        world.refresh_terrain()
        if force_regenerate or saved is None: self._save_overworld_layout(layout)

        # URSINA Y-UP placement
        bank = Bank(self.render, self.bullet_world, (20, 0, 0), self.inventory)
        vendor = Vendor(self.render, self.bullet_world, (-20, 0, 0), self.inventory, vendor_id="materials_supplier")
        anvil = Anvil(self.render, self.bullet_world, (10, world.terrain.height_at(10, 10), 10))
        campfire = Campfire(self.render, self.bullet_world, (-10, world.terrain.height_at(-10, 10), 10))
        
        tele_pos = (0, world.terrain.height_at(0, 32), 32)
        teleporter = Teleporter(self.render, self.bullet_world, tele_pos, "Press E to enter Dev Zone", "dev_zone", "from_overworld", "Dev Gate")
        
        spawn_points = {
            "default": (0, world.terrain.height_at(0, 0) + 14.0, 0),
            "return_from_dev": (0, world.terrain.height_at(0, 24) + 14.0, 24),
        }
        return LevelInstance(world=world, resources=resources, hostiles=hostiles, interactables=[bank, vendor, anvil, campfire], teleporters=[teleporter], spawn_points=spawn_points, extras=[decor])

    def _build_resource(self, descriptor, pos):
        kind, kwargs = descriptor
        if kind == "tree": return Tree(self.render, self.bullet_world, pos, **kwargs)
        if kind == "rock": return Rock(self.render, self.bullet_world, pos, **kwargs)
        if kind == "herb": return HerbPatch(self.render, self.bullet_world, pos, **kwargs)
        if kind == "water": return WaterSource(self.render, self.bullet_world, pos)
        if kind == "fishing":
            y_lift = kwargs.get("y_lift", 0.0)
            return FishingSpot(self.render, self.bullet_world, (pos[0], pos[1] + y_lift, pos[2]))
        raise ValueError(f"Unknown kind: {kind}")

    def _spawn_resource_row(self, resources, world, z, entries, y_offset=0.0):
        x = -40.0
        for desc in entries:
            y = world.terrain.height_at(x, z) + y_offset
            resources.append(self._build_resource(desc, (x, y, z)))
            x += 10.0

    def _build_dev_zone(self, force_regenerate=False):
        world = World(self.render, self.bullet_world, seed=self.seed ^ 0xABC, world_half=120)
        world.terrain.spawn_flat_radius = 105.0; world.terrain.spawn_blend_radius = 118.0; world.refresh_terrain()
        resources, interactables, extras = [], [], []
        
        cobbles = CobblestoneField(self.render, self.bullet_world, world.terrain, center=(0, 0), radius=58.0)
        extras.append(cobbles)

        tele_pos = (0, world.terrain.height_at(0, 52), 52)
        teleporter = Teleporter(self.render, self.bullet_world, tele_pos, "Press E to return to Overworld", "overworld", "return_from_dev", "Return Gate")

        for row in DEV_ZONE_RESOURCE_ROWS:
            self._spawn_resource_row(resources, world, row["z"], row["entries"], y_offset=row["y_offset"])

        for station_cls, x, z in [ (Anvil, -42, -44), (Forge, -28, -44), (Campfire, -14, -44), (TanningRack, 0, -44), (Loom, 14, -44), (FletchingBench, 28, -44), (AlchemyTable, 42, -44), (EnchantingTable, 56, -44) ]:
            interactables.append(station_cls(self.render, self.bullet_world, (x, world.terrain.height_at(x, z), z)))

        bank_x, bank_z = -30.0, -62.0
        interactables.append(Bank(self.render, self.bullet_world, (bank_x, world.terrain.height_at(bank_x, bank_z), bank_z), self.inventory))

        for vendor_id, x, z, prop_kind, height in [ ("materials_supplier", -8, -62, "crate_stack", 1.95), ("smith_supplier", 10, -62, "chair", 0.75), ("ranger_supplier", 28, -62, "crate_stack", 1.95), ("alchemist_supplier", 46, -62, "chair", 0.75) ]:
            y = world.terrain.height_at(x, z)
            extras.append(DevPropCluster(self.render, (x, y, z), kind=prop_kind))
            interactables.append(Vendor(self.render, self.bullet_world, (x, y + height, z), self.inventory, vendor_id=vendor_id, static_idle=True))

        spawn_points = {
            "default": (0, world.terrain.height_at(0, 44) + 14.0, 44),
            "from_overworld": (0, world.terrain.height_at(0, 44) + 14.0, 44),
        }
        return LevelInstance(world=world, resources=resources, hostiles=[], interactables=interactables, teleporters=[teleporter], spawn_points=spawn_points, extras=extras)
