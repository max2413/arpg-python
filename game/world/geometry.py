"""Shared procedural geometry helpers used across the game."""

import math

from panda3d.core import GeomVertexFormat, GeomVertexData
from panda3d.core import GeomVertexWriter, GeomTriangles, Geom, GeomNode, Vec3


def make_plane_geom(half_size=100, color=(0.28, 0.55, 0.22, 1)):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("ground", fmt, Geom.UHStatic)
    vdata.setNumRows(4)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")

    s = half_size
    for x, y in [(-s, -s), (s, -s), (s, s), (-s, s)]:
        vertex.addData3(x, y, 0)
        normal.addData3(0, 0, 1)
        color_w.addData4(*color)

    tris = GeomTriangles(Geom.UHStatic)
    tris.addVertices(0, 1, 2)
    tris.addVertices(0, 2, 3)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("plane_geom")
    node.addGeom(geom)
    return node


def make_box_geom(sx, sy, sz, color):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("box", fmt, Geom.UHStatic)
    vdata.setNumRows(24)

    hx, hy, hz = sx / 2, sy / 2, sz / 2
    face_verts = [
        [(-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz)],
        [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)],
        [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)],
        [(-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz)],
        [(-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz)],
        [(hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz)],
    ]
    normals_list = [
        (0, 0, -1), (0, 0, 1), (0, -1, 0),
        (0, 1, 0), (-1, 0, 0), (1, 0, 0),
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
    return node


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
        x0, y0 = radius * math.cos(a0), radius * math.sin(a0)
        x1, y1 = radius * math.cos(a1), radius * math.sin(a1)
        nx0, ny0 = math.cos(a0), math.sin(a0)

        base = i * 4
        for x, y, z in [(x0, y0, 0), (x1, y1, 0), (x1, y1, height), (x0, y0, height)]:
            vertex.addData3(x, y, z)
            normal_w.addData3(nx0, ny0, 0)
            color_w.addData4(*color)
        tris.addVertices(base, base + 1, base + 2)
        tris.addVertices(base, base + 2, base + 3)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("cylinder")
    node.addGeom(geom)
    return node


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

            pts = [
                (
                    radius * math.cos(phi0) * math.cos(th0),
                    radius * math.cos(phi0) * math.sin(th0),
                    radius * math.sin(phi0),
                ),
                (
                    radius * math.cos(phi0) * math.cos(th1),
                    radius * math.cos(phi0) * math.sin(th1),
                    radius * math.sin(phi0),
                ),
                (
                    radius * math.cos(phi1) * math.cos(th1),
                    radius * math.cos(phi1) * math.sin(th1),
                    radius * math.sin(phi1),
                ),
                (
                    radius * math.cos(phi1) * math.cos(th0),
                    radius * math.cos(phi1) * math.sin(th0),
                    radius * math.sin(phi1),
                ),
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
    return node
