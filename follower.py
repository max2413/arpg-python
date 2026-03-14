"""
follower.py - Patrol hostile that chases the player when they enter aggro range.
"""

import math
import random

from panda3d.core import Vec3, NodePath, TextNode, BillboardEffect, LineSegs

from resources import _make_cylinder, _make_sphere_approx

PATROL_SPEED = 4.0
CHASE_SPEED = 8.5
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
PLAYER_ATTACK_DAMAGE = 20
PLAYER_ATTACK_COOLDOWN = 0.25
HOSTILE_MAX_HEALTH = 45
HOSTILE_RESPAWN_TIME = 6.0
ATTACK_PROMPT = "Press E to attack Scout"
LOOT_PROMPT = "Press E to loot Scout"
HURT_FLASH_TIME = 0.12
LOOT_INDICATOR_TEXT = "Loot"
LOOT_RESPAWN_MULT = 2.0
HOSTILE_HIT_RADIUS = 1.65
HOSTILE_HIT_HEIGHT = 3.8
RANGED_PROJECTILE_SPEED = 22.0
RANGED_PROJECTILE_RANGE = 20.0
RANGED_PROJECTILE_DAMAGE = 10
RANGED_ATTACK_DISTANCE = 14.0
RANGED_ATTACK_COOLDOWN = 2.2
RANGED_PROJECTILE_RADIUS = 0.24
TARGETED_LABEL_COLOR = (1.0, 0.82, 0.22, 1)


class EnemyProjectile:
    def __init__(self, render, pos, direction, color, speed, max_range, damage):
        self.pos = Vec3(pos)
        self.direction = Vec3(direction)
        self.direction.z = 0
        if self.direction.lengthSquared() == 0:
            self.direction = Vec3(0, 1, 0)
        else:
            self.direction.normalize()
        self.speed = speed
        self.max_range = max_range
        self.damage = damage
        self.distance_traveled = 0.0

        self.root = render.attachNewNode("enemy_projectile")
        self.root.setPos(self.pos)
        orb = self.root.attachNewNode(_make_sphere_approx(RANGED_PROJECTILE_RADIUS, color))
        orb.setPos(0, 0, 0)

    def update(self, dt):
        step = self.direction * (self.speed * dt)
        self.pos += step
        self.distance_traveled += step.length()
        self.root.setPos(self.pos)

    def is_expired(self):
        return self.distance_traveled >= self.max_range

    def remove(self):
        self.root.removeNode()


class Follower:
    def __init__(self, render, pos, patrol_center=None):
        self.render = render
        self.pos = Vec3(*pos)
        self.patrol_center = Vec3(*(patrol_center or pos))
        self._rng = random.Random(f"{self.patrol_center.x:.2f},{self.patrol_center.y:.2f}")
        self._state = "patrol"
        self._wait_timer = 0.0
        self._patrol_target = self._pick_patrol_target()
        self._attack_cooldown = 0.0
        self._player_attack_cooldown = 0.0
        self.max_health = HOSTILE_MAX_HEALTH
        self.health = self.max_health
        self.dead = False
        self._respawn_timer = 0.0
        self._prompt_shown = False
        self._prompt_msg = ""
        self._hurt_flash_timer = 0.0
        self._dead_time = 0.0
        self._loot = []
        self.projectiles = []
        self._targeted = False
        self._label_color = (1, 0.95, 0.8, 1)

        self.root = NodePath("follower_npc")
        self.root.reparentTo(render)
        self.root.setPos(self.pos)
        self.root.setP(0)

        self._build_npc()
        self._build_target_arrow()

    def _build_npc(self):
        body = self.root.attachNewNode(_make_cylinder(0.35, 2.8, (0.7, 0.25, 0.2, 1)))
        body.setPos(0, 0, 0)

        head = self.root.attachNewNode(_make_sphere_approx(0.45, (0.9, 0.78, 0.62, 1)))
        head.setPos(0, 0, 3.3)

        self._label_np = self._make_label("scout_label", "Scout", self._label_color, scale=1.1)
        self._label_np.setPos(0, 0, 4.3)

        loot_node = TextNode("scout_loot_label")
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

    def update(self, dt, player, hud):
        player_pos = player.get_pos()
        self._attack_cooldown = max(0.0, self._attack_cooldown - dt)
        self._player_attack_cooldown = max(0.0, self._player_attack_cooldown - dt)
        self._hurt_flash_timer = max(0.0, self._hurt_flash_timer - dt)
        self._update_projectiles(dt, player)
        player_target = Vec3(player_pos.x, player_pos.y, self.pos.z)
        to_player = player_target - self.pos
        player_dist = to_player.length()

        if self.dead:
            self._dead_time += dt
            if not player.dead and self._loot and player_dist <= ATTACK_RANGE:
                self._show_prompt(hud, LOOT_PROMPT)
            else:
                self._clear_prompt(hud)

            should_respawn = (
                (not self._loot and self._dead_time >= HOSTILE_RESPAWN_TIME) or
                self._dead_time >= HOSTILE_RESPAWN_TIME * LOOT_RESPAWN_MULT
            )
            if should_respawn:
                self._respawn()
            return

        if self._hurt_flash_timer == 0.0:
            self.root.setColorScale(1, 1, 1, 1)

        if player.dead:
            self._clear_prompt(hud)
            self._state = "patrol"
            self._wait_timer = 0.0
            self._patrol_target = self._pick_patrol_target()
            self._move_toward(self.patrol_center, PATROL_SPEED, dt, stop_distance=0.0)
            return

        if self._state == "patrol" and player_dist <= AGGRO_DISTANCE:
            self._state = "chase"
        elif self._state == "chase" and player_dist >= LEASH_DISTANCE:
            self._state = "patrol"
            self._wait_timer = 0.0
            self._patrol_target = self._pick_patrol_target()

        if player_dist <= ATTACK_RANGE:
            self._show_prompt(hud, ATTACK_PROMPT)
        else:
            self._clear_prompt(hud)

        if self._state == "chase":
            self._move_toward(player_target, CHASE_SPEED, dt, stop_distance=STOP_DISTANCE)
            if player_dist <= ATTACK_RANGE and self._attack_cooldown <= 0.0:
                player.take_damage(ATTACK_DAMAGE)
                self._attack_cooldown = ATTACK_COOLDOWN
            return

        if self._wait_timer > 0.0:
            self._wait_timer = max(0.0, self._wait_timer - dt)
            return

        patrol_target = Vec3(self._patrol_target.x, self._patrol_target.y, self.pos.z)
        if (patrol_target - self.pos).length() <= PATROL_POINT_TOLERANCE:
            self._wait_timer = self._rng.uniform(PATROL_WAIT_MIN, PATROL_WAIT_MAX)
            self._patrol_target = self._pick_patrol_target()
            return

        self._move_toward(patrol_target, PATROL_SPEED, dt, stop_distance=0.0)

    def _update_projectiles(self, dt, player):
        active = []
        for projectile in self.projectiles:
            projectile.update(dt)
            if self._projectile_hit_player(projectile, player):
                projectile.remove()
                continue
            if projectile.is_expired():
                projectile.remove()
                continue
            active.append(projectile)
        self.projectiles = active

    def _projectile_hit_player(self, projectile, player):
        if player.dead:
            return False
        player_pos = player.get_pos() + Vec3(0, 0, 1.8)
        delta = projectile.pos - player_pos
        return delta.lengthSquared() <= 1.2 * 1.2 and player.take_damage(projectile.damage)

    def _pick_patrol_target(self):
        angle = self._rng.uniform(0, 2 * math.pi)
        radius = self._rng.uniform(4.0, PATROL_RADIUS)
        return Vec3(
            self.patrol_center.x + math.cos(angle) * radius,
            self.patrol_center.y + math.sin(angle) * radius,
            self.patrol_center.z,
        )

    def _move_toward(self, target, speed, dt, stop_distance):
        to_target = target - self.pos
        distance = to_target.length()
        if distance <= stop_distance:
            return

        to_target.normalize()
        step = min(distance - stop_distance, speed * dt)
        self.pos += to_target * step
        self.root.setPos(self.pos)

        desired_heading = math.degrees(math.atan2(-to_target.x, to_target.y))
        current_heading = self.root.getH()
        heading_delta = (desired_heading - current_heading + 180.0) % 360.0 - 180.0
        max_turn = TURN_SPEED * dt
        heading_delta = max(-max_turn, min(max_turn, heading_delta))
        self.root.setH(current_heading + heading_delta)

    def try_player_interact(self, player, inventory, hud):
        if player.dead:
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

        self.take_damage(PLAYER_ATTACK_DAMAGE, hud)
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

    def take_damage(self, amount, hud):
        if self.dead or amount <= 0:
            return False

        self.health = max(0, self.health - amount)
        if self.health == 0:
            self.dead = True
            self._state = "dead"
            self._attack_cooldown = 0.0
            self._player_attack_cooldown = 0.0
            self._wait_timer = 0.0
            self._dead_time = 0.0
            self._loot = self._roll_loot()
            self._clear_projectiles()
            if self._loot:
                self._loot_label_np.show()
            else:
                self._loot_label_np.hide()
            self.root.setColorScale(0.25, 0.25, 0.25, 0.35)
            self.root.setP(90)
            self._clear_prompt(hud)
            return True

        self.root.setColorScale(1.3, 0.6, 0.6, 1)
        self._hurt_flash_timer = HURT_FLASH_TIME
        return False

    def _respawn(self):
        self.dead = False
        self.health = self.max_health
        self.pos = Vec3(self.patrol_center)
        self.root.setPos(self.pos)
        self.root.setH(0)
        self.root.setP(0)
        self.root.setColorScale(1, 1, 1, 1)
        self._state = "patrol"
        self._wait_timer = 0.0
        self._patrol_target = self._pick_patrol_target()
        self._attack_cooldown = 0.0
        self._player_attack_cooldown = 0.0
        self._dead_time = 0.0
        self._loot = []
        self._loot_label_np.hide()
        self._clear_projectiles()

    def remove_from_world(self, hud=None):
        self._clear_prompt(hud)
        self._clear_projectiles()
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
        return self.pos + Vec3(0, 0, 2.2)

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
        loot = [("gold", self._rng.randint(2, 6))]
        if self._rng.random() < 0.55:
            loot.append(("ore", self._rng.randint(1, 2)))
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


class Spitter(Follower):
    def _build_npc(self):
        self._label_color = (0.88, 1, 0.78, 1)
        body = self.root.attachNewNode(_make_cylinder(0.34, 2.7, (0.3, 0.55, 0.22, 1)))
        body.setPos(0, 0, 0)

        head = self.root.attachNewNode(_make_sphere_approx(0.47, (0.82, 0.88, 0.6, 1)))
        head.setPos(0, 0, 3.25)

        self._label_np = self._make_label("spitter_label", "Spitter", self._label_color, scale=1.0)
        self._label_np.setPos(0, 0, 4.3)

        loot_node = TextNode("spitter_loot_label")
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

    def update(self, dt, player, hud):
        super().update(dt, player, hud)

        if self.dead or player.dead or self._state != "chase":
            return

        player_target = Vec3(player.get_pos().x, player.get_pos().y, self.pos.z)
        to_player = player_target - self.pos
        player_dist = to_player.length()
        if ATTACK_RANGE < player_dist <= RANGED_ATTACK_DISTANCE and self._attack_cooldown <= 0.0:
            self._fire_projectile(to_player)
            self._attack_cooldown = RANGED_ATTACK_COOLDOWN

    def _fire_projectile(self, to_player):
        direction = Vec3(to_player)
        origin = Vec3(self.pos.x, self.pos.y, self.pos.z + 2.1) + direction.normalized() * 0.8
        self.projectiles.append(
            EnemyProjectile(
                self.render,
                origin,
                direction,
                color=(0.7, 1.0, 0.35, 1),
                speed=RANGED_PROJECTILE_SPEED,
                max_range=RANGED_PROJECTILE_RANGE,
                damage=RANGED_PROJECTILE_DAMAGE,
            )
        )

    def _roll_loot(self):
        loot = super()._roll_loot()
        if self._rng.random() < 0.7:
            loot.append(("fish", 1))
        return loot
