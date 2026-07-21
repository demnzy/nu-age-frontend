import httpx
api_url = "https://api.nu-age.name.ng"



async def get_courses(token:str, params:dict| None): 
    url = f"{api_url}/courses" 
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            if params:
                response= await client.get(url,headers=headers, params=params)
            elif not params:
                response = await client.get(url, headers=headers)
            if response.status_code == 200:
                print("Courses fetched successfully") 
                return response.json() # Returns the list

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}

async def create_course(token:str, payload): 
    url = f"{api_url}/courses/create" 
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
    
async def get_categories(token:str, params:dict| None): 
    url = f"{api_url}/categories" 
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            if params:
                response= await client.get(url,headers=headers, params=params)
            elif not params:
                response = await client.get(url, headers=headers)
            if response.status_code == 200:
                print("Categories fetched successfully") 
                return response.json() # Returns the list

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    
async def upload_video_background(token: str, file_name: str, file_bytes: bytes): 
    """
    Uploads raw video bytes to Bunny Stream via the FastAPI backend.
    Returns a dict containing the generated {"url": "https://iframe..."}
    """
    url = f"{api_url}/media/upload/video" 
    headers = {"Authorization": f"Bearer {token}"}
    
    # Package the raw binary into a multipart file envelope
    multipart_files = {
        "file": (file_name, file_bytes, "video/mp4")
    }
    
    try:
        # 300-second timeout handles large video files without crashing
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(url, headers=headers, files=multipart_files)
            
            if response.status_code == 200:
                print(f"Video uploaded successfully: {file_name}") 
                return response.json() 

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                print(f"Video upload failed: {response.text}")
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}


async def upload_asset_background(token: str, course_id: str, asset_type: str, file_name: str, file_bytes: bytes): 
    """
    Uploads audio or documents to Private Edge Storage.
    asset_type should be 'audio' or 'document'.
    Returns a dict containing the {"path": "/courses/..."}
    """
    url = f"{api_url}/media/upload/private-asset" 
    headers = {"Authorization": f"Bearer {token}"}
    
    # Text data goes in 'data'
    form_data = {
        "course_id": str(course_id),
        "type": asset_type
    }
    
    # Determine basic mime type
    mime_type = "audio/mpeg" if asset_type == "audio" else "application/pdf"
    
    # File goes in 'files'
    multipart_files = {
        "file": (file_name, file_bytes, mime_type)
    }
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # httpx automatically combines form_data and multipart_files
            response = await client.post(url, headers=headers, data=form_data, files=multipart_files)
            
            if response.status_code == 200:
                print(f"{asset_type.capitalize()} uploaded successfully: {file_name}") 
                return response.json() 

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                print(f"Asset upload failed: {response.text}")
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}


async def save_bulk_curriculum(token: str, course_id: str, payload: dict): 
    """
    The final bulk publish! Sends the fully constructed JSON dictionary 
    (with media URLs already injected) to the database.
    """
    url = f"{api_url}/courses/{course_id}/curriculum/bulk" 
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Standard timeout is fine here since it's just pure JSON text!
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                print("Curriculum published successfully!") 
                return response.json() 

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                print(f"Curriculum publish failed: {response.text}")
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    
async def get_course_curriculum(token: str, course_id: str):
    """
    Fetches the full nested curriculum structure for a specific course.
    """
    url = f"{api_url}/courses/{course_id}/curriculum" 
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                print(f"Curriculum for course {course_id} fetched successfully")
                return response.json() # This will be your nested JSON object
            
            elif response.status_code == 404:
                print("Curriculum not found.")
                return {"error": "not_found"}
            
            elif response.status_code == 401:
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail", "details": response.text}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "connection_failed"}
    
async def update_course_settings(token: str, course_id: str, setting: dict):
    """
    Updates the settings for a specific course.
    """
    url = f"{api_url}/courses/{course_id}/update_settings"  
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=setting)
            
            if response.status_code == 200:
                print(f"Settings for course {course_id} updated successfully")
                return response.json() # This will be your updated course object
            
            elif response.status_code == 404:
                print("Course not found.")
                return {"error": "not_found"}
            
            elif response.status_code == 401:
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail", "details": response.text}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "connection_failed"}
    
async def delete_course(token: str, course_id: str):
    """
    Deletes a specific course.
    """
    url = f"{api_url}/courses/{course_id}/delete"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=headers)

            if response.status_code == 200:
                print(f"Course {course_id} deleted successfully")
                return {"message": "Course deleted successfully"}
            
            elif response.status_code == 404:
                print("Course not found.")
                return {"error": "not_found"}
            
            elif response.status_code == 401:
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail", "details": response.text}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "connection_failed"}
    

async def mark_complete(token: str, course_id: str, lesson_id: str):
    """
    Marks a lesson as complete.
    """
    url = f"{api_url}/courses/{course_id}/lessons/{lesson_id}/complete"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers)

            if response.status_code == 200:
                print(f"Lesson {lesson_id} marked as complete for course {course_id}")
                return {"message": "Lesson marked as complete"}
            
            elif response.status_code == 404:
                print("Course not found.")
                return {"error": "not_found"}
            
            elif response.status_code == 401:
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail", "details": response.text}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "connection_failed"}

async def generate_course_certificate(token: str, course_id: str):
    """Hits the backend to generate or fetch the existing certificate for a course."""
    # Replace `API_BASE_URL` with your actual backend URL variable
    url = f"{api_url}/certificates/{course_id}/generate"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client: # Generates can take a few seconds
            response = await client.post(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            return {"error": f"Failed to generate certificate: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}
    
# ── Paste this into src/requests/Courses.py alongside your existing helpers ──

async def generate_course_draft(token: str, topic: str, context: str) -> dict:
    """Hit the /courses/generate-draft endpoint and return the parsed draft dict."""
    url = f"{api_url}/courses/generate-draft"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"topic": topic, "context": context}

    try:
        async with httpx.AsyncClient(timeout=120) as client:   # AI gen can be slow
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            print("[AI] Draft generated successfully.")
            return response.json()          # {"status": "success", "data": {...}}

        elif response.status_code == 403:
            print("[AI] Forbidden — user role not permitted.")
            return {"error": "forbidden"}

        elif response.status_code == 402:
            print("[AI] Plan gate — org not on a paid plan.")
            return {"error": "plan_required"}

        else:
            print(f"[AI] Generation failed: {response.status_code}")
            return {"error": "server_fail"}

    except Exception as ex:
        print(f"[AI] Request exception: {ex}")
        return {"error": "server_fail"}
    
async def get_completion_stats(token: str, course_id: str, params: dict | None = None): 
    url = f"{api_url}/courses/{course_id}/completion-stats" 
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
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
    
async def get_certificates_issued(token: str, course_id: str, params: dict | None = None): 
    url = f"{api_url}/courses/{course_id}/certificates" 
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
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