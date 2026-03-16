"""
dev_menu.py - A lightweight developer menu for spawning items and NPCs.
"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText, DirectScrolledFrame
from panda3d.core import TextNode, Vec3

from game.ui.widgets import DraggableWindow, create_item_icon
from game.systems.inventory import ITEMS, get_item_def
from game.entities.creatures import Creature
from game.services.vendor import Vendor

class DevMenu(DraggableWindow):
    def __init__(self, app):
        self.app = app
        super().__init__(
            "Developer Menu (F1)",
            frame_size=(-0.6, 0.6, -0.8, 0.8),
            pos=(0, 0, 0),
            close_command=self.hide
        )
        self._build_content()
        self.hide()

    def _build_content(self):
        # Spawner Header
        OnscreenText(
            text="Item Spawner",
            parent=self.body,
            pos=(0, 0.6),
            scale=0.05,
            fg=(1, 0.8, 0.2, 1),
            align=TextNode.ACenter
        )

        # Scrolled frame for items
        self.item_list = DirectScrolledFrame(
            parent=self.body,
            canvasSize=(-0.5, 0.5, -1.5, 0),
            frameSize=(-0.55, 0.55, -0.1, 0.55),
            frameColor=(0.1, 0.1, 0.1, 1),
            scrollBarWidth=0.04,
            pos=(0, 0, 0)
        )
        canvas = self.item_list.getCanvas()
        
        # Grid of items
        sorted_items = sorted(ITEMS.keys())
        cols = 4
        slot_size = 0.2
        for i, item_id in enumerate(sorted_items):
            col = i % cols
            row = i // cols
            x = -0.4 + col * 0.25
            z = -0.12 - row * 0.25
            
            item_def = ITEMS[item_id]
            btn = DirectButton(
                parent=canvas,
                frameSize=(0, slot_size, -slot_size, 0),
                pos=(x, 0, z),
                frameColor=(0.2, 0.2, 0.2, 1),
                relief=DGG.FLAT,
                command=self._spawn_item,
                extraArgs=[item_id]
            )
            icon_root = DirectFrame(
                parent=btn,
                frameColor=(0, 0, 0, 0),
                pos=(0.01, 0, -slot_size + 0.01),
                scale=slot_size - 0.02
            )
            create_item_icon(icon_root, item_def)
            
            # Tooltip-ish label
            OnscreenText(
                text=item_id,
                parent=btn,
                pos=(slot_size*0.5, -slot_size - 0.03),
                scale=0.02,
                fg=(0.8, 0.8, 0.8, 1),
                align=TextNode.ACenter
            )

        # Entity Spawner
        OnscreenText(
            text="Entity Spawner",
            parent=self.body,
            pos=(0, -0.2),
            scale=0.05,
            fg=(1, 0.8, 0.2, 1),
            align=TextNode.ACenter
        )
        
        spawn_options = [
            ("Scout", "scout"),
            ("Ranger", "ranger"),
            ("Wolf", "wolf"),
            ("Deer", "deer"),
            ("Vendor", Vendor)
        ]
        
        for i, (name, target) in enumerate(spawn_options):
            DirectButton(
                parent=self.body,
                text=name,
                scale=0.045,
                pos=(-0.45 + i*0.23, 0, -0.3),
                frameSize=(-2.2, 2.2, -0.6, 1.2),
                frameColor=(0.25, 0.25, 0.25, 1),
                text_fg=(1, 1, 1, 1),
                command=self._spawn_entity,
                extraArgs=[target]
            )

        # Utilities
        OnscreenText(
            text="Utilities",
            parent=self.body,
            pos=(0, -0.45),
            scale=0.05,
            fg=(1, 0.8, 0.2, 1),
            align=TextNode.ACenter
        )
        
        DirectButton(
            parent=self.body,
            text="Heal Full",
            scale=0.045,
            pos=(-0.3, 0, -0.55),
            frameSize=(-3, 3, -0.6, 1.2),
            command=self._heal_player
        )
        
        DirectButton(
            parent=self.body,
            text="+1000 Gold",
            scale=0.045,
            pos=(0.3, 0, -0.55),
            frameSize=(-3, 3, -0.6, 1.2),
            command=self._add_gold
        )
        
        DirectButton(
            parent=self.body,
            text="Save Game",
            scale=0.045,
            pos=(0, 0, -0.7),
            frameSize=(-3, 3, -0.6, 1.2),
            command=self._save_game
        )

    def toggle(self):
        if self.root.isHidden():
            self.show()
            self.app.hud.show_prompt("Dev Menu Open")
        else:
            self.hide()

    def _spawn_item(self, item_id):
        if self.app.player.inventory.add_item(item_id, 1):
            self.app.hud.refresh_inventory()
            self.app.hud.show_prompt(f"Spawned 1 {item_id}")
        else:
            self.app.hud.show_prompt("Inventory Full!")

    def _spawn_entity(self, target):
        active_level = self.app._active_level
        if active_level is None:
            self.app.hud.show_prompt("No active level!")
            return

        pos = self.app.player.get_pos()
        # Offset slightly forward
        heading_rad = math.radians(self.app.player.char_np.getH())
        offset = Vec3(-math.sin(heading_rad) * 5, math.cos(heading_rad) * 5, 0)
        spawn_pos = pos + offset
        
        if target == Vendor:
            entity = target(self.app.render, self.app.bullet_world, spawn_pos, self.app.player.inventory)
            active_level.interactables.append(entity)
            name = "Vendor"
        else:
            entity = Creature(
                self.app.render,
                spawn_pos,
                creature_id=target,
                patrol_center=spawn_pos,
                terrain=self.app.player.terrain,
                bullet_world=self.app.bullet_world
            )
            active_level.hostiles.append(entity)
            name = target.capitalize()
        
        self.app.hud.show_prompt(f"Spawned {name}")

    def _heal_player(self):
        self.app.player.heal_full()
        self.app.hud.show_prompt("Player Healed")

    def _add_gold(self):
        self.app.player.inventory.add_item("gold", 1000)
        self.app.hud.refresh_inventory()
        self.app.hud.show_prompt("Added 1000 Gold")

    def _save_game(self):
        if hasattr(self.app, "_save_current_game"):
            self.app._save_current_game()

import math
