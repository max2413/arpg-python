"""World terrain, static scenery, and collision geometry.
URSINA Y-UP VERSION
"""

from panda3d.core import Vec3
from panda3d.bullet import (
    BulletPlaneShape,
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
)

from game.world.collision import attach_static_box_collider, remove_static_collider
from game.world.geometry import make_box_geom, make_terrain_geom
from game.world.terrain import TerrainField

WORLD_HALF = 500
TERRAIN_RENDER_STEP = 12
TERRAIN_COLLISION_BASE_Y = -20.0


class World:
    def __init__(self, render, bullet_world, seed=42, world_half=WORLD_HALF):
        self.render = render
        self.bullet_world = bullet_world
        self.world_half = world_half
        self.terrain = TerrainField(world_half=world_half, seed=seed)
        self._ground_np = None
        self._base_ground_np = None
        self._terrain_body_np = None
        self._terrain_mesh = None
        self._scenery_nodes = []
        self._scenery_colliders = []

        self._build_base_ground()
        self.refresh_terrain()
        self._make_scenery()

    def refresh_terrain(self):
        if self._ground_np is not None and not self._ground_np.isEmpty():
            self._ground_np.removeNode()
        if self._terrain_body_np is not None and not self._terrain_body_np.isEmpty():
            self.bullet_world.removeRigidBody(self._terrain_body_np.node())
            self._terrain_body_np.removeNode()
            self._terrain_body_np = None

        ground_node = make_terrain_geom(self.terrain, self.world_half, TERRAIN_RENDER_STEP)
        self._ground_np = self.render.attachNewNode(ground_node)
        self._build_terrain_collision()

    def _build_base_ground(self):
        if self._base_ground_np is not None and not self._base_ground_np.isEmpty():
            return
        # URSINA Y-UP: Normal points Up on Y
        shape = BulletPlaneShape(Vec3(0, 1, 0), 0)
        body = BulletRigidBodyNode("base_ground")
        body.setMass(0)
        body.addShape(shape)
        self._base_ground_np = self.render.attachNewNode(body)
        self._base_ground_np.setPos(0, TERRAIN_COLLISION_BASE_Y, 0)
        self.bullet_world.attachRigidBody(body)

    def _build_terrain_collision(self):
        mesh = BulletTriangleMesh()
        geom = self._ground_np.node().getGeom(0)
        mesh.addGeom(geom)
        self._terrain_mesh = mesh
        shape = BulletTriangleMeshShape(mesh, dynamic=False)
        body = BulletRigidBodyNode("terrain_mesh")
        body.setMass(0)
        body.addShape(shape)
        self._terrain_body_np = self.render.attachNewNode(body)
        self._terrain_body_np.setPos(0, 0, 0)
        self.bullet_world.attachRigidBody(body)

    def _make_box(self, pos, size, color):
        geom_node = make_box_geom(size[0], size[1], size[2], color)
        np = self.render.attachNewNode(geom_node)
        np.setPos(*pos)
        collider = attach_static_box_collider(self.render, self.bullet_world, "wall", pos, size)
        self._scenery_nodes.append(np)
        self._scenery_colliders.append(collider)

    def _make_scenery(self):
        wall_color = (0.6, 0.5, 0.4, 1)
        edge = self.world_half

        # Boundary walls (invisible fences) on XZ plane
        # size: (width_x, height_y, depth_z)
        for x, z, sx, sz in [
            (0, edge, edge * 2, 2),
            (0, -edge, edge * 2, 2),
            (edge, 0, 2, edge * 2),
            (-edge, 0, 2, edge * 2),
        ]:
            # Height = 12, Y-center = 6
            self._make_box((x, 6, z), (sx, 12, sz), wall_color)

    def destroy(self):
        if self._ground_np is not None and not self._ground_np.isEmpty():
            self._ground_np.removeNode()
            self._ground_np = None
        if self._terrain_body_np is not None and not self._terrain_body_np.isEmpty():
            self.bullet_world.removeRigidBody(self._terrain_body_np.node())
            self._terrain_body_np.removeNode()
            self._terrain_body_np = None
        if self._base_ground_np is not None and not self._base_ground_np.isEmpty():
            self.bullet_world.removeRigidBody(self._base_ground_np.node())
            self._base_ground_np.removeNode()
            self._base_ground_np = None
        for collider in self._scenery_colliders:
            remove_static_collider(self.bullet_world, collider)
        self._scenery_colliders = []
        for node in self._scenery_nodes:
            if node is not None and not node.isEmpty():
                node.removeNode()
        self._scenery_nodes = []
        self._terrain_mesh = None
