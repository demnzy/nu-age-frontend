import httpx
import typing
api_url = "https://api.nu-age.name.ng"

async def get_due_cards(token: str, material_ids: typing.Optional[list] = None) -> list:
    url = f"{api_url}/study/cards/due"
    headers = {"Authorization": f"Bearer {token}"}
    params = {}
    if material_ids:
        params["material_ids"] = ",".join(material_ids)
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

async def post_review(token: str, card_id: str, quality: int) -> dict:
    url = f"{api_url}/study/review"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"card_id": card_id, "quality": quality}
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

async def save_card(token: str, front: str, back: str, source_material_id: typing.Optional[str] = None) -> dict:
    url = f"{api_url}/study/cards/save"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "front": front,
        "back": back,
        "source_material_id": source_material_id
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

async def get_materials(token: str) -> list:
    url = f"{api_url}/study/materials"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

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

    # Timeout extended for file uploads
    async with httpx.AsyncClient(timeout=30.0) as client:
        if files:
            response = await client.post(url, headers=headers, data=data, files=files)
        else:
            response = await client.post(url, headers=headers, data=data)
        
        response.raise_for_status()
        return response.json()

async def get_quiz_questions(token: str, material_ids: typing.Optional[list] = None) -> list:
    url = f"{api_url}/study/quiz/questions"
    headers = {"Authorization": f"Bearer {token}"}
    params = {}
    
    if material_ids:
        # FastAPI expects a comma-separated string for the material_ids Optional[str]
        params["material_ids"] = ",".join(material_ids)
        
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

async def get_exam_questions(token: str, material_ids: typing.Optional[list] = None) -> list:
    url = f"{api_url}/study/exam/questions"
    headers = {"Authorization": f"Bearer {token}"}
    params = {}
    
    if material_ids:
        params["material_ids"] = ",".join(material_ids)
        
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

async def generate_from_materials(token: str, material_ids: list, types: list) -> dict:
    url = f"{api_url}/study/generate"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "material_ids": material_ids,
        "types": types
    }
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    
async def check_generation_status(token: str, material_id: str) -> dict:
    url = f"{api_url}/study/materials/{material_id}/status"
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json() # Expects {"status": "completed" | "processing"}