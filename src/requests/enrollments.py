from uuid import UUID

import httpx
import os
from dotenv import load_dotenv
load_dotenv()
api_url = os.getenv("API_URL")



async def get_enrollments(token:str, params:dict| None): 
    url = f"{api_url}/courses/enrolled" 
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            if params:
                response= await client.get(url,headers=headers, params=params)
            elif not params:
                response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json() # Returns the list

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}

async def enrol_user(token:str, course_id, params:dict|None): 
    url = f"{api_url}/courses/{course_id}/enrol" 
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            if params:
                response= await client.post(url,headers=headers, params=params)
            elif not params:
                response = await client.post(url, headers=headers)
            if response.status_code == 200:
                return response.status_code,response.json()

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}

async def get_enrolled_students(token:str, course_id, params:dict|None): 
    url = f"{api_url}/courses/{course_id}/enrollments/org-students" 
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            if params:
                response= await client.get(url,headers=headers, params=params)
            elif not params:
                response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    
async def bulk_enrol_students(token:str, course_id, payload, params:dict|None): 
    url = f"{api_url}/courses/{course_id}/enrollments/bulk-enroll" 
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            if params:
                response= await client.post(url,headers=headers, params=params, json=payload)
            elif not params:
                response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    
async def bulk_unenrol_students(token:str, course_id,payload, params:dict|None): 
    url = f"{api_url}/courses/{course_id}/enrollments/bulk-unenroll" 
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            if params:
                response= await client.post(url,headers=headers, params=params, json=payload)
            elif not params:
                response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}



async def get_enrollment(token: str,course_id):
    """
    Gets an enrollment given course id
    """
    async with httpx.AsyncClient() as client:
        try:
            # Note: Adjust the "/enrollments/" prefix to match exactly where 
            # this router is mounted in your FastAPI main.py
            response = await client.get(
                f"{api_url}/courses/{course_id}/enrollment", 
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            # Catches the 404 (Not Found) or 400 (Not 100% complete) errors
            return {"error": e.response.json().get("detail", "Failed to fetch enrollment")}
        except Exception as e:
            return {"error": str(e)}
        

async def get_enrollment_stats(token: str, enrollment_id: str):
    # Force a 10-second timeout so it never hangs infinitely
    async with httpx.AsyncClient(timeout=10.0) as client: 
        try:
            response = await client.get(
                f"{api_url}/enrollments/{enrollment_id}/stats", 
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            # Fix a potential crash if the backend returns a 422 Validation Error (which is a list, not a dict)
            data = e.response.json()
            if isinstance(data, list): return {"error": str(data)}
            return {"error": data.get("detail", "Failed to fetch stats")}
        except Exception as e:
            return {"error": str(e)}