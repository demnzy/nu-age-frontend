"""
src/utils/modal_guard.py

Centralized Modal & Dialog Safeguard Utility for Flet 0.86.5.
Guarantees:
1. Zero Modal Superimposition: Ensures only one modal/barrier is active at any time,
   preventing compounding semi-transparent black overlays (the "clouded view" bug).
2. Anti-Spam & Tap Debouncing: Drops rapid duplicate clicks and duplicate dialog requests.
3. Flet 0.86.5 Lifecycle Compliance:
   - Modals are cleanly dismissed via `dlg.open = False; page.update()`.
   - NEVER calls `page.overlay.remove(dlg)`, which breaks Flutter route transitions and freezes the UI.
4. Automatic Lifecycle Tracking: Cleans up registry state when a dialog is dismissed via barrier tap.
"""

import time
from typing import Callable, Dict, Any, Optional
import flet as ft

# Registry mapping page ID -> dict with active modal state
# {page_id: {"active_dlg": control, "active_tag": str, "last_open_time": float}}
_PAGE_MODAL_REGISTRY: Dict[int, Dict[str, Any]] = {}


def _get_page_state(page: ft.Page) -> Dict[str, Any]:
    """Retrieves or initializes the modal state for a given page instance."""
    p_id = id(page)
    if p_id not in _PAGE_MODAL_REGISTRY:
        _PAGE_MODAL_REGISTRY[p_id] = {
            "active_dlg": None,
            "active_tag": None,
            "last_open_time": 0.0,
        }
    return _PAGE_MODAL_REGISTRY[p_id]


def safe_open_dialog(
    page: ft.Page,
    dlg: ft.Control,
    tag: Optional[str] = None,
    min_interval_ms: int = 350,
) -> bool:
    """
    Safely presents a dialog (AlertDialog or BottomSheet) on page.overlay.

    - If the exact same dialog or tag is already open, ignores duplicate requests (anti-spam).
    - If another dialog is already open, cleanly closes it before presenting the new one
      so modal barriers never stack and cloud the screen.
    - Preserves existing on_dismiss handlers while guaranteeing registry cleanup.
    - Strictly follows Flet 0.86.5 conventions.
    """
    if not page or not dlg:
        return False

    now = time.monotonic()
    state = _get_page_state(page)

    active_dlg = state.get("active_dlg")
    active_tag = state.get("active_tag")
    last_open = state.get("last_open_time", 0.0)

    is_active_open = active_dlg is not None and getattr(active_dlg, "open", False)
    is_same_tag = tag is not None and active_tag is not None and (tag == active_tag)
    is_same_dlg = active_dlg is dlg

    # 1. Anti-spam: Ignore if already open with the same tag or same dialog instance
    if is_active_open and (is_same_tag or is_same_dlg):
        return False

    # 2. Debounce rapid repeat attempts with the same tag within cooldown
    if is_same_tag and ((now - last_open) < (min_interval_ms / 1000.0)):
        return False

    # 3. Prevent superimposition: If another dialog is currently open, close it cleanly
    if is_active_open and active_dlg is not dlg:
        try:
            active_dlg.open = False
        except Exception:
            pass

    # 4. Wrap on_dismiss to clear registry when user dismisses via barrier tap or ESC
    orig_on_dismiss = getattr(dlg, "on_dismiss", None)

    def _guarded_on_dismiss(e=None):
        curr_state = _get_page_state(page)
        if curr_state.get("active_dlg") is dlg:
            curr_state["active_dlg"] = None
            curr_state["active_tag"] = None
        if orig_on_dismiss:
            try:
                orig_on_dismiss(e)
            except Exception as ex:
                print(f"[modal_guard] on_dismiss callback error: {ex}")

    dlg.on_dismiss = _guarded_on_dismiss

    # 5. Ensure dialog is mounted in page.overlay
    if hasattr(page, "overlay"):
        if dlg not in page.overlay:
            page.overlay.append(dlg)

    dlg.open = True
    state["active_dlg"] = dlg
    state["active_tag"] = tag
    state["last_open_time"] = now

    try:
        page.update()
    except Exception:
        pass

    return True


def safe_close_dialog(page: ft.Page, dlg: Optional[ft.Control] = None) -> None:
    """
    Safely dismisses a dialog without calling page.overlay.remove (Flet 0.86.5 rule).
    If dlg is None, dismisses whichever dialog is currently tracked as active on page.
    """
    if not page:
        return

    state = _get_page_state(page)
    active_dlg = state.get("active_dlg")

    target = dlg if dlg is not None else active_dlg
    if target is not None:
        try:
            target.open = False
        except Exception:
            pass

    if target is active_dlg or dlg is None:
        state["active_dlg"] = None
        state["active_tag"] = None

    try:
        page.update()
    except Exception:
        pass


def is_modal_open(page: ft.Page, tag: Optional[str] = None) -> bool:
    """
    Checks if a modal (or a modal with a specific tag) is currently open on page.
    """
    if not page:
        return False
    state = _get_page_state(page)
    active_dlg = state.get("active_dlg")
    if active_dlg is None or not getattr(active_dlg, "open", False):
        return False
    if tag is not None:
        return state.get("active_tag") == tag
    return True


def debounced_click(callback: Callable, min_interval_ms: int = 400) -> Callable:
    """
    Returns an event handler that ignores repeated calls occurring within min_interval_ms.
    Works seamlessly with both `on_click=debounced_click(func)` and zero-argument callbacks.
    """
    last_called = [0.0]

    def _wrapper(e=None):
        now = time.monotonic()
        if (now - last_called[0]) < (min_interval_ms / 1000.0):
            return
        last_called[0] = now
        try:
            return callback(e)
        except TypeError:
            return callback()

    return _wrapper

