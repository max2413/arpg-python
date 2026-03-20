"""Reusable structure shells and simple structure prototypes.
URSINA Y-UP VERSION
"""

from game.world.collision import attach_static_box_collider
from game.world.geometry import make_box_geom, make_cylinder


def build_structure_shell(kind, parent, render, bullet_world, world_pos, scale=1.0):
    if kind == "bank":
        return _build_bank_shell(parent, render, bullet_world, world_pos, scale)
    if kind == "open_stone_hall":
        return _build_open_stone_hall(parent, render, bullet_world, world_pos, scale)
    raise ValueError(f"Unknown structure shell: {kind}")


def _build_bank_shell(parent, render, bullet_world, world_pos, scale):
    floor_color = (0.56, 0.48, 0.36, 1.0)
    wall_color = (0.72, 0.66, 0.54, 1.0)
    trim_color = (0.33, 0.22, 0.14, 1.0)
    roof_color = (0.24, 0.14, 0.10, 1.0)
    counter_color = (0.42, 0.27, 0.17, 1.0)
    pillar_color = (0.62, 0.56, 0.44, 1.0)

    # pieces: (pos, size, color)
    # size is (sx, sy, sz) where sy is height
    # pos is (x, y, z) where y is vertical
    pieces = [
        ((0, 0.18, 0), (10.5, 0.35, 8.5), floor_color),
        ((0, 2.6, 3.95), (10.0, 4.8, 0.4), wall_color),
        ((-4.8, 2.6, 0.35), (0.4, 4.8, 7.2), wall_color),
        ((4.8, 2.6, 0.35), (0.4, 4.8, 7.2), wall_color),
        ((0, 5.4, 3.9), (10.0, 1.7, 0.35), wall_color),
        ((0, 4.95, -3.6), (10.0, 0.55, 0.35), trim_color),
        ((0, 5.15, 0.1), (11.4, 0.35, 9.4), roof_color),
        ((0, 5.62, 0.18), (10.4, 0.25, 8.4), (0.44, 0.29, 0.18, 1.0)),
        ((0, 0.95, 1.4), (7.4, 1.3, 1.2), counter_color),
        ((0, 1.58, 1.25), (7.8, 0.18, 1.45), trim_color),
        ((-1.7, 1.77, 1.0), (1.3, 0.18, 0.9), (0.16, 0.24, 0.22, 1.0)),
        ((2.6, 0.72, 1.05), (1.2, 1.0, 0.9), (0.5, 0.38, 0.18, 1.0)),
        ((0, 4.0, -3.55), (3.6, 1.1, 0.18), (0.2, 0.12, 0.08, 1.0)),
    ]

    roof_main = None
    roof_cap = None
    for pos, size, color in pieces:
        piece = parent.attachNewNode(make_box_geom(size[0], size[1], size[2], color))
        piece.setPos(*pos)
        if pos == (0, 5.15, 0.1): roof_main = piece
        elif pos == (0, 5.62, 0.18): roof_cap = piece

    for x in (-4.1, -1.4, 1.4, 4.1):
        pillar = parent.attachNewNode(make_cylinder(0.22, 4.5, pillar_color))
        pillar.setPos(x, 0.35, -3.25)

    if roof_main: roof_main.setP(-8)
    if roof_cap: roof_cap.setP(-8)

    collision_nodes = []
    for pos, size in [
        ((0, 0.18, 0), (10.5, 0.35, 8.5)),
        ((0, 2.6, 3.95), (10.0, 4.8, 0.4)),
        ((-4.8, 2.6, 0.35), (0.4, 4.8, 7.2)),
        ((4.8, 2.6, 0.35), (0.4, 4.8, 7.2)),
        ((0, 0.95, 1.4), (7.4, 1.3, 1.2)),
        ((-4.1, 2.25, -3.25), (0.5, 4.5, 0.6)),
        ((-1.4, 2.25, -3.25), (0.5, 4.5, 0.6)),
        ((1.4, 2.25, -3.25), (0.5, 4.5, 0.6)),
        ((4.1, 2.25, -3.25), (0.5, 4.5, 0.6)),
    ]:
        collider = attach_static_box_collider(render, bullet_world, "bank_collision",
            (world_pos[0] + pos[0]*scale, world_pos[1] + pos[1]*scale, world_pos[2] + pos[2]*scale),
            (size[0]*scale, size[1]*scale, size[2]*scale))
        collision_nodes.append(collider)

    anchors = {"npc": (0.0, 0.35, 2.2), "sign": (0.0, 4.0, -3.55)}
    return {"anchors": anchors, "collision_nodes": collision_nodes}


def _build_open_stone_hall(parent, render, bullet_world, world_pos, scale):
    floor_color = (0.42, 0.43, 0.40, 1.0)
    wall_color = (0.42, 0.48, 0.44, 1.0)
    wall_dark = (0.31, 0.36, 0.33, 1.0)
    roof_color = (0.24, 0.24, 0.28, 1.0)
    beam_color = (0.27, 0.18, 0.12, 1.0)

    pieces = [
        ((0, 0.18, 0), (12.0, 0.35, 10.0), floor_color),
        ((0, 2.7, 4.8), (11.4, 5.0, 0.55), wall_color),
        ((-5.7, 2.7, 0.1), (0.55, 5.0, 8.8), wall_color),
        ((5.7, 2.7, 0.1), (0.55, 5.0, 8.8), wall_color),
        ((0, 4.6, -4.2), (12.0, 0.45, 0.35), beam_color),
        ((0, 5.3, 0.2), (13.0, 0.4, 11.0), roof_color),
    ]

    roof_main = None
    for pos, size, color in pieces:
        piece = parent.attachNewNode(make_box_geom(size[0], size[1], size[2], color))
        piece.setPos(*pos)
        if pos == (0, 5.3, 0.2): roof_main = piece

    if roof_main: roof_main.setP(-7)

    start_x, start_y = -4.4, 0.52
    block_w, block_h = 1.75, 0.72
    for row in range(6):
        row_off = 0.85 if row % 2 else 0.0
        for col in range(5):
            x = start_x + col * block_w + row_off
            if x > 4.45: continue
            col_val = wall_dark if (row + col) % 2 else wall_color
            block = parent.attachNewNode(make_box_geom(1.55, 0.58, 0.16, col_val))
            block.setPos(x, start_y + row * block_h, 4.5)

    for x in (-4.8, -1.6, 1.6, 4.8):
        post = parent.attachNewNode(make_cylinder(0.18, 4.45, beam_color))
        post.setPos(x, 0.2, -3.95)

    collision_nodes = []
    for pos, size in [
        ((0, 0.18, 0), (12.0, 0.35, 10.0)),
        ((0, 2.7, 4.8), (11.4, 5.0, 0.55)),
        ((-5.7, 2.7, 0.1), (0.55, 5.0, 8.8)),
        ((5.7, 2.7, 0.1), (0.55, 5.0, 8.8)),
        ((-4.8, 2.2, -3.95), (0.45, 4.45, 0.45)),
        ((-1.6, 2.2, -3.95), (0.45, 4.45, 0.45)),
        ((1.6, 2.2, -3.95), (0.45, 4.45, 0.45)),
        ((4.1, 2.2, -3.95), (0.45, 4.45, 0.45)),
    ]:
        collider = attach_static_box_collider(render, bullet_world, "open_stone_hall_collision",
            (world_pos[0] + pos[0]*scale, world_pos[1] + pos[1]*scale, world_pos[2] + pos[2]*scale),
            (size[0]*scale, size[1]*scale, size[2]*scale))
        collision_nodes.append(collider)

    anchors = {"center": (0.0, 0.35, 0.0), "back_wall": (0.0, 2.7, 4.8), "front_opening": (0.0, 0.35, -4.4)}
    return {"anchors": anchors, "collision_nodes": collision_nodes}
