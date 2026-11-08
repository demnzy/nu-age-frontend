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


async def send_channel_message_api(token: str, channel_id: str, content: str, msg_type: str = "text", metadata_payload: dict = None):
    """Sends a message to a channel via REST."""
    url = f"{api_url}/chat/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"content": content, "type": msg_type, "metadata_payload": metadata_payload}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (200, 201):
                return resp.json()
            return {"error": f"Status {resp.status_code}"}
    except Exception as ex:
        return {"error": str(ex)}


async def ask_ai_tutor_api(
    token: str,
    query: str,
    course_title: str = "Course",
    module_title: str = "Module",
    lesson_title: str = "Lesson",
    lesson_content: str = "",
    conversation_history: list = None,
    is_assessment: bool = False,
    material_id: str = None,
):
    """Calls the OpenAI-powered educational AI Doubt Assistant."""
    url = f"{api_url}/study/ai-tutor"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "query": query,
        "course_title": course_title,
        "module_title": module_title,
        "lesson_title": lesson_title,
        "lesson_content": lesson_content,
        "conversation_history": conversation_history or [],
        "is_assessment": is_assessment,
        "material_id": str(material_id) if material_id else None,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(35.0, connect=10.0), verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 403:
                try:
                    err_json = resp.json()
                    detail = err_json.get("detail", "Free daily AI tutor limit reached (15/15). Upgrade to Pro Scholar for unlimited access.")
                except Exception:
                    detail = "Free daily AI tutor limit reached (15/15). Upgrade to Pro Scholar for unlimited access."
                return {"error": detail, "quota_locked": True, "status_code": 403}
            try:
                err_json = resp.json()
                detail = err_json.get("detail")
            except Exception:
                detail = None
            msg = detail or "I ran into a brief hiccup reaching the AI tutor service right now. Please try asking again in a moment."
            return {"error": msg, "is_ai_error": True, "status_code": resp.status_code}
    except httpx.TimeoutException:
        return {"error": "The AI tutor took longer than expected to answer. Please try asking again.", "is_ai_error": True, "is_timeout": True}
    except Exception as ex:
        print(f"[ask_ai_tutor_api] network exception: {ex}")
        return {"error": "I'm having trouble connecting to the study server. Please verify your internet connection.", "is_ai_error": True}



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
        self.reconnect_task = None
        self.on_message_callback = None
        self.on_disconnect_callback = None
        self.on_connected_callback = None
        self._is_closed = False
        self._is_connecting = False
        self._backoff = 2.0

    async def connect(self, on_message_callback, on_disconnect_callback=None, timeout: float = 6.0) -> bool:
        """
        Connects to the live WebSocket server with fast timeout and ssl_context.
        Starts listener and supervisor reconnect task on disconnect.
        """
        self.on_message_callback = on_message_callback
        if on_disconnect_callback:
            self.on_disconnect_callback = on_disconnect_callback
        self._is_closed = False

        if self.websocket and not getattr(self.websocket, "closed", False):
            return True

        if self._is_connecting:
            return False
        self._is_connecting = True

        connection_url = f"{ws_url}/chat/ws?token={self.token}"
        use_ssl = ssl_context if connection_url.startswith("wss://") else None

        try:
            self.websocket = await asyncio.wait_for(
                websockets.connect(
                    connection_url,
                    ssl=use_ssl,
                    open_timeout=5.0,
                    ping_interval=25.0,
                    ping_timeout=15.0,
                    close_timeout=4.0,
                ),
                timeout=timeout,
            )
            print("[NuChat] Connected to Nu-Chat Live!")
            self._backoff = 2.0
            self._is_connecting = False
            if self.listen_task:
                self.listen_task.cancel()
            self.listen_task = asyncio.create_task(self._listen())
            if self.on_connected_callback:
                try:
                    self.on_connected_callback()
                except Exception:
                    pass
            return True
        except asyncio.TimeoutError:
            print("[NuChat] WebSocket connection timed out (server slow or waking up).")
            self.websocket = None
            self._is_connecting = False
            self._schedule_reconnect()
            return False
        except Exception as e:
            print(f"[NuChat] WebSocket connection failed: {e}")
            self.websocket = None
            self._is_connecting = False
            self._schedule_reconnect()
            return False

    def _schedule_reconnect(self):
        """Schedules background reconnection with backoff without blocking the UI."""
        if self._is_closed or self._is_connecting:
            return
        if self.reconnect_task and not self.reconnect_task.done():
            return
        self.reconnect_task = asyncio.create_task(self._reconnect_worker())

    async def _reconnect_worker(self):
        """Silent background worker that re-establishes socket connection."""
        await asyncio.sleep(self._backoff)
        if self._is_closed:
            return
        self._backoff = min(20.0, self._backoff * 1.5)
        if self.on_message_callback:
            await self.connect(self.on_message_callback, self.on_disconnect_callback, timeout=6.0)

    async def _listen(self):
        """The permanent background loop waiting for new messages."""
        try:
            while self.websocket and not getattr(self.websocket, "closed", False):
                message_str = await self.websocket.recv()
                try:
                    message_dict = json.loads(message_str)
                except json.JSONDecodeError:
                    print(f"[NuChat] Received malformed message, skipping: {message_str!r}")
                    continue

                if self.on_message_callback:
                    try:
                        self.on_message_callback(message_dict)
                    except Exception as cb_err:
                        print(f"[NuChat] Error in on_message_callback: {cb_err}")

        except websockets.exceptions.ConnectionClosed:
            print("[NuChat] Disconnected from Nu-Chat Live.")
        except Exception as e:
            print(f"[NuChat] WebSocket Error: {e}")
        finally:
            self.websocket = None
            if self.on_disconnect_callback and not self._is_closed:
                try:
                    self.on_disconnect_callback()
                except Exception:
                    pass
            if not self._is_closed:
                self._schedule_reconnect()

    async def send_message(self, channel_id: str, content: str, msg_type: str = "text", **kwargs) -> bool:
        """Pushes data up the live pipe to the server with fast timeout. Returns True/False for success."""
        if not self.websocket or getattr(self.websocket, "closed", False):
            return False

        payload = {
            "channel_id": channel_id,
            "content": content,
            "type": msg_type
        }
        payload.update(kwargs)
        try:
            await asyncio.wait_for(self.websocket.send(json.dumps(payload)), timeout=2.5)
            return True
        except websockets.exceptions.ConnectionClosedError:
            print("[NuChat] Socket disconnected! Message will fall back to REST.")
            self.websocket = None
            self._schedule_reconnect()
            return False
        except Exception as e:
            print(f"[NuChat] WebSocket sending error: {e}")
            return False

    async def disconnect(self):
        """Cleanly shuts down the pipe when leaving the chat screen."""
        self._is_closed = True
        if self.reconnect_task:
            self.reconnect_task.cancel()
        if self.listen_task:
            self.listen_task.cancel()
            try:
                await self.listen_task
            except (asyncio.CancelledError, Exception):
                pass
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None
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
                return response.json()
            return {}
    except Exception as e:
        print(f"get_group_members error: {e}")
        return {}


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
    """Hits the DELETE /chat/channels/{channel_id}/leave endpoint."""
    url = f"{api_url}/chat/channels/{channel_id}/leave"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.delete(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                try:
                    err_detail = response.json().get("detail", "Cannot leave this group.")
                    return {"error": err_detail}
                except Exception:
                    return {"error": response.text}
            return {"error": f"Failed with status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def upload_chat_media_api(token: str, channel_id: str, file_bytes: bytes, filename: str, mime_type: str = "image/jpeg"):
    """Uploads lightweight images or audio notes directly to BunnyCDN via the chat API."""
    url = f"{api_url}/chat/upload_media"
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, file_bytes, mime_type)}
    data = {"channel_id": channel_id}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0), verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, data=data, files=files)
            if resp.status_code == 200:
                return resp.json()
            try:
                err = resp.json().get("detail", f"Upload failed: {resp.status_code}")
            except Exception:
                err = resp.text or f"Upload failed: {resp.status_code}"
            return {"error": err}
    except Exception as ex:
        return {"error": str(ex)}


async def get_pinned_chat_message(token: str, channel_id: str):
    """Fetches the active pinned message in a channel."""
    url = f"{api_url}/chat/channels/{channel_id}/pinned"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception:
        return None


async def delete_channel_message_api(token: str, channel_id: str, message_id: str):
    """Deletes a message or poll from a channel for everyone via REST fallback."""
    url = f"{api_url}/chat/channels/{channel_id}/messages/{message_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            try:
                err = resp.json().get("detail", f"Status {resp.status_code}")
            except Exception:
                err = resp.text or f"Status {resp.status_code}"
            return {"error": err}
    except Exception as ex:
        return {"error": str(ex)}


async def vote_poll_message_api(token: str, channel_id: str, message_id: str, option: str):
    """Casts or toggles a vote on a poll via REST fallback if WebSocket connection drops."""
    url = f"{api_url}/chat/channels/{channel_id}/messages/{message_id}/vote"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"option": option}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception:
        return None


async def search_channel_messages_api(token: str, channel_id: str, query: str, limit: int = 30):
    """Searches messages inside a channel by text content."""
    url = f"{api_url}/chat/channels/{channel_id}/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": query, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                return resp.json()
            return []
    except Exception:
        return []
