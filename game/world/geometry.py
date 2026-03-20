"""Shared procedural geometry helpers used across the game.
URSINA Y-UP VERSION
"""

import math

from panda3d.core import GeomVertexFormat, GeomVertexData
from panda3d.core import GeomVertexWriter, GeomTriangles, Geom, GeomNode, LightAttrib, Vec3


def _finalize_node(node):
    # Keep procedural vertex-colored geometry visible while the lighting path is
    # still a mix of Ursina entities and raw Panda GeomNodes.
    node.setAttrib(LightAttrib.makeAllOff())
    return node


def make_plane_geom(half_size=100, color=(0.28, 0.55, 0.22, 1)):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("ground", fmt, Geom.UHStatic)
    vdata.setNumRows(4)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")

    s = half_size
    # URSINA Y-UP: X is right, Y is up, Z is forward
    # Plane on XZ floor
    for x, z in [(-s, -s), (s, -s), (s, s), (-s, s)]:
        vertex.addData3(x, 0, z)
        normal.addData3(0, 1, 0)
        color_w.addData4(*color)

    tris = GeomTriangles(Geom.UHStatic)
    tris.addVertices(0, 1, 2)
    tris.addVertices(0, 2, 3)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("plane_geom")
    node.addGeom(geom)
    return _finalize_node(node)


def make_terrain_geom(terrain, half_size=500, step=16):
    verts_per_side = int((half_size * 2) / step) + 1
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("terrain", fmt, Geom.UHStatic)
    vdata.setNumRows(verts_per_side * verts_per_side)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")

    start = -half_size
    for gz in range(verts_per_side):
        z = start + gz * step
        for gx in range(verts_per_side):
            x = start + gx * step
            # height_at(x, z) - treating Y as vertical height
            y = terrain.height_at(x, z)
            nx, ny, nz = terrain.normal_at(x, z)
            # URSINA Y-UP: (X, Height, Z)
            vertex.addData3(x, y, z)
            # terrain.normal_at returns (nx, vertical_ny, nz)
            normal.addData3(nx, ny, nz)
            color_w.addData4(*terrain.ground_color_at(x, z))

    tris = GeomTriangles(Geom.UHStatic)
    for gz in range(verts_per_side - 1):
        for gx in range(verts_per_side - 1):
            base = gz * verts_per_side + gx
            tris.addVertices(base, base + 1, base + verts_per_side)
            tris.addVertices(base + 1, base + verts_per_side + 1, base + verts_per_side)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("terrain_geom")
    node.addGeom(geom)
    return _finalize_node(node)


def make_box_geom(sx, sy, sz, color):
    """Note: sy is height in Ursina notation if we pass it correctly."""
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("box", fmt, Geom.UHStatic)
    vdata.setNumRows(24)

    hx, hy, hz = sx / 2, sy / 2, sz / 2
    face_verts = [
        # Bottom (Y-)
        [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)],
        # Top (Y+)
        [(-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz)],
        # Front (Z-)
        [(-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz)],
        # Back (Z+)
        [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)],
        # Left (X-)
        [(-hx, -hy, -hz), (-hx, -hy, hz), (hx, hy, hz), (-hx, hy, -hz)],
        # Right (X+)
        [(hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz)],
    ]
    normals_list = [
        (0, -1, 0), (0, 1, 0), (0, 0, -1),
        (0, 0, 1), (-1, 0, 0), (1, 0, 0),
    ]

    vertex = GeomVertexWriter(vdata, "vertex")
    normal_w = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)

    for face_i, (face, nrm) in enumerate(zip(face_verts, normals_list)):
        base = face_i * 4
        for v in face:
            vertex.addData3(*v)
            normal_w.addData3(*nrm)
            color_w.addData4(*color)
        tris.addVertices(base, base + 1, base + 2)
        tris.addVertices(base, base + 2, base + 3)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("box_geom")
    node.addGeom(geom)
    return _finalize_node(node)


def make_cylinder(radius, height, color, segments=12):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("cyl", fmt, Geom.UHStatic)
    vdata.setNumRows(segments * 4)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal_w = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)

    for i in range(segments):
        a0 = math.radians(i * 360 / segments)
        a1 = math.radians((i + 1) * 360 / segments)
        x0, z0 = radius * math.cos(a0), radius * math.sin(a0)
        x1, z1 = radius * math.cos(a1), radius * math.sin(a1)
        nx0, nz0 = math.cos(a0), math.sin(a0)

        base = i * 4
        # URSINA Y-UP: Height on Y
        for x, z, y in [(x0, z0, 0), (x1, z1, 0), (x1, z1, height), (x0, z0, height)]:
            vertex.addData3(x, y, z)
            normal_w.addData3(nx0, 0, nz0)
            color_w.addData4(*color)
        tris.addVertices(base, base + 1, base + 2)
        tris.addVertices(base, base + 2, base + 3)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("cylinder")
    node.addGeom(geom)
    return _finalize_node(node)


def make_sphere_approx(radius, color, stacks=6, slices=8):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("sphere", fmt, Geom.UHStatic)
    vdata.setNumRows(stacks * slices * 4)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal_w = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)

    idx = 0
    for i in range(stacks):
        phi0 = math.pi * i / stacks - math.pi / 2
        phi1 = math.pi * (i + 1) / stacks - math.pi / 2
        for j in range(slices):
            th0 = math.radians(j * 360 / slices)
            th1 = math.radians((j + 1) * 360 / slices)

            # Spherical coords to XYZ
            # Ursina Y-up
            def sph(r, p, t):
                x = r * math.cos(p) * math.cos(t)
                z = r * math.cos(p) * math.sin(t)
                y = r * math.sin(p)
                return (x, y, z)

            pts = [
                sph(radius, phi0, th0),
                sph(radius, phi0, th1),
                sph(radius, phi1, th1),
                sph(radius, phi1, th0),
            ]
            for p in pts:
                vertex.addData3(*p)
                n = Vec3(*p).normalized()
                normal_w.addData3(n.x, n.y, n.z)
                color_w.addData4(*color)
            tris.addVertices(idx, idx + 1, idx + 2)
            tris.addVertices(idx, idx + 2, idx + 3)
            idx += 4

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("sphere")
    node.addGeom(geom)
    return _finalize_node(node)
