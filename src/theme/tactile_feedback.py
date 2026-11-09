"""
Universal Tactile Button Physics & Feedback for Nu Age LMS (Flet 1.1.2)
Provides:
1. Universal press feedback: scales buttons to 0.95 on press for tactile response.
2. Return to normal: restores scale to 1.0 on release.
3. Success confirmation pulse: triggers a subtle 1.04 pulse on successful action completion.
"""

from __future__ import annotations
import asyncio
from typing import Any, Optional
import flet as ft


_TACTILE_INSTALLED = False


def enable_tactile_button_physics():
    """
    Hooks into `ft.Control._trigger_event` so that ANY button click event
    (ft.Button, ft.IconButton, ft.FilledButton, ft.OutlinedButton, ft.TextButton, etc.)
    automatically executes snappy tactile scale-down (0.95), smooth release (1.0),
    and a subtle success confirmation pulse (1.04) without modifying individual button call-sites.
    """
    global _TACTILE_INSTALLED
    if _TACTILE_INSTALLED:
        return
    _TACTILE_INSTALLED = True

    orig_trigger = ft.Control._trigger_event

    # Discover all button classes dynamically available in Flet 1.1.2
    button_class_names = [
        "Button",
        "FilledButton",
        "IconButton",
        "OutlinedButton",
        "TextButton",
        "CupertinoButton",
        "FloatingActionButton",
        "FilledIconButton",
        "FilledTonalButton",
        "FilledTonalIconButton",
        "OutlinedIconButton",
    ]
    button_classes = tuple(
        getattr(ft, name) for name in button_class_names if hasattr(ft, name)
    )

    async def _tactile_trigger_event(
        self: ft.Control,
        event_name: str,
        event_data: Any,
        e: Optional[Any] = None,
    ):
        is_btn = isinstance(self, button_classes)
        # Also check custom clickable containers that opt into tactile physics
        is_tactile_container = isinstance(self, ft.Container) and getattr(self, "ink", False) and bool(self.on_click)

        should_animate = (is_btn or is_tactile_container) and event_name == "click"

        if should_animate:
            try:
                if not getattr(self, "animate_scale", None):
                    self.animate_scale = ft.Animation(75, ft.AnimationCurve.EASE_OUT)
                self.scale = 0.95
                if getattr(self, "page", None):
                    self.update()
                    await asyncio.sleep(0.06)
                    self.scale = 1.0
                    self.update()
            except Exception:
                pass

        # Execute original event handler
        result = await orig_trigger(self, event_name, event_data, e)

        # Success confirmation pulse
        if should_animate:
            try:
                if getattr(self, "page", None):
                    self.scale = 1.04
                    self.update()
                    await asyncio.sleep(0.07)
                    if getattr(self, "page", None):
                        self.scale = 1.0
                        self.update()
            except Exception:
                pass

        return result

    ft.Control._trigger_event = _tactile_trigger_event
