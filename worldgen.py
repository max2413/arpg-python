"""
worldgen.py — Procedural world generation.
Generates forests (tree clusters), ore patches (rock clusters), and
meandering rivers (chains of fishing spots) across a 1000x1000 world.
Also lays ground decals: dark-blue river beds and tan ore-patch dirt.
"""

import math
import random

from panda3d.core import (
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    GeomTriangles, Geom, GeomNode, Vec3,
    TransparencyAttrib,
)
from resources import Tree, Rock, FishingSpot
from follower import Follower, Spitter

# ---------------------------------------------------------------------------
# Tuneable constants
# ---------------------------------------------------------------------------

WORLD_HALF = 500        # map extends ±500 on X and Y
SAFE_RADIUS = 50        # clear zone around origin (spawn + bank/vendor)

# Forests
FOREST_CLUSTERS       = 6
TREES_PER_CLUSTER_MIN = 30
TREES_PER_CLUSTER_MAX = 50
CLUSTER_RADIUS        = 40   # max distance from cluster center to any tree
TREE_MIN_SPACING      = 3.0  # minimum gap between tree trunks

# Ore patches
ORE_PATCHES           = 5
ROCKS_PER_PATCH_MIN   = 5
ROCKS_PER_PATCH_MAX   = 10
PATCH_RADIUS          = 20
ROCK_MIN_SPACING      = 2.0

# Rivers
RIVER_COUNT           = 3
RIVER_POINTS          = 40   # path sample points per river (decal + spots)
FISHING_SPACING       = 4.0  # minimum distance between consecutive fish spots
RIVER_WIDTH           = 13.5 # half-width of the river bed decal strip

# Hostiles
HOSTILE_COUNT         = 4
SPITTER_COUNT         = 3
HOSTILE_MIN_SPACING   = 18.0
HOSTILE_PATROL_RADIUS = 18.0

# Decal colours
RIVER_COLOR   = (0.10, 0.28, 0.55, 1.0)  # dark blue
ORE_COLOR     = (0.62, 0.52, 0.35, 1.0)  # sandy tan
ORE_DECAL_Z   = 0.0                      # ore ground effect stays on the ground plane
RIVER_DECAL_Z = 0.01                     # river draws slightly above ground decals


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_world(render, bullet_world, seed=42):
    """
    Procedurally place all resources and ground decals.

    Returns `(resources, hostiles)` for use as main.py's world object lists.

    Each sub-system gets its own seeded RNG derived from the master seed so
    that changing forest density never shifts the river layout.
    """
    occupied = []
    resources = []
    hostiles = []

    # cluster_centers tracks placed cluster/patch centres so they don't
    # overlap each other even across subsystems.
    cluster_centers = []

    _generate_forests(random.Random(seed ^ 0x1111),
                      render, bullet_world, occupied, resources,
                      cluster_centers)

    # Ore patches: collect centres so we can draw tan decals under them
    ore_centers = []
    _generate_ore_patches(random.Random(seed ^ 0x2222),
                          render, bullet_world, occupied, resources,
                          ore_centers, cluster_centers)
    for cx, cy in ore_centers:
        _place_circle_decal(render, cx, cy, PATCH_RADIUS + 5, ORE_COLOR)

    # Rivers: collect path points so we can draw the river-bed strip
    river_paths = []
    _generate_rivers(random.Random(seed ^ 0x3333),
                     render, bullet_world, occupied, resources,
                     river_paths)
    for path in river_paths:
        _place_river_decal(render, path, RIVER_WIDTH, RIVER_COLOR)

    _generate_hostiles(random.Random(seed ^ 0x4444),
                       render, occupied, hostiles)

    # Post-pass: remove any land object that sits on a river bed.
    resources, hostiles = _cull_land_on_water(resources, hostiles, river_paths)

    trees  = sum(1 for r in resources if isinstance(r, Tree))
    rocks  = sum(1 for r in resources if isinstance(r, Rock))
    fish   = sum(1 for r in resources if isinstance(r, FishingSpot))
    print(
        f"[worldgen] trees={trees}  rocks={rocks}  fishing_spots={fish}  "
        f"hostiles={len(hostiles)}  rivers={len(river_paths)}"
    )

    return resources, hostiles


# ---------------------------------------------------------------------------
# Geometry helpers — ground decals
# ---------------------------------------------------------------------------

def _place_river_decal(render, path, half_width, color):
    """
    Build a triangle-strip ribbon along `path` (list of (x, y)) with the
    given half_width, laid flat at RIVER_DECAL_Z.
    """
    if len(path) < 2:
        return

    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("river_decal", fmt, Geom.UHStatic)
    vdata.setNumRows(len(path) * 2)

    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")

    def _perp(ax, ay, bx, by):
        """Unit perpendicular to the segment a→b, in XY."""
        dx, dy = bx - ax, by - ay
        L = math.sqrt(dx * dx + dy * dy) or 1.0
        return -dy / L, dx / L

    # Emit left/right edge vertices for each path point
    for i, (x, y) in enumerate(path):
        if i == 0:
            px, py = _perp(path[0][0], path[0][1], path[1][0], path[1][1])
        elif i == len(path) - 1:
            px, py = _perp(path[-2][0], path[-2][1], path[-1][0], path[-1][1])
        else:
            # Average of the two adjacent segment perpendiculars
            p1x, p1y = _perp(path[i-1][0], path[i-1][1], x, y)
            p2x, p2y = _perp(x, y, path[i+1][0], path[i+1][1])
            px = (p1x + p2x) * 0.5
            py = (p1y + p2y) * 0.5
            L = math.sqrt(px * px + py * py) or 1.0
            px /= L
            py /= L

        for side in (-1, 1):
            vw.addData3(x + side * px * half_width,
                        y + side * py * half_width,
                        RIVER_DECAL_Z)
            nw.addData3(0, 0, 1)
            cw.addData4(*color)

    # Triangle strip: pairs of quads from consecutive path points
    tris = GeomTriangles(Geom.UHStatic)
    for i in range(len(path) - 1):
        b = i * 2           # left  vertex at point i
        # quad: b, b+1, b+2, b+3  (left-i, right-i, left-i+1, right-i+1)
        tris.addVertices(b,     b + 1, b + 2)
        tris.addVertices(b + 1, b + 3, b + 2)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("river_decal")
    node.addGeom(geom)
    np = render.attachNewNode(node)
    np.setBin("fixed", 15)
    np.setDepthOffset(1)
    np.setTwoSided(True)  # render both faces regardless of winding order
    print(f"[river decal] {len(path)} pts, first={path[0]}, last={path[-1]}")


def _place_circle_decal(render, cx, cy, radius, color, segments=32):
    """
    Flat filled circle decal (fan of triangles) centred at (cx, cy).
    """
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("ore_decal", fmt, Geom.UHStatic)
    vdata.setNumRows(segments + 1)

    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")

    # Centre vertex
    vw.addData3(cx, cy, ORE_DECAL_Z)
    nw.addData3(0, 0, 1)
    cw.addData4(*color)

    for i in range(segments):
        angle = math.radians(i * 360 / segments)
        vw.addData3(cx + radius * math.cos(angle),
                    cy + radius * math.sin(angle),
                    ORE_DECAL_Z)
        nw.addData3(0, 0, 1)
        cw.addData4(*color)

    tris = GeomTriangles(Geom.UHStatic)
    for i in range(segments):
        tris.addVertices(0, i + 1, (i + 1) % segments + 1)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("ore_decal")
    node.addGeom(geom)
    np = render.attachNewNode(node)
    np.setBin("fixed", 15)
    np.setDepthOffset(1)


# ---------------------------------------------------------------------------
# Post-generation culling
# ---------------------------------------------------------------------------

def _cull_land_on_water(resources, hostiles, river_paths):
    """
    Remove any land object whose position falls within RIVER_WIDTH of any river
    path point. Hidden objects are excluded from the returned lists so the game
    loop ignores them.
    """
    # Build a flat list of all river path points for fast checking
    all_river_pts = [pt for path in river_paths for pt in path]
    w_sq = RIVER_WIDTH * RIVER_WIDTH

    def _on_river(rx, ry):
        for px, py in all_river_pts:
            dx = rx - px
            dy = ry - py
            if dx * dx + dy * dy <= w_sq:
                return True
        return False

    kept_resources = []
    for res in resources:
        if isinstance(res, (Tree, Rock)):
            if _on_river(res.pos.x, res.pos.y):
                res.root.hide()
                res.ghost_np.hide()
                continue
        kept_resources.append(res)

    kept_hostiles = []
    for hostile in hostiles:
        if _on_river(hostile.pos.x, hostile.pos.y):
            hostile.remove_from_world()
            continue
        kept_hostiles.append(hostile)

    return kept_resources, kept_hostiles


# ---------------------------------------------------------------------------
# Placement helpers
# ---------------------------------------------------------------------------

def _in_safe_zone(x, y):
    return (x * x + y * y) <= (SAFE_RADIUS * SAFE_RADIUS)


def _in_bounds(x, y, margin=5):
    limit = WORLD_HALF - margin
    return -limit <= x <= limit and -limit <= y <= limit


def _has_conflict(x, y, min_spacing, occupied):
    sq = min_spacing * min_spacing
    for ox, oy in occupied:
        dx = x - ox
        dy = y - oy
        if dx * dx + dy * dy < sq:
            return True
    return False


def _try_place(rng, cx, cy, radius, min_spacing, occupied, max_attempts=200):
    for _ in range(max_attempts):
        angle = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0, radius)
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)

        if not _in_bounds(x, y):
            continue
        if _in_safe_zone(x, y):
            continue
        if _has_conflict(x, y, min_spacing, occupied):
            continue

        return (x, y)
    return None


def _edge_point(rng, edge):
    """Random point near a map edge (0=N, 1=E, 2=S, 3=W)."""
    rim = rng.uniform(450, 480)
    spread = rng.uniform(-400, 400)
    if edge == 0:
        return (spread, rim)
    elif edge == 1:
        return (rim, spread)
    elif edge == 2:
        return (spread, -rim)
    else:
        return (-rim, spread)


# ---------------------------------------------------------------------------
# Forest generation
# ---------------------------------------------------------------------------

def _generate_forests(rng, render, bullet_world, occupied, resources,
                      cluster_centers):
    # Minimum distance between any two cluster/patch centres
    MIN_CLUSTER_SEP = CLUSTER_RADIUS + PATCH_RADIUS + 10
    for _ in range(FOREST_CLUSTERS):
        # Find a centre that doesn't overlap existing cluster centres
        for _attempt in range(100):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(100, 430)
            cx = dist * math.cos(angle)
            cy = dist * math.sin(angle)
            if not _has_conflict(cx, cy, MIN_CLUSTER_SEP, cluster_centers):
                break
        else:
            continue  # couldn't place this cluster, skip it

        cluster_centers.append((cx, cy))

        count = rng.randint(TREES_PER_CLUSTER_MIN, TREES_PER_CLUSTER_MAX)
        for _ in range(count):
            pos = _try_place(rng, cx, cy, CLUSTER_RADIUS,
                             TREE_MIN_SPACING, occupied)
            if pos:
                x, y = pos
                occupied.append((x, y))
                resources.append(Tree(render, bullet_world, (x, y, 0)))


# ---------------------------------------------------------------------------
# Ore patch generation
# ---------------------------------------------------------------------------

def _generate_ore_patches(rng, render, bullet_world, occupied, resources,
                          ore_centers, cluster_centers):
    MIN_CLUSTER_SEP = CLUSTER_RADIUS + PATCH_RADIUS + 10
    for _ in range(ORE_PATCHES):
        for _attempt in range(100):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(80, 430)
            cx = dist * math.cos(angle)
            cy = dist * math.sin(angle)
            if not _has_conflict(cx, cy, MIN_CLUSTER_SEP, cluster_centers):
                break
        else:
            continue

        cluster_centers.append((cx, cy))
        ore_centers.append((cx, cy))

        count = rng.randint(ROCKS_PER_PATCH_MIN, ROCKS_PER_PATCH_MAX)
        for _ in range(count):
            pos = _try_place(rng, cx, cy, PATCH_RADIUS,
                             ROCK_MIN_SPACING, occupied)
            if pos:
                x, y = pos
                occupied.append((x, y))
                resources.append(Rock(render, bullet_world, (x, y, 0)))


# ---------------------------------------------------------------------------
# Hostile generation
# ---------------------------------------------------------------------------

def _generate_hostiles(rng, render, occupied, hostiles):
    def _spawn(count, hostile_cls):
        for _ in range(count):
            for _attempt in range(150):
                angle = rng.uniform(0, 2 * math.pi)
                dist = rng.uniform(100, 430)
                cx = dist * math.cos(angle)
                cy = dist * math.sin(angle)
                if _has_conflict(cx, cy, HOSTILE_MIN_SPACING, occupied):
                    continue
                if not _in_bounds(cx, cy, margin=HOSTILE_PATROL_RADIUS + 5):
                    continue
                occupied.append((cx, cy))
                hostiles.append(hostile_cls(render, (cx, cy, 0), patrol_center=(cx, cy, 0)))
                break

    _spawn(HOSTILE_COUNT, Follower)
    _spawn(SPITTER_COUNT, Spitter)


# ---------------------------------------------------------------------------
# River generation
# ---------------------------------------------------------------------------

def _generate_rivers(rng, render, bullet_world, occupied, resources,
                     river_paths):
    for _ in range(RIVER_COUNT):
        edge_start = rng.randint(0, 3)
        edge_end = (edge_start + 2) % 4

        start = _edge_point(rng, edge_start)
        end = _edge_point(rng, edge_end)

        amplitude = rng.uniform(30, 80)
        frequency = rng.uniform(1.0, 3.0)

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.sqrt(dx * dx + dy * dy)
        perp_x = -dy / length
        perp_y = dx / length

        # Dense path points for the decal (more than RIVER_POINTS fish spots).
        # Skip any segment that crosses through the spawn safe zone so the
        # river visually avoids the starting area.
        DECAL_STEPS = 120
        path = []
        limit = WORLD_HALF - 5
        for i in range(DECAL_STEPS):
            t = i / (DECAL_STEPS - 1)
            lateral = amplitude * math.sin(t * frequency * 2 * math.pi)
            x = start[0] + t * dx + lateral * perp_x
            y = start[1] + t * dy + lateral * perp_y
            x = max(-limit, min(limit, x))
            y = max(-limit, min(limit, y))
            if _in_safe_zone(x, y):
                # Gap in the path — start a new segment after the safe zone
                if path:
                    river_paths.append(path)
                path = []
                continue
            path.append((x, y))

        if path:
            river_paths.append(path)

        # Place FishingSpots along the same curve (sparser)
        last_pos = None
        for i in range(RIVER_POINTS):
            t = i / (RIVER_POINTS - 1)
            lateral = amplitude * math.sin(t * frequency * 2 * math.pi)
            x = start[0] + t * dx + lateral * perp_x
            y = start[1] + t * dy + lateral * perp_y
            x = max(-limit, min(limit, x))
            y = max(-limit, min(limit, y))

            if _in_safe_zone(x, y):
                last_pos = None
                continue

            # Enforce spacing from previous fish spot (river continuity)
            if last_pos is not None:
                ddx = x - last_pos[0]
                ddy = y - last_pos[1]
                if math.sqrt(ddx * ddx + ddy * ddy) < FISHING_SPACING:
                    continue

            # Don't overlap trees or rocks already in occupied
            if _has_conflict(x, y, TREE_MIN_SPACING, occupied):
                last_pos = None
                continue

            occupied.append((x, y))
            resources.append(FishingSpot(render, bullet_world, (x, y, 0.1)))
            last_pos = (x, y)
