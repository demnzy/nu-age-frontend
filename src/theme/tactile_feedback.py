"""
Universal Tactile Button Physics & Feedback for Nu Age LMS (Flet 1.1.2)
Provides:
1. Universal press feedback: scales buttons to 0.95 on press for tactile response.
2. Return to normal: restores scale to 1.0 on release.
3. Success confirmation pulse: triggers a subtle 1.04 pulse on successful action completion.
4. Circuit-breaker protection: drops in-flight events targeting unmounted controls to eliminate RuntimeError crashes.
Non-blocking: Executes animations asynchronously without delaying event dispatch or locking UI.
"""

from __future__ import annotations
import asyncio
from typing import Any, Optional
import flet as ft


_TACTILE_INSTALLED = False


def is_control_mounted(ctrl: ft.Control) -> bool:
    """Safely determines if a control is mounted to an active Page without triggering RuntimeError."""
    try:
        parent = ctrl
        while parent:
            if isinstance(parent, ft.Page):
                return True
            parent = parent.parent
        return False
    except Exception:
        return False


async def _run_tactile_animation(ctrl: ft.Control):
    """Executes smooth tactile scale-down, release, and confirmation pulse in background."""
    try:
        if not is_control_mounted(ctrl):
            return
        if not getattr(ctrl, "animate_scale", None):
            ctrl.animate_scale = ft.Animation(75, ft.AnimationCurve.EASE_OUT)
        ctrl.scale = 0.95
        ctrl.update()
        await asyncio.sleep(0.06)
        if not is_control_mounted(ctrl):
            return
        ctrl.scale = 1.0
        ctrl.update()
        await asyncio.sleep(0.04)
        if not is_control_mounted(ctrl):
            return
        ctrl.scale = 1.04
        ctrl.update()
        await asyncio.sleep(0.06)
        if not is_control_mounted(ctrl):
            return
        ctrl.scale = 1.0
        ctrl.update()
    except Exception:
        pass


def enable_tactile_button_physics():
    """
    Hooks into `ft.Control._trigger_event` so that standard button click events
    (ft.Button, ft.IconButton, ft.FilledButton, ft.OutlinedButton, ft.TextButton, etc.)
    automatically execute snappy tactile scale-down (0.95), smooth release (1.0),
    and a subtle success confirmation pulse (1.04) without delaying event callbacks.
    Also acts as a resilient circuit-breaker against unmounted control race conditions.
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
        # Guard 1: Drop stale in-flight events targeting unmounted/detached controls
        if not is_control_mounted(self):
            return None

        # Only apply tactile physics to standard buttons on click events (never arbitrary containers)
        if isinstance(self, button_classes) and event_name == "click":
            asyncio.create_task(_run_tactile_animation(self))

        # Execute original event handler safely, suppressing unmounted control race conditions
        try:
            return await orig_trigger(self, event_name, event_data, e)
        except RuntimeError as err:
            err_msg = str(err)
            if "must be added to the page first" in err_msg or "must be added to a page" in err_msg:
                return None
            raise
        except Exception as ex:
            ex_msg = str(ex)
            if "must be added to the page first" in ex_msg or "must be added to a page" in ex_msg:
                return None
            raise

    ft.Control._trigger_event = _tactile_trigger_event
