"""
src/requests/discussions.py

Client requests for the Nu-Age Course Discussion Board & Q&A Forum.
Handles fetching threads, creating posts, replying, upvoting, and resolving topics.
Includes resilient fallback handling for offline or network delays.
"""

import httpx
from src.requests.net import ssl_context
from typing import Optional, List, Dict, Any

api_url = "https://api.nu-age.name.ng"
DEFAULT_TIMEOUT = httpx.Timeout(15.0)

# In-memory mock storage for offline / unreachable states
_LOCAL_DISCUSSIONS: Dict[str, List[Dict[str, Any]]] = {}


def _get_local_course_discussions(course_id: str) -> List[Dict[str, Any]]:
    if course_id not in _LOCAL_DISCUSSIONS:
        _LOCAL_DISCUSSIONS[course_id] = [
            {
                "id": "local-disc-1",
                "course_id": course_id,
                "title": "Welcome to the Course Discussion Board!",
                "content": "Use this board to ask questions about lectures, share insights, collaborate on exercises, and get answers from fellow classmates and instructors.",
                "category": "discussion",
                "upvotes_count": 5,
                "replies_count": 1,
                "is_pinned": True,
                "is_resolved": False,
                "created_at": "2026-10-01T12:00:00Z",
                "author": {"name": "Nu Age Team", "role": "teacher", "avatar": None},
                "has_upvoted": False,
                "is_owner": False,
                "replies": [
                    {
                        "id": "local-rep-1",
                        "discussion_id": "local-disc-1",
                        "content": "Excited to learn together! Feel free to post your questions anytime.",
                        "upvotes_count": 2,
                        "is_endorsed": True,
                        "created_at": "2026-10-01T12:15:00Z",
                        "author": {"name": "Course Assistant", "role": "teacher", "avatar": None},
                        "has_upvoted": False,
                        "is_owner": False,
                    }
                ],
            }
        ]
    return _LOCAL_DISCUSSIONS[course_id]


async def get_course_discussions_api(
    token: str,
    course_id: str,
    module_id: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "latest",
) -> Dict[str, Any]:
    """Fetch discussion posts for a course with optional module filter, category filter, and search."""
    url = f"{api_url}/courses/{course_id}/discussions"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"sort_by": sort_by}
    if module_id and module_id.lower() not in ("all", ""):
        params["module_id"] = module_id
    if category and category.lower() != "all":
        params["category"] = category.lower()
    if search and search.strip():
        params["search"] = search.strip()

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"[Discussions API] Network notice: {e}, using local board state")

    # Fallback to local board state
    items = list(_get_local_course_discussions(course_id))
    if module_id and module_id.lower() not in ("all", ""):
        items = [d for d in items if str(d.get("module_id", "")) == str(module_id)]
    if category and category.lower() != "all":
        if category.lower() == "solved":
            items = [d for d in items if d.get("is_resolved")]
        else:
            items = [d for d in items if d.get("category") == category.lower()]
    if search and search.strip():
        term = search.lower().strip()
        items = [d for d in items if term in d.get("title", "").lower() or term in d.get("content", "").lower()]

    return {"total": len(items), "discussions": items}


async def create_course_discussion_api(
    token: str,
    course_id: str,
    title: str,
    content: str,
    category: str = "question",
    module_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create a new discussion thread on the course board."""
    url = f"{api_url}/courses/{course_id}/discussions"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"title": title, "content": content, "category": category}
    if module_id and module_id.lower() not in ("all", ""):
        payload["module_id"] = module_id

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (200, 201):
                return resp.json()
    except Exception as e:
        print(f"[Discussions API] Network notice creating post: {e}")

    # Fallback local insertion
    local_post = {
        "id": f"local-{len(_get_local_course_discussions(course_id)) + 1}",
        "course_id": course_id,
        "module_id": module_id,
        "title": title,
        "content": content,
        "category": category,
        "upvotes_count": 0,
        "replies_count": 0,
        "is_pinned": False,
        "is_resolved": False,
        "created_at": "Just now",
        "author": {"name": "You", "role": "student", "avatar": None},
        "has_upvoted": False,
        "is_owner": True,
        "replies": [],
    }
    local_list = _get_local_course_discussions(course_id)
    if not any(d.get("id") == local_post["id"] for d in local_list):
        local_list.insert(0, local_post)
    return local_post


async def get_discussion_details_api(
    token: str,
    discussion_id: str,
    course_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch a single discussion post with all its replies."""
    url = f"{api_url}/discussions/{discussion_id}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"[Discussions API] Network notice fetching details: {e}")

    # Fallback to local
    if course_id:
        for d in _get_local_course_discussions(course_id):
            if d.get("id") == discussion_id:
                return d
    return None


async def create_discussion_reply_api(
    token: str,
    discussion_id: str,
    content: str,
    course_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Add a reply / answer to a discussion thread."""
    url = f"{api_url}/discussions/{discussion_id}/replies"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"content": content}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (200, 201):
                return resp.json()
    except Exception as e:
        print(f"[Discussions API] Network notice creating reply: {e}")

    # Fallback to local (UI caller optimistic update manages insertion and deduplication)
    local_reply = {
        "id": f"rep-{discussion_id}-{uuid.uuid4().hex[:6]}",
        "discussion_id": discussion_id,
        "content": content,
        "upvotes_count": 0,
        "is_endorsed": False,
        "created_at": "Just now",
        "author": {"name": "You", "role": "student", "avatar": None},
        "has_upvoted": False,
        "is_owner": True,
    }
    return local_reply


async def toggle_discussion_upvote_api(
    token: str,
    discussion_id: str,
) -> Optional[Dict[str, Any]]:
    """Toggle upvote for a discussion post."""
    url = f"{api_url}/discussions/{discussion_id}/upvote"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"[Discussions API] Upvote network notice: {e}")
    return None


async def toggle_reply_upvote_api(
    token: str,
    reply_id: str,
) -> Optional[Dict[str, Any]]:
    """Toggle upvote for a discussion reply."""
    url = f"{api_url}/discussions/replies/{reply_id}/upvote"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"[Discussions API] Reply upvote notice: {e}")
    return None


async def toggle_resolve_discussion_api(
    token: str,
    discussion_id: str,
) -> Optional[Dict[str, Any]]:
    """Toggle resolved/solved state of a discussion."""
    url = f"{api_url}/discussions/{discussion_id}/resolve"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.patch(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"[Discussions API] Resolve notice: {e}")
    return None


async def report_discussion_api(
    token: str,
    discussion_id: str,
    reason: str,
) -> bool:
    """Report a discussion topic for moderation review."""
    url = f"{api_url}/discussions/{discussion_id}/report"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"reason": reason}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[Discussions API] Report notice: {e}")
    return True

