"""Minimal Ursina UI primitives used by the ported HUD/menu shell."""

from ursina import Entity, Text, Vec3, camera, clamp, color, mouse, window
from ursina.shaders.unlit_shader import unlit_shader


class FlatButton(Entity):
    def __init__(
        self,
        *,
        text="",
        parent=camera.ui,
        position=(0, 0, 0),
        scale=(0.1, 0.04),
        color_value=color.rgba32(44, 66, 94),
        highlight_color=color.rgba32(62, 88, 120),
        pressed_color=color.rgba32(34, 50, 72),
        text_color=color.rgba32(235, 242, 255),
        text_scale=1.0,
        on_click=None,
        focus_callback=None,
        **kwargs,
    ):
        super().__init__(
            parent=parent,
            position=position,
            scale=scale,
            model="quad",
            shader=unlit_shader,
            unlit=True,
            texture=None,
            color=color_value,
            collider="box",
            **kwargs,
        )
        self.base_color = color_value
        self.highlight_color = highlight_color
        self.pressed_color = pressed_color
        self._click_callback = on_click
        self._focus_callback = focus_callback
        self.setLightOff(True)
        self.clearTexture()
        self.setColorScale(color_value)

        self.label = Text(
            parent=self,
            text=text,
            origin=(0, 0),
            position=(0, 0, -0.02),
            scale=1,
            color=text_color,
        )
        self.label.world_parent = self
        self.label.world_scale = Vec3(20 * text_scale)

    def on_mouse_enter(self):
        self.color = self.highlight_color
        self.setColorScale(self.highlight_color)

    def on_mouse_exit(self):
        self.color = self.base_color
        self.setColorScale(self.base_color)

    def input(self, key):
        if not self.hovered:
            return
        if key == "left mouse down":
            if callable(self._focus_callback):
                self._focus_callback()
            self.color = self.pressed_color
            self.setColorScale(self.pressed_color)
        elif key == "left mouse up":
            self.color = self.highlight_color
            self.setColorScale(self.highlight_color)
            if callable(self._click_callback):
                self._click_callback()


class _WindowDragHandle(Entity):
    def __init__(self, *, target, min_x, max_x, min_y, max_y, focus_callback=None, **kwargs):
        super().__init__(
            model="quad",
            shader=unlit_shader,
            unlit=True,
            texture=None,
            color=color.clear,
            collider="box",
            **kwargs,
        )
        self.target = target
        self.dragging = False
        self.drag_offset = Vec3.zero
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self._focus_callback = focus_callback
        self.setLightOff(True)
        self.clearTexture()

    def input(self, key):
        if self.hovered and key == "left mouse down":
            if callable(self._focus_callback):
                self._focus_callback()
            self.dragging = True
            self.drag_offset = self.target.position - Vec3(mouse.x, mouse.y, self.target.z)
        elif self.dragging and key == "left mouse up":
            self.dragging = False

    def update(self):
        if not self.dragging:
            return
        self.target.position = Vec3(
            clamp(mouse.x + self.drag_offset.x, self.min_x, self.max_x),
            clamp(mouse.y + self.drag_offset.y, self.min_y, self.max_y),
            self.target.z,
        )


class UiWindow:
    _z_counter = 0

    def __init__(
        self,
        *,
        title,
        parent=camera.ui,
        position=(0, 0, 0),
        scale=(0.5, 0.5),
        panel_color=color.rgba32(20, 28, 40, 240),
        header_color=color.rgba32(34, 46, 66, 255),
        close_callback=None,
    ):
        aspect = getattr(window, "aspect_ratio", 16 / 9)
        self.root = Entity(
            parent=parent,
            position=position,
        )
        self.drag_handle = _WindowDragHandle(
            parent=self.root,
            target=self.root,
            focus_callback=self.focus,
            position=(0, scale[1] * 0.45, -0.01),
            scale=(max(0.08, scale[0] - 0.08), 0.07),
            min_x=-aspect + scale[0] * 0.5,
            max_x=aspect - scale[0] * 0.5,
            min_y=-0.5 + scale[1] * 0.5,
            max_y=0.5 - scale[1] * 0.5,
        )
        self.panel = Entity(
            parent=self.root,
            model="quad",
            shader=unlit_shader,
            unlit=True,
            texture=None,
            color=panel_color,
            scale=scale,
        )
        self.panel.setLightOff(True)
        self.panel.clearTexture()
        self.panel.setColorScale(panel_color)
        self.panel.input = lambda key: self.focus() if key == "left mouse down" else None

        self.header = Entity(
            parent=self.root,
            model="quad",
            shader=unlit_shader,
            unlit=True,
            texture=None,
            color=header_color,
            scale=(scale[0], 0.07),
            position=(0, scale[1] * 0.45, -0.001),
        )
        self.header.setLightOff(True)
        self.header.clearTexture()
        self.header.setColorScale(header_color)
        self.header.input = lambda key: self.focus() if key == "left mouse down" else None

        self.title = Text(
            parent=self.root,
            text=title,
            origin=(0, 0),
            position=(0, scale[1] * 0.45, -0.02),
            scale=1.2,
            color=color.rgba32(235, 242, 255),
        )
        self.title.world_parent = self.root
        self.title.world_scale = Vec3(18)

        self.content = Entity(parent=self.root, z=-0.01)

        self.close_button = None
        if close_callback is not None:
            self.close_button = FlatButton(
                parent=self.root,
                text="X",
                position=(scale[0] * 0.43, scale[1] * 0.45, -0.02),
                scale=(0.045, 0.045),
                color_value=color.rgba32(156, 42, 42),
                highlight_color=color.rgba32(182, 60, 60),
                pressed_color=color.rgba32(120, 32, 32),
                text_scale=0.9,
                on_click=close_callback,
                focus_callback=self.focus,
            )

        self.hide()

    def focus(self):
        UiWindow._z_counter += 1
        self.root.z = -0.01 * UiWindow._z_counter

    def show(self):
        self.focus()
        self.root.enabled = True

    def hide(self):
        self.root.enabled = False

    def destroy(self):
        self.root.disable()
