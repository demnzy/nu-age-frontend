import httpx
from src.requests.net import ssl_context
import typing

api_url = "https://api.nu-age.name.ng"

# Default timeout for standard JSON requests (matches the 15s "server waking up"
# allowance used elsewhere in the app). Slow endpoints keep their own longer timeouts.
DEFAULT_TIMEOUT = httpx.Timeout(15.0)


async def get_due_cards(token: str, material_ids: typing.Optional[list] = None) -> list:
    url = f"{api_url}/study/cards/due"
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
    file_name: typing.Optional[str] = None
) -> dict:
    url = f"{api_url}/study/materials/upload"
    headers = {"Authorization": f"Bearer {token}"}

    # Form Data for FastAPI
    data = {"title": title}
    if text:
        data["pasted_text"] = text

    # Multipart File Data
    files = None
    if file_bytes and file_name:
        files = {"file": (file_name, file_bytes)}

    try:
        # Timeout extended for file uploads
        async with httpx.AsyncClient(timeout=30.0, verify=ssl_context) as client:
            if files:
                response = await client.post(url, headers=headers, data=data, files=files)
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