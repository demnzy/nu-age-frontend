import httpx
from src.requests.net import ssl_context
import typing

api_url = "https://api.nu-age.name.ng"

# Default timeout for standard JSON requests (matches the 15s "server waking up"
# allowance used elsewhere in the app). Slow endpoints keep their own longer timeouts.
DEFAULT_TIMEOUT = httpx.Timeout(15.0)


async def get_due_cards(token: str, material_ids: typing.Optional[list] = None, all_cards: bool = False) -> list:
    url = f"{api_url}/study/cards/due"
    headers = {"Authorization": f"Bearer {token}"}
    params = {}
    if material_ids:
        params["material_ids"] = ",".join(material_ids)
    if all_cards:
        params["all_cards"] = "true"

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print("get_due_cards timed out.")
        return []
    except httpx.HTTPStatusError as e:
        print(f"get_due_cards failed with status {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        print(f"get_due_cards connection error: {e}")
        return []
    except Exception as e:
        print(f"get_due_cards unexpected error: {e}")
        return []


async def get_all_cards(token: str, material_ids: typing.Optional[list] = None) -> list:
    """Fetch all flashcards for a material (both due and scheduled/mastered)."""
    return await get_due_cards(token, material_ids=material_ids, all_cards=True)


async def post_review(token: str, card_id: str, quality: int) -> dict:
    url = f"{api_url}/study/review"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"card_id": card_id, "quality": quality}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "The server is taking too long to respond. Please try again."}
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed with status {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": "Please check your internet connection and try again."}
    except Exception as e:
        return {"error": str(e)}


async def save_card(token: str, front: str, back: str, source_material_id: typing.Optional[str] = None) -> dict:
    url = f"{api_url}/study/cards/save"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "front": front,
        "back": back,
        "source_material_id": source_material_id
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "The server is taking too long to respond. Please try again."}
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed with status {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": "Please check your internet connection and try again."}
    except Exception as e:
        return {"error": str(e)}


async def get_materials(token: str) -> list:
    url = f"{api_url}/study/materials"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print("get_materials timed out.")
        return []
    except httpx.HTTPStatusError as e:
        print(f"get_materials failed with status {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        print(f"get_materials connection error: {e}")
        return []
    except Exception as e:
        print(f"get_materials unexpected error: {e}")
        return []


async def upload_material(
    token: str,
    title: str,
    text: typing.Optional[str] = None,
    file_bytes: typing.Optional[bytes] = None,
    file_name: typing.Optional[str] = None,
    extra_files: typing.Optional[typing.List[typing.Tuple[str, bytes]]] = None,
) -> dict:
    url = f"{api_url}/study/materials/upload"
    headers = {"Authorization": f"Bearer {token}"}

    # Form Data for FastAPI
    data = {"title": title}
    if text:
        data["pasted_text"] = text

    # Multipart File Data (FastAPI accepts multiple 'files' fields)
    files_list = []
    if file_bytes and file_name:
        files_list.append(("files", (file_name, file_bytes)))
    if extra_files:
        for fname, fbytes in extra_files:
            files_list.append(("files", (fname, fbytes)))

    try:
        # Timeout extended for file / vision uploads
        async with httpx.AsyncClient(timeout=60.0, verify=ssl_context) as client:
            if files_list:
                response = await client.post(url, headers=headers, data=data, files=files_list)
            else:
                response = await client.post(url, headers=headers, data=data)

            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "The upload timed out. Please check your connection and try again."}
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed with status {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": "Please check your internet connection and try again."}
    except Exception as e:
        return {"error": str(e)}


async def get_quiz_questions(token: str, material_ids: typing.Optional[list] = None) -> list:
    url = f"{api_url}/study/quiz/questions"
    headers = {"Authorization": f"Bearer {token}"}
    params = {}

    if material_ids:
        # FastAPI expects a comma-separated string for the material_ids Optional[str]
        params["material_ids"] = ",".join(material_ids)

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print("get_quiz_questions timed out.")
        return []
    except httpx.HTTPStatusError as e:
        print(f"get_quiz_questions failed with status {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        print(f"get_quiz_questions connection error: {e}")
        return []
    except Exception as e:
        print(f"get_quiz_questions unexpected error: {e}")
        return []


async def get_exam_categories(token: str, material_ids: typing.Optional[list] = None) -> dict:
    url = f"{api_url}/study/exam/categories"
    headers = {"Authorization": f"Bearer {token}"}
    params = {}
    if material_ids:
        params["material_ids"] = ",".join(str(mid) for mid in material_ids if mid)
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"get_exam_categories error: {e}")
        return {"total_questions": 0, "exam_type": None, "categories": []}


async def get_exam_questions(
    token: str,
    material_ids: typing.Optional[list] = None,
    limit: typing.Optional[int] = None,
    topics: typing.Optional[list] = None,
    duration_seconds: typing.Optional[int] = None
) -> dict:
    url = f"{api_url}/study/exam/questions"
    headers = {"Authorization": f"Bearer {token}"}
    params = {}

    if material_ids:
        params["material_ids"] = ",".join(str(mid) for mid in material_ids if mid)
    if limit is not None:
        params["limit"] = str(limit)
    if topics:
        params["topics"] = ",".join(str(t) for t in topics if t)
    if duration_seconds is not None:
        params["duration_seconds"] = str(duration_seconds)

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print("get_exam_questions timed out.")
        return {"questions": [], "duration_seconds": 300}
    except httpx.HTTPStatusError as e:
        print(f"get_exam_questions failed with status {e.response.status_code}")
        return {"questions": [], "duration_seconds": 300}
    except httpx.RequestError as e:
        print(f"get_exam_questions connection error: {e}")
        return {"questions": [], "duration_seconds": 300}
    except Exception as e:
        print(f"get_exam_questions unexpected error: {e}")
        return {"questions": [], "duration_seconds": 300}


async def generate_from_materials(token: str, material_ids: list, types: list) -> dict:
    url = f"{api_url}/study/generate"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "material_ids": material_ids,
        "types": types
    }

    try:
        async with httpx.AsyncClient(timeout=45.0, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "Generation is taking too long. Please try again."}
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed with status {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": "Please check your internet connection and try again."}
    except Exception as e:
        return {"error": str(e)}


async def check_generation_status(token: str, material_id: str) -> dict:
    url = f"{api_url}/study/materials/{material_id}/status"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()  # Expects {"status": "completed" | "processing"}
    except httpx.TimeoutException:
        return {"error": "The server is taking too long to respond. Please try again."}
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed with status {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": "Please check your internet connection and try again."}
    except Exception as e:
        return {"error": str(e)}


async def check_journal_generation_status_api(token: str, journal_id: str) -> dict:
    url = f"{api_url}/study/journals/{journal_id}/status"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "The server is taking too long to respond. Please try again."}
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed with status {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": "Please check your internet connection and try again."}
    except Exception as e:
        return {"error": str(e)}


async def import_youtube_material(
    token: str,
    youtube_url: str,
    title: typing.Optional[str] = None
) -> dict:
    """Imports an educational YouTube video into study materials."""
    url = f"{api_url}/study/materials/youtube"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"url": youtube_url, "title": title}

    try:
        async with httpx.AsyncClient(timeout=45.0, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code in (200, 201):
                return response.json()
            elif response.status_code in (404, 501):
                # Remote endpoint not deployed yet; perform resilient client-assisted fallback
                pass
            else:
                try:
                    err_json = response.json()
                    return {"error": err_json.get("detail", f"Import failed with status {response.status_code}")}
                except Exception:
                    return {"error": f"Import failed with status {response.status_code}"}
    except Exception as e:
        print(f"[STUDY] Direct YouTube endpoint unreachable ({e}), attempting resilient fallback...")

    # Resilient Fallback: synthesize notes via ask_ai_tutor_api and save as material
    try:
        from src.requests.chats import ask_ai_tutor_api
        clean_title = title or "YouTube Study Lesson"
        synthesis_prompt = (
            f"You are an expert educational study coach. Create structured, comprehensive study notes for this YouTube video:\n"
            f"Link: {youtube_url}\n"
            f"Topic/Title: {clean_title}\n\n"
            f"Generate study notes formatted in Markdown with:\n"
            f"1. Core Conceptual Overview\n"
            f"2. Key Terminology & Definitions\n"
            f"3. 3-5 Foundational Takeaways\n"
            f"4. Practice & Self-Check Questions with Brief Answers"
        )
        ai_resp = await ask_ai_tutor_api(
            token=token,
            course_id="self-study-youtube",
            message=synthesis_prompt,
            context={"mode": "youtube_synthesis", "url": youtube_url}
        )
        study_text = ai_resp.get("response") or ai_resp.get("answer") or f"# {clean_title}\n\nNotes from {youtube_url}"
        
        # Save via standard material upload
        return await upload_material(token=token, title=clean_title, text=study_text)
    except Exception as fallback_err:
        return {"error": f"Could not process YouTube video: {fallback_err}"}


async def get_youtube_recommendations(token: str, query: str) -> list:
    """Retrieves relevant YouTube tutorial recommendations for a query."""
    url = f"{api_url}/study/youtube/recommendations"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"query": query}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"[STUDY] Recommendations endpoint error: {e}")

    # Fallback to search query link
    import urllib.parse
    encoded = urllib.parse.quote(f"{query} tutorial")
    return [{
        "video_id": "",
        "url": f"https://www.youtube.com/results?search_query={encoded}",
        "title": f"Search YouTube: {query} tutorials",
        "channel": "YouTube Search",
        "thumbnail": ""
    }]


async def delete_study_material(token: str, material_id: str) -> dict:
    """Deletes a study material from the user's vault."""
    url = f"{api_url}/study/materials/{material_id}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=15.0, verify=ssl_context) as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code in (200, 204):
                try:
                    return resp.json()
                except Exception:
                    return {"success": True}
            elif resp.status_code == 404:
                return {"error": "Material not found in vault."}
            else:
                try:
                    err = resp.json()
                    return {"error": err.get("detail", f"Failed with status {resp.status_code}")}
                except Exception:
                    return {"error": f"Failed with status {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def log_study_session_api(token: str, minutes_spent: int, questions_completed: int = 0) -> dict:
    """Logs study session time and completed questions, triggering backend milestone objectives."""
    url = f"{api_url}/study/log-session"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "minutes_spent": int(minutes_spent),
        "questions_completed": int(questions_completed),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json()
            return {"status": "error", "code": resp.status_code}
    except Exception as e:
        print(f"[log_study_session_api] error: {e}")
        return {"status": "error", "message": str(e)}


# ==========================================
# COURSE NOTEBOOKS / JOURNALS API
# ==========================================

async def get_journals_api(token: str) -> list:
    """Fetches all Course Journals for the current user."""
    url = f"{api_url}/study/journals"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return []
    except Exception as e:
        print(f"[get_journals_api] error: {e}")
        return []


async def create_journal_api(
    token: str,
    title: str,
    description: str = "",
    color: str = "teal",
    icon: str = "book",
    material_ids: list = None
) -> dict:
    """Creates a new Course Journal with optional existing vault material IDs."""
    url = f"{api_url}/study/journals"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "title": title.strip(),
        "description": description.strip() if description else None,
        "color": color,
        "icon": icon,
        "material_ids": material_ids or [],
    }
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (200, 201):
                return resp.json()
            try:
                err = resp.json()
                return {"error": err.get("detail", f"Error {resp.status_code}")}
            except Exception:
                return {"error": f"Error {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def create_multi_journal_api(
    token: str,
    title: str,
    description: str = "",
    color: str = "teal",
    icon: str = "book",
    pasted_texts: list = None,
    pasted_titles: list = None,
    files_payload: list = None,
    auto_generate: bool = True,
    generate_types: list = None,
) -> dict:
    """
    Creates a new Course Journal with up to 5 source materials.
    Consumes 3 upload slots and 3 generation credits.
    """
    url = f"{api_url}/study/journals/create-multi"
    headers = {"Authorization": f"Bearer {token}"}

    data = {
        "title": title.strip(),
        "description": description.strip() if description else "",
        "color": color,
        "icon": icon,
        "auto_generate": "true" if auto_generate else "false",
    }
    if generate_types:
        for t in generate_types:
            data.setdefault("generate_types", []).append(t)

    outgoing_files = []
    if files_payload:
        for item in files_payload:
            # item is a dict with "name", "bytes", "mime_type"
            fname = item.get("name", "document.pdf")
            fbytes = item.get("bytes", b"")
            fmime = item.get("mime_type", "application/pdf")
            outgoing_files.append(("files", (fname, fbytes, fmime)))

    if pasted_texts:
        for txt in pasted_texts:
            if txt and txt.strip():
                data.setdefault("pasted_texts", []).append(txt.strip())
    if pasted_titles:
        for pt in pasted_titles:
            data.setdefault("pasted_titles", []).append((pt or "").strip())

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0), verify=ssl_context) as client:
            resp = await client.post(
                url,
                headers=headers,
                data=data,
                files=outgoing_files if outgoing_files else None
            )
            if resp.status_code in (200, 201):
                return resp.json()
            try:
                err = resp.json()
                detail = err.get("detail")
                if isinstance(detail, dict):
                    return {"error": detail.get("message", "Quota error"), "details": detail, "code": resp.status_code}
                return {"error": str(detail or f"Error {resp.status_code}"), "code": resp.status_code}
            except Exception:
                return {"error": f"Error {resp.status_code}", "code": resp.status_code}
    except Exception as e:
        return {"error": str(e)}


async def get_journal_details_api(token: str, journal_id: str) -> dict:
    """Fetches details of a specific Course Journal including constituent modules."""
    url = f"{api_url}/study/journals/{journal_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Error {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def update_journal_api(token: str, journal_id: str, payload: dict) -> dict:
    """Updates journal metadata (title, description, color, icon)."""
    url = f"{api_url}/study/journals/{journal_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.patch(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Error {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def delete_journal_api(token: str, journal_id: str) -> dict:
    """Deletes a journal while safely retaining materials in vault."""
    url = f"{api_url}/study/journals/{journal_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Error {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def add_materials_to_journal_api(token: str, journal_id: str, material_ids: list) -> dict:
    """Attaches existing vault materials into a journal (capped at 5 total)."""
    url = f"{api_url}/study/journals/{journal_id}/materials"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"material_ids": material_ids}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json()
            try:
                err = resp.json()
                return {"error": err.get("detail", f"Error {resp.status_code}")}
            except Exception:
                return {"error": f"Error {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def remove_material_from_journal_api(token: str, journal_id: str, material_id: str) -> dict:
    """Unlinks a material from a journal without deleting it from the vault."""
    url = f"{api_url}/study/journals/{journal_id}/materials/{material_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Error {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def generate_journal_content_api(token: str, journal_id: str, types: list = None, replace_existing: bool = False) -> dict:
    """Triggers AI generation for the journal (3x credits cost)."""
    url = f"{api_url}/study/journals/{journal_id}/generate"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "types": types or ["exam", "study_guide"],
        "replace_existing": bool(replace_existing)
    }
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (200, 201):
                return resp.json()
            try:
                err = resp.json()
                detail = err.get("detail")
                if isinstance(detail, dict):
                    return {"error": detail.get("message", "Quota error"), "details": detail, "code": resp.status_code}
                return {"error": str(detail or f"Error {resp.status_code}"), "code": resp.status_code}
            except Exception:
                return {"error": f"Error {resp.status_code}", "code": resp.status_code}
    except Exception as e:
        return {"error": str(e)}


async def get_ai_tutor_quota_api(token: str) -> dict:
    """Fetches real-time daily AI tutor quota for the current student."""
    url = f"{api_url}/study/ai-tutor/quota"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"[get_ai_tutor_quota_api] error fetching quota endpoint: {e}")

    # Fallback to subscription status to avoid downgrading paid subscribers on transient errors
    try:
        from src.requests.subscription import get_subscription_status
        sub = await get_subscription_status(token)
        if isinstance(sub, dict) and not sub.get("error"):
            plan_id = sub.get("plan_id", "free")
            status = sub.get("status", "active")
            if plan_id != "free" and status in ("active", "grace_period"):
                return {
                    "plan": plan_id,
                    "plan_name": sub.get("label", "Pro Scholar"),
                    "is_unlimited": True,
                    "limit": -1,
                    "used": 0,
                    "remaining": -1,
                    "locked": False,
                    "reset_at": "00:00 UTC",
                }
    except Exception as sub_err:
        print(f"[get_ai_tutor_quota_api] subscription status fallback error: {sub_err}")

    return {"plan": "free", "plan_name": "Free Tier", "is_unlimited": False, "limit": 15, "used": 0, "remaining": 15, "locked": False, "reset_at": "00:00 UTC"}


async def ask_journal_tutor_api(
    token: str,
    journal_id: str,
    query: str,
    conversation_history: list = None
) -> dict:
    """Grounded AI tutor answering queries across the entire journal."""
    url = f"{api_url}/study/journals/{journal_id}/ai-tutor"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "query": query,
        "conversation_history": conversation_history or []
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0), verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 403:
                try:
                    err_json = resp.json()
                    detail = err_json.get("detail", "Free daily AI tutor limit reached (15/15). Upgrade to Pro Scholar for unlimited access.")
                except Exception:
                    detail = "Free daily AI tutor limit reached (15/15). Upgrade to Pro Scholar for unlimited access."
                return {"error": detail, "quota_locked": True, "status_code": 403}
            try:
                err_json = resp.json()
                detail = err_json.get("detail")
            except Exception:
                detail = None
            msg = detail or "I ran into a brief hiccup synthesizing your journal notes right now. Please try asking again in a few moments."
            return {"error": msg, "is_ai_error": True, "status_code": resp.status_code}
    except httpx.TimeoutException:
        return {"error": "Synthesizing across journal modules took longer than expected. Please try asking again.", "is_ai_error": True, "is_timeout": True}
    except Exception as e:
        print(f"[ask_journal_tutor_api] network exception: {e}")
        return {"error": "I'm having trouble connecting to the study server. Please verify your internet connection.", "is_ai_error": True}


async def get_journal_due_cards_api(token: str, journal_id: str) -> list:
    """Fetches flashcards for this journal."""
    url = f"{api_url}/study/journals/{journal_id}/due-cards"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return []
    except Exception as e:
        print(f"[get_journal_due_cards_api] error: {e}")
        return []


async def get_journal_questions_api(token: str, journal_id: str, limit: int = 15) -> list:
    """Fetches quiz/exam questions for this journal."""
    url = f"{api_url}/study/journals/{journal_id}/questions"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": limit}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                return resp.json()
            return []
    except Exception as e:
        print(f"[get_journal_questions_api] error: {e}")
        return []


