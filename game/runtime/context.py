"""Shared runtime context for gameplay modules."""

from dataclasses import dataclass, field

from ursina import held_keys, mouse, scene


_CURRENT_RUNTIME = None


class InputState:
    """Small adapter that keeps Panda mouse details out of gameplay code."""

    def __init__(self, app):
        self._app = app

    def is_held(self, key):
        aliases = {
            "shift": ("shift", "left shift", "right shift"),
            "right mouse": ("right mouse",),
            "left mouse": ("left mouse",),
        }
        keys = aliases.get(key, (key,))
        return any(bool(held_keys[k]) for k in keys)

    def has_mouse(self):
        return self._app.mouseWatcherNode.hasMouse()

    def mouse_position(self):
        if not self.has_mouse():
            return None
        return self._app.mouseWatcherNode.getMouse()

    @property
    def mouse(self):
        return mouse


@dataclass
class RuntimeContext:
    app: object
    game: object
    bullet_world: object
    input_state: InputState = field(init=False)
    hud: object = None
    crafting_ui: object = None
    quest_manager: object = None
    player: object = None

    def __post_init__(self):
        self.input_state = InputState(self.app)

    @property
    def scene(self):
        return scene


def set_runtime(runtime):
    global _CURRENT_RUNTIME
    _CURRENT_RUNTIME = runtime


def get_runtime():
    return _CURRENT_RUNTIME
