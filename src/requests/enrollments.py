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
    