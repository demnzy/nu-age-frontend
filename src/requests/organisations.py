import json

import httpx
api_url = "https://nu-age.fly.dev"

async def create_organisation(token:str, payload): 
    url = f"{api_url}/organisations/create" 
    headers = {"Authorization": f"Bearer {token}"}
    payload = {**payload}
    try:
        async with httpx.AsyncClient() as client:
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
        return e
    
async def get_my_organisation(token:str): 
    url = f"{api_url}/organisations/me" 
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient() as client:
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
        return e

async def get_organisation_members(token:str, id: str, students: bool = False, teachers: bool = False): 
    url = f"{api_url}/organisations/members?id={id}&students={students}&teachers={teachers}" 
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient() as client:
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
        return e

async def get_organisation_courses(token:str, id: str): 
    url = f"{api_url}/organisations/courses?id={id}" 
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient() as client:
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
        return e
    
async def join_org(org_id: str, user_id: str): 
    url = f"{api_url}/organisations/{org_id}/join?user_id={user_id}"

    try:
        async with httpx.AsyncClient() as client:
            # THE FIX: Use client.post if sending a JSON body
            response = await client.post(url)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response}
    except Exception as e:
        print(f"Request Error: {e}")
        # THE FIX: Return a dict, NEVER the raw exception object!
        return {"error": str(e)}