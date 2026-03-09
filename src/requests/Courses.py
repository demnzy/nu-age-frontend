import httpx
api_url = "http://localhost:8000"



async def get_courses(token:str):
    url = f"{api_url}/courses" 
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            return response.json()
    except Exception as e:
        print(f"Request Error: {e}")
        return 500, {"detail": "Connection failed"}