"""Procedural world generation with terrain-aware placement and decals.
URSINA Y-UP VERSION
"""

import math
import random

from panda3d.core import (
    GeomVertexFormat,
    GeomVertexData,
    GeomVertexWriter,
    GeomTriangles,
    Geom,
    GeomNode,
    TransparencyAttrib,
)

from game.entities.creatures import Creature
from game.world.resources import FishingSpot, HerbPatch, Rock, Tree

WORLD_HALF = 500
SAFE_RADIUS = 50

FOREST_CLUSTERS = 6
TREES_PER_CLUSTER_MIN = 30
TREES_PER_CLUSTER_MAX = 50
CLUSTER_RADIUS = 40
TREE_MIN_SPACING = 3.0
TREE_MAX_SLOPE = 0.35
TREE_BASE_SCALE = 2.0
TREE_SCALE_VARIATION = 0.20

ORE_PATCHES = 5
ROCKS_PER_PATCH_MIN = 5
ROCKS_PER_PATCH_MAX = 10
PATCH_RADIUS = 20
ROCK_MIN_SPACING = 2.0
ROCK_MAX_SLOPE = 0.45
ROCK_BASE_SCALE = 1.2
ROCK_SCALE_VARIATION = 0.20

RIVER_COUNT = 3
RIVER_POINTS = 40
RIVER_DECAL_STEPS = 120
FISHING_SPACING = 4.0
RIVER_WIDTH = 13.5

HOSTILE_COUNT = 4
RANGER_COUNT = 3
WOLF_COUNT = 2
DEER_COUNT = 5
HOSTILE_MIN_SPACING = 18.0
HOSTILE_PATROL_RADIUS = 18.0
HOSTILE_MAX_SLOPE = 0.28

FOREST_DRESSING_PATCHES = 18
HERBS_PER_CLUSTER_MIN = 4
HERBS_PER_CLUSTER_MAX = 8
HERB_MIN_SPACING = 4.0

RIVER_COLOR = (0.10, 0.28, 0.55, 0.96)
FOREST_FLOOR_COLOR = (0.17, 0.14, 0.07, 0.08)
ORE_ACCENT_COLOR = (0.54, 0.45, 0.27, 0.14)
# URSINA Y-UP
RIVER_DECAL_Y = 0.06
FOREST_DECAL_Y = 0.05
FISHING_BANK_OFFSET = RIVER_WIDTH * 0.56
FISHING_PATH_JITTER = 4.0


def generate_world(render, bullet_world, terrain, seed=42, parent=None, layout=None):
    scene_root = parent if parent is not None else render
    decor_root = scene_root.attachNewNode("worldgen_decor")
    occupied = []
    resources = []
    hostiles = []
    load_mode = "cached" if layout is not None else "generated"
    if layout is None:
        cluster_centers = []
        forest_centers = []
        ore_centers = []

        _generate_forests(random.Random(seed ^ 0x1111), scene_root, bullet_world, terrain, occupied, resources, forest_centers, cluster_centers)
        _generate_ore_patches(random.Random(seed ^ 0x2222), scene_root, bullet_world, terrain, occupied, resources, ore_centers, cluster_centers)

        river_paths = _generate_river_paths(random.Random(seed ^ 0x3333))
        terrain.set_river_paths(river_paths, RIVER_WIDTH)
        terrain.set_forest_patches([(cx, cz, CLUSTER_RADIUS + 16.0) for cx, cz in forest_centers])
        terrain.set_ore_patches([(cx, cz, PATCH_RADIUS + 8.0) for cx, cz in ore_centers])
        _reground_resources(resources, terrain)

        resources, hostiles = _cull_land_on_water(resources, hostiles, terrain)

        _generate_river_spots(random.Random(seed ^ 0x6666), scene_root, bullet_world, terrain, occupied, resources, river_paths)
        _generate_hostiles(random.Random(seed ^ 0x4444), scene_root, bullet_world, terrain, occupied, hostiles)
        _reground_hostiles(hostiles)

        for cx, cz in ore_centers:
            _place_ore_accent(decor_root, terrain, random.Random((seed ^ 0x7777) + int(cx * 3) + int(cz * 5)), cx, cz, PATCH_RADIUS + 4.0)

        decor_rng = random.Random(seed ^ 0x5555)
        for cx, cz in forest_centers:
            _place_forest_floor(decor_root, terrain, decor_rng, cx, cz, CLUSTER_RADIUS * 0.9)
            _generate_herbs(random.Random(seed ^ 0x8888), scene_root, bullet_world, terrain, occupied, resources, cx, cz)

        for path in river_paths:
            _place_river_decal(decor_root, terrain, path, RIVER_WIDTH, RIVER_COLOR)
        layout = _build_layout(seed, river_paths, forest_centers, ore_centers, resources, hostiles)
    else:
        river_paths = [[tuple(point) for point in path] for path in layout.get("river_paths", [])]
        forest_centers = [tuple(center) for center in layout.get("forest_centers", [])]
        ore_centers = [tuple(center) for center in layout.get("ore_centers", [])]
        terrain.set_river_paths(river_paths, RIVER_WIDTH)
        terrain.set_forest_patches([(cx, cz, CLUSTER_RADIUS + 16.0) for cx, cz in forest_centers])
        terrain.set_ore_patches([(cx, cz, PATCH_RADIUS + 8.0) for cx, cz in ore_centers])

        for entry in layout.get("resources", []):
            kind = entry["type"]
            pos = tuple(entry["pos"]) # (x, y, z)
            scale = entry.get("scale", 1.0)
            if kind == "tree":
                resources.append(Tree(scene_root, bullet_world, pos, scale=scale, item_id=entry.get("item_id", "pine_log")))
            elif kind == "rock":
                resources.append(Rock(scene_root, bullet_world, pos, scale=scale, item_id=entry.get("item_id", "copper_ore")))
            elif kind == "fishing":
                resources.append(FishingSpot(scene_root, bullet_world, pos))
            elif kind == "herb":
                resources.append(HerbPatch(scene_root, bullet_world, pos, herb_type=entry.get("item_id", "marigold")))

        for entry in layout.get("hostiles", []):
            kind = entry["type"]
            pos = tuple(entry["pos"])
            patrol_center = tuple(entry.get("patrol_center", entry["pos"]))
            level = entry.get("level")
            level_range = entry.get("level_range")
            role = entry.get("role")
            if level_range: level_range = tuple(level_range)

            hostiles.append(Creature(scene_root, pos, creature_id=kind, level=level, level_range=level_range, role=role, patrol_center=patrol_center, terrain=terrain, bullet_world=bullet_world))

        for cx, cz in ore_centers:
            _place_ore_accent(decor_root, terrain, random.Random((seed ^ 0x7777) + int(cx * 3) + int(cz * 5)), cx, cz, PATCH_RADIUS + 4.0)
        decor_rng = random.Random(seed ^ 0x5555)
        for cx, cz in forest_centers:
            _place_forest_floor(decor_root, terrain, decor_rng, cx, cz, CLUSTER_RADIUS * 0.9)
        for path in river_paths:
            _place_river_decal(decor_root, terrain, path, RIVER_WIDTH, RIVER_COLOR)

    trees = sum(1 for r in resources if isinstance(r, Tree))
    rocks = sum(1 for r in resources if isinstance(r, Rock))
    fish = sum(1 for r in resources if isinstance(r, FishingSpot))
    print(f"[worldgen:{load_mode}] trees={trees}  rocks={rocks}  fishing_spots={fish}  hostiles={len(hostiles)}  rivers={len(river_paths)}")
    return resources, hostiles, decor_root, layout


def _build_layout(seed, river_paths, forest_centers, ore_centers, resources, hostiles):
    layout = {
        "seed": seed,
        "river_paths": [[[x, z] for x, z in path] for path in river_paths],
        "forest_centers": [[x, z] for x, z in forest_centers],
        "ore_centers": [[x, z] for x, z in ore_centers],
        "resources": [],
        "hostiles": [],
    }
    for resource in resources:
        entry = {"pos": [resource.pos.x, resource.pos.y, resource.pos.z]}
        if isinstance(resource, Tree):
            entry["type"] = "tree"; entry["scale"] = resource.scale; entry["item_id"] = resource.item_id
        elif isinstance(resource, Rock):
            entry["type"] = "rock"; entry["scale"] = resource.scale; entry["item_id"] = resource.item_id
        elif isinstance(resource, FishingSpot): entry["type"] = "fishing"
        elif isinstance(resource, HerbPatch): entry["type"] = "herb"; entry["item_id"] = resource.item_id
        else: continue
        layout["resources"].append(entry)
    for hostile in hostiles:
        entry = {
            "type": hostile.creature_id,
            "pos": [hostile.x, hostile.y, hostile.z],
            "patrol_center": [hostile.patrol_center.x, hostile.patrol_center.y, hostile.patrol_center.z],
        }
        if hasattr(hostile, "_level_range") and hostile._level_range: entry["level_range"] = list(hostile._level_range)
        if hasattr(hostile, "_current_level"): entry["level"] = hostile._current_level
        if hasattr(hostile, "_role_override") and hostile._role_override: entry["role"] = hostile._role_override
        layout["hostiles"].append(entry)
    return layout


def _place_river_decal(parent, terrain, path, half_width, color):
    if len(path) < 2: return
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("river_decal", fmt, Geom.UHStatic)
    vdata.setNumRows(len(path) * 2)
    vw = GeomVertexWriter(vdata, "vertex"); nw = GeomVertexWriter(vdata, "normal"); cw = GeomVertexWriter(vdata, "color")

    def _perp(ax, az, bx, bz):
        dx, dz = bx - ax, bz - az
        length = math.sqrt(dx * dx + dz * dz) or 1.0
        return -dz / length, dx / length

    for i, (x, z) in enumerate(path):
        if i == 0: px, pz = _perp(path[0][0], path[0][1], path[1][0], path[1][1])
        elif i == len(path) - 1: px, pz = _perp(path[-2][0], path[-2][1], path[-1][0], path[-1][1])
        else:
            p1x, p1z = _perp(path[i - 1][0], path[i - 1][1], x, z)
            p2x, p2z = _perp(x, z, path[i + 1][0], path[i + 1][1])
            px = (p1x + p2x) * 0.5; pz = (p1z + p2z) * 0.5
            length = math.sqrt(px * px + pz * pz) or 1.0
            px /= length; pz /= length

        for side in (-1, 1):
            vx = x + side * px * half_width
            vz = z + side * pz * half_width
            vy = terrain.height_at(x, z) + RIVER_DECAL_Y
            vw.addData3(vx, vy, vz); nw.addData3(0, 1, 0); cw.addData4(*color)

    tris = GeomTriangles(Geom.UHStatic)
    for i in range(len(path) - 1):
        base = i * 2
        tris.addVertices(base, base + 1, base + 2)
        tris.addVertices(base + 1, base + 3, base + 2)

    geom = Geom(vdata); geom.addPrimitive(tris)
    node = GeomNode("river_decal"); node.addGeom(geom)
    np = parent.attachNewNode(node); np.setBin("fixed", 15); np.setDepthOffset(8); np.setTwoSided(True); np.setTransparency(TransparencyAttrib.MAlpha)


def _place_circle_decal(parent, terrain, cx, cz, radius, color, y_offset, segments=24):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("terrain_decal", fmt, Geom.UHStatic)
    vdata.setNumRows(segments + 1)
    vw = GeomVertexWriter(vdata, "vertex"); nw = GeomVertexWriter(vdata, "normal"); cw = GeomVertexWriter(vdata, "color")

    center_y = terrain.height_at(cx, cz) + y_offset
    nx, ny, nz = terrain.normal_at(cx, cz) # assumed (nx, ny, vertical_z) -> we want (nx, vertical_z, ny)
    vw.addData3(cx, center_y, cz); nw.addData3(nx, nz, ny); cw.addData4(*color)

    for i in range(segments):
        angle = math.radians(i * 360.0 / segments)
        vx = cx + radius * math.cos(angle)
        vz = cz + radius * math.sin(angle)
        vy = terrain.height_at(vx, vz) + y_offset
        nx, ny, nz = terrain.normal_at(vx, vz)
        vw.addData3(vx, vy, vz); nw.addData3(nx, nz, ny); cw.addData4(*color)

    tris = GeomTriangles(Geom.UHStatic)
    for i in range(segments): tris.addVertices(0, i + 1, ((i + 1) % segments) + 1)
    geom = Geom(vdata); geom.addPrimitive(tris)
    node = GeomNode("terrain_decal"); node.addGeom(geom)
    np = parent.attachNewNode(node); np.setBin("fixed", 15); np.setDepthOffset(4); np.setTransparency(TransparencyAttrib.MAlpha)


def _place_forest_floor(parent, terrain, rng, cx, cz, radius):
    litter_colors = [(0.21, 0.17, 0.08, 0.09), (0.18, 0.14, 0.06, 0.08), (0.14, 0.16, 0.08, 0.07)]
    for _ in range(FOREST_DRESSING_PATCHES * 4):
        angle = rng.uniform(0.0, math.tau)
        dist = rng.uniform(0.0, radius)
        x = cx + math.cos(angle) * dist
        z = cz + math.sin(angle) * dist
        if not _in_bounds(x, z): continue
        if terrain.is_river(x, z, margin=2.0): continue
        size = rng.uniform(0.8, 2.2); color = litter_colors[rng.randrange(len(litter_colors))]
        _place_circle_decal(parent, terrain, x, z, size, color, FOREST_DECAL_Y, segments=8)


def _place_ore_accent(parent, terrain, rng, cx, cz, radius):
    for _ in range(10):
        angle = rng.uniform(0.0, math.tau)
        dist = rng.uniform(0.0, radius)
        x = cx + math.cos(angle) * dist
        z = cz + math.sin(angle) * dist
        if not _in_bounds(x, z): continue
        if terrain.is_river(x, z, margin=1.0): continue
        size = rng.uniform(1.4, 4.6)
        _place_circle_decal(parent, terrain, x, z, size, ORE_ACCENT_COLOR, FOREST_DECAL_Y - 0.01, segments=10)


def _cull_land_on_water(resources, hostiles, terrain):
    kept_r = []
    for r in resources:
        if isinstance(r, (Tree, Rock)) and terrain.is_river(r.pos.x, r.pos.z, margin=0.5):
            r.remove_from_world(); continue
        kept_r.append(r)
    kept_h = []
    for h in hostiles:
        if terrain.is_river(h.x, h.z, margin=1.0):
            h.remove_from_world(); continue
        kept_h.append(h)
    return kept_r, kept_h


def _reground_resources(resources, terrain):
    for r in resources:
        if isinstance(r, FishingSpot): continue
        y = terrain.height_at(r.pos.x, r.pos.z)
        r.set_ground_pos((r.pos.x, y, r.pos.z))


def _reground_hostiles(hostiles):
    for h in hostiles: h.reground()


def _in_safe_zone(x, z): return (x * x + z * z) <= (SAFE_RADIUS * SAFE_RADIUS)
def _in_bounds(x, z, margin=5): limit = WORLD_HALF - margin; return -limit <= x <= limit and -limit <= z <= limit
def _has_conflict(x, z, min_s, occupied):
    sq = min_s * min_s
    for ox, oz in occupied:
        if (x-ox)**2 + (z-oz)**2 < sq: return True
    return False

def _is_terrain_valid(terrain, x, z, max_s, margin=0.0):
    if terrain.is_river(x, z, margin=margin): return False
    return terrain.slope_at(x, z) <= max_s

def _try_place(rng, cx, cz, radius, min_s, occupied, terrain, max_s, max_attempts=200):
    for _ in range(max_attempts):
        angle = rng.uniform(0.0, math.tau); dist = rng.uniform(0.0, radius)
        x = cx + dist * math.cos(angle); z = cz + dist * math.sin(angle)
        if not _in_bounds(x, z) or _in_safe_zone(x, z) or _has_conflict(x, z, min_s, occupied): continue
        if not _is_terrain_valid(terrain, x, z, max_s, margin=RIVER_WIDTH * 0.4): continue
        return (x, z)
    return None

def _edge_point(rng, edge):
    rim = rng.uniform(450, 480); spread = rng.uniform(-400, 400)
    if edge == 0: return (spread, rim)
    if edge == 1: return (rim, spread)
    if edge == 2: return (spread, -rim)
    return (-rim, spread)

def _pick_cluster_center(rng, terrain, cluster_centers, min_sep, min_dist, max_dist, max_slope):
    for _ in range(120):
        angle = rng.uniform(0.0, math.tau); dist = rng.uniform(min_dist, max_dist)
        cx = dist * math.cos(angle); cz = dist * math.sin(angle)
        if not _in_bounds(cx, cz, margin=CLUSTER_RADIUS + 10) or _has_conflict(cx, cz, min_sep, cluster_centers): continue
        if not _is_terrain_valid(terrain, cx, cz, max_slope, margin=RIVER_WIDTH): continue
        return (cx, cz)
    return None

def _generate_forests(rng, render, bullet_world, terrain, occupied, resources, forest_centers, cluster_centers):
    min_sep = CLUSTER_RADIUS + PATCH_RADIUS + 10.0
    for _ in range(FOREST_CLUSTERS):
        center = _pick_cluster_center(rng, terrain, cluster_centers, min_sep, 100.0, 430.0, TREE_MAX_SLOPE)
        if center is None: continue
        cx, cz = center; cluster_centers.append(center); forest_centers.append(center)
        count = rng.randint(TREES_PER_CLUSTER_MIN, TREES_PER_CLUSTER_MAX)
        for _ in range(count):
            pos = _try_place(rng, cx, cz, CLUSTER_RADIUS, TREE_MIN_SPACING, occupied, terrain, TREE_MAX_SLOPE)
            if pos is None: continue
            x, z = pos; y = terrain.height_at(x, z)
            scale = rng.uniform(TREE_BASE_SCALE * 0.8, TREE_BASE_SCALE * 1.2)
            occupied.append((x, z))
            tree_item = rng.choices(["pine_log", "ash_log", "yew_log"], weights=(0.62, 0.28, 0.10), k=1)[0]
            resources.append(Tree(render, bullet_world, (x, y, z), scale=scale, item_id=tree_item))

def _generate_ore_patches(rng, render, bullet_world, terrain, occupied, resources, ore_centers, cluster_centers):
    min_sep = CLUSTER_RADIUS + PATCH_RADIUS + 10.0
    for _ in range(ORE_PATCHES):
        center = _pick_cluster_center(rng, terrain, cluster_centers, min_sep, 80.0, 430.0, ROCK_MAX_SLOPE)
        if center is None: continue
        cx, cz = center; cluster_centers.append(center); ore_centers.append(center)
        count = rng.randint(ROCKS_PER_PATCH_MIN, ROCKS_PER_PATCH_MAX)
        for _ in range(count):
            pos = _try_place(rng, cx, cz, PATCH_RADIUS, ROCK_MIN_SPACING, occupied, terrain, ROCK_MAX_SLOPE)
            if pos is None: continue
            x, z = pos; y = terrain.height_at(x, z)
            scale = rng.uniform(ROCK_BASE_SCALE * 0.8, ROCK_BASE_SCALE * 1.2)
            occupied.append((x, z))
            ore_item = rng.choices(["copper_ore", "iron_ore", "coal"], weights=(0.58, 0.27, 0.15), k=1)[0]
            resources.append(Rock(render, bullet_world, (x, y, z), scale=scale, item_id=ore_item))

def _generate_hostiles(rng, render, bullet_world, terrain, occupied, hostiles):
    def _spawn(count, creature_id):
        for _ in range(count):
            for _ in range(150):
                angle = rng.uniform(0.0, math.tau); dist = rng.uniform(100.0, 430.0)
                x = dist * math.cos(angle); z = dist * math.sin(angle)
                if _has_conflict(x, z, HOSTILE_MIN_SPACING, occupied) or not _in_bounds(x, z, margin=HOSTILE_PATROL_RADIUS + 5): continue
                if not _is_terrain_valid(terrain, x, z, HOSTILE_MAX_SLOPE, margin=RIVER_WIDTH * 0.8): continue
                y = terrain.height_at(x, z); occupied.append((x, z))
                base_lvl = int(1 + (dist - 100) / 330 * 14)
                level_range = (max(1, base_lvl - 1), min(20, base_lvl + 2))
                from game.entities.creatures import CREATURE_DEFS
                c_data = CREATURE_DEFS.get(creature_id, {})
                role = c_data.get("role", "normal")
                if role == "critter": level_range = (1, 1)
                hostiles.append(Creature(render, (x, y, z), creature_id=creature_id, level_range=level_range, patrol_center=(x, y, z), terrain=terrain, bullet_world=bullet_world))
                break
    _spawn(HOSTILE_COUNT, "scout"); _spawn(RANGER_COUNT, "ranger"); _spawn(WOLF_COUNT, "wolf"); _spawn(DEER_COUNT, "deer")

def _generate_herbs(rng, render, bullet_world, terrain, occupied, resources, cx, cz):
    count = rng.randint(HERBS_PER_CLUSTER_MIN, HERBS_PER_CLUSTER_MAX)
    for _ in range(count):
        pos = _try_place(rng, cx, cz, CLUSTER_RADIUS * 0.8, HERB_MIN_SPACING, occupied, terrain, TREE_MAX_SLOPE)
        if pos is None: continue
        x, z = pos; y = terrain.height_at(x, z); herb_type = rng.choice(["marigold", "belladonna", "bloodmoss"])
        occupied.append((x, z)); resources.append(HerbPatch(render, bullet_world, (x, y, z), herb_type=herb_type))

def _generate_river_paths(rng):
    river_paths = []
    for _ in range(RIVER_COUNT):
        start = _edge_point(rng, rng.randint(0, 3)); end = _edge_point(rng, (rng.randint(0, 3) + 2) % 4)
        amplitude = rng.uniform(30.0, 80.0); frequency = rng.uniform(1.0, 3.0)
        dx, dz = end[0] - start[0], end[1] - start[1]; length = math.sqrt(dx*dx + dz*dz) or 1.0
        perp_x, perp_z = -dz / length, dx / length
        path = []; limit = WORLD_HALF - 5
        for i in range(RIVER_DECAL_STEPS):
            t = i / (RIVER_DECAL_STEPS - 1); lateral = amplitude * math.sin(t * frequency * 2.0 * math.pi)
            x, z = start[0] + t * dx + lateral * perp_x, start[1] + t * dz + lateral * perp_z
            x, z = max(-limit, min(limit, x)), max(-limit, min(limit, z))
            if _in_safe_zone(x, z):
                if path: river_paths.append(path); path = []
                continue
            path.append((x, z))
        if path: river_paths.append(path)
    return river_paths

def _generate_river_spots(rng, render, bullet_world, terrain, occupied, resources, river_paths):
    for path in river_paths:
        if len(path) < 2: continue
        step = max(5, len(path) // 10); last_pos = None; last_side = rng.choice((-1, 1))
        for i in range(step, len(path) - step, step):
            x, z = path[i]
            if _in_safe_zone(x, z): last_pos = None; continue
            dx, dz = path[i+step][0]-path[i-step][0], path[i+step][1]-path[i-step][1]
            seg_len = math.sqrt(dx*dx + dz*dz) or 1.0
            px, pz = -dz / seg_len, dx / seg_len
            side = last_side if rng.random() < 0.7 else -last_side; last_side = side
            along = rng.uniform(-FISHING_PATH_JITTER, FISHING_PATH_JITTER)
            bank = rng.uniform(FISHING_BANK_OFFSET * 0.8, FISHING_BANK_OFFSET)
            x += px * bank * side + (dx / seg_len) * along; z += pz * bank * side + (dz / seg_len) * along
            if not terrain.is_river(x, z, margin=1.5) or (last_pos and math.sqrt((x-last_pos[0])**2+(z-last_pos[1])**2) < FISHING_SPACING*1.8): continue
            if _has_conflict(x, z, TREE_MIN_SPACING, occupied): last_pos = None; continue
            y = RIVER_DECAL_Y + 0.28; occupied.append((x, z)); resources.append(FishingSpot(render, bullet_world, (x, y, z))); last_pos = (x, z)
