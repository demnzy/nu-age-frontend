import os
import typing
import httpx
from src.requests.net import ssl_context

api_url = os.getenv("NU_API_URL", "https://api.nu-age.name.ng").rstrip("/")
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


async def get_store_catalog() -> dict:
    """
    Fetches the store catalog containing plans, top-up booster packs, nu-coins, and org products
    directly from the authoritative backend PostgreSQL store_products table.
    """
    url = f"{api_url}/payments/store/catalog"
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, dict):
                    return data
            return {}
    except Exception as ex:
        print(f"[STORE] Error fetching remote catalog: {ex}")
        return {}


async def get_payment_history(token: str) -> list:
    """
    Fetches past transactions, payment receipts, and fulfillment status for the authenticated user.
    """
    url = f"{api_url}/payments/history"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return []
    except Exception as ex:
        print(f"[STORE] Error fetching payment history: {ex}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# SUPER ADMIN STORE CATALOG STUDIO API CALLS
# ─────────────────────────────────────────────────────────────────────────────

async def get_admin_store_products(token: str) -> list:
    """
    Fetches all store products (active and inactive) for Super Admin Studio.
    """
    url = f"{api_url}/payments/admin/products"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return []
    except Exception as ex:
        print(f"[ADMIN_STORE] Failed to fetch products: {ex}")
        return []


async def create_admin_store_product(token: str, payload: dict) -> dict:
    """
    Creates a new product in the store database.
    """
    url = f"{api_url}/payments/admin/products"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        try:
            return {"error": e.response.json().get("detail", str(e))}
        except Exception:
            return {"error": f"Failed with status {e.response.status_code}"}
    except Exception as ex:
        return {"error": str(ex)}


async def update_admin_store_product(token: str, product_id: str, payload: dict) -> dict:
    """
    Updates price, badges, perks, or active status of a store product.
    """
    url = f"{api_url}/payments/admin/products/{product_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.put(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        try:
            return {"error": e.response.json().get("detail", str(e))}
        except Exception:
            return {"error": f"Failed with status {e.response.status_code}"}
    except Exception as ex:
        return {"error": str(ex)}


async def delete_admin_store_product(token: str, product_id: str) -> dict:
    """
    Deletes a store product from the database.
    """
    url = f"{api_url}/payments/admin/products/{product_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.delete(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as ex:
        return {"error": str(ex)}


async def get_admin_org_plans(token: str) -> list:
    """
    Fetches all organisation plans from PostgreSQL 'plans' table.
    """
    url = f"{api_url}/payments/admin/org-plans"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return []
    except Exception as ex:
        print(f"[ADMIN_STORE] Failed to fetch org plans: {ex}")
        return []


async def save_admin_org_plan(token: str, payload: dict) -> dict:
    """
    Creates or updates an organisation plan in the PostgreSQL 'plans' table.
    """
    url = f"{api_url}/payments/admin/org-plans"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        try:
            return {"error": e.response.json().get("detail", str(e))}
        except Exception:
            return {"error": f"Failed with status {e.response.status_code}"}
    except Exception as ex:
        return {"error": str(ex)}


async def exchange_coins_api(token: str, package_id: str) -> dict:
    """
    Explicitly exchanges user's Nu-Coins for bonus AI Generation credits.
    """
    url = f"{api_url}/payments/store/exchange-coins"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers, json={"package_id": package_id})
            if resp.status_code == 200:
                return resp.json()
            try:
                detail = resp.json().get("detail", "Exchange failed.")
            except Exception:
                detail = resp.text or "Exchange failed."
            return {"error": detail}
    except Exception as ex:
        return {"error": str(ex)}
