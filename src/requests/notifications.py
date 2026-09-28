import httpx
from typing import Optional, Dict, Any, List
from src.requests.net import ssl_context

api_url = "https://api.nu-age.name.ng"
DEFAULT_TIMEOUT = httpx.Timeout(15.0)

async def get_user_notifications(token: str, skip: int = 0, limit: int = 50) -> Dict[str, Any]:
    """Fetches paginated user notifications from the backend."""
    url = f"{api_url}/notifications?skip={skip}&limit={limit}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return {"items": [], "total": 0, "unread_count": 0, "error": f"Status {resp.status_code}"}
    except Exception as e:
        return {"items": [], "total": 0, "unread_count": 0, "error": str(e)}

async def get_unread_notifications_count(token: str) -> int:
    """Fetches the lightweight total unread notifications count for badge rendering."""
    url = f"{api_url}/notifications/unread-count"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return int(data.get("unread_count", 0))
            return 0
    except Exception:
        return 0

async def mark_notification_read(token: str, notification_id: str) -> bool:
    """Marks a single persistent notification as read."""
    url = f"{api_url}/notifications/{notification_id}/read"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.put(url, headers=headers)
            return resp.status_code == 200
    except Exception:
        return False

async def mark_all_notifications_read(token: str) -> bool:
    """Marks all user persistent notifications as read."""
    url = f"{api_url}/notifications/read-all"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.put(url, headers=headers)
            return resp.status_code == 200
    except Exception:
        return False
