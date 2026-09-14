import httpx
from src.requests.net import ssl_context

api_url = "https://api.nu-age.name.ng"

# Default timeout for all requests in this file (matches the 15s "server
# waking up" allowance used elsewhere in the app).
DEFAULT_TIMEOUT = httpx.Timeout(15.0)


async def create_organisation(token: str, payload):
    url = f"{api_url}/organisations/create"
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
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": str(e)}


async def get_my_organisation(token: str):
    url = f"{api_url}/organisations/me"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
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
        return {"error": str(e)}


async def get_organisation_members(
    token: str,
    id: str,
    students: bool = False,
    teachers: bool = False,
):
    url = f"{api_url}/organisations/members"
    params = {"id": id, "students": students, "teachers": teachers}
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, params=params, headers=headers)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": str(e)}

async def get_organisation_courses(
    token: str,
    id: str,
    teacher_id: str | None = None,
    is_freelance: bool | None = None,
):
    url = f"{api_url}/organisations/courses?id={id}"
    if teacher_id is not None:
        url += f"&teacher_id={teacher_id}"
    if is_freelance is not None:
        # FastAPI's bool Query parser accepts "true"/"false" (case-insensitive)
        url += f"&is_freelance={'true' if is_freelance else 'false'}"

    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
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
        return {"error": str(e)}


async def join_org(org_id: str, user_id: str):
    # Intentionally unauthenticated — this is a public join-by-link endpoint.
    url = f"{api_url}/organisations/{org_id}/join?user_id={user_id}"

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url)

            if response.status_code == 200:
                return response.json()
            else:
                # THE FIX: never put the raw Response object in the dict —
                # it isn't JSON-serializable and can't be displayed directly.
                try:
                    error_detail = response.json().get("detail", f"HTTP {response.status_code}")
                except Exception:
                    error_detail = f"HTTP {response.status_code}: {response.text}"
                return {"error": error_detail}
    except Exception as e:
        print(f"Request Error: {e}")
        # THE FIX: Return a dict, NEVER the raw exception object!
        return {"error": str(e)}


async def process_invite_token(token: str) -> dict:
    url = f"{api_url}/organisations/process-invite"

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, json={"token": token})

            if response.status_code == 200:
                return response.json()
            else:
                # Try to safely extract FastAPI's error detail
                try:
                    error_detail = response.json().get("detail", f"HTTP {response.status_code}")
                except Exception:
                    error_detail = f"HTTP {response.status_code}: {response.text}"
                return {"error": error_detail}

    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": str(e)}


async def get_pending_invitations(token: str, org_id: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/invitations/pending"

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {token}"})

            if response.status_code == 200:
                return response.json()
            else:
                # Try to safely extract FastAPI's error detail
                try:
                    error_detail = response.json().get("detail", f"HTTP {response.status_code}")
                except Exception:
                    error_detail = f"HTTP {response.status_code}: {response.text}"
                return {"error": error_detail}

    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": str(e)}


async def revoke_invitation(token: str, invite_id: str) -> dict:
    url = f"{api_url}/organisations/invitations/{invite_id}/revoke"

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.delete(url, headers={"Authorization": f"Bearer {token}"})

            if response.status_code == 200:
                return response.json()
            else:
                # Try to safely extract FastAPI's error detail
                try:
                    error_detail = response.json().get("detail", f"HTTP {response.status_code}")
                except Exception:
                    error_detail = f"HTTP {response.status_code}: {response.text}"
                return {"error": error_detail}

    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": str(e)}


async def send_org_invite(token: str, org_id: str, email: str, role: str) -> dict:
    url = f"{api_url}/organisations/invite"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"organisation_id": org_id, "target_email": email, "role": role}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                return response.json()
            else:
                # Try to safely extract FastAPI's error detail
                try:
                    error_detail = response.json().get("detail", f"HTTP {response.status_code}")
                except Exception:
                    error_detail = f"HTTP {response.status_code}: {response.text}"
                return {"error": error_detail}

    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": str(e)}


async def get_joined_organisations(token: str) -> list:
    url = f"{api_url}/organisations/joined"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_detail = response.json().get("detail", f"HTTP {response.status_code}")
                except Exception:
                    error_detail = f"HTTP {response.status_code}: {response.text}"
                print(f"get_joined_organisations error: {error_detail}")
                return []

    except Exception as e:
        print(f"get_joined_organisations request error: {e}")
        return []

async def get_enrolled_org_students(token: str, course_id: str, params: dict | None = None):
    # NOTE: was previously missing the /courses prefix and would 404 against
    # the real FastAPI route. This duplicates enrollments.get_enrolled_students —
    # consider calling that instead of keeping two copies in sync.
    url = f"{api_url}/{course_id}/enrollments/org-students"
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


async def remove_organisation_member(token: str, org_id: str, user_id: str) -> dict:
    url = f"{api_url}/organisations/{org_id}/members/{user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.delete(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_detail = response.json().get("detail", f"HTTP {response.status_code}")
                except Exception:
                    error_detail = f"HTTP {response.status_code}: {response.text}"
                return {"error": error_detail}
    except Exception as e:
        print(f"remove_organisation_member error: {e}")
        return {"error": str(e)}