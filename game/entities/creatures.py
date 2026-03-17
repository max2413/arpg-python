"""
creatures.py - Data-driven world entities (monsters, animals, etc).
"""

import math
import random
import json
import os

from panda3d.core import Vec3, NodePath, TextNode, BillboardEffect, LineSegs
from panda3d.bullet import BulletGhostNode, BulletSphereShape

from game.entities.models import HumanoidModel, CreatureModel
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

# Fallback Profiles
SCOUT_MELEE_PROFILE = make_combat_profile("Claws", ATTACK_RANGE, 2.2, 10, projectile=False)
RANGER_RANGED_PROFILE = make_combat_profile(
    "Spit", 14.0, 2.6, 6, projectile=True, preferred_range=12.0, 
    projectile_speed=22.0, projectile_radius=0.24, projectile_color=(0.7, 1.0, 0.35, 1)
)

CREATURE_DEFS = {}
CREATURES_PATH = os.path.join("data", "creatures.json")

def load_creature_defs():
    global CREATURE_DEFS
    if not os.path.exists(CREATURES_PATH):
        print(f"[creatures] definition file not found: {CREATURES_PATH}")
        return
    try:
        with open(CREATURES_PATH, "r") as f:
            CREATURE_DEFS = json.load(f)
        print(f"[creatures] loaded {len(CREATURE_DEFS)} definitions")
    except Exception as e:
        print(f"[creatures] failed to load definitions: {e}")

class Creature:
    def __init__(self, render, pos, creature_id, level=None, level_range=None, role=None, patrol_center=None, terrain=None, bullet_world=None):
        self.render = render
        self.terrain = terrain
        self.bullet_world = bullet_world
        self.pos = Vec3(*pos)
        self.patrol_center = Vec3(*(patrol_center or pos))
        
        # Data loading
        self.creature_id = creature_id
        self.data = CREATURE_DEFS.get(creature_id, {})
        if not self.data:
            print(f"[creatures] warning: no definition for {creature_id}")

        self._rng = random.Random(f"{self.patrol_center.x:.2f},{self.patrol_center.y:.2f}")
        self._role_override = role
        
        # Level initialization
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

        self.root = NodePath(f"creature_{creature_id}")
        self.root.reparentTo(render)
        self.root.setPos(self.pos)
        self.root.setP(0)

        self._build_visual()
        self._build_target_arrow()
        self._build_debug_ghost()

    def _roll_level(self, level, level_range):
        if level is not None:
            return level
        if level_range:
            return self._rng.randint(level_range[0], level_range[1])
        return 1

    def _apply_data_stats(self):
        # We inject the current level into a copy of the data so balance.py can use it
        stats_def = dict(self.data)
        stats_def["level"] = self._current_level
        if self._role_override:
            stats_def["role"] = self._role_override
            
        for k, v in creature_runtime_stats(stats_def).items():
            self.stats.set_base_stat(k, v)

    @property
    def max_health(self):
        return self.stats.get("max_health")

    @property
    def is_hostile(self):
        return self.data.get("ai_type", "hostile") == "hostile"

    @property
    def role(self):
        if self._role_override:
            return self._role_override
        return self.data.get("role", "normal")

    def get_level(self):
        return self._current_level

    def _build_visual(self):
        v = self.data.get("visuals", {})
        m_type = self.data.get("model_type", "humanoid")
        
        if m_type == "humanoid":
            self.model = HumanoidModel(
                self.root,
                skin_color=tuple(v.get("skin_color", [0.9, 0.8, 0.7, 1.0])),
                tunic_color=tuple(v.get("tunic_color", [0.5, 0.5, 0.5, 1.0]))
            )
            self.model.hide_arrow()
        else:
            self.model = CreatureModel(
                self.root,
                main_color=tuple(v.get("color", [0.4, 0.4, 0.4, 1.0])),
                size=tuple(v.get("size", [0.8, 1.6, 0.8]))
            )

        self._label_color = tuple(v.get("label_color", [1, 1, 1, 1]))
        name = self.data.get("name", self.creature_id.capitalize())
        
        # Threat tier visual hooks
        role = self.role
        if role == "elite":
            label_text = f"* {name} *"
            self._label_color = (1.0, 0.9, 0.4, 1.0)
        elif role == "boss":
            label_text = f"!!! {name} !!!"
            self._label_color = (1.0, 0.2, 0.2, 1.0)
        else:
            label_text = name

        label_scale = v.get("label_scale", 1.0)
        z_off = 4.3 if m_type == "humanoid" else 2.8
        
        self._label_np = self._make_label("creature_label", label_text, self._label_color, scale=label_scale)
        self._label_np.setPos(0, 0, z_off)

        # Loot indicator
        loot_node = TextNode("loot_label")
        loot_node.setText(LOOT_INDICATOR_TEXT)
        loot_node.setAlign(TextNode.ACenter)
        loot_node.setTextColor(1, 0.9, 0.2, 1)
        loot_node.setShadow(0.04, 0.04)
        loot_node.setShadowColor(0, 0, 0, 0.8)
        self._loot_label_np = self.root.attachNewNode(loot_node)
        self._loot_label_np.setPos(0, 0, 1.1)
        self._loot_label_np.setScale(0.9)
        self._loot_label_np.setEffect(BillboardEffect.makePointEye())
        self._loot_label_np.hide()

    def _make_label(self, node_name, text, color, scale):
        label_node = TextNode(node_name)
        label_node.setText(text)
        label_node.setAlign(TextNode.ACenter)
        label_node.setTextColor(*color)
        label_node.setShadow(0.04, 0.04)
        label_node.setShadowColor(0, 0, 0, 0.8)
        label_np = self.root.attachNewNode(label_node)
        label_np.setScale(scale)
        label_np.setEffect(BillboardEffect.makePointEye())
        return label_np

    def _build_target_arrow(self):
        arrow = LineSegs("target_arrow")
        arrow.setThickness(4.0)
        arrow.setColor(1.0, 0.82, 0.22, 1)
        arrow.moveTo(0, 0, 0)
        arrow.drawTo(0, 0, -0.9)
        arrow.moveTo(0, 0, -0.9)
        arrow.drawTo(-0.22, 0, -0.62)
        arrow.moveTo(0, 0, -0.9)
        arrow.drawTo(0.22, 0, -0.62)
        self._target_arrow_np = self.root.attachNewNode(arrow.create())
        self._target_arrow_np.setPos(0, 0, 5.25)
        self._target_arrow_np.setEffect(BillboardEffect.makePointEye())
        self._target_arrow_np.hide()

    def _build_debug_ghost(self):
        self._ghost_np = None
        self._ghost = None
        if self.bullet_world is None:
            return
        ghost = BulletGhostNode("creature_debug_ghost")
        ghost.addShape(BulletSphereShape(1.0))
        self._ghost = ghost
        self._ghost_np = self.render.attachNewNode(ghost)
        self._ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 1.2)
        self.bullet_world.attachGhost(ghost)

    def update(self, dt, player, hud):
        player_pos = player.get_pos()
        self._player_attack_cooldown = max(0.0, self._player_attack_cooldown - dt)
        self._hurt_flash_timer = max(0.0, self._hurt_flash_timer - dt)
        self._time_since_damage_taken += dt
        self._update_projectiles(dt, player)
        player_target = Vec3(player_pos.x, player_pos.y, self.pos.z)
        to_player = player_target - self.pos
        player_dist = to_player.length()

        if self.dead:
            if self._despawned:
                if getattr(self, "_disable_respawn", False):
                    return
                self._respawn_timer += dt
                if self._respawn_timer >= HOSTILE_RESPAWN_TIME:
                    self._respawn()
                return

            self._animate(dt, False)
            self._dead_time += dt
            if not player.dead and self._loot and player_dist <= ATTACK_RANGE:
                self._show_prompt(hud, "Press E to loot")
            else:
                self._clear_prompt(hud)

            should_despawn = (
                (not self._loot and self._dead_time >= 3.0) or
                self._dead_time >= HOSTILE_RESPAWN_TIME * 2.0
            )
            if should_despawn:
                self._despawn(hud)
            return

        if self._hurt_flash_timer == 0.0:
            self.root.setColorScale(1, 1, 1, 1)

        if player.dead:
            self._clear_prompt(hud)
            self._enter_reset()
            self._update_reset(dt)
            return

        # AI Behavior
        if self.role == "critter" and player_dist <= AGGRO_DISTANCE:
            self._state = "flight"
        elif self._state == "patrol" and player_dist <= AGGRO_DISTANCE:
            if self.is_hostile:
                self._acquire_target(player, "proximity")
            else:
                self._state = "flight"
        elif self._state == "chase" and self._time_since_damage_taken >= AGGRO_RESET_TIME:
            self._enter_reset()
        elif (
            self._state == "flight"
            and player_dist > LEASH_DISTANCE
            and self._time_since_damage_taken >= AGGRO_RESET_TIME
        ):
            self._enter_reset()

        if player_dist <= ATTACK_RANGE:
            self._show_prompt(hud, "Press E to attack")
        else:
            self._clear_prompt(hud)

        if self._state == "chase":
            self._update_chase(dt)
            return
        elif self._state == "flight":
            self._update_flight(dt, to_player)
            return

        if self._state == "reset":
            self._update_reset(dt)
            return

        if self._wait_timer > 0.0:
            self._wait_timer = max(0.0, self._wait_timer - dt)
            self._animate(dt, False)
            return

        patrol_target = self._ground_point(self._patrol_target.x, self._patrol_target.y)
        if (patrol_target - self.pos).length() <= PATROL_POINT_TOLERANCE:
            self._wait_timer = self._rng.uniform(PATROL_WAIT_MIN, PATROL_WAIT_MAX)
            self._patrol_target = self._pick_patrol_target()
            self._animate(dt, False)
            return

        self._move_toward(patrol_target, PATROL_SPEED, dt, stop_distance=0.0)
        self._animate(dt, True)

    def _update_projectiles(self, dt, player):
        active = []
        for projectile in self.projectiles:
            if projectile.update(dt, player):
                continue
            active.append(projectile)
        self.projectiles = active

    def _pick_patrol_target(self):
        angle = self._rng.uniform(0, 2 * math.pi)
        radius = self._rng.uniform(4.0, PATROL_RADIUS)
        x = self.patrol_center.x + math.cos(angle) * radius
        y = self.patrol_center.y + math.sin(angle) * radius
        return self._ground_point(x, y)

    def _ground_point(self, x, y):
        z = self.terrain.height_at(x, y) if self.terrain is not None else self.patrol_center.z
        return Vec3(x, y, z)

    def reground(self):
        self.pos = self._ground_point(self.pos.x, self.pos.y)
        self.patrol_center = self._ground_point(self.patrol_center.x, self.patrol_center.y)
        self.root.setPos(self.pos)
        if self._ghost_np is not None and not self._ghost_np.isEmpty():
            self._ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 1.2)

    def _move_toward(self, target, speed, dt, stop_distance):
        to_target = target - self.pos
        distance = to_target.length()
        if distance <= stop_distance:
            return

        to_target.normalize()
        step = min(distance - stop_distance, speed * dt)
        next_pos = self.pos + to_target * step
        if self.terrain is not None:
            next_pos.z = self.terrain.height_at(next_pos.x, next_pos.y)
        self.pos = next_pos
        self.root.setPos(self.pos)
        if self._ghost_np is not None and not self._ghost_np.isEmpty():
            self._ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 1.2)

        desired_heading = math.degrees(math.atan2(-to_target.x, to_target.y))
        current_heading = self.root.getH()
        heading_delta = (desired_heading - current_heading + 180.0) % 360.0 - 180.0
        max_turn = TURN_SPEED * dt
        heading_delta = max(-max_turn, min(max_turn, heading_delta))
        self.root.setH(current_heading + heading_delta)

    def _update_chase(self, dt):
        target = self._combat_target
        if target is None or not self._is_valid_combat_target(target):
            self._enter_reset()
            self._animate(dt, False)
            return

        target_point = target.get_target_point()
        self._face_target(target_point)
        profile = self.get_combat_profile()
        if in_attack_range(self.pos, target_point, profile):
            self._animate(dt, False)
            return

        chase_target = self._ground_point(target_point.x, target_point.y)
        self._move_toward(chase_target, CHASE_SPEED, dt, stop_distance=stop_distance_for(profile))
        self._animate(dt, True)

    def _update_flight(self, dt, to_player):
        away = -to_player
        away.z = 0
        if away.lengthSquared() > 0:
            away.normalize()
        
        target_pt = self.pos + away * 10.0
        target_pt = self._ground_point(target_pt.x, target_pt.y)
        self._move_toward(target_pt, FLIGHT_SPEED, dt, stop_distance=0.0)
        self._animate(dt, True)

    def _enter_reset(self):
        if self.dead:
            return
        _log_combat(f"creature reset target={self.get_target_name()} health={self.health:.1f}")
        self._state = "reset"
        self._wait_timer = 0.0
        self._attack_cooldown = 0.0
        self._combat_target = None
        self._clear_projectiles()

    def _update_reset(self, dt):
        if self.is_hostile or self._time_since_damage_taken >= AGGRO_RESET_TIME:
            self.health = min(self.max_health, self.health + RESET_REGEN_RATE * dt)
        self._move_toward(self._ground_point(self.patrol_center.x, self.patrol_center.y), PATROL_SPEED, dt, stop_distance=0.0)
        if (self.patrol_center - self.pos).length() <= PATROL_POINT_TOLERANCE:
            if self.is_hostile or self._time_since_damage_taken >= AGGRO_RESET_TIME:
                self.health = self.max_health
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
            profile = dict(RANGER_RANGED_PROFILE)
            profile["damage"] = self.stats.get("ranged_damage")
        else:
            profile = dict(SCOUT_MELEE_PROFILE)
            profile["damage"] = self.stats.get("melee_damage")
        
        return profile

    def combat_tick(self, tick_dt, player, hud):
        if self.dead or player.dead or self._state != "chase" or not self.is_hostile:
            return

        profile = self.get_combat_profile()
        if profile is None:
            return

        if self._combat_target is None:
            self._combat_target = player

        self._attack_cooldown = max(0.0, self._attack_cooldown - tick_dt)
        if self._attack_cooldown > 0.0:
            return

        target = self._combat_target
        if target is None or not self._is_valid_combat_target(target):
            return

        target_point = target.get_target_point()
        if not in_attack_range(self.pos, target_point, profile):
            return

        self._face_target(target_point)
        
        if hasattr(self, "model") and self.model:
            self.model.play_attack("ranged" if profile["projectile"] else "melee")
        
        if profile["projectile"]:
            self._fire_projectile(target, profile)
        else:
            outcome = resolve_attack(self, target, "melee", profile["damage"])
            _log_combat(f"creature melee {outcome['type']} attacker={self.get_target_name()} damage={outcome['damage']}")
            _report_combat_event(self, target, outcome, "melee")
            if outcome["type"] != "miss" and outcome["type"] != "parry":
                target.take_damage(outcome["damage"], hud, attacker=self)
        self._attack_cooldown = profile["speed"]

    def _animate(self, dt, moving):
        if hasattr(self, "model") and self.model:
            self.model.animate(dt, moving)

    def try_player_interact(self, player, inventory, hud):
        if player.dead or self._despawned:
            return False

        player_pos = player.get_pos()
        dx = player_pos.x - self.pos.x
        dy = player_pos.y - self.pos.y
        if math.sqrt(dx * dx + dy * dy) > ATTACK_RANGE:
            return False

        if self.dead:
            return self._loot_interact(inventory, hud)

        if self._player_attack_cooldown > 0.0:
            return True

        self.take_damage(PLAYER_ATTACK_DAMAGE, hud, attacker=player, attack_style="melee")
        if hasattr(player, "grant_combat_xp"):
            player.grant_combat_xp("melee", PLAYER_ATTACK_DAMAGE)
        self._player_attack_cooldown = PLAYER_ATTACK_COOLDOWN
        return True

    def _loot_interact(self, inventory, hud):
        if not self._loot:
            return True

        if not self._loot_fits(inventory):
            hud.show_prompt("Inventory full!")
            return True

        parts = []
        for item_id, qty in self._loot:
            inventory.add_item(item_id, qty)
            parts.append(f"{qty} {item_id}")
        self._loot = []
        self._loot_label_np.hide()
        self._clear_prompt(hud)
        hud.refresh_inventory()
        hud.show_prompt(f"Looted {', '.join(parts)}")
        hud.add_log(f"Looted {', '.join(parts)}")
        return True

    def _loot_fits(self, inventory):
        needed_slots = 0
        seen = set()
        for item_id, _qty in self._loot:
            if item_id in seen:
                continue
            seen.add(item_id)
            if inventory.count_item(item_id) == 0:
                needed_slots += 1
        return inventory.get_free_slots() >= needed_slots

    def take_damage(self, amount, hud, attacker=None, attack_style=None):
        if self.dead or amount <= 0:
            return False

        self.health = max(0, self.health - amount)
        self._record_damage_contribution(attacker, attack_style, amount)
        self._time_since_damage_taken = 0.0
        _log_combat(f"creature damaged target={self.get_target_name()} amount={amount} health={self.health:.1f}")
        if self.health == 0:
            self.dead = True
            self._state = "dead"
            self._attack_cooldown = 0.0
            self._player_attack_cooldown = 0.0
            self._wait_timer = 0.0
            self._dead_time = 0.0
            self._combat_target = None
            self._loot = self._roll_loot()
            self._clear_projectiles()
            if self._loot:
                self._loot_label_np.show()
            else:
                self._loot_label_np.hide()
            self.root.setColorScale(0.25, 0.25, 0.25, 0.35)
            self.root.setP(90)
            self._clear_prompt(hud)
            self._grant_kill_xp(attacker, attack_style)
            self._on_death()
            
            # Notify QuestManager
            import builtins
            app = getattr(builtins, "base", None)
            if app and hasattr(app, "quest_manager"):
                app.quest_manager.notify_action("kill", self.creature_id)
                
            return True

        if self.is_hostile:
            self._state = "chase"
            self._combat_target = attacker
        else:
            self._state = "flight"
            
        self._wait_timer = 0.0
        self._attack_cooldown = 0.0
        _log_combat(f"creature aggro/flight target={self.get_target_name()} reason=damage")
        self.root.setColorScale(1.3, 0.6, 0.6, 1)
        self._hurt_flash_timer = HURT_FLASH_TIME
        return False

    def _grant_kill_xp(self, attacker, attack_style):
        if attacker is None or not hasattr(attacker, "grant_combat_xp"):
            return
        xp_reward = self.data.get("xp_reward", max(1, int(self.max_health * 0.4)))
        damage_total = sum(self._player_damage_by_style.values())
        if damage_total > 0:
            xp_by_style = {
                style: round(xp_reward * (damage / damage_total))
                for style, damage in self._player_damage_by_style.items()
            }
            remainder = xp_reward - sum(xp_by_style.values())
            if remainder > 0:
                favored_style = max(self._player_damage_by_style, key=self._player_damage_by_style.get)
                xp_by_style[favored_style] += remainder
            for style, xp_amount in xp_by_style.items():
                if xp_amount > 0:
                    attacker.grant_combat_xp(style, xp_amount)
            return
        if attack_style in PLAYER_XP_STYLES:
            attacker.grant_combat_xp(attack_style, xp_reward)

    def _record_damage_contribution(self, attacker, attack_style, amount):
        if attacker is None or attack_style not in self._player_damage_by_style:
            return
        if not hasattr(attacker, "grant_combat_xp"):
            return
        self._player_damage_by_style[attack_style] += amount

    def _on_death(self):
        pass

    def _respawn(self):
        self.dead = False
        self._despawned = False
        
        # Re-roll level if we have a range
        if self._level_range:
            self._current_level = self._roll_level(None, self._level_range)
            self._apply_data_stats()
            # Update nameplate label if necessary
            name = self.data.get("name", self.creature_id.capitalize())
            role = self.role
            if role == "elite":
                label_text = f"★ {name} ★"
            elif role == "boss":
                label_text = f"💀 {name} 💀"
            else:
                label_text = name
            self._label_np.node().setText(label_text)

        self.health = self.max_health
        self.pos = self._ground_point(self.patrol_center.x, self.patrol_center.y)
        self.root.setPos(self.pos)
        if self._ghost_np is not None and not self._ghost_np.isEmpty():
            self._ghost_np.setPos(self.pos.x, self.pos.y, self.pos.z + 1.2)
            self._ghost_np.show()
        self.root.setH(0)
        self.root.setP(0)
        self.root.show()
        self.root.setColorScale(1, 1, 1, 1)
        self._state = "patrol"
        self._wait_timer = 0.0
        self._patrol_target = self._pick_patrol_target()
        self._attack_cooldown = 0.0
        self._player_attack_cooldown = 0.0
        self._time_since_damage_taken = AGGRO_RESET_TIME
        self._dead_time = 0.0
        self._loot = []
        self._combat_target = None
        self._player_damage_by_style = {style: 0.0 for style in PLAYER_XP_STYLES}
        self._loot_label_np.hide()
        self._clear_projectiles()

    def _despawn(self, hud):
        self._despawned = True
        self._respawn_timer = 0.0
        self._clear_prompt(hud)
        self.root.hide()
        if self._ghost_np is not None and not self._ghost_np.isEmpty():
            self._ghost_np.setPos(0, 0, -1000) # Move to limbo
            self._ghost_np.hide()
        self._on_despawn()

    def _on_despawn(self):
        s = self.data.get("special", {})
        c_type = s.get("spawn_carcass")
        if c_type:
            from game.world.resources import AnimalCarcass
            import builtins
            app = getattr(builtins, "base", None)
            if app and app._active_level:
                carcass = AnimalCarcass(self.render, self.bullet_world, self.pos, animal_type=c_type)
                app._active_level.resources.append(carcass)

    def remove_from_world(self, hud=None):
        self._clear_prompt(hud)
        self._clear_projectiles()
        if self._ghost_np is not None and not self._ghost_np.isEmpty():
            self.bullet_world.removeGhost(self._ghost)
            self._ghost_np.removeNode()
            self._ghost_np = None
        self.root.hide()

    def set_targeted(self, targeted):
        self._targeted = targeted
        color = TARGETED_LABEL_COLOR if targeted else self._label_color
        self._label_np.node().setTextColor(*color)
        if targeted:
            self._target_arrow_np.show()
        else:
            self._target_arrow_np.hide()

    def is_targetable(self):
        return not self.dead

    def get_target_point(self):
        m_type = self.data.get("model_type", "humanoid")
        z = 2.2 if m_type == "humanoid" else 1.0
        return self.pos + Vec3(0, 0, z)

    def get_target_name(self):
        return self._label_np.node().getText()

    def can_be_hit(self, projectile_pos):
        if self.dead:
            return False
        dx = self.pos.x - projectile_pos.x
        dy = self.pos.y - projectile_pos.y
        if dx * dx + dy * dy > HOSTILE_HIT_RADIUS * HOSTILE_HIT_RADIUS:
            return False
        return self.pos.z <= projectile_pos.z <= self.pos.z + HOSTILE_HIT_HEIGHT

    def _roll_loot(self):
        l_data = self.data.get("loot", {})
        loot = []
        
        role = self.role
        gold_mult = 1.0
        extra_mult = 1.0
        if role == "critter":
            gold_mult = 0.5
        elif role == "elite":
            gold_mult = 3.0
            extra_mult = 2.0
        elif role == "boss":
            gold_mult = 10.0
            extra_mult = 5.0

        # Gold
        g_range = l_data.get("gold", [2, 6])
        gold_amt = int(self._rng.randint(g_range[0], g_range[1]) * gold_mult)
        if gold_amt > 0:
            loot.append(("gold", gold_amt))
        
        # Guaranteed items
        for item_id, qty in l_data.get("guaranteed", []):
            loot.append((item_id, qty))
            
        # Extra items (chance)
        for item_id, chance in l_data.get("extra_items", []):
            if self._rng.random() < (chance * extra_mult):
                loot.append((item_id, 1))
                
        return loot

    def _show_prompt(self, hud, msg):
        self._prompt_msg = msg
        self._prompt_shown = True
        hud.show_prompt(msg)

    def _clear_prompt(self, hud):
        if self._prompt_shown and hud is not None:
            hud.clear_prompt_if(self._prompt_msg)
        self._prompt_shown = False
        self._prompt_msg = ""

    def _clear_projectiles(self):
        for projectile in self.projectiles:
            projectile.remove()
        self.projectiles = []

    def _acquire_target(self, target, reason):
        self._combat_target = target
        self._state = "chase"
        self._wait_timer = 0.0
        self._attack_cooldown = 0.0
        self._time_since_damage_taken = 0.0
        _log_combat(f"creature aggro target={self.get_target_name()} reason={reason}")

    def _is_valid_combat_target(self, target):
        return target is not None and not getattr(target, "dead", False)

    def _face_target(self, target_pos):
        delta = target_pos - self.pos
        delta.z = 0
        if delta.lengthSquared() > 0:
            self.root.setH(math.degrees(math.atan2(-delta.x, delta.y)))

    def _fire_projectile(self, target, profile):
        origin = Vec3(self.pos.x, self.pos.y, self.pos.z + 2.1)
        toward_target = target.get_target_point() - origin
        if toward_target.lengthSquared() > 0:
            toward_target.normalize()
            origin += toward_target * 0.8
        self.projectiles.append(
            TargetedProjectile(self.render, origin, target, profile["damage"], profile, self._on_projectile_hit)
        )

    def _on_projectile_hit(self, target, base_damage, hud):
        outcome = resolve_attack(self, target, "ranged", base_damage)
        _log_combat(f"creature ranged {outcome['type']} target={target.get_target_name()} damage={outcome['damage']}")
        _report_combat_event(self, target, outcome, "ranged")
        if outcome["type"] != "miss" and outcome["type"] != "parry":
            target.take_damage(outcome["damage"], hud, attacker=self)


def _log_combat(message):
    import builtins
    app = getattr(builtins, "base", None)
    if app is not None and hasattr(app, "hud"):
        app.hud.add_combat_log(message)
    if DEBUG_COMBAT_LOGS:
        print(f"[combat] {message}")


def _report_combat_event(attacker, defender, outcome, style):
    import builtins
    app = getattr(builtins, "base", None)
    if app is not None and hasattr(app, "hud"):
        app.hud.record_combat_event(
            {
                "attacker": attacker.get_target_name(),
                "defender": defender.get_target_name(),
                "style": style,
                "result": outcome.get("type", "hit"),
                "damage": outcome.get("damage", 0.0),
                "base_damage": outcome.get("base_damage", 0.0),
                "mitigated": outcome.get("mitigated", 0.0),
            }
        )

load_creature_defs()
