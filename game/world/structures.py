"""Reusable structure shells and simple structure prototypes."""

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

    pieces = [
        ((0, 0, 0.18), (10.5, 8.5, 0.35), floor_color),
        ((0, 3.95, 2.6), (10.0, 0.4, 4.8), wall_color),
        ((-4.8, 0.35, 2.6), (0.4, 7.2, 4.8), wall_color),
        ((4.8, 0.35, 2.6), (0.4, 7.2, 4.8), wall_color),
        ((0, 3.9, 5.4), (10.0, 0.35, 1.7), wall_color),
        ((0, -3.6, 4.95), (10.0, 0.35, 0.55), trim_color),
        ((0, 0.1, 5.15), (11.4, 9.4, 0.35), roof_color),
        ((0, 0.18, 5.62), (10.4, 8.4, 0.25), (0.44, 0.29, 0.18, 1.0)),
        ((0, 1.4, 0.95), (7.4, 1.2, 1.3), counter_color),
        ((0, 1.25, 1.58), (7.8, 1.45, 0.18), trim_color),
        ((-1.7, 1.0, 1.77), (1.3, 0.9, 0.18), (0.16, 0.24, 0.22, 1.0)),
        ((2.6, 1.05, 0.72), (1.2, 0.9, 1.0), (0.5, 0.38, 0.18, 1.0)),
        ((0, -3.55, 4.0), (3.6, 0.18, 1.1), (0.2, 0.12, 0.08, 1.0)),
    ]

    roof_main = None
    roof_cap = None
    for pos, size, color in pieces:
        piece = parent.attachNewNode(make_box_geom(size[0], size[1], size[2], color))
        piece.setPos(*pos)
        if pos == (0, 0.1, 5.15):
            roof_main = piece
        elif pos == (0, 0.18, 5.62):
            roof_cap = piece

    for x in (-4.1, -1.4, 1.4, 4.1):
        pillar = parent.attachNewNode(make_cylinder(0.22, 4.5, pillar_color))
        pillar.setPos(x, -3.25, 0.35)

    if roof_main is not None:
        roof_main.setP(-8)
    if roof_cap is not None:
        roof_cap.setP(-8)

    collision_nodes = []
    for pos, size in [
        ((0, 0, 0.18), (10.5, 8.5, 0.35)),
        ((0, 3.95, 2.6), (10.0, 0.4, 4.8)),
        ((-4.8, 0.35, 2.6), (0.4, 7.2, 4.8)),
        ((4.8, 0.35, 2.6), (0.4, 7.2, 4.8)),
        ((0, 1.4, 0.95), (7.4, 1.2, 1.3)),
        ((-4.1, -3.25, 2.25), (0.5, 0.6, 4.5)),
        ((-1.4, -3.25, 2.25), (0.5, 0.6, 4.5)),
        ((1.4, -3.25, 2.25), (0.5, 0.6, 4.5)),
        ((4.1, -3.25, 2.25), (0.5, 0.6, 4.5)),
    ]:
        collider = attach_static_box_collider(
            render,
            bullet_world,
            "bank_collision",
            (
                world_pos[0] + pos[0] * scale,
                world_pos[1] + pos[1] * scale,
                world_pos[2] + pos[2] * scale,
            ),
            (size[0] * scale, size[1] * scale, size[2] * scale),
        )
        collision_nodes.append(collider)

    anchors = {
        "npc": (0.0, 2.2, 0.35),
        "sign": (0.0, -3.55, 4.0),
    }
    return {"anchors": anchors, "collision_nodes": collision_nodes}


def _build_open_stone_hall(parent, render, bullet_world, world_pos, scale):
    floor_color = (0.42, 0.43, 0.40, 1.0)
    wall_color = (0.42, 0.48, 0.44, 1.0)
    wall_dark = (0.31, 0.36, 0.33, 1.0)
    roof_color = (0.24, 0.24, 0.28, 1.0)
    beam_color = (0.27, 0.18, 0.12, 1.0)

    pieces = [
        ((0, 0, 0.18), (12.0, 10.0, 0.35), floor_color),
        ((0, 4.8, 2.7), (11.4, 0.55, 5.0), wall_color),
        ((-5.7, 0.1, 2.7), (0.55, 8.8, 5.0), wall_color),
        ((5.7, 0.1, 2.7), (0.55, 8.8, 5.0), wall_color),
        ((0, -4.2, 4.6), (12.0, 0.35, 0.45), beam_color),
        ((0, 0.2, 5.3), (13.0, 11.0, 0.4), roof_color),
    ]

    roof_main = None
    for pos, size, color in pieces:
        piece = parent.attachNewNode(make_box_geom(size[0], size[1], size[2], color))
        piece.setPos(*pos)
        if pos == (0, 0.2, 5.3):
            roof_main = piece

    if roof_main is not None:
        roof_main.setP(-7)

    # Add a visible block pattern to the rear wall only so the shell has some
    # masonry character without overcomplicating every face yet.
    block_w = 1.75
    block_h = 0.72
    start_x = -4.4
    start_z = 0.52
    cols = 5
    rows = 6
    for row in range(rows):
        row_offset = 0.85 if row % 2 else 0.0
        for col in range(cols):
            x = start_x + col * block_w + row_offset
            if x > 4.45:
                continue
            color = wall_dark if (row + col) % 2 else wall_color
            block = parent.attachNewNode(make_box_geom(1.55, 0.16, 0.58, color))
            block.setPos(x, 4.5, start_z + row * block_h)

    for x in (-4.8, -1.6, 1.6, 4.8):
        post = parent.attachNewNode(make_cylinder(0.18, 4.45, beam_color))
        post.setPos(x, -3.95, 0.2)

    collision_nodes = []
    for pos, size in [
        ((0, 0, 0.18), (12.0, 10.0, 0.35)),
        ((0, 4.8, 2.7), (11.4, 0.55, 5.0)),
        ((-5.7, 0.1, 2.7), (0.55, 8.8, 5.0)),
        ((5.7, 0.1, 2.7), (0.55, 8.8, 5.0)),
        ((-4.8, -3.95, 2.2), (0.45, 0.45, 4.45)),
        ((-1.6, -3.95, 2.2), (0.45, 0.45, 4.45)),
        ((1.6, -3.95, 2.2), (0.45, 0.45, 4.45)),
        ((4.8, -3.95, 2.2), (0.45, 0.45, 4.45)),
    ]:
        collider = attach_static_box_collider(
            render,
            bullet_world,
            "open_stone_hall_collision",
            (
                world_pos[0] + pos[0] * scale,
                world_pos[1] + pos[1] * scale,
                world_pos[2] + pos[2] * scale,
            ),
            (size[0] * scale, size[1] * scale, size[2] * scale),
        )
        collision_nodes.append(collider)

    anchors = {
        "center": (0.0, 0.0, 0.35),
        "back_wall": (0.0, 4.8, 2.7),
        "front_opening": (0.0, -4.4, 0.35),
    }
    return {"anchors": anchors, "collision_nodes": collision_nodes}
