import typing
import httpx
from src.requests.net import ssl_context

api_url = "https://api.nu-age.name.ng"
DEFAULT_TIMEOUT = httpx.Timeout(20.0)


async def get_payment_config() -> dict:
    """
    Fetches available payment configuration, active gateway, and public keys.
    """
    url = f"{api_url}/payments/config"
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as ex:
        return {"gateway": "paystack", "is_configured": False, "error": str(ex)}


async def initialize_payment(
    token: str,
    amount: float,
    purpose: str,
    organisation_id: typing.Optional[str] = None,
    callback_url: typing.Optional[str] = None,
    metadata: typing.Optional[dict] = None,
) -> dict:
    """
    Initializes a checkout transaction with the backend payment service.
    Returns: {"reference": str, "authorization_url": str, "access_code": str}
    """
    url = f"{api_url}/payments/initialize"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "amount": float(amount),
        "purpose": purpose,
        "organisation_id": organisation_id,
        "callback_url": callback_url,
        "metadata": metadata or {},
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        try:
            err_data = e.response.json()
            return {"error": err_data.get("detail", str(e))}
        except Exception:
            return {"error": f"Failed with status {e.response.status_code}"}
    except Exception as ex:
        return {"error": str(ex)}


async def verify_payment(token: str, reference: str) -> dict:
    """
    Verifies transaction status and triggers quota fulfillment on backend.
    """
    url = f"{api_url}/payments/verify/{reference}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        try:
            err_data = e.response.json()
            return {"error": err_data.get("detail", str(e))}
        except Exception:
            return {"error": f"Verification failed with status {e.response.status_code}"}
    except Exception as ex:
        return {"error": str(ex)}
