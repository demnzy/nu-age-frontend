import httpx
from src.requests.net import ssl_context
from typing import Optional, List, Dict, Any

api_url = "https://api.nu-age.name.ng"
DEFAULT_TIMEOUT = httpx.Timeout(15.0)

DEFAULT_PRELIM_OBJECTIVES = [
    {
        "code": "finish_first_course",
        "title": "Course Master",
        "description": "Complete all modules in any registered university course.",
        "category": "course",
        "target_value": 1,
        "reward_coins": 100,
        "current_value": 0,
        "is_completed": False,
        "can_claim": False,
    },
    {
        "code": "streak_5_day",
        "title": "5-Day Duo Streak",
        "description": "Maintain an unbroken 5-day study streak with your accountability partner.",
        "category": "streak",
        "target_value": 5,
        "reward_coins": 60,
        "current_value": 0,
        "is_completed": False,
        "can_claim": False,
    },
    {
        "code": "study_time_60m",
        "title": "Deep Focus (60m)",
        "description": "Log at least 60 active study minutes in the Self-Study Hub today.",
        "category": "study_time",
        "target_value": 60,
        "reward_coins": 40,
        "current_value": 0,
        "is_completed": False,
        "can_claim": False,
    },
    {
        "code": "practice_100q",
        "title": "Question Grinder",
        "description": "Complete 100 CBT or practice questions across your courses.",
        "category": "questions",
        "target_value": 100,
        "reward_coins": 50,
        "current_value": 0,
        "is_completed": False,
        "can_claim": False,
    },
    {
        "code": "win_duel",
        "title": "Duel Victor",
        "description": "Win a 15-question Quickfire Duel against your study partner.",
        "category": "duel",
        "target_value": 1,
        "reward_coins": 50,
        "current_value": 0,
        "is_completed": False,
        "can_claim": False,
    },
    {
        "code": "share_pack",
        "title": "Knowledge Sharer",
        "description": "Share a custom study pack with your accountability partner.",
        "category": "sharing",
        "target_value": 1,
        "reward_coins": 20,
        "current_value": 0,
        "is_completed": False,
        "can_claim": False,
    },
]


_LAST_KNOWN_COINS = 0


async def get_platform_objectives_api(token: str) -> dict:
    global _LAST_KNOWN_COINS
    url = f"{api_url}/objectives"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                # Remote deployment pending or route not yet propagated on cloud host
                return {
                    "status": "success",
                    "coins_balance": _LAST_KNOWN_COINS,
                    "objectives": DEFAULT_PRELIM_OBJECTIVES,
                }
            resp.raise_for_status()
            data = resp.json()
            # If backend returned no objectives list, fallback to defaults
            if not data.get("objectives"):
                data["objectives"] = DEFAULT_PRELIM_OBJECTIVES
            if "coins_balance" in data:
                _LAST_KNOWN_COINS = data["coins_balance"]
            return data
    except Exception as e:
        return {
            "status": "success",
            "coins_balance": _LAST_KNOWN_COINS,
            "objectives": DEFAULT_PRELIM_OBJECTIVES,
            "offline_mode": True,
        }


async def claim_objective_reward_api(token: str, objective_code: str) -> dict:
    url = f"{api_url}/objectives/{objective_code}/claim"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.post(url, headers=headers)
            if resp.status_code == 404:
                return {"status": "error", "message": "Objective claiming requires backend deployment to cloud."}
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        detail = "Failed to claim reward"
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return {"status": "error", "message": detail}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def get_coin_wallet_ledger_api(token: str, limit: int = 50) -> dict:
    url = f"{api_url}/objectives/wallet/ledger"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=ssl_context) as client:
            resp = await client.get(url, headers=headers, params={"limit": limit})
            if resp.status_code == 404:
                return {"status": "success", "balance": 0, "transactions": []}
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"status": "success", "balance": 0, "transactions": []}
