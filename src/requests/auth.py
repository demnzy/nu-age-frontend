import httpx
import os
from dotenv import load_dotenv

load_dotenv()
api_url = os.getenv("API_URL")

async def login_request(email: str, password: str):
    limits = httpx.Timeout(5.0, read=10.0)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/users/auth/login", 

            data={'username': email, 'password': password} 
        )
        return response.status_code, response.json()
    
async def signup_request(email: str, username: str, password: str, first_name: str, last_name: str, gender: str, role: str, university: str | None = None, organisation: dict | None = None):
    
    payload = {
        "username": username,
        "email": email,
        "password": password,
        "first_name": first_name,
        "last_name": last_name,
        "gender": gender,
        "role": role,
        "university": university if university else None
    }

    if organisation is not None:
        payload["organisation"] = organisation

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{api_url}/users/auth/register", 
            json=payload 
        )
        return response.status_code, response.json()

async def get_current_user_request(token: str):

    url = f"{api_url}/users/me" 
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            return response.status_code, response.json()
    except Exception as e:
        print(f"Request Error: {e}")
        return 500, {"detail": "Connection failed"}
    
async def reset_request(token: str, payload: dict):
    payload = payload
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.patch(
            f"{api_url}/users/me/update", 
            json=payload, headers=headers
        )
        return response.status_code, response.json()

async def get_universities():
    url = "http://universities.hipolabs.com/search?country=Nigeria" 
    
    try:
        # Added a timeout so a slow network triggers the except block cleanly
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            
            # Ensure we don't accidentally try to parse an HTML error page as JSON
            response.raise_for_status() 
            
            return response.json()
            
    except Exception as e:
        print(f"Request Error: {e}")
        # THE FIX: Return a dictionary (or empty list) instead of a tuple!
        return {"error": "Connection failed"}
    
async def get_member_profile(token: str, identifier: str):
    """Fetches a specific user's public profile data."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{api_url}/users/one?identifier={identifier}", # Assuming your router prefix is /users
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json()