"""
creatures.py - Data-driven world entities (monsters, animals, etc).
URSINA Y-UP VERSION
"""

import math
import random
import json
import os

from ursina import Entity, Vec3, color
from panda3d.core import NodePath, TextNode, BillboardEffect, LineSegs, TransparencyAttrib
from panda3d.bullet import BulletGhostNode, BulletSphereShape

from game.entities.models import HumanoidModel, CreatureModel
from game.runtime import get_runtime
from game.systems.combat import (
    TargetedProjectile,
    in_attack_range,
    make_combat_profile,
    stop_distance_for,
    resolve_attack,
)
from game.systems.balance import creature_runtime_stats
from game.systems.stats import StatManager

# AI Balance Constants
PATROL_SPEED = 4.0
CHASE_SPEED = 8.5
FLIGHT_SPEED = 10.0
STOP_DISTANCE = 2.2
TURN_SPEED = 540.0
AGGRO_DISTANCE = 18.0
LEASH_DISTANCE = 28.0
PATROL_RADIUS = 18.0
PATROL_POINT_TOLERANCE = 1.5
PATROL_WAIT_MIN = 0.8
PATROL_WAIT_MAX = 1.8
ATTACK_RANGE = 2.8
ATTACK_DAMAGE = 15
ATTACK_COOLDOWN = 1.0
AGGRO_RESET_TIME = 6.0
RESET_REGEN_RATE = 10.0
PLAYER_ATTACK_DAMAGE = 20
PLAYER_ATTACK_COOLDOWN = 0.25
HOSTILE_RESPAWN_TIME = 6.0
HURT_FLASH_TIME = 0.12
LOOT_INDICATOR_TEXT = "Loot"
LOOT_RESPAWN_MULT = 2.0
HOSTILE_HIT_RADIUS = 1.65
HOSTILE_HIT_HEIGHT = 3.8
TARGETED_LABEL_COLOR = (1.0, 0.82, 0.22, 1)
DEBUG_COMBAT_LOGS = False
PLAYER_XP_STYLES = ("melee", "ranged", "magic")

CREATURE_DEFS = {}
CREATURES_PATH = os.path.join("data", "creatures.json")

def load_creature_defs():
    global CREATURE_DEFS
    if not os.path.exists(CREATURES_PATH): return
    try:
        with open(CREATURES_PATH, "r") as f: CREATURE_DEFS = json.load(f)
    except: pass

class Creature(Entity):
    def __init__(self, render, pos, creature_id, level=None, level_range=None, role=None, patrol_center=None, terrain=None, bullet_world=None):
        super().__init__()
        self.render = render
        self.terrain = terrain
        self.bullet_world = bullet_world
        # URSINA Y-UP: pos is (x, y, z)
        self.position = Vec3(*pos)
        self.patrol_center = Vec3(*(patrol_center or pos))
        
        self.creature_id = creature_id
        self.data = CREATURE_DEFS.get(creature_id, {})
        self._rng = random.Random(f"{self.patrol_center.x:.2f},{self.patrol_center.z:.2f}")
        self._role_override = role
        self._level_range = level_range
        self._current_level = self._roll_level(level, level_range)
        
        self._state = "patrol"
        self._wait_timer = 0.0
        self._patrol_target = self._pick_patrol_target()
        self._attack_cooldown = 0.0
        self._player_attack_cooldown = 0.0
        self._time_since_damage_taken = AGGRO_RESET_TIME
        
        self.stats = StatManager(self)
        self._apply_data_stats()
        self.health = self.max_health
        self.dead = False
        self._despawned = False
        self._respawn_timer = 0.0
        self._prompt_shown = False
        self._prompt_msg = ""
        self._hurt_flash_timer = 0.0
        self._dead_time = 0.0
        self._loot = []
        self.projectiles = []
        self._combat_target = None
        self._targeted = False
        self._player_damage_by_style = {style: 0.0 for style in PLAYER_XP_STYLES}
        self._last_damage_taken = 0.0

        self._build_visual()
        self._build_target_arrow()
        self._build_debug_ghost()

    def _roll_level(self, level, level_range):
        if level is not None: return level
        if level_range: return self._rng.randint(level_range[0], level_range[1])
        return 1

    def _apply_data_stats(self):
        stats_def = dict(self.data)
        stats_def["level"] = self._current_level
        if self._role_override: stats_def["role"] = self._role_override
        for k, v in creature_runtime_stats(stats_def).items():
            self.stats.set_base_stat(k, v)

    @property
    def max_health(self): return self.stats.get("max_health")
    @property
    def is_hostile(self): return self.data.get("ai_type", "hostile") == "hostile"
    @property
    def role(self): return self._role_override or self.data.get("role", "normal")
    def get_level(self): return self._current_level

    def _build_visual(self):
        v = self.data.get("visuals", {})
        m_type = self.data.get("model_type", "humanoid")
        if m_type == "humanoid":
            self.model = HumanoidModel(self, skin_color=tuple(v.get("skin_color", [0.9, 0.8, 0.7, 1.0])), tunic_color=tuple(v.get("tunic_color", [0.5, 0.5, 0.5, 1.0])))
            self.model.hide_arrow()
        else:
            self.model = CreatureModel(self, main_color=tuple(v.get("color", [0.4, 0.4, 0.4, 1.0])), size=tuple(v.get("size", [0.8, 1.6, 0.8])))

        self._label_color = tuple(v.get("label_color", [1, 1, 1, 1]))
        name = self.data.get("name", self.creature_id.capitalize())
        role = self.role
        if role == "elite":
            label_text = f"* {name} *"
            self._label_color = (1.0, 0.9, 0.4, 1.0)
        elif role == "boss":
            label_text = f"!!! {name} !!!"
            self._label_color = (1.0, 0.2, 0.2, 1.0)
        else: label_text = name

        label_scale = v.get("label_scale", 1.0)
        y_off = 4.3 if m_type == "humanoid" else 2.8
        self._label_np = self._make_label("creature_label", label_text, self._label_color, scale=label_scale)
        self._label_np.setY(y_off)

        loot_node = TextNode("loot_label")
        loot_node.setText(LOOT_INDICATOR_TEXT)
        loot_node.setAlign(TextNode.ACenter)
        loot_node.setTextColor(1, 0.9, 0.2, 1)
        self._loot_label_np = self.attachNewNode(loot_node)
        self._loot_label_np.setY(1.1)
        self._loot_label_np.setScale(0.9)
        self._loot_label_np.setEffect(BillboardEffect.makePointEye())
        self._loot_label_np.hide()

    def _make_label(self, node_name, text, col, scale):
        label_node = TextNode(node_name)
        label_node.setText(text)
        label_node.setAlign(TextNode.ACenter)
        label_node.setTextColor(*col)
        label_np = self.attachNewNode(label_node)
        label_np.setScale(scale)
        label_np.setEffect(BillboardEffect.makePointEye())
        return label_np

    def _build_target_arrow(self):
        arrow = LineSegs("target_arrow")
        arrow.setThickness(4.0)
        arrow.setColor(1.0, 0.82, 0.22, 1)
        # URSINA Y-UP: Arrow points down on Y
        arrow.moveTo(0, 0, 0)
        arrow.drawTo(0, -0.9, 0)
        arrow.moveTo(0, -0.9, 0)
        arrow.drawTo(-0.22, -0.62, 0)
        arrow.moveTo(0, -0.9, 0)
        arrow.drawTo(0.22, -0.62, 0)
        self._target_arrow_np = self.attachNewNode(arrow.create())
        self._target_arrow_np.setY(5.25)
        self._target_arrow_np.setEffect(BillboardEffect.makePointEye())
        self._target_arrow_np.hide()

    def _build_debug_ghost(self):
        self._ghost_np = None
        self._ghost = None
        if self.bullet_world is None: return
        ghost = BulletGhostNode("creature_debug_ghost")
        ghost.addShape(BulletSphereShape(1.0))
        self._ghost = ghost
        self._ghost_np = self.render.attachNewNode(ghost)
        self._ghost_np.setPos(self.x, self.y + 1.2, self.z)
        self.bullet_world.attachGhost(ghost)

    def update(self):
        runtime = get_runtime()
        if runtime is None or runtime.player is None or runtime.hud is None:
            return
        from ursina import time
        dt = time.dt

        player = runtime.player
        hud = runtime.hud

        p_pos = player.get_pos()
        self._player_attack_cooldown = max(0.0, self._player_attack_cooldown - dt)
        self._hurt_flash_timer = max(0.0, self._hurt_flash_timer - dt)
        self._time_since_damage_taken += dt
        self._update_projectiles(dt, player)
        
        # URSINA Y-UP: Distance on XZ plane
        p_target = Vec3(p_pos.x, self.y, p_pos.z)
        to_player = p_target - self.position
        player_dist = to_player.length()

        if self.dead:
            if self._despawned:
                if not getattr(self, "_disable_respawn", False):
                    self._respawn_timer += dt
                    if self._respawn_timer >= HOSTILE_RESPAWN_TIME: self._respawn()
                return
            self._animate(dt, False)
            self._dead_time += dt
            if not player.dead and self._loot and player_dist <= ATTACK_RANGE:
                self._show_prompt(hud, "Press E to loot")
            else: self._clear_prompt(hud)
            if (not self._loot and self._dead_time >= 3.0) or self._dead_time >= HOSTILE_RESPAWN_TIME * 2.0:
                self._despawn(hud)
            return

        if self._hurt_flash_timer == 0.0: self.color_scale = color.white
        if player.dead:
            self._clear_prompt(hud)
            self._enter_reset()
            self._update_reset(dt)
            return

        if self.role == "critter" and player_dist <= AGGRO_DISTANCE: self._state = "flight"
        elif self._state == "patrol" and player_dist <= AGGRO_DISTANCE:
            if self.is_hostile: self._acquire_target(player, "proximity")
            else: self._state = "flight"
        elif self._state == "chase" and self._time_since_damage_taken >= AGGRO_RESET_TIME: self._enter_reset()
        elif self._state == "flight" and player_dist > LEASH_DISTANCE and self._time_since_damage_taken >= AGGRO_RESET_TIME:
            self._enter_reset()

        if player_dist <= ATTACK_RANGE: self._show_prompt(hud, "Press E to attack")
        else: self._clear_prompt(hud)

        if self._state == "chase": self._update_chase(dt); return
        elif self._state == "flight": self._update_flight(dt, to_player); return
        elif self._state == "reset": self._update_reset(dt); return

        if self._wait_timer > 0.0:
            self._wait_timer = max(0.0, self._wait_timer - dt)
            self._animate(dt, False)
            return

        pat_target = self._ground_point(self._patrol_target.x, self._patrol_target.z)
        if (pat_target - self.position).length() <= PATROL_POINT_TOLERANCE:
            self._wait_timer = self._rng.uniform(PATROL_WAIT_MIN, PATROL_WAIT_MAX)
            self._patrol_target = self._pick_patrol_target()
            self._animate(dt, False)
            return
        self._move_toward(pat_target, PATROL_SPEED, dt, stop_distance=0.0)
        self._animate(dt, True)

    def _update_projectiles(self, dt, player):
        active = []
        for p in self.projectiles:
            if p.update(dt, player): continue
            active.append(p)
        self.projectiles = active

    def _pick_patrol_target(self):
        angle = self._rng.uniform(0, 2 * math.pi)
        radius = self._rng.uniform(4.0, PATROL_RADIUS)
        x = self.patrol_center.x + math.cos(angle) * radius
        z = self.patrol_center.z + math.sin(angle) * radius
        return self._ground_point(x, z)

    def _ground_point(self, x, z):
        y = self.terrain.height_at(x, z) if self.terrain else self.patrol_center.y
        return Vec3(x, y, z)

    def reground(self):
        self.position = self._ground_point(self.x, self.z)
        self.patrol_center = self._ground_point(self.patrol_center.x, self.patrol_center.z)
        if self._ghost_np and not self._ghost_np.isEmpty():
            self._ghost_np.setPos(self.x, self.y + 1.2, self.z)

    def _move_toward(self, target, speed, dt, stop_distance):
        to_target = target - self.position
        dist = to_target.length()
        if dist <= stop_distance: return
        to_target.normalize()
        step = min(dist - stop_distance, speed * dt)
        next_pos = self.position + to_target * step
        if self.terrain: next_pos.y = self.terrain.height_at(next_pos.x, next_pos.z)
        self.position = next_pos
        if self._ghost_np and not self._ghost_np.isEmpty():
            self._ghost_np.setPos(self.x, self.y + 1.2, self.z)
        # URSINA Y-UP: Rotation
        self.rotation_y = math.degrees(math.atan2(to_target.x, to_target.z))

    def _update_chase(self, dt):
        t = self._combat_target
        if t is None or not self._is_valid_combat_target(t): self._enter_reset(); self._animate(dt, False); return
        tp = t.get_target_point()
        self._face_target(tp)
        prof = self.get_combat_profile()
        if in_attack_range(self.position, tp, prof): self._animate(dt, False); return
        chase_t = self._ground_point(tp.x, tp.z)
        self._move_toward(chase_t, CHASE_SPEED, dt, stop_distance=stop_distance_for(prof))
        self._animate(dt, True)

    def _update_flight(self, dt, to_p):
        away = -to_p
        away.y = 0
        if away.length_squared() > 0: away.normalize()
        t_pt = self.position + away * 10.0
        t_pt = self._ground_point(t_pt.x, t_pt.z)
        self._move_toward(t_pt, FLIGHT_SPEED, dt, stop_distance=0.0)
        self._animate(dt, True)

    def _enter_reset(self):
        if self.dead: return
        self._state = "reset"
        self._wait_timer = 0.0
        self._attack_cooldown = 0.0
        self._combat_target = None
        self._clear_projectiles()

    def _update_reset(self, dt):
        if self.is_hostile or self._time_since_damage_taken >= AGGRO_RESET_TIME:
            self.health = min(self.max_health, self.health + RESET_REGEN_RATE * dt)
        self._move_toward(self._ground_point(self.patrol_center.x, self.patrol_center.z), PATROL_SPEED, dt, stop_distance=0.0)
        if (self.patrol_center - self.position).length() <= PATROL_POINT_TOLERANCE:
            if self.is_hostile or self._time_since_damage_taken >= AGGRO_RESET_TIME: self.health = self.max_health
            self._state = "patrol"
            self._wait_timer = 0.0
            self._patrol_target = self._pick_patrol_target()
            self._time_since_damage_taken = AGGRO_RESET_TIME
            self._animate(dt, False)
            return
        self._animate(dt, True)

    def get_combat_profile(self):
        c_data = self.data.get("combat", {})
        style = c_data.get("style", "melee")
        if style == "ranged":
            from game.entities.creatures import RANGER_RANGED_PROFILE
            p = dict(RANGER_RANGED_PROFILE)
            p["damage"] = self.stats.get("ranged_damage")
        else:
            from game.entities.creatures import SCOUT_MELEE_PROFILE
            p = dict(SCOUT_MELEE_PROFILE)
            p["damage"] = self.stats.get("melee_damage")
        return p

    def combat_tick(self, tick_dt, player, hud):
        if self.dead or player.dead or self._state != "chase" or not self.is_hostile: return
        prof = self.get_combat_profile()
        if prof is None: return
        if self._combat_target is None: self._combat_target = player
        self._attack_cooldown = max(0.0, self._attack_cooldown - tick_dt)
        if self._attack_cooldown > 0.0: return
        t = self._combat_target
        if t is None or not self._is_valid_combat_target(t): return
        tp = t.get_target_point()
        if not in_attack_range(self.position, tp, prof): return
        self._face_target(tp)
        if hasattr(self, "model") and self.model:
            self.model.play_attack("ranged" if prof["projectile"] else "melee")
        if prof["projectile"]: self._fire_projectile(t, prof)
        else:
            outcome = resolve_attack(self, t, "melee", prof["damage"])
            _report_combat_event(self, t, outcome, "melee")
            if outcome["type"] != "miss" and outcome["type"] != "parry":
                t.take_damage(outcome["damage"], hud, attacker=self)
        self._attack_cooldown = prof["speed"]

    def _animate(self, dt, moving):
        if hasattr(self, "model") and self.model: self.model.animate(dt, moving)

    def try_player_interact(self, player, inventory, hud):
        if player.dead or self._despawned: return False
        p_pos = player.get_pos()
        dx, dz = p_pos.x - self.x, p_pos.z - self.z
        if math.sqrt(dx*dx + dz*dz) > ATTACK_RANGE: return False
        if self.dead: return self._loot_interact(inventory, hud)
        if self._player_attack_cooldown > 0.0: return True
        self.take_damage(PLAYER_ATTACK_DAMAGE, hud, attacker=player, attack_style="melee")
        if hasattr(player, "grant_combat_xp"): player.grant_combat_xp("melee", self._last_damage_taken)
        self._player_attack_cooldown = PLAYER_ATTACK_COOLDOWN
        return True

    def _loot_interact(self, inventory, hud):
        if not self._loot: return True
        if not self._loot_fits(inventory): hud.show_prompt("Inventory full!"); return True
        parts = []
        for item_id, qty in self._loot:
            inventory.add_item(item_id, qty)
            parts.append(f"{qty} {item_id}")
        self._loot = []; self._loot_label_np.hide(); self._clear_prompt(hud); hud.refresh_inventory()
        hud.show_prompt(f"Looted {', '.join(parts)}")
        return True

    def _loot_fits(self, inv):
        needed = 0; seen = set()
        for item_id, _ in self._loot:
            if item_id in seen: continue
            seen.add(item_id)
            if inv.count_item(item_id) == 0: needed += 1
        return inv.get_free_slots() >= needed

    def take_damage(self, amount, hud, attacker=None, attack_style=None):
        if self.dead or amount <= 0: self._last_damage_taken = 0.0; return False
        eff = min(amount, self.health)
        self._last_damage_taken = eff
        self.health = max(0, self.health - eff)
        self._record_damage_contribution(attacker, attack_style, eff)
        self._time_since_damage_taken = 0.0
        if self.health == 0:
            self.dead = True; self._state = "dead"; self._attack_cooldown = 0.0
            self._player_attack_cooldown = 0.0; self._wait_timer = 0.0; self._dead_time = 0.0
            self._combat_target = None; self._loot = self._roll_loot(); self._clear_projectiles()
            if self._loot: self._loot_label_np.show()
            else: self._loot_label_np.hide()
            self.color_scale = color.gray
            # Death tilt (rotate around X)
            self.rotation_x = 90
            self._clear_prompt(hud); self._grant_kill_xp(attacker, attack_style); self._on_death()
            runtime = get_runtime()
            if runtime is not None and runtime.quest_manager is not None:
                runtime.quest_manager.notify_action("kill", self.creature_id)
            return True
        self._state = "chase" if self.is_hostile else "flight"
        self._wait_timer = 0.0; self._attack_cooldown = 0.0
        self.color_scale = color.red
        self._hurt_flash_timer = HURT_FLASH_TIME
        return False

    def _grant_kill_xp(self, attacker, style):
        if attacker is None or not hasattr(attacker, "grant_combat_xp"): return
        xp = self.data.get("xp_reward", max(1, int(self.max_health * 0.4)))
        total = sum(self._player_damage_by_style.values())
        if total > 0:
            for s, d in self._player_damage_by_style.items():
                if d > 0: attacker.grant_combat_xp(s, round(xp * (d / total)))
            return
        if style in PLAYER_XP_STYLES: attacker.grant_combat_xp(style, xp)

    def _record_damage_contribution(self, attacker, style, amount):
        if attacker and style in self._player_damage_by_style: self._player_damage_by_style[style] += amount

    def _on_death(self): pass

    def _respawn(self):
        self.dead = False; self._despawned = False
        if self._level_range:
            self._current_level = self._roll_level(None, self._level_range)
            self._apply_data_stats()
            name = self.data.get("name", self.creature_id.capitalize())
            self._label_np.node().setText(name)
        self.health = self.max_health
        self.position = self._ground_point(self.patrol_center.x, self.patrol_center.z)
        if self._ghost_np and not self._ghost_np.isEmpty():
            self._ghost_np.setPos(self.x, self.y + 1.2, self.z); self._ghost_np.show()
        self.rotation = (0, 0, 0); self.show(); self.color_scale = color.white
        self._state = "patrol"; self._wait_timer = 0.0; self._patrol_target = self._pick_patrol_target()
        self._attack_cooldown = 0.0; self._player_attack_cooldown = 0.0
        self._time_since_damage_taken = AGGRO_RESET_TIME; self._dead_time = 0.0
        self._loot = []; self._combat_target = None; self._player_damage_by_style = {s: 0.0 for s in PLAYER_XP_STYLES}
        self._loot_label_np.hide(); self._clear_projectiles()

    def _despawn(self, hud):
        self._despawned = True; self._respawn_timer = 0.0; self._clear_prompt(hud); self.hide()
        if self._ghost_np and not self._ghost_np.isEmpty(): self._ghost_np.setPos(0, -1000, 0); self._ghost_np.hide()
        self._on_despawn()

    def _on_despawn(self):
        s = self.data.get("special", {})
        c_type = s.get("spawn_carcass")
        if c_type:
            from game.world.resources import AnimalCarcass
            runtime = get_runtime()
            if runtime is not None and runtime.game._active_level:
                carcass = AnimalCarcass(self.render, self.bullet_world, self.position, animal_type=c_type)
                runtime.game._active_level.resources.append(carcass)

    def remove_from_world(self, hud=None):
        self._clear_prompt(hud); self._clear_projectiles()
        if self._ghost_np and not self._ghost_np.isEmpty():
            self.bullet_world.removeGhost(self._ghost); self._ghost_np.removeNode(); self._ghost_np = None
        self.hide()

    def set_targeted(self, targeted):
        self._targeted = targeted
        col = TARGETED_LABEL_COLOR if targeted else self._label_color
        self._label_np.node().setTextColor(*col)
        if targeted: self._target_arrow_np.show()
        else: self._target_arrow_np.hide()

    def is_targetable(self): return not self.dead
    def get_target_point(self): return self.position + Vec3(0, 2.2 if self.data.get("model_type") == "humanoid" else 1.0, 0)
    def get_target_name(self): return self._label_np.node().getText()

    def can_be_hit(self, proj_pos):
        if self.dead: return False
        dx, dz = self.x - proj_pos.x, self.z - proj_pos.z
        if dx*dx + dz*dz > HOSTILE_HIT_RADIUS**2: return False
        return self.y <= proj_pos.y <= self.y + HOSTILE_HIT_HEIGHT

    def _roll_loot(self):
        l_data = self.data.get("loot", {})
        loot = []; role = self.role
        g_mult = 0.5 if role == "critter" else (3.0 if role == "elite" else (10.0 if role == "boss" else 1.0))
        e_mult = 2.0 if role == "elite" else (5.0 if role == "boss" else 1.0)
        g_range = l_data.get("gold", [2, 6])
        g_amt = int(self._rng.randint(g_range[0], g_range[1]) * g_mult)
        if g_amt > 0: loot.append(("gold", g_amt))
        for i, q in l_data.get("guaranteed", []): loot.append((i, q))
        for i, c in l_data.get("extra_items", []):
            if self._rng.random() < (c * e_mult): loot.append((i, 1))
        return loot

    def _show_prompt(self, hud, msg):
        self._prompt_msg = msg; self._prompt_shown = True; hud.show_prompt(msg)
    def _clear_prompt(self, hud):
        if self._prompt_shown and hud: hud.clear_prompt_if(self._prompt_msg)
        self._prompt_shown = False; self._prompt_msg = ""
    def _clear_projectiles(self):
        for p in self.projectiles: p.remove()
        self.projectiles = []
    def _acquire_target(self, t, reason):
        self._combat_target = t; self._state = "chase"; self._wait_timer = 0.0
        self._attack_cooldown = 0.0; self._time_since_damage_taken = 0.0
    def _is_valid_combat_target(self, t): return t and not getattr(t, "dead", False)

    def _face_target(self, tp):
        delta = tp - self.position
        delta.y = 0
        if delta.length_squared() > 0: self.rotation_y = math.degrees(math.atan2(delta.x, delta.z))

    def _fire_projectile(self, t, prof):
        origin = self.position + Vec3(0, 2.1, 0)
        toward = t.get_target_point() - origin
        if toward.length_squared() > 0: toward.normalize(); origin += toward * 0.8
        self.projectiles.append(TargetedProjectile(self.render, origin, t, prof["damage"], prof, self._on_projectile_hit))

    def _on_projectile_hit(self, t, base, hud):
        outcome = resolve_attack(self, t, "ranged", base)
        _report_combat_event(self, t, outcome, "ranged")
        if outcome["type"] != "miss" and outcome["type"] != "parry": t.take_damage(outcome["damage"], hud, attacker=self)

def _report_combat_event(attacker, defender, outcome, style):
    runtime = get_runtime()
    if runtime is not None and runtime.hud is not None:
        runtime.hud.record_combat_event({
            "attacker": attacker.get_target_name(), "defender": defender.get_target_name(),
            "style": style, "result": outcome.get("type", "hit"),
            "damage": outcome.get("damage", 0.0), "base_damage": outcome.get("base_damage", 0.0),
            "mitigated": outcome.get("mitigated", 0.0),
        })

load_creature_defs()
SCOUT_MELEE_PROFILE = make_combat_profile("Claws", ATTACK_RANGE, 2.2, 10, projectile=False)
RANGER_RANGED_PROFILE = make_combat_profile("Spit", 14.0, 2.6, 6, projectile=True, preferred_range=12.0, projectile_speed=22.0, projectile_radius=0.24, projectile_color=(0.7, 1.0, 0.35, 1))
