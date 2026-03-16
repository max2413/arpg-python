"""Game runtime entrypoint and top-level wiring."""

import math

from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import DirectFrame, DirectButton, OnscreenText
from panda3d.bullet import BulletWorld, BulletDebugNode
from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Point2,
    Point3,
    TextNode,
    Vec3,
    WindowProperties,
)

from game.core.camera import CameraController
from game.entities.player import Player
from game.systems.combat import in_attack_range
from game.systems.inventory import Inventory
from game.systems.skills import Skills
from game.systems.persistence import save_game, load_game
from game.systems.quests import QuestManager, create_tutorial_quest
from game.ui.hud import HUD
from game.ui.dev_menu import DevMenu
from game.ui.crafting_ui import CraftingUI
from game.services.crafting import load_recipes
from game.world.levels import LevelManager

RESPAWN_DELAY = 3.0
COMBAT_TICK = 0.2
TAB_TARGET_RANGE = 96.0
TAB_TARGET_MIN_DOT = 0.45
PLAYER_TEST_DROP_HEIGHT = 14.0


class Game(ShowBase):
    def __init__(self):
        super().__init__()
        world_seed = 42

        props = WindowProperties()
        props.setTitle("ARPG Prototype")
        self.win.requestProperties(props)

        self._paused = False
        self._pause_ui = None
        self._respawn_timer = 0.0
        self._was_player_dead = False
        self._selected_target = None
        self._combat_tick_accum = 0.0
        self._spawn_point = Vec3(0, 0, PLAYER_TEST_DROP_HEIGHT)
        self._collision_debug_enabled = False
        self._collision_debug_np = None

        self.bullet_world = BulletWorld()
        self.bullet_world.setGravity(Vec3(0, 0, -25))
        self._setup_collision_debug()

        self.inventory = Inventory(size=28)
        self.skills = Skills()
        self.quest_manager = QuestManager(self)
        load_game(self.inventory, self.skills, self.quest_manager)
        
        self.inventory.add_item("gold", 1000) # Ensure some gold for testing
        self._setup_lighting()
        self.player = Player(self.render, self.bullet_world, self.inventory, terrain=None)
        self.player.stats.skills = self.skills
        self.player.stats.recalculate()
        self.cam_controller = CameraController(self.cam, self.player, self.bullet_world)
        self.hud = HUD(self.inventory, self.skills, player=self.player)
        self.hud.refresh_health(self.player.get_health_display(), self.player.max_health)
        
        if not self.quest_manager.active_quests and not self.quest_manager.completed_ids:
            self.quest_manager.start_quest(create_tutorial_quest())
        
        self.crafting_ui = CraftingUI(self)
        load_recipes()
        
        self.level_manager = LevelManager(self.render, self.bullet_world, self.inventory, seed=world_seed)
        self._load_level("overworld", "default", force_regenerate=True)
        
        self.dev_menu = DevMenu(self)

        self.accept("i", self.hud.toggle_inventory)
        self.accept("c", self.hud.toggle_equipment)
        self.accept("k", self.hud.toggle_skills)
        self.accept("f1", self.dev_menu.toggle)
        self.accept("escape", self._on_escape)
        self.accept("e", self._on_e_pressed)
        self.accept("e-up", self._on_e_released)
        self.accept("mouse1", self._on_mouse1)
        self.accept("tab", self._on_tab_target)
        self.accept("1", self._on_melee_ability)
        self.accept("2", self._on_ranged_ability)
        self.accept("f3", self._toggle_collision_debug)

        self.taskMgr.add(self.update, "game_update")

    def _setup_lighting(self):
        ambient = AmbientLight("world_ambient")
        ambient.setColor((0.42, 0.42, 0.46, 1.0))
        ambient_np = self.render.attachNewNode(ambient)

        sun = DirectionalLight("world_sun")
        sun.setColor((0.92, 0.9, 0.82, 1.0))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(-38, -52, 0)

        self.render.setLight(ambient_np)
        self.render.setLight(sun_np)

    def _setup_collision_debug(self):
        debug_node = BulletDebugNode("bullet_debug")
        debug_node.showWireframe(True)
        debug_node.showConstraints(True)
        debug_node.showBoundingBoxes(False)
        debug_node.showNormals(False)
        self._collision_debug_np = self.render.attachNewNode(debug_node)
        self._collision_debug_np.hide()
        self.bullet_world.setDebugNode(debug_node)

    def _toggle_collision_debug(self):
        self._collision_debug_enabled = not self._collision_debug_enabled
        if self._collision_debug_enabled:
            self._collision_debug_np.show()
            if hasattr(self, "hud"):
                self.hud.show_prompt("Collision debug: ON")
        else:
            self._collision_debug_np.hide()
            if hasattr(self, "hud"):
                self.hud.show_prompt("Collision debug: OFF")

    @property
    def _active_level(self):
        return self.level_manager.get_active_level()

    def _level_interactables(self):
        return self._active_level.interactables if self._active_level is not None else []

    def _level_ui_interactables(self):
        return [obj for obj in self._level_interactables() if hasattr(obj, "ui_open")]

    def _any_ui_open(self):
        return self._modal_ui_open() or self.hud.is_any_window_open()

    def _modal_ui_open(self):
        return any(obj.ui_open for obj in self._level_ui_interactables()) or self._paused

    def _open_ui(self, ui_obj):
        ui_obj.open_ui()
        self.cam_controller.set_ui_open(True)

    def _sync_camera_ui_state(self):
        self.cam_controller.set_ui_open(self._modal_ui_open())

    def _open_pause(self):
        self._paused = True
        self.cam_controller.set_ui_open(True)

        self._pause_ui = DirectFrame(
            frameColor=(0, 0, 0, 0.7),
            frameSize=(-0.5, 0.5, -0.35, 0.35),
            pos=(0, 0, 0),
        )
        OnscreenText(
            text="Paused",
            parent=self._pause_ui,
            pos=(0, 0.22),
            scale=0.08,
            fg=(1, 1, 1, 1),
            align=TextNode.ACenter,
        )
        DirectButton(
            parent=self._pause_ui,
            text="Resume",
            scale=0.06,
            pos=(0, 0, 0.05),
            command=self._close_pause,
            frameColor=(0.2, 0.5, 0.2, 1),
            text_fg=(1, 1, 1, 1),
        )
        DirectButton(
            parent=self._pause_ui,
            text="Save Game",
            scale=0.06,
            pos=(0, 0, -0.06),
            command=self._save_current_game,
            frameColor=(0.2, 0.4, 0.6, 1),
            text_fg=(1, 1, 1, 1),
        )
        DirectButton(
            parent=self._pause_ui,
            text="Regenerate World",
            scale=0.055,
            pos=(0, 0, -0.16),
            command=self._regenerate_overworld,
            frameColor=(0.45, 0.32, 0.1, 1),
            text_fg=(1, 1, 1, 1),
        )
        DirectButton(
            parent=self._pause_ui,
            text="Exit Game",
            scale=0.06,
            pos=(0, 0, -0.28),
            command=self._exit_game,
            frameColor=(0.6, 0.1, 0.1, 1),
            text_fg=(1, 1, 1, 1),
        )

    def _save_current_game(self):
        save_game(self.inventory, self.skills)
        if hasattr(self, "hud"):
            self.hud.show_prompt("Game Saved")

    def _exit_game(self):
        self._save_current_game()
        self.userExit()

    def _close_pause(self):
        self._paused = False
        if self._pause_ui:
            self._pause_ui.destroy()
            self._pause_ui = None
        self._sync_camera_ui_state()

    def _close_level_ui(self):
        closed = False
        for obj in self._level_ui_interactables():
            if obj.ui_open:
                obj.close_ui()
                closed = True
        if closed:
            self._sync_camera_ui_state()
        return closed

    def _load_level(self, level_id, entry_key, force_regenerate=False):
        self._set_selected_target(None)
        self.player.clear_auto_attack()
        self.player._clear_projectiles()
        self._close_level_ui()
        spawn = self.level_manager.load_level(level_id, entry_key, hud=self.hud, force_regenerate=force_regenerate)
        self.player.terrain = self._active_level.world.terrain if self._active_level and self._active_level.world else None
        self._spawn_point = Vec3(*spawn)
        self.player.respawn((self._spawn_point.x, self._spawn_point.y, self._spawn_point.z))
        self.hud.clear_prompt()
        self.hud.clear_target()
        self.hud.clear_range_indicators()
        self._sync_camera_ui_state()

    def _regenerate_overworld(self):
        self.level_manager.clear_saved_overworld()
        self._close_pause()
        self._load_level("overworld", "default", force_regenerate=True)

    def _on_e_pressed(self):
        if self._paused or self.player.dead:
            return
        if self._close_level_ui():
            return
        for teleporter in self._active_level.teleporters:
            if teleporter.try_interact():
                self._load_level(teleporter.destination_level_id, teleporter.destination_entry_key)
                return
        for interactable in self._level_interactables():
            if getattr(interactable, "_in_range", False):
                self._open_ui(interactable)
                return
        for hostile in self._active_level.hostiles:
            if hostile.try_player_interact(self.player, self.inventory, self.hud):
                return
        for resource in self._active_level.resources:
            resource._on_e_pressed()

    def _on_mouse1(self):
        if self._paused or self.player.dead or self._any_ui_open():
            return
        self._pick_target()

    def _on_e_released(self):
        if self.player.dead:
            return
        for resource in self._active_level.resources:
            resource._on_e_released()

    def _on_escape(self):
        if self._close_level_ui():
            return
        if self._paused:
            self._close_pause()
            return
        self._open_pause()

    def _on_melee_ability(self):
        self._begin_auto_attack("melee", "Target too far for melee")

    def _on_ranged_ability(self):
        self._begin_auto_attack("ranged", "Target too far for ranged")

    def _begin_auto_attack(self, style, fail_msg):
        if self._paused or self.player.dead:
            return
        target = self._selected_target
        if target is None or not target.is_targetable():
            self.hud.show_prompt("No target selected")
            return

        profile = self.player.get_combat_profile(style)
        if profile is None:
            return
        if not in_attack_range(self.player.get_pos(), target.get_target_point(), profile):
            self.hud.show_prompt(fail_msg)
            return

        self.player.face_target(target.get_target_point())
        self.player.start_auto_attack(style)
        self.hud.show_prompt(f"Auto attacking with {profile['name']}")

    def _set_selected_target(self, hostile):
        if self._selected_target is hostile:
            return
        if self._selected_target is not None:
            self._selected_target.set_targeted(False)
        self._selected_target = hostile
        if self._selected_target is not None:
            self._selected_target.set_targeted(True)
            self.hud.show_prompt(f"Targeted {self._selected_target.get_target_name()}")
        else:
            self.player.clear_auto_attack()
            self.hud.clear_target()

    def _pick_target(self):
        if not self.mouseWatcherNode.hasMouse():
            return

        mouse = self.mouseWatcherNode.getMouse()
        best = None
        best_score = None
        screen_pt = Point2()

        for hostile in self._active_level.hostiles:
            if not hostile.is_targetable():
                continue
            world_pt = hostile.get_target_point()
            camera_pt = self.cam.getRelativePoint(self.render, Point3(world_pt.x, world_pt.y, world_pt.z))
            if camera_pt.y <= 0:
                continue
            if not self.camLens.project(camera_pt, screen_pt):
                continue
            dx = screen_pt.x - mouse.x
            dy = screen_pt.y - mouse.y
            score = dx * dx + dy * dy
            if score > 0.03:
                continue
            if best_score is None or score < best_score:
                best = hostile
                best_score = score

        self._set_selected_target(best)

    def _on_tab_target(self):
        if self._paused or self.player.dead or self._modal_ui_open():
            return

        player_pos = self.player.get_pos()
        heading_rad = math.radians(self.player.get_heading())
        forward = Vec3(-math.sin(heading_rad), math.cos(heading_rad), 0)
        best = None
        best_score = None

        for hostile in self._active_level.hostiles:
            if not hostile.is_targetable():
                continue
            to_target = hostile.get_target_point() - player_pos
            to_target.z = 0
            distance = to_target.length()
            if distance <= 0.001 or distance > TAB_TARGET_RANGE:
                continue
            to_target.normalize()
            dot = forward.dot(to_target)
            if dot < TAB_TARGET_MIN_DOT:
                continue
            score = dot * 100.0 - distance
            if best_score is None or score > best_score:
                best = hostile
                best_score = score

        if best is not None:
            self._set_selected_target(best)
        else:
            self.hud.show_prompt("No enemy in front")

    def update(self, task):
        if self._paused:
            return task.cont

        dt = globalClock.getDt()  # noqa: F821 - Panda3D global
        dt = min(dt, 0.05)
        self._combat_tick_accum += dt

        self.bullet_world.doPhysics(dt)

        self.player.update(dt)
        player_pos = self.player.get_pos()
        self.cam_controller.update(
            dt,
            player_pos,
            self.player.get_heading(),
            self.player.is_advancing(),
            self.player.is_moving(),
            self.player.is_turning(),
        )

        for resource in self._active_level.resources:
            resource.update(dt, player_pos, self.player, self.inventory, self.skills, self.hud)
        for interactable in self._level_interactables():
            interactable.update(dt, player_pos, self.hud)
        for teleporter in self._active_level.teleporters:
            teleporter.update(player_pos, self.hud)
        for hostile in self._active_level.hostiles:
            hostile.update(dt, self.player, self.hud)

        while self._combat_tick_accum >= COMBAT_TICK:
            self._combat_tick_accum -= COMBAT_TICK
            self.player.combat_tick(COMBAT_TICK, self._selected_target, self.hud)
            for hostile in self._active_level.hostiles:
                hostile.combat_tick(COMBAT_TICK, self.player, self.hud)

        self.player.update_projectiles(dt, self.hud)
        self.hud.refresh_health(self.player.get_health_display(), self.player.max_health)

        if self._selected_target is not None and not self._selected_target.is_targetable():
            self._set_selected_target(None)
        elif self._selected_target is not None:
            distance = self.player.distance_to(self._selected_target.get_target_point())
            self.hud.refresh_target(
                self._selected_target.get_target_name(),
                self._selected_target.health,
                self._selected_target.max_health,
            )
            self.hud.refresh_range_indicators(
                distance <= self.player.melee_ability_range,
                distance <= self.player.ranged_ability_range,
            )
        else:
            self.hud.clear_target()
            self.hud.clear_range_indicators()

        if self.player.dead:
            if not self._was_player_dead:
                self._respawn_timer = RESPAWN_DELAY
                self._was_player_dead = True
            self._respawn_timer = max(0.0, self._respawn_timer - dt)
            self.hud.show_death(self._respawn_timer)
            self.hud.show_prompt("You are dead")
            if self._respawn_timer <= 0.0:
                self.player.respawn((self._spawn_point.x, self._spawn_point.y, self._spawn_point.z))
                self.hud.refresh_health(self.player.get_health_display(), self.player.max_health)
                self.hud.clear_death()
                self.hud.clear_prompt_if("You are dead")
                self._was_player_dead = False
        else:
            self._respawn_timer = 0.0
            self._was_player_dead = False
            self.hud.clear_death()

        self._sync_camera_ui_state()
        return task.cont


def main():
    game = Game()
    game.run()
