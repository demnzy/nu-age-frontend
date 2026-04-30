import httpx
import asyncio
import json
import websockets

api_url = "https://nu-age.fly.dev"

# Automatically convert http:// to ws:// for the WebSocket connection
if api_url and api_url.startswith("https"):
    ws_url = api_url.replace("https://", "wss://")
else:
    ws_url = api_url.replace("http://", "ws://") if api_url else "ws://127.0.0.1:8000/api"

# ==========================================
# REST API FUNCTIONS (The "Pull" Network Layer)
# ==========================================

async def get_user_channels(token: str): 
    """Fetches all chat channels the user is a member of."""
    url = f"{api_url}/chat/channels" 
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                return {"error": "unauthorized"}
            else:
                return {"error": "server_fail"}
    except Exception as e:
        return {"error": "Connection failed", "detail": str(e)}

async def get_channel_messages(token: str, channel_id: str, limit: int = 50, offset: int = 0): 
    """Fetches the paginated message history for a specific channel."""
    url = f"{api_url}/chat/channels/{channel_id}/messages" 
    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": limit, "offset": offset}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                return {"error": "unauthorized"}
            elif response.status_code == 403:
                return {"error": "forbidden", "detail": "You don't have access to this chat."}
            else:
                return {"error": "server_fail"}
    except Exception as e:
        return {"error": "Connection failed", "detail": str(e)}

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
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json() 
            return {"error": f"Failed with status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

async def start_direct_message(token: str, target_user_id: str):
    """Initializes a 1-on-1 chat with another student or instructor."""
    url = f"{api_url}/chat/dms/{target_user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers)
            if response.status_code == 200:
                return response.json() 
            return {"error": f"Failed with status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# ==========================================
# WEBSOCKET MANAGER (The "Live" Network Layer)
# ==========================================

class ChatWebSocketClient:
    def __init__(self, token: str):
        self.token = token
        self.websocket = None
        self.listen_task = None
        self.on_message_callback = None

    async def connect(self, on_message_callback):
        """Opens the pipe and starts listening in the background."""
        self.on_message_callback = on_message_callback
        
        # Ensure your backend router prefix matches this path
        connection_url = f"{ws_url}/chat/ws?token={self.token}"
        
        try:
            self.websocket = await websockets.connect(connection_url)
            print("Connected to Nu-Chat Live!")
            self.listen_task = asyncio.create_task(self._listen())
        except Exception as e:
            print(f"WebSocket connection failed: {e}")

    async def _listen(self):
        """The permanent background loop waiting for new messages."""
        try:
            while True:
                message_str = await self.websocket.recv()
                message_dict = json.loads(message_str)
                
                if self.on_message_callback:
                    self.on_message_callback(message_dict)
                    
        except websockets.exceptions.ConnectionClosed:
            print("Disconnected from Nu-Chat Live.")
        except Exception as e:
            print(f"WebSocket Error: {e}")

    async def send_message(self, channel_id: str, content: str, msg_type: str = "text"):
        """Pushes data up the live pipe to the server."""
        if self.websocket:
            payload = {
                "channel_id": channel_id,
                "content": content,
                "type": msg_type
            }
            # THE FIX: Catch closed connections safely
            try:
                await self.websocket.send(json.dumps(payload))
            except websockets.exceptions.ConnectionClosedError:
                print("Socket disconnected! Message failed to send.")
                self.websocket = None # Mark as dead so the UI knows
            except Exception as e:
                print(f"Unknown sending error: {e}")

    async def disconnect(self):
        """Cleanly shuts down the pipe when leaving the chat screen."""
        if self.listen_task:
            self.listen_task.cancel()
        if self.websocket:
            await self.websocket.close()

async def get_all_users(token: str):
    """Fetches the list of all user IDs and names for manual testing/DMs."""
    url = f"{api_url}/users/directory"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            return {"error": f"Failed with status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

async def get_group_members(token: str, channel_id: str):
    url = f"{api_url}/chat/channels/{channel_id}/members"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json().get("member_ids", [])
            return []
    except Exception:
        return []

async def add_group_members(token: str, channel_id: str, member_ids: list):
    url = f"{api_url}/chat/channels/{channel_id}/members"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"member_ids": member_ids}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()
            return {"error": f"Failed: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

async def delete_chat_channel(token: str, channel_id: str):
    """Permanently deletes a chat room and all its messages."""
    url = f"{api_url}/chat/channels/{channel_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=headers)
            
            if response.status_code == 200:
                return response.json() # Returns {"message": "...", "channel_id": "..."}
            elif response.status_code == 403:
                return {"error": "forbidden", "detail": "You lack permission to delete this."}
            elif response.status_code == 404:
                return {"error": "not_found", "detail": "Chat already deleted."}
            else:
                return {"error": f"Failed with status {response.status_code}"}
                
    except Exception as e:
        return {"error": str(e)}

async def leave_group_channel(token: str, channel_id: str):
    """Hits the DELETE /{chat_id}/leave endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{api_url}/chats/{channel_id}/leave", 
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json()