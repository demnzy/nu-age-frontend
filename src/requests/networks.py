import httpx
from typing import List, Dict, Any

import os
from dotenv import load_dotenv
load_dotenv()
api_url = os.getenv("API_URL")

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

# ══════════════════════════════════════════════════════════════════════════════
# 1. MY NETWORK (The Roster)
# ══════════════════════════════════════════════════════════════════════════════

async def get_friends(token: str, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{api_url}/network/friends",
            headers=_headers(token),
            params={"skip": skip, "limit": limit}
        )
        response.raise_for_status()
        return response.json()

async def remove_friend(token: str, friend_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{api_url}/network/friends/{friend_id}",
            headers=_headers(token)
        )
        response.raise_for_status()
        return response.json()

# ══════════════════════════════════════════════════════════════════════════════
# 2. CONNECTION REQUESTS (The Inbox)
# ══════════════════════════════════════════════════════════════════════════════

async def get_incoming_requests(token: str) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{api_url}/network/requests/incoming",
            headers=_headers(token)
        )
        response.raise_for_status()
        return response.json()

# NOTE: You will need to add this endpoint to your FastAPI router!
async def get_sent_requests(token: str) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{api_url}/network/requests/sent",
            headers=_headers(token)
        )
        response.raise_for_status()
        return response.json()

async def send_request(token: str, target_user_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/network/requests/{target_user_id}",
            headers=_headers(token)
        )
        response.raise_for_status()
        return response.json()

async def accept_request(token: str, request_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/network/requests/{request_id}/accept",
            headers=_headers(token)
        )
        response.raise_for_status()
        return response.json()

async def decline_request(token: str, request_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/network/requests/{request_id}/decline",
            headers=_headers(token)
        )
        response.raise_for_status()
        return response.json()

async def cancel_outgoing_request(token: str, request_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{api_url}/network/requests/{request_id}/cancel",
            headers=_headers(token)
        )
        response.raise_for_status()
        return response.json()

# ══════════════════════════════════════════════════════════════════════════════
# 3. DISCOVER (The Growth Engine)
# ══════════════════════════════════════════════════════════════════════════════

async def get_discover_peers(token: str, limit: int = 10) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{api_url}/network/discover/peers",
            headers=_headers(token),
            params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()
    
async def send_request(token: str, target_user_id: str) -> Dict[str, Any]:
    """Sends a friend request to a specific user."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/network/requests/{target_user_id}",
            headers=_headers(token)
        )
        response.raise_for_status()
        return response.json()

async def get_discover_peers(token: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches users from the same university."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{api_url}/network/discover/peers",
            headers=_headers(token),
            params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()

async def get_discover_org(token: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches users from the same organization."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{api_url}/network/discover/organization",
            headers=_headers(token),
            params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()

async def get_discover_trending(token: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches globally active/trending users."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{api_url}/network/discover/trending",
            headers=_headers(token),
            params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()