"""
Shared network setup for all request modules.

Why this exists:
On Android, ssl.create_default_context() (which httpx uses by default) tries
to read the OS certificate store. That path doesn't exist inside the
Flet/serious_python Android build, so every httpx.AsyncClient() call was
crashing with:

    FileNotFoundError: [Errno 2] No such file or directory
    File ".../ssl.py", line 717, in create_default_context

Fix: build the SSL context once from certifi's bundled cacert.pem (which
*is* packaged with the app) and pass it to every client via verify=.

Resilience Enhancement:
Automatic 401 interception and token refresh:
When the access token expires (60-minute lifetime), API calls across the app
receive a 401 Unauthorized. TokenRefreshAuth intercepts this, coordinates with
AuthSession to execute a synchronized token refresh using the stored refresh_token,
updates the Authorization header with the new access token, and retries the
original request seamlessly.
"""
import ssl
from typing import Optional
import certifi
import httpx

ssl_context = ssl.create_default_context(cafile=certifi.where())

AUTH_BYPASS_PATHS = (
    "/users/auth/login",
    "/users/auth/refresh",
    "/users/auth/register",
    "/users/auth/verify-email",
    "/users/auth/resend-verification-otp",
    "/users/auth/reset-password",
    "/users/auth/verify-password",
    "/users/auth/logout-all",
)


class TokenRefreshAuth(httpx.Auth):
    """
    Transparent httpx.Auth handler that intercepts 401 Unauthorized responses
    on authenticated endpoints, coordinates a mutex-synchronized token refresh
    via AuthSession, updates the Authorization header, and retries the request once.
    """
    def __init__(self, token: Optional[str] = None):
        self.token = token

    async def async_auth_flow(self, request: httpx.Request):
        from src.services.auth_session import AuthSession
        # No page reference here (httpx auth context), but init() on each
        # Flet session already sets _fallback_instance to the per-page
        # session, so this resolves correctly for the active session.
        session = AuthSession.get_instance()

        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        active_token = self.token or await session.get_access_token()

        if not auth_header:
            if active_token:
                request.headers["Authorization"] = f"Bearer {active_token}"
        elif active_token and auth_header.startswith("Bearer "):
            passed_token = auth_header[7:].strip()
            # If the session has a newer/different active token than the stale one passed by the caller,
            # proactively use the active token to avoid unnecessary 401 round-trips.
            if passed_token != active_token:
                request.headers["Authorization"] = f"Bearer {active_token}"

        # Send request
        response = yield request

        # Only intercept 401 on authenticated API endpoints where Authorization was sent
        is_bypass = any(request.url.path.endswith(p) for p in AUTH_BYPASS_PATHS)
        has_auth = "authorization" in request.headers or "Authorization" in request.headers

        if response.status_code == 401 and not is_bypass and has_auth:
            print(f"[net.py] 401 received on {request.url.path}. Attempting synchronized token refresh...")
            new_token = await session.refresh_access_token()
            if new_token:
                request.headers["Authorization"] = f"Bearer {new_token}"
                print(f"[net.py] Retrying request to {request.url.path} with refreshed token...")
                retry_response = yield request
                print(f"[net.py] Retry response status for {request.url.path}: {retry_response.status_code}")


_OriginalAsyncClient = httpx.AsyncClient


class AsyncClient(_OriginalAsyncClient):
    """
    Custom AsyncClient that defaults to using ssl_context and TokenRefreshAuth,
    guaranteeing SSL compatibility and silent token refresh across all modules.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("verify", ssl_context)
        if "auth" not in kwargs:
            kwargs["auth"] = TokenRefreshAuth()
        super().__init__(*args, **kwargs)


# Patch httpx.AsyncClient so any module doing `httpx.AsyncClient(...)`
# automatically inherits SSL context and token refresh resilience.
httpx.AsyncClient = AsyncClient


async def authenticated_request(
    method: str,
    url: str,
    *,
    headers: Optional[dict] = None,
    token: Optional[str] = None,
    timeout: Optional[httpx.Timeout] = None,
    **kwargs
) -> httpx.Response:
    """
    Convenience helper for making single authenticated requests with automatic
    retry on 401.
    """
    hdrs = dict(headers or {})
    if token:
        hdrs["Authorization"] = f"Bearer {token}"

    auth = kwargs.pop("auth", TokenRefreshAuth(token=token))
    verify = kwargs.pop("verify", ssl_context)

    async with _OriginalAsyncClient(verify=verify, auth=auth, timeout=timeout) as client:
        return await client.request(method, url, headers=hdrs, **kwargs)