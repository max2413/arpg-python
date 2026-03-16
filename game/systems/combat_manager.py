"""
combat_manager.py - Manages the high-level combat loop and attack resolution.
"""

from game.systems.combat import in_attack_range

COMBAT_TICK = 0.2

class CombatManager:
    def __init__(self, app):
        self.app = app
        self._combat_tick_accum = 0.0

    def update(self, dt):
        self._combat_tick_accum += dt
        
        while self._combat_tick_accum >= COMBAT_TICK:
            self._combat_tick_accum -= COMBAT_TICK
            self._tick_combat(COMBAT_TICK)

    def _tick_combat(self, tick_dt):
        selected_target = self.app.selection_manager.selected_target
        
        # Player auto-attack
        self.app.player.combat_tick(tick_dt, selected_target, self.app.hud)
        
        # Hostile AI combat
        active_level = self.app._active_level
        if active_level:
            for hostile in active_level.hostiles:
                hostile.combat_tick(tick_dt, self.app.player, self.app.hud)

    def begin_auto_attack(self, style, fail_msg):
        if self.app._paused or self.app.player.dead:
            return
            
        target = self.app.selection_manager.selected_target
        if target is None or not target.is_targetable():
            self.app.hud.show_prompt("No target selected")
            return

        profile = self.app.player.get_combat_profile(style)
        if profile is None:
            if style == "ranged":
                self.app.hud.show_prompt("No ranged weapon equipped")
            return
            
        if not in_attack_range(self.app.player.get_pos(), target.get_target_point(), profile):
            self.app.hud.show_prompt(fail_msg)
            return

        self.app.player.face_target(target.get_target_point())
        self.app.player.start_auto_attack(style)
        self.app.hud.show_prompt(f"Auto attacking with {profile['name']}")
