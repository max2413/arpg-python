"""Ursina entity that owns the per-frame update and input dispatch."""

from ursina import Entity, time


class RuntimeDriver(Entity):
    def __init__(self, update_callback, input_callback):
        super().__init__()
        self._update_callback = update_callback
        self._input_callback = input_callback

    def update(self):
        self._update_callback(min(time.dt, 0.05))

    def input(self, key):
        self._input_callback(key)
