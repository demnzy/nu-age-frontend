import httpx
import base64
from typing import Dict, Any, List

# Re-use the existing network functions or import the base URL
URL = "https://api.nu-age.name.ng"

async def create_playlist(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{URL}/playlists/"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 201:
                return response.json()
            else:
                return {"error": response.json().get("detail", "Error creating playlist")}
        except Exception as e:
            return {"error": str(e)}

async def get_all_playlists(token: str) -> List[Dict[str, Any]]:
    url = f"{URL}/playlists/"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except Exception as e:
            return []

async def get_org_playlists(token: str, org_id: str) -> List[Dict[str, Any]]:
    url = f"{URL}/playlists/orgs/{org_id}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except Exception as e:
            return []

async def get_playlist(token: str, playlist_id: str) -> Dict[str, Any]:
    url = f"{URL}/playlists/{playlist_id}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.json().get("detail", "Error fetching playlist")}
        except Exception as e:
            return {"error": str(e)}

async def update_playlist(token: str, playlist_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{URL}/playlists/{playlist_id}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.put(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.json().get("detail", "Error updating playlist")}
        except Exception as e:
            return {"error": str(e)}

async def add_courses_to_playlist(token: str, playlist_id: str, course_ids: List[str]) -> Dict[str, Any]:
    url = f"{URL}/playlists/{playlist_id}/courses"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"course_ids": course_ids}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 201:
                return response.json()
            else:
                return {"error": response.json().get("detail", "Error adding courses")}
        except Exception as e:
            return {"error": str(e)}

async def remove_course_from_playlist(token: str, playlist_id: str, course_id: str) -> Dict[str, Any]:
    url = f"{URL}/playlists/{playlist_id}/courses/{course_id}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.delete(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.json().get("detail", "Error removing course")}
        except Exception as e:
            return {"error": str(e)}

async def reorder_playlist_course(token: str, playlist_id: str, course_id: str, direction: str) -> Dict[str, Any]:
    url = f"{URL}/playlists/{playlist_id}/courses/reorder"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"course_id": course_id, "direction": direction}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.put(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.json().get("detail", "Error reordering course")}
        except Exception as e:
            return {"error": str(e)}

async def enroll_in_playlist(token: str, playlist_id: str) -> Dict[str, Any]:
    url = f"{URL}/playlists/{playlist_id}/enroll"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.json().get("detail", "Error enrolling in playlist")}
        except Exception as e:
            return {"error": str(e)}

async def get_playlist_analytics(token: str, playlist_id: str) -> List[Dict[str, Any]]:
    url = f"{URL}/playlists/{playlist_id}/analytics"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except Exception as e:
            return []

async def save_bulk_playlist_courses(token: str, playlist_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{URL}/playlists/{playlist_id}/courses/bulk"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.json().get("detail", "Error saving bulk courses")}
        except Exception as e:
            return {"error": str(e)}
