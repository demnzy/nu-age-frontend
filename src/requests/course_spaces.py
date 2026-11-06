"""
Course Spaces API Client for Nu-Age LMS.

Handles:
- Fetching user's Course Spaces & public Explore Spaces.
- Space creation and code-based / open joining.
- Asynchronous resource uploads (tied to courses/modules) and listings.
- Topic-aligned practice drills / quiz taking and scoring.
- Scheduled live sessions (Google Meet / Zoom).
"""

import httpx
from typing import Optional, Dict, Any, List
from src.requests.net import ssl_context

api_url = "https://api.nu-age.name.ng"
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=25.0, pool=5.0)


def _auth_headers(token: Optional[str] = None) -> dict:
    if token and str(token).strip() and str(token).strip() not in ("None", "null", "undefined"):
        return {"Authorization": f"Bearer {str(token).strip()}"}
    return {}


async def get_my_spaces(token: str, scope: str = "learner") -> dict:
    url = f"{api_url}/course-spaces/my-spaces"
    headers = _auth_headers(token)
    params = {"scope": scope}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers, params=params)
            if res.status_code == 200:
                return res.json()
            return {"status": "error", "message": res.text, "spaces": []}
    except Exception as e:
        print(f"get_my_spaces error: {e}")
        return {"status": "error", "message": str(e), "spaces": []}


async def get_explore_spaces(token: str, query: str = "", limit: int = 30, offset: int = 0) -> dict:
    url = f"{api_url}/course-spaces/explore"
    headers = _auth_headers(token)
    params = {"limit": limit, "offset": offset}
    if query:
        params["query"] = query
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers, params=params)
            if res.status_code == 200:
                return res.json()
            return {"status": "error", "message": res.text, "spaces": []}
    except Exception as e:
        print(f"get_explore_spaces error: {e}")
        return {"status": "error", "message": str(e), "spaces": []}


async def get_organisation_spaces(token: str, org_id: str) -> dict:
    url = f"{api_url}/course-spaces/organisation/{org_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"status": "error", "message": res.text, "spaces": []}
    except Exception as e:
        print(f"get_organisation_spaces error: {e}")
        return {"status": "error", "message": str(e), "spaces": []}


async def get_space_details(token: str, space_id: str) -> dict:
    if not space_id or str(space_id).strip() in ("", "None", "undefined"):
        return {"status": "error", "message": "Invalid space ID"}
    clean_id = str(space_id).split("?")[0].rstrip("/").replace("/manage", "").strip()
    url = f"{api_url}/course-spaces/{clean_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        err_msg = str(e) or type(e).__name__ or "Network request failed"
        print(f"get_space_details error: {type(e).__name__}: {e}")
        return {"status": "error", "message": err_msg}


async def create_course_space(token: str, payload: dict) -> dict:
    url = f"{api_url}/course-spaces"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code in (200, 201):
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"create_course_space error: {e}")
        return {"status": "error", "message": str(e)}


async def join_course_space(token: str, code: Optional[str] = None, space_id: Optional[str] = None) -> dict:
    url = f"{api_url}/course-spaces/join"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {}
    if code:
        payload["code"] = code.strip().upper()
    if space_id:
        payload["space_id"] = space_id
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"join_course_space error: {e}")
        return {"status": "error", "message": str(e)}


async def update_course_space(token: str, space_id: str, payload: dict) -> dict:
    url = f"{api_url}/course-spaces/{space_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.patch(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"update_course_space error: {e}")
        return {"status": "error", "message": str(e)}


async def delete_course_space(token: str, space_id: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"delete_course_space error: {e}")
        return {"status": "error", "message": str(e)}


async def regenerate_space_code(token: str, space_id: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/regenerate-code"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"regenerate_space_code error: {e}")
        return {"status": "error", "message": str(e)}


async def leave_course_space(token: str, space_id: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/leave"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"leave_course_space error: {e}")
        return {"status": "error", "message": str(e)}


async def add_courses_to_space(token: str, space_id: str, course_ids: List[str]) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/courses"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json={"course_ids": course_ids})
            if res.status_code in (200, 201):
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"add_courses_to_space error: {e}")
        return {"status": "error", "message": str(e)}


async def remove_course_from_space(token: str, space_id: str, course_id: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/courses/{course_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"remove_course_from_space error: {e}")
        return {"status": "error", "message": str(e)}


async def get_space_members(token: str, space_id: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/members"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"status": "error", "members": []}
    except Exception as e:
        print(f"get_space_members error: {e}")
        return {"status": "error", "members": []}


async def invite_space_members(token: str, space_id: str, user_identifiers: list, role: str = "student") -> dict:
    url = f"{api_url}/course-spaces/{space_id}/invite"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"user_identifiers": user_identifiers, "role": role}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code in (200, 201):
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"invite_space_members error: {e}")
        return {"status": "error", "message": str(e)}


async def update_space_member_role(token: str, space_id: str, member_user_id: str, role: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/members/{member_user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.patch(url, headers=headers, json={"role": role})
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"update_space_member_role error: {e}")
        return {"status": "error", "message": str(e)}


async def remove_space_member(token: str, space_id: str, member_user_id: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/members/{member_user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"remove_space_member error: {e}")
        return {"status": "error", "message": str(e)}


async def upload_space_material(
    token: str,
    space_id: str,
    file_bytes: bytes,
    filename: str,
    course_id: str,
    module_id: Optional[str] = None,
    title: str = "",
    description: Optional[str] = None
) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/materials"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "course_id": course_id,
        "title": title or filename,
    }
    if module_id:
        data["module_id"] = module_id
    if description:
        data["description"] = description

    files = {
        "file": (filename, file_bytes, "application/octet-stream")
    }

    try:
        upload_timeout = httpx.Timeout(connect=10.0, read=90.0, write=90.0, pool=5.0)
        async with httpx.AsyncClient(timeout=upload_timeout, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, data=data, files=files)
            if res.status_code in (200, 201):
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"upload_space_material error: {e}")
        return {"status": "error", "message": str(e)}


async def get_space_materials(token: str, space_id: str, course_id: Optional[str] = None, module_id: Optional[str] = None) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/materials"
    headers = {"Authorization": f"Bearer {token}"}
    params = {}
    if course_id:
        params["course_id"] = course_id
    if module_id:
        params["module_id"] = module_id
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers, params=params)
            if res.status_code == 200:
                return res.json()
            return {"status": "error", "materials": []}
    except Exception as e:
        print(f"get_space_materials error: {e}")
        return {"status": "error", "materials": []}


async def delete_space_material(token: str, space_id: str, material_id: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/materials/{material_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"delete_space_material error: {e}")
        return {"status": "error", "message": str(e)}


async def get_space_quizzes(token: str, space_id: str, course_id: Optional[str] = None, module_id: Optional[str] = None) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/quizzes"
    headers = {"Authorization": f"Bearer {token}"}
    params = {}
    if course_id:
        params["course_id"] = course_id
    if module_id:
        params["module_id"] = module_id
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers, params=params)
            if res.status_code == 200:
                return res.json()
            return {"status": "error", "quizzes": []}
    except Exception as e:
        print(f"get_space_quizzes error: {e}")
        return {"status": "error", "quizzes": []}


async def get_quiz_for_taking(token: str, space_id: str, quiz_id: str, include_answers: bool = False) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/quizzes/{quiz_id}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"include_answers": "true"} if include_answers else {}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers, params=params)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"get_quiz_for_taking error: {e}")
        return {"status": "error", "message": str(e)}


async def submit_quiz_attempt(token: str, space_id: str, quiz_id: str, answers: List[dict], duration_seconds: int = 0) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/quizzes/{quiz_id}/submit"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "answers": answers,
        "duration_seconds": duration_seconds
    }
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"submit_quiz_attempt error: {e}")
        return {"status": "error", "message": str(e)}


async def create_topic_quiz(token: str, space_id: str, payload: dict) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/quizzes"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code in (200, 201):
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"create_topic_quiz error: {e}")
        return {"status": "error", "message": str(e)}


async def update_space_quiz(token: str, space_id: str, quiz_id: str, payload: dict) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/quizzes/{quiz_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.put(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"update_space_quiz error: {e}")
        return {"status": "error", "message": str(e)}


async def delete_space_quiz(token: str, space_id: str, quiz_id: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/quizzes/{quiz_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"delete_space_quiz error: {e}")
        return {"status": "error", "message": str(e)}


async def get_space_quiz_attempts(token: str, space_id: str, quiz_id: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/quizzes/{quiz_id}/attempts"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"status": "error", "attempts": [], "summary": {}}
    except Exception as e:
        print(f"get_space_quiz_attempts error: {e}")
        return {"status": "error", "attempts": [], "summary": {}}


async def ai_parse_space_quiz_text(
    token: str,
    space_id: str,
    raw_text: str,
    subject: str = "General",
    exam_type: str = "Topic Drill CBT",
    exam_year: Optional[int] = None,
    mode: str = "auto",
    question_count: int = 10,
    difficulty: str = "standard",
) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/quizzes/ai-parse-text"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "raw_text": raw_text,
        "subject": subject,
        "exam_type": exam_type,
        "exam_year": exam_year,
        "mode": mode,
        "question_count": question_count,
        "difficulty": difficulty,
    }
    try:
        ai_timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)
        async with httpx.AsyncClient(timeout=ai_timeout, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail, "questions": []}
    except Exception as e:
        print(f"ai_parse_space_quiz_text error: {e}")
        return {"status": "error", "message": str(e), "questions": []}


async def ai_parse_space_quiz_file(
    token: str,
    space_id: str,
    file_bytes: bytes,
    filename: str,
    subject: str = "General",
    exam_type: str = "Topic Drill CBT",
    exam_year: Optional[str] = None,
    mode: str = "auto",
    question_count: int = 10,
    difficulty: str = "standard",
) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/quizzes/ai-parse-file"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "subject": subject,
        "exam_type": exam_type,
        "mode": mode,
        "question_count": str(question_count),
        "difficulty": difficulty,
    }
    if exam_year:
        data["exam_year"] = str(exam_year)
    files = {"file": (filename, file_bytes, "application/octet-stream")}
    try:
        ai_timeout = httpx.Timeout(connect=10.0, read=150.0, write=60.0, pool=5.0)
        async with httpx.AsyncClient(timeout=ai_timeout, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, data=data, files=files)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail, "questions": []}
    except Exception as e:
        print(f"ai_parse_space_quiz_file error: {e}")
        return {"status": "error", "message": str(e), "questions": []}


async def upload_space_quiz_image(token: str, space_id: str, file_bytes: bytes, filename: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/quizzes/upload-image"
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, file_bytes, "image/png")}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, files=files)
            if res.status_code in (200, 201):
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"upload_space_quiz_image error: {e}")
        return {"status": "error", "message": str(e)}


async def schedule_live_session(token: str, space_id: str, payload: dict) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/sessions"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code in (200, 201):
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"schedule_live_session error: {e}")
        return {"status": "error", "message": str(e)}


async def get_scheduled_sessions(token: str, space_id: str, course_id: Optional[str] = None, upcoming_only: bool = False) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/sessions"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"upcoming_only": upcoming_only}
    if course_id:
        params["course_id"] = course_id
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers, params=params)
            if res.status_code == 200:
                return res.json()
            return {"status": "error", "sessions": []}
    except Exception as e:
        print(f"get_scheduled_sessions error: {e}")
        return {"status": "error", "sessions": []}


async def cancel_scheduled_session(token: str, space_id: str, session_id: str) -> dict:
    url = f"{api_url}/course-spaces/{space_id}/sessions/{session_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.delete(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            return {"status": "error", "message": detail}
    except Exception as e:
        print(f"cancel_scheduled_session error: {e}")
        return {"status": "error", "message": str(e)}


async def get_upcoming_sessions(token: str) -> dict:
    """Fetch active and upcoming live classes across all spaces the learner belongs to."""
    url = f"{api_url}/course-spaces/upcoming-sessions"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"status": "error", "sessions": []}
    except Exception as e:
        print(f"get_upcoming_sessions error: {e}")
        return {"status": "error", "sessions": []}


