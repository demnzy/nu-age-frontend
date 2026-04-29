import httpx

import os
from dotenv import load_dotenv
load_dotenv()
api_url = os.getenv("API_URL")

async def get_plans_config(token: str) -> dict:
    url = f"{api_url}/subscription/plans/config"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

async def get_subscription_status(token: str) -> dict:
    url = f"{api_url}/subscription/status"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()