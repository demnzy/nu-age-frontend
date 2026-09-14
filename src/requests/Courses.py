import httpx
from src.requests.net import ssl_context
import asyncio
api_url = "https://api.nu-age.name.ng"

# Default timeout for standard JSON requests. Uses connect=3.5s so offline network
# issues fail fast, while retaining read=15.0s for server waking up/cold starts.
DEFAULT_TIMEOUT = httpx.Timeout(connect=3.5, read=15.0, write=10.0, pool=5.0)


async def get_courses(token: str, params: dict | None = None):
    url = f"{api_url}/courses"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                print("Courses fetched successfully")
                return response.json()  # Returns the list

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        print("get_courses timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def create_course(token: str, payload):
    url = f"{api_url}/courses/create"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {**payload}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                print(f"Error {response.status_code}: {response.text}")
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        print("create_course timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def get_categories(token: str, params: dict | None = None):
    url = f"{api_url}/categories"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                print("Categories fetched successfully")
                return response.json()  # Returns the list

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        print("get_categories timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
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
        async with httpx.AsyncClient(timeout=300.0, verify=ssl_context) as client:
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
    except httpx.TimeoutException:
        print(f"Video upload timed out: {file_name}")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
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
        async with httpx.AsyncClient(timeout=300.0, verify=ssl_context) as client:
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
    except httpx.TimeoutException:
        print(f"Asset upload timed out: {file_name}")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def save_bulk_curriculum(token: str, course_id: str, payload: dict):
    """
    The final bulk publish! Sends the fully constructed JSON dictionary
    (with media URLs already injected) to the database.
    """
    url = f"{api_url}/courses/{course_id}/curriculum/bulk"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
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
    except httpx.TimeoutException:
        print("save_bulk_curriculum timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def get_course_curriculum(token: str, course_id: str):
    """
    Fetches the full nested curriculum structure for a specific course.
    """
    url = f"{api_url}/courses/{course_id}/curriculum"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                print(f"Curriculum for course {course_id} fetched successfully")
                return response.json()  # This will be your nested JSON object

            elif response.status_code == 404:
                print("Curriculum not found.")
                return {"error": "not_found"}

            elif response.status_code == 401:
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail", "details": response.text}
    except httpx.TimeoutException:
        print("get_course_curriculum timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def update_course_settings(token: str, course_id: str, setting: dict):
    """
    Updates the settings for a specific course.
    """
    url = f"{api_url}/courses/{course_id}/update_settings"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, json=setting)

            if response.status_code == 200:
                print(f"Settings for course {course_id} updated successfully")
                return response.json()  # This will be your updated course object

            elif response.status_code == 404:
                print("Course not found.")
                return {"error": "not_found"}

            elif response.status_code == 401:
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail", "details": response.text}
    except httpx.TimeoutException:
        print("update_course_settings timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def delete_course(token: str, course_id: str):
    """
    Deletes a specific course.
    """
    url = f"{api_url}/courses/{course_id}/delete"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
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
    except httpx.TimeoutException:
        print("delete_course timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def mark_complete(token: str, course_id: str, lesson_id: str):
    """
    Marks a lesson as complete.
    """
    url = f"{api_url}/courses/{course_id}/lessons/{lesson_id}/complete"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
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
    except httpx.TimeoutException:
        print("mark_complete timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def generate_course_certificate(token: str, course_id: str):
    """Hits the backend to generate or fetch the existing certificate for a course."""
    url = f"{api_url}/certificates/{course_id}/generate"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=ssl_context) as client:  # Generates can take a few seconds
            response = await client.post(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            return {"error": "server_fail"}
    except httpx.TimeoutException:
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        return {"error": "Connection failed"}
    except Exception as e:
        return {"error": "Connection failed"}


async def start_course_draft_job(token: str, topic: str, context: str) -> dict:
    """
    Kicks off generation on the backend. Backend now returns 202 immediately
    with a job_id instead of blocking on the full generation — this is a fast
    call (should return in well under a second).
    """
    url = f"{api_url}/courses/generate-draft"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"topic": topic, "context": context}
 
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=ssl_context) as client:  # fast call now, no AI wait here
            response = await client.post(url, headers=headers, json=payload)
 
        if response.status_code == 202:
            data = response.json()  # {"status": "queued", "job_id": "..."}
            print(f"[AI] Job queued: {data.get('job_id')}")
            return {"status": "queued", "job_id": data.get("job_id")}
 
        elif response.status_code == 403:
            print("[AI] Forbidden — user role not permitted.")
            return {"error": "forbidden"}
 
        elif response.status_code == 402:
            print("[AI] Plan gate — org not on a paid plan.")
            return {"error": "plan_required"}
 
        else:
            print(f"[AI] Failed to queue job: {response.status_code} — {response.text}")
            return {"error": "server_fail"}
 
    except httpx.TimeoutException:
        print("[AI] Job creation request timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as ex:
        print(f"[AI] Connection error: {ex}")
        return {"error": "Connection failed"}
    except Exception as ex:
        print(f"[AI] Unexpected exception starting job: {ex}")
        return {"error": "Connection failed"}
 
 
async def poll_course_draft_job(
    token: str,
    job_id: str,
    interval_seconds: float = 3.0,
    max_wait_seconds: float = 600.0,
) -> dict:
    """
    Polls the job status endpoint until SUCCESS, FAILED, or max_wait_seconds
    is exceeded. Returns the same {"status": "success", "data": {...}} shape
    the old single-call function returned, so callers barely change.
    """
    url = f"{api_url}/courses/generate-draft/{job_id}"
    headers = {"Authorization": f"Bearer {token}"}
    elapsed = 0.0
 
    async with httpx.AsyncClient(timeout=30.0, verify=ssl_context) as client:
        while elapsed < max_wait_seconds:
            try:
                response = await client.get(url, headers=headers)
 
                if response.status_code == 404:
                    print(f"[AI] Job {job_id} not found.")
                    return {"error": "server_fail"}
 
                if response.status_code != 200:
                    print(f"[AI] Poll failed: {response.status_code} — {response.text}")
                    return {"error": "server_fail"}
 
                data = response.json()
                job_status = data.get("status")
 
                if job_status == "SUCCESS":
                    print(f"[AI] Job {job_id} completed.")
                    return {"status": "success", "data": data.get("data", {})}
 
                if job_status == "FAILED":
                    print(f"[AI] Job {job_id} failed: {data.get('detail')}")
                    return {"error": "generation_failed", "detail": data.get("detail")}
 
                # PENDING or RUNNING — keep waiting
                await asyncio.sleep(interval_seconds)
                elapsed += interval_seconds
 
            except httpx.RequestError as ex:
                print(f"[AI] Poll connection error: {ex}")
                return {"error": "Connection failed"}
 
    print(f"[AI] Job {job_id} exceeded max wait of {max_wait_seconds}s.")
    return {"error": "timeout"}
 
 
async def generate_course_draft(token: str, topic: str, context: str) -> dict:
    """
    Drop-in replacement for the old single-call version — same signature,
    same return shape. Internally: start job, then poll until done.
    """
    start_result = await start_course_draft_job(token, topic, context)
 
    if "error" in start_result:
        return start_result
 
    job_id = start_result.get("job_id")
    if not job_id:
        return {"error": "server_fail"}
 
    return await poll_course_draft_job(token, job_id)

async def get_completion_stats(token: str, course_id: str, params: dict | None = None):
    url = f"{api_url}/courses/{course_id}/completion-stats"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        print("get_completion_stats timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def get_certificates_issued(token: str, course_id: str, params: dict | None = None):
    url = f"{api_url}/courses/{course_id}/certificates"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        print("get_certificates_issued timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}

async def rate_course(token: str, course_id: str, rating: float):
    url = f"{api_url}/courses/{course_id}/rate"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"rating": float(rating)}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                return {"error": "unauthorized"}
            elif response.status_code in [400, 403, 404]:
                try:
                    return {"error": response.json().get("detail", "Error submitting rating")}
                except Exception:
                    return {"error": response.text or "Error submitting rating"}
            else:
                try:
                    return {"error": response.json().get("detail", f"Server error ({response.status_code})")}
                except Exception:
                    return {"error": f"Server error ({response.status_code})"}
    except Exception as e:
        print(f"Unexpected Error in rate_course: {e}")
        return {"error": "Connection failed"}