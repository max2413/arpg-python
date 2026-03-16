"""Procedural world generation with terrain-aware placement and decals."""

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

from game.entities.creatures import Scout, Ranger, Wolf, Deer
from game.world.resources import Tree, Rock, FishingSpot, HerbPatch

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
RIVER_DECAL_Z = 0.06
FOREST_DECAL_Z = 0.05
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

        _generate_forests(
            random.Random(seed ^ 0x1111),
            scene_root,
            bullet_world,
            terrain,
            occupied,
            resources,
            forest_centers,
            cluster_centers,
        )

        _generate_ore_patches(
            random.Random(seed ^ 0x2222),
            scene_root,
            bullet_world,
            terrain,
            occupied,
            resources,
            ore_centers,
            cluster_centers,
        )

        river_paths = _generate_river_paths(random.Random(seed ^ 0x3333))
        terrain.set_river_paths(river_paths, RIVER_WIDTH)
        terrain.set_forest_patches([(cx, cy, CLUSTER_RADIUS + 16.0) for cx, cy in forest_centers])
        terrain.set_ore_patches([(cx, cy, PATCH_RADIUS + 8.0) for cx, cy in ore_centers])
        _reground_resources(resources, terrain)

        resources, hostiles = _cull_land_on_water(resources, hostiles, terrain)

        _generate_river_spots(
            random.Random(seed ^ 0x6666),
            scene_root,
            bullet_world,
            terrain,
            occupied,
            resources,
            river_paths,
        )
        _generate_hostiles(
            random.Random(seed ^ 0x4444),
            scene_root,
            bullet_world,
            terrain,
            occupied,
            hostiles,
        )
        _reground_hostiles(hostiles)

        for cx, cy in ore_centers:
            _place_ore_accent(decor_root, terrain, random.Random((seed ^ 0x7777) + int(cx * 3) + int(cy * 5)), cx, cy, PATCH_RADIUS + 4.0)

        decor_rng = random.Random(seed ^ 0x5555)
        for cx, cy in forest_centers:
            _place_forest_floor(decor_root, terrain, decor_rng, cx, cy, CLUSTER_RADIUS * 0.9)
            _generate_herbs(random.Random(seed ^ 0x8888), scene_root, bullet_world, terrain, occupied, resources, cx, cy)

        for path in river_paths:
            _place_river_decal(decor_root, terrain, path, RIVER_WIDTH, RIVER_COLOR)
        layout = _build_layout(seed, river_paths, forest_centers, ore_centers, resources, hostiles)
    else:
        river_paths = [[tuple(point) for point in path] for path in layout.get("river_paths", [])]
        forest_centers = [tuple(center) for center in layout.get("forest_centers", [])]
        ore_centers = [tuple(center) for center in layout.get("ore_centers", [])]
        terrain.set_river_paths(river_paths, RIVER_WIDTH)
        terrain.set_forest_patches([(cx, cy, CLUSTER_RADIUS + 16.0) for cx, cy in forest_centers])
        terrain.set_ore_patches([(cx, cy, PATCH_RADIUS + 8.0) for cx, cy in ore_centers])

        for entry in layout.get("resources", []):
            kind = entry["type"]
            pos = tuple(entry["pos"])
            scale = entry.get("scale", 1.0)
            if kind == "tree":
                resources.append(Tree(scene_root, bullet_world, pos, scale=scale))
            elif kind == "rock":
                resources.append(Rock(scene_root, bullet_world, pos, scale=scale))
            elif kind == "fishing":
                resources.append(FishingSpot(scene_root, bullet_world, pos))

        for entry in layout.get("hostiles", []):
            kind = entry["type"]
            pos = tuple(entry["pos"])
            patrol_center = tuple(entry.get("patrol_center", entry["pos"]))
            hostile_cls = Ranger if kind in ("spitter", "ranger") else (Wolf if kind == "wolf" else Scout)
            hostiles.append(
                hostile_cls(
                    scene_root,
                    pos,
                    patrol_center=patrol_center,
                    terrain=terrain,
                    bullet_world=bullet_world,
                )
            )

        for cx, cy in ore_centers:
            _place_ore_accent(decor_root, terrain, random.Random((seed ^ 0x7777) + int(cx * 3) + int(cy * 5)), cx, cy, PATCH_RADIUS + 4.0)
        decor_rng = random.Random(seed ^ 0x5555)
        for cx, cy in forest_centers:
            _place_forest_floor(decor_root, terrain, decor_rng, cx, cy, CLUSTER_RADIUS * 0.9)
        for path in river_paths:
            _place_river_decal(decor_root, terrain, path, RIVER_WIDTH, RIVER_COLOR)

    trees = sum(1 for r in resources if isinstance(r, Tree))
    rocks = sum(1 for r in resources if isinstance(r, Rock))
    fish = sum(1 for r in resources if isinstance(r, FishingSpot))
    print(
        f"[worldgen:{load_mode}] trees={trees}  rocks={rocks}  fishing_spots={fish}  "
        f"hostiles={len(hostiles)}  rivers={len(river_paths)}"
    )
    return resources, hostiles, decor_root, layout


def _build_layout(seed, river_paths, forest_centers, ore_centers, resources, hostiles):
    layout = {
        "seed": seed,
        "river_paths": [[[x, y] for x, y in path] for path in river_paths],
        "forest_centers": [[x, y] for x, y in forest_centers],
        "ore_centers": [[x, y] for x, y in ore_centers],
        "resources": [],
        "hostiles": [],
    }
    for resource in resources:
        entry = {"pos": [resource.pos.x, resource.pos.y, resource.pos.z]}
        if isinstance(resource, Tree):
            entry["type"] = "tree"
            entry["scale"] = resource.scale
        elif isinstance(resource, Rock):
            entry["type"] = "rock"
            entry["scale"] = resource.scale
        elif isinstance(resource, FishingSpot):
            entry["type"] = "fishing"
        else:
            continue
        layout["resources"].append(entry)
    for hostile in hostiles:
        layout["hostiles"].append(
            {
                "type": "ranger" if isinstance(hostile, Ranger) else ("wolf" if isinstance(hostile, Wolf) else "scout"),
                "pos": [hostile.pos.x, hostile.pos.y, hostile.pos.z],
                "patrol_center": [hostile.patrol_center.x, hostile.patrol_center.y, hostile.patrol_center.z],
            }
        )
    return layout


def _place_river_decal(parent, terrain, path, half_width, color):
    if len(path) < 2:
        return

    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("river_decal", fmt, Geom.UHStatic)
    vdata.setNumRows(len(path) * 2)

    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")

    def _perp(ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        length = math.sqrt(dx * dx + dy * dy) or 1.0
        return -dy / length, dx / length

    for i, (x, y) in enumerate(path):
        if i == 0:
            px, py = _perp(path[0][0], path[0][1], path[1][0], path[1][1])
        elif i == len(path) - 1:
            px, py = _perp(path[-2][0], path[-2][1], path[-1][0], path[-1][1])
        else:
            p1x, p1y = _perp(path[i - 1][0], path[i - 1][1], x, y)
            p2x, p2y = _perp(x, y, path[i + 1][0], path[i + 1][1])
            px = (p1x + p2x) * 0.5
            py = (p1y + p2y) * 0.5
            length = math.sqrt(px * px + py * py) or 1.0
            px /= length
            py /= length

        for side in (-1, 1):
            vx = x + side * px * half_width
            vy = y + side * py * half_width
            vz = RIVER_DECAL_Z
            nx, ny, nz = (0.0, 0.0, 1.0)
            vw.addData3(vx, vy, vz)
            nw.addData3(nx, ny, nz)
            cw.addData4(*color)

    tris = GeomTriangles(Geom.UHStatic)
    for i in range(len(path) - 1):
        base = i * 2
        tris.addVertices(base, base + 1, base + 2)
        tris.addVertices(base + 1, base + 3, base + 2)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("river_decal")
    node.addGeom(geom)
    np = parent.attachNewNode(node)
    np.setBin("fixed", 15)
    np.setDepthOffset(8)
    np.setTwoSided(True)
    np.setTransparency(TransparencyAttrib.MAlpha)


def _place_circle_decal(parent, terrain, cx, cy, radius, color, z_offset, segments=24):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("terrain_decal", fmt, Geom.UHStatic)
    vdata.setNumRows(segments + 1)

    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")

    center_z = terrain.height_at(cx, cy) + z_offset
    nx, ny, nz = terrain.normal_at(cx, cy)
    vw.addData3(cx, cy, center_z)
    nw.addData3(nx, ny, nz)
    cw.addData4(*color)

    for i in range(segments):
        angle = math.radians(i * 360.0 / segments)
        vx = cx + radius * math.cos(angle)
        vy = cy + radius * math.sin(angle)
        vz = terrain.height_at(vx, vy) + z_offset
        nx, ny, nz = terrain.normal_at(vx, vy)
        vw.addData3(vx, vy, vz)
        nw.addData3(nx, ny, nz)
        cw.addData4(*color)

    tris = GeomTriangles(Geom.UHStatic)
    for i in range(segments):
        tris.addVertices(0, i + 1, ((i + 1) % segments) + 1)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("terrain_decal")
    node.addGeom(geom)
    np = parent.attachNewNode(node)
    np.setBin("fixed", 15)
    np.setDepthOffset(4)
    np.setTransparency(TransparencyAttrib.MAlpha)


def _place_forest_floor(parent, terrain, rng, cx, cy, radius):
    litter_colors = [
        (0.21, 0.17, 0.08, 0.09),
        (0.18, 0.14, 0.06, 0.08),
        (0.14, 0.16, 0.08, 0.07),
    ]
    for _ in range(FOREST_DRESSING_PATCHES * 4):
        angle = rng.uniform(0.0, math.tau)
        dist = rng.uniform(0.0, radius)
        x = cx + math.cos(angle) * dist
        y = cy + math.sin(angle) * dist
        if not _in_bounds(x, y):
            continue
        if terrain.is_river(x, y, margin=2.0):
            continue
        size = rng.uniform(0.8, 2.2)
        color = litter_colors[rng.randrange(len(litter_colors))]
        _place_circle_decal(parent, terrain, x, y, size, color, FOREST_DECAL_Z, segments=8)


def _place_ore_accent(parent, terrain, rng, cx, cy, radius):
    for _ in range(10):
        angle = rng.uniform(0.0, math.tau)
        dist = rng.uniform(0.0, radius)
        x = cx + math.cos(angle) * dist
        y = cy + math.sin(angle) * dist
        if not _in_bounds(x, y):
            continue
        if terrain.is_river(x, y, margin=1.0):
            continue
        size = rng.uniform(1.4, 4.6)
        _place_circle_decal(parent, terrain, x, y, size, ORE_ACCENT_COLOR, FOREST_DECAL_Z - 0.01, segments=10)


def _cull_land_on_water(resources, hostiles, terrain):
    kept_resources = []
    for resource in resources:
        if isinstance(resource, (Tree, Rock)) and terrain.is_river(resource.pos.x, resource.pos.y, margin=0.5):
            resource.remove_from_world()
            continue
        kept_resources.append(resource)

    kept_hostiles = []
    for hostile in hostiles:
        if terrain.is_river(hostile.pos.x, hostile.pos.y, margin=1.0):
            hostile.remove_from_world()
            continue
        kept_hostiles.append(hostile)
    return kept_resources, kept_hostiles


def _reground_resources(resources, terrain):
    for resource in resources:
        if isinstance(resource, FishingSpot):
            continue
        z = terrain.height_at(resource.pos.x, resource.pos.y)
        resource.set_ground_pos((resource.pos.x, resource.pos.y, z))


def _reground_hostiles(hostiles):
    for hostile in hostiles:
        hostile.reground()


def _in_safe_zone(x, y):
    return (x * x + y * y) <= (SAFE_RADIUS * SAFE_RADIUS)


def _in_bounds(x, y, margin=5):
    limit = WORLD_HALF - margin
    return -limit <= x <= limit and -limit <= y <= limit


def _has_conflict(x, y, min_spacing, occupied):
    spacing_sq = min_spacing * min_spacing
    for ox, oy in occupied:
        dx = x - ox
        dy = y - oy
        if dx * dx + dy * dy < spacing_sq:
            return True
    return False


def _is_terrain_valid(terrain, x, y, max_slope, river_margin=0.0):
    if terrain.is_river(x, y, margin=river_margin):
        return False
    return terrain.slope_at(x, y) <= max_slope


def _try_place(rng, cx, cy, radius, min_spacing, occupied, terrain, max_slope, max_attempts=200):
    for _ in range(max_attempts):
        angle = rng.uniform(0.0, math.tau)
        dist = rng.uniform(0.0, radius)
        x = cx + dist * math.cos(angle)
        y = cy + dist * math.sin(angle)

        if not _in_bounds(x, y):
            continue
        if _in_safe_zone(x, y):
            continue
        if _has_conflict(x, y, min_spacing, occupied):
            continue
        if not _is_terrain_valid(terrain, x, y, max_slope, river_margin=RIVER_WIDTH * 0.4):
            continue
        return (x, y)
    return None


def _edge_point(rng, edge):
    rim = rng.uniform(450, 480)
    spread = rng.uniform(-400, 400)
    if edge == 0:
        return (spread, rim)
    if edge == 1:
        return (rim, spread)
    if edge == 2:
        return (spread, -rim)
    return (-rim, spread)


def _pick_cluster_center(rng, terrain, cluster_centers, min_sep, min_dist, max_dist, max_slope):
    for _ in range(120):
        angle = rng.uniform(0.0, math.tau)
        dist = rng.uniform(min_dist, max_dist)
        cx = dist * math.cos(angle)
        cy = dist * math.sin(angle)
        if not _in_bounds(cx, cy, margin=CLUSTER_RADIUS + 10):
            continue
        if _has_conflict(cx, cy, min_sep, cluster_centers):
            continue
        if not _is_terrain_valid(terrain, cx, cy, max_slope, river_margin=RIVER_WIDTH):
            continue
        return (cx, cy)
    return None


def _generate_forests(rng, render, bullet_world, terrain, occupied, resources, forest_centers, cluster_centers):
    min_cluster_sep = CLUSTER_RADIUS + PATCH_RADIUS + 10.0
    for _ in range(FOREST_CLUSTERS):
        center = _pick_cluster_center(rng, terrain, cluster_centers, min_cluster_sep, 100.0, 430.0, TREE_MAX_SLOPE)
        if center is None:
            continue
        cx, cy = center
        cluster_centers.append(center)
        forest_centers.append(center)

        count = rng.randint(TREES_PER_CLUSTER_MIN, TREES_PER_CLUSTER_MAX)
        for _ in range(count):
            pos = _try_place(rng, cx, cy, CLUSTER_RADIUS, TREE_MIN_SPACING, occupied, terrain, TREE_MAX_SLOPE)
            if pos is None:
                continue
            x, y = pos
            z = terrain.height_at(x, y)
            scale = rng.uniform(
                TREE_BASE_SCALE * (1.0 - TREE_SCALE_VARIATION),
                TREE_BASE_SCALE * (1.0 + TREE_SCALE_VARIATION),
            )
            occupied.append((x, y))
            resources.append(Tree(render, bullet_world, (x, y, z), scale=scale))


def _generate_ore_patches(rng, render, bullet_world, terrain, occupied, resources, ore_centers, cluster_centers):
    min_cluster_sep = CLUSTER_RADIUS + PATCH_RADIUS + 10.0
    for _ in range(ORE_PATCHES):
        center = _pick_cluster_center(rng, terrain, cluster_centers, min_cluster_sep, 80.0, 430.0, ROCK_MAX_SLOPE)
        if center is None:
            continue
        cx, cy = center
        cluster_centers.append(center)
        ore_centers.append(center)

        count = rng.randint(ROCKS_PER_PATCH_MIN, ROCKS_PER_PATCH_MAX)
        for _ in range(count):
            pos = _try_place(rng, cx, cy, PATCH_RADIUS, ROCK_MIN_SPACING, occupied, terrain, ROCK_MAX_SLOPE)
            if pos is None:
                continue
            x, y = pos
            z = terrain.height_at(x, y)
            scale = rng.uniform(
                ROCK_BASE_SCALE * (1.0 - ROCK_SCALE_VARIATION),
                ROCK_BASE_SCALE * (1.0 + ROCK_SCALE_VARIATION),
            )
            occupied.append((x, y))
            resources.append(Rock(render, bullet_world, (x, y, z), scale=scale))


def _generate_hostiles(rng, render, bullet_world, terrain, occupied, hostiles):
    def _spawn(count, hostile_cls):
        for _ in range(count):
            for _ in range(150):
                angle = rng.uniform(0.0, math.tau)
                dist = rng.uniform(100.0, 430.0)
                x = dist * math.cos(angle)
                y = dist * math.sin(angle)
                if _has_conflict(x, y, HOSTILE_MIN_SPACING, occupied):
                    continue
                if not _in_bounds(x, y, margin=HOSTILE_PATROL_RADIUS + 5):
                    continue
                if not _is_terrain_valid(terrain, x, y, HOSTILE_MAX_SLOPE, river_margin=RIVER_WIDTH * 0.8):
                    continue
                z = terrain.height_at(x, y)
                occupied.append((x, y))
                hostile = hostile_cls(
                    render,
                    (x, y, z),
                    patrol_center=(x, y, z),
                    terrain=terrain,
                    bullet_world=bullet_world,
                )
                hostiles.append(hostile)
                break

    _spawn(HOSTILE_COUNT, Scout)
    _spawn(RANGER_COUNT, Ranger)
    _spawn(WOLF_COUNT, Wolf)
    _spawn(DEER_COUNT, Deer)


def _generate_herbs(rng, render, bullet_world, terrain, occupied, resources, cx, cy):
    count = rng.randint(HERBS_PER_CLUSTER_MIN, HERBS_PER_CLUSTER_MAX)
    for _ in range(count):
        pos = _try_place(rng, cx, cy, CLUSTER_RADIUS * 0.8, HERB_MIN_SPACING, occupied, terrain, TREE_MAX_SLOPE)
        if pos is None:
            continue
        x, y = pos
        z = terrain.height_at(x, y)
        herb_type = rng.choice(["marigold", "belladonna"])
        occupied.append((x, y))
        resources.append(HerbPatch(render, bullet_world, (x, y, z), herb_type=herb_type))


def _generate_river_paths(rng):
    river_paths = []
    for _ in range(RIVER_COUNT):
        edge_start = rng.randint(0, 3)
        edge_end = (edge_start + 2) % 4
        start = _edge_point(rng, edge_start)
        end = _edge_point(rng, edge_end)
        amplitude = rng.uniform(30.0, 80.0)
        frequency = rng.uniform(1.0, 3.0)

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.sqrt(dx * dx + dy * dy) or 1.0
        perp_x = -dy / length
        perp_y = dx / length

        path = []
        limit = WORLD_HALF - 5
        for i in range(RIVER_DECAL_STEPS):
            t = i / (RIVER_DECAL_STEPS - 1)
            lateral = amplitude * math.sin(t * frequency * 2.0 * math.pi)
            x = start[0] + t * dx + lateral * perp_x
            y = start[1] + t * dy + lateral * perp_y
            x = max(-limit, min(limit, x))
            y = max(-limit, min(limit, y))
            if _in_safe_zone(x, y):
                if path:
                    river_paths.append(path)
                path = []
                continue
            path.append((x, y))
        if path:
            river_paths.append(path)
    return river_paths


def _generate_river_spots(rng, render, bullet_world, terrain, occupied, resources, river_paths):
    for path in river_paths:
        if len(path) < 2:
            continue
        step = max(5, len(path) // max(10, RIVER_POINTS // 2))
        last_pos = None
        last_side = rng.choice((-1, 1))
        for i in range(step, len(path) - step, step):
            x, y = path[i]
            if _in_safe_zone(x, y):
                last_pos = None
                continue
            prev_x, prev_y = path[i - step]
            next_x, next_y = path[min(len(path) - 1, i + step)]
            dx = next_x - prev_x
            dy = next_y - prev_y
            seg_len = math.sqrt(dx * dx + dy * dy) or 1.0
            perp_x = -dy / seg_len
            perp_y = dx / seg_len
            side = last_side if rng.random() < 0.7 else -last_side
            last_side = side
            along_jitter = rng.uniform(-FISHING_PATH_JITTER, FISHING_PATH_JITTER)
            bank_pull = rng.uniform(FISHING_BANK_OFFSET * 0.8, FISHING_BANK_OFFSET)
            x += perp_x * bank_pull * side + (dx / seg_len) * along_jitter
            y += perp_y * bank_pull * side + (dy / seg_len) * along_jitter
            if not terrain.is_river(x, y, margin=1.5):
                continue
            if last_pos is not None:
                last_dx = x - last_pos[0]
                last_dy = y - last_pos[1]
                if math.sqrt(last_dx * last_dx + last_dy * last_dy) < FISHING_SPACING * 1.8:
                    continue
            if _has_conflict(x, y, TREE_MIN_SPACING, occupied):
                last_pos = None
                continue
            z = RIVER_DECAL_Z + 0.28
            occupied.append((x, y))
            resources.append(FishingSpot(render, bullet_world, (x, y, z)))
            last_pos = (x, y)
