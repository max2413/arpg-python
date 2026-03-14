"""
main.py — Entry point, ShowBase, Bullet physics world, game loop.
"""

from direct.showbase.ShowBase import ShowBase
from panda3d.bullet import BulletWorld
from panda3d.core import Vec3, WindowProperties, TextNode
from direct.gui.DirectGui import DirectFrame, DirectButton, OnscreenText

from world import World
from player import Player
from camera import CameraController
from inventory import Inventory
from hud import HUD
from bank import Bank
from vendor import Vendor
from worldgen import generate_world


class Game(ShowBase):
    def __init__(self):
        super().__init__()

        props = WindowProperties()
        props.setTitle("ARPG Prototype")
        self.win.requestProperties(props)

        self._paused = False
        self._pause_ui = None

        # --- Physics ---
        self.bullet_world = BulletWorld()
        self.bullet_world.setGravity(Vec3(0, 0, -25))

        # --- Game systems ---
        self.inventory = Inventory(size=28)

        # --- World ---
        self.world = World(self.render, self.bullet_world)

        # --- Player ---
        self.player = Player(self.render, self.bullet_world, self.inventory)

        # --- Camera ---
        self.cam_controller = CameraController(self.cam, self.player)

        # --- HUD ---
        self.hud = HUD(self.inventory)

        # --- Resources (procedurally generated) ---
        self.resources = generate_world(self.render, self.bullet_world, seed=42)

        # --- Bank ---
        self.bank = Bank(self.render, self.bullet_world, (20, 0, 0), self.inventory)

        # --- Vendor ---
        self.vendor = Vendor(self.render, self.bullet_world, (-20, 0, 0), self.inventory)

        # --- Input ---
        self.accept("i", self.hud.toggle_inventory)
        self.accept("k", self.hud.toggle_skills)
        self.accept("escape", self._on_escape)
        self.accept("e", self._on_e_pressed)
        self.accept("e-up", self._on_e_released)

        # --- Game loop task ---
        self.taskMgr.add(self.update, "game_update")

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _any_ui_open(self):
        return self.bank.ui_open or self.vendor.ui_open or self._paused

    def _open_ui(self, ui_obj):
        ui_obj.open_ui()
        self.cam_controller.set_ui_open(True)

    def _sync_camera_ui_state(self):
        """Re-evaluate all UI state and update camera accordingly."""
        if self._any_ui_open():
            self.cam_controller.set_ui_open(True)
        else:
            self.cam_controller.set_ui_open(False)

    # ------------------------------------------------------------------
    # Pause screen
    # ------------------------------------------------------------------

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
            text="Exit Game",
            scale=0.06,
            pos=(0, 0, -0.12),
            command=self.userExit,
            frameColor=(0.6, 0.1, 0.1, 1),
            text_fg=(1, 1, 1, 1),
        )

    def _close_pause(self):
        self._paused = False
        if self._pause_ui:
            self._pause_ui.destroy()
            self._pause_ui = None
        self._sync_camera_ui_state()

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _on_e_pressed(self):
        if self._paused:
            return
        if self.bank.ui_open:
            self.bank.close_ui()
            self._sync_camera_ui_state()
            return
        if self.vendor.ui_open:
            self.vendor.close_ui()
            self._sync_camera_ui_state()
            return
        if self.bank._in_range:
            self._open_ui(self.bank)
            return
        if self.vendor._in_range:
            self._open_ui(self.vendor)
            return
        for res in self.resources:
            res._on_e_pressed()

    def _on_e_released(self):
        for res in self.resources:
            res._on_e_released()

    def _on_escape(self):
        if self.bank.ui_open:
            self.bank.close_ui()
            self._sync_camera_ui_state()
            return
        if self.vendor.ui_open:
            self.vendor.close_ui()
            self._sync_camera_ui_state()
            return
        if self._paused:
            self._close_pause()
            return
        self._open_pause()

    # ------------------------------------------------------------------
    # Game loop
    # ------------------------------------------------------------------

    def update(self, task):
        if self._paused:
            return task.cont

        dt = globalClock.getDt()  # noqa: F821 — Panda3D global
        dt = min(dt, 0.05)

        self.bullet_world.doPhysics(dt)

        player_pos = self.player.get_pos()

        self.cam_controller.update(player_pos)
        self.player.update(dt, self.cam_controller.pivot)

        for res in self.resources:
            res.update(dt, player_pos, self.player, self.inventory, self.hud)

        self.bank.update(dt, player_pos, self.hud)
        self.vendor.update(dt, player_pos, self.hud)

        # If bank/vendor closed themselves via their X button, restore camera
        self._sync_camera_ui_state()

        return task.cont


game = Game()
game.run()
