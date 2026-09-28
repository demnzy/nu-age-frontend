import asyncio
import time
from typing import Optional, Callable
import flet as ft

class AuthSession:
    _instance: Optional["AuthSession"] = None

    def __init__(self):
        self._page: Optional[ft.Page] = None
        self._lock: Optional[asyncio.Lock] = None
        self._cached_access_token: Optional[str] = None
        self._cached_refresh_token: Optional[str] = None
        self._last_refresh_timestamp: float = 0.0
        self._min_refresh_interval_secs: float = 5.0
        self._session_expired_shown: bool = False
        self._on_session_expired_handlers: list[Callable] = []

    @classmethod
    def get_instance(cls) -> "AuthSession":
        if cls._instance is None:
            cls._instance = AuthSession()
        return cls._instance

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def init(self, page: ft.Page):
        """Initialise or rebind the AuthSession with the active Flet page."""
        self._page = page
        self._session_expired_shown = False
        # Reset lock so it binds to the current event loop if needed
        self._lock = asyncio.Lock()

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

    def get_token_age_seconds(self) -> float:
        """Returns seconds elapsed since tokens were last saved or refreshed."""
        if self._last_refresh_timestamp <= 0.0:
            return 999999.0
        return time.time() - self._last_refresh_timestamp

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
                # The refresh token itself is expired, revoked, or compromised.
                print(f"[AuthSession] Refresh token rejected by server (status {status}). Session expired.")
                await self.handle_session_expired(
                    message="Your session has expired. Please log in again to continue."
                )
                return None
            else:
                # Other status code (e.g. 500, 502, 504) -> transient server issue
                print(f"[AuthSession] Token refresh returned unexpected status {status}: {data}")
                return None

    async def handle_session_expired(
        self,
        message: str = "Your session has expired. Please log in again to continue.",
        title: str = "Session expired",
    ):
        """Prompt user that their session has expired and safely redirect to login."""
        if self._session_expired_shown:
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

        # Show session expired alert dialog
        try:
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row(
                    [
                        ft.Icon(ft.Icons.LOCK_CLOCK, color=ft.Colors.PRIMARY),
                        ft.Text(title, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8,
                ),
                content=ft.Text(message),
                actions=[
                    ft.FilledButton(
                        "Log in again",
                        on_click=close_dialog_and_redirect,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dlg)

            # Auto-redirect after 4 seconds if not clicked
            await asyncio.sleep(4)
            if getattr(dlg, "open", False):
                close_dialog_and_redirect()
        except Exception as ex:
            print(f"[AuthSession] Error displaying session expired dialog: {ex}")
            try:
                page.go("/login")
            except Exception:
                pass
