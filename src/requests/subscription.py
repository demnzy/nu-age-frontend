import httpx
from src.requests.net import ssl_context

api_url = "https://api.nu-age.name.ng"

# Default timeout for all requests in this file (matches the 15s "server
# waking up" allowance used elsewhere in the app).
DEFAULT_TIMEOUT = httpx.Timeout(15.0)


async def get_plans_config(token: str) -> dict:
    url = f"{api_url}/subscription/plans/config"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)
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


async def get_subscription_status(token: str) -> dict:
    url = f"{api_url}/subscription/status"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            response = await client.get(url, headers=headers)
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