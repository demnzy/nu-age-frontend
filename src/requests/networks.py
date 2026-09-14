import httpx
from src.requests.net import ssl_context
from typing import List, Dict, Any

api_url = "https://api.nu-age.name.ng"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# Default timeout for all requests in this file.
DEFAULT_TIMEOUT = httpx.Timeout(15.0)


# ══════════════════════════════════════════════════════════════════════════════
# 1. MY NETWORK (The Roster)
# ══════════════════════════════════════════════════════════════════════════════

async def get_friends(token: str, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(
                f"{api_url}/network/friends",
                headers=_headers(token),
                params={"skip": skip, "limit": limit}
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print("get_friends timed out.")
        return []
    except httpx.HTTPStatusError as e:
        print(f"get_friends failed with status {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        print(f"get_friends connection error: {e}")
        return []
    except Exception as e:
        print(f"get_friends unexpected error: {e}")
        return []


async def remove_friend(token: str, friend_id: str) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.delete(
                f"{api_url}/network/friends/{friend_id}",
                headers=_headers(token)
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "The server is taking too long to respond. Please try again."}
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed with status {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": "Please check your internet connection and try again."}
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# 2. CONNECTION REQUESTS (The Inbox)
# ══════════════════════════════════════════════════════════════════════════════

async def get_incoming_requests(token: str) -> List[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(
                f"{api_url}/network/requests/incoming",
                headers=_headers(token)
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print("get_incoming_requests timed out.")
        return []
    except httpx.HTTPStatusError as e:
        print(f"get_incoming_requests failed with status {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        print(f"get_incoming_requests connection error: {e}")
        return []
    except Exception as e:
        print(f"get_incoming_requests unexpected error: {e}")
        return []


# NOTE: You will need to add this endpoint to your FastAPI router!
async def get_sent_requests(token: str) -> List[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(
                f"{api_url}/network/requests/sent",
                headers=_headers(token)
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print("get_sent_requests timed out.")
        return []
    except httpx.HTTPStatusError as e:
        print(f"get_sent_requests failed with status {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        print(f"get_sent_requests connection error: {e}")
        return []
    except Exception as e:
        print(f"get_sent_requests unexpected error: {e}")
        return []


async def send_request(token: str, target_user_id: str) -> Dict[str, Any]:
    """Sends a friend request to a specific user."""
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(
                f"{api_url}/network/requests/{target_user_id}",
                headers=_headers(token)
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "The server is taking too long to respond. Please try again."}
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed with status {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": "Please check your internet connection and try again."}
    except Exception as e:
        return {"error": str(e)}


async def accept_request(token: str, request_id: str) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(
                f"{api_url}/network/requests/{request_id}/accept",
                headers=_headers(token)
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "The server is taking too long to respond. Please try again."}
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed with status {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": "Please check your internet connection and try again."}
    except Exception as e:
        return {"error": str(e)}


async def decline_request(token: str, request_id: str) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(
                f"{api_url}/network/requests/{request_id}/decline",
                headers=_headers(token)
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "The server is taking too long to respond. Please try again."}
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed with status {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": "Please check your internet connection and try again."}
    except Exception as e:
        return {"error": str(e)}


async def cancel_outgoing_request(token: str, request_id: str) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.delete(
                f"{api_url}/network/requests/{request_id}/cancel",
                headers=_headers(token)
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "The server is taking too long to respond. Please try again."}
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed with status {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": "Please check your internet connection and try again."}
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# 3. DISCOVER (The Growth Engine)
# ══════════════════════════════════════════════════════════════════════════════

async def get_discover_peers(token: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches users from the same university."""
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(
                f"{api_url}/network/discover/peers",
                headers=_headers(token),
                params={"limit": limit}
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print("get_discover_peers timed out.")
        return []
    except httpx.HTTPStatusError as e:
        print(f"get_discover_peers failed with status {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        print(f"get_discover_peers connection error: {e}")
        return []
    except Exception as e:
        print(f"get_discover_peers unexpected error: {e}")
        return []


async def get_discover_org(token: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches users from the same organization."""
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(
                f"{api_url}/network/discover/organization",
                headers=_headers(token),
                params={"limit": limit}
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print("get_discover_org timed out.")
        return []
    except httpx.HTTPStatusError as e:
        print(f"get_discover_org failed with status {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        print(f"get_discover_org connection error: {e}")
        return []
    except Exception as e:
        print(f"get_discover_org unexpected error: {e}")
        return []


async def get_discover_trending(token: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches globally active/trending users."""
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(
                f"{api_url}/network/discover/trending",
                headers=_headers(token),
                params={"limit": limit}
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        print("get_discover_trending timed out.")
        return []
    except httpx.HTTPStatusError as e:
        print(f"get_discover_trending failed with status {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        print(f"get_discover_trending connection error: {e}")
        return []
    except Exception as e:
        print(f"get_discover_trending unexpected error: {e}")
        return []