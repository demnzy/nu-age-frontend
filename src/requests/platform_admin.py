import os
import json
import httpx
from typing import Optional, Tuple, Any, Dict, List
from src.requests.net import ssl_context

API_URL = os.getenv("API_URL", "https://api.nu-age.name.ng")
TIMEOUT = httpx.Timeout(connect=15.0, read=45.0, write=20.0, pool=10.0)


async def verify_admin_credentials(username: str, password: str) -> Tuple[int, Dict[str, Any]]:
    """
    Verifies super administrator credentials and returns an elevated token.
    """
    url = f"{API_URL}/platform-admin/auth/verify"
    payload = {"username": username.strip(), "password": password}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, json=payload)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text or "Unexpected response from server"}
            return res.status_code, data
    except Exception as ex:
        print(f"[platform_admin_api] verify_admin_credentials failed: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def get_platform_analytics(token: str) -> Tuple[int, Dict[str, Any]]:
    """
    Fetches global platform metrics (user counts, roles, active learners, orgs, courses).
    """
    url = f"{API_URL}/platform-admin/analytics"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[platform_admin_api] get_platform_analytics failed: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def get_platform_users(
    token: str,
    q: Optional[str] = None,
    role: Optional[str] = None,
    is_verified: Optional[bool] = None,
    page: int = 1,
    limit: int = 25,
    sort_by: str = "created_desc",
) -> Tuple[int, Dict[str, Any]]:
    """
    Returns a paginated list of users with search and filter controls.
    """
    url = f"{API_URL}/platform-admin/users"
    headers = {"Authorization": f"Bearer {token}"}
    params: Dict[str, Any] = {
        "page": page,
        "limit": limit,
        "sort_by": sort_by,
    }
    if q and q.strip():
        params["q"] = q.strip()
    if role and role.strip() and role.lower() != "all":
        params["role"] = role.strip()
    if is_verified is not None:
        params["is_verified"] = is_verified

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers, params=params)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[platform_admin_api] get_platform_users failed: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def get_user_details(token: str, user_id: str) -> Tuple[int, Dict[str, Any]]:
    """
    Retrieves full user profile and enrollment details.
    """
    url = f"{API_URL}/platform-admin/users/{user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[platform_admin_api] get_user_details failed: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def update_user_attributes(
    token: str,
    user_id: str,
    role: Optional[str] = None,
    is_verified: Optional[bool] = None,
    streak: Optional[int] = None,
    university: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    """
    Updates role, verification flag, streak, or university on a user account.
    """
    url = f"{API_URL}/platform-admin/users/{user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    payload: Dict[str, Any] = {}
    if role is not None:
        payload["role"] = role
    if is_verified is not None:
        payload["is_verified"] = is_verified
    if streak is not None:
        payload["streak"] = streak
    if university is not None:
        payload["university"] = university

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.patch(url, headers=headers, json=payload)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[platform_admin_api] update_user_attributes failed: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def delete_user_account(token: str, user_id: str) -> Tuple[int, Dict[str, Any]]:
    """
    Permanently deletes a user account with foreign key cascade cleanup.
    """
    url = f"{API_URL}/platform-admin/users/{user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[platform_admin_api] delete_user_account failed: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def export_users_data(
    token: str,
    format: str = "xlsx",
    role: Optional[str] = None,
) -> Tuple[int, bytes, str]:
    """
    Streams a formatted Excel (.xlsx) or CSV file of platform users.
    Returns (status_code, content_bytes, filename).
    """
    url = f"{API_URL}/platform-admin/users/export"
    headers = {"Authorization": f"Bearer {token}"}
    params: Dict[str, Any] = {"format": format}
    if role and role.strip() and role.lower() != "all":
        params["role"] = role.strip()

    filename = f"nu_age_users_export.{format}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=15.0, read=90.0, write=30.0, pool=10.0), verify=ssl_context) as client:
            res = await client.get(url, headers=headers, params=params)
            if res.status_code == 200:
                # Extract filename from header if present
                disp = res.headers.get("Content-Disposition", "")
                if "filename=" in disp:
                    filename = disp.split("filename=")[-1].strip('"\'')
                return 200, res.content, filename
            else:
                return res.status_code, b"", filename
    except Exception as ex:
        print(f"[platform_admin_api] export_users_data failed: {ex}")
        return 503, b"", filename


async def broadcast_bulk_email(
    token: str,
    audience: str,
    subject: str,
    body_html: str,
    sender_name: str = "Tobi from Nu Age",
) -> Tuple[int, Dict[str, Any]]:
    """
    Triggers a background bulk email blast via Resend.
    """
    url = f"{API_URL}/platform-admin/broadcast/email"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "audience": audience,
        "subject": subject,
        "body_html": body_html,
        "sender_name": sender_name,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[platform_admin_api] broadcast_bulk_email failed: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def broadcast_bulk_push(
    token: str,
    audience: str,
    title: str,
    body: str,
    action_route: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    """
    Triggers a push notification broadcast via Firebase Cloud Messaging.
    """
    url = f"{API_URL}/platform-admin/broadcast/push"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "audience": audience,
        "title": title,
        "body": body,
        "action_route": action_route,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[platform_admin_api] broadcast_bulk_push failed: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def get_platform_health(token: str) -> Tuple[int, Dict[str, Any]]:
    """
    Retrieves system and database latency health report.
    """
    url = f"{API_URL}/platform-admin/health"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[platform_admin_api] get_platform_health failed: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}
