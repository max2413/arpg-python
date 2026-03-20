"""Bullet-backed player entity using Ursina-facing runtime services."""

import math
from ursina import Entity, Vec3, scene
from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    TransparencyAttrib,
    BitMask32,
)
from panda3d.bullet import BulletCharacterControllerNode, BulletCapsuleShape, YUp
from game.entities.models import (
    CHARACTER_FOOT_Y,
    HumanoidModel,
    build_equipment_model,
)
from game.runtime import get_runtime
from game.systems.combat import TargetedProjectile, in_attack_range, make_combat_profile, resolve_attack
from game.systems.inventory import get_item_def
from game.systems.stats import StatManager


MOVE_SPEED   = 12.0
SPRINT_MULT  = 5.0
JUMP_SPEED   = 9.0
JUMP_HEIGHT  = 3.0
TURN_SPEED   = 180.0
SPRINT_TURN_MULT = 1.6
BACKPEDAL_MULT = 0.75
PLAYER_CAPSULE_RADIUS = 0.5
PLAYER_CAPSULE_HEIGHT = 3.0
HEALTH_REGEN_DELAY = 6.0
HEALTH_REGEN_RATE  = 4.0
DEBUG_COMBAT_LOGS = False
UNARMED_MELEE_PROFILE = make_combat_profile("Fists", 3.1, 2.0, 18, projectile=False)
UNARMED_RANGED_PROFILE = make_combat_profile(
    "Thrown",
    54.0,
    2.4,
    14,
    projectile=True,
    projectile_speed=30.0,
    projectile_radius=0.2,
    projectile_color=(0.95, 0.78, 0.22, 1),
)

# Vertical offset to align visual feet with capsule bottom
PLAYER_VISUAL_OFFSET_Y = -(PLAYER_CAPSULE_HEIGHT * 0.5 + PLAYER_CAPSULE_RADIUS + CHARACTER_FOOT_Y)
GROUND_MARKER_OUTER = (0.02, 0.02, 0.02, 0.42)
GROUND_MARKER_INNER = (0.92, 0.36, 0.12, 0.18)


def _make_ground_marker(outer_rx=0.72, outer_ry=0.46, inner_rx=0.48, inner_ry=0.28, segments=24):
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("player_ground_marker", fmt, Geom.UHStatic)
    vdata.setNumRows(segments * 4)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    color_w = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)

    for i in range(segments):
        a0 = math.radians((i / segments) * 360.0)
        a1 = math.radians(((i + 1) / segments) * 360.0)
        ring = [
            (math.cos(a0) * outer_rx, 0.0, math.sin(a0) * outer_ry, GROUND_MARKER_OUTER),
            (math.cos(a1) * outer_rx, 0.0, math.sin(a1) * outer_ry, GROUND_MARKER_OUTER),
            (math.cos(a1) * inner_rx, 0.0, math.sin(a1) * inner_ry, GROUND_MARKER_INNER),
            (math.cos(a0) * inner_rx, 0.0, math.sin(a0) * inner_ry, GROUND_MARKER_INNER),
        ]
        base = i * 4
        for x, y, z, col in ring:
            vertex.addData3(x, y, z)
            normal.addData3(0, 1, 0)
            color_w.addData4(*col)
        tris.addVertices(base, base + 1, base + 2)
        tris.addVertices(base, base + 2, base + 3)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("player_ground_marker")
    node.addGeom(geom)
    return node


class Player(Entity):
    def __init__(self, render, bullet_world, inventory, terrain=None):
        super().__init__()
        self.render = render
        self.bullet_world = bullet_world
        self.inventory = inventory
        self.terrain = terrain

        # Key state
        self._keys = {"w": False, "s": False, "a": False, "d": False}
        self._sprinting = False
        self._space_down = False
        self._space_was_down = False
        self._jump_pending = False

        # Visuals (Initialize AFTER Entity core is ready)
        self.model = HumanoidModel(
            parent=self,
            skin_color=(0.9, 0.85, 0.75, 1.0),
            tunic_color=(0.68, 0.24, 0.12, 1.0),
        )
        self.figure = self.model
        
        # Avoid passing model to constructor to bypass Ursina's buggy model_setter in init
        self._ground_marker = Entity(parent=self)
        self._ground_marker.model = _make_ground_marker()
        self._ground_marker.y = 0.04
        self._ground_marker.setTransparency(TransparencyAttrib.MAlpha)
        self._ground_marker.setLightOff()
        self._ground_marker.setDepthWrite(False)
        self._ground_marker.setBin("fixed", 13)

        # Physics (URSINA Y-UP)
        shape = BulletCapsuleShape(PLAYER_CAPSULE_RADIUS, PLAYER_CAPSULE_HEIGHT, YUp)
        self.char_node = BulletCharacterControllerNode(shape, 0.4, "player")
        self.char_np = scene.attachNewNode(self.char_node)
        self.char_np.setPos(0, PLAYER_CAPSULE_HEIGHT * 0.5 + PLAYER_CAPSULE_RADIUS + 1.0, 0)
        self.char_np.setCollideMask(BitMask32.allOn())
        bullet_world.attachCharacter(self.char_node)
        
        self.stats = StatManager(self, inventory=self.inventory)
        self.max_health = self.stats.get("max_health")
        self.health = float(self.max_health)
        self.dead = False
        self._last_damage_taken = 0.0
        self._time_since_damage = HEALTH_REGEN_DELAY
        self.melee_ability_range = UNARMED_MELEE_PROFILE["range"]
        self.ranged_ability_range = UNARMED_RANGED_PROFILE["range"]
        self.projectiles = []
        self._auto_attack_style = None
        self._auto_attack_timer = 0.0
        self.inventory.equipment.add_listener(self._on_equipment_changed)
        self.refresh_equipment_models()

    def _on_equipment_changed(self):
        self.refresh_equipment_models()

    def refresh_equipment_models(self):
        for slot_name in ["weapon", "offhand", "ranged", "head", "chest", "legs", "hands", "feet"]:
            stack = self.inventory.equipment.get_slot(slot_name)
            if stack:
                model_np = build_equipment_model(stack["id"])
                self.model.set_equipment(slot_name, model_np)
            else:
                self.model.set_equipment(slot_name, None)
        self.stats.recalculate()
        self.max_health = self.stats.get("max_health")

    def take_damage(self, amount, hud=None, attacker=None):
        if self.dead or amount <= 0: self._last_damage_taken = 0.0; return False
        eff = min(amount, self.health)
        self._last_damage_taken = eff
        if hasattr(self, "stats") and self.stats.skills: self.stats.skills.add_xp("Defense", eff * 0.5)
        self.health = max(0, self.health - eff)
        self._time_since_damage = 0.0
        if self.health == 0: self.dead = True; self._jump_pending = False; return True
        return False

    def heal_full(self): self.health = float(self.max_health); self._time_since_damage = HEALTH_REGEN_DELAY

    def respawn(self, pos=(0, 0, 0)):
        self.dead = False; self.heal_full(); self._jump_pending = False; self.clear_auto_attack(); self._clear_projectiles()
        self.char_np.setPos(*pos)
        self.char_node.setLinearMovement(Vec3(0, 0, 0), False)
        self.rotation_y = 0; self.model.set_color_scale(1, 1, 1, 1)
        self.position = Vec3(pos[0], pos[1] + PLAYER_VISUAL_OFFSET_Y, pos[2])

    def update(self):
        runtime = get_runtime()
        if runtime is not None and getattr(runtime.game, "_paused", False):
            return

        from ursina import time
        dt = time.dt
        
        if self.dead:
            self.char_node.setLinearMovement(Vec3(0, 0, 0), False)
            p = self.char_np.getPos()
            self.position = Vec3(p.x, p.y + PLAYER_VISUAL_OFFSET_Y, p.z)
            self.model.set_color_scale(0.45, 0.2, 0.2, 1)
            self.model.animate(dt, False)
            return

        self._time_since_damage += dt
        if self._time_since_damage >= HEALTH_REGEN_DELAY and self.health < self.max_health:
            self.health = min(self.max_health, self.health + HEALTH_REGEN_RATE * dt)

        self._poll_input()
        if self._space_down and not self._space_was_down: self._jump_pending = True
        self._space_was_down = self._space_down

        # Turning (Reverted to A/D turning)
        turn_spd = TURN_SPEED * (SPRINT_TURN_MULT if self._sprinting else 1.0)
        if self._keys["a"]: self.rotation_y -= turn_spd * dt
        if self._keys["d"]: self.rotation_y += turn_spd * dt

        # Sync physics orientation
        self.char_np.setH(-self.rotation_y)

        # Movement (Reverted to Forward/Back logic)
        h_rad = math.radians(self.rotation_y)
        forward = Vec3(math.sin(h_rad), 0, math.cos(h_rad))
        
        move_dir = Vec3(0, 0, 0)
        if self._keys["w"]: move_dir += forward
        if self._keys["s"]: move_dir -= forward
        
        is_moving = move_dir.length_squared() > 0
        if is_moving:
            move_dir.normalize()
            speed = MOVE_SPEED
            if self._keys["s"] and not self._keys["w"]: speed *= BACKPEDAL_MULT
            if self._sprinting and self._keys["w"]: speed *= SPRINT_MULT
            velocity = move_dir * speed
        else:
            velocity = Vec3(0, 0, 0)

        # Apply world-space movement
        self.char_node.setLinearMovement(velocity, False)

        if self._jump_pending and self.char_node.isOnGround():
            self.char_node.setMaxJumpHeight(JUMP_HEIGHT); self.char_node.setJumpSpeed(JUMP_SPEED); self.char_node.doJump(); self._jump_pending = False

        self.model.animate(dt, is_moving, speed_mult=(SPRINT_MULT if self._sprinting else 1.0))
        p = self.char_np.getPos(); self.position = Vec3(p.x, p.y + PLAYER_VISUAL_OFFSET_Y, p.z)

    def get_pos(self): return self.position - Vec3(0, PLAYER_VISUAL_OFFSET_Y, 0)
    def get_health_display(self): return int(math.ceil(self.health))
    def is_targetable(self): return not self.dead
    def get_target_point(self): return self.get_pos() + Vec3(0, 2.2, 0)
    def get_target_name(self): return "Player"
    def get_combat_level(self):
        if hasattr(self, "stats") and self.stats.skills: return self.stats.skills.get_combat_level()
        return 1
    def is_moving(self): return self._keys["w"] or self._keys["s"]
    def is_action_interrupting(self): return self.is_moving() or self._jump_pending or not self.char_node.isOnGround()
    def is_advancing(self): return self._keys["w"]
    def is_turning(self): return self._keys["a"] or self._keys["d"]
    def get_heading(self): return self.rotation_y

    def get_combat_profile(self, style):
        if style == "melee":
            p = dict(UNARMED_MELEE_PROFILE); p["damage"] = self.stats.get("melee_damage"); p["xp_style"] = "melee"
            return p
        elif style == "ranged":
            r_item = self.inventory.equipment.get_slot("ranged")
            if r_item is None: return None
            p = dict(UNARMED_RANGED_PROFILE); idef = get_item_def(r_item["id"]); sub = idef.get("subtype") if idef else None
            if sub in ("wand", "staff"):
                p["damage"] = self.stats.get("magic_damage"); p["name"] = idef["name"] if idef else "Magic"; p["projectile_color"] = tuple(idef.get("accent_color", (0.35, 0.75, 1.0, 1.0))) if idef else (0.35, 0.75, 1.0, 1.0); p["xp_style"] = "magic"
            else:
                p["damage"] = self.stats.get("ranged_damage"); p["name"] = idef["name"] if idef else p["name"]; p["xp_style"] = "ranged"
            return p
        return None

    def grant_combat_xp(self, style, amount):
        if amount <= 0 or not hasattr(self, "stats") or not self.stats.skills: return
        sn = {"melee": "Melee", "ranged": "Ranged", "magic": "Magic"}.get(style)
        if sn is None: return
        lvls = self.stats.skills.add_xp(sn, amount)
        runtime = get_runtime()
        if runtime is None or runtime.hud is None:
            return
        if lvls > 0:
            runtime.hud.refresh_skills()
            runtime.hud.show_prompt(f"{sn} level up! Level {self.stats.skills.get_level(sn)}")
            runtime.hud.add_log(f"{sn} level up! Level {self.stats.skills.get_level(sn)}")
        else:
            runtime.hud.refresh_skills()

    def play_work_animation(self):
        if hasattr(self, "model") and self.model: self.model.play_work()

    def start_auto_attack(self, style):
        if style not in ("melee", "ranged"): return
        if self._auto_attack_style != style: self._auto_attack_style = style; self._auto_attack_timer = 0.0

    def clear_auto_attack(self): self._auto_attack_style = None; self._auto_attack_timer = 0.0

    def combat_tick(self, tick_dt, target, hud):
        if self.dead or self._auto_attack_style is None or target is None or not target.is_targetable(): self.clear_auto_attack(); return
        prof = self.get_combat_profile(self._auto_attack_style)
        if prof is None: self.clear_auto_attack(); return
        self._auto_attack_timer = max(0.0, self._auto_attack_timer - tick_dt)
        if self._auto_attack_timer > 0.0: return
        tp = target.get_target_point()
        if not in_attack_range(self.get_pos(), tp, prof): return
        self.face_target(tp); self.model.play_attack(self._auto_attack_style)
        if prof["projectile"]: self.fire_target_projectile(target, prof)
        else:
            xs = prof.get("xp_style", self._auto_attack_style); out = resolve_attack(self, target, xs, prof["damage"]); _report_combat_event(self, target, out, xs)
            if out["type"] not in ("miss", "parry"):
                target.take_damage(out["damage"], hud, attacker=self, attack_style=xs); self.grant_combat_xp(xs, getattr(target, "_last_damage_taken", out["damage"]))
        self._auto_attack_timer = prof["speed"]

    def _poll_input(self):
        runtime = get_runtime()
        if runtime is None:
            return
        input_state = runtime.input_state
        self._keys["w"] = input_state.is_held("w")
        self._keys["s"] = input_state.is_held("s")
        self._keys["a"] = input_state.is_held("a")
        self._keys["d"] = input_state.is_held("d")
        self._space_down = input_state.is_held("space")
        self._sprinting = input_state.is_held("shift")

    def face_target(self, tp):
        delta = tp - self.get_pos(); delta.y = 0
        if delta.length_squared() > 0: self.rotation_y = math.degrees(math.atan2(delta.x, delta.z))

    def distance_to(self, tp):
        delta = tp - self.get_pos(); delta.y = 0
        return delta.length()

    def fire_target_projectile(self, target, profile):
        self._clear_expired_target_projectiles(); origin = self.get_pos() + Vec3(0, 2.2, 0)
        self.projectiles.append(TargetedProjectile(self.render, origin, target, profile["damage"], profile, self._on_projectile_hit))

    def update_projectiles(self, dt, hud):
        active = []
        for p in self.projectiles:
            if p.update(dt, hud): continue
            active.append(p)
        self.projectiles = active

    def _clear_projectiles(self):
        for p in self.projectiles: p.remove()
        self.projectiles = []

    def _clear_expired_target_projectiles(self):
        active = []
        for p in self.projectiles:
            if p.expired: p.remove()
            else: active.append(p)
        self.projectiles = active

    def _on_projectile_hit(self, target, base_damage, hud):
        prof = self.get_combat_profile("ranged"); xs = prof.get("xp_style", "ranged") if prof else "ranged"
        out = resolve_attack(self, target, xs, base_damage); _report_combat_event(self, target, out, xs)
        if out["type"] not in ("miss", "parry"):
            target.take_damage(out["damage"], hud, attacker=self, attack_style=xs); self.grant_combat_xp(xs, getattr(target, "_last_damage_taken", out["damage"]))

def _report_combat_event(attacker, defender, outcome, style):
    runtime = get_runtime()
    if runtime is not None and runtime.hud is not None:
        runtime.hud.record_combat_event({
            "attacker": attacker.get_target_name(), "defender": defender.get_target_name(), "style": style, "result": outcome.get("type", "hit"), "damage": outcome.get("damage", 0.0), "base_damage": outcome.get("base_damage", 0.0), "mitigated": outcome.get("mitigated", 0.0),
        })
