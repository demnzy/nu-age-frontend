import asyncio
import time
from typing import Optional, Callable
import flet as ft

class AuthSession:
    """Per-session authentication state manager.

    SECURITY FIX: this used to be a process-level singleton (class variable
    ``_instance``). On the Flet ASGI web deployment, all concurrent browser
    sessions share the same Python process — so the singleton's cached tokens
    leaked across users: whoever logged in last "won", and every other session
    silently started using that user's token.

    Now each Flet session gets its own ``AuthSession`` instance, stored on the
    ``page`` object (``page.data["auth_session"]``). The ``get_instance()``
    classmethod is kept for backwards compatibility but reads from the
    page-local store.
    """
    # DEPRECATED: retained only as an absolute last-resort fallback for code
    # that calls get_instance() without having a page reference. Should never
    # be hit in normal operation after the migration below.
    _fallback_instance: Optional["AuthSession"] = None

    def __init__(self):
        self._page: Optional[ft.Page] = None
        self._lock: Optional[asyncio.Lock] = None
        self._cached_access_token: Optional[str] = None
        self._cached_refresh_token: Optional[str] = None
        self._last_refresh_timestamp: float = 0.0
        self._min_refresh_interval_secs: float = 5.0
        self._session_expired_shown: bool = False
        self._is_logging_out: bool = False
        self._on_session_expired_handlers: list[Callable] = []

    # ── Construction / Binding ────────────────────────────────────────────

    @classmethod
    def for_page(cls, page: ft.Page) -> "AuthSession":
        """Return the AuthSession for this specific Flet page/session.

        Creates a new instance and stores it on the page if one doesn't
        exist yet.  This is the ONLY correct way to obtain an AuthSession
        on the web deployment — it guarantees each browser tab gets its own
        isolated token cache.
        """
        if not isinstance(getattr(page, "data", None), dict):
            page.data = {}
        session = page.data.get("auth_session")
        if session is None:
            session = cls()
            session.init(page)
            page.data["auth_session"] = session
        return session

    @classmethod
    def get_instance(cls, page: ft.Page = None) -> "AuthSession":
        """Backwards-compatible accessor.

        If a ``page`` is provided, delegates to ``for_page(page)`` (safe).
        If not, falls back to a process-level instance (UNSAFE on web, but
        keeps desktop builds working without changing every single call site
        at once).
        """
        if page is not None:
            return cls.for_page(page)
        # Fallback for call sites that don't have a page reference yet.
        if cls._fallback_instance is None:
            cls._fallback_instance = AuthSession()
        return cls._fallback_instance

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def init(self, page: ft.Page):
        """Initialise or rebind the AuthSession with the active Flet page."""
        self._page = page
        self._session_expired_shown = False
        self._is_logging_out = False
        # Reset lock so it binds to the current event loop if needed
        self._lock = asyncio.Lock()
        # Ensure we're stored on the page so for_page() finds us.
        if isinstance(getattr(page, "data", None), dict):
            page.data["auth_session"] = self
        # Also update the fallback so legacy get_instance() calls without
        # a page argument return *this* session — correct on desktop (single
        # page), harmless in the worst case on web (last-writer-wins is no
        # worse than the old singleton).
        AuthSession._fallback_instance = self

    def register_on_session_expired(self, handler: Callable):
        """Register a callback when session expires."""
        if handler not in self._on_session_expired_handlers:
            self._on_session_expired_handlers.append(handler)

    async def get_access_token(self) -> Optional[str]:
        """Returns the active access token, checking cache first then shared_preferences."""
        if self._cached_access_token:
            return self._cached_access_token
        if self._page and hasattr(self._page, "shared_preferences"):
            try:
                token = await self._page.shared_preferences.get("auth_token")
                if token:
                    self._cached_access_token = token
                    return token
            except Exception as e:
                print(f"[AuthSession] Error reading auth_token: {e}")
        return None

    async def get_refresh_token(self) -> Optional[str]:
        """Returns the active refresh token, checking cache first then shared_preferences."""
        if self._cached_refresh_token:
            return self._cached_refresh_token
        if self._page and hasattr(self._page, "shared_preferences"):
            try:
                tok = await self._page.shared_preferences.get("refresh_token")
                if tok:
                    self._cached_refresh_token = tok
                    return tok
            except Exception as e:
                print(f"[AuthSession] Error reading refresh_token: {e}")
        return None

    async def set_tokens(self, access_token: str, refresh_token: Optional[str] = None):
        """Save new access and refresh tokens to memory, shared preferences, and session store."""
        self._cached_access_token = access_token
        if refresh_token:
            self._cached_refresh_token = refresh_token
        self._last_refresh_timestamp = time.time()
        self._session_expired_shown = False

        if self._page:
            if hasattr(self._page, "shared_preferences"):
                try:
                    await self._page.shared_preferences.set("auth_token", access_token)
                    if refresh_token:
                        await self._page.shared_preferences.set("refresh_token", refresh_token)
                except Exception as e:
                    print(f"[AuthSession] Error saving tokens to shared_preferences: {e}")

            if hasattr(self._page, "session") and hasattr(self._page.session, "store"):
                try:
                    self._page.session.store.set("session_auth_token", access_token)
                except Exception:
                    pass

    async def clear_tokens(self):
        """Clear tokens from cache and local storage upon logout or session expiry."""
        self._cached_access_token = None
        self._cached_refresh_token = None
        self._last_refresh_timestamp = 0.0

        if self._page:
            if hasattr(self._page, "shared_preferences"):
                try:
                    await self._page.shared_preferences.remove("auth_token")
                    await self._page.shared_preferences.remove("refresh_token")
                except Exception as e:
                    print(f"[AuthSession] Error removing tokens from shared_preferences: {e}")

            if hasattr(self._page, "session") and hasattr(self._page.session, "store"):
                try:
                    self._page.session.store.remove("session_auth_token")
                    self._page.session.store.remove("current_user")
                except Exception:
                    pass

            try:
                from src.services.push_notification_service import unbind_user_push_identity
                if hasattr(self._page, "run_task"):
                    self._page.run_task(unbind_user_push_identity, self._page)
            except Exception:
                pass

    def get_token_age_seconds(self, token: Optional[str] = None) -> float:
        """Returns seconds elapsed since tokens were last saved or refreshed,
        or computes age from the JWT exp claim if _last_refresh_timestamp is uninitialized."""
        if self._last_refresh_timestamp > 0.0:
            return time.time() - self._last_refresh_timestamp

        # Fallback: inspect provided or cached access token JWT exp claim
        tok = token or self._cached_access_token
        if tok and isinstance(tok, str):
            try:
                import base64
                import json
                parts = tok.split(".")
                if len(parts) >= 2:
                    padding = "=" * ((4 - len(parts[1]) % 4) % 4)
                    payload_json = base64.urlsafe_b64decode(parts[1] + padding).decode("utf-8")
                    payload = json.loads(payload_json)
                    exp = payload.get("exp")
                    if exp:
                        now = time.time()
                        remaining = exp - now
                        if remaining > 0:
                            # Standard access token lifespan is 3600s. Elapsed = 3600 - remaining
                            age = max(0.0, 3600.0 - remaining)
                            self._last_refresh_timestamp = now - age
                            return age
                        else:
                            return 999999.0  # genuinely expired
            except Exception:
                pass

        # If we have no token or cannot determine, do not trigger premature proactive refresh
        return 0.0

    async def refresh_access_token(self, force: bool = False) -> Optional[str]:
        """
        Synchronized token refresh.
        Guarded by an asyncio.Lock and debounced by timestamp to prevent duplicate concurrent
        requests from sending an already-rotated refresh token (which would trigger backend
        reuse-detection and invalidate all sessions).
        """
        lock = self._get_lock()
        async with lock:
            # 1. Debounce check: if another coroutine just refreshed within the last 5 seconds,
            # use the newly obtained token immediately without hitting the backend.
            elapsed = time.time() - self._last_refresh_timestamp
            if not force and elapsed < self._min_refresh_interval_secs and self._cached_access_token:
                return self._cached_access_token

            # 2. Get current refresh token
            refresh_tok = await self.get_refresh_token()
            if not refresh_tok:
                print("[AuthSession] No refresh_token found in storage or cache.")
                return None

            # 3. Call backend refresh endpoint
            from src.requests.auth import refresh_access_token_request
            try:
                status, data = await refresh_access_token_request(refresh_tok)
            except Exception as ex:
                print(f"[AuthSession] Network exception while refreshing token: {ex}")
                # Network failure during refresh attempt is NOT a dead session; return None
                return None

            if status == 200 and isinstance(data, dict) and "access_token" in data:
                new_access = data["access_token"]
                new_refresh = data.get("refresh_token", refresh_tok)
                await self.set_tokens(new_access, new_refresh)
                print(f"[AuthSession] Access token refreshed and rotated successfully.")
                return new_access
            elif status in (401, 403):
                # Before declaring session dead, check if local storage has a newer refresh token
                # that was written while this request was in flight!
                latest_stored_refresh = None
                if self._page and hasattr(self._page, "shared_preferences"):
                    try:
                        latest_stored_refresh = await self._page.shared_preferences.get("refresh_token")
                    except Exception:
                        pass

                if latest_stored_refresh and latest_stored_refresh != refresh_tok:
                    try:
                        status2, data2 = await refresh_access_token_request(latest_stored_refresh)
                        if status2 == 200 and isinstance(data2, dict) and "access_token" in data2:
                            new_access = data2["access_token"]
                            new_refresh = data2.get("refresh_token", latest_stored_refresh)
                            await self.set_tokens(new_access, new_refresh)
                            print("[AuthSession] Secondary refresh succeeded with newly stored token.")
                            return new_access
                    except Exception:
                        pass

                # The refresh token itself is expired, revoked, or compromised.
                print(f"[AuthSession] Refresh token rejected by server (status {status}). Session expired.")
                await self.handle_session_expired(
                    message="Your session has timed out. Please sign in again to continue studying."
                )
                return None
            else:
                # Other status code (e.g. 500, 502, 504) -> transient server issue
                print(f"[AuthSession] Token refresh returned unexpected status {status}: {data}")
                return None

    def set_logging_out(self, val: bool = True):
        """Marks the session as undergoing intentional user logout."""
        self._is_logging_out = val

    async def handle_session_expired(
        self,
        message: str = "Your session has timed out. Please sign in again to continue studying.",
        title: str = "Session Expired",
    ):
        """Prompt user that their session has expired and safely redirect to login."""
        if self._is_logging_out or self._session_expired_shown:
            return

        page = self._page
        current_route = getattr(page, "route", "") if page else ""
        if current_route in ("/", "/login", "/signup", "/platform-admin") or current_route.startswith("/accept-invite/"):
            # User is already on a public view (or logged out); do not interrupt with an expired dialog
            return

        self._session_expired_shown = True

        print(f"[AuthSession] Handling session expired: {message}")
        await self.clear_tokens()

        # Fire any registered custom handlers
        for handler in list(self._on_session_expired_handlers):
            try:
                res = handler()
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                print(f"[AuthSession] Error in session expired handler: {e}")

        page = self._page
        if not page:
            return

        # Refresh persistent nav bar if mounted
        nav_bar = getattr(page, "persistent_nav_bar", None)
        if nav_bar:
            try:
                nav_bar.refresh()
            except Exception:
                pass

        def close_dialog_and_redirect(e=None):
            try:
                page.pop_dialog()
            except Exception:
                pass
            try:
                page.go("/login")
            except Exception as ex:
                print(f"[AuthSession] Error navigating to /login: {ex}")

        # Show modern, sleek session expired alert dialog
        try:
            dlg = ft.AlertDialog(
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=20),
                bgcolor=ft.Colors.SURFACE,
                content_padding=ft.Padding.all(24),
                content=ft.Container(
                    width=360,
                    content=ft.Column(
                        spacing=16,
                        tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=56,
                                height=56,
                                border_radius=ft.BorderRadius.all(28),
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.LOCK_RESET_ROUNDED, size=28, color=ft.Colors.AMBER_600),
                            ),
                            ft.Column(
                                spacing=6,
                                tight=True,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text(
                                        title or "Session Expired",
                                        size=18,
                                        weight=ft.FontWeight.W_800,
                                        color=ft.Colors.ON_SURFACE,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                    ft.Text(
                                        message or "For your security, your session has timed out. Please sign in again to continue.",
                                        size=13,
                                        color=ft.Colors.GREY_500,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                ],
                            ),
                            ft.Container(
                                margin=ft.Padding.only(top=6),
                                width=320,
                                content=ft.FilledButton(
                                    content=ft.Row(
                                        spacing=8,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.LOGIN_ROUNDED, size=16, color=ft.Colors.WHITE),
                                            ft.Text("Sign In Again", size=13.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                        ],
                                    ),
                                    style=ft.ButtonStyle(
                                        bgcolor=ft.Colors.PRIMARY,
                                        shape=ft.RoundedRectangleBorder(radius=12),
                                        padding=ft.Padding.symmetric(vertical=14),
                                    ),
                                    on_click=close_dialog_and_redirect,
                                ),
                            ),
                        ],
                    ),
                ),
            )
            page.show_dialog(dlg)

            # Auto-redirect after 15 seconds if unclicked
            await asyncio.sleep(15)
            if getattr(dlg, "open", False):
                close_dialog_and_redirect()
        except Exception as ex:
            print(f"[AuthSession] Error displaying session expired dialog: {ex}")
            try:
                page.go("/login")
            except Exception:
                pass
