import flet as ft
from typing import Any, Optional


def get_session_store(page: Optional[ft.Page]) -> Any:
    """Safely retrieves the session store object without triggering
    RuntimeError: 'An attempt to fetch destroyed session' in Flet 0.86.5.
    Returns the session store, or an empty dict fallback if the session is destroyed or unavailable.
    """
    if page is None:
        return {}
    try:
        sess = getattr(page, "session", None)
        if sess is not None and hasattr(sess, "store"):
            return sess.store
    except (RuntimeError, AttributeError, Exception):
        pass
    return {}


def get_session_user(page: Optional[ft.Page]) -> dict:
    """Safely returns current_user from session store as a dictionary."""
    store = get_session_store(page)
    if hasattr(store, "get"):
        try:
            val = store.get("current_user")
            if isinstance(val, dict):
                return val
        except Exception:
            pass
    elif isinstance(store, dict):
        val = store.get("current_user")
        if isinstance(val, dict):
            return val
    return {}


def set_session_value(page: Optional[ft.Page], key: str, value: Any) -> bool:
    """Safely sets a key-value pair in session store."""
    store = get_session_store(page)
    if hasattr(store, "set"):
        try:
            store.set(key, value)
            return True
        except Exception:
            pass
    elif isinstance(store, dict):
        store[key] = value
        return True
    return False


def clear_session_store(page: Optional[ft.Page]) -> bool:
    """Safely clears the session store."""
    store = get_session_store(page)
    if hasattr(store, "clear"):
        try:
            store.clear()
            return True
        except Exception:
            pass
    elif isinstance(store, dict):
        store.clear()
        return True
    return False
