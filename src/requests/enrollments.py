import httpx
api_url = "http://localhost:8000"



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