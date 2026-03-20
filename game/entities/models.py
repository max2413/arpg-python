"""
models.py - Shared character and creature models, and animation logic.
URSINA Y-UP VERSION
"""

import math

from ursina import Entity, Vec3, color
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

# URSINA Y-UP: Y is vertical
HEAD_Y = 3.8
HEAD_RADIUS = 0.48
FACE_EYE_RADIUS = 0.045
FACE_EYE_FORWARD = HEAD_RADIUS * 0.88
FACE_EYE_X = 0.14
FACE_EYE_Y = 0.08
FACE_MOUTH_SIZE = (0.18, 0.03, 0.03)
FACE_MOUTH_FORWARD = HEAD_RADIUS * 0.9
FACE_MOUTH_Y = -0.12
FACE_COLOR = (0.08, 0.08, 0.08, 1.0)
CHEST_SIZE = (0.45, 0.7, 0.34)
WAIST_SIZE = (0.34, 0.62, 0.3)
UPPER_ARM_SIZE = (0.18, 0.56, 0.18)
LOWER_ARM_SIZE = (0.16, 0.56, 0.16)
HAND_RADIUS = 0.12
UPPER_LEG_SIZE = (0.2, 0.79, 0.2)
LOWER_LEG_SIZE = (0.18, 0.79, 0.18)
FOOT_SIZE = (0.22, 0.14, 0.34)
CHARACTER_FOOT_Y = 0.37
TUNIC_BASE = 0.62
TUNIC_BOTTOM_Y = 2.02
TUNIC_HEAD_GAP = 0.08
DEFAULT_TUNIC_COLOR = (0.68, 0.24, 0.12, 1.0)
DEFAULT_ARROW_COLOR = (1.0, 0.3, 0.1)
ARROW_SHAFT_SIZE = (0.12, 0.12, 0.82)
ARROW_HEAD_SIZE = (0.12, 0.12, 0.3)
SHADOW_RADIUS_X = 0.62
SHADOW_RADIUS_Z = 0.42
SHADOW_ALPHA = 0.18
ARM_REST_ANGLE = 10.0
ARM_HANG_ROLL = 8.0
SHOULDER_GAP = 0.05

WALK_FREQ = 1.8
WALK_AMP = 35.0
ATTACK_ANIM_DURATION = 0.3
WORK_ANIM_DURATION = 0.35

def _make_shadow_disc(radius_x, radius_z, color, segments=20):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("shadow_disc", fmt, Geom.UHStatic)
    vdata.setNumRows(segments + 1)
    vertex = GeomVertexWriter(vdata, "vertex"); normal = GeomVertexWriter(vdata, "normal"); color_w = GeomVertexWriter(vdata, "color")
    vertex.addData3(0, 0, 0); normal.addData3(0, 1, 0); color_w.addData4(*color)
    for i in range(segments):
        angle = math.radians((i / segments) * 360.0)
        vertex.addData3(math.cos(angle) * radius_x, 0, math.sin(angle) * radius_z); normal.addData3(0, 1, 0); color_w.addData4(*color)
    tris = GeomTriangles(Geom.UHStatic)
    for i in range(segments): tris.addVertices(0, i + 1, (i + 1) % segments + 1)
    geom = Geom(vdata); geom.addPrimitive(tris); node = GeomNode("shadow_disc"); node.addGeom(geom)
    return node

class HumanoidModel(Entity):
    def __init__(self, parent, skin_color, tunic_color=DEFAULT_TUNIC_COLOR, arrow_color=DEFAULT_ARROW_COLOR):
        super().__init__(parent=parent)
        # Use ourself as the root
        self.root = self
        self.y = -CHARACTER_FOOT_Y
        
        self._equipment_models = {}
        self._idle_t = 0.0; self._walk_t = 0.0; self._attack_anim_timer = 0.0; self._attack_anim_style = None; self._work_anim_timer = 0.0

        shadow = self.attachNewNode(_make_shadow_disc(SHADOW_RADIUS_X, SHADOW_RADIUS_Z, (0, 0, 0, SHADOW_ALPHA)))
        shadow.setY(0.03); shadow.setTransparency(TransparencyAttrib.MAlpha); shadow.setLightOff(); shadow.setDepthWrite(False); shadow.setBin("fixed", 12)

        self.waist = self.attachNewNode(make_box_geom(*WAIST_SIZE, skin_color))
        self.waist.setPos(0, 2.02 + WAIST_SIZE[1] * 0.5, 0)
        self.chest = self.waist.attachNewNode(make_box_geom(*CHEST_SIZE, skin_color))
        self.chest.setPos(0, WAIST_SIZE[1] * 0.5 + CHEST_SIZE[1] * 0.5, 0)

        tunic_h = WAIST_SIZE[1] + CHEST_SIZE[1]
        self.tunic = self.attachNewNode(make_box_geom(TUNIC_BASE, tunic_h, TUNIC_BASE, tunic_color))
        self.tunic.setPos(0, TUNIC_BOTTOM_Y + tunic_h * 0.5, 0)

        self.head = self.attachNewNode(make_sphere_approx(HEAD_RADIUS, skin_color))
        self.head.setPos(0, HEAD_Y, 0); self._build_face()
        
        self.head_anchor = self.head.attachNewNode("head_anchor")
        self.back_anchor = self.chest.attachNewNode("back_anchor")
        self.back_anchor.setPos(0, 0.1, -0.22); self.back_anchor.setH(90); self.back_anchor.setP(-20)

        self.arrow_root = self.attachNewNode("direction_arrow")
        self.arrow_root.setPos(0, HEAD_Y + 0.9, 0)
        arrow_shaft = self.arrow_root.attachNewNode(make_box_geom(*ARROW_SHAFT_SIZE, (*arrow_color, 1.0))); arrow_shaft.setPos(0, 0, 0.41)
        arrow_left = self.arrow_root.attachNewNode(make_box_geom(*ARROW_HEAD_SIZE, (*arrow_color, 1.0))); arrow_left.setPos(-0.1, 0, 0.74); arrow_left.setH(-40)
        arrow_right = self.arrow_root.attachNewNode(make_box_geom(*ARROW_HEAD_SIZE, (*arrow_color, 1.0))); arrow_right.setPos(0.1, 0, 0.74); arrow_right.setH(40)

        self.l_arm = self.chest.attachNewNode("l_arm_pivot"); self.l_arm.setPos(-CHEST_SIZE[0]*0.5 - SHOULDER_GAP, CHEST_SIZE[1]*0.3, 0); self.l_arm.setR(ARM_HANG_ROLL)
        self.l_upper_arm = self.l_arm.attachNewNode(make_box_geom(*UPPER_ARM_SIZE, skin_color)); self.l_upper_arm.setPos(-UPPER_ARM_SIZE[0]*0.5, -UPPER_ARM_SIZE[1]*0.5, 0)
        self.l_elbow = self.l_upper_arm.attachNewNode("l_elbow_pivot"); self.l_elbow.setPos(0, -UPPER_ARM_SIZE[1]*0.5, 0)
        self.l_lower_arm = self.l_elbow.attachNewNode(make_box_geom(*LOWER_ARM_SIZE, skin_color)); self.l_lower_arm.setPos(0, -LOWER_ARM_SIZE[1]*0.5, 0)
        self.l_hand = self.l_lower_arm.attachNewNode(make_sphere_approx(HAND_RADIUS, skin_color)); self.l_hand.setPos(0, -LOWER_ARM_SIZE[1]*0.5, 0); self.l_hand_anchor = self.l_hand.attachNewNode("l_hand_anchor")

        self.r_arm = self.chest.attachNewNode("r_arm_pivot"); self.r_arm.setPos(CHEST_SIZE[0]*0.5 + SHOULDER_GAP, CHEST_SIZE[1]*0.3, 0); self.r_arm.setR(-ARM_HANG_ROLL)
        self.r_upper_arm = self.r_arm.attachNewNode(make_box_geom(*UPPER_ARM_SIZE, skin_color)); self.r_upper_arm.setPos(UPPER_ARM_SIZE[0]*0.5, -UPPER_ARM_SIZE[1]*0.5, 0)
        self.r_elbow = self.r_upper_arm.attachNewNode("r_elbow_pivot"); self.r_elbow.setPos(0, -UPPER_ARM_SIZE[1]*0.5, 0)
        self.r_lower_arm = self.r_elbow.attachNewNode(make_box_geom(*LOWER_ARM_SIZE, skin_color)); self.r_lower_arm.setPos(0, -LOWER_ARM_SIZE[1]*0.5, 0)
        self.r_hand = self.r_lower_arm.attachNewNode(make_sphere_approx(HAND_RADIUS, skin_color)); self.r_hand.setPos(0, -LOWER_ARM_SIZE[1]*0.5, 0); self.r_hand_anchor = self.r_hand.attachNewNode("r_hand_anchor")

        leg_y = 2.02
        self.l_leg = self.attachNewNode("l_leg_pivot"); self.l_leg.setPos(-0.14, leg_y, 0)
        self.l_upper_leg = self.l_leg.attachNewNode(make_box_geom(*UPPER_LEG_SIZE, skin_color)); self.l_upper_leg.setPos(0, -UPPER_LEG_SIZE[1]*0.5, 0)
        self.l_knee = self.l_upper_leg.attachNewNode("l_knee_pivot"); self.l_knee.setPos(0, -UPPER_LEG_SIZE[1]*0.5, 0)
        self.l_lower_leg = self.l_knee.attachNewNode(make_box_geom(*LOWER_LEG_SIZE, skin_color)); self.l_lower_leg.setPos(0, -LOWER_LEG_SIZE[1]*0.5, 0)
        self.l_foot = self.l_lower_leg.attachNewNode(make_box_geom(*FOOT_SIZE, skin_color)); self.l_foot.setPos(0, -LOWER_LEG_SIZE[1]*0.5, FOOT_SIZE[2]*0.3)

        self.r_leg = self.attachNewNode("r_leg_pivot"); self.r_leg.setPos(0.14, leg_y, 0)
        self.r_upper_leg = self.r_leg.attachNewNode(make_box_geom(*UPPER_LEG_SIZE, skin_color)); self.r_upper_leg.setPos(0, -UPPER_LEG_SIZE[1]*0.5, 0)
        self.r_knee = self.r_upper_leg.attachNewNode("r_knee_pivot"); self.r_knee.setPos(0, -UPPER_LEG_SIZE[1]*0.5, 0)
        self.r_lower_leg = self.r_knee.attachNewNode(make_box_geom(*LOWER_LEG_SIZE, skin_color)); self.r_lower_leg.setPos(0, -LOWER_LEG_SIZE[1]*0.5, 0)
        self.r_foot = self.r_lower_leg.attachNewNode(make_box_geom(*FOOT_SIZE, skin_color)); self.r_foot.setPos(0, -LOWER_LEG_SIZE[1]*0.5, FOOT_SIZE[2]*0.3)

    def _build_face(self):
        l_eye = self.head.attachNewNode(make_sphere_approx(FACE_EYE_RADIUS, FACE_COLOR)); l_eye.setPos(-FACE_EYE_X, FACE_EYE_Y, FACE_EYE_FORWARD)
        r_eye = self.head.attachNewNode(make_sphere_approx(FACE_EYE_RADIUS, FACE_COLOR)); r_eye.setPos(FACE_EYE_X, FACE_EYE_Y, FACE_EYE_FORWARD)
        mouth = self.head.attachNewNode(make_box_geom(*FACE_MOUTH_SIZE, FACE_COLOR)); mouth.setPos(0, FACE_MOUTH_Y, FACE_MOUTH_FORWARD)

    def play_attack(self, style): self._attack_anim_timer = ATTACK_ANIM_DURATION; self._attack_anim_style = style
    def play_work(self):
        if self._work_anim_timer <= 0.0: self._work_anim_timer = WORK_ANIM_DURATION

    def animate(self, dt, moving, speed_mult=1.0):
        self._attack_anim_timer = max(0.0, self._attack_anim_timer - dt); self._work_anim_timer = max(0.0, self._work_anim_timer - dt); self._idle_t += dt
        if moving: self._walk_t += dt * WALK_FREQ * speed_mult * 2 * math.pi
        else: self._walk_t = 0.0
        swing = math.sin(self._walk_t) * WALK_AMP if moving else 0.0
        knee_bend = abs(math.sin(self._walk_t)) * 40.0 if moving else 0.0
        elbow_swing = (math.sin(self._walk_t + math.pi*0.5) + 1.0) * 20.0 if moving else 10.0
        idle_sway = math.sin(self._idle_t * 1.6); idle_arm = idle_sway * 7.5; idle_chest = idle_sway * 2.0
        l_arm_p = -swing * 0.6 + idle_arm; r_arm_p = swing * 0.6 + idle_arm; l_elbow_p = elbow_swing; r_elbow_p = elbow_swing
        l_leg_p, r_leg_p = swing, -swing
        l_knee_p = -knee_bend if l_leg_p < 0 else -knee_bend * 0.15
        r_knee_p = -knee_bend if r_leg_p < 0 else -knee_bend * 0.15
        chest_p = idle_chest
        if self._attack_anim_timer > 0.0:
            prog = 1.0 - (self._attack_anim_timer / ATTACK_ANIM_DURATION); curve = math.sin(prog * math.pi)
            if self._attack_anim_style == "melee": r_arm_p += 80.0 * curve; r_elbow_p += 50.0 * curve
            elif self._attack_anim_style == "ranged": l_arm_p += 70.0 * curve; r_arm_p += 70.0 * curve; l_elbow_p += 40.0 * curve; r_elbow_p += 40.0 * curve
        elif self._work_anim_timer > 0.0:
            prog = 1.0 - (self._work_anim_timer / WORK_ANIM_DURATION); curve = math.sin(prog * math.pi)
            chest_p = idle_chest - 6.0 * curve; l_arm_p = 40.0 + 22.0 * curve; r_arm_p = 58.0 + 42.0 * curve; l_elbow_p = 42.0 + 24.0 * curve; r_elbow_p = 68.0 + 38.0 * curve; l_leg_p = -8.0 * curve; r_leg_p = 6.0 * curve; l_knee_p = -10.0 * curve; r_knee_p = -6.0 * curve
        self.chest.setP(chest_p); self.l_leg.setP(l_leg_p); self.r_leg.setP(r_leg_p); self.l_knee.setP(l_knee_p); self.r_knee.setP(r_knee_p); self.l_arm.setP(l_arm_p); self.r_arm.setP(r_arm_p); self.l_elbow.setP(l_elbow_p); self.r_elbow.setP(r_elbow_p)

    def set_color_scale(self, r, g, b, a): self.setColorScale(r, g, b, a)
    def hide_arrow(self): self.arrow_root.hide()
    def set_equipment(self, slot, model_np):
        if slot in self._equipment_models:
            ex = self._equipment_models[slot]
            if isinstance(ex, list):
                for m in ex:
                    if m and not m.isEmpty(): m.removeNode()
            elif ex and not ex.isEmpty(): ex.removeNode()
        self._equipment_models[slot] = model_np
        if model_np:
            if isinstance(model_np, list):
                for i, m in enumerate(model_np): self._attach_to_slot(slot, m, index=i)
            else: self._attach_to_slot(slot, model_np)

    def _attach_to_slot(self, slot, m, index=0):
        if slot == "weapon": m.reparentTo(self.r_hand_anchor)
        elif slot == "offhand": m.reparentTo(self.l_hand_anchor)
        elif slot == "ranged": m.reparentTo(self.back_anchor)
        elif slot == "head": m.reparentTo(self.head_anchor)
        elif slot == "chest":
            if index == 0: m.reparentTo(self.chest)
            elif index == 1: m.reparentTo(self.waist)
            elif index == 2: m.reparentTo(self.l_upper_arm)
            elif index == 3: m.reparentTo(self.r_upper_arm)
        elif slot == "legs":
            if index == 0: m.reparentTo(self.l_upper_leg)
            else: m.reparentTo(self.r_upper_leg)
        elif slot == "hands":
            if index == 0: m.reparentTo(self.l_lower_arm)
            else: m.reparentTo(self.r_lower_arm)
        elif slot == "feet":
            if index == 0: m.reparentTo(self.l_foot)
            else: m.reparentTo(self.r_foot)

class CreatureModel(Entity):
    def __init__(self, parent, main_color, size=(0.8, 1.6, 0.8)):
        super().__init__(parent=parent)
        self.root = self
        self.y = size[1] * 0.5 + size[1] * 0.25
        self._idle_t = 0.0; self._walk_t = 0.0; self._attack_anim_timer = 0.0; self._attack_anim_style = None; self.size = size
        shadow = self.attachNewNode(_make_shadow_disc(size[0], size[2], (0, 0, 0, SHADOW_ALPHA)))
        shadow.setY(-size[1]*0.75 + 0.03); shadow.setTransparency(TransparencyAttrib.MAlpha); shadow.setLightOff(); shadow.setDepthWrite(False); shadow.setBin("fixed", 12)
        self.body = self.attachNewNode(make_box_geom(*size, main_color))
        self.head = self.attachNewNode(make_box_geom(size[0]*0.7, size[1]*0.4, size[2]*0.7, main_color)); self.head.setPos(0, size[1]*0.2, size[2]*0.6)
        leg_y = size[1] * 0.5
        self.fl_leg = self._make_leg(main_color, leg_y, -size[0]*0.4, size[2]*0.3)
        self.fr_leg = self._make_leg(main_color, leg_y, size[0]*0.4, size[2]*0.3)
        self.bl_leg = self._make_leg(main_color, leg_y, -size[0]*0.4, -size[2]*0.3)
        self.br_leg = self._make_leg(main_color, leg_y, size[0]*0.4, -size[2]*0.3)

    def _make_leg(self, color, height, x, z):
        pivot = self.attachNewNode("leg_pivot"); pivot.setPos(x, -self.size[1]*0.2, z)
        geom = pivot.attachNewNode(make_box_geom(self.size[0]*0.2, height, self.size[0]*0.2, color)); geom.setPos(0, -height*0.5, 0)
        return pivot

    def play_attack(self, style): self._attack_anim_timer = ATTACK_ANIM_DURATION; self._attack_anim_style = style
    def animate(self, dt, moving, speed_mult=1.0):
        self._attack_anim_timer = max(0.0, self._attack_anim_timer - dt); self._idle_t += dt
        if moving: self._walk_t += dt * WALK_FREQ * speed_mult * 2 * math.pi
        else: self._walk_t = 0.0
        swing = math.sin(self._walk_t) * WALK_AMP if moving else 0.0
        self.fl_leg.setP(swing); self.br_leg.setP(swing); self.fr_leg.setP(-swing); self.bl_leg.setP(-swing)
        if self._attack_anim_timer > 0.0:
            prog = 1.0 - (self._attack_anim_timer / ATTACK_ANIM_DURATION); curve = math.sin(prog * math.pi)
            self.setP(-15.0 * curve)
        else: self.setP(math.sin(self._idle_t * 1.5) * 1.5)

    def set_color_scale(self, r, g, b, a): self.setColorScale(r, g, b, a)
    def hide_arrow(self): pass

def build_sword(item_def):
    root = NodePath("sword_model"); root.setP(-90)
    blade_color = item_def.get("color", (0.72, 0.46, 0.2, 1.0)); hilt_color = item_def.get("accent_color", (0.35, 0.25, 0.15, 1.0))
    blade = root.attachNewNode(make_box_geom(0.12, 1.8, 0.04, blade_color)); blade.setY(1.1)
    guard = root.attachNewNode(make_box_geom(0.6, 0.1, 0.1, hilt_color)); guard.setY(0.2)
    handle = root.attachNewNode(make_box_geom(0.08, 0.4, 0.08, hilt_color)); handle.setY(0.0)
    pommel = root.attachNewNode(make_sphere_approx(0.08, hilt_color)); pommel.setY(-0.25)
    return root

def build_shield(item_def):
    root = NodePath("shield_model"); root.setX(-0.4); root.setY(0.1)
    wood_color = item_def.get("color", (0.45, 0.3, 0.16, 1.0)); body = root.attachNewNode(make_box_geom(0.15, 1.5, 1.2, wood_color))
    trim_color = item_def.get("accent_color", (0.72, 0.46, 0.2, 1.0))
    top_trim = root.attachNewNode(make_box_geom(0.18, 0.1, 1.3, trim_color)); top_trim.setY(0.75)
    bottom_trim = root.attachNewNode(make_box_geom(0.18, 0.1, 1.3, trim_color)); bottom_trim.setY(-0.75)
    return root

def build_hood(item_def):
    root = NodePath("hood_model"); color_val = item_def.get("color", (0.52, 0.22, 0.2, 1.0))
    hood = root.attachNewNode(make_sphere_approx(0.55, color_val)); hood.setZ(-0.05)
    return root

def build_armor(item_def):
    color_val = item_def.get("color", (0.64, 0.24, 0.12, 1.0))
    chest = NodePath("armor_chest"); chest.attachNewNode(make_box_geom(CHEST_SIZE[0] + 0.05, CHEST_SIZE[1] + 0.05, CHEST_SIZE[2] + 0.05, color_val))
    waist = NodePath("armor_waist"); waist.attachNewNode(make_box_geom(WAIST_SIZE[0] + 0.05, WAIST_SIZE[1] + 0.05, WAIST_SIZE[2] + 0.05, color_val))
    l_sleeve = NodePath("l_sleeve"); l_sleeve.attachNewNode(make_box_geom(UPPER_ARM_SIZE[0] + 0.04, UPPER_ARM_SIZE[1] + 0.04, UPPER_ARM_SIZE[2] + 0.04, color_val))
    r_sleeve = NodePath("r_sleeve"); r_sleeve.attachNewNode(make_box_geom(UPPER_ARM_SIZE[0] + 0.04, UPPER_ARM_SIZE[1] + 0.04, UPPER_ARM_SIZE[2] + 0.04, color_val))
    return [chest, waist, l_sleeve, r_sleeve]

def build_legs(item_def):
    color_val = item_def.get("color", (0.4, 0.44, 0.52, 1.0))
    l_p = NodePath("l_leg_armor"); l_p.attachNewNode(make_box_geom(UPPER_LEG_SIZE[0] + 0.04, UPPER_LEG_SIZE[1] + LOWER_LEG_SIZE[1] + 0.04, UPPER_LEG_SIZE[2] + 0.04, color_val))
    r_p = NodePath("r_leg_armor"); r_p.attachNewNode(make_box_geom(UPPER_LEG_SIZE[0] + 0.04, UPPER_LEG_SIZE[1] + LOWER_LEG_SIZE[1] + 0.04, UPPER_LEG_SIZE[2] + 0.04, color_val))
    return [l_p, r_p]

def build_bow(item_def):
    root = NodePath("bow_model"); root.setP(-90); color_val = item_def.get("color", (0.5, 0.3, 0.1, 1.0))
    center = root.attachNewNode(make_box_geom(0.08, 0.8, 0.1, color_val)); center.setY(0.4)
    top = root.attachNewNode(make_box_geom(0.06, 0.7, 0.08, color_val)); top.setY(0.9); top.setZ(0.2); top.setP(20)
    bot = root.attachNewNode(make_box_geom(0.06, 0.7, 0.08, color_val)); bot.setY(-0.1); bot.setZ(0.2); bot.setP(-20)
    string = root.attachNewNode(make_box_geom(0.02, 1.8, 0.02, (0.9, 0.9, 0.9, 1.0))); string.setY(0.4); string.setZ(0.4)
    return root

def build_crossbow(item_def):
    root = NodePath("crossbow_model"); root.setP(-90); color_val = item_def.get("color", (0.4, 0.25, 0.15, 1.0))
    stock = root.attachNewNode(make_box_geom(0.12, 1.2, 0.15, color_val)); stock.setY(0.4)
    prod = root.attachNewNode(make_box_geom(1.4, 0.1, 0.1, color_val)); prod.setY(0.8)
    return root

def build_book(item_def):
    root = NodePath("book_model"); root.setP(-90); color_val = item_def.get("color", (0.2, 0.3, 0.6, 1.0))
    book = root.attachNewNode(make_box_geom(0.6, 0.8, 0.2, color_val)); book.setY(0.2); book.setZ(0.2)
    pages = root.attachNewNode(make_box_geom(0.55, 0.75, 0.18, (0.9, 0.9, 0.8, 1.0))); pages.setY(0.2); pages.setZ(0.22)
    return root

def build_staff(item_def):
    root = NodePath("staff_model"); root.setP(-90); color_val = item_def.get("color", (0.6, 0.4, 0.2, 1.0)); acc = item_def.get("accent_color", (0.2, 0.6, 0.9, 1.0))
    shaft = root.attachNewNode(make_box_geom(0.08, 2.5, 0.08, color_val)); shaft.setY(0.5)
    tip = root.attachNewNode(make_sphere_approx(0.15, acc)); tip.setY(1.8)
    return root

def build_mace(item_def):
    root = NodePath("mace_model"); root.setP(-90); color_val = item_def.get("color", (0.5, 0.5, 0.5, 1.0))
    shaft = root.attachNewNode(make_box_geom(0.08, 1.0, 0.08, (0.4, 0.3, 0.2, 1.0))); shaft.setY(0.5)
    head = root.attachNewNode(make_sphere_approx(0.25, color_val)); head.setY(1.0)
    return root

def build_axe(item_def):
    root = NodePath("axe_model"); root.setP(-90); color_val = item_def.get("color", (0.6, 0.6, 0.6, 1.0))
    shaft = root.attachNewNode(make_box_geom(0.08, 1.0, 0.08, (0.4, 0.3, 0.2, 1.0))); shaft.setY(0.4)
    blade = root.attachNewNode(make_box_geom(0.4, 0.3, 0.04, color_val)); blade.setY(0.8); blade.setX(0.2)
    return root

def build_battle_axe(item_def):
    root = NodePath("battle_axe_model"); root.setP(-90); color_val = item_def.get("color", (0.4, 0.4, 0.4, 1.0))
    shaft = root.attachNewNode(make_box_geom(0.1, 1.8, 0.1, (0.3, 0.2, 0.1, 1.0))); shaft.setY(0.8)
    b1 = root.attachNewNode(make_box_geom(0.6, 0.5, 0.05, color_val)); b1.setY(1.5); b1.setX(0.3)
    b2 = root.attachNewNode(make_box_geom(0.6, 0.5, 0.05, color_val)); b2.setY(1.5); b2.setX(-0.3)
    return root

def build_2h_sword(item_def):
    root = NodePath("2h_sword_model"); root.setP(-90); blade_c = item_def.get("color", (0.7, 0.7, 0.7, 1.0)); hilt_c = item_def.get("accent_color", (0.2, 0.2, 0.2, 1.0))
    blade = root.attachNewNode(make_box_geom(0.16, 2.6, 0.06, blade_c)); blade.setY(1.7)
    guard = root.attachNewNode(make_box_geom(0.8, 0.12, 0.12, hilt_c)); guard.setY(0.4)
    handle = root.attachNewNode(make_box_geom(0.08, 0.8, 0.08, hilt_c)); handle.setY(0.0)
    return root

def build_wand(item_def):
    root = NodePath("wand_model"); root.setP(-90); color_val = item_def.get("color", (0.8, 0.7, 0.5, 1.0)); acc = item_def.get("accent_color", (0.9, 0.2, 0.2, 1.0))
    shaft = root.attachNewNode(make_box_geom(0.04, 0.8, 0.04, color_val)); shaft.setY(0.4)
    tip = root.attachNewNode(make_sphere_approx(0.06, acc)); tip.setY(0.8)
    return root

def build_dagger(item_def):
    root = NodePath("dagger_model"); root.setP(-90); blade_c = item_def.get("color", (0.65, 0.65, 0.7, 1.0)); hilt_c = item_def.get("accent_color", (0.3, 0.2, 0.1, 1.0))
    blade = root.attachNewNode(make_box_geom(0.08, 0.8, 0.02, blade_c)); blade.setY(0.5)
    guard = root.attachNewNode(make_box_geom(0.3, 0.06, 0.06, hilt_c)); guard.setY(0.1)
    handle = root.attachNewNode(make_box_geom(0.06, 0.2, 0.06, hilt_c)); handle.setY(0.0)
    return root

def build_gloves(item_def):
    color_val = item_def.get("color", (0.4, 0.4, 0.4, 1.0))
    l_g = NodePath("l_glove"); l_g.attachNewNode(make_box_geom(0.2, 0.4, 0.2, color_val))
    r_g = NodePath("r_glove"); r_g.attachNewNode(make_box_geom(0.2, 0.4, 0.2, color_val))
    return [l_g, r_g]

def build_boots(item_def):
    color_val = item_def.get("color", (0.3, 0.3, 0.3, 1.0))
    l_b = NodePath("l_boot"); l_b.attachNewNode(make_box_geom(0.24, 0.2, 0.36, color_val))
    r_b = NodePath("r_boot"); r_b.attachNewNode(make_box_geom(0.24, 0.2, 0.36, color_val))
    return [l_b, r_b]

EQUIPMENT_BUILDERS = { "sword": build_sword, "shield": build_shield, "hood": build_hood, "armor": build_armor, "legs": build_legs, "hands": build_gloves, "feet": build_boots, "bow": build_bow, "crossbow": build_crossbow, "book": build_book, "staff": build_staff, "mace": build_mace, "axe": build_axe, "battle_axe": build_battle_axe, "2h_sword": build_2h_sword, "wand": build_wand, "dagger": build_dagger }

def build_equipment_model(item_id):
    item_def = get_item_def(item_id)
    if not item_def: return None
    builder = EQUIPMENT_BUILDERS.get(item_def.get("subtype"))
    return builder(item_def) if builder else None
