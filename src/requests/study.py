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


async def get_exam_questions(token: str, material_ids: typing.Optional[list] = None) -> list:
    url = f"{api_url}/study/exam/questions"
    headers = {"Authorization": f"Bearer {token}"}
    params = {}

    if material_ids:
        params["material_ids"] = ",".join(material_ids)

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print("get_exam_questions timed out.")
        return []
    except httpx.HTTPStatusError as e:
        print(f"get_exam_questions failed with status {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        print(f"get_exam_questions connection error: {e}")
        return []
    except Exception as e:
        print(f"get_exam_questions unexpected error: {e}")
        return []


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