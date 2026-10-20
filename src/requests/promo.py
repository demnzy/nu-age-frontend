"""
src/requests/promo.py
──────────────────────────────────────────────────────────────────────────────
API Client for Promo Codes, Badges, and Campus Ambassadors.
──────────────────────────────────────────────────────────────────────────────
"""

import httpx
from typing import Tuple, Dict, Any, List, Optional
from src.requests.net import ssl_context

API_URL = "https://api.nu-age.name.ng"
TIMEOUT = httpx.Timeout(connect=4.0, read=15.0, write=15.0, pool=5.0)


# ─────────────────────────────────────────────────────────────────────────────
# 1. LEARNER PROMO & BADGE ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

async def redeem_promo_code_api(token: str, code: str) -> Tuple[int, Dict[str, Any]]:
    """
    Submits a promo code for redemption.
    Returns (status_code, response_dict).
    """
    url = f"{API_URL}/promo/redeem"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json={"code": code.strip()})
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] redeem_promo_code_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def get_my_badges_api(token: str) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Retrieves the learner's earned badges.
    """
    url = f"{API_URL}/promo/my-badges"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            try:
                data = res.json()
                if isinstance(data, dict) and "badges" in data:
                    return res.status_code, data["badges"]
                elif isinstance(data, list):
                    return res.status_code, data
                return res.status_code, []
            except Exception:
                return res.status_code, []
    except Exception as ex:
        print(f"[promo_api] get_my_badges_api error: {ex}")
        return 503, []


async def equip_primary_badge_api(token: str, badge_id: str) -> Tuple[int, Dict[str, Any]]:
    """
    Sets the selected badge as the learner's primary equipped badge.
    """
    url = f"{API_URL}/promo/my-badges/{badge_id}/equip"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.put(url, headers=headers)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] equip_primary_badge_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def accept_ambassador_invitation_api(token: str, invite_token: str) -> Tuple[int, Dict[str, Any]]:
    """
    Accepts an ambassador invitation using a secure token.
    """
    url = f"{API_URL}/promo/ambassador/accept"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json={"token": invite_token.strip()})
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] accept_ambassador_invitation_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


# ─────────────────────────────────────────────────────────────────────────────
# 2. SUPER ADMIN PROMO CODES ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

async def get_admin_promo_codes_api(token: str) -> Tuple[int, List[Dict[str, Any]]]:
    """Lists all promo codes for the Super Admin."""
    url = f"{API_URL}/platform-admin/promo-codes"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            try:
                data = res.json()
                if isinstance(data, dict) and "promo_codes" in data:
                    return res.status_code, data["promo_codes"]
                return res.status_code, []
            except Exception:
                return res.status_code, []
    except Exception as ex:
        print(f"[promo_api] get_admin_promo_codes_api error: {ex}")
        return 503, []


async def create_admin_promo_code_api(token: str, payload: dict) -> Tuple[int, Dict[str, Any]]:
    """Creates a promo code in Super Admin."""
    url = f"{API_URL}/platform-admin/promo-codes"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] create_admin_promo_code_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def toggle_admin_promo_code_api(token: str, code_id: str) -> Tuple[int, Dict[str, Any]]:
    """Toggles active state for a promo code."""
    url = f"{API_URL}/platform-admin/promo-codes/{code_id}/toggle-active"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.put(url, headers=headers)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] toggle_admin_promo_code_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def delete_admin_promo_code_api(token: str, code_id: str) -> Tuple[int, Dict[str, Any]]:
    """Deletes a promo code."""
    url = f"{API_URL}/platform-admin/promo-codes/{code_id}"
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
        print(f"[promo_api] delete_admin_promo_code_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


# ─────────────────────────────────────────────────────────────────────────────
# 3. SUPER ADMIN BADGES ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

async def get_admin_badges_api(token: str) -> Tuple[int, List[Dict[str, Any]]]:
    """Lists all registered system badges."""
    url = f"{API_URL}/platform-admin/badges"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            try:
                data = res.json()
                if isinstance(data, dict) and "badges" in data:
                    return res.status_code, data["badges"]
                return res.status_code, []
            except Exception:
                return res.status_code, []
    except Exception as ex:
        print(f"[promo_api] get_admin_badges_api error: {ex}")
        return 503, []


async def create_admin_badge_api(token: str, payload: dict) -> Tuple[int, Dict[str, Any]]:
    """Creates a custom badge."""
    url = f"{API_URL}/platform-admin/badges"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] create_admin_badge_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def update_admin_badge_api(token: str, badge_id: str, payload: dict) -> Tuple[int, Dict[str, Any]]:
    """Updates custom badge details."""
    url = f"{API_URL}/platform-admin/badges/{badge_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.put(url, headers=headers, json=payload)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] update_admin_badge_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def delete_admin_badge_api(token: str, badge_id: str) -> Tuple[int, Dict[str, Any]]:
    """Deletes a custom badge."""
    url = f"{API_URL}/platform-admin/badges/{badge_id}"
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
        print(f"[promo_api] delete_admin_badge_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def award_badge_to_user_api(token: str, user_id: str, badge_slug: str, is_primary: bool = False) -> Tuple[int, Dict[str, Any]]:
    """Awards a badge to a specific user account."""
    url = f"{API_URL}/platform-admin/users/{user_id}/award-badge"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json={"badge_slug": badge_slug, "is_primary": is_primary})
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] award_badge_to_user_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


# ─────────────────────────────────────────────────────────────────────────────
# 4. SUPER ADMIN CAMPUS AMBASSADORS ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

async def get_admin_ambassadors_api(token: str) -> Tuple[int, List[Dict[str, Any]]]:
    """Lists all campus ambassadors with statuses and metrics."""
    url = f"{API_URL}/platform-admin/ambassadors"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            try:
                data = res.json()
                if isinstance(data, dict) and "ambassadors" in data:
                    return res.status_code, data["ambassadors"]
                return res.status_code, []
            except Exception:
                return res.status_code, []
    except Exception as ex:
        print(f"[promo_api] get_admin_ambassadors_api error: {ex}")
        return 503, []


async def invite_admin_ambassador_api(token: str, payload: dict) -> Tuple[int, Dict[str, Any]]:
    """Dispatches a campus ambassador invitation email."""
    url = f"{API_URL}/platform-admin/ambassadors/invite"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] invite_admin_ambassador_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def update_admin_ambassador_status_api(token: str, ambassador_id: str, new_status: str) -> Tuple[int, Dict[str, Any]]:
    """Updates an ambassador's status."""
    url = f"{API_URL}/platform-admin/ambassadors/{ambassador_id}/status"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.put(url, headers=headers, json={"status": new_status})
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] update_admin_ambassador_status_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def get_admin_ambassador_applications_api(token: str, status_filter: Optional[str] = None) -> Tuple[int, List[Dict[str, Any]]]:
    """Lists submitted campus ambassador applications with platform user metrics."""
    url = f"{API_URL}/platform-admin/ambassadors/applications"
    params = {}
    if status_filter and status_filter != "all":
        params["status"] = status_filter
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers, params=params)
            try:
                data = res.json()
                if isinstance(data, dict) and "applications" in data:
                    return res.status_code, data["applications"]
                return res.status_code, []
            except Exception:
                return res.status_code, []
    except Exception as ex:
        print(f"[promo_api] get_admin_ambassador_applications_api error: {ex}")
        return 503, []


async def approve_ambassador_application_api(token: str, application_id: str) -> Tuple[int, Dict[str, Any]]:
    """Approves an ambassador application and triggers the invite email."""
    url = f"{API_URL}/platform-admin/ambassadors/applications/{application_id}/approve"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] approve_ambassador_application_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}


async def reject_ambassador_application_api(token: str, application_id: str) -> Tuple[int, Dict[str, Any]]:
    """Rejects an ambassador application."""
    url = f"{API_URL}/platform-admin/ambassadors/applications/{application_id}/reject"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers)
            try:
                data = res.json()
            except Exception:
                data = {"detail": res.text}
            return res.status_code, data
    except Exception as ex:
        print(f"[promo_api] reject_ambassador_application_api error: {ex}")
        return 503, {"detail": f"Connection error: {ex}"}

