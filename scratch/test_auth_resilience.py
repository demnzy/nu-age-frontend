import sys
import os
sys.path.insert(0, os.path.abspath("."))
import asyncio
import json
import httpx
from unittest.mock import MagicMock, AsyncMock
from src.services.auth_session import AuthSession
from src.requests.net import TokenRefreshAuth, AsyncClient, AUTH_BYPASS_PATHS

async def run_tests():
    print("=== TEST 1: TokenRefreshAuth retries on 401 with refreshed token ===")
    mock_page = MagicMock()
    mock_shared_prefs = AsyncMock()
    mock_page.shared_preferences = mock_shared_prefs

    stored_prefs = {
        "auth_token": "expired_access_token_123",
        "refresh_token": "valid_refresh_token_456"
    }
    async def fake_get(k):
        return stored_prefs.get(k)
    async def fake_set(k, v):
        stored_prefs[k] = v
    async def fake_remove(k):
        stored_prefs.pop(k, None)
    mock_shared_prefs.get.side_effect = fake_get
    mock_shared_prefs.set.side_effect = fake_set
    mock_shared_prefs.remove.side_effect = fake_remove

    session = AuthSession.get_instance()
    session.init(mock_page)

    backend_refresh_called = 0

    # Handler simulating API server
    def api_transport_handler(request: httpx.Request):
        nonlocal backend_refresh_called
        path = request.url.path
        auth = request.headers.get("Authorization")

        if path == "/users/auth/refresh":
            backend_refresh_called += 1
            body = json.loads(request.content.decode("utf-8"))
            if body.get("refresh_token") == "valid_refresh_token_456":
                return httpx.Response(200, json={
                    "access_token": "new_fresh_token_789",
                    "refresh_token": "rotated_refresh_token_999",
                    "type": "Bearer"
                })
            else:
                return httpx.Response(401, json={"detail": "Invalid refresh token"})

        if path == "/courses":
            if auth == "Bearer new_fresh_token_789":
                return httpx.Response(200, json=[{"id": 1, "title": "Advanced Python"}])
            else:
                return httpx.Response(401, json={"detail": "Token expired"})

        return httpx.Response(404)

    mock_transport = httpx.MockTransport(api_transport_handler)

    # Monkeypatch refresh_access_token_request's internal call to use our transport
    import src.requests.auth as auth_mod
    original_refresh = auth_mod.refresh_access_token_request
    async def mocked_refresh(ref_tok):
        async with httpx.AsyncClient(transport=mock_transport, auth=None) as c:
            r = await c.post(f"{auth_mod.api_url}/users/auth/refresh", json={"refresh_token": ref_tok})
            return r.status_code, r.json()
    auth_mod.refresh_access_token_request = mocked_refresh

    try:
        # Call with expired token
        async with AsyncClient(transport=mock_transport) as client:
            resp = await client.get(
                "https://api.nu-age.name.ng/courses",
                headers={"Authorization": "Bearer expired_access_token_123"}
            )
            print("Response status:", resp.status_code)
            print("Response body:", resp.json())
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
            assert resp.json() == [{"id": 1, "title": "Advanced Python"}]
            assert backend_refresh_called == 1, f"Expected 1 refresh call, got {backend_refresh_called}"
            assert stored_prefs["auth_token"] == "new_fresh_token_789"
            assert stored_prefs["refresh_token"] == "rotated_refresh_token_999"
            print("TEST 1 PASSED: 401 was intercepted, token refreshed, and 200 received!")

        print("\n=== TEST 2: Concurrent 401 requests trigger only 1 backend refresh ===")
        # Reset to expired token
        stored_prefs["auth_token"] = "expired_token_abc"
        stored_prefs["refresh_token"] = "valid_refresh_token_456"
        backend_refresh_called = 0
        session._last_refresh_timestamp = 0.0
        session._cached_access_token = "expired_token_abc"
        session._cached_refresh_token = "valid_refresh_token_456"

        async def make_call(call_id):
            async with AsyncClient(transport=mock_transport) as client:
                r = await client.get(
                    "https://api.nu-age.name.ng/courses",
                    headers={"Authorization": "Bearer expired_token_abc"}
                )
                return r.status_code, r.json()

        results = await asyncio.gather(
            make_call(1),
            make_call(2),
            make_call(3),
            make_call(4),
            make_call(5),
        )

        for status, data in results:
            assert status == 200, f"Expected 200 for concurrent call, got {status}"
        assert backend_refresh_called == 1, f"Expected exactly 1 refresh call for concurrent requests, got {backend_refresh_called}"
        print(f"TEST 2 PASSED: 5 concurrent requests resulted in exactly {backend_refresh_called} backend refresh!")

        print("\n=== TEST 3: Dead refresh token triggers session expired cleanly ===")
        stored_prefs["refresh_token"] = "dead_revoked_refresh_token"
        session._last_refresh_timestamp = 0.0
        session._cached_access_token = "expired_token_xyz"
        session._cached_refresh_token = "dead_revoked_refresh_token"

        expired_callback_fired = False
        def on_expired():
            nonlocal expired_callback_fired
            expired_callback_fired = True
        session.register_on_session_expired(on_expired)

        async with AsyncClient(transport=mock_transport) as client:
            resp = await client.get(
                "https://api.nu-age.name.ng/courses",
                headers={"Authorization": "Bearer expired_token_xyz"}
            )
            print("Dead refresh response status:", resp.status_code)
            assert resp.status_code == 401
            assert expired_callback_fired is True, "Expected on_session_expired callback to fire"
            assert stored_prefs.get("auth_token") is None, "Expected auth_token to be cleared"
            assert stored_prefs.get("refresh_token") is None, "Expected refresh_token to be cleared"
            print("TEST 3 PASSED: Dead refresh token cleanly cleared storage and fired session expired!")

    finally:
        auth_mod.refresh_access_token_request = original_refresh

    print("\nALL RESILIENCE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
