"""
src/services/ai_tutor_session.py

In-memory conversation history session manager for the Nu-AI Study Assistant.
Persists conversational turn history during course study sessions across drawer open/close,
lesson/module transitions, and tab switches.
"""

from typing import List, Dict, Any, Optional

_SESSION_HISTORIES: Dict[str, List[Dict[str, Any]]] = {}
_MATERIAL_HISTORIES: Dict[str, List[Dict[str, Any]]] = {}


def get_course_history(course_id: str) -> List[Dict[str, Any]]:
    """Retrieve existing conversation turns for a course in the active session."""
    cid = str(course_id or "default")
    if cid not in _SESSION_HISTORIES:
        _SESSION_HISTORIES[cid] = []
    return _SESSION_HISTORIES[cid]


def append_course_message(
    course_id: str,
    role: str,
    content: str,
    lesson_title: Optional[str] = None,
):
    """Append a user or assistant message to the course conversation history."""
    cid = str(course_id or "default")
    if cid not in _SESSION_HISTORIES:
        _SESSION_HISTORIES[cid] = []
    _SESSION_HISTORIES[cid].append({
        "role": role,
        "is_user": role == "user",
        "content": content,
        "lesson_title": lesson_title or "",
    })


def clear_course_history(course_id: str):
    """Reset the session conversation history for a specific course."""
    cid = str(course_id or "default")
    _SESSION_HISTORIES[cid] = []


async def get_material_tutor_history(page, material_id: str) -> List[Dict[str, Any]]:
    """Retrieve persistent conversation turns for an uploaded study material."""
    mid = str(material_id or "default").strip()
    if mid in _MATERIAL_HISTORIES and _MATERIAL_HISTORIES[mid]:
        return _MATERIAL_HISTORIES[mid]

    # Attempt to restore from client storage
    if page and hasattr(page, "client_storage"):
        try:
            stored = await page.client_storage.get(f"ai_tutor_chat_{mid}")
            if isinstance(stored, list):
                _MATERIAL_HISTORIES[mid] = stored
                return stored
        except Exception:
            pass

    _MATERIAL_HISTORIES.setdefault(mid, [])
    return _MATERIAL_HISTORIES[mid]


async def save_material_tutor_history(page, material_id: str, history: List[Dict[str, Any]]):
    """Persist conversation turns for a study material."""
    mid = str(material_id or "default").strip()
    clean_history = list(history or [])
    _MATERIAL_HISTORIES[mid] = clean_history

    if page and hasattr(page, "client_storage"):
        try:
            await page.client_storage.set(f"ai_tutor_chat_{mid}", clean_history)
        except Exception:
            pass


async def append_material_tutor_message(page, material_id: str, role: str, text: str):
    """Append a turn to the material's tutor history and commit to storage."""
    mid = str(material_id or "default").strip()
    if mid not in _MATERIAL_HISTORIES:
        _MATERIAL_HISTORIES[mid] = []
    _MATERIAL_HISTORIES[mid].append({"role": role, "text": text})

    if page and hasattr(page, "client_storage"):
        try:
            await page.client_storage.set(f"ai_tutor_chat_{mid}", _MATERIAL_HISTORIES[mid])
        except Exception:
            pass


async def clear_material_tutor_history(page, material_id: str):
    """Clear conversation history for a study material."""
    mid = str(material_id or "default").strip()
    _MATERIAL_HISTORIES[mid] = []
    if page and hasattr(page, "client_storage"):
        try:
            await page.client_storage.remove(f"ai_tutor_chat_{mid}")
        except Exception:
            pass
