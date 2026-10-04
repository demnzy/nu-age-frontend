import httpx
from typing import Optional, Dict, Any, List
from src.requests.net import ssl_context

api_url = "https://api.nu-age.name.ng"
DEFAULT_TIMEOUT = httpx.Timeout(15.0)


async def fetch_marketplace_packs(
    token: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    official_only: bool = False,
    free_only: bool = False,
    sort_by: str = "popular",
    page: int = 1,
    limit: int = 24,
) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/packs"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {
        "page": page,
        "limit": limit,
        "sort_by": sort_by,
        "official_only": "true" if official_only else "false",
        "free_only": "true" if free_only else "false",
    }
    if category and category.lower() not in ("all", ""):
        params["category"] = category
    if search and search.strip():
        params["search"] = search.strip()

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        return {"items": [], "total": 0, "error": "Server took too long to respond."}
    except httpx.HTTPStatusError as e:
        return {"items": [], "total": 0, "error": f"Failed with status {e.response.status_code}"}
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}


async def fetch_pack_detail(token: Optional[str], pack_id: str) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/packs/{pack_id}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        return {"error": "Server took too long to respond."}
    except httpx.HTTPStatusError as e:
        detail = "Failed to load pack details"
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"error": detail}
    except Exception as e:
        return {"error": str(e)}


async def submit_study_pack(
    token: str,
    material_id: str,
    title: str,
    description: str = "",
    category: str = "General",
    theme_gradient: str = "purple_indigo",
    price_coins: int = 0
) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/packs/submit"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "material_id": material_id,
        "title": title,
        "description": description,
        "category": category,
        "theme_gradient": theme_gradient,
        "price_coins": price_coins
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        detail = "Submission failed."
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"error": detail}
    except Exception as e:
        return {"error": str(e)}


async def download_study_pack(token: str, pack_id: str) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/packs/{pack_id}/download"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), verify=ssl_context) as client:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        detail = "Download failed."
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"error": detail, "status_code": e.response.status_code}
    except Exception as e:
        return {"error": str(e)}


async def toggle_like_pack(token: str, pack_id: str) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/packs/{pack_id}/like"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def fetch_my_submissions(token: str) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/my-submissions"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"items": [], "total_packs": 0, "total_coins_earned": 0, "error": str(e)}


async def fetch_admin_pending_submissions(token: str, page: int = 1, limit: int = 50) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/admin/submissions"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"page": page, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}


async def review_admin_submission(
    token: str,
    pack_id: str,
    action: str,
    reward_coins: int = 50,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    price_coins: Optional[int] = None,
    cover_image_url: Optional[str] = None,
    review_notes: str = "",
    is_official: bool = False
) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/admin/submissions/{pack_id}/review"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "action": action,
        "reward_coins": reward_coins,
        "review_notes": review_notes
    }
    if title:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if category:
        payload["category"] = category
    if price_coins is not None:
        payload["price_coins"] = price_coins
    if cover_image_url is not None:
        payload["cover_image_url"] = cover_image_url
    if is_official:
        payload["is_official"]= is_official

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def update_admin_pack(
    token: str,
    pack_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    price_coins: Optional[int] = None,
    cover_image_url: Optional[str] = None,
    is_official: Optional[bool] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/admin/packs/{pack_id}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {}
    if title: payload["title"] = title
    if description is not None: payload["description"] = description
    if category: payload["category"] = category
    if price_coins is not None: payload["price_coins"] = price_coins
    if cover_image_url is not None: payload["cover_image_url"] = cover_image_url
    if is_official is not None: payload["is_official"] = is_official
    if status: payload["status"] = status

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.patch(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}
