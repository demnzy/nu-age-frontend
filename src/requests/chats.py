import httpx
from src.requests.net import ssl_context
import asyncio
import json
import websockets

api_url = "https://api.nu-age.name.ng"

# Automatically convert http:// to ws:// for the WebSocket connection
if api_url and api_url.startswith("https"):
    ws_url = api_url.replace("https://", "wss://")
else:
    ws_url = api_url.replace("http://", "ws://") if api_url else "ws://127.0.0.1:8000/api"

# Default timeout for all REST calls in this file.
# Matches the 15s "server waking up" allowance used in auth.py.
DEFAULT_TIMEOUT = httpx.Timeout(15.0)

# ==========================================
# REST API FUNCTIONS (The "Pull" Network Layer)
# ==========================================

async def get_user_channels(token: str):
    """Fetches all chat channels the user is a member of."""
    url = f"{api_url}/chat/channels"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        return {"error": "Connection failed"}
    except Exception as e:
        return {"error": "Connection failed"}


async def get_channel_messages(token: str, channel_id: str, limit: int = 50, offset: int = 0):
    """Fetches the paginated message history for a specific channel."""
    url = f"{api_url}/chat/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": limit, "offset": offset}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                return {"error": "unauthorized"}
            elif response.status_code == 403:
                return {"error": "forbidden", "detail": "You don't have access to this chat."}
            else:
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        return {"error": "Connection failed"}
    except Exception as e:
        return {"error": "Connection failed"}


async def create_group_channel(token: str, name: str, channel_type: str, org_id: str = None, is_announcement: bool = False, member_ids: list = None):
    """Creates a new group chat (Custom or Org-wide)."""
    url = f"{api_url}/chat/channels"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "name": name,
        "type": channel_type,
        "org_id": org_id,
        "is_announcement_only": is_announcement,
        "member_ids": member_ids or []  # <--- CRITICAL: Pass the selected users to the backend
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()
            return {"error": f"Failed with status {response.status_code}"}
    except httpx.TimeoutException:
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        return {"error": "Connection failed"}
    except Exception as e:
        return {"error": str(e)}


async def start_direct_message(token: str, target_user_id: str, params: dict | None = None):
    """Initializes a 1-on-1 chat with another student or instructor."""
    url = f"{api_url}/chat/dms/{target_user_id}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                print("Unauthorized access. Please log in again.")
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except httpx.TimeoutException:
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"Request Error: {e}")
        return {"error": "Connection failed"}


# ==========================================
# WEBSOCKET MANAGER (The "Live" Network Layer)
# ==========================================

class ChatWebSocketClient:
    def __init__(self, token: str):
        self.token = token
        self.websocket = None
        self.listen_task = None
        self.on_message_callback = None
        self.on_disconnect_callback = None  # NEW: lets the UI react when the socket dies

    async def connect(self, on_message_callback, on_disconnect_callback=None, timeout: float = 15.0) -> bool:
        """
        Opens the pipe and starts listening in the background.
        Returns True on success, False on failure, so the caller can
        show a proper error state instead of silently doing nothing.
        """
        self.on_message_callback = on_message_callback
        self.on_disconnect_callback = on_disconnect_callback

        # Ensure your backend router prefix matches this path
        connection_url = f"{ws_url}/chat/ws?token={self.token}"

        try:
            self.websocket = await asyncio.wait_for(
                websockets.connect(connection_url), timeout=timeout
            )
            print("Connected to Nu-Chat Live!")
            self.listen_task = asyncio.create_task(self._listen())
            return True
        except asyncio.TimeoutError:
            print("WebSocket connection timed out.")
            self.websocket = None
            return False
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            self.websocket = None
            return False

    async def _listen(self):
        """The permanent background loop waiting for new messages."""
        try:
            while True:
                message_str = await self.websocket.recv()
                try:
                    message_dict = json.loads(message_str)
                except json.JSONDecodeError:
                    print(f"Received malformed message, skipping: {message_str!r}")
                    continue

                if self.on_message_callback:
                    self.on_message_callback(message_dict)

        except websockets.exceptions.ConnectionClosed:
            print("Disconnected from Nu-Chat Live.")
        except Exception as e:
            print(f"WebSocket Error: {e}")
        finally:
            # Socket is dead either way — mark it and let the UI know
            self.websocket = None
            if self.on_disconnect_callback:
                self.on_disconnect_callback()

    async def send_message(self, channel_id: str, content: str, msg_type: str = "text", **kwargs) -> bool:
        """Pushes data up the live pipe to the server. Returns True/False for success."""
        if not self.websocket:
            print("Cannot send: no active socket connection.")
            return False

        payload = {
            "channel_id": channel_id,
            "content": content,
            "type": msg_type
        }
        payload.update(kwargs)
        try:
            await self.websocket.send(json.dumps(payload))
            return True
        except websockets.exceptions.ConnectionClosedError:
            print("Socket disconnected! Message failed to send.")
            self.websocket = None  # Mark as dead so the UI knows
            return False
        except Exception as e:
            print(f"Unknown sending error: {e}")
            return False

    async def disconnect(self):
        """Cleanly shuts down the pipe when leaving the chat screen."""
        if self.listen_task:
            self.listen_task.cancel()
            try:
                await self.listen_task
            except (asyncio.CancelledError, Exception):
                pass
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                print(f"Error closing socket cleanly: {e}")
        self.websocket = None


async def get_all_users(token: str):
    """Fetches the list of all user IDs and names for manual testing/DMs."""
    url = f"{api_url}/users/directory"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            return {"error": f"Failed with status {response.status_code}"}
    except httpx.TimeoutException:
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        return {"error": "Connection failed"}
    except Exception as e:
        return {"error": str(e)}


async def get_group_members(token: str, channel_id: str):
    url = f"{api_url}/chat/channels/{channel_id}/members"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json().get("member_ids", [])
            return []
    except httpx.TimeoutException:
        print("get_group_members timed out.")
        return []
    except httpx.RequestError as e:
        print(f"get_group_members connection error: {e}")
        return []
    except Exception as e:
        print(f"get_group_members unknown error: {e}")
        return []


async def add_group_members(token: str, channel_id: str, member_ids: list):
    url = f"{api_url}/chat/channels/{channel_id}/members"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"member_ids": member_ids}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()
            return {"error": f"Failed: {response.status_code}"}
    except httpx.TimeoutException:
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        return {"error": "Connection failed"}
    except Exception as e:
        return {"error": str(e)}


async def delete_chat_channel(token: str, channel_id: str):
    """Permanently deletes a chat room and all its messages."""
    url = f"{api_url}/chat/channels/{channel_id}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.delete(url, headers=headers)

            if response.status_code == 200:
                return response.json()  # Returns {"message": "...", "channel_id": "..."}
            elif response.status_code == 403:
                return {"error": "forbidden", "detail": "You lack permission to delete this."}
            elif response.status_code == 404:
                return {"error": "not_found", "detail": "Chat already deleted."}
            else:
                return {"error": f"Failed with status {response.status_code}"}
    except httpx.TimeoutException:
        return {"error": "Connection failed"}
    except httpx.RequestError as e:
        return {"error": "Connection failed"}
    except Exception as e:
        return {"error": str(e)}


async def leave_group_channel(token: str, channel_id: str):
    """Hits the DELETE /{chat_id}/leave endpoint."""
    url = f"{api_url}/chats/{channel_id}/leave"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.delete(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "Connection failed"}
    except httpx.HTTPStatusError as e:
        return {"error": str(e)}
    except httpx.RequestError as e:
        return {"error": "Connection failed"}
    except Exception as e:
        return {"error": str(e)}