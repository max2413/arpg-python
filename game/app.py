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
from game.core.selection import SelectionManager
from game.entities.player import Player
from game.systems.combat_manager import CombatManager
from game.systems.inventory import Inventory
from game.systems.skills import Skills
from game.systems.persistence import save_game, load_game
from game.systems.quests import QuestManager, create_tutorial_quest
from game.ui.hud import HUD
from game.ui.dev_menu import DevMenu
from game.ui.crafting_ui import CraftingUI
from game.entities.creatures import load_creature_defs
from game.services.crafting import load_recipes
from game.world.levels import LevelManager

RESPAWN_DELAY = 3.0
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
        self._spawn_point = Vec3(0, 0, PLAYER_TEST_DROP_HEIGHT)
        self._collision_debug_enabled = False
        self._collision_debug_np = None
        self._benchmark_target = None
        self._benchmark_started = None

        self.bullet_world = BulletWorld()
        self.bullet_world.setGravity(Vec3(0, 0, -25))
        self._setup_collision_debug()

        self.inventory = Inventory(size=28)
        self.skills = Skills()
        self.quest_manager = QuestManager(self)
        load_game(self.inventory, self.skills, self.quest_manager)
        self._setup_lighting()
        self.player = Player(self.render, self.bullet_world, self.inventory, terrain=None)
        self.player.stats.skills = self.skills
        self.player.stats.recalculate()
        self.cam_controller = CameraController(self.cam, self.player, self.bullet_world)
        load_recipes()
        self.hud = HUD(self.inventory, self.skills, player=self.player)
        self.hud.refresh_health(self.player.get_health_display(), self.player.max_health)
        
        self.selection_manager = SelectionManager(self)
        self.combat_manager = CombatManager(self)

        if not self.quest_manager.active_quests and not self.quest_manager.completed_ids:
            self.quest_manager.start_quest(create_tutorial_quest())

        self.crafting_ui = CraftingUI(self)
        
        self.level_manager = LevelManager(self.render, self.bullet_world, self.inventory, seed=world_seed)
        self._load_level("overworld", "default")
        
        self.dev_menu = DevMenu(self)

        self.accept("i", self.hud.toggle_inventory)
        self.accept("c", self.hud.toggle_equipment)
        self.accept("k", self.hud.toggle_skills)
        self.accept("l", self.hud.toggle_game_log)
        self.accept("j", self.hud.toggle_combat_log)
        self.accept("f4", self.hud.toggle_combat_debug)
        self.accept("f1", self.dev_menu.toggle)
        self.accept("escape", self._on_escape)
        self.accept("e", self._on_e_pressed)
        self.accept("e-up", self._on_e_released)
        self.accept("mouse1", self._on_mouse1)
        self.accept("tab", self.selection_manager.on_tab_target)
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
        save_game(self.inventory, self.skills, self.quest_manager)
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
        self.selection_manager.set_selected_target(None)
        self._benchmark_target = None
        self._benchmark_started = None
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

    def start_benchmark(self, target, expected_level=None):
        self._benchmark_target = target
        self._benchmark_started = globalClock.getFrameTime()  # noqa: F821 - Panda3D global
        target_level = target.get_level() if hasattr(target, "get_level") else expected_level
        self.hud.set_benchmark_summary(
            f"Benchmark active vs {target.get_target_name()} Lv {target_level}"
        )

    def _update_benchmark(self):
        if self._benchmark_target is None:
            return
        if self._benchmark_started is None:
            self._benchmark_started = globalClock.getFrameTime()  # noqa: F821 - Panda3D global
        elapsed = max(0.0, globalClock.getFrameTime() - self._benchmark_started)  # noqa: F821 - Panda3D global
        if self.player.dead:
            name = self._benchmark_target.get_target_name() if self._benchmark_target is not None else "target"
            self.hud.set_benchmark_summary(f"Failed vs {name} after {elapsed:.1f}s")
            self._benchmark_target = None
            self._benchmark_started = None
            return
        if getattr(self._benchmark_target, "dead", False):
            self.hud.set_benchmark_summary(
                f"Victory vs {self._benchmark_target.get_target_name()} in {elapsed:.1f}s"
            )
            self._benchmark_target = None
            self._benchmark_started = None

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
        self.selection_manager.pick_target()

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
        self.combat_manager.begin_auto_attack("melee", "Target too far for melee")

    def _on_ranged_ability(self):
        self.combat_manager.begin_auto_attack("ranged", "Target too far for ranged")

    def update(self, task):
        if self._paused:
            return task.cont

        dt = globalClock.getDt()  # noqa: F821 - Panda3D global
        dt = min(dt, 0.05)

        self.bullet_world.doPhysics(dt)

        self.player.update(dt)
        self.crafting_ui.update(dt)
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

        self.combat_manager.update(dt)
        self.selection_manager.update()
        self._update_benchmark()

        self.player.update_projectiles(dt, self.hud)
        self.hud.refresh_health(self.player.get_health_display(), self.player.max_health)
        self.hud.refresh_player_level(self.skills.get_combat_level())

        target = self.selection_manager.selected_target
        if target is not None:
            distance = self.player.distance_to(target.get_target_point())
            self.hud.refresh_target(
                target.get_target_name(),
                target.health,
                target.max_health,
                target.get_level() if hasattr(target, "get_level") else None,
                self.skills.get_combat_level(),
                target_role=getattr(target, "role", "normal")
            )
            self.hud.refresh_range_indicators(
                distance <= self.player.melee_ability_range,
                distance <= self.player.ranged_ability_range,
            )
        else:
            self.hud.clear_target()
            self.hud.clear_range_indicators()

        self.hud.refresh_combat_debug(self.player, target)

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
