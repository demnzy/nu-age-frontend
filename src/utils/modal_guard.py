"""
src/utils/modal_guard.py

Centralized Modal & Dialog Safeguard Utility for Flet 1.1.2.
Guarantees:
1. Native Flet 1.1.2 Dialog Lifecycle (`page.show_dialog` / `page._dialogs`):
   - Uses Flet 1.1.2's native `page.show_dialog(dlg)` for `DialogControl` subclasses
     (`AlertDialog`, `BottomSheet`), which updates ONLY `page._dialogs` (never serializing
     the full 2,000+ control page tree) and automatically removes the dialog from
     `page._dialogs` only after Flutter completes the exit animation and fires `dismiss`.
   - Avoids reusing/mutating stale `AlertDialog` control IDs (`_i`), which in Flet 1.1.2
     desyncs Dart's internal `_open` property and `ModalRoute` reference.
2. Zero Modal Superimposition: Ensures only one modal/barrier is active at any time.
3. Anti-Spam & Single-Fire `on_dismiss`: Drops rapid duplicate clicks and guarantees
   `on_dismiss` callbacks execute at most once per open cycle.
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


def _is_mounted(ctrl: Optional[ft.Control]) -> bool:
    """Safely checks if a control is mounted to a page without raising RuntimeError in Flet 1.1.2."""
    if ctrl is None:
        return False
    try:
        return ctrl.page is not None
    except (RuntimeError, AttributeError):
        return False


def _identity_in(target: Any, items: Any) -> bool:
    """Checks object identity (`is`) membership to avoid expensive dataclass `==` comparisons."""
    if not items:
        return False
    for item in items:
        if item is target:
            return True
    return False


def safe_open_dialog(
    page: ft.Page,
    dlg: ft.Control,
    tag: Optional[str] = None,
    min_interval_ms: int = 250,
) -> bool:
    """
    Safely presents a dialog (AlertDialog or BottomSheet) using Flet 1.1.2's native
    `page.show_dialog` stack (or `page.overlay` fallback for mock/test pages).
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

    # 3. Prevent superimposition: If another dialog is currently open, close it cleanly first
    if is_active_open and active_dlg is not dlg:
        try:
            active_dlg.open = False
            if _is_mounted(active_dlg):
                active_dlg.update()
        except Exception:
            pass

    orig_on_dismiss = getattr(dlg, "on_dismiss", None)
    dismiss_fired = [False]

    def _guarded_on_dismiss(e=None):
        if dismiss_fired[0]:
            return
        dismiss_fired[0] = True
        curr_state = _get_page_state(page)
        if curr_state.get("active_dlg") is dlg:
            curr_state["active_dlg"] = None
            curr_state["active_tag"] = None
        if orig_on_dismiss:
            try:
                orig_on_dismiss(e)
            except TypeError:
                try:
                    orig_on_dismiss()
                except Exception:
                    pass
            except Exception as ex:
                print(f"[modal_guard] on_dismiss callback error: {ex}")

    dlg.on_dismiss = _guarded_on_dismiss
    try:
        dlg._single_dismiss_fn = _guarded_on_dismiss
        dlg._modal_guard_tag = tag
    except Exception:
        pass

    state["active_dlg"] = dlg
    state["active_tag"] = tag
    state["last_open_time"] = now

    # 4. Present via Flet 1.1.2 native `page.show_dialog` when available (scoped `_dialogs.update()`)
    dialogs_container = getattr(page, "_dialogs", None)
    if (
        hasattr(page, "show_dialog")
        and dialogs_container is not None
        and isinstance(dlg, ft.DialogControl)
    ):
        try:
            if not _identity_in(dlg, dialogs_container.controls):
                page.show_dialog(dlg)
            else:
                dlg.open = True
                if _is_mounted(dlg):
                    dlg.update()
                else:
                    dialogs_container.update()
            return True
        except Exception:
            pass

    # Fallback for mock pages or non-DialogControl overlays
    overlay = getattr(page, "overlay", None)
    if overlay is not None and not _identity_in(dlg, overlay):
        overlay.append(dlg)

    dlg.open = True
    try:
        if _is_mounted(dlg):
            dlg.update()
        else:
            page.update()
    except Exception:
        try:
            page.update()
        except Exception:
            pass

    return True


def safe_close_dialog(page: ft.Page, dlg: Optional[ft.Control] = None) -> None:
    """
    Safely dismisses a dialog using scoped `target.update()` (1-attribute patch `open=False`)
    so Flutter's ModalRoute pops immediately without serializing the entire page.
    """
    if not page:
        return

    state = _get_page_state(page)
    active_dlg = state.get("active_dlg")

    target = dlg if dlg is not None else active_dlg
    if target is None:
        # Check page._dialogs stack for any open dialog
        dialogs_container = getattr(page, "_dialogs", None)
        if dialogs_container is not None:
            for d in reversed(getattr(dialogs_container, "controls", [])):
                if getattr(d, "open", False):
                    target = d
                    break

    if target is not None:
        try:
            target.open = False
        except Exception:
            pass

    if target is active_dlg or dlg is None:
        state["active_dlg"] = None
        state["active_tag"] = None

    if target is not None:
        try:
            if _is_mounted(target):
                target.update()
                return
            dialogs_container = getattr(page, "_dialogs", None)
            if dialogs_container is not None and _identity_in(target, dialogs_container.controls):
                dialogs_container.update()
                return
        except Exception:
            pass

    try:
        page.update()
    except Exception:
        pass


def safe_update_dialog(page: ft.Page, dlg: Optional[ft.Control] = None) -> None:
    """
    Safely updates only the dialog subtree (avoiding full-page serialization)
    when the dialog is mounted in `page._dialogs` or `page.overlay`.
    """
    if not page:
        return
    state = _get_page_state(page)
    target = dlg if dlg is not None else state.get("active_dlg")
    if target is not None:
        try:
            if _is_mounted(target):
                target.update()
                return
            dialogs_container = getattr(page, "_dialogs", None)
            if dialogs_container is not None and _identity_in(target, dialogs_container.controls):
                dialogs_container.update()
                return
        except Exception:
            pass
    try:
        page.update()
    except Exception:
        pass


def run_after_modal_close(
    page: ft.Page,
    dlg: Optional[ft.Control],
    callback: Callable,
    *args,
    delay: float = 0.05,
    **kwargs,
) -> None:
    """
    Closes `dlg` immediately via `safe_close_dialog(page, dlg)` and defers `callback`
    by `delay` seconds (1 animation frame) so Flutter pops the ModalRoute barrier
    cleanly before opening a secondary dialog or updating heavy view state.
    """
    import asyncio
    import inspect

    safe_close_dialog(page, dlg)

    async def _deferred():
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            res = callback(*args, **kwargs)
            if inspect.iscoroutine(res):
                await res
        except Exception as ex:
            print(f"[modal_guard] run_after_modal_close callback error: {ex}")

    if page and hasattr(page, "run_task"):
        try:
            page.run_task(_deferred)
            return
        except Exception:
            pass

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_deferred())
    except RuntimeError:
        try:
            res = callback(*args, **kwargs)
            if inspect.iscoroutine(res):
                res.close()
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


def debounced_click(callback: Callable, min_interval_ms: int = 350) -> Callable:
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

