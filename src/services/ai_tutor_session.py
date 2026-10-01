"""
src/services/ai_tutor_session.py

In-memory conversation history session manager for the Nu-AI Study Assistant.
Persists conversational turn history during course study sessions across drawer open/close,
lesson/module transitions, and tab switches.
"""

from typing import List, Dict, Any, Optional

_SESSION_HISTORIES: Dict[str, List[Dict[str, Any]]] = {}


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
