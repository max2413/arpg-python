"""Runtime services for the Ursina-led game bootstrap."""

from game.runtime.context import RuntimeContext, get_runtime, set_runtime
from game.runtime.driver import RuntimeDriver
from game.runtime.rendering import configure_scene_lighting

__all__ = [
    "RuntimeContext",
    "RuntimeDriver",
    "configure_scene_lighting",
    "get_runtime",
    "set_runtime",
]
