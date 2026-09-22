import asyncio
import flet as ft
# Automatically mitigate CORS/COEP header restrictions for Bunny CDN videos on Web
try:
    from src.utils.web_patch import patch_flet_web_coep
    patch_flet_web_coep()
except Exception:
    pass
from src.Login import login_view
from src.course_analytics import course_analytics_view
from src.playlist_analytics import playlist_analytics_view
from src.signup import Signup_view
from src.dashboard import dashboard_view
from src.requests.auth import get_current_user_request, refresh_access_token_request
from src.courses import courses_view
from src.course_view import course_details_view
from src.profile import profile_view
from src.edit_profile import edit_profile_view
from src.org_view import organisations_view
from src.create_course import create_courses_view
from src.course_builder import course_builder_view
from src.course_settings import course_settings_view
from src.course_page import course_learner_view
from src.chat_view import chat_view
from src.self_study import self_study_view
from src.network import network_view
from src.member_profile import member_profile_view
from src.course_stats import course_stats_view
from src.member_invite_view import member_invite_view
from src.invite_members import invite_members_view
from src.offline_courses_view import offline_courses_view
from src.offline_course_page import offline_course_learner_view
from src.download_manager import is_course_downloaded
from src.progress_sync import sync_offline_progress
from src.local_db import get_local_db, has_any_downloaded_courses
from src.components.shimmer_skeletons import build_skeleton_view
from src.components.bottom_appbar import PersistentBottomAppBar
from src.notifications_view import notifications_view
import os


# ─────────────────────────────────────────────
# CENTRALIZED ERROR CLASSIFICATION / COPY
# ─────────────────────────────────────────────
#
# Single source of truth for "what kind of failure is this, and what does
# the user see for it" — used by both the route-change failure handling
# (SnackBar / session-expired dialog) AND the per-view error fallback
# screen (_error_fallback_view), so wording/behavior can't drift between
# the two. Module-level (not nested in main()) so it's usable from
# anywhere without needing page/closures.
#
# There are three KINDS of failure anywhere in this app:
#   - CONNECTIVITY: the request never got a real response — timeout, DNS
#     failure, connection refused, offline, etc. Also includes 503/504
#     specifically, because src/requests/auth.py's own functions (see
#     get_current_user_request, login_request) catch httpx.RequestError/
#     ReadTimeout internally and RETURN these codes rather than raising —
#     used for both "couldn't reach the server at all" AND "server/DB is
#     cold-starting". We deliberately don't try to split those two apart:
#     from the user's seat, both mean "can't get through right now", so
#     both get the same treatment (including the offline-courses button).
#   - SERVER: the request reached the server and got back a DIFFERENT
#     error status (500, 422, etc). Not the user's network — the backend
#     itself is unhappy about something once actually reached.
#   - BUG: the code itself raised something like TypeError/KeyError/
#     IndexError/AttributeError while handling a response that DID come
#     back successfully (e.g. `data["key"]` where `data` turned out to be
#     a string, or an unexpected response shape). This is neither the
#     user's network nor the server being down — it's a client-side
#     coding mistake. Showing "Network error" for this is actively
#     misleading (as seen: "string indices must be integers, not 'str'"
#     displayed under a wifi icon), so it gets its own honest bucket.


def classify_failure(ex: Exception = None, status: int = None) -> str:
    """Returns 'connectivity', 'server', or 'bug'."""
    if status in (503, 504):
        # IMPORTANT: in this codebase, 503/504 don't necessarily mean the
        # server responded — src/requests/auth.py's own functions (see
        # get_current_user_request, login_request) catch httpx.RequestError
        # and httpx.ReadTimeout internally and RETURN these codes as a
        # stand-in for "couldn't reach the server at all" / "timed out
        # waiting", rather than letting the exception propagate. Treating
        # every non-None status as "server" (the old behavior) meant a
        # pure connectivity failure — no data connection, DNS failure,
        # dead network — got mislabeled as "something went wrong on our
        # end" and never triggered the offline-courses escape hatch, even
        # though the actual server was never contacted.
        return "connectivity"
    if status is not None:
        # Any other status means we genuinely got an HTTP response, so
        # the connection itself is fine — this is the server's problem.
        return "server"
    if isinstance(ex, (TypeError, KeyError, IndexError, AttributeError, ValueError)):
        # These exception types almost never come from a dead connection
        # — they come from code assuming a shape/type that the actual
        # data didn't have. Treat as a bug, not a network issue.
        return "bug"
    # Everything else (ConnectionError, TimeoutError, httpx/aiohttp
    # exceptions, DNS failures, etc.) defaults to connectivity, since
    # that's overwhelmingly what "the request itself failed" means here.
    return "connectivity"


def failure_copy(kind: str, ex: Exception = None, status: int = None) -> dict:
    """What the user sees for each failure kind, in both the SnackBar
    (fell back to a previous view) and dialog/screen (nothing to fall
    back to) forms. `dev_detail` is the raw exception text — always
    available for a "Details" toggle, but never shown by default."""
    dev_detail = (str(ex) if ex else None) or (type(ex).__name__ if ex else None)

    if kind == "server":
        detail = f" (error {status})" if status is not None else ""
        return {
            "icon": ft.Icons.DNS_OUTLINED,
            "snack_message": "Server error, please try again",
            "dialog_title": "Network error",
            "dialog_message": f"Something went wrong on our end{detail}. Please try again shortly.",
            "dev_detail": dev_detail or (f"HTTP {status}" if status else None),
        }
    if kind == "bug":
        return {
            "icon": ft.Icons.BUG_REPORT_OUTLINED,
            "snack_message": "Something went wrong, please try again",
            "dialog_title": "Something went wrong",
            "dialog_message": "This page hit an unexpected problem. Please try again — if it keeps happening, let us know.",
            "dev_detail": dev_detail,
        }
    return {
        "icon": ft.Icons.WIFI_OFF,
        "snack_message": "Network error, please try again",
        "dialog_title": "Connection error",
        "dialog_message": "Couldn't reach the server. Check your connection and try again.",
        "dev_detail": dev_detail,
    }


# ─────────────────────────────────────────────
# REFRESH TOKEN HELPER
# ─────────────────────────────────────────────
#
# Attempts to use the stored refresh token to get a new access token.
# Module-level (not nested in main()) so both route_change and
# on_window_event can call it without duplicating logic — same reasoning
# as classify_failure/failure_copy above.
#
# On success: overwrites BOTH stored tokens and returns True. The refresh
# token MUST be overwritten every call — the backend rotates it on every
# use (see auth.py), and reusing an old one trips reuse-detection and logs
# the user out of every device.
#
# On failure: returns False and leaves storage untouched. This covers two
# different situations the caller may want to distinguish:
#   - network failure while attempting the refresh (not a dead session)
#   - the refresh token itself is dead: expired, revoked, or already used
# Both currently collapse to False here; callers that need to tell these
# apart check whether a refresh_token is still present in storage afterward
# (still present + refresh failed == token dead OR network blip during the
# call; absent == never had one). See route_change's 401/403 branch.
async def try_refresh_token(page: ft.Page) -> bool:
    refresh_token = await page.shared_preferences.get("refresh_token")
    if not refresh_token:
        return False

    try:
        status, data = await refresh_access_token_request(refresh_token)
    except Exception:
        # Network failure during refresh attempt — NOT a dead session.
        return False

    if status != 200:
        # Refresh token itself is dead (expired / revoked / reused).
        return False

    await page.shared_preferences.set("auth_token", data["access_token"])
    await page.shared_preferences.set("refresh_token", data["refresh_token"])
    return True


async def main(page: ft.Page):
    from src.local_db import init_local_db
    from src.download_manager import init_download_manager
    if not getattr(page, "web", False):
        await init_local_db(page)
        await init_download_manager(page)

    async def keep_alive():
        while True:
            await asyncio.sleep(30)  # Wait 30 seconds
            try:
                # Silently update an invisible text or just ping the page
                page.update()
            except Exception:
                # If the page is truly dead, break the loop
                break

    # Start the heartbeat in the background as soon as the user logs in
    page.run_task(keep_alive)
    # --- 1. THE UNIVERSAL SOURCE OF TRUTH ---
    # We define the ColorScheme AND Transitions in ONE object so they don't overwrite each other.
    page.window.icon = "icon.ico"

    # ── PERSISTENT APP SHELL & BOTTOM NAVIGATION ─────────────────────────────
    # The bottom app bar is instantiated once and mounted onto a stationary
    # App Shell View. Content above the bar transitions smoothly inside an
    # AnimatedSwitcher, completely eliminating tab sliding/flickering.
    persistent_nav_bar = PersistentBottomAppBar(page)
    page.persistent_nav_bar = persistent_nav_bar
    shell_history = []

    shell_content = ft.AnimatedSwitcher(
        content=ft.Container(expand=True),
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=180,
        reverse_duration=150,
        switch_in_curve=ft.AnimationCurve.EASE_OUT,
        switch_out_curve=ft.AnimationCurve.EASE_IN,
        expand=True,
    )

    shell_view = ft.View(
        route="/dashboard",
        bottom_appbar=persistent_nav_bar.bar,
        padding=0,
        bgcolor=ft.Colors.SURFACE,
        controls=[shell_content],
    )

    def is_shell_route(route: str) -> bool:
        if not route:
            return False
        clean = route.split("?")[0]
        if clean in ("/", "/login", "/signup", "/offline"):
            return False
        if clean.startswith("/accept-invite/"):
            return False
        if clean.startswith("/courses/") and (clean.endswith("/view") or clean.endswith("/offline")):
            return False
        if clean.startswith("/playlists/") and not (clean.endswith("/build") or clean.endswith("/settings") or clean.endswith("/analytics")):
            return False
        return True

    def view_pop(view):
        for ctrl in list(page.overlay):
            if isinstance(ctrl, ft.AlertDialog):
                ctrl.open = False
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            if top_view is shell_view:
                page.go(shell_history[-1] if shell_history else "/dashboard")
            else:
                page.go(top_view.route)
        elif len(shell_history) > 1:
            shell_history.pop()
            prev_route = shell_history.pop()
            page.go(prev_route)

    # 2. Attach it to the page event
    page.on_view_pop = view_pop
    page.fonts = {
        "inter": "/fonts/Inter_28pt-Regular.ttf",  # Local path in /assets/
        "roboto": "/fonts/Roboto_SemiCondensed-Regular.ttf",
        "montserrat": "/fonts/Montserrat-Regular.ttf",
    }
    LIGHT_THEME = ft.Theme(
        font_family="montserrat",
        color_scheme=ft.ColorScheme(
            primary="#035800",
            secondary="#37BF14",       # Refactored modules use ft.Colors.PRIMARY
            on_primary="#FAFAFAF8",
            surface="#FAFAFA",          # Refactored modules use ft.Colors.SURFACE
            on_surface="#1A1A1A",
            outline="#E0E0E0",
            scrim="#ECE5DD",
            tertiary="#E6FAE5"

        ),
        page_transitions=ft.PageTransitionsTheme(
            android="cupertino",
            ios="cupertino",
        ),
    )
    DARK_THEME = ft.Theme(
        font_family="montserrat",
        color_scheme=ft.ColorScheme(
            primary="#4CAF50",        # Lighter green — readable on dark bg
            secondary="#37BF14",      # Stays the same — pops on dark
            on_primary="#1A1717",     # Dark text on lighter green button
            surface="#252424",        # True dark surface
            on_surface="#E8E8E8",     # Soft white text
            outline="#2C2C2C",
            scrim="#302D2D",  
                    tertiary="#212121",          # Subtle borders
        ),
        page_transitions=ft.PageTransitionsTheme(
            android=ft.PageTransitionTheme.CUPERTINO,
            ios="cupertino",
        ),
    )
    splash_logo = ft.Image(
        src="Nu age new logo.png",
        width=400, height=600, fit="contain",
    )

    # --- 2. FORCE LIGHT MODE ---

    # ─────────────────────────────────────────────s
    # DARK MODE TOGGLE — the only new function
    # ─────────────────────────────────────────────

    async def apply_theme(is_dark: bool, trigger_update: bool = True):
        """Apply the correct theme and persist the preference."""
        if is_dark:
            page.theme_mode = ft.ThemeMode.DARK
            if page.theme is not LIGHT_THEME:
                page.theme = LIGHT_THEME       # used as fallback base
            if page.dark_theme is not DARK_THEME:
                page.dark_theme = DARK_THEME   # Flet uses dark_theme in dark mode
            page.bgcolor = "#121212"
            shell_view.bgcolor = "#121212"

            # Set to Dark Mode Logo
            splash_logo.src = "nu_age_black_2-removebg-preview.png"
            splash_logo.width = 300
            splash_logo.height = 500
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
            if page.theme is not LIGHT_THEME:
                page.theme = LIGHT_THEME
            if page.dark_theme is not DARK_THEME:
                page.dark_theme = DARK_THEME
            page.bgcolor = ft.Colors.SURFACE
            shell_view.bgcolor = ft.Colors.SURFACE

            # THE FIX: Explicitly reset to Light Mode Logo
            splash_logo.src = "Nu age new logo.png"
            splash_logo.width = 400
            splash_logo.height = 600

        if trigger_update:
            page.update()

    async def _persist_theme_pref(is_dark: bool):
        try:
            await page.shared_preferences.set("dark_mode", "true" if is_dark else "false")
        except Exception:
            pass

    async def toggle_dark_mode(target_is_dark: bool = None, trigger_update: bool = True):
        """
        Call this from anywhere in your app:
            await page.session.store.get("toggle_dark_mode")()
        Or expose it via page.data for global access.
        """
        if target_is_dark is not None:
            is_dark = target_is_dark
        else:
            current = await page.shared_preferences.get("dark_mode")
            is_dark = not (current == "true")
        page.run_task(_persist_theme_pref, is_dark)
        await apply_theme(is_dark, trigger_update=trigger_update)
        return is_dark

    # Store the toggle function so any view can access it
    page.data = {"toggle_dark_mode": toggle_dark_mode}

    # ─────────────────────────────────────────────
    # LOAD PERSISTED THEME PREFERENCE ON STARTUP
    # ─────────────────────────────────────────────

    saved_mode = await page.shared_preferences.get("dark_mode")
    is_dark_on_start = saved_mode == "true"
    await apply_theme(is_dark_on_start)

    page.title = "Nu-age"
    page.window_width = 400
    page.window_height = 650
    page.appbar = None

    # --- 3. SPLASH SCREEN ---

    splash_container = ft.Container(
        content=splash_logo,
        alignment=ft.Alignment(0, 0),
        expand=True,
        bgcolor=ft.Colors.SURFACE,  # Use the alias for consistency
    )

    page.add(splash_container)
    page.update()

    await asyncio.sleep(2.0)

    # Fade Out Animation
    steps = 15
    for i in range(steps, -1, -1):
        splash_logo.opacity = i / steps
        splash_logo.scale = 0.8 + (0.2 * (i / steps))
        page.update()
        await asyncio.sleep(0.04)

    page.remove(splash_container)
    page.update()

    # ─────────────────────────────────────────────
    # SKELETON LOADING HELPERS
    # ─────────────────────────────────────────────

    def _has_any_downloaded_courses() -> bool:
        # Thin wrapper around the shared check in local_db.py — kept as a
        # local name here since _error_fallback_view already calls it by
        # this name, but the actual query lives in one place (local_db.py)
        # so main.py and Login.py can't drift out of sync on what counts
        # as "something to send this person offline to".
        return has_any_downloaded_courses(page)

    def _get_downloaded_course_count() -> int:
        if getattr(page, "web", False):
            return 0
        try:
            db = get_local_db(page)
            row = db.execute("SELECT COUNT(*) FROM downloaded_courses").fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0

    def _view_offline_courses_button() -> ft.Control:
        def go_offline(e):
            page.go("/offline")

        return ft.FilledButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.DOWNLOAD_FOR_OFFLINE_ROUNDED, size=18),
                    ft.Text("View Your Downloads", weight=ft.FontWeight.W_600, size=13),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                padding=ft.Padding.symmetric(horizontal=18, vertical=12),
            ),
            on_click=go_offline,
        )

    def _error_fallback_view(route: str, ex: Exception, status: int = None) -> ft.View:
        """A sleek, modern offline and error screen used whenever a view fails to load.
        Provides a dedicated, elegant 'Offline Mode' experience when disconnected,
        offering direct one-tap access to downloaded courses, or clear diagnostics
        for server/client errors."""
        kind = classify_failure(ex, status)
        copy = failure_copy(kind, ex, status)
        is_offline = (kind == "connectivity")
        has_downloads = is_offline and _has_any_downloaded_courses()
        download_count = _get_downloaded_course_count() if has_downloads else 0

        def retry(e):
            page.run_task(route_change, None)

        def go_offline(e):
            page.go("/offline")

        # ── Technical Diagnostics Toggle ──────────────────────────────
        details_text = ft.Text(
            copy["dev_detail"] or "No further diagnostic details available.",
            size=11,
            color=ft.Colors.ON_SURFACE,
            selectable=True,
            font_family="roboto",
        )
        details_container = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("DIAGNOSTIC DETAILS", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=6,
                        tight=True,
                    ),
                    details_text,
                ],
                spacing=6,
            ),
            visible=False,
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            border_radius=10,
            width=360,
        )

        def toggle_details(e):
            details_container.visible = not details_container.visible
            toggle_icon.name = ft.Icons.KEYBOARD_ARROW_UP_ROUNDED if details_container.visible else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
            toggle_label.text = "Hide diagnostic details" if details_container.visible else "Show diagnostic details"
            details_container.update()
            toggle_button.update()

        toggle_icon = ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, size=16, color=ft.Colors.ON_SURFACE_VARIANT)
        toggle_label = ft.Text("Show diagnostic details", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500)
        toggle_button = ft.TextButton(
            content=ft.Row([toggle_icon, toggle_label], spacing=4, tight=True),
            on_click=toggle_details,
        )

        # ── Visual Badging & Hero Icon ─────────────────────────────────
        accent_color = ft.Colors.PRIMARY if is_offline else ft.Colors.ERROR
        badge_text = "OFFLINE MODE" if is_offline else ("SERVER ISSUE" if kind == "server" else "SYSTEM NOTICE")
        badge_icon = ft.Icons.WIFI_OFF_ROUNDED if is_offline else (ft.Icons.DNS_ROUNDED if kind == "server" else ft.Icons.BUG_REPORT_ROUNDED)

        badge_pill = ft.Container(
            content=ft.Row(
                [
                    ft.Container(width=6, height=6, border_radius=3, bgcolor=accent_color),
                    ft.Text(badge_text, size=11, weight=ft.FontWeight.BOLD, color=accent_color),
                ],
                tight=True,
                spacing=6,
            ),
            bgcolor=ft.Colors.with_opacity(0.10, accent_color),
            padding=ft.Padding.symmetric(horizontal=12, vertical=5),
            border_radius=20,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, accent_color)),
        )

        hero_icon_widget = ft.Container(
            width=80,
            height=80,
            border_radius=40,
            bgcolor=ft.Colors.with_opacity(0.08, accent_color),
            alignment=ft.Alignment.CENTER,
            content=ft.Container(
                width=56,
                height=56,
                border_radius=28,
                bgcolor=ft.Colors.with_opacity(0.16, accent_color),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(badge_icon, size=28, color=accent_color),
            ),
        )

        # ── Dynamic Action Section ─────────────────────────────────────
        action_elements = []

        if has_downloads:
            # Standout Hero Card for Offline Study
            action_elements.append(
                ft.Container(
                    width=360,
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.all(1.2, ft.Colors.with_opacity(0.25, ft.Colors.PRIMARY)),
                    border_radius=16,
                    padding=18,
                    shadow=ft.BoxShadow(
                        blur_radius=16,
                        color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                        offset=ft.Offset(0, 4),
                    ),
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        width=44,
                                        height=44,
                                        border_radius=12,
                                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(
                                            ft.Icons.DOWNLOAD_FOR_OFFLINE_ROUNDED,
                                            color=ft.Colors.PRIMARY,
                                            size=24,
                                        ),
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                "Downloaded Courses",
                                                size=15,
                                                weight=ft.FontWeight.BOLD,
                                                color=ft.Colors.ON_SURFACE,
                                            ),
                                            ft.Text(
                                                f"{download_count} course{'s' if download_count != 1 else ''} ready for offline study",
                                                size=12,
                                                color=ft.Colors.ON_SURFACE_VARIANT,
                                            ),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                ],
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.FilledButton(
                                content=ft.Row(
                                    [
                                        ft.Text("View Your Downloads", weight=ft.FontWeight.BOLD, size=13),
                                        ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16),
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=8,
                                ),
                                height=44,
                                width=360,
                                on_click=go_offline,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    bgcolor=ft.Colors.PRIMARY,
                                    color=ft.Colors.ON_PRIMARY,
                                ),
                            ),
                        ],
                        spacing=14,
                    ),
                )
            )
            # Secondary reconnection button
            action_elements.append(
                ft.OutlinedButton(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.REFRESH_ROUNDED, size=16),
                            ft.Text("Try Reconnecting", weight=ft.FontWeight.W_600, size=13),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    height=42,
                    width=360,
                    on_click=retry,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        side=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.OUTLINE)),
                    ),
                )
            )
        else:
            # No offline downloads available or non-connectivity error
            primary_text = "Retry Connection" if is_offline else "Try Again"
            action_elements.append(
                ft.FilledButton(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.REFRESH_ROUNDED, size=18),
                            ft.Text(primary_text, weight=ft.FontWeight.BOLD, size=14),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    height=46,
                    width=360,
                    on_click=retry,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        bgcolor=ft.Colors.PRIMARY,
                        color=ft.Colors.ON_PRIMARY,
                    ),
                )
            )
            if is_offline and not getattr(page, "web", False):
                action_elements.append(
                    ft.Text(
                        "Tip: Download courses while online to access them anytime without internet.",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    )
                )

        main_card = ft.Container(
            width=400,
            bgcolor=ft.Colors.SURFACE,
            border_radius=20,
            padding=ft.Padding.symmetric(horizontal=24, vertical=32),
            shadow=ft.BoxShadow(
                blur_radius=24,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 8),
            ),
            content=ft.Column(
                [
                    badge_pill,
                    hero_icon_widget,
                    ft.Text(
                        "You're Offline" if is_offline else copy["dialog_title"],
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    ft.Text(
                        "No internet connection was detected. You can still study any courses you've previously downloaded."
                        if (is_offline and has_downloads)
                        else copy["dialog_message"],
                        size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=6),
                    *action_elements,
                    ft.Container(height=4),
                    toggle_button,
                    details_container,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
        )

        return ft.View(
            route=route,
            bgcolor=ft.Colors.SURFACE,
            padding=16,
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Container(
                        expand=True,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            [main_card],
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            scroll=ft.ScrollMode.ADAPTIVE,
                        ),
                    ),
                ),
            ],
            vertical_alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    def skeleton_view(route: str, rows: int = 5) -> ft.View:
        """Full-screen shimmer placeholder shown instantly while the real
        view loads. Uses 1-to-1 accurate grey shimmer skeletons matching
        the destination route, excluding top app bars, and responsive to
        mobile/desktop layouts."""
        return build_skeleton_view(route, page)

    async def run_shimmer(boxes, view: ft.View):
        """Continuously pulses each box's opacity out of phase, producing a
        travelling shimmer. Stops instantly when cancelled by load_view()
        (the normal path), or on its own if `view` somehow stops being the
        active/top view without an explicit cancel."""
        phase = 0
        try:
            while page.views and page.views[-1] is view:
                for i, box in enumerate(boxes):
                    # Offset each box's phase so the shimmer appears to
                    # travel down the screen rather than blinking in unison.
                    on = (i + phase) % 3 == 0
                    box.opacity = 0.65 if on else 0.3
                page.update()
                phase += 1
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            # Expected: load_view() cancels us the instant the real view
            # is ready. Exit immediately, no cleanup needed.
            pass
        except Exception:
            # View/page torn down mid-animation for some other reason —
            # stop quietly rather than crashing the background task.
            pass

    def _strip_redundant_appbars(controls: list) -> list:
        """Safeguard: filters out any ft.BottomAppBar or ft.AppBar instances
        accidentally included in controls, preventing stacked/duplicate app bars
        when views are mounted inside the persistent shell or as standalone pages."""
        if not controls:
            return []
        cleaned = []
        for c in controls:
            if isinstance(c, (ft.BottomAppBar, ft.AppBar)):
                continue
            if isinstance(c, ft.Container) and isinstance(getattr(c, "content", None), (ft.BottomAppBar, ft.AppBar)):
                continue
            if isinstance(c, ft.Column) and hasattr(c, "controls") and c.controls:
                c.controls = [child for child in c.controls if not isinstance(child, (ft.BottomAppBar, ft.AppBar))]
            cleaned.append(c)
        return cleaned

    async def load_view(
        coro,
        route: str,
        existing_skeleton=None,
        existing_shimmer_task=None,
        on_failure=None,
    ):
        """Push an animated skeleton immediately so the UI never sits blank,
        then replace it with the real view the instant its data is ready.
        If a skeleton is already showing (e.g. one pushed during the auth
        check that ran before this), reuse it instead of flickering closed
        and reopening a fresh one.

        on_failure(route, ex) -> bool, if given, is awaited when the view
        fails to load. It should push whatever should be shown instead
        (typically: restore the previous view) directly onto page.views,
        and return True if it did so (meaning load_view should NOT also
        push its own dedicated error screen) or False if there was nothing
        to fall back to (meaning load_view should show the error screen).
        May be a sync or async callable — both are supported."""
        in_shell = is_shell_route(route)
        shimmer_task = None
        skel = None

        coro_task = asyncio.ensure_future(coro)

        if existing_skeleton is not None:
            skel = existing_skeleton
            shimmer_task = existing_shimmer_task
        else:
            # Check if coro takes longer than 350ms (e.g. cold start).
            # Normal in-memory view construction completes in <100ms and transitions
            # directly and smoothly without jarring skeleton flicker or premature view popping.
            done, _ = await asyncio.wait([coro_task], timeout=0.35)
            if not done:
                if in_shell:
                    if shell_view not in page.views:
                        page.views.clear()
                        page.views.append(shell_view)
                    else:
                        while len(page.views) > 1 and page.views[-1] is not shell_view:
                            page.views.pop()
                    persistent_nav_bar.set_active_route(route)
                    skel = skeleton_view(route)
                    shell_content.content = ft.Container(
                        content=ft.Column(skel.controls, expand=True, spacing=0) if len(skel.controls) > 1 else (skel.controls[0] if skel.controls else ft.Container()),
                        expand=True,
                        key=f"skel_{route}",
                    )
                    page.update()
                    await asyncio.sleep(0)
                    shimmer_task = page.run_task(run_shimmer, skel.data, shell_view)
                else:
                    skel = skeleton_view(route)
                    page.views.append(skel)
                    page.update()
                    await asyncio.sleep(0)
                    shimmer_task = page.run_task(run_shimmer, skel.data, skel)

        async def handle_failure(ex: Exception):
            if shimmer_task:
                shimmer_task.cancel()

            if in_shell:
                fell_back = False
                if on_failure is not None:
                    result = on_failure(route, ex)
                    if asyncio.iscoroutine(result):
                        result = await result
                    fell_back = result

                if not fell_back:
                    err_v = _error_fallback_view(route, ex)
                    shell_view.appbar = err_v.appbar
                    shell_view.floating_action_button = err_v.floating_action_button
                    shell_content.content = ft.Container(
                        content=ft.Column(err_v.controls, expand=True, spacing=0) if len(err_v.controls) > 1 else (err_v.controls[0] if err_v.controls else ft.Container()),
                        expand=True,
                        key=f"shell_error_{route}",
                    )
                page.update()
            else:
                # Pop the skeleton first — whatever happens next (restored
                # previous view, or dedicated error screen) replaces it.
                if page.views and skel is not None and page.views[-1] is skel:
                    page.views.pop()

                fell_back = False
                if on_failure is not None:
                    result = on_failure(route, ex)
                    if asyncio.iscoroutine(result):
                        result = await result
                    fell_back = result

                if not fell_back:
                    page.views.append(_error_fallback_view(route, ex))

                page.update()

        try:
            real_view = await coro_task
        except Exception as ex:
            # The view function itself raised (e.g. an unhandled
            # ConnectTimeout deep inside its own data-fetching code).
            # Don't let this leave a blank screen — fall back gracefully.
            print(f"load_view: view coroutine raised: {ex!r}")
            import traceback
            traceback.print_exc()
            await handle_failure(ex)
            return

        if real_view is None or not isinstance(real_view, ft.View):
            # The view function swallowed its own exception internally and
            # returned None (or something invalid) instead of a real
            # ft.View — this is what produces a silent blank screen with
            # no dialog and no traceback. Treat it the same as a raised
            # exception rather than trying to render it.
            print(f"load_view: {route} view function returned {real_view!r} instead of an ft.View")
            await handle_failure(RuntimeError("This page failed to load. Please try again."))
            return

        # Stop the shimmer the instant we're done, don't wait for its
        # own loop to notice on its next 0.25s tick.
        if shimmer_task:
            shimmer_task.cancel()

        if in_shell:
            if shell_view not in page.views:
                page.views.clear()
                page.views.append(shell_view)
            else:
                while len(page.views) > 1 and page.views[-1] is not shell_view:
                    page.views.pop()

            shell_view.appbar = real_view.appbar
            shell_view.floating_action_button = real_view.floating_action_button
            default_shell_bg = "#121212" if page.theme_mode == ft.ThemeMode.DARK else ft.Colors.SURFACE
            shell_view.bgcolor = real_view.bgcolor or default_shell_bg
            shell_view.scroll = real_view.scroll
            shell_view.horizontal_alignment = real_view.horizontal_alignment
            shell_view.vertical_alignment = real_view.vertical_alignment
            shell_view.drawer = real_view.drawer
            shell_view.end_drawer = real_view.end_drawer
            shell_view.route = route

            clean_controls = _strip_redundant_appbars(real_view.controls)
            shell_content.content = ft.Container(
                content=ft.Column(clean_controls, expand=True, spacing=0) if len(clean_controls) > 1 else (clean_controls[0] if clean_controls else ft.Container()),
                expand=True,
                key=f"shell_content_{route}",
            )

            persistent_nav_bar.set_active_route(route)
            if not shell_history or shell_history[-1] != route:
                shell_history.append(route)
            page.update()
        else:
            if real_view.bottom_appbar is not None or real_view.appbar is not None:
                real_view.controls = _strip_redundant_appbars(real_view.controls)
            if page.views and skel is not None and page.views[-1] is skel:
                page.views[-1] = real_view
            else:
                page.views.append(real_view)
            page.update()

    # --- 4. ROUTING LOGIC ---
    route_change_state = {"in_flight": False, "pending_rerun": False}

    async def route_change(e):
        # Re-entrancy guard: on resume-from-background, on_window_event
        # can call route_change(None) directly at roughly the same moment
        # Flet's own on_route_change fires for the same resume. Without
        # this guard, two overlapping runs both push a skeleton and race
        # to pop/replace page.views — whichever shimmer_task.cancel() loses
        # the race leaves an orphaned shimmer animating forever over a view
        # that's already been swapped or cleared by the other run. That's
        # the "blank screen after a long time away" bug.
        #
        # BUG FIX: the original version of this guard just returned
        # immediately when a run was already in flight — silently
        # DROPPING the new navigation request rather than queuing it.
        # That's what caused "I have to tap the button multiple times":
        # a tap that landed while a previous route_change was still
        # finishing (e.g. the fallback error view's own render, or the
        # connectivity probe on a course open) did nothing at all, with
        # no feedback — the user had no way to know their tap was
        # ignored, so they just kept tapping until one landed in the gap
        # between runs. Fixed by remembering that a rerun was requested
        # and immediately re-running _route_change_inner() (against
        # whatever page.route is by then) once the in-flight run
        # finishes, instead of dropping it.
        if route_change_state["in_flight"]:
            route_change_state["pending_rerun"] = True
            return

        route_change_state["in_flight"] = True
        try:
            while True:
                route_change_state["pending_rerun"] = False
                try:
                    await _route_change_inner()
                except Exception as ex:
                    # Absolute last line of defense: nothing that happens
                    # while building/loading a view should ever be allowed
                    # to escape route_change uncaught — an uncaught
                    # exception here crashes Flet's session bootstrap
                    # itself (AttributeError on a None session), not just
                    # this one navigation.
                    print(f"route_change failed: {ex!r}")
                    try:
                        page.views.clear()
                        page.views.append(
                            ft.View(
                                route=page.route,
                                controls=[
                                    ft.Column(
                                        [
                                            ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.ERROR, size=40),
                                            ft.Text("Something went wrong loading this page.", size=16),
                                            ft.Text(str(ex), size=12, color=ft.Colors.OUTLINE),
                                            ft.FilledButton(
                                                "Go to login",
                                                on_click=lambda e: page.go("/"),
                                            ),
                                        ],
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        spacing=12,
                                    )
                                ],
                                padding=20,
                            )
                        )
                        page.update()
                    except Exception:
                        # If even the fallback error view fails to render,
                        # there's nothing more we can safely do from here.
                        pass

                if not route_change_state["pending_rerun"]:
                    break
                # A navigation request came in while we were busy — run
                # once more against the now-current page.route rather
                # than the stale one this iteration started with.
        finally:
            route_change_state["in_flight"] = False
            route_change_state["pending_rerun"] = False

    async def _route_change_inner():
        # Remember what was on screen before this navigation, so that if
        # the new route fails to load we can restore it (with an error
        # dialog on top) instead of leaving the user on a dead-end error
        # page or a blank screen.
        #
        # BUG FIX (root cause of both the login shimmer-loop and the
        # "navigation failure doesn't stay put" regression): this used to
        # do `page.views.clear()` right here, unconditionally, before we
        # even knew whether the new route would load successfully. That
        # meant:
        #   1. `previous_view` became a *removed* View instance — Flet
        #      doesn't reliably support reviving an already-torn-down view
        #      by re-appending the same object later, so "restoring" it on
        #      failure often just left the client stuck on whatever was
        #      last rendered (the shimmer).
        #   2. On the very first protected navigation after login,
        #      `previous_view` was the login view itself. If the auth
        #      check then failed (e.g. a real network hiccup — much more
        #      likely on desktop/mobile builds than on web, since they use
        #      a real HTTP client instead of the browser's fetch),
        #      "restoring" put the user BACK on the login view. If that
        #      view re-checks the stored token on mount and redirects,
        #      this re-enters route_change and repeats — the shimmer /
        #      red-error / shimmer loop you were seeing.
        #
        # Fix: never destroy the current views up front. Keep whatever is
        # already on screen, push the new skeleton ON TOP of it, and only
        # remove the old view once the new one has actually succeeded. On
        # failure, we simply pop the skeleton/error screen back off —
        # the previous view was never touched, so it's still exactly as
        # it was, no risky re-append of a stale instance required.
        previous_view = page.views[-1] if page.views else None
        previous_route = previous_view.route if previous_view is not None else None
        previous_shell_content = getattr(shell_content, "content", None)
        previous_shell_appbar = getattr(shell_view, "appbar", None)
        previous_shell_fab = getattr(shell_view, "floating_action_button", None)
        previous_shell_route = getattr(shell_view, "route", None)

        clean_route = (page.route or "").split("?")[0]
        troute = ft.TemplateRoute(clean_route)

        def is_public_route(route):
            return route in ["/", "/login", "/signup"] or route.startswith("/accept-invite/")

        def is_offline_capable_route(route):
            if getattr(page, "web", False):
                return False
            # Routes reachable without a network call succeeding, even
            # though they still need to know "which user" (so NOT lumped
            # in with is_public_route, which is for pre-login routes).
            # /offline: the downloaded-courses list, reads only SQLite.
            # /courses/{id}/learn: gets a second, offline-specific check
            # below (only skips the auth gate if THIS SPECIFIC course was
            # actually downloaded) rather than being blanket-exempted here.
            return route == "/offline"

        async def is_route_for_downloaded_course(route):
            if getattr(page, "web", False):
                return False
            c_route = (route or "").split("?")[0]
            troute_check = ft.TemplateRoute(c_route)
            if troute_check.match("/courses/:course_id/offline"):
                return is_course_downloaded(page, troute_check.course_id)
            if troute_check.match("/courses/:course_id/view"):
                return is_course_downloaded(page, troute_check.course_id)
            return False

        def show_error_dialog(message: str = "Network error, please try again", title: str = None, icon=None, offer_offline: bool = False):
            """Sleek, non-blocking error notice shown after falling back to
            the previous view. Uses a SnackBar (not a modal AlertDialog) so
            the view underneath stays fully interactable — the user can keep
            tapping around immediately, the notice just floats on top and
            dismisses itself.

            offer_offline=True adds a "Downloaded courses" action to the
            SnackBar itself. This matters because falling back to a
            previous view (the fell_back=True path in report_failure)
            previously had NO offline escape hatch at all — only the
            fell_back=False path (_error_fallback_view, shown when there's
            no previous view to restore) had the button. A connectivity
            failure mid-navigation, with a previous view to fall back to,
            showed a bare SnackBar and nothing else — which is why the
            offline button seemed to "not show" even though it existed on
            the other failure path.

            NOTE on the SnackBar API used here (verified against Flet's
            current docs, since an earlier version of this guessed wrong
            and used action_color, which doesn't exist):
            - `action` accepts either a plain str OR a full SnackBarAction
              control. We use SnackBarAction here (not the plain string
              shortcut) specifically because we want custom text_color —
              the plain-string form has no way to set that; only
              SnackBarAction exposes text_color/bgcolor directly.
            - `on_action` lives on SnackBar itself and fires for the
              plain-string form. Since we're using SnackBarAction, the
              click handler goes on SnackBarAction.on_click instead —
              SnackBar.on_action would never fire in that case.
            - Showing a SnackBar in this Flet version is
              page.show_dialog(snack), not page.overlay.append(...).
            - duration must be a Duration (or int of ms is NOT directly
              accepted per current signature — DurationValue), so we wrap
              it explicitly rather than passing a bare int.
            """
            snack_icon = icon or (ft.Icons.WIFI_OFF_ROUNDED if offer_offline else ft.Icons.ERROR_OUTLINE_ROUNDED)
            snack_content_controls = [
                ft.Icon(snack_icon, color=ft.Colors.PRIMARY if offer_offline else ft.Colors.WHITE, size=20),
                ft.Text(message, color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_500, expand=True),
            ]

            if offer_offline and _has_any_downloaded_courses():
                def go_offline(e):
                    page.go("/offline")

                snack_content_controls.append(
                    ft.FilledButton(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.DOWNLOAD_FOR_OFFLINE_ROUNDED, size=14),
                                ft.Text("View Downloads", size=12, weight=ft.FontWeight.BOLD),
                            ],
                            tight=True,
                            spacing=4,
                        ),
                        on_click=go_offline,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.ON_PRIMARY,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        ),
                    )
                )

            snack = ft.SnackBar(
                content=ft.Row(
                    snack_content_controls,
                    spacing=12,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor="#1B221E" if offer_offline else "#242424",
                duration=ft.Duration(milliseconds=5000 if offer_offline else 3000),
                behavior=ft.SnackBarBehavior.FIXED,
            )
            page.show_dialog(snack)

        # ─────────────────────────────────────────────
        # CENTRALIZED ERROR REPORTING
        # ─────────────────────────────────────────────
        #
        # Every place in this file that can fail while loading a page
        # funnels through report_failure() for what the user sees. Before
        # this, each call site hand-wrote its own message/title, which
        # made wording drift and made it easy to mislabel a bug as a
        # network error (as happened: a TypeError from bad response
        # parsing was shown to users under a wifi-off icon). The actual
        # classify_failure()/failure_copy() logic lives at module level
        # (top of file) so _error_fallback_view — which needs the same
        # copy but isn't nested inside this function — can share it too.

        async def report_failure(
            fell_back: bool,
            ex: Exception = None,
            status: int = None,
            auto_redirect_seconds: int = 6,
        ):
            """Call this after a load/auth-check has already failed and
            (if applicable) already fallen back to the previous view.
            Picks connectivity vs. server vs. bug wording automatically
            and shows the right widget:
              - fell_back=True  -> SnackBar over the restored previous view
              - fell_back=False -> blocking dialog (nothing to fall back to)
            """
            kind = classify_failure(ex, status)
            copy = failure_copy(kind, ex, status)
            if fell_back:
                show_error_dialog(
                    copy["snack_message"],
                    icon=copy["icon"],
                    offer_offline=(kind == "connectivity" and not getattr(page, "web", False)),
                )
            else:
                await show_session_expired_dialog(
                    copy["dialog_message"],
                    auto_redirect_seconds=auto_redirect_seconds,
                    title=copy["dialog_title"],
                    redirect_to_login=False,
                )

        async def restore_previous_or_fallback(route: str, ex: Exception, status: int = None):
            """On failure: if we have a previous view to go back to, restore
            it (caller shows a dialog on top). Otherwise — e.g. this was the
            very first view of the session, or the only thing we have to
            fall back to is a public/login view — show the dedicated error
            fallback screen since there's nothing safe to fall back to.

            BUG FIX: previously this re-appended the `previous_view` object
            after `page.views` had already been cleared. Flet views aren't
            reliably revivable that way once torn down client-side, which
            is why "falling back" often just left the UI stuck on whatever
            was last rendered (the shimmer). Now that we never clear
            `page.views` up front, the previous view is *still on screen*
            underneath whatever we pushed for the failed navigation — so
            "restoring" is just popping those failed layers back off,
            no re-append needed.

            We also refuse to restore into a public route (login/signup).
            That was the source of the login shimmer-loop: right after
            login, the previous view is the login screen itself. If a
            transient network error hit the very next auth check, we'd
            silently drop the user back onto login, which then re-checks
            the stored token and re-navigates to /dashboard, re-entering
            this whole flow. Since there's nothing safe to fall back to in
            that case, we show the dedicated error screen instead (with a
            Retry button) rather than bouncing back into login.
            """
            if previous_view is not None and not is_public_route(previous_route):
                # Pop everything we pushed for this failed navigation
                # (skeleton and/or error view) down to the previous view,
                # which was never removed from page.views.
                while page.views and page.views[-1] is not previous_view:
                    page.views.pop()

                if not page.views:
                    # Defensive fallback — should not normally happen since
                    # previous_view should still be in the list.
                    page.views.append(previous_view)

                # page.route currently points at the route that just failed
                # to load (e.g. "/courses"), but the view actually on screen
                # is the previous one (e.g. "/dashboard"). Keep them in sync
                # so back-navigation (on_view_pop) and any future route
                # comparisons aren't looking at a stale/wrong route.
                #
                # BUG FIX: setting page.route here only updates server-side
                # state — it does NOT tell the browser/client router that
                # the URL changed. So the browser's address bar/history is
                # left pointing at the route that just failed. The next
                # time the user taps a nav item for that same destination,
                # the client router sees "already there" (same route string
                # as its own history) and never re-fires on_route_change —
                # the tap silently does nothing. We now AWAIT push_route
                # (previously fire-and-forget via page.run_task, so a
                # failure here was invisible and the resync wasn't
                # guaranteed to happen before we told the caller "restored
                # successfully") to keep the browser's actual navigation
                # state in sync with what's really on screen.
                if previous_view is shell_view:
                    if previous_shell_content is not None:
                        shell_content.content = previous_shell_content
                    if previous_shell_appbar is not None:
                        shell_view.appbar = previous_shell_appbar
                    if previous_shell_fab is not None:
                        shell_view.floating_action_button = previous_shell_fab
                    if previous_shell_route:
                        shell_view.route = previous_shell_route
                        page.route = previous_shell_route
                        persistent_nav_bar.set_active_route(previous_shell_route)
                    else:
                        page.route = previous_view.route
                else:
                    page.route = previous_view.route

                route_change_state["pending_rerun"] = False
                if getattr(page, "web", False):
                    try:
                        await page.push_route(page.route, skip_route_change_event=True)
                    except Exception as resync_ex:
                        print(f"restore_previous_or_fallback: push_route resync failed: {resync_ex!r}")
                    finally:
                        route_change_state["pending_rerun"] = False
                return True
            else:
                # Nothing safe to fall back to (first view of the session,
                # or the only prior view was login/signup) — show the
                # dedicated error screen with a Retry button instead.
                while page.views and page.views[-1] is not previous_view:
                    page.views.pop()
                if page.views and page.views[-1] is previous_view and is_public_route(previous_route):
                    # Don't leave the public view underneath either — pop it
                    # too, since we're intentionally not restoring into it.
                    page.views.pop()
                page.views.append(_error_fallback_view(route, ex, status))
                return False

        # Tracks whether the last load_view() call fell back to a previous
        # view (vs. showing the dedicated error screen) so we know whether
        # to also pop up an explanatory dialog afterwards.
        failure_state = {"fell_back": False, "ex": None}

        async def on_view_failure(route: str, ex: Exception) -> bool:
            fell_back = await restore_previous_or_fallback(route, ex)
            failure_state["fell_back"] = fell_back
            failure_state["ex"] = ex
            return fell_back

        async def load_view_and_report(coro, route: str, skel=None, shimmer=None):
            """Thin wrapper around load_view() that also shows the
            'something went wrong' notice afterwards if it fell back to the
            previous view, so the user understands why the screen didn't
            change even though nothing crashed loudly."""
            failure_state["fell_back"] = False
            failure_state["ex"] = None
            await load_view(coro, route, skel, shimmer, on_failure=on_view_failure)
            if failure_state["fell_back"]:
                # A view's own load failed. We don't have an HTTP status
                # here (the exception came from inside the view's own
                # data-fetching code), so this always classifies as
                # "connectivity" — reasonable default, since the far more
                # common case is a timed-out/failed request deep inside
                # the view rather than a clean HTTP error response.
                await report_failure(fell_back=True, ex=failure_state["ex"])

        async def show_session_expired_dialog(
            message: str,
            auto_redirect_seconds: int = 4,
            title: str = "Session expired",
            redirect_to_login: bool = True,
        ):
            """Sleek dialog shown instead of silently kicking the user to login.
            redirect_to_login=False is used for non-auth errors (network/server)
            where we want to inform the user but not force them back to login."""

            def close_dialog(e=None):
                page.pop_dialog()
                if redirect_to_login:
                    page.go("/login")

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row(
                    [ft.Icon(ft.Icons.LOCK_CLOCK, color=ft.Colors.PRIMARY), ft.Text(title)],
                    spacing=8,
                ),
                content=ft.Text(message),
                actions=[
                    ft.FilledButton(
                        "Log in again" if redirect_to_login else "OK",
                        on_click=close_dialog,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dlg)

            # Auto-dismiss/redirect after a few seconds if they don't tap the button
            await asyncio.sleep(auto_redirect_seconds)
            if dlg.open:
                close_dialog()

        in_shell_route_flag = is_shell_route(page.route)
        current_user = page.session.store.get("current_user") if hasattr(page, "session") and hasattr(page.session, "store") else None
        cached_token = page.session.store.get("session_auth_token") if hasattr(page, "session") and hasattr(page.session, "store") else None
        stored_token = await page.shared_preferences.get("auth_token")

        needs_auth_check = (
            not is_public_route(page.route)
            and not is_offline_capable_route(page.route)
            and not await is_route_for_downloaded_course(page.route)
            and (current_user is None or not stored_token or cached_token != stored_token)
        )
        if needs_auth_check:
            # Show the skeleton IMMEDIATELY for cold-open / unverified session auth check
            # starts — otherwise on a slow connection the screen sits
            # blank during get_current_user_request(), and only pushes
            # the skeleton afterwards for the (much shorter) view fetch.
            skel = skeleton_view(page.route)
            if in_shell_route_flag:
                if shell_view not in page.views:
                    page.views.clear()
                    page.views.append(shell_view)
                else:
                    while len(page.views) > 1 and page.views[-1] is not shell_view:
                        page.views.pop()
                persistent_nav_bar.set_active_route(page.route)
                shell_content.content = ft.Container(
                    content=ft.Column(skel.controls, expand=True, spacing=0) if len(skel.controls) > 1 else (skel.controls[0] if skel.controls else ft.Container()),
                    expand=True,
                    key=f"skel_{page.route}",
                )
                page.update()
                await asyncio.sleep(0)
                shimmer_task = page.run_task(run_shimmer, skel.data, shell_view)
            else:
                page.views.append(skel)
                page.update()
                await asyncio.sleep(0)
                shimmer_task = page.run_task(run_shimmer, skel.data, skel)

            # Fast local check first — no network call needed to know
            # whether a token even exists.
            token = await page.shared_preferences.get("auth_token")

            if not token:
                shimmer_task.cancel()
                if hasattr(page, "session") and hasattr(page.session, "store"):
                    try:
                        page.session.store.clear()
                    except Exception:
                        pass
                persistent_nav_bar.refresh()
                # Pop the skeleton, but NEVER leave page.views empty here.
                # If this is the very first route of the session (cold
                # open straight into a protected route), page.views was
                # empty before the skeleton was pushed, so popping it
                # leaves nothing for the dialog to render on top of —
                # that's the "white screen after the shimmer" bug. Always
                # ensure a real view (login) is underneath the dialog.
                if in_shell_route_flag:
                    if page.views and page.views[-1] is shell_view:
                        page.views.pop()
                else:
                    if page.views and page.views[-1] is skel:
                        page.views.pop()
                if not page.views:
                    page.views.append(login_view(page))
                    page.update()
                await show_session_expired_dialog(
                    "Please log in to continue.",
                    auto_redirect_seconds=3,
                    title="Login required",
                )
                return

            # --- VALIDATE TOKEN, WITHOUT MISLABELING NON-AUTH ERRORS ---
            try:
                status, user_data = await get_current_user_request(token)
            except Exception as ex:
                # Network failure, timeout, DNS issue, etc. This is NOT a
                # session problem — do NOT delete the token. Fall back to
                # whatever was on screen before, same as a failed view load,
                # rather than stranding the user on a dialog-only screen.
                shimmer_task.cancel()
                if not in_shell_route_flag and page.views and page.views[-1] is skel:
                    page.views.pop()
                fell_back = await restore_previous_or_fallback(page.route, ex)
                page.update()
                await report_failure(fell_back=fell_back, ex=ex)
                return

            if status == 200:
                page.session.store.set("current_user", user_data)
                page.session.store.set("session_auth_token", token)
                persistent_nav_bar.refresh()
            elif status in (401, 403):
                # Access token expired/invalid — this is now the EXPECTED
                # steady state (access tokens are short-lived by design).
                # Try a silent refresh before treating this as a dead
                # session. Only fall through to session-expired if the
                # refresh token is ALSO dead (or absent).
                refreshed = await try_refresh_token(page)

                if refreshed:
                    # Retry the current-user check with the new token.
                    new_token = await page.shared_preferences.get("auth_token")
                    try:
                        status, user_data = await get_current_user_request(new_token)
                    except Exception as ex:
                        # Network failure on the retry — not a session
                        # problem, treat like any other failed view load.
                        shimmer_task.cancel()
                        if not in_shell_route_flag and page.views and page.views[-1] is skel:
                            page.views.pop()
                        fell_back = await restore_previous_or_fallback(page.route, ex)
                        page.update()
                        await report_failure(fell_back=fell_back, ex=ex)
                        return

                    if status == 200:
                        page.session.store.set("current_user", user_data)
                        page.session.store.set("session_auth_token", new_token)
                        persistent_nav_bar.refresh()
                        # Fall through to the normal view-render path below
                        # (do NOT return here) — this is now a success case.
                    else:
                        # Refreshed token STILL failed the current-user
                        # check. Shouldn't normally happen right after a
                        # successful refresh, but fail safe rather than
                        # loop — treat as a genuine session end.
                        shimmer_task.cancel()
                        if in_shell_route_flag:
                            if page.views and page.views[-1] is shell_view:
                                page.views.pop()
                        else:
                            if page.views and page.views[-1] is skel:
                                page.views.pop()
                        if not page.views:
                            page.views.append(login_view(page))
                            page.update()
                        await page.shared_preferences.remove("auth_token")
                        await page.shared_preferences.remove("refresh_token")
                        if hasattr(page, "session") and hasattr(page.session, "store"):
                            try:
                                page.session.store.clear()
                            except Exception:
                                pass
                        persistent_nav_bar.refresh()
                        await show_session_expired_dialog(
                            "Your session has ended. Please log in again to continue."
                        )
                        return
                else:
                    # Refresh didn't succeed — either there was no refresh
                    # token to begin with, or trying it failed (dead token,
                    # or a network hiccup during the refresh call itself).
                    # Same fix as the "no token" branch above: don't leave
                    # page.views empty before showing the dialog. On a cold
                    # open into a protected route (e.g. reopening the app
                    # after everything expired), page.views was empty
                    # before the skeleton was pushed, so popping it here
                    # leaves the dialog with nothing to render on top of —
                    # that's the white-screen-after-shimmer bug. Always
                    # land on a real login view underneath the dialog.
                    shimmer_task.cancel()
                    if in_shell_route_flag:
                        if page.views and page.views[-1] is shell_view:
                            page.views.pop()
                    else:
                        if page.views and page.views[-1] is skel:
                            page.views.pop()
                    if not page.views:
                        page.views.append(login_view(page))
                        page.update()
                    await page.shared_preferences.remove("auth_token")
                    await page.shared_preferences.remove("refresh_token")
                    if hasattr(page, "session") and hasattr(page.session, "store"):
                        try:
                            page.session.store.clear()
                        except Exception:
                            pass
                    persistent_nav_bar.refresh()
                    await show_session_expired_dialog(
                        "Your session has ended. Please log in again to continue."
                    )
                    return
            else:
                # Some other backend response arrived (any non-401/403
                # status). The token might still be valid — don't destroy
                # it. Fall back to whatever was on screen before, rather
                # than a dead-end dialog.
                #
                # NOTE: 503/504 specifically are now classified as
                # CONNECTIVITY, not server — see classify_failure's
                # comment block for why (auth.py's own request functions
                # use those codes to mean "couldn't reach the server" or
                # "server is cold-starting", not "server sent a real error
                # response"). Only genuine other-status responses (500,
                # 422, etc) land in the SERVER bucket.
                shimmer_task.cancel()
                if not in_shell_route_flag and page.views and page.views[-1] is skel:
                    page.views.pop()
                server_ex = RuntimeError(f"Server error {status}")
                fell_back = await restore_previous_or_fallback(page.route, server_ex, status=status)
                page.update()
                await report_failure(fell_back=fell_back, status=status)
                return

            # Auth check passed — hand the still-running skeleton off to
            # load_view() so it continues shimmering through the view
            # fetch too, instead of flickering closed and reopening.
            active_skeleton = skel
            active_shimmer_task = shimmer_task
        else:
            active_skeleton = None
            active_shimmer_task = None

        if not is_public_route(page.route):
            try:
                from src.services.notification_service import sync_learner_notifications
                page.run_task(sync_learner_notifications, page, False)
            except Exception:
                pass

        # --- VIEW MAPPING ---
        #
        # NOTE on why public routes (/, /login, /signup) clear page.views
        # here but protected routes don't: protected routes already had a
        # skeleton pushed ON TOP of whatever was previously on screen (see
        # the auth-check block above), and load_view_and_report/load_view
        # replace just that top slot (`page.views[-1] = real_view`) once
        # ready — so the stack never grows unbounded and previous_view
        # stays intact underneath for restore_previous_or_fallback to use
        # if the load fails.
        #
        # Public routes don't go through that skeleton dance at all (see
        # `if not is_public_route(page.route):` above, which is skipped
        # for them), so nothing has trimmed the stack for them yet. Since
        # we no longer do an unconditional page.views.clear() at the top
        # of this function, we clear explicitly here before mounting them
        # — otherwise navigating to /login or /signup would just stack a
        # new view on top of whatever was already showing instead of
        # replacing it.
        if page.route == "/dashboard":
            await load_view_and_report(dashboard_view(page), page.route, active_skeleton, active_shimmer_task)
        elif page.route in ("/", "/login"):
            token = await page.shared_preferences.get("auth_token")
            if not token:
                if hasattr(page, "session") and hasattr(page.session, "store"):
                    try:
                        page.session.store.clear()
                    except Exception:
                        pass
                persistent_nav_bar.refresh()
            page.views.clear()
            page.views.append(login_view(page))
        elif page.route == "/signup":
            page.views.clear()
            page.views.append(Signup_view(page))
        elif page.route == "/profile":
            await load_view_and_report(profile_view(page), page.route, active_skeleton, active_shimmer_task)
        elif page.route == "/courses":
            await load_view_and_report(courses_view(page), page.route, active_skeleton, active_shimmer_task)
        elif page.route == "/create-course":
            await load_view_and_report(create_courses_view(page, None), page.route, active_skeleton, active_shimmer_task)
        elif page.route == "/edit-profile":
            await load_view_and_report(edit_profile_view(page), page.route, active_skeleton, active_shimmer_task)
        elif page.route == "/organisations":
            await load_view_and_report(organisations_view(page), page.route, active_skeleton, active_shimmer_task)
        elif page.route == "/network":
            await load_view_and_report(network_view(page), page.route, active_skeleton, active_shimmer_task)
        elif page.route == "/nu-chat":
            await load_view_and_report(chat_view(page), page.route, active_skeleton, active_shimmer_task)
        elif page.route == "/notifications":
            await load_view_and_report(notifications_view(page), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/courses/:id/stats"):
            await load_view_and_report(course_stats_view(page, troute.id), page.route, active_skeleton, active_shimmer_task)
        elif page.route == "/self-study":
            await load_view_and_report(self_study_view(page), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/organisations/:org_id/playlists"):
            user_data = page.session.store.get("current_user") or {} if hasattr(page, "session") and hasattr(page.session, "store") else {}
            u_role = str(user_data.get("role", "")).upper()
            if u_role in ("ADMIN", "OWNER"):
                page.go("/organisations")
                return
            from src.create_playlist import create_playlists_view
            await load_view_and_report(create_playlists_view(page, troute.org_id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/playlists/:id/build"):
            from src.playlist_builder import playlist_builder_view
            await load_view_and_report(playlist_builder_view(page, troute.id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/playlists/:id/settings"):
            from src.playlist_settings import playlist_settings_view
            await load_view_and_report(playlist_settings_view(page, troute.id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/playlists/:id/analytics"):
            org_id = (page.session.store.get("current_org_id") if hasattr(page, "session") and hasattr(page.session, "store") else "") or ""
            await load_view_and_report(playlist_analytics_view(page, org_id, troute.id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/playlists/:id"):
            from src.playlist_view import playlist_view
            target_back = previous_route if (previous_route and not previous_route.endswith("/view") and not previous_route.endswith("/offline")) else "/courses"
            await load_view_and_report(playlist_view(page, troute.id, back_target=target_back), page.route, active_skeleton, active_shimmer_task)
        # --- Organization Courses Route (Admins redirected to dashboard) ---
        elif troute.match("/organisations/:org_id/courses"):
            user_data = page.session.store.get("current_user") or {} if hasattr(page, "session") and hasattr(page.session, "store") else {}
            u_role = str(user_data.get("role", "")).upper()
            if u_role in ("ADMIN", "OWNER"):
                page.go("/organisations")
                return
            await load_view_and_report(create_courses_view(page, troute.org_id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/courses/:course_id/manage"):
            # Extracts the ID from the URL and passes it to the view
            await load_view_and_report(course_builder_view(page, troute.course_id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/courses/:course_id/offline"):
            if getattr(page, "web", False):
                page.go(f"/courses/{troute.course_id}/view")
                return
            # Explicit offline course learner view: strictly offline, zero network probe
            course_id_param = troute.course_id
            target_back = previous_route if (previous_route and not previous_route.endswith("/view") and not previous_route.endswith("/offline")) else "/offline"
            await load_view_and_report(
                offline_course_learner_view(page, course_id_param, back_target=target_back),
                page.route, active_skeleton, active_shimmer_task
            )
        elif troute.match("/courses/:course_id/view"):
            # Decide online vs offline engine for this course.
            course_id_param = troute.course_id
            current_token = await page.shared_preferences.get("auth_token")
            course_downloaded = is_course_downloaded(page, course_id_param)

            # Check if strictly coming from offline view or requested as offline
            is_from_offline_view = (
                (previous_route == "/offline")
                or (page.route and ("/offline" in page.route or "offline=true" in page.route))
            )

            # Semantic back-navigation: preserve where the user actually navigated from
            if is_from_offline_view or previous_route == "/offline":
                back_target = "/offline"
            elif previous_route and not previous_route.endswith("/view") and not previous_route.endswith("/offline"):
                back_target = previous_route
            else:
                back_target = "/courses"

            # STRICT OFFLINE LOADING for /view route:
            if (is_from_offline_view or not current_token) and course_downloaded:
                await load_view_and_report(
                    offline_course_learner_view(page, course_id_param, back_target=back_target),
                    page.route, active_skeleton, active_shimmer_task
                )
            elif current_token and course_downloaded:
                # Normal browsing from online catalog (/courses, /dashboard):
                # Probe network to decide online vs offline engine using centralized auth request
                try:
                    probe_status, _ = await asyncio.wait_for(get_current_user_request(current_token), timeout=2.5)
                    online_reachable = (probe_status == 200)
                except Exception:
                    online_reachable = False

                if online_reachable:
                    await load_view_and_report(
                        course_learner_view(page, course_id_param, back_target=back_target),
                        page.route, active_skeleton, active_shimmer_task
                    )
                else:
                    await load_view_and_report(
                        offline_course_learner_view(page, course_id_param, back_target=back_target),
                        page.route, active_skeleton, active_shimmer_task
                    )
            else:
                # Have a token, no local copy — nothing to fall back to,
                # let the normal online path + its own error handling run.
                await load_view_and_report(
                    course_learner_view(page, course_id_param, back_target=back_target),
                    page.route, active_skeleton, active_shimmer_task
                )
        elif troute.match("/offline"):
            if getattr(page, "web", False):
                page.go("/courses")
                return
            while len(page.views) > 1 and page.views[-1] is not shell_view:
                page.views.pop()
            valid_back = previous_route if (previous_route and previous_route != "/offline") else "/dashboard"
            offline_v = await offline_courses_view(page, back_target=valid_back)
            page.views.append(offline_v)
            page.update()
        elif troute.match("/member/:user_id"):
            # Extracts the ID from the URL and passes it to the view
            await load_view_and_report(member_profile_view(page, troute.user_id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/organisations/:org_id/courses/:course_id/settings"):
            await load_view_and_report(
                course_settings_view(page, course_id=troute.course_id, org_id=troute.org_id),
                page.route, active_skeleton, active_shimmer_task,
            )
        elif troute.match("/courses/:course_id/settings"):
            await load_view_and_report(
                course_settings_view(page, course_id=troute.course_id),
                page.route, active_skeleton, active_shimmer_task,
            )
        elif troute.match("/accept-invite/:token"):
            # Safely extract the token natively and mount the invite view.
            # member_invite_view is a regular (non-async) function that
            # returns a View directly, so no `await` here — skip the skeleton.
            # This is also a public route (see is_public_route) that
            # bypasses the auth-check/skeleton block above, so — same as
            # /, /login, /signup — it needs its own explicit clear.
            page.views.clear()
            page.views.append(member_invite_view(page, token=troute.token))
        elif troute.match("/organisations/:org_id/invite-members"):
            # Safely extract the query parameter ('3839') natively
            # Mount your view and hand off the token cleanly
            await load_view_and_report(invite_members_view(page, org_id=troute.org_id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/organisations/:org_id/courses/:course_id/analytics"):
            await load_view_and_report(
                course_analytics_view(page, org_id=troute.org_id, course_id=troute.course_id),
                page.route, active_skeleton, active_shimmer_task,
            )
        elif troute.match("/organisations/:org_id/playlists/:playlist_id/analytics"):
            await load_view_and_report(
                playlist_analytics_view(page, org_id=troute.org_id, playlist_id=troute.playlist_id),
                page.route, active_skeleton, active_shimmer_task,
            )
        elif troute.match("/courses/:course_id"):
            # Compute where the back arrow should return to
            target_back = previous_route if (previous_route and not previous_route.endswith("/view") and not previous_route.endswith("/offline")) else "/courses"
            await load_view_and_report(
                course_details_view(page, troute.course_id, back_target=target_back), page.route,
                active_skeleton, active_shimmer_task,
            )
        elif troute.match("/cohorts/:cohort_id"):
            from src.cohort_page import cohort_page_view
            target_back = previous_route if (previous_route and not previous_route.endswith("/view") and not previous_route.endswith("/offline")) else "/dashboard"
            await load_view_and_report(
                cohort_page_view(page, troute.cohort_id, back_target=target_back),
                page.route, active_skeleton, active_shimmer_task
            )
        elif page.route == "/cohorts":
            from src.cohort_page import cohort_page_view
            target_back = previous_route if (previous_route and not previous_route.endswith("/view") and not previous_route.endswith("/offline")) else "/dashboard"
            await load_view_and_report(
                cohort_page_view(page, None, back_target=target_back),
                page.route, active_skeleton, active_shimmer_task
            )

        elif active_skeleton is not None:
            active_shimmer_task.cancel()
            if not in_shell_route_flag and page.views and page.views[-1] is active_skeleton:
                page.views.pop()
            fell_back = await restore_previous_or_fallback(
                page.route, RuntimeError(f"Unknown route: {page.route}")
            )
            if fell_back:
                show_error_dialog("That page couldn't be found", icon=ft.Icons.ERROR_OUTLINE)

        saved_mode = await page.shared_preferences.get("dark_mode")
        await apply_theme(saved_mode == "true")
        page.update()

    page.on_route_change = route_change

    # --- BUG FIX: token-expiry white screen after backgrounding the app ---
    #
    # Root cause: `main()` runs once per live session, and until now the
    # ONLY thing that ever re-checked the auth token was `route_change` —
    # which only fires when `page.route` actually changes. Backgrounding
    # the app (switching away, locking the screen, minimizing) and coming
    # back later doesn't change the route at all: the session was never
    # torn down, so `main()` never re-runs and route_change never re-fires.
    # The token can sit expired for hours with nothing ever re-validating
    # it — you just see whatever was last on screen, frozen. If that
    # happened to be a skeleton mid-shimmer, the animation task is still
    # technically "running" but the client-side view underneath it is
    # stale/torn-down by the time you look again, which is what reads as
    # "shimmer, then white screen". Force-quitting and reopening "fixes"
    # it only because that starts a brand-new session, which runs the
    # bootstrap token check near the end of main() fresh.
    #
    # Fix: listen for the window regaining focus (fires when the OS brings
    # the app back to the foreground) and silently re-validate the token
    # against the backend. We deliberately do NOT just call route_change()
    # unconditionally here — route_change always pushes a fresh skeleton
    # over whatever's on screen before it knows if anything's actually
    # wrong, which would flash on every single resume even when the
    # session is perfectly fine. Instead: ping the backend quietly, and
    # only fall through to the full route_change() (which knows how to
    # clear the token, show the session-expired dialog, and land on
    # login) when we actually find the token is dead or missing.
    resume_check_state = {"in_flight": False}

    def _is_public_route(route):
        # Kept in sync with is_public_route() inside _route_change_inner —
        # duplicated here because that one is a nested closure scoped to
        # a single route_change() call, not reachable from this handler.
        return route in ["/", "/login", "/signup"] or (route or "").startswith("/accept-invite/")

    async def on_window_event(e: ft.WindowEvent):
        if e.data not in ("focus", "restore", "show"):
            return
        if _is_public_route(page.route):
            return  # not logged in / not on a protected screen — nothing to check
        # Guard against overlapping checks if multiple focus-ish events
        # fire in quick succession (observed on some platforms).
        if resume_check_state["in_flight"]:
            return
        resume_check_state["in_flight"] = True
        try:
            token = await page.shared_preferences.get("auth_token")
            if not token:
                return  # already logged out; nothing new to report
            try:
                status, _ = await get_current_user_request(token)
            except Exception:
                # Network hiccup on resume — not a session problem, don't
                # act on it. The next real navigation will surface any
                # persisting issue through the normal route_change path.
                return
            if status in (401, 403):
                # Access token expired while backgrounded — the expected
                # steady state. Try a silent refresh first so a routine
                # resume doesn't interrupt the user with a dialog. Only
                # fall through to the full route_change (which clears
                # tokens and shows session-expired) if refresh also fails.
                refreshed = await try_refresh_token(page)
                if not refreshed:
                    await route_change(None)
                    return
                # If refreshed succeeded: do nothing further. The app
                # continues showing whatever screen it already had, now
                # backed by a valid token — no visible interruption.

            # Opportunistic sync-back: resume-with-a-valid-session is a
            # reasonable moment to push any progress that was tracked
            # offline. Best-effort — failures here are silent (the sync
            # job itself just leaves rows unsynced for next time), so this
            # never interrupts the resume flow with an error.
            try:
                if not getattr(page, "web", False):
                    await sync_offline_progress(page)
            except Exception:
                pass
        finally:
            resume_check_state["in_flight"] = False

    page.window.on_event = on_window_event

    # --- BUG FIX: intermittent white screen on FIRST load (distinct from
    # the token-expiry bug above — this can happen regardless of whether
    # a token exists, and a manual reload always "fixes" it) ---
    #
    # On a genuinely cold load, `main()` can start running before the
    # client's own connection/transport has fully finished handshaking.
    # `page.shared_preferences.get(...)` is a platform-channel RPC to the
    # client — if it's issued while that handshake is still settling, it
    # can raise, hang, or return an unusable result. Since the block below
    # was previously unguarded, any of those outcomes could leave
    # `page.route` unset and skip `route_change` doing anything useful —
    # nothing throws loudly, nothing gets logged, and the session just
    # sits there blank until a reload gives the client more time before
    # we touch it again.
    #
    # Fix: guard the shared_preferences read so a slow/unready client
    # fails safe into the public login route instead of silently
    # producing no view at all, and (belt-and-suspenders, below) verify
    # something actually landed in page.views afterwards.

    # Previously this unconditionally overwrote page.route with "/dashboard"
    # or "/", which destroyed real deep links (e.g. /accept-invite/<uuid>
    # from an email) before route_change ever saw them. Now we only apply
    # that default when there's no real route to honor (fresh load with no
    # path, or bare "/").
    if not page.route or page.route == "/":
        try:
            # Bounded wait, not just a try/except — an unready platform
            # channel can hang rather than raise, and an unguarded await
            # here would block bootstrap forever with no fallback at all.
            has_token = await asyncio.wait_for(
                page.shared_preferences.get("auth_token"), timeout=5
            )
        except Exception as ex:
            # Covers both raised errors and the timeout above. If
            # shared_preferences genuinely isn't ready/available yet,
            # don't let that stall or crash session bootstrap and leave
            # a blank screen with no recovery — fail safe to the public
            # login route, which route_change can always render.
            print(f"initial shared_preferences read failed: {ex!r}")
            has_token = None
        page.route = "/dashboard" if has_token else "/"
        if has_token:
            try:
                from src.services.notification_service import sync_learner_notifications
                page.run_task(sync_learner_notifications, page, True)
            except Exception:
                pass

    await route_change(None)
    # Belt-and-suspenders: if for any reason the manual call above didn't
    # result in anything being pushed to page.views (e.g. it silently
    # no-opped during a still-settling connection), make sure the user
    # never lands on a truly empty screen with nothing to look at or
    # recover from. Guarded with try/except since this runs outside
    # route_change's own try/except — an unhandled exception here (e.g.
    # a view constructor hitting another None-dependent property before
    # the client has fully reported in) would otherwise crash bootstrap
    # itself instead of just failing to show a view.
    if not page.views:
        try:
            page.views.append(login_view(page))
            page.update()
        except Exception as ex:
            print(f"fallback login_view construction failed: {ex!r}")

# ─────────────────────────────────────────────────────────────────
# WEB & ASGI EXPORT (Coolify / Docker / Uvicorn & Local Flet Run)
# ─────────────────────────────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
absolute_assets_path = os.path.join(current_dir, "assets")

try:
    import flet.fastapi as flet_fastapi
    from fastapi import FastAPI, Request

    # 1. Initialize a FastAPI app for ASGI runners (Coolify, uvicorn main:app)
    app = FastAPI()

    # 2. Credentialless COEP Middleware: intercepts web pages and allows cross-origin Bunny CDN videos
    @app.middleware("http")
    async def apply_credentialless_coep(request: Request, call_next):
        response = await call_next(request)
        if "Cross-Origin-Embedder-Policy" in response.headers:
            response.headers["Cross-Origin-Embedder-Policy"] = "credentialless"
        return response

    # 3. Mount Flet FastAPI app
    flet_app = flet_fastapi.app(main, assets_dir=absolute_assets_path, session_timeout_seconds=86400)
    app.mount("/", flet_app)
except Exception as ex:
    import traceback
    traceback.print_exc()
    print(f"CRITICAL: Failed to initialize FastAPI ASGI app in main.py: {ex}", flush=True)
    app = None


if __name__ == "__main__":
    # If running inside Coolify or standalone production container without Flet CLI:
    if os.environ.get("COOLIFY_CONTAINER") or (os.environ.get("PORT") and not os.environ.get("FLET_SERVER_PORT")):
        if app is None:
            raise RuntimeError("Cannot start uvicorn: FastAPI app failed to initialize (see traceback above).")
        import uvicorn
        port = int(os.environ.get("PORT", 8000))
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        # Standard development run (Desktop or `flet run main.py --web`)
        # COEP patch automatically active for Bunny CDN videos on web!
        ft.run(main, assets_dir="assets")