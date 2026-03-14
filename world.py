"""
world.py — Ground plane, static scenery, collision geometry.
"""

from panda3d.core import Vec3, Vec4, NodePath, GeomVertexFormat, GeomVertexData
from panda3d.core import GeomVertexWriter, GeomTriangles, Geom, GeomNode
from panda3d.bullet import BulletRigidBodyNode, BulletPlaneShape, BulletBoxShape


def make_plane_geom(half_size=100):
    """Build a flat quad mesh for the ground."""
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("ground", fmt, Geom.UHStatic)
    vdata.setNumRows(4)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    color = GeomVertexWriter(vdata, "color")

    s = half_size
    for x, y in [(-s, -s), (s, -s), (s, s), (-s, s)]:
        vertex.addData3(x, y, 0)
        normal.addData3(0, 0, 1)
        color.addData4(0.28, 0.55, 0.22, 1)  # grass green

    tris = GeomTriangles(Geom.UHStatic)
    tris.addVertices(0, 1, 2)
    tris.addVertices(0, 2, 3)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("ground_geom")
    node.addGeom(geom)
    return node


def make_box_geom(sx, sy, sz, color):
    """Build a solid box mesh (for walls/platforms) with a given color."""
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("box", fmt, Geom.UHStatic)

    hx, hy, hz = sx / 2, sy / 2, sz / 2

    face_verts = [
        [(-hx, -hy, -hz), (-hx,  hy, -hz), ( hx,  hy, -hz), ( hx, -hy, -hz)],  # bottom
        [(-hx, -hy,  hz), ( hx, -hy,  hz), ( hx,  hy,  hz), (-hx,  hy,  hz)],  # top
        [(-hx, -hy, -hz), ( hx, -hy, -hz), ( hx, -hy,  hz), (-hx, -hy,  hz)],  # back
        [(-hx,  hy, -hz), (-hx,  hy,  hz), ( hx,  hy,  hz), ( hx,  hy, -hz)],  # front
        [(-hx, -hy, -hz), (-hx, -hy,  hz), (-hx,  hy,  hz), (-hx,  hy, -hz)],  # left
        [( hx, -hy, -hz), ( hx,  hy, -hz), ( hx,  hy,  hz), ( hx, -hy,  hz)],  # right
    ]
    normals_list = [
        (0, 0, -1), (0, 0, 1), (0, -1, 0), (0, 1, 0), (-1, 0, 0), (1, 0, 0)
    ]

    vdata.setNumRows(24)
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


class World:
    def __init__(self, render, bullet_world):
        self.render = render
        self.bullet_world = bullet_world

        self._make_ground()
        self._make_scenery()

    def _make_ground(self):
        # Visual ground mesh — fixed bin sort=10 so decals (sort=15) draw on top
        ground_node = make_plane_geom(500)
        ground_np = self.render.attachNewNode(ground_node)
        ground_np.setPos(0, 0, 0)
        ground_np.setBin("fixed", 10)

        # Bullet collision plane
        shape = BulletPlaneShape(Vec3(0, 0, 1), 0)
        body = BulletRigidBodyNode("ground")
        body.addShape(shape)
        body_np = self.render.attachNewNode(body)
        body_np.setPos(0, 0, 0)
        self.bullet_world.attachRigidBody(body)

    def _make_box(self, pos, size, color):
        sx, sy, sz = size
        # Visual
        geom_node = make_box_geom(sx, sy, sz, color)
        np = self.render.attachNewNode(geom_node)
        np.setPos(*pos)

        # Physics
        shape = BulletBoxShape(Vec3(sx / 2, sy / 2, sz / 2))
        body = BulletRigidBodyNode("wall")
        body.setMass(0)
        body.addShape(shape)
        body_np = self.render.attachNewNode(body)
        body_np.setPos(pos[0], pos[1], pos[2])
        self.bullet_world.attachRigidBody(body)

    def _make_scenery(self):
        wall_color = (0.6, 0.5, 0.4, 1)
        platform_color = (0.5, 0.45, 0.35, 1)

        # Boundary walls (invisible fences)
        for x, y, sx, sy in [
            (0,  500, 1000, 2),
            (0, -500, 1000, 2),
            ( 500, 0, 2, 1000),
            (-500, 0, 2, 1000),
        ]:
            self._make_box((x, y, 2), (sx, sy, 4), wall_color)

        # Raised platforms for variety
        self._make_box((5, -15, 0), (8, 8, 2), platform_color)
        self._make_box((-5, 15, 0), (6, 6, 3), platform_color)
