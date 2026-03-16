"""
models.py - Shared character and creature models, and animation logic.
"""

import math

from panda3d.core import (
    GeomVertexFormat,
    GeomVertexData,
    GeomVertexWriter,
    GeomTriangles,
    Geom,
    GeomNode,
    TransparencyAttrib,
    NodePath,
)

from game.world.geometry import make_box_geom, make_sphere_approx
from game.systems.inventory import get_item_def

HEAD_Z = 3.8
HEAD_RADIUS = 0.48
TORSO_SIZE = (0.34, 0.34, 1.32)
ARM_SIZE = (0.18, 0.18, 1.12)
LEG_SIZE = (0.2, 0.2, 1.58)
CHARACTER_FOOT_Z = 0.42
TUNIC_BASE = 0.62
TUNIC_BOTTOM_Z = 2.02
TUNIC_HEAD_GAP = 0.08
DEFAULT_TUNIC_COLOR = (0.68, 0.24, 0.12, 1.0)
DEFAULT_ARROW_COLOR = (1.0, 0.3, 0.1)
ARROW_SHAFT_SIZE = (0.12, 0.82, 0.12)
ARROW_HEAD_SIZE = (0.12, 0.3, 0.12)
SHADOW_RADIUS_X = 0.62
SHADOW_RADIUS_Y = 0.42
SHADOW_ALPHA = 0.18
ARM_REST_ANGLE = 10.0

WALK_FREQ = 3.5
WALK_AMP = 35.0
ATTACK_ANIM_DURATION = 0.3

def _make_shadow_disc(radius_x, radius_y, color, segments=20):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("shadow_disc", fmt, Geom.UHStatic)
    vdata.setNumRows(segments + 1)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")

    vertex.addData3(0, 0, 0)
    normal.addData3(0, 0, 1)
    color_w.addData4(*color)

    for i in range(segments):
        angle = math.radians((i / segments) * 360.0)
        vertex.addData3(math.cos(angle) * radius_x, math.sin(angle) * radius_y, 0)
        normal.addData3(0, 0, 1)
        color_w.addData4(*color)

    tris = GeomTriangles(Geom.UHStatic)
    for i in range(segments):
        tris.addVertices(0, i + 1, (i + 1) % segments + 1)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("shadow_disc")
    node.addGeom(geom)
    return node


class HumanoidModel:
    def __init__(self, parent, skin_color, tunic_color=DEFAULT_TUNIC_COLOR, arrow_color=DEFAULT_ARROW_COLOR):
        self.root = parent.attachNewNode("humanoid_actor")
        self.root.setZ(-CHARACTER_FOOT_Z)
        
        # Equipment state
        self._equipment_models = {}

        # Animation state
        self._idle_t = 0.0
        self._walk_t = 0.0
        self._attack_anim_timer = 0.0
        self._attack_anim_style = None

        tunic_top_z = HEAD_Z - HEAD_RADIUS - TUNIC_HEAD_GAP
        tunic_height = tunic_top_z - TUNIC_BOTTOM_Z

        shadow = self.root.attachNewNode(_make_shadow_disc(SHADOW_RADIUS_X, SHADOW_RADIUS_Y, (0, 0, 0, SHADOW_ALPHA)))
        shadow.setPos(0, 0, 0.03)
        shadow.setTransparency(TransparencyAttrib.MAlpha)
        shadow.setLightOff()
        shadow.setDepthWrite(False)
        shadow.setBin("fixed", 12)

        self.torso = self.root.attachNewNode(make_box_geom(*TORSO_SIZE, skin_color))
        self.torso.setPos(0, 0, 2.66)

        self.tunic = self.root.attachNewNode(make_box_geom(TUNIC_BASE, TUNIC_BASE, tunic_height, tunic_color))
        self.tunic.setPos(0, 0, TUNIC_BOTTOM_Z + tunic_height * 0.5)

        self.head = self.root.attachNewNode(make_sphere_approx(HEAD_RADIUS, skin_color))
        self.head.setPos(0, 0, HEAD_Z)
        
        self.head_anchor = self.head.attachNewNode("head_anchor")
        self.head_anchor.setPos(0, 0, 0)

        self.arrow_root = self.root.attachNewNode("direction_arrow")
        self.arrow_root.setPos(0, 0, HEAD_Z + 0.9)
        arrow_shaft = self.arrow_root.attachNewNode(make_box_geom(*ARROW_SHAFT_SIZE, (*arrow_color, 1.0)))
        arrow_shaft.setPos(0, 0.41, 0)
        arrow_left = self.arrow_root.attachNewNode(make_box_geom(*ARROW_HEAD_SIZE, (*arrow_color, 1.0)))
        arrow_left.setPos(-0.1, 0.74, 0)
        arrow_left.setH(-40)
        arrow_right = self.arrow_root.attachNewNode(make_box_geom(*ARROW_HEAD_SIZE, (*arrow_color, 1.0)))
        arrow_right.setPos(0.1, 0.74, 0)
        arrow_right.setH(40)

        self.l_arm = self.root.attachNewNode("l_arm_pivot")
        self.l_arm.setPos(0, 0, 3.2)
        self.l_arm_geom = self.l_arm.attachNewNode(make_box_geom(*ARM_SIZE, skin_color))
        self.l_arm_geom.setPos(-0.32, 0, -0.58)
        self.l_arm_geom.setR(ARM_REST_ANGLE)
        self.l_hand_anchor = self.l_arm_geom.attachNewNode("l_hand_anchor")
        self.l_hand_anchor.setPos(0, 0, -ARM_SIZE[2] * 0.5)

        self.r_arm = self.root.attachNewNode("r_arm_pivot")
        self.r_arm.setPos(0, 0, 3.2)
        self.r_arm_geom = self.r_arm.attachNewNode(make_box_geom(*ARM_SIZE, skin_color))
        self.r_arm_geom.setPos(0.32, 0, -0.58)
        self.r_arm_geom.setR(-ARM_REST_ANGLE)
        self.r_hand_anchor = self.r_arm_geom.attachNewNode("r_hand_anchor")
        self.r_hand_anchor.setPos(0, 0, -ARM_SIZE[2] * 0.5)

        self.l_leg = self.root.attachNewNode("l_leg_pivot")
        self.l_leg.setPos(0, 0, 2.0)
        self.l_leg_geom = self.l_leg.attachNewNode(make_box_geom(*LEG_SIZE, skin_color))
        self.l_leg_geom.setPos(-0.14, 0, -0.79)

        self.r_leg = self.root.attachNewNode("r_leg_pivot")
        self.r_leg.setPos(0, 0, 2.0)
        self.r_leg_geom = self.r_leg.attachNewNode(make_box_geom(*LEG_SIZE, skin_color))
        self.r_leg_geom.setPos(0.14, 0, -0.79)

    def play_attack(self, style):
        self._attack_anim_timer = ATTACK_ANIM_DURATION
        self._attack_anim_style = style

    def animate(self, dt, moving, speed_mult=1.0):
        self._attack_anim_timer = max(0.0, self._attack_anim_timer - dt)
        self._idle_t += dt

        if moving:
            self._walk_t += dt * WALK_FREQ * speed_mult * 2 * math.pi
        else:
            self._walk_t = 0.0

        swing = math.sin(self._walk_t) * WALK_AMP if moving else 0.0

        # Idle breathing/sway (arms only)
        idle_arm = math.sin(self._idle_t * 1.6) * 7.5

        l_arm_pitch = -swing * 0.6 + idle_arm
        r_arm_pitch = swing * 0.6 + idle_arm
        
        l_leg_pitch = swing
        r_leg_pitch = -swing
        
        # Attack animations blend over these pitches
        if self._attack_anim_timer > 0.0:
            progress = 1.0 - (self._attack_anim_timer / ATTACK_ANIM_DURATION)
            strike_curve = math.sin(progress * math.pi)
            if self._attack_anim_style == "melee":
                r_arm_pitch += 80.0 * strike_curve
            elif self._attack_anim_style == "ranged":
                l_arm_pitch += 70.0 * strike_curve
                r_arm_pitch += 70.0 * strike_curve

        self.l_leg.setP(l_leg_pitch)
        self.r_leg.setP(r_leg_pitch)
        self.l_arm.setP(l_arm_pitch)
        self.r_arm.setP(r_arm_pitch)

    def set_color_scale(self, r, g, b, a):
        self.root.setColorScale(r, g, b, a)

    def hide_arrow(self):
        self.arrow_root.hide()

    def set_equipment(self, slot, model_np):
        """Attach a model or list of models to equipment slot anchors."""
        if slot in self._equipment_models:
            existing = self._equipment_models[slot]
            if isinstance(existing, list):
                for m in existing:
                    if m and not m.isEmpty(): m.removeNode()
            else:
                if existing and not existing.isEmpty():
                    existing.removeNode()
        
        self._equipment_models[slot] = model_np
        if model_np:
            if isinstance(model_np, list):
                for i, m in enumerate(model_np):
                    self._attach_to_slot(slot, m, index=i)
            else:
                self._attach_to_slot(slot, model_np)

    def _attach_to_slot(self, slot, m, index=0):
        if slot == "weapon":
            m.reparentTo(self.r_hand_anchor)
        elif slot == "offhand":
            m.reparentTo(self.l_hand_anchor)
        elif slot == "head":
            m.reparentTo(self.head_anchor)
        elif slot == "chest":
            if index == 0:
                m.reparentTo(self.torso)
            elif index == 1:
                m.reparentTo(self.l_arm_geom)
            elif index == 2:
                m.reparentTo(self.r_arm_geom)
        elif slot == "legs":
            # Expects list [left_leg_armor, right_leg_armor]
            if index == 0:
                m.reparentTo(self.l_leg_geom)
            else:
                m.reparentTo(self.r_leg_geom)


class CreatureModel:
    def __init__(self, parent, main_color, size=(0.8, 1.6, 0.8)):
        self.root = parent.attachNewNode("creature_actor")
        # Grounding fix: legs are now much longer (length is size[2] * 1.25)
        self.root.setZ(size[2] * 1.5)

        # Animation state
        self._idle_t = 0.0
        self._walk_t = 0.0
        self._attack_anim_timer = 0.0
        self._attack_anim_style = None
        self.size = size

        shadow = self.root.attachNewNode(_make_shadow_disc(size[0], size[1], (0, 0, 0, SHADOW_ALPHA)))
        shadow.setPos(0, 0, -size[2] * 1.5 + 0.03) # Adjusted for grounding fix
        shadow.setTransparency(TransparencyAttrib.MAlpha)
        shadow.setLightOff()
        shadow.setDepthWrite(False)
        shadow.setBin("fixed", 12)

        self.body = self.root.attachNewNode(make_box_geom(*size, main_color))
        self.head = self.root.attachNewNode(make_box_geom(size[0]*0.7, size[1]*0.4, size[2]*0.7, main_color))
        self.head.setPos(0, size[1]*0.6, size[2]*0.2)

        # 4 legs (length increased by 2.5x from original 0.5 ratio)
        leg_z = size[2] * 1.25
        self.fl_leg = self._make_leg(main_color, leg_z, -size[0]*0.4, size[1]*0.3)
        self.fr_leg = self._make_leg(main_color, leg_z, size[0]*0.4, size[1]*0.3)
        self.bl_leg = self._make_leg(main_color, leg_z, -size[0]*0.4, -size[1]*0.3)
        self.br_leg = self._make_leg(main_color, leg_z, size[0]*0.4, -size[1]*0.3)

    def _make_leg(self, color, height, x, y):
        pivot = self.root.attachNewNode("leg_pivot")
        pivot.setPos(x, y, -self.size[2] * 0.2)
        geom = pivot.attachNewNode(make_box_geom(self.size[0]*0.2, self.size[0]*0.2, height, color))
        geom.setPos(0, 0, -height*0.5)
        return pivot

    def play_attack(self, style):
        self._attack_anim_timer = ATTACK_ANIM_DURATION
        self._attack_anim_style = style

    def animate(self, dt, moving, speed_mult=1.0):
        self._attack_anim_timer = max(0.0, self._attack_anim_timer - dt)
        self._idle_t += dt

        if moving:
            self._walk_t += dt * WALK_FREQ * speed_mult * 2 * math.pi
        else:
            self._walk_t = 0.0

        swing = math.sin(self._walk_t) * WALK_AMP if moving else 0.0

        self.fl_leg.setP(swing)
        self.br_leg.setP(swing)
        self.fr_leg.setP(-swing)
        self.bl_leg.setP(-swing)

        if self._attack_anim_timer > 0.0:
            progress = 1.0 - (self._attack_anim_timer / ATTACK_ANIM_DURATION)
            strike_curve = math.sin(progress * math.pi)
            # Simple head butt or lunge
            self.root.setP(-15.0 * strike_curve)
        else:
            self.root.setP(math.sin(self._idle_t * 1.5) * 1.5)

    def set_color_scale(self, r, g, b, a):
        self.root.setColorScale(r, g, b, a)

    def hide_arrow(self):
        # Creatures might not have an arrow yet, but expose the method
        pass


def build_sword(item_def):
    """Procedural sword model."""
    root = NodePath("sword_model")
    root.setP(-90)
    
    blade_color = item_def.get("color", (0.72, 0.46, 0.2, 1.0))
    hilt_color = item_def.get("accent_color", (0.35, 0.25, 0.15, 1.0))
    
    blade = root.attachNewNode(make_box_geom(0.12, 0.04, 1.8, blade_color))
    blade.setZ(1.1)
    guard = root.attachNewNode(make_box_geom(0.6, 0.1, 0.1, hilt_color))
    guard.setZ(0.2)
    handle = root.attachNewNode(make_box_geom(0.08, 0.08, 0.4, hilt_color))
    handle.setZ(0.0)
    pommel = root.attachNewNode(make_sphere_approx(0.08, hilt_color))
    pommel.setZ(-0.25)
    
    return root

def build_shield(item_def):
    """Procedural shield model."""
    root = NodePath("shield_model")
    root.setH(0)
    root.setX(-0.4)
    root.setY(0.1)
    
    wood_color = item_def.get("color", (0.45, 0.3, 0.16, 1.0))
    body = root.attachNewNode(make_box_geom(0.15, 1.2, 1.5, wood_color))
    
    trim_color = item_def.get("accent_color", (0.72, 0.46, 0.2, 1.0))
    top_trim = root.attachNewNode(make_box_geom(0.18, 1.3, 0.1, trim_color))
    top_trim.setZ(0.75)
    bottom_trim = root.attachNewNode(make_box_geom(0.18, 1.3, 0.1, trim_color))
    bottom_trim.setZ(-0.75)
    
    return root

def build_hood(item_def):
    """Procedural hood model - rounded."""
    root = NodePath("hood_model")
    color = item_def.get("color", (0.52, 0.22, 0.2, 1.0))
    
    hood = root.attachNewNode(make_sphere_approx(0.55, color))
    hood.setY(-0.05)
    
    return root

def build_armor(item_def):
    """Procedural armor/tunic overlay with sleeves."""
    color = item_def.get("color", (0.64, 0.24, 0.12, 1.0))
    
    torso = NodePath("armor_torso")
    torso.attachNewNode(make_box_geom(0.7, 0.7, 1.4, color))
    
    l_sleeve = NodePath("l_sleeve")
    l_sleeve.attachNewNode(make_box_geom(0.24, 0.24, 0.6, color))
    l_sleeve.setZ(0.25)
    
    r_sleeve = NodePath("r_sleeve")
    r_sleeve.attachNewNode(make_box_geom(0.24, 0.24, 0.6, color))
    r_sleeve.setZ(0.25)
    
    return [torso, l_sleeve, r_sleeve]

def build_legs(item_def):
    """Procedural pants/legs overlay (two nodes)."""
    color = item_def.get("color", (0.4, 0.44, 0.52, 1.0))
    
    l_pant = NodePath("l_leg_armor")
    l_pant.attachNewNode(make_box_geom(0.24, 0.24, 1.62, color))
    
    r_pant = NodePath("r_leg_armor")
    r_pant.attachNewNode(make_box_geom(0.24, 0.24, 1.62, color))
    
    return [l_pant, r_pant]

def build_bow(item_def):
    root = NodePath("bow_model")
    root.setP(-90)
    color = item_def.get("color", (0.5, 0.3, 0.1, 1.0))
    
    center = root.attachNewNode(make_box_geom(0.08, 0.1, 0.8, color))
    center.setZ(0.4)
    top = root.attachNewNode(make_box_geom(0.06, 0.08, 0.7, color))
    top.setZ(0.9)
    top.setY(0.2)
    top.setP(20)
    bot = root.attachNewNode(make_box_geom(0.06, 0.08, 0.7, color))
    bot.setZ(-0.1)
    bot.setY(0.2)
    bot.setP(-20)
    
    string = root.attachNewNode(make_box_geom(0.02, 0.02, 1.8, (0.9, 0.9, 0.9, 1.0)))
    string.setZ(0.4)
    string.setY(0.4)
    return root

def build_crossbow(item_def):
    root = NodePath("crossbow_model")
    root.setP(-90)
    color = item_def.get("color", (0.4, 0.25, 0.15, 1.0))
    
    stock = root.attachNewNode(make_box_geom(0.12, 0.15, 1.2, color))
    stock.setZ(0.4)
    prod = root.attachNewNode(make_box_geom(1.4, 0.1, 0.1, color))
    prod.setZ(0.8)
    return root

def build_book(item_def):
    root = NodePath("book_model")
    root.setP(-90)
    color = item_def.get("color", (0.2, 0.3, 0.6, 1.0))
    
    book = root.attachNewNode(make_box_geom(0.6, 0.2, 0.8, color))
    book.setZ(0.2)
    book.setY(0.2)
    pages = root.attachNewNode(make_box_geom(0.55, 0.18, 0.75, (0.9, 0.9, 0.8, 1.0)))
    pages.setZ(0.2)
    pages.setY(0.22)
    return root

def build_staff(item_def):
    root = NodePath("staff_model")
    root.setP(-90)
    color = item_def.get("color", (0.6, 0.4, 0.2, 1.0))
    accent = item_def.get("accent_color", (0.2, 0.6, 0.9, 1.0))
    
    shaft = root.attachNewNode(make_box_geom(0.08, 0.08, 2.5, color))
    shaft.setZ(0.5)
    tip = root.attachNewNode(make_sphere_approx(0.15, accent))
    tip.setZ(1.8)
    return root

def build_mace(item_def):
    root = NodePath("mace_model")
    root.setP(-90)
    color = item_def.get("color", (0.5, 0.5, 0.5, 1.0))
    
    shaft = root.attachNewNode(make_box_geom(0.08, 0.08, 1.0, (0.4, 0.3, 0.2, 1.0)))
    shaft.setZ(0.5)
    head = root.attachNewNode(make_sphere_approx(0.25, color))
    head.setZ(1.0)
    return root

def build_axe(item_def):
    root = NodePath("axe_model")
    root.setP(-90)
    color = item_def.get("color", (0.6, 0.6, 0.6, 1.0))
    
    shaft = root.attachNewNode(make_box_geom(0.08, 0.08, 1.0, (0.4, 0.3, 0.2, 1.0)))
    shaft.setZ(0.4)
    blade = root.attachNewNode(make_box_geom(0.4, 0.04, 0.3, color))
    blade.setZ(0.8)
    blade.setX(0.2)
    return root

def build_battle_axe(item_def):
    root = NodePath("battle_axe_model")
    root.setP(-90)
    color = item_def.get("color", (0.4, 0.4, 0.4, 1.0))
    
    shaft = root.attachNewNode(make_box_geom(0.1, 0.1, 1.8, (0.3, 0.2, 0.1, 1.0)))
    shaft.setZ(0.8)
    blade1 = root.attachNewNode(make_box_geom(0.6, 0.05, 0.5, color))
    blade1.setZ(1.5)
    blade1.setX(0.3)
    blade2 = root.attachNewNode(make_box_geom(0.6, 0.05, 0.5, color))
    blade2.setZ(1.5)
    blade2.setX(-0.3)
    return root

def build_2h_sword(item_def):
    root = NodePath("2h_sword_model")
    root.setP(-90)
    blade_color = item_def.get("color", (0.7, 0.7, 0.7, 1.0))
    hilt_color = item_def.get("accent_color", (0.2, 0.2, 0.2, 1.0))
    
    blade = root.attachNewNode(make_box_geom(0.16, 0.06, 2.6, blade_color))
    blade.setZ(1.7)
    guard = root.attachNewNode(make_box_geom(0.8, 0.12, 0.12, hilt_color))
    guard.setZ(0.4)
    handle = root.attachNewNode(make_box_geom(0.08, 0.08, 0.8, hilt_color))
    handle.setZ(0.0)
    return root

def build_wand(item_def):
    root = NodePath("wand_model")
    root.setP(-90)
    color = item_def.get("color", (0.8, 0.7, 0.5, 1.0))
    accent = item_def.get("accent_color", (0.9, 0.2, 0.2, 1.0))
    
    shaft = root.attachNewNode(make_box_geom(0.04, 0.04, 0.8, color))
    shaft.setZ(0.4)
    tip = root.attachNewNode(make_sphere_approx(0.06, accent))
    tip.setZ(0.8)
    return root

def build_dagger(item_def):
    root = NodePath("dagger_model")
    root.setP(-90)
    blade_color = item_def.get("color", (0.65, 0.65, 0.7, 1.0))
    hilt_color = item_def.get("accent_color", (0.3, 0.2, 0.1, 1.0))
    
    blade = root.attachNewNode(make_box_geom(0.08, 0.02, 0.8, blade_color))
    blade.setZ(0.5)
    guard = root.attachNewNode(make_box_geom(0.3, 0.06, 0.06, hilt_color))
    guard.setZ(0.1)
    handle = root.attachNewNode(make_box_geom(0.06, 0.06, 0.2, hilt_color))
    handle.setZ(0.0)
    return root

EQUIPMENT_BUILDERS = {
    "sword": build_sword,
    "shield": build_shield,
    "hood": build_hood,
    "armor": build_armor,
    "legs": build_legs,
    "bow": build_bow,
    "crossbow": build_crossbow,
    "book": build_book,
    "staff": build_staff,
    "mace": build_mace,
    "axe": build_axe,
    "battle_axe": build_battle_axe,
    "2h_sword": build_2h_sword,
    "wand": build_wand,
    "dagger": build_dagger
}

def build_equipment_model(item_id):
    item_def = get_item_def(item_id)
    if not item_def:
        return None
    subtype = item_def.get("subtype")
    builder = EQUIPMENT_BUILDERS.get(subtype)
    if builder:
        return builder(item_def)
    return None
