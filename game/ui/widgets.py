"""Reusable DirectGUI widgets for draggable windows and item slots."""

import builtins

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import MouseButton, Point3, TextNode

from game.systems.inventory import (
    EQUIPMENT_SLOTS,
    clone_stack,
    get_item_def,
    get_item_name,
    move_item,
)


def _shade(color, factor):
    return tuple(max(0.0, min(1.0, channel * factor)) for channel in color[:3]) + (color[3],)


def _rect(parent, left, right, bottom, top, color):
    return DirectFrame(
        parent=parent,
        frameColor=color,
        frameSize=(left, right, bottom, top),
        relief=DGG.FLAT,
    )


ICON_TEMPLATES = {
    "logs": [
        (0.14, 0.38, 0.18, 0.78, 1.0),
        (0.39, 0.63, 0.14, 0.74, 0.9),
        (0.64, 0.88, 0.20, 0.80, 1.1),
    ],
    "ore": [
        (0.16, 0.48, 0.20, 0.55, 1.0),
        (0.40, 0.78, 0.28, 0.72, 0.85),
        (0.28, 0.62, 0.56, 0.86, 1.12),
    ],
    "fish": [
        (0.18, 0.74, 0.34, 0.66, 1.0),
        (0.68, 0.88, 0.42, 0.58, 0.82),
        (0.12, 0.28, 0.40, 0.60, 1.1),
    ],
    "coins": [
        (0.18, 0.78, 0.18, 0.34, 1.0),
        (0.24, 0.84, 0.40, 0.56, 0.9),
        (0.14, 0.74, 0.62, 0.78, 1.08),
    ],
    "sword": [
        (0.44, 0.56, 0.18, 0.82, 1.2), # Blade (uses shade for metal look)
        (0.24, 0.76, 0.32, 0.42, 1.0), # Crossguard
        (0.40, 0.60, 0.06, 0.18, 0.7), # Hilt
    ],
    "shield": [
        (0.22, 0.78, 0.18, 0.82, 1.0),
        (0.30, 0.70, 0.26, 0.74, 1.15),
        (0.46, 0.54, 0.24, 0.76, 0.65),
    ],
    "hood": [
        (0.20, 0.80, 0.18, 0.84, 1.0),
        (0.34, 0.66, 0.34, 0.64, 0.2), # Face opening
    ],
    "armor": [
        (0.24, 0.76, 0.18, 0.82, 1.0),
        (0.12, 0.30, 0.48, 0.72, 0.92),
        (0.70, 0.88, 0.48, 0.72, 0.92),
    ],
    "legs": [
        (0.26, 0.46, 0.16, 0.82, 1.0),
        (0.54, 0.74, 0.16, 0.82, 0.92),
    ],
    # New types
    "herb": [
        (0.45, 0.55, 0.10, 0.50, 0.6), # Stem
        (0.30, 0.50, 0.50, 0.70, 1.0), # Leaf/Flower L
        (0.50, 0.70, 0.55, 0.75, 1.1), # Leaf/Flower R
        (0.40, 0.60, 0.70, 0.90, 1.2), # Flower Top
    ],
    "hide": [
        (0.15, 0.85, 0.20, 0.80, 1.0),
        (0.10, 0.20, 0.10, 0.90, 0.9),
        (0.80, 0.90, 0.10, 0.90, 0.9),
    ],
    "meat": [
        (0.20, 0.80, 0.25, 0.75, 1.0), # Main chunk
        (0.30, 0.70, 0.40, 0.60, 1.2), # Fat/Bone marbling
    ],
    "staff": [
        (0.45, 0.55, 0.10, 0.80, 1.0),
        (0.35, 0.65, 0.80, 0.95, 1.3), # Orb top
    ],
    "mace": [
        (0.46, 0.54, 0.10, 0.60, 0.8), # Handle
        (0.30, 0.70, 0.60, 0.90, 1.0), # Heavy head
    ],
    "axe": [
        (0.46, 0.54, 0.10, 0.85, 0.8), # Handle
        (0.54, 0.85, 0.60, 0.90, 1.0), # Blade
    ],
    "battle_axe": [
        (0.46, 0.54, 0.10, 0.90, 0.8), # Handle
        (0.54, 0.85, 0.60, 0.90, 1.0), # Blade R
        (0.15, 0.46, 0.60, 0.90, 1.0), # Blade L
    ],
    "wand": [
        (0.48, 0.52, 0.20, 0.75, 1.0),
        (0.45, 0.55, 0.75, 0.85, 1.4), # Tip
    ],
    "dagger": [
        (0.46, 0.54, 0.10, 0.30, 0.7), # Handle
        (0.44, 0.56, 0.30, 0.85, 1.1), # Blade
    ],
    "bow": [
        (0.20, 0.30, 0.20, 0.80, 1.0), # Limbs
        (0.70, 0.72, 0.10, 0.90, 0.5), # String
    ],
    "crossbow": [
        (0.45, 0.55, 0.10, 0.85, 1.0), # Stock
        (0.15, 0.85, 0.70, 0.80, 0.9), # Prod
    ],
    "book": [
        (0.20, 0.80, 0.20, 0.80, 1.0), # Cover
        (0.25, 0.75, 0.25, 0.75, 1.3), # Pages
    ]
}

def create_item_icon(parent, item_def):
    color = item_def["color"]
    spec = item_def.get("icon_spec", {})
    kind = spec.get("kind", item_def.get("category", "generic"))
    parts = [_rect(parent, 0.05, 0.95, 0.05, 0.95, (0.08, 0.08, 0.08, 0.2))]

    template = ICON_TEMPLATES.get(kind)
    if template:
        for left, right, bottom, top, shade_factor in template:
            c = _shade(color, shade_factor)
            # Special case for metal-looking items like swords
            if kind in ("sword", "2h_sword", "dagger", "axe", "battle_axe") and shade_factor > 1.0:
                c = _shade((0.78, 0.8, 0.84, 1.0), 1.0)
            parts.append(_rect(parent, left, right, bottom, top, c))
    else:
        # Fallback generic box
        parts.append(_rect(parent, 0.2, 0.8, 0.2, 0.8, color))
        parts.append(_rect(parent, 0.3, 0.7, 0.3, 0.7, _shade(color, 1.1)))

    return parts


class DraggableWindow:
    def __init__(self, title, frame_size, pos, close_command=None):
        self._base = builtins.base
        self.root = DirectFrame(
            frameColor=(0.12, 0.12, 0.12, 0.95),
            frameSize=frame_size,
            pos=pos,
        )
        self._frame_size = frame_size
        self._drag_task_name = f"window_drag_{id(self)}"
        self._dragging = False
        self._drag_start_mouse = (0.0, 0.0)
        self._drag_start_pos = self.root.getPos()

        left, right, bottom, top = frame_size
        title_bottom = top - 0.1
        self.title_bar_bg = DirectFrame(
            parent=self.root,
            frameColor=(0.22, 0.22, 0.22, 1),
            relief=DGG.FLAT,
            frameSize=(left, right, title_bottom, top),
            pos=(0, 0, 0),
        )
        self.title_label = OnscreenText(
            text=title,
            parent=self.root,
            pos=((left + right) * 0.5, top - 0.065),
            scale=0.045,
            fg=(1, 1, 1, 1),
            align=TextNode.ACenter,
        )
        drag_right = right - 0.12 if close_command is not None else right
        self.title_bar = DirectButton(
            parent=self.root,
            frameColor=(0, 0, 0, 0),
            frameSize=(left, drag_right, title_bottom, top),
            pos=(0, 0, 0),
            relief=DGG.FLAT,
            pressEffect=False,
            command=self._noop,
        )
        self.title_bar.bind(DGG.B1PRESS, self._begin_drag)
        self.title_bar.bind(DGG.B1RELEASE, self._end_drag)

        self.body = DirectFrame(
            parent=self.root,
            frameColor=(0, 0, 0, 0),
            frameSize=(left, right, bottom, title_bottom - 0.01),
            pos=(0, 0, 0),
        )

        self.close_button = None
        if close_command is not None:
            self.close_button = DirectButton(
                parent=self.root,
                text="X",
                scale=0.04,
                pos=(right - 0.07, 0, top - 0.055),
                command=close_command,
                frameColor=(0.6, 0.14, 0.14, 1),
                text_fg=(1, 1, 1, 1),
            )

    def show(self):
        self.root.show()

    def hide(self):
        self.root.hide()

    def destroy(self):
        self._stop_drag_task()
        self.root.destroy()

    def _noop(self):
        return None

    def _begin_drag(self, _event):
        if not self._base.mouseWatcherNode.hasMouse():
            return
        mouse = self._mouse_point()
        self._dragging = True
        self._drag_start_mouse = (mouse.x, mouse.z)
        self._drag_start_pos = self.root.getPos()
        if not self._base.taskMgr.hasTaskNamed(self._drag_task_name):
            self._base.taskMgr.add(self._drag_task, self._drag_task_name)

    def _end_drag(self, _event):
        self._dragging = False
        self._stop_drag_task()

    def _stop_drag_task(self):
        self._base.taskMgr.remove(self._drag_task_name)

    def _drag_task(self, task):
        if not self._dragging:
            return task.done
        if not self._base.mouseWatcherNode.hasMouse():
            return task.cont
        if not self._base.mouseWatcherNode.isButtonDown(MouseButton.one()):
            self._dragging = False
            return task.done
        mouse = self._mouse_point()
        dx = mouse.x - self._drag_start_mouse[0]
        dz = mouse.z - self._drag_start_mouse[1]
        self.root.setPos(self._drag_start_pos.x + dx, 0, self._drag_start_pos.z + dz)
        return task.cont

    def _mouse_point(self):
        mouse = self._base.mouseWatcherNode.getMouse()
        return self._base.aspect2d.getRelativePoint(self._base.render2d, Point3(mouse.x, 0, mouse.y))


class ItemDragManager:
    def __init__(self):
        self._base = None
        self.active = None
        self._task_name = "item_drag_ghost"
        self._hover_target = None
        self._collections = []

    def register_collection(self, slot_view):
        if slot_view not in self._collections:
            self._collections.append(slot_view)

    def unregister_collection(self, slot_view):
        if slot_view in self._collections:
            self._collections.remove(slot_view)

    def begin_drag(self, slot_view, slot_key):
        stack = slot_view.container.get_slot(slot_key)
        if stack is None or self.active is not None:
            return
        self._ensure_base()
        self.active = {
            "slot_view": slot_view,
            "slot_key": slot_key,
            "stack": clone_stack(stack),
            "ghost": self._build_ghost(stack),
        }
        self._hover_target = (slot_view, slot_key)
        self._base.taskMgr.add(self._ghost_task, self._task_name)

    def set_hover_target(self, slot_view, slot_key):
        if self.active is None:
            return
        self._hover_target = (slot_view, slot_key)

    def clear_hover_target(self, slot_view, slot_key):
        if self._hover_target == (slot_view, slot_key):
            self._hover_target = None

    def drop_on(self, slot_view, slot_key):
        if self.active is None:
            return
        source_view = self.active["slot_view"]
        source_key = self.active["slot_key"]
        changed = move_item(source_view.container, source_key, slot_view.container, slot_key)
        self._finish_drag(changed, slot_view)

    def cancel(self):
        if self.active is None:
            return
        self._finish_drag(False, None)

    def _ensure_base(self):
        if self._base is None:
            self._base = builtins.base

    def _build_ghost(self, stack):
        item_def = get_item_def(stack["id"])
        ghost = DirectFrame(
            parent=self._base.aspect2d,
            frameColor=(0.18, 0.18, 0.18, 0.9),
            frameSize=(-0.05, 0.05, -0.05, 0.05),
            pos=(0, 0, 0),
            state=DGG.DISABLED,
        )
        icon_root = DirectFrame(
            parent=ghost,
            frameColor=(0, 0, 0, 0),
            frameSize=(0, 1, 0, 1),
            pos=(-0.05, 0, -0.05),
            scale=0.1,
        )
        if item_def:
            create_item_icon(icon_root, item_def)
        if stack["quantity"] > 1:
            OnscreenText(
                text=str(stack["quantity"]),
                parent=ghost,
                pos=(0.03, -0.04),
                scale=0.03,
                fg=(1, 1, 1, 1),
                align=TextNode.ARight,
            )
        return ghost

    def _ghost_task(self, task):
        if self.active is None:
            return task.done
        if not self._base.mouseWatcherNode.hasMouse():
            return task.cont
        mouse = self._base.mouseWatcherNode.getMouse()
        point = self._base.aspect2d.getRelativePoint(self._base.render2d, Point3(mouse.x, 0, mouse.y))
        self.active["ghost"].setPos(point.x, 0, point.z)
        if not self._base.mouseWatcherNode.isButtonDown(MouseButton.one()):
            target = self._hover_target or self._hit_test_target(point.x, point.z)
            if target is not None:
                self.drop_on(*target)
            else:
                self.cancel()
            return task.done
        return task.cont

    def _hit_test_target(self, mouse_x, mouse_z):
        for slot_view in reversed(self._collections):
            target = slot_view.hit_test(mouse_x, mouse_z)
            if target is not None:
                return target
        return None

    def _finish_drag(self, changed, target_view):
        source_view = self.active["slot_view"]
        ghost = self.active["ghost"]
        ghost.destroy()
        self._base.taskMgr.remove(self._task_name)
        self.active = None
        self._hover_target = None
        source_view.refresh()
        if target_view is not None and target_view is not source_view:
            target_view.refresh()
        if changed:
            source_view.notify_changed()
            if target_view is not None and target_view is not source_view:
                target_view.notify_changed()


DRAG_MANAGER = ItemDragManager()


class ItemSlotCollection:
    def __init__(
        self,
        parent,
        container,
        slot_defs,
        slot_size,
        on_change=None,
        show_names=False,
    ):
        self.parent = parent
        self.container = container
        self.slot_defs = slot_defs
        self.slot_size = slot_size
        self.on_change = on_change
        self.show_names = show_names
        self.entries = {}
        DRAG_MANAGER.register_collection(self)
        self._build()

    def _build(self):
        for slot_def in self.slot_defs:
            key = slot_def["key"]
            button = DirectButton(
                parent=self.parent,
                frameColor=(0.24, 0.24, 0.24, 1),
                frameSize=(0, self.slot_size, -self.slot_size, 0),
                pos=(slot_def["x"], 0, slot_def["z"]),
                relief=DGG.FLAT,
                pressEffect=False,
                command=self._noop,
            )
            button.bind(DGG.B1PRESS, lambda event, slot_key=key: self._on_press(slot_key))
            button.bind(DGG.ENTER, lambda event, slot_key=key: self._on_enter(slot_key))
            button.bind(DGG.EXIT, lambda event, slot_key=key: self._on_exit(slot_key))
            icon_root = DirectFrame(
                parent=button,
                frameColor=(0, 0, 0, 0),
                frameSize=(0, 1, 0, 1),
                pos=(0.004, 0, -self.slot_size + 0.004),
                scale=self.slot_size - 0.008,
            )
            qty_label = OnscreenText(
                text="",
                parent=button,
                pos=(self.slot_size - 0.007, -self.slot_size + 0.015),
                scale=0.023,
                fg=(1, 1, 1, 1),
                align=TextNode.ARight,
                mayChange=True,
            )
            empty_label = OnscreenText(
                text=slot_def.get("label", ""),
                parent=button,
                pos=(self.slot_size * 0.5, -self.slot_size * 0.56),
                scale=0.022,
                fg=(0.65, 0.65, 0.68, 1),
                align=TextNode.ACenter,
                mayChange=True,
            )
            self.entries[key] = {
                "button": button,
                "icon_root": icon_root,
                "qty_label": qty_label,
                "empty_label": empty_label,
                "icon_parts": [],
                "slot_def": slot_def,
            }
        self.refresh()

    def destroy(self):
        DRAG_MANAGER.unregister_collection(self)
        for entry in self.entries.values():
            entry["button"].destroy()
        self.entries = {}

    def refresh(self):
        for key, entry in self.entries.items():
            for part in entry["icon_parts"]:
                part.destroy()
            entry["icon_parts"] = []
            stack = self.container.get_slot(key)
            if stack is None:
                entry["qty_label"].setText("")
                entry["empty_label"].setText(entry["slot_def"].get("label", ""))
                continue
            item_def = get_item_def(stack["id"])
            if item_def is not None:
                entry["icon_parts"] = create_item_icon(entry["icon_root"], item_def)
            entry["qty_label"].setText(str(stack["quantity"]) if stack["quantity"] > 1 else "")
            entry["empty_label"].setText(get_item_name(stack["id"]) if self.show_names else "")

    def notify_changed(self):
        if self.on_change is not None:
            self.on_change()

    def _noop(self):
        return None

    def _on_press(self, slot_key):
        DRAG_MANAGER.begin_drag(self, slot_key)

    def _on_enter(self, slot_key):
        DRAG_MANAGER.set_hover_target(self, slot_key)

    def _on_exit(self, slot_key):
        DRAG_MANAGER.clear_hover_target(self, slot_key)

    def hit_test(self, mouse_x, mouse_z):
        for key, entry in self.entries.items():
            button = entry["button"]
            if button.isEmpty():
                continue
            try:
                pos = button.getPos(builtins.base.aspect2d)
                scale = button.getScale(builtins.base.aspect2d)
            except AssertionError:
                continue
            left, right, bottom, top = button["frameSize"]
            x0 = pos.x + left * scale.x
            x1 = pos.x + right * scale.x
            z0 = pos.z + bottom * scale.z
            z1 = pos.z + top * scale.z
            if x0 <= mouse_x <= x1 and z0 <= mouse_z <= z1:
                return (self, key)
        return None


def build_grid_slot_defs(cols, rows, slot_size, slot_gap, origin_x, origin_z):
    slot_defs = []
    for i in range(cols * rows):
        col = i % cols
        row = i // cols
        slot_defs.append(
            {
                "key": i,
                "x": origin_x + col * (slot_size + slot_gap),
                "z": origin_z - row * (slot_size + slot_gap),
            }
        )
    return slot_defs


def build_equipment_slot_defs(slot_size, origin_x, origin_z):
    positions = {
        "head": (origin_x + slot_size * 1.1, origin_z),
        "weapon": (origin_x, origin_z - slot_size * 1.15),
        "chest": (origin_x + slot_size * 1.1, origin_z - slot_size * 1.15),
        "offhand": (origin_x + slot_size * 2.2, origin_z - slot_size * 1.15),
        "legs": (origin_x + slot_size * 1.1, origin_z - slot_size * 2.3),
    }
    slot_defs = []
    for slot_name, meta in EQUIPMENT_SLOTS.items():
        x, z = positions[slot_name]
        slot_defs.append({"key": slot_name, "x": x, "z": z, "label": meta["label"]})
    return slot_defs
