"""
resources.py — Tree, Rock, FishingSpot node classes with harvest logic.
State machine: IDLE → HARVESTING → DEPLETED → RESPAWNING → IDLE
"""

import math
from panda3d.core import Vec3, LineSegs, NodePath, GeomVertexFormat, GeomVertexData
from panda3d.core import GeomVertexWriter, GeomTriangles, Geom, GeomNode, BitMask32
from panda3d.core import TransparencyAttrib
from panda3d.bullet import BulletGhostNode, BulletSphereShape

# State constants
IDLE = "idle"
HARVESTING = "harvesting"
DEPLETED = "depleted"
RESPAWNING = "respawning"

PROXIMITY_RADIUS = 3.5
RESPAWN_TIME = 15.0


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _make_cylinder(radius, height, color, segments=12):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("cyl", fmt, Geom.UHStatic)

    sides = segments
    total_verts = sides * 2 + 2  # side strip + top center + bottom center
    # Simpler: just the side quads
    vdata.setNumRows(sides * 4)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal_w = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)

    for i in range(sides):
        a0 = math.radians(i * 360 / sides)
        a1 = math.radians((i + 1) * 360 / sides)
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


def _make_sphere_approx(radius, color, stacks=6, slices=8):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("sphere", fmt, Geom.UHStatic)

    rows = stacks * slices * 4
    vdata.setNumRows(rows)
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
                (radius * math.cos(phi0) * math.cos(th0),
                 radius * math.cos(phi0) * math.sin(th0),
                 radius * math.sin(phi0)),
                (radius * math.cos(phi0) * math.cos(th1),
                 radius * math.cos(phi0) * math.sin(th1),
                 radius * math.sin(phi0)),
                (radius * math.cos(phi1) * math.cos(th1),
                 radius * math.cos(phi1) * math.sin(th1),
                 radius * math.sin(phi1)),
                (radius * math.cos(phi1) * math.cos(th0),
                 radius * math.cos(phi1) * math.sin(th0),
                 radius * math.sin(phi1)),
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


def _make_box_geom(sx, sy, sz, color):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("box", fmt, Geom.UHStatic)
    vdata.setNumRows(24)

    hx, hy, hz = sx / 2, sy / 2, sz / 2
    face_verts = [
        [(-hx, -hy, -hz), (-hx,  hy, -hz), ( hx,  hy, -hz), ( hx, -hy, -hz)],  # bottom
        [(-hx, -hy,  hz), ( hx, -hy,  hz), ( hx,  hy,  hz), (-hx,  hy,  hz)],  # top
        [(-hx, -hy, -hz), ( hx, -hy, -hz), ( hx, -hy,  hz), (-hx, -hy,  hz)],  # back
        [(-hx,  hy, -hz), (-hx,  hy,  hz), ( hx,  hy,  hz), ( hx,  hy, -hz)],  # front
        [(-hx, -hy, -hz), (-hx, -hy,  hz), (-hx,  hy,  hz), (-hx,  hy, -hz)],  # left
        [( hx, -hy, -hz), ( hx,  hy, -hz), ( hx,  hy,  hz), ( hx, -hy,  hz)],  # right
    ]
    normals_list = [(0, 0, -1), (0, 0, 1), (0, -1, 0), (0, 1, 0), (-1, 0, 0), (1, 0, 0)]

    vertex = GeomVertexWriter(vdata, "vertex")
    normal_w = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)

    for fi, (face, nrm) in enumerate(zip(face_verts, normals_list)):
        base = fi * 4
        for v in face:
            vertex.addData3(*v)
            normal_w.addData3(*nrm)
            color_w.addData4(*color)
        tris.addVertices(base, base+1, base+2)
        tris.addVertices(base, base+2, base+3)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("box")
    node.addGeom(geom)
    return node


# ---------------------------------------------------------------------------
# Base ResourceNode
# ---------------------------------------------------------------------------

class ResourceNode:
    def __init__(self, render, bullet_world, pos, item_id, skill, harvest_time, xp_reward):
        self.render = render
        self.bullet_world = bullet_world
        self.pos = Vec3(*pos)
        self.item_id = item_id
        self.skill = skill
        self.harvest_time = harvest_time
        self.xp_reward = xp_reward

        self.state = IDLE
        self.harvest_timer = 0.0
        self.respawn_timer = 0.0
        self.in_range = False

        self.root = NodePath("resource_root")
        self.root.reparentTo(render)
        self.root.setPos(self.pos)

        # Ghost node for proximity
        ghost_shape = BulletSphereShape(PROXIMITY_RADIUS)
        self.ghost = BulletGhostNode("resource_ghost")
        self.ghost.addShape(ghost_shape)
        self.ghost_np = render.attachNewNode(self.ghost)
        self.ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 1.5)
        bullet_world.attachGhost(self.ghost)

        self._build_visuals()
        self._setup_input()

    def _setup_input(self):
        # E key handled centrally in main.py; just track state here
        self._e_held = False

    def _on_e_pressed(self):
        self._e_held = True

    def _on_e_released(self):
        self._e_held = False
        if self.state == HARVESTING:
            self.state = IDLE
            self.harvest_timer = 0.0

    def _build_visuals(self):
        pass  # Overridden by subclasses

    def _set_depleted_look(self):
        pass  # Overridden

    def _reset_look(self):
        pass  # Overridden

    def _check_proximity(self, player_pos):
        dx = player_pos.x - self.pos.x
        dy = player_pos.y - self.pos.y
        dist = math.sqrt(dx * dx + dy * dy)
        return dist <= PROXIMITY_RADIUS

    def update(self, dt, player_pos, player, inventory, hud):
        self.in_range = self._check_proximity(player_pos)

        if self.state == IDLE:
            if self.in_range:
                hud.show_prompt(f"Hold E to harvest {self.item_id}")
                if self._e_held:
                    self.state = HARVESTING
                    self.harvest_timer = 0.0
            else:
                hud.clear_prompt_if(f"Hold E to harvest {self.item_id}")

        elif self.state == HARVESTING:
            if not self.in_range or not self._e_held:
                self.state = IDLE
                self.harvest_timer = 0.0
                hud.clear_prompt_if(f"Hold E to harvest {self.item_id}")
                return

            self.harvest_timer += dt
            hud.show_prompt(f"Harvesting... {self.harvest_timer:.1f}/{self.harvest_time:.1f}s")

            if self.harvest_timer >= self.harvest_time:
                if inventory.is_full():
                    hud.show_prompt("Inventory full!")
                    self.state = IDLE
                    self.harvest_timer = 0.0
                else:
                    inventory.add_item(self.item_id)
                    levels = inventory.add_xp(self.skill, self.xp_reward)
                    hud.refresh_inventory()
                    hud.refresh_skills()
                    if levels > 0:
                        hud.show_prompt(f"{self.skill} level up! Level {inventory.get_level(self.skill)}")
                    self.state = DEPLETED
                    self.respawn_timer = 0.0
                    self._set_depleted_look()

        elif self.state == DEPLETED:
            hud.clear_prompt_if(f"Hold E to harvest {self.item_id}")

        elif self.state == RESPAWNING:
            self.respawn_timer += dt
            if self.respawn_timer >= RESPAWN_TIME:
                self.state = IDLE
                self._reset_look()

        # Transition depleted → respawning after a short pause
        if self.state == DEPLETED:
            self.respawn_timer += dt
            if self.respawn_timer >= 2.0:
                self.state = RESPAWNING


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------

class Tree(ResourceNode):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos,
                         item_id="wood", skill="Woodcutting",
                         harvest_time=2.5, xp_reward=25)

    def _build_visuals(self):
        # Trunk
        trunk = self.root.attachNewNode(_make_cylinder(0.3, 3.0, (0.4, 0.25, 0.1, 1)))
        # Foliage (sphere on top)
        foliage = self.root.attachNewNode(_make_sphere_approx(1.5, (0.15, 0.55, 0.1, 1)))
        foliage.setPos(0, 0, 3.5)
        self._trunk = trunk
        self._foliage = foliage
        self._depleted_color = (0.4, 0.35, 0.3, 1)
        self._active_foliage_color = (0.15, 0.55, 0.1, 1)

    def _set_depleted_look(self):
        self._foliage.setColorScale(0.5, 0.5, 0.5, 1)
        self._trunk.setColorScale(0.5, 0.5, 0.5, 1)

    def _reset_look(self):
        self._foliage.setColorScale(1, 1, 1, 1)
        self._trunk.setColorScale(1, 1, 1, 1)


# ---------------------------------------------------------------------------
# Rock
# ---------------------------------------------------------------------------

class Rock(ResourceNode):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos,
                         item_id="ore", skill="Mining",
                         harvest_time=3.5, xp_reward=35)

    def _build_visuals(self):
        # Cluster of two offset boxes
        c = (0.45, 0.45, 0.45, 1)
        b1 = self.root.attachNewNode(_make_box_geom(1.5, 1.5, 1.2, c))
        b1.setPos(-0.3, 0, 0)
        b2 = self.root.attachNewNode(_make_box_geom(1.0, 1.0, 1.5, c))
        b2.setPos(0.6, 0.2, 0.1)
        self._parts = [b1, b2]

    def _set_depleted_look(self):
        for p in self._parts:
            p.setColorScale(0.3, 0.3, 0.3, 1)

    def _reset_look(self):
        for p in self._parts:
            p.setColorScale(1, 1, 1, 1)


# ---------------------------------------------------------------------------
# FishingSpot
# ---------------------------------------------------------------------------

class FishingSpot(ResourceNode):
    def __init__(self, render, bullet_world, pos):
        super().__init__(render, bullet_world, pos,
                         item_id="fish", skill="Fishing",
                         harvest_time=4.0, xp_reward=30)
        self._anim_timer = 0.0

    def _build_visuals(self):
        # Animated blue plane (we animate color/scale each frame)
        from panda3d.core import CardMaker
        cm = CardMaker("fishing_spot")
        cm.setFrame(-1.5, 1.5, -1.5, 1.5)
        self._plane = self.root.attachNewNode(cm.generate())
        self._plane.setP(-90)  # lay flat
        self._plane.setColor(0.2, 0.5, 0.8, 0.8)
        self._plane.setTransparency(TransparencyAttrib.MAlpha)

    def update(self, dt, player_pos, player, inventory, hud):
        # Animate the water shimmer
        self._anim_timer += dt
        scale = 1.0 + 0.08 * math.sin(self._anim_timer * 3.0)
        self._plane.setScale(scale, scale, 1)
        super().update(dt, player_pos, player, inventory, hud)

    def _set_depleted_look(self):
        self._plane.setColor(0.5, 0.5, 0.5, 0.5)

    def _reset_look(self):
        self._plane.setColor(0.2, 0.5, 0.8, 0.8)
