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
FACE_EYE_RADIUS = 0.045
FACE_EYE_FORWARD = HEAD_RADIUS * 0.88
FACE_EYE_X = 0.14
FACE_EYE_Z = 0.08
FACE_MOUTH_SIZE = (0.18, 0.03, 0.03)
FACE_MOUTH_FORWARD = HEAD_RADIUS * 0.9
FACE_MOUTH_Z = -0.12
FACE_COLOR = (0.08, 0.08, 0.08, 1.0)
CHEST_SIZE = (0.45, 0.34, 0.7)
WAIST_SIZE = (0.34, 0.3, 0.62)
UPPER_ARM_SIZE = (0.18, 0.18, 0.56)
LOWER_ARM_SIZE = (0.16, 0.16, 0.56)
HAND_RADIUS = 0.12
UPPER_LEG_SIZE = (0.2, 0.2, 0.79)
LOWER_LEG_SIZE = (0.18, 0.18, 0.79)
FOOT_SIZE = (0.22, 0.34, 0.14)
CHARACTER_FOOT_Z = 0.37
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
ARM_HANG_ROLL = 8.0
SHOULDER_GAP = 0.05

WALK_FREQ = 1.8
WALK_AMP = 35.0
ATTACK_ANIM_DURATION = 0.3
WORK_ANIM_DURATION = 0.35

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
        self._work_anim_timer = 0.0

        shadow = self.root.attachNewNode(_make_shadow_disc(SHADOW_RADIUS_X, SHADOW_RADIUS_Y, (0, 0, 0, SHADOW_ALPHA)))
        shadow.setPos(0, 0, 0.03)
        shadow.setTransparency(TransparencyAttrib.MAlpha)
        shadow.setLightOff()
        shadow.setDepthWrite(False)
        shadow.setBin("fixed", 12)

        # Torso (Waist and Chest)
        self.waist = self.root.attachNewNode(make_box_geom(*WAIST_SIZE, skin_color))
        self.waist.setPos(0, 0, 2.02 + WAIST_SIZE[2] * 0.5)
        
        self.chest = self.waist.attachNewNode(make_box_geom(*CHEST_SIZE, skin_color))
        self.chest.setPos(0, 0, WAIST_SIZE[2] * 0.5 + CHEST_SIZE[2] * 0.5)

        # Tunic (covers both)
        tunic_height = WAIST_SIZE[2] + CHEST_SIZE[2]
        self.tunic = self.root.attachNewNode(make_box_geom(TUNIC_BASE, TUNIC_BASE, tunic_height, tunic_color))
        self.tunic.setPos(0, 0, TUNIC_BOTTOM_Z + tunic_height * 0.5)

        # Head
        self.head = self.root.attachNewNode(make_sphere_approx(HEAD_RADIUS, skin_color))
        self.head.setPos(0, 0, HEAD_Z)
        self._build_face()
        
        self.head_anchor = self.head.attachNewNode("head_anchor")
        self.head_anchor.setPos(0, 0, 0)
        self.back_anchor = self.chest.attachNewNode("back_anchor")
        self.back_anchor.setPos(0, -0.22, 0.1) # Adjusted relative to chest
        self.back_anchor.setH(90)
        self.back_anchor.setP(-20)

        # UI/Direction Arrow
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

        # Arms (Upper, Lower, Hands)
        self.l_arm = self.chest.attachNewNode("l_arm_pivot")
        self.l_arm.setPos(-CHEST_SIZE[0] * 0.5 - SHOULDER_GAP, 0, CHEST_SIZE[2] * 0.3)
        self.l_arm.setR(ARM_HANG_ROLL)
        self.l_upper_arm = self.l_arm.attachNewNode(make_box_geom(*UPPER_ARM_SIZE, skin_color))
        self.l_upper_arm.setPos(-UPPER_ARM_SIZE[0] * 0.5, 0, -UPPER_ARM_SIZE[2] * 0.5)
        
        self.l_elbow = self.l_upper_arm.attachNewNode("l_elbow_pivot")
        self.l_elbow.setPos(0, 0, -UPPER_ARM_SIZE[2] * 0.5)
        self.l_lower_arm = self.l_elbow.attachNewNode(make_box_geom(*LOWER_ARM_SIZE, skin_color))
        self.l_lower_arm.setPos(0, 0, -LOWER_ARM_SIZE[2] * 0.5)
        
        self.l_hand = self.l_lower_arm.attachNewNode(make_sphere_approx(HAND_RADIUS, skin_color))
        self.l_hand.setPos(0, 0, -LOWER_ARM_SIZE[2] * 0.5)
        self.l_hand_anchor = self.l_hand.attachNewNode("l_hand_anchor")

        self.r_arm = self.chest.attachNewNode("r_arm_pivot")
        self.r_arm.setPos(CHEST_SIZE[0] * 0.5 + SHOULDER_GAP, 0, CHEST_SIZE[2] * 0.3)
        self.r_arm.setR(-ARM_HANG_ROLL)
        self.r_upper_arm = self.r_arm.attachNewNode(make_box_geom(*UPPER_ARM_SIZE, skin_color))
        self.r_upper_arm.setPos(UPPER_ARM_SIZE[0] * 0.5, 0, -UPPER_ARM_SIZE[2] * 0.5)
        
        self.r_elbow = self.r_upper_arm.attachNewNode("r_elbow_pivot")
        self.r_elbow.setPos(0, 0, -UPPER_ARM_SIZE[2] * 0.5)
        self.r_lower_arm = self.r_elbow.attachNewNode(make_box_geom(*LOWER_ARM_SIZE, skin_color))
        self.r_lower_arm.setPos(0, 0, -LOWER_ARM_SIZE[2] * 0.5)
        
        self.r_hand = self.r_lower_arm.attachNewNode(make_sphere_approx(HAND_RADIUS, skin_color))
        self.r_hand.setPos(0, 0, -LOWER_ARM_SIZE[2] * 0.5)
        self.r_hand_anchor = self.r_hand.attachNewNode("r_hand_anchor")

        # Legs (Upper, Lower, Feet)
        leg_spawn_z = 2.02
        self.l_leg = self.root.attachNewNode("l_leg_pivot")
        self.l_leg.setPos(-0.14, 0, leg_spawn_z)
        self.l_upper_leg = self.l_leg.attachNewNode(make_box_geom(*UPPER_LEG_SIZE, skin_color))
        self.l_upper_leg.setPos(0, 0, -UPPER_LEG_SIZE[2] * 0.5)
        
        self.l_knee = self.l_upper_leg.attachNewNode("l_knee_pivot")
        self.l_knee.setPos(0, 0, -UPPER_LEG_SIZE[2] * 0.5)
        self.l_lower_leg = self.l_knee.attachNewNode(make_box_geom(*LOWER_LEG_SIZE, skin_color))
        self.l_lower_leg.setPos(0, 0, -LOWER_LEG_SIZE[2] * 0.5)
        
        self.l_foot = self.l_lower_leg.attachNewNode(make_box_geom(*FOOT_SIZE, skin_color))
        self.l_foot.setPos(0, FOOT_SIZE[1] * 0.3, -LOWER_LEG_SIZE[2] * 0.5)

        self.r_leg = self.root.attachNewNode("r_leg_pivot")
        self.r_leg.setPos(0.14, 0, leg_spawn_z)
        self.r_upper_leg = self.r_leg.attachNewNode(make_box_geom(*UPPER_LEG_SIZE, skin_color))
        self.r_upper_leg.setPos(0, 0, -UPPER_LEG_SIZE[2] * 0.5)
        
        self.r_knee = self.r_upper_leg.attachNewNode("r_knee_pivot")
        self.r_knee.setPos(0, 0, -UPPER_LEG_SIZE[2] * 0.5)
        self.r_lower_leg = self.r_knee.attachNewNode(make_box_geom(*LOWER_LEG_SIZE, skin_color))
        self.r_lower_leg.setPos(0, 0, -LOWER_LEG_SIZE[2] * 0.5)
        
        self.r_foot = self.r_lower_leg.attachNewNode(make_box_geom(*FOOT_SIZE, skin_color))
        self.r_foot.setPos(0, FOOT_SIZE[1] * 0.3, -LOWER_LEG_SIZE[2] * 0.5)

    def _build_face(self):
        left_eye = self.head.attachNewNode(make_sphere_approx(FACE_EYE_RADIUS, FACE_COLOR))
        left_eye.setPos(-FACE_EYE_X, FACE_EYE_FORWARD, FACE_EYE_Z)

        right_eye = self.head.attachNewNode(make_sphere_approx(FACE_EYE_RADIUS, FACE_COLOR))
        right_eye.setPos(FACE_EYE_X, FACE_EYE_FORWARD, FACE_EYE_Z)

        mouth = self.head.attachNewNode(make_box_geom(*FACE_MOUTH_SIZE, FACE_COLOR))
        mouth.setPos(0, FACE_MOUTH_FORWARD, FACE_MOUTH_Z)

    def play_attack(self, style):
        self._attack_anim_timer = ATTACK_ANIM_DURATION
        self._attack_anim_style = style

    def play_work(self):
        if self._work_anim_timer <= 0.0:
            self._work_anim_timer = WORK_ANIM_DURATION

    def animate(self, dt, moving, speed_mult=1.0):
        self._attack_anim_timer = max(0.0, self._attack_anim_timer - dt)
        self._work_anim_timer = max(0.0, self._work_anim_timer - dt)
        self._idle_t += dt

        if moving:
            self._walk_t += dt * WALK_FREQ * speed_mult * 2 * math.pi
        else:
            self._walk_t = 0.0

        swing = math.sin(self._walk_t) * WALK_AMP if moving else 0.0
        # Knee bend: bend BACK (negative pitch) when leg is swinging through or back
        knee_bend = abs(math.sin(self._walk_t)) * 40.0 if moving else 0.0
        # Elbow bend: bend FORWARD (positive pitch)
        elbow_swing = (math.sin(self._walk_t + math.pi*0.5) + 1.0) * 20.0 if moving else 10.0

        # Idle breathing/sway
        idle_sway = math.sin(self._idle_t * 1.6)
        idle_arm = idle_sway * 7.5
        idle_chest = idle_sway * 2.0

        l_arm_pitch = -swing * 0.6 + idle_arm
        r_arm_pitch = swing * 0.6 + idle_arm
        
        l_elbow_pitch = elbow_swing
        r_elbow_pitch = elbow_swing
        
        l_leg_pitch = swing
        r_leg_pitch = -swing
        
        # Natural stride: bend knee when leg is back (pitch < 0)
        l_knee_pitch = -knee_bend if l_leg_pitch < 0 else -knee_bend * 0.15
        r_knee_pitch = -knee_bend if r_leg_pitch < 0 else -knee_bend * 0.15
        
        # Attack animations blend over these pitches
        chest_pitch = idle_chest
        if self._attack_anim_timer > 0.0:
            progress = 1.0 - (self._attack_anim_timer / ATTACK_ANIM_DURATION)
            strike_curve = math.sin(progress * math.pi)
            if self._attack_anim_style == "melee":
                r_arm_pitch += 80.0 * strike_curve
                r_elbow_pitch += 50.0 * strike_curve
            elif self._attack_anim_style == "ranged":
                l_arm_pitch += 70.0 * strike_curve
                r_arm_pitch += 70.0 * strike_curve
                l_elbow_pitch += 40.0 * strike_curve
                r_elbow_pitch += 40.0 * strike_curve
        elif self._work_anim_timer > 0.0:
            progress = 1.0 - (self._work_anim_timer / WORK_ANIM_DURATION)
            work_curve = math.sin(progress * math.pi)
            chest_pitch = idle_chest - (6.0 * work_curve)
            l_arm_pitch = 40.0 + (22.0 * work_curve)
            r_arm_pitch = 58.0 + (42.0 * work_curve)
            l_elbow_pitch = 42.0 + (24.0 * work_curve)
            r_elbow_pitch = 68.0 + (38.0 * work_curve)
            l_leg_pitch = -8.0 * work_curve
            r_leg_pitch = 6.0 * work_curve
            l_knee_pitch = -10.0 * work_curve
            r_knee_pitch = -6.0 * work_curve

        self.chest.setP(chest_pitch)
        self.l_leg.setP(l_leg_pitch)
        self.r_leg.setP(r_leg_pitch)
        self.l_knee.setP(l_knee_pitch)
        self.r_knee.setP(r_knee_pitch)
        self.l_arm.setP(l_arm_pitch)
        self.r_arm.setP(r_arm_pitch)
        self.l_elbow.setP(l_elbow_pitch)
        self.r_elbow.setP(r_elbow_pitch)

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
        elif slot == "ranged":
            m.reparentTo(self.back_anchor)
        elif slot == "head":
            m.reparentTo(self.head_anchor)
        elif slot == "chest":
            if index == 0:
                m.reparentTo(self.chest)
            elif index == 1:
                m.reparentTo(self.waist)
            elif index == 2:
                m.reparentTo(self.l_upper_arm)
            elif index == 3:
                m.reparentTo(self.r_upper_arm)
        elif slot == "legs":
            if index == 0:
                m.reparentTo(self.l_upper_leg)
            else:
                m.reparentTo(self.r_upper_leg)
        elif slot == "hands":
            if index == 0:
                m.reparentTo(self.l_lower_arm)
            else:
                m.reparentTo(self.r_lower_arm)
        elif slot == "feet":
            if index == 0:
                m.reparentTo(self.l_foot)
            else:
                m.reparentTo(self.r_foot)


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
    """Procedural armor/tunic overlay with sleeves. Returns [chest, waist, l_sleeve, r_sleeve]."""
    color = item_def.get("color", (0.64, 0.24, 0.12, 1.0))
    
    chest = NodePath("armor_chest")
    chest.attachNewNode(make_box_geom(CHEST_SIZE[0] + 0.05, CHEST_SIZE[1] + 0.05, CHEST_SIZE[2] + 0.05, color))
    
    waist = NodePath("armor_waist")
    waist.attachNewNode(make_box_geom(WAIST_SIZE[0] + 0.05, WAIST_SIZE[1] + 0.05, WAIST_SIZE[2] + 0.05, color))
    
    l_sleeve = NodePath("l_sleeve")
    l_sleeve.attachNewNode(make_box_geom(UPPER_ARM_SIZE[0] + 0.04, UPPER_ARM_SIZE[1] + 0.04, UPPER_ARM_SIZE[2] + 0.04, color))
    
    r_sleeve = NodePath("r_sleeve")
    r_sleeve.attachNewNode(make_box_geom(UPPER_ARM_SIZE[0] + 0.04, UPPER_ARM_SIZE[1] + 0.04, UPPER_ARM_SIZE[2] + 0.04, color))
    
    return [chest, waist, l_sleeve, r_sleeve]
CHARACTER_FOOT_Z = 0.37
...
def build_legs(item_def):
    """Procedural pants/legs overlay (two nodes)."""
    color = item_def.get("color", (0.4, 0.44, 0.52, 1.0))

    l_pant = NodePath("l_leg_armor")
    l_pant.attachNewNode(make_box_geom(UPPER_LEG_SIZE[0] + 0.04, UPPER_LEG_SIZE[1] + 0.04, UPPER_LEG_SIZE[2] + LOWER_LEG_SIZE[2] + 0.04, color))

    r_pant = NodePath("r_leg_armor")
    r_pant.attachNewNode(make_box_geom(UPPER_LEG_SIZE[0] + 0.04, UPPER_LEG_SIZE[1] + 0.04, UPPER_LEG_SIZE[2] + LOWER_LEG_SIZE[2] + 0.04, color))

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

def build_gloves(item_def):
    """Procedural gloves/gauntlets (two nodes)."""
    color = item_def.get("color", (0.4, 0.4, 0.4, 1.0))
    
    l_glove = NodePath("l_glove")
    l_glove.attachNewNode(make_box_geom(0.2, 0.2, 0.4, color))
    
    r_glove = NodePath("r_glove")
    r_glove.attachNewNode(make_box_geom(0.2, 0.2, 0.4, color))
    
    return [l_glove, r_glove]

def build_boots(item_def):
    """Procedural boots/sabatons (two nodes)."""
    color = item_def.get("color", (0.3, 0.3, 0.3, 1.0))
    
    l_boot = NodePath("l_boot")
    l_boot.attachNewNode(make_box_geom(0.24, 0.36, 0.2, color))
    
    r_boot = NodePath("r_boot")
    r_boot.attachNewNode(make_box_geom(0.24, 0.36, 0.2, color))
    
    return [l_boot, r_boot]

EQUIPMENT_BUILDERS = {
    "sword": build_sword,
    "shield": build_shield,
    "hood": build_hood,
    "armor": build_armor,
    "legs": build_legs,
    "hands": build_gloves,
    "feet": build_boots,
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
