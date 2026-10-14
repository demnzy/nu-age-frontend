import httpx
from src.requests.net import ssl_context
from typing import Optional, List, Dict, Any

api_url = "https://api.nu-age.name.ng"
DEFAULT_TIMEOUT = httpx.Timeout(15.0)


_PARTNERSHIPS_CACHE: dict = {}


async def get_active_partnership(token: str) -> dict:
    url = f"{api_url}/study/partnerships/active"
    headers = {"Authorization": f"Bearer {token}"}
    cache_key = token[:16] if token else "anon"
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if not data or not isinstance(data, dict):
                data = {"has_partnership": False}
            if data.get("has_partnership"):
                _PARTNERSHIPS_CACHE[cache_key] = data
            return data
    except Exception as e:
        cached = _PARTNERSHIPS_CACHE.get(cache_key)
        if cached:
            return {**cached, "is_offline": True}
        return {"has_partnership": False, "is_offline": True, "error": str(e)}


async def get_partner_recommendations(token: str, limit: int = 10) -> list:
    url = f"{api_url}/study/partnerships/recommendations"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params={"limit": limit})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[get_partner_recommendations] error: {e}")
        return []


async def get_incoming_partnership_requests(token: str) -> list:
    url = f"{api_url}/study/partnerships/requests/incoming"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[get_incoming_partnership_requests] error: {e}")
        return []


async def get_sent_partnership_requests(token: str) -> list:
    url = f"{api_url}/study/partnerships/requests/sent"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[get_sent_partnership_requests] error: {e}")
        return []


async def invite_study_partner(
    token: str,
    target_user_id: str,
    goal_type: str = "mutual_accountability",
    target_exam: Optional[str] = None,
    target_subjects: Optional[List[str]] = None,
    daily_target_minutes: int = 45,
    daily_target_questions: int = 20
) -> dict:
    url = f"{api_url}/study/partnerships/invite/{target_user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "goal_type": goal_type,
        "target_exam": target_exam,
        "target_subjects": target_subjects or [],
        "daily_target_minutes": daily_target_minutes,
        "daily_target_questions": daily_target_questions,
    }
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        detail = "Failed to send invitation"
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"error": detail}
    except Exception as e:
        return {"error": str(e)}


async def accept_partnership_request(token: str, partnership_id: str) -> dict:
    url = f"{api_url}/study/partnerships/{partnership_id}/accept"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        detail = "Failed to accept partnership"
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"error": detail}
    except Exception as e:
        return {"error": str(e)}


async def decline_partnership_request(token: str, partnership_id: str) -> dict:
    url = f"{api_url}/study/partnerships/{partnership_id}/decline"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def delete_partnership(token: str, partnership_id: str) -> dict:
    url = f"{api_url}/study/partnerships/{partnership_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.delete(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def nudge_study_partner(token: str, partnership_id: str, message: Optional[str] = None) -> dict:
    url = f"{api_url}/study/partnerships/{partnership_id}/nudge"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"message": message} if message else {}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        detail = "Failed to nudge partner"
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"error": detail}
    except Exception as e:
        return {"error": str(e)}


async def log_partnership_activity(
    token: str,
    partnership_id: str,
    minutes_studied: int = 0,
    questions_solved: int = 0
) -> dict:
    url = f"{api_url}/study/partnerships/{partnership_id}/log-activity"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "minutes_studied": minutes_studied,
        "questions_solved": questions_solved
    }
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def create_partner_challenge(
    token: str,
    partnership_id: str,
    challenge_type: str,
    total_questions: int,
    question_snapshot: List[dict],
    challenger_score: int,
    challenger_time_seconds: int,
    challenger_breakdown: Optional[dict] = None
) -> dict:
    url = f"{api_url}/study/partnerships/{partnership_id}/challenges/create"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "challenge_type": challenge_type,
        "total_questions": total_questions,
        "question_snapshot": question_snapshot,
        "challenger_score": challenger_score,
        "challenger_time_seconds": challenger_time_seconds,
        "challenger_breakdown": challenger_breakdown or {},
    }
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        detail = "Failed to create duel challenge"
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"error": detail}
    except Exception as e:
        return {"error": str(e)}


async def get_partner_challenge(token: str, challenge_id: str) -> dict:
    url = f"{api_url}/study/partnerships/challenges/{challenge_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def submit_partner_challenge(
    token: str,
    challenge_id: str,
    challenged_score: int,
    challenged_time_seconds: int,
    challenged_breakdown: Optional[dict] = None
) -> dict:
    url = f"{api_url}/study/partnerships/challenges/{challenge_id}/submit"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "score": challenged_score,
        "time_seconds": challenged_time_seconds,
        "breakdown": challenged_breakdown or {},
        "challenged_score": challenged_score,
        "challenged_time_seconds": challenged_time_seconds,
        "challenged_breakdown": challenged_breakdown or {},
    }
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        detail = "Failed to submit challenge results"
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"error": detail}
    except Exception as e:
        return {"error": str(e)}


async def share_study_pack_api(token: str, partnership_id: str, pack_id: str) -> dict:
    url = f"{api_url}/study/partnerships/{partnership_id}/share-pack"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"pack_id": pack_id}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        detail = "Failed to share study pack"
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"error": detail}
    except Exception as e:
        return {"error": str(e)}


async def get_shared_study_packs_api(token: str, partnership_id: str) -> list:
    url = f"{api_url}/study/partnerships/{partnership_id}/shared-packs"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data.get("shared_packs", [])
    except Exception as e:
        print(f"[get_shared_study_packs_api] error: {e}")
        return []


async def accept_shared_study_pack_api(token: str, partnership_id: str, shared_id: str) -> dict:
    url = f"{api_url}/study/partnerships/{partnership_id}/shared-packs/{shared_id}/accept"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        detail = "Failed to accept study pack"
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"error": detail}
    except Exception as e:
        return {"error": str(e)}


async def generate_quickfire_from_pack_api(token: str, partnership_id: str, pack_id: str) -> dict:
    url = f"{api_url}/study/partnerships/{partnership_id}/challenges/quickfire-from-pack"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"pack_id": pack_id}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        detail = "Failed to generate quickfire duel from pack"
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"error": detail}
    except Exception as e:
        return {"error": str(e)}


async def get_study_leaderboard_api(token: str, filter_type: str = "today") -> list:
    url = f"{api_url}/study/partnerships/leaderboard"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params={"filter": filter_type})
            resp.raise_for_status()
            data = resp.json()
            return data.get("leaderboard", [])
    except Exception as e:
        print(f"[get_study_leaderboard_api] error: {e}")
        return []


async def log_partnership_study_activity_api(
    token: str,
    partnership_id: str,
    minutes_spent: int = 0,
    questions_completed: int = 0
) -> dict:
    url = f"{api_url}/study/partnerships/{partnership_id}/log-activity"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "minutes_spent": minutes_spent,
        "questions_completed": questions_completed,
    }
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[log_partnership_study_activity_api] error: {e}")
        return {"status": "error", "error": str(e)}


async def get_challenge_history_api(token: str, partnership_id: Optional[str] = None, limit: int = 20) -> list:
    if partnership_id:
        url = f"{api_url}/study/partnerships/{partnership_id}/challenges/history"
    else:
        url = f"{api_url}/study/partnerships/challenges/history"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params={"limit": limit})
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                return data.get("challenges", [])
            elif isinstance(data, list):
                return data
            return []
    except Exception as e:
        print(f"[get_challenge_history_api] error: {e}")
        return []


async def preview_shared_study_pack_api(token: str, partnership_id: str, pack_id: str) -> dict:
    url = f"{api_url}/study/partnerships/{partnership_id}/shared-packs/{pack_id}/preview"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                return {"error": "Preview not available on this server yet."}
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[preview_shared_study_pack_api] error: {e}")
        return {"error": str(e)}



