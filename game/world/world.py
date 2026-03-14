"""
world.py — Ground plane, static scenery, collision geometry.
"""

from panda3d.core import Vec3
from panda3d.bullet import BulletRigidBodyNode, BulletPlaneShape, BulletBoxShape

from game.world.geometry import make_box_geom, make_plane_geom


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
