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


async def fetch_admin_all_packs(
    token: str,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50
) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/admin/packs"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"page": page, "limit": limit}
    if status:
        params["status"] = status
    if search:
        params["search"] = search

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}


async def toggle_admin_pack_visibility(token: str, pack_id: str) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/admin/packs/{pack_id}/toggle-visibility"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def delete_admin_pack(token: str, pack_id: str) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/admin/packs/{pack_id}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.delete(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def parse_past_questions_ai(
    token: str,
    raw_text: str,
    subject: str = "General",
    exam_type: str = "JAMB UTME",
    exam_year: Optional[int] = None
) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/admin/ai/parse-past-questions"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "raw_text": raw_text,
        "subject": subject,
        "exam_type": exam_type,
        "exam_year": exam_year
    }

    try:
        async with httpx.AsyncClient(timeout=300.0, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e), "success": False, "questions": []}


async def parse_past_questions_file_ai(
    token: str,
    file_name: str,
    file_bytes: bytes,
    subject: str = "General",
    exam_type: str = "JAMB UTME",
    exam_year: Optional[int] = None
) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/admin/ai/parse-past-questions-file"
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (file_name, file_bytes)}
    data = {
        "subject": subject,
        "exam_type": exam_type,
    }
    if exam_year is not None:
        data["exam_year"] = str(exam_year)

    try:
        async with httpx.AsyncClient(timeout=300.0, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, data=data, files=files)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e), "success": False, "questions": []}


async def upload_cbt_diagram_image_api(
    token: str,
    file_name: str,
    file_bytes: bytes,
) -> Dict[str, Any]:
    """Uploads CBT question figure / diagram directly to CDN."""
    url = f"{api_url}/study/marketplace/admin/cbt/upload-image"
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (file_name, file_bytes)}
    try:
        async with httpx.AsyncClient(timeout=180.0, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, files=files)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e), "success": False}


async def create_official_curated_pack(
    token: str,
    title: str,
    description: str,
    category: str,
    price_coins: int = 0,
    theme_gradient: str = "emerald_teal",
    cover_image_url: Optional[str] = None,
    flashcards: Optional[list] = None,
    questions: Optional[list] = None,
    duration_minutes: int = 60
) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/admin/packs/create-curated"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "title": title,
        "description": description,
        "category": category,
        "price_coins": price_coins,
        "theme_gradient": theme_gradient,
        "cover_image_url": cover_image_url,
        "flashcards": flashcards or [],
        "questions": questions or [],
        "duration_minutes": duration_minutes
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e), "success": False}


async def fetch_marketplace_bundles(token: Optional[str] = None, category: Optional[str] = None) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/bundles"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    params = {}
    if category and category != "All":
        params["category"] = category

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"bundles": [], "count": 0, "error": str(e)}


async def fetch_bundle_detail(bundle_id: str, token: Optional[str] = None) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/bundles/{bundle_id}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def download_study_bundle(token: str, bundle_id: str) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/bundles/{bundle_id}/download"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e), "success": False}


async def create_study_bundle_admin(
    token: str,
    title: str,
    description: str,
    category: str,
    pack_ids: list,
    price_coins: int = 0,
    discount_percentage: int = 0,
    theme_gradient: str = "purple_indigo",
    banner_url: Optional[str] = None
) -> Dict[str, Any]:
    url = f"{api_url}/study/marketplace/admin/bundles"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "title": title,
        "description": description,
        "category": category,
        "pack_ids": pack_ids,
        "price_coins": price_coins,
        "discount_percentage": discount_percentage,
        "theme_gradient": theme_gradient,
        "banner_url": banner_url
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e), "success": False}


async def fetch_admin_all_bundles(token: str) -> Dict[str, Any]:
    """Super Admin: Fetch all bundles (including hidden) with metrics."""
    url = f"{api_url}/study/marketplace/admin/bundles"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"bundles": [], "count": 0, "error": str(e)}


async def update_study_bundle_admin(
    token: str,
    bundle_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    pack_ids: Optional[list] = None,
    price_coins: Optional[int] = None,
    discount_percentage: Optional[int] = None,
    theme_gradient: Optional[str] = None,
    banner_url: Optional[str] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """Super Admin: Update an existing bundle's metadata, pricing, or constituent packs."""
    url = f"{api_url}/study/marketplace/admin/bundles/{bundle_id}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if category is not None:
        payload["category"] = category
    if pack_ids is not None:
        payload["pack_ids"] = pack_ids
    if price_coins is not None:
        payload["price_coins"] = price_coins
    if discount_percentage is not None:
        payload["discount_percentage"] = discount_percentage
    if theme_gradient is not None:
        payload["theme_gradient"] = theme_gradient
    if banner_url is not None:
        payload["banner_url"] = banner_url
    if status is not None:
        payload["status"] = status

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.put(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e), "success": False}


async def toggle_admin_bundle_visibility(token: str, bundle_id: str) -> Dict[str, Any]:
    """Super Admin: Toggle a bundle between approved (live) and hidden."""
    url = f"{api_url}/study/marketplace/admin/bundles/{bundle_id}/toggle-visibility"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.patch(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e), "success": False}


async def delete_admin_bundle(token: str, bundle_id: str) -> Dict[str, Any]:
    """Super Admin: Permanently delete a bundle."""
    url = f"{api_url}/study/marketplace/admin/bundles/{bundle_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.delete(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e), "success": False}


