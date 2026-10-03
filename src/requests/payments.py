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


DEFAULT_STORE_CATALOG = {
    "currency": "NGN",
    "currency_symbol": "₦",
    "plans": [
        {
            "id": "free",
            "name": "Free Tier",
            "badge": "DEFAULT",
            "price": 0,
            "interval": "forever",
            "materials_limit": 25,
            "generations_limit": 40,
            "exam_quota": 10,
            "description": "Essential study toolkit for everyday comprehension.",
            "features": [
                "25 Material Upload slots (PDF, Text, Notes)",
                "40 AI Study Deck Generation bundles",
                "10 Full Practice Exam simulations",
                "Unlimited Spaced Repetition Flashcards",
                "Socratic AI Chat Tutor",
            ],
            "is_current": True,
        },
        {
            "id": "pro",
            "name": "Pro Scholar",
            "badge": "MOST POPULAR",
            "price": 2500,
            "interval": "month",
            "materials_limit": 45,
            "generations_limit": 100,
            "exam_quota": 40,
            "description": "For dedicated undergraduates seeking an academic edge.",
            "features": [
                "45 Total Material Upload slots (+20 extra/month)",
                "100 AI Study Deck Generation bundles/month",
                "40 Full Practice Exam simulations/month",
                "Unlimited Quick Quiz & Spaced Repetition",
                "Priority Socratic AI Tutor & LaTeX formatting",
                "Multi-photo whiteboard & slide OCR",
            ],
            "recommended": True,
        },
        {
            "id": "unlimited",
            "name": "Unlimited Ultimate",
            "badge": "BEST VALUE",
            "price": 8500,
            "interval": "month",
            "materials_limit": None,
            "generations_limit": None,
            "exam_quota": None,
            "description": "Unbounded power for medical, law, and intensive exam candidates.",
            "features": [
                "Unlimited Material Upload slots",
                "Unlimited AI Study Deck Generation bundles",
                "Unlimited Exam Simulations & Timer drills",
                "Deep Grounded Document Synthesis",
                "Early Access to new learning AI models",
            ],
            "recommended": False,
        },
    ],
    "packs": [
        {
            "id": "starter_booster",
            "name": "Starter Booster",
            "badge": "QUICK TOP-UP",
            "price": 1000,
            "materials": 10,
            "generations": 25,
            "description": "+10 materials & +25 AI generations. Non-expiring.",
            "features": [
                "+10 Additional Material slots",
                "+25 AI Generation bundles",
                "Credits never expire across cycles",
            ],
        },
        {
            "id": "semester_pack",
            "name": "Semester Pack",
            "badge": "STUDY SPRINT",
            "price": 2200,
            "materials": 25,
            "generations": 50,
            "description": "+25 materials & +50 AI generations. Perfect for midterm & finals prep.",
            "features": [
                "+25 Additional Material slots",
                "+50 AI Generation bundles",
                "Credits never expire across cycles",
            ],
        },
        {
            "id": "mega_vault",
            "name": "Mega Vault Booster",
            "badge": "POWER USER",
            "price": 4500,
            "materials": 50,
            "generations": 100,
            "description": "+50 materials & +100 AI generations. Non-expiring consumable expansion.",
            "features": [
                "+50 Additional Material slots",
                "+100 AI Generation bundles",
                "Credits never expire across cycles",
            ],
        },
    ],
    "org_products": [
        {
            "id": "org_seat_single",
            "name": "Single Member Seat",
            "price": 1500,
            "interval": "month",
            "description": "Add 1 additional student/faculty seat to your organisation workspace.",
            "features": [
                "1 Extra Member Seat",
                "Full cohort & training access",
                "Analytics & gradebook monitoring",
            ],
        },
        {
            "id": "org_seat_pack_10",
            "name": "Classroom 10-Seat Pack",
            "badge": "POPULAR FOR TEAMS",
            "price": 12000,
            "interval": "month",
            "description": "Add 10 seats to your organisation workspace with a bulk discount.",
            "features": [
                "10 Extra Member Seats (Save 20%)",
                "Full cohort & training access",
                "Team exam distribution & proctoring",
            ],
        },
    ],
}


async def get_store_catalog() -> dict:
    """
    Fetches the store catalog containing plans, top-up booster packs, and org products.
    Falls back gracefully to DEFAULT_STORE_CATALOG if remote backend route is not yet deployed.
    """
    url = f"{api_url}/payments/store/catalog"
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data and (data.get("plans") or data.get("packs")):
                    return data
            return DEFAULT_STORE_CATALOG
    except Exception as ex:
        print(f"[STORE] Remote catalog unavailable ({ex}); using fallback catalog.")
        return DEFAULT_STORE_CATALOG
