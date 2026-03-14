"""Shared helpers for static Bullet collision geometry."""

from panda3d.core import Vec3
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode


def attach_static_box_collider(render, bullet_world, name, pos, size):
    sx, sy, sz = size
    shape = BulletBoxShape(Vec3(sx * 0.5, sy * 0.5, sz * 0.5))
    body = BulletRigidBodyNode(name)
    body.setMass(0)
    body.addShape(shape)
    body_np = render.attachNewNode(body)
    body_np.setPos(*pos)
    bullet_world.attachRigidBody(body)
    return body_np


def remove_static_collider(bullet_world, collider_np):
    if collider_np is None or collider_np.isEmpty():
        return
    bullet_world.removeRigidBody(collider_np.node())
    collider_np.removeNode()
