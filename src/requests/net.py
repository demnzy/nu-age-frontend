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
    "/users/auth/logout",
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

        # Sanitize malformed or empty Bearer headers to avoid httpx LocalProtocolError: Illegal header value b'Bearer '
        if auth_header and auth_header.startswith("Bearer "):
            raw_tok = auth_header[7:].strip()
            if not raw_tok or raw_tok in ("None", "null", "undefined"):
                if active_token and active_token not in ("None", "null", "undefined"):
                    request.headers["Authorization"] = f"Bearer {active_token}"
                else:
                    if "authorization" in request.headers:
                        del request.headers["authorization"]
                    if "Authorization" in request.headers:
                        del request.headers["Authorization"]
            elif active_token and raw_tok != active_token:
                request.headers["Authorization"] = f"Bearer {active_token}"
        elif not auth_header and active_token and active_token not in ("None", "null", "undefined"):
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

_SHARED_LIMITS = httpx.Limits(
    max_keepalive_connections=25,
    max_connections=60,
    keepalive_expiry=60.0,
)
_DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=8.0)
_shared_pool_client: Optional[_OriginalAsyncClient] = None


def _get_shared_client() -> _OriginalAsyncClient:
    """
    Returns a process-wide persistent httpx.AsyncClient that maintains warm
    TCP + TLS 1.3 keep-alive connections across all API requests.
    """
    global _shared_pool_client
    if _shared_pool_client is None or _shared_pool_client.is_closed:
        _shared_pool_client = _OriginalAsyncClient(
            verify=ssl_context,
            auth=TokenRefreshAuth(),
            limits=_SHARED_LIMITS,
            timeout=_DEFAULT_TIMEOUT,
        )
    return _shared_pool_client


class AsyncClient:
    """
    Connection-pooling wrapper around the shared persistent _OriginalAsyncClient.
    All 290+ `async with httpx.AsyncClient(...) as client:` call sites across the
    codebase reuse the warm TCP/TLS connection pool instead of performing a fresh
    TCP + SSL handshake on every single request.
    """
    def __init__(self, *args, **kwargs):
        self._timeout = kwargs.get("timeout", httpx.USE_CLIENT_DEFAULT)
        self._follow_redirects = kwargs.get("follow_redirects", httpx.USE_CLIENT_DEFAULT)
        self._default_headers = kwargs.get("headers")
        self._custom_auth = kwargs.get("auth", httpx.USE_CLIENT_DEFAULT)

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        # Intentionally do NOT close the shared connection pool on context exit
        pass

    async def aclose(self) -> None:
        pass

    def _merge_kwargs(self, kwargs: dict) -> dict:
        if "timeout" not in kwargs and self._timeout is not httpx.USE_CLIENT_DEFAULT:
            kwargs["timeout"] = self._timeout
        if "follow_redirects" not in kwargs and self._follow_redirects is not httpx.USE_CLIENT_DEFAULT:
            kwargs["follow_redirects"] = self._follow_redirects
        if "auth" not in kwargs and self._custom_auth is not httpx.USE_CLIENT_DEFAULT:
            kwargs["auth"] = self._custom_auth
        if self._default_headers:
            merged_hdrs = dict(self._default_headers)
            if "headers" in kwargs and kwargs["headers"]:
                merged_hdrs.update(kwargs["headers"])
            kwargs["headers"] = merged_hdrs
        return kwargs

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        client = _get_shared_client()
        return await client.request(method, url, **self._merge_kwargs(kwargs))

    async def get(self, url: str, **kwargs) -> httpx.Response:
        client = _get_shared_client()
        return await client.get(url, **self._merge_kwargs(kwargs))

    async def post(self, url: str, **kwargs) -> httpx.Response:
        client = _get_shared_client()
        return await client.post(url, **self._merge_kwargs(kwargs))

    async def put(self, url: str, **kwargs) -> httpx.Response:
        client = _get_shared_client()
        return await client.put(url, **self._merge_kwargs(kwargs))

    async def patch(self, url: str, **kwargs) -> httpx.Response:
        client = _get_shared_client()
        return await client.patch(url, **self._merge_kwargs(kwargs))

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        client = _get_shared_client()
        return await client.delete(url, **self._merge_kwargs(kwargs))

    async def head(self, url: str, **kwargs) -> httpx.Response:
        client = _get_shared_client()
        return await client.head(url, **self._merge_kwargs(kwargs))

    async def options(self, url: str, **kwargs) -> httpx.Response:
        client = _get_shared_client()
        return await client.options(url, **self._merge_kwargs(kwargs))

    def stream(self, method: str, url: str, **kwargs):
        client = _get_shared_client()
        return client.stream(method, url, **self._merge_kwargs(kwargs))


def auth_headers(token: Optional[str] = None) -> dict:
    """
    Returns a clean Authorization header dict if token is non-empty and valid,
    or an empty dict to prevent 'Illegal header value b'Bearer '' protocol crashes.
    """
    if token and str(token).strip() and str(token).strip() not in ("None", "null", "undefined"):
        return {"Authorization": f"Bearer {str(token).strip()}"}
    return {}


# Patch httpx.AsyncClient so any module doing `httpx.AsyncClient(...)`
# automatically inherits persistent connection pooling, SSL context, and token refresh.
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
    retry on 401 over the shared persistent connection pool.
    """
    hdrs = dict(headers or {})
    if token and str(token).strip() and str(token).strip() not in ("None", "null", "undefined"):
        hdrs["Authorization"] = f"Bearer {str(token).strip()}"
    elif "Authorization" in hdrs and not hdrs["Authorization"].replace("Bearer ", "").strip():
        del hdrs["Authorization"]

    auth = kwargs.pop("auth", TokenRefreshAuth(token=token))
    kwargs.pop("verify", None)
    if timeout is not None:
        kwargs["timeout"] = timeout

    client = _get_shared_client()
    return await client.request(method, url, headers=hdrs, auth=auth, **kwargs)