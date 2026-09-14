import httpx
from src.requests.net import ssl_context
import json

api_url = "https://api.nu-age.name.ng"

# Default timeout for standard JSON requests. Uses connect=3.5s so offline network
# issues fail fast, while retaining read=15.0s for server waking up/cold starts.
DEFAULT_TIMEOUT = httpx.Timeout(connect=3.5, read=15.0, write=10.0, pool=5.0)


async def get_enrollments(token: str, params: dict | None = None):
    url = f"{api_url}/courses/enrolled"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()  # Returns the list

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        print("get_enrollments timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def enrol_user(token: str, course_id, params: dict | None = None):
    """
    Returns (status_code, data) on success, matching original behavior.
    Returns a bare {"error": ...} dict on failure, matching original behavior.
    """
    url = f"{api_url}/courses/{course_id}/enrol"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.status_code, response.json()

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        print("enrol_user timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def get_enrolled_students(token: str, course_id: str, params: dict | None = None):
    url = f"{api_url}/courses/{course_id}/enrollments/org-students"
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
        print("get_enrolled_students timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def bulk_enrol_students(token: str, course_id, payload, params: dict | None = None):
    url = f"{api_url}/courses/{course_id}/enrollments/bulk-enroll"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, params=params, json=payload)
            if response.status_code == 200:
                return response.json()

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        print("bulk_enrol_students timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def bulk_unenrol_students(token: str, course_id, payload, params: dict | None = None):
    url = f"{api_url}/courses/{course_id}/enrollments/bulk-unenroll"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, params=params, json=payload)
            if response.status_code == 200:
                return response.json()

            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        print("bulk_unenrol_students timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}


async def get_enrollment(token: str, course_id):
    """
    Gets an enrollment given course id
    """
    url = f"{api_url}/courses/{course_id}/enrollment"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        # Catches the 404 (Not Found) or 400 (Not 100% complete) errors
        try:
            detail = e.response.json().get("detail", "Failed to fetch enrollment")
        except (json.JSONDecodeError, ValueError):
            # Backend returned a non-JSON error page (e.g. a raw 502 from Fly.io)
            detail = "Failed to fetch enrollment"
        return {"error": detail}
    except httpx.TimeoutException:
        print("get_enrollment timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": str(e)}


async def get_enrollment_stats(token: str, enrollment_id: str):
    url = f"{api_url}/enrollments/{enrollment_id}/stats"
    headers = {"Authorization": f"Bearer {token}"}
    # Force a 10-second timeout so it never hangs infinitely
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        # Fix a potential crash if the backend returns a 422 Validation Error (which is a list, not a dict)
        try:
            data = e.response.json()
        except (json.JSONDecodeError, ValueError):
            return {"error": "Failed to fetch stats"}

        if isinstance(data, list):
            return {"error": str(data)}
        return {"error": data.get("detail", "Failed to fetch stats")}
    except httpx.TimeoutException:
        print("get_enrollment_stats timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": str(e)}


async def get_weekly_activity(token: str, course_id: str, params: dict | None = None):
    url = f"{api_url}/courses/{course_id}/activity"
    headers = {"Authorization": f"Bearer {token}"}

    # Ensure the period query parameter defaults to 'weekly' if not provided
    if not params:
        params = {"period": "weekly"}

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
        print("get_weekly_activity timed out.")
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return {"error": "Connection failed"}