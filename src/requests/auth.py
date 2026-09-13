import httpx
from src.requests.net import ssl_context
import json
api_url = "https://api.nu-age.name.ng"

async def login_request(email: str, password: str):
    # I bumped the timeout to 15 seconds. If the DB is waking up, 
    # giving it 5 extra seconds might just save the request.
    limits = httpx.Timeout(15.0) 
    
    try:
        async with httpx.AsyncClient(timeout=limits, verify=ssl_context) as client:
            response = await client.post(
                f"{api_url}/users/auth/login", 
                data={'username': email, 'password': password} 
            )
            
            # Scenario A: Perfect Login
            if response.status_code == 200:
                return response.status_code, response.json()
            
            # Scenario B: Wrong password, or a 502/504 Bad Gateway from Fly.io
            else:
                try:
                    # Attempt to parse it if FastAPI returned a clean 401 error
                    error_data = response.json()
                    return response.status_code, error_data
                except json.decoder.JSONDecodeError:
                    # The server threw an HTML error page (like a 502 Proxy Error)
                    return response.status_code, {"detail": "Server error or waking up. Please try again."}

    # Scenario C: The timeout elapsed before Fly.io or Neon could respond
    except httpx.ReadTimeout:
        return 504, {"detail": "The server is waking up. Please click login again."}
        
    # Scenario D: Catch-all for complete network failures (e.g., no internet)
    except httpx.RequestError as e:
        return 503, {"detail": f"Please Check you Internet Connection and Try again."}
    
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

    try:
        async with httpx.AsyncClient(timeout=15.0, verify=ssl_context) as client:  # bumped from 10s, matches login
            response = await client.post(
                f"{api_url}/users/auth/register", 
                json=payload 
            )
            try:
                return response.status_code, response.json()
            except json.decoder.JSONDecodeError:
                return response.status_code, {"detail": "Server error or waking up. Please try again."}

    except httpx.ReadTimeout:
        return 504, {"detail": "The server is waking up. Please try again."}

    except httpx.RequestError as e:
        return 503, {"detail": "Please check your internet connection and try again."}

async def get_current_user_request(token: str):

    url = f"{api_url}/users/me"
    headers = {"Authorization": f"Bearer {token}"}
    limits = httpx.Timeout(15.0)

    try:
        async with httpx.AsyncClient(timeout=limits, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)
            try:
                return response.status_code, response.json()
            except json.decoder.JSONDecodeError:
                return response.status_code, {"detail": "Server returned an unexpected response."}

    except httpx.ReadTimeout:
        return 504, {"detail": "The server is taking too long to respond. Please try again."}

    except httpx.RequestError as e:
        print(f"Request Error: {e!r}")
        return 503, {"detail": "Could not connect to the server. Check your internet connection."}

    except Exception as e:
        print(f"Unexpected Error: {e!r}")
        return 500, {"detail": "Something went wrong."}
    
async def reset_request(token: str, payload: dict):
    payload = payload
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=10.0, verify=ssl_context) as client:
        response = await client.patch(
            f"{api_url}/users/me/update", 
            json=payload, headers=headers
        )
        return response.status_code, response.json()

async def get_universities():
    url = "http://universities.hipolabs.com/search?country=Nigeria" 
    
    try:
        # Added a timeout so a slow network triggers the except block cleanly
        async with httpx.AsyncClient(timeout=10.0, verify=ssl_context) as client:
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
    try:
        async with httpx.AsyncClient(verify=ssl_context, timeout=10.0) as client:
            response = await client.get(
                f"{api_url}/users/one?identifier={identifier}",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                return response.json()
            return {"error": response.json().get("detail", "User not found")}
    except Exception as e:
        print(f"Request Error in get_member_profile: {e}")
        return {"error": "Connection failed"}

async def verify_email_request(email: str, code: str):
    # Adjust your base URL if it is different
    payload = {"email": email, "code": code}
    
    async with httpx.AsyncClient(verify=ssl_context) as client:
        try:
            response = await client.post(f"{api_url}/users/auth/verify-email", json=payload)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"detail": str(e)}
        
async def send_password_reset_otp(email: str):
    # Adjust your base URL if it is different
    
    
    async with httpx.AsyncClient(verify=ssl_context) as client:
        try:
            response = await client.post(f"{api_url}/users/auth/reset-password?email={email}")
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"detail": str(e)}
    
async def verify_password(email: str, new_password: str, otp: str):
    # Adjust your base URL if it is different
    payload = {"email": email, "new_password": new_password, "otp": otp}
    
    async with httpx.AsyncClient(verify=ssl_context) as client:
        try:
            response = await client.post(f"{api_url}/users/auth/verify-password?email={email}&otp={otp}&new_password={new_password}")
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"detail": str(e)}

async def refresh_access_token_request(refresh_token: str):
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{api_url}/users/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        return resp.status_code, resp.json()

async def logout_request(refresh_token: str):
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                f"{api_url}/users/auth/logout",
                json={"refresh_token": refresh_token},
            )
            return resp.status_code
        except httpx.RequestError:
            return None