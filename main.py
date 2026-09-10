import asyncio
import flet as ft
#import uvicorn
from src.Login import login_view
from src.course_analytics import course_analytics_view
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

    def view_pop(view):
        # Prevent crashing if there's only one page left
        if len(page.views) > 1:
            # BUG FIX: if a dialog was opened on the view *underneath* the
            # one being popped (e.g. login's connectivity dialog, before
            # navigating to /offline via "View downloaded courses"),
            # page.pop_dialog()'s bookkeeping can end up out of sync with
            # which View is actually on screen once we come back via the
            # back arrow — the dialog can resurface stuck open, with dead
            # handlers and no scrim-tap-to-dismiss. Force-close anything
            # left open on page.overlay here, unconditionally, before we
            # even look at what's underneath, so the revealed view never
            # resurfaces with a stuck dialog regardless of ordering.
            for ctrl in list(page.overlay):
                if isinstance(ctrl, ft.AlertDialog):
                    ctrl.open = False
            page.views.pop()             # Remove the current view from the stack
            top_view = page.views[-1]    # Look at the view underneath it
            page.go(top_view.route)      # Navigate to that route
            page.update()

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

    async def apply_theme(is_dark: bool):
        """Apply the correct theme and persist the preference."""
        if is_dark:
            page.theme_mode = ft.ThemeMode.DARK
            page.theme = LIGHT_THEME       # used as fallback base
            page.dark_theme = DARK_THEME   # Flet uses dark_theme in dark mode
            page.bgcolor = "#121212"

            # Set to Dark Mode Logo
            splash_logo.src = "nu_age_black_2-removebg-preview.png"
            splash_logo.width = 300
            splash_logo.height = 500
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
            page.theme = LIGHT_THEME
            page.bgcolor = ft.Colors.SURFACE

            # THE FIX: Explicitly reset to Light Mode Logo
            splash_logo.src = "Nu age new logo.png"
            splash_logo.width = 400
            splash_logo.height = 600

        page.update()

    async def toggle_dark_mode():
        """
        Call this from anywhere in your app:
            await page.session.store.get("toggle_dark_mode")()
        Or expose it via page.data for global access.
        """
        current = await page.shared_preferences.get("dark_mode")
        is_dark = not (current == "true")
        await page.shared_preferences.set("dark_mode", "true" if is_dark else "false")
        await apply_theme(is_dark)

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

    def _view_offline_courses_button() -> ft.Control:
        def go_offline(e):
            page.go("/offline")

        return ft.ElevatedButton(
            "Downloads",
            icon=ft.Icons.DOWNLOAD_FOR_OFFLINE,
            color=ft.Colors.PRIMARY,
            bgcolor=ft.Colors.ON_PRIMARY,
            on_click=go_offline,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=20, top=12, right=20, bottom=12),
            )
        )

    def _error_fallback_view(route: str, ex: Exception, status: int = None) -> ft.View:
        """A visible error screen used whenever a view fails to load —
        whether it raised an exception or silently returned nothing. Ensures
        the user always sees *something* explaining the failure, with a way
        to retry, instead of a dead blank screen.

        Uses the same classify_failure()/failure_copy() as the rest of the
        app's error handling (see module-level definitions near the top of
        this file), so this screen and the SnackBar/dialog notices always
        agree on wording — and so a code bug (e.g. "string indices must be
        integers, not 'str'") shows as "Something went wrong", not under a
        wifi-off icon with "This page couldn't load", which is what was
        happening before this screen was wired into the shared classifier.

        The raw exception text is still available — behind a "Details"
        toggle, collapsed by default — rather than permanently on screen.
        Keeps the friendly message for regular users while the exact error
        is still one tap away for debugging."""
        kind = classify_failure(ex, status)
        copy = failure_copy(kind, ex, status)

        def retry(e):
            # page.route already equals `route` here (this view's own
            # route is the one that failed), so a plain page.go(route)
            # is a same-route no-op client-side — the tap would do
            # nothing. Directly re-run the route-loading logic instead
            # of relying on a "route change" the client won't detect.
            page.run_task(route_change, None)

        details_text = ft.Text(
            copy["dev_detail"] or "No further detail available.",
            size=11,
            color=ft.Colors.BLACK,
            selectable=True,
        )
        details_container = ft.Container(
            content=details_text,
            visible=False,
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            border_radius=8,
            width=320,
        )

        def toggle_details(e):
            details_container.visible = not details_container.visible
            toggle_button.text = "Hide details" if details_container.visible else "Show details"
            details_container.update()
            toggle_button.update()

        toggle_button = ft.TextButton("Show details", on_click=toggle_details)

        # Centralized offline escape hatch: only offered when the failure
        # is genuinely a connectivity problem (not a 5xx or a code bug —
        # those aren't fixed by going offline) AND there's actually
        # something downloaded to send the person to. Covers exactly the
        # case you flagged: cold app open, offline, with a token that
        # might still be perfectly valid — previously this screen was a
        # dead end even when local course content existed.
        offer_offline = kind == "connectivity" and _has_any_downloaded_courses()

        primary_actions = [
            ft.FilledButton(
                "Retry",
                icon=ft.Icons.REFRESH,
                on_click=retry,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding(left=20, top=12, right=20, bottom=12),
                )
            )
        ]
        
        if offer_offline:
            primary_actions.append(_view_offline_courses_button())
            
        action_row = ft.Row(
            primary_actions,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=16,
        )

        return ft.View(
    route=route,
    controls=[
        ft.Column(
            [
                ft.Icon(copy["icon"], color=ft.Colors.ERROR, size=48),
                ft.Text(copy["dialog_title"], size=18, weight=ft.FontWeight.BOLD),
                ft.Text(
                    copy["dialog_message"],
                    size=14,
                    color=ft.Colors.OUTLINE,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=4),
                action_row,
                toggle_button,
                details_container,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=12,
            expand=True,
        )
    ],
    vertical_alignment=ft.MainAxisAlignment.CENTER,
    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    padding=20,
)
    def shimmer_box(radius=12, height=None, width=None, expand = False):
        """A single placeholder rectangle. Its opacity gets pulsed by the
        shimmer loop below to create the animated shimmer effect. Pass
        height/width to make a fixed-size piece (avatar, button, chat
        bubble); leave both None to have it expand and fill its slot,
        same as before. Tagged via `.data` so _collect_boxes can find
        exactly these (and not the plain layout/spacer containers used
        to arrange them)."""
        box = ft.Container(
            expand=True if ((height is None and width is None) or expand) else None,
            height=height,
            width=width,
            border_radius=radius,
            bgcolor=ft.Colors.OUTLINE,
            animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
            opacity=0.35,
        )
        box.data = "shimmer_box"
        return box

    def _collect_boxes(control):
        """Walk a control tree and pull out every shimmer_box (tagged via
        `.data`) so run_shimmer can animate them, no matter how deeply
        nested the layout is. Plain wrapper/spacer containers used to
        arrange the boxes are skipped."""
        boxes = []

        def walk(c):
            if isinstance(c, ft.Container):
                if getattr(c, "data", None) == "shimmer_box":
                    boxes.append(c)
                if c.content is not None:
                    walk(c.content)
            elif isinstance(c, (ft.Row, ft.Column)):
                for child in c.controls:
                    walk(child)

        walk(control)
        return boxes

    # ── Shared building blocks ────────────────────────────────────
    # Small pieces reused across several layouts below, so every
    # skeleton banner/navbar/card looks consistent with the others.

    def _bottom_navbar():
        """One continuous shimmer bar at the same height as the real
        bottom app bar, set apart by a hairline top divider (no filled
        background) with guaranteed top spacing so it never collides
        with the content above it on smaller screens."""
        return ft.Container(
            height=60,
                        bgcolor=ft.Colors.OUTLINE,
            margin=ft.Margin.only(top=14),
            border_radius=ft.BorderRadius(top_left=15,top_right=15, bottom_left=None, bottom_right=None),
            padding=ft.Padding.symmetric(horizontal=4, vertical=6),
            border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.OUTLINE)),
            animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
                        opacity=0.35
        )

    def _section_bg(content, padding=16, radius=16, expand=False):
        """Wraps a chunk of a layout in a faintly tinted background
        panel — used sparingly to divide an otherwise sparse skeleton
        into two or three visually distinct sections (not one per
        element, just enough that the page doesn't look like scattered
        bars floating on nothing, especially on wide/desktop viewports)."""
        return ft.Container(
            content=content,
            padding=padding,
            border_radius=radius,
            bgcolor=ft.Colors.with_opacity(0.035, ft.Colors.ON_SURFACE),
            expand=expand,
        )

    def _top_banner(height=110, radius=20):
        """Solid rounded block standing in for the green gradient header
        used at the top of most pages."""
        return shimmer_box(radius=radius, height=height)

    def _section_label():
        """A short bar + a shorter 'See All'-style bar, mimicking a
        section header row like 'Friends  ···  See All'."""
        return ft.Row(
            [
                shimmer_box(radius=6, height=16, width=110),
                shimmer_box(radius=6, height=12, width=44),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _avatar_col(size=56):
        return ft.Column(
            [shimmer_box(radius=size / 2, width=size, height=size),
             shimmer_box(radius=6, width=size - 10, height=10)],
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # ── Individual layout templates ─────────────────────────────
    # Each returns an ft.Control built from shimmer_box() pieces,
    # arranged to roughly mirror a real page's shape. Add a new one
    # here, then register it in SKELETON_LAYOUTS / _PREFIXES below —
    # nothing else needs to change.

    def _layout_default(rows: int = 5):
        """Generic fallback: evenly spaced bars (the original look)."""
        boxes = [shimmer_box() for _ in range(rows)]
        return ft.Column(controls=boxes, spacing=14, expand=True,
                          alignment=ft.MainAxisAlignment.SPACE_EVENLY)

    def _layout_dashboard():
        """Mirrors /dashboard: greeting banner, two side-by-side action
        cards (Courses/Network), a 'Friends' row of avatars, a 'Weekly
        Activity' chart block, bottom nav."""
        banner = _top_banner(height=100)

        action_cards = ft.Row(
            [shimmer_box(radius=16, height=110, expand=True), shimmer_box(radius=16, height=110, expand=True)],
            spacing=14,
        )

        friends_row = ft.Row(
            [_avatar_col(size=52) for _ in range(6)],
            spacing=16,
            scroll=ft.ScrollMode.HIDDEN,
        )
        friends_section = _section_bg(
            ft.Column([_section_label(), ft.Container(height=8), friends_row], spacing=4)
        )

        chart_section = _section_bg(
            ft.Column([_section_label(), ft.Container(height=8), shimmer_box(radius=12, height=120)],
                      spacing=4, expand=True),
            padding=16,
            expand=True,
        )

        return ft.Column(
            controls=[
                banner,
                action_cards,
                friends_section,
                chart_section,
                _bottom_navbar(),
            ],
            spacing=20,
            expand=True,
        )

    def _layout_chat_list():
        """Mirrors /nu-chat: green header with search bar, then a list
        of chat rows (avatar + title/timestamp + preview line), bottom
        nav. (This is the conversation-list state, not an open thread.)"""
        header = ft.Column(
            [shimmer_box(radius=6, height=22, width=110),
             shimmer_box(radius=10, height=40)],
            spacing=14,
        )
        header_container = ft.Container(content=header, padding=16, bgcolor=None)

        def chat_row():
            return ft.Row(
                [
                    shimmer_box(radius=24, width=48, height=48),
                    ft.Column(
                        [
                            ft.Row(
                                [shimmer_box(radius=6, height=13, width=170),
                                 shimmer_box(radius=6, height=10, width=36)],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            shimmer_box(radius=6, height=10, width=120),
                        ],
                        spacing=8,
                        expand=True,
                    ),
                ],
                spacing=12,
            )

        chat_list = ft.Column(
            controls=[chat_row() for _ in range(5)],
            spacing=20,
            expand=True,
        )

        return ft.Column(
            controls=[
                shimmer_box(radius=16, height=90),
                ft.Container(content=chat_list, expand=True, padding=ft.Padding.only(top=12, bottom=8)),
                _bottom_navbar(),
            ],
            spacing=16,
            expand=True,
        )

    def _layout_course_grid():
        """Mirrors /courses (learner library): green banner, a tab row
        (Available/Ongoing/Completed), 2-col grid of solid course-card
        silhouettes (one shimmer block per card, matching the real
        image+text card shape), bottom nav."""
        banner = _top_banner(height=70)
        tabs = ft.Row(
            [shimmer_box(radius=6, height=14, width=100),
             shimmer_box(radius=6, height=14, width=100),
             shimmer_box(radius=6, height=14, width=110)],
            spacing=24,
        )

        def card_silhouette():
            # One solid block per card — mirrors the real card's outer
            # shape (image + text stacked). expand=True is required here:
            # shimmer_box() only auto-expands when height/width are both
            # left None, and this box has a fixed height, so without
            # expand=True it collapses to near-zero width inside the Row.
            box = shimmer_box(radius=14, height=190)
            box.expand = True
            return box

        grid = ft.Column(
            [
                ft.Row([card_silhouette(), card_silhouette()], spacing=14, expand=True),
                ft.Row([card_silhouette(), card_silhouette()], spacing=14, expand=True),
            ],
            spacing=14,
            expand=True,
        )

        return ft.Column(
            controls=[banner, tabs, ft.Container(content=grid, expand=True, padding=ft.Padding.only(top=8)),
                      _bottom_navbar()],
            spacing=16,
            expand=True,
        )

    def _layout_course_reader():
        """Mirrors the standard LMS reading page: dark top app bar, a
        left sidebar (course title card + module/lesson rows) taking
        roughly a third of the width — slightly more, since that's how
        it renders in the real app — a main content pane on the right,
        and a single long bar along the bottom the same height as the
        real bottom app bar (standing in for it, since the exact
        prev/next controls vary by lesson)."""
        topbar = ft.Row(
            [shimmer_box(radius=8, width=28, height=28),
             shimmer_box(radius=6, height=18, width=220)],
            spacing=16,
        )

        sidebar_card = shimmer_box(radius=12, height=70)
        sidebar_rows = ft.Column(
            [shimmer_box(radius=6, height=14) for _ in range(6)],
            spacing=16,
            expand=True,
        )
        sidebar = ft.Container(
            content=ft.Column(
                [sidebar_card, ft.Container(height=10), sidebar_rows],
                spacing=0,
                expand=True,
            ),
            expand=4,  # ~38% of the row's width — a third, slightly bigger
            padding=ft.Padding.only(right=16),
        )

        breadcrumb = ft.Row(
            [shimmer_box(radius=6, height=10, width=130),
             shimmer_box(radius=20, height=18, width=60)],
            spacing=10,
        )
        title = shimmer_box(radius=6, height=24, width=260)
        paragraph = ft.Column(
            [shimmer_box(radius=6, height=12) for _ in range(6)],
            spacing=10,
            expand=True,
        )
        main_pane = ft.Container(
            content=ft.Column(
                [breadcrumb, ft.Container(height=8), title, ft.Container(height=14), paragraph],
                spacing=0,
                expand=True,
            ),
            expand=6,  # remaining ~62%
        )

        body = ft.Row([sidebar, main_pane], expand=True)

        # Standard LMS bottom bar: reuse the same bottom-navbar treatment
        # (continuous bar, tinted strip, hairline divider) so it's
        # visually identical to the app's real bottom nav, rather than a
        # separately-styled lookalike.
        bottom_bar = _bottom_navbar()

        return ft.Column(
            controls=[topbar, ft.Container(height=10), ft.Container(content=body, expand=True), bottom_bar],
            spacing=0,
            expand=True,
        )


    def _layout_org_admin_dashboard():
        """Mirrors /organisations (admin view): hero cover image,
        circular org avatar overlapping, title, count chips, tab row,
        then a list of cards."""
        # Cover image (200px tall)
        cover = shimmer_box(radius=0, height=200, expand=True)
        # Org avatar (overlapping: negative top margin if possible, but in skeleton we just place it)
        avatar = ft.Container(content=shimmer_box(radius=50, width=100, height=100), margin=ft.Margin.only(top=-50, left=20))
        # Title
        title = ft.Container(content=shimmer_box(radius=6, height=24, width=200), margin=ft.Margin.only(left=20, top=10))
        # Count chips
        counts = ft.Container(
            content=ft.Row([shimmer_box(radius=16, height=32, width=100), shimmer_box(radius=16, height=32, width=100)], spacing=10),
            margin=ft.Margin.only(left=20, top=10)
        )
        # Tabs
        tabs = ft.Container(
            content=ft.Row([shimmer_box(radius=18, height=36, width=90) for _ in range(4)], spacing=10),
            margin=ft.Margin.only(left=20, top=20, bottom=20)
        )
        # Cards (e.g. Dashboard cards)
        cards = ft.Column([shimmer_box(radius=16, height=140, expand=True) for _ in range(3)], spacing=16)

        return ft.ListView(
            controls=[cover, avatar, title, counts, tabs, ft.Container(content=cards, padding=20)],
            expand=True,
            padding=0,
        )

    def _layout_profile():
        """Mirrors /profile: green banner with centered avatar, name,
        role pill; a 'Quick Actions' 2-card row; a toggle row; and an
        account-details list."""
        banner = ft.Column(
            [
                ft.Container(height=10),
                ft.Row([shimmer_box(radius=45, width=88, height=88)], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([shimmer_box(radius=6, height=18, width=110)], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([shimmer_box(radius=14, height=24, width=64)], alignment=ft.MainAxisAlignment.CENTER),
            ],
            spacing=12,
        )

        quick_actions = ft.Row(
            [shimmer_box(radius=14, height=90, expand=True), shimmer_box(radius=14, height=90, expand=True)],
            spacing=14,
        )

        toggle_row = ft.Row(
            [shimmer_box(radius=6, height=12, width=130), shimmer_box(radius=10, width=32, height=18)],
            spacing=12,
        )

        detail_rows = _section_bg(
            ft.Column(
                [ft.Row([shimmer_box(radius=8, width=32, height=32),
                         ft.Column([shimmer_box(radius=6, height=10, width=50),
                                    shimmer_box(radius=6, height=13, width=160)], spacing=6)],
                        spacing=12)
                 for _ in range(2)],
                spacing=18,
            )
        )

        return ft.Column(
            controls=[
                banner,
                ft.Container(height=8),
                quick_actions,
                toggle_row,
                ft.Container(content=detail_rows, expand=True, padding=ft.Padding.only(top=8)),
                _bottom_navbar(),
            ],
            spacing=18,
            expand=True,
        )

    def _layout_network():
        """Mirrors /network: dark header with back arrow + title, a tab
        row (My Network/Requests/Discover), a search bar, then a vertical 
        list of user profile rows (avatar, name column, action buttons)."""
        header = ft.Row(
            [shimmer_box(radius=8, width=24, height=24), shimmer_box(radius=6, height=18, width=100)],
            spacing=14,
        )
        tabs = ft.Row(
            [shimmer_box(radius=18, height=32, width=110),
             shimmer_box(radius=6, height=14, width=70),
             shimmer_box(radius=6, height=14, width=60)],
            spacing=20,
        )
        search = shimmer_box(radius=10, height=42, expand=True)

        def user_row():
            return ft.Row(
                [
                    shimmer_box(radius=24, width=48, height=48),
                    ft.Column([shimmer_box(radius=6, height=14, width=120), shimmer_box(radius=6, height=10, width=80)], spacing=4, expand=True),
                    ft.Row([shimmer_box(radius=16, width=40, height=32), shimmer_box(radius=16, width=40, height=32)], spacing=8)
                ],
                spacing=12,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )

        list_view = ft.Column(
            [user_row() for _ in range(6)],
            spacing=16,
            expand=True,
        )

        return ft.Column(
            controls=[
                shimmer_box(radius=16, height=64, expand=True),
                tabs, search,
                ft.Container(content=list_view, expand=True, padding=ft.Padding.only(top=8)),
                _bottom_navbar(),
            ],
            spacing=16,
            expand=True,
        )

    def _layout_course_library():
        """Mirrors an org's course library: green banner with title +
        count + 'New Course' button, then a grid of course cards (image,
        two pills, title, description bars, enrolled count, two
        buttons)."""
        banner = ft.Row(
            [
                ft.Column([shimmer_box(radius=6, height=20, width=160),
                           shimmer_box(radius=6, height=10, width=70)], spacing=8),
                shimmer_box(radius=20, height=36, width=110),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        banner_container = ft.Container(content=banner, bgcolor=None, height=90, expand=True)

        def lib_card():
            btn_left = shimmer_box(radius=18, height=34, expand=True)
            btn_right = shimmer_box(radius=18, height=34, expand=True)
            return ft.Column(
                [
                    shimmer_box(radius=12, height=110, expand=True),
                    ft.Row([shimmer_box(radius=20, width=44, height=18),
                            shimmer_box(radius=20, width=64, height=18)], spacing=6),
                    shimmer_box(radius=6, height=14, expand=True),
                    shimmer_box(radius=6, height=9, width=180),
                    ft.Row([btn_left, btn_right], spacing=8),
                ],
                spacing=8,
                expand=True
            )

        grid = ft.Column(
            [ft.Row([lib_card(), lib_card()], spacing=14, expand=True)
             for _ in range(2)],
            spacing=18,
            expand=True,
        )

        return ft.Column(
            controls=[banner_container, ft.Container(content=grid, expand=True), _bottom_navbar()],
            spacing=12,
            expand=True,
        )

    def _layout_self_study():
        """Mirrors the Self Study Hub: top app bar, limit/status pill chips,
        a secondary tab row, and a vertical list of material cards."""
        header = ft.Row(
            [shimmer_box(radius=8, width=24, height=24), shimmer_box(radius=6, height=18, width=120)],
            spacing=14,
        )
        limit_chips = ft.Row(
            [shimmer_box(radius=12, height=24, expand=True) for _ in range(3)],
            spacing=8
        )
        tabs = ft.Row(
            [shimmer_box(radius=16, height=32, width=80) for _ in range(4)],
            spacing=12
        )
        def material_card():
            return ft.Container(
                content=ft.Row([
                    shimmer_box(radius=12, width=48, height=48),
                    ft.Column([shimmer_box(radius=6, height=14, width=150), shimmer_box(radius=6, height=10, width=90)], spacing=4, expand=True),
                    shimmer_box(radius=20, width=40, height=40)
                ], spacing=12),
                padding=12,
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_PRIMARY)
            )
        
        list_view = ft.Column(
            [material_card() for _ in range(5)],
            spacing=12,
            expand=True
        )

        return ft.Column(
            controls=[
                header,
                ft.Container(height=8),
                limit_chips,
                ft.Container(height=8),
                tabs,
                ft.Container(height=16),
                list_view
            ],
            spacing=0,
            expand=True
        )

    def _layout_course_builder():
        """Mirrors the course builder: plain header (back arrow + title
        + subtitle), a row of 3 action buttons, then a module section
        with a title/icon row and a stack of lesson rows (icon + title
        + tag pill + edit/delete icons)."""
        header = ft.Row(
            [
                shimmer_box(radius=8, width=24, height=24),
                ft.Column([shimmer_box(radius=6, height=16, width=150),
                           shimmer_box(radius=6, height=10, width=220)], spacing=8),
            ],
            spacing=14,
        )
        action_buttons = ft.Row(
            [shimmer_box(radius=20, height=36, width=100) for _ in range(3)],
            spacing=10,
        )

        module_header = ft.Row(
            [shimmer_box(radius=6, height=16, width=200),
             ft.Row([shimmer_box(radius=6, width=18, height=18) for _ in range(4)], spacing=12)],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        def lesson_row():
            return ft.Row(
                [
                    shimmer_box(radius=10, width=36, height=36),
                    ft.Column([shimmer_box(radius=6, height=13, width=220),
                               shimmer_box(radius=20, height=16, width=64)], spacing=8, expand=True),
                    ft.Row([shimmer_box(radius=6, width=16, height=16),
                            shimmer_box(radius=6, width=16, height=16)], spacing=12),
                ],
                spacing=14,
            )

        lessons = ft.Column([lesson_row() for _ in range(4)], spacing=16)

        return ft.Column(
            controls=[
                header,
                ft.Container(height=8),
                action_buttons,
                ft.Container(height=8),
                module_header,
                ft.Container(height=8),
                ft.Container(content=lessons, expand=True),
            ],
            spacing=0,
            expand=True,
        )

    def _layout_form():
        """Stacked input-field placeholders with a full-width button at
        the bottom. For accept-invite / invite-members / create flows."""
        fields = ft.Column(controls=[shimmer_box(radius=10, height=52) for _ in range(4)], spacing=16)
        button = shimmer_box(radius=10, height=48)
        return ft.Column(
            controls=[ft.Container(content=fields, expand=True), button],
            spacing=20,
            expand=True,
        )

    def _layout_analytics():
        """Mirrors analytics/stats dashboards: small metric cards row,
        then large chart blocks."""
        metrics_row = ft.Row([shimmer_box(radius=12, height=100, expand=True) for _ in range(2)], spacing=16)
        chart_block1 = shimmer_box(radius=16, height=220, expand=True)
        chart_block2 = shimmer_box(radius=16, height=220, expand=True)
        return ft.Column([metrics_row, ft.Container(height=16), chart_block1, ft.Container(height=16), chart_block2], expand=True)

    def _layout_settings():
        """Mirrors settings pages: a list of toggle/input rows."""
        def setting_row():
            return ft.Row([
                shimmer_box(radius=6, height=16, width=160),
                shimmer_box(radius=12, height=24, width=44)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        return ft.Column([setting_row(), ft.Container(height=20)] * 6, expand=True)

    def _layout_offline():
        """Mirrors the offline downloaded courses list."""
        def offline_card():
            return ft.Container(
                content=ft.Row([
                    ft.Column([shimmer_box(radius=6, height=16, width=180), shimmer_box(radius=6, height=12, width=80)], expand=True, spacing=8),
                    shimmer_box(radius=18, height=36, width=80)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=16,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_PRIMARY)),
                border_radius=14,
                margin=ft.Margin.only(bottom=12)
            )
        return ft.Column([offline_card() for _ in range(5)], expand=True)

    def _layout_course_details():
        """Mirrors a course or playlist details page: hero banner with image/title,
        then description blocks and an enroll button."""
        hero = shimmer_box(radius=16, height=200, expand=True)
        title = shimmer_box(radius=6, height=24, width=240)
        desc_lines = ft.Column([shimmer_box(radius=6, height=14, expand=True) for _ in range(4)])
        button = shimmer_box(radius=24, height=48, expand=True)
        return ft.Column([hero, ft.Container(height=16), title, ft.Container(height=16), desc_lines, ft.Container(height=24), button], expand=True)

    # ── Route → layout registry ─────────────────────────────────
    # Add/re-map routes here; nothing else needs to change. Exact
    # matches first, then prefix matches for parametrized routes.

    SKELETON_LAYOUTS = {
        "/dashboard": _layout_dashboard,
        "/network": _layout_network,
        "/nu-chat": _layout_chat_list,
        "/courses": _layout_course_grid,
        "/organisations": _layout_org_admin_dashboard,
        "/self-study": _layout_self_study,
        "/profile": _layout_profile,
        "/edit-profile": _layout_profile,
        "/offline": _layout_offline,
    }

    # Ordered (most-specific-first) substring checks for parametrized
    # routes — checked before the plain prefix list below.
    SKELETON_LAYOUT_CONTAINS = [
        ("/create", _layout_form),                     # catches /courses/create, /organisations/:org_id/courses/create, /playlists/create
        ("/invite-members", _layout_form),             # .../organisations/:org_id/invite-members
        ("/manage", _layout_course_builder),           # .../courses/:id/manage
        ("/build", _layout_course_builder),            # .../playlists/:id/build
        ("/view", _layout_course_reader),               # .../courses/:id/view
        ("/stats", _layout_analytics),
        ("/analytics", _layout_analytics),
        ("/settings", _layout_settings),
        ("/courses/", _layout_course_details),          # Catches /courses/:id and /organisations/:org_id/courses/:id
        ("/playlists/", _layout_course_details),        # Catches /playlists/:id and /organisations/:org_id/playlists/:id
    ]

    SKELETON_LAYOUT_PREFIXES = [
        ("/member/", _layout_profile),
        ("/organisations/", _layout_course_library),    # org sub-routes fallback
        ("/accept-invite/", _layout_form),
    ]

    def _resolve_layout(route: str):
        if route in SKELETON_LAYOUTS:
            return SKELETON_LAYOUTS[route]
        for needle, layout_fn in SKELETON_LAYOUT_CONTAINS:
            if needle in route:
                return layout_fn
        for prefix, layout_fn in SKELETON_LAYOUT_PREFIXES:
            if route.startswith(prefix):
                return layout_fn
        return _layout_default

    def skeleton_view(route: str, rows: int = 5) -> ft.View:
        """Full-screen shimmer placeholder shown instantly while the real
        view loads. Picks a layout template matching the destination
        route so the skeleton roughly mirrors the real page's shape
        (hero + list, grid, profile header, chat bubbles, form fields,
        etc.) instead of one generic stack of bars everywhere. Swapped
        out for the real ft.View once its data finishes fetching."""
        layout_fn = _resolve_layout(route)
        content = layout_fn() if layout_fn is not _layout_default else layout_fn(rows)

        view = ft.View(
            route=route,
            controls=[
                ft.Container(
                    content=content,
                    expand=True,
                    padding=20,
                )
            ],
            padding=0,
        )
        # Stash the boxes on the view so the shimmer loop can find and
        # animate them without needing a separate registry.
        view.data = _collect_boxes(content)
        return view

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
        if existing_skeleton is not None:
            skel = existing_skeleton
            shimmer_task = existing_shimmer_task
        else:
            skel = skeleton_view(route)
            page.views.append(skel)
            page.update()
            # CRITICAL: page.update() only queues the change — without
            # yielding back to the event loop here, the blocking `await
            # coro` below can start executing before that update has
            # actually been flushed to the client, making the skeleton
            # appear late. asyncio.sleep(0) forces a real scheduler tick
            # so the update is sent immediately.
            await asyncio.sleep(0)
            shimmer_task = page.run_task(run_shimmer, skel.data, skel)

        async def handle_failure(ex: Exception):
            shimmer_task.cancel()
            # Pop the skeleton first — whatever happens next (restored
            # previous view, or dedicated error screen) replaces it.
            if page.views and page.views[-1] is skel:
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
            real_view = await coro
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
        shimmer_task.cancel()

        page.views[-1] = real_view
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
            snack_content_controls = [
                ft.Icon(icon or ft.Icons.WIFI_OFF, color=ft.Colors.ON_PRIMARY, size=20),
                ft.Text(message, color=ft.Colors.ON_PRIMARY, expand=True),
            ]

            if offer_offline and _has_any_downloaded_courses():
                def go_offline(e):
                    page.go("/offline")

                snack_content_controls.append(
                    ft.ElevatedButton(
                        "View Your Downloads",
                        icon=ft.Icons.DOWNLOAD_FOR_OFFLINE,
                        color=ft.Colors.ERROR,
                        bgcolor=ft.Colors.WHITE,
                        on_click=go_offline,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=ft.Padding(12, 6, 12, 6),
                        )
                    )
                )

            snack = ft.SnackBar(
                content=ft.Row(
                    snack_content_controls,
                    spacing=10,
                    tight=True,
                ),
                bgcolor=ft.Colors.ERROR,
                duration=ft.Duration(milliseconds=5000 if offer_offline else 3000),
                behavior=ft.SnackBarBehavior.FLOATING,
                shape=ft.RoundedRectangleBorder(radius=10),
                margin=ft.Margin.only(left=20, right=20, bottom=20),
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
                page.route = previous_view.route
                try:
                    await page.push_route(previous_view.route, skip_route_change_event=True)
                except Exception as resync_ex:
                    print(f"restore_previous_or_fallback: push_route resync failed: {resync_ex!r}")
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

        if not is_public_route(page.route) and not is_offline_capable_route(page.route) and not await is_route_for_downloaded_course(page.route):
            # Show the skeleton IMMEDIATELY, before the auth check even
            # starts — otherwise on a slow connection the screen sits
            # blank during get_current_user_request(), and only pushes
            # the skeleton afterwards for the (much shorter) view fetch.
            skel = skeleton_view(page.route)
            page.views.append(skel)
            page.update()
            await asyncio.sleep(0)
            shimmer_task = page.run_task(run_shimmer, skel.data, skel)

            # Fast local check first — no network call needed to know
            # whether a token even exists.
            token = await page.shared_preferences.get("auth_token")

            if not token:
                shimmer_task.cancel()
                # Pop the skeleton, but NEVER leave page.views empty here.
                # If this is the very first route of the session (cold
                # open straight into a protected route), page.views was
                # empty before the skeleton was pushed, so popping it
                # leaves nothing for the dialog to render on top of —
                # that's the "white screen after the shimmer" bug. Always
                # ensure a real view (login) is underneath the dialog.
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
                page.views.pop()
                fell_back = await restore_previous_or_fallback(page.route, ex)
                page.update()
                await report_failure(fell_back=fell_back, ex=ex)
                return

            if status == 200:
                page.session.store.set("current_user", user_data)
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
                        page.views.pop()
                        fell_back = await restore_previous_or_fallback(page.route, ex)
                        page.update()
                        await report_failure(fell_back=fell_back, ex=ex)
                        return

                    if status == 200:
                        page.session.store.set("current_user", user_data)
                        # Fall through to the normal view-render path below
                        # (do NOT return here) — this is now a success case.
                    else:
                        # Refreshed token STILL failed the current-user
                        # check. Shouldn't normally happen right after a
                        # successful refresh, but fail safe rather than
                        # loop — treat as a genuine session end.
                        shimmer_task.cancel()
                        if page.views and page.views[-1] is skel:
                            page.views.pop()
                        if not page.views:
                            page.views.append(login_view(page))
                            page.update()
                        await page.shared_preferences.remove("auth_token")
                        await page.shared_preferences.remove("refresh_token")
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
                    if page.views and page.views[-1] is skel:
                        page.views.pop()
                    if not page.views:
                        page.views.append(login_view(page))
                        page.update()
                    await page.shared_preferences.remove("auth_token")
                    await page.shared_preferences.remove("refresh_token")
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
        elif page.route == "/":
            page.views.clear()
            page.views.append(login_view(page))
        elif page.route == "/login":
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
        elif troute.match("/courses/:id/stats"):
            await load_view_and_report(course_stats_view(page, troute.id), page.route, active_skeleton, active_shimmer_task)
        elif page.route == "/self-study":
            await load_view_and_report(self_study_view(page), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/organisations/:org_id/playlists"):
            from src.create_playlist import create_playlists_view
            await load_view_and_report(create_playlists_view(page, troute.org_id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/playlists/:id/build"):
            from src.playlist_builder import playlist_builder_view
            await load_view_and_report(playlist_builder_view(page, troute.id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/playlists/:id/settings"):
            from src.playlist_settings import playlist_settings_view
            await load_view_and_report(playlist_settings_view(page, troute.id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/playlists/:id"):
            from src.playlist_view import playlist_view
            await load_view_and_report(playlist_view(page, troute.id), page.route, active_skeleton, active_shimmer_task)
        # --- NEW: Dynamic Organization Courses Route ---
        elif troute.match("/organisations/:org_id/courses"):
            # Extracts the ID from the URL and passes it to the view
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
            await load_view_and_report(
                offline_course_learner_view(page, course_id_param, back_target="/offline"),
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

            # Semantic back-navigation:
            valid_back_targets = ("/offline", "/courses", "/dashboard", "/network", "/self-study", "/organisations")
            if is_from_offline_view:
                back_target = "/offline"
            elif previous_route and (previous_route in valid_back_targets or previous_route.startswith("/playlists/") or previous_route.startswith("/organisations/")):
                back_target = previous_route
            else:
                back_target = "/courses"

            # STRICT OFFLINE LOADING for /view route:
            if (is_from_offline_view or not current_token) and course_downloaded:
                await load_view_and_report(
                    offline_course_learner_view(page, course_id_param, back_target="/offline"),
                    page.route, active_skeleton, active_shimmer_task
                )
            elif current_token and course_downloaded:
                # Normal browsing from online catalog (/courses, /dashboard):
                # Probe network to decide if we can load fresh online course or fall back to offline
                try:
                    probe_status, _ = await get_current_user_request(current_token)
                    online_reachable = probe_status == 200
                except Exception:
                    online_reachable = False

                if online_reachable:
                    await load_view_and_report(
                        course_learner_view(page, course_id_param, back_target=back_target),
                        page.route, active_skeleton, active_shimmer_task
                    )
                else:
                    await load_view_and_report(
                        offline_course_learner_view(page, course_id_param, back_target="/offline"),
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
            await load_view_and_report(offline_courses_view(page), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/member/:user_id"):
            # Extracts the ID from the URL and passes it to the view
            await load_view_and_report(member_profile_view(page, troute.user_id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/organisations/:org_id/courses/:course_id/settings"):
            # Extracts the ID from the URL and passes it to the view
            await load_view_and_report(
                course_settings_view(page, troute.course_id, troute.org_id), page.route,
                active_skeleton, active_shimmer_task,
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
        elif troute.match("/courses/:course_id"):
            # Compute where the back arrow should return to
            valid_back_targets = ("/offline", "/courses", "/dashboard", "/network", "/self-study", "/organisations")
            if previous_route and (previous_route in valid_back_targets or previous_route.startswith("/playlists/") or previous_route.startswith("/organisations/")):
                back_target = previous_route
            else:
                back_target = "/courses"
                
            await load_view_and_report(
                course_details_view(page, troute.course_id, back_target=back_target), page.route,
                active_skeleton, active_shimmer_task,
            )

        elif active_skeleton is not None:
            # Protected route matched none of the branches above — same
            # fix as directly above: actually remove the frozen skeleton,
            # don't just stop its animation. Also a routing bug, not a
            # network/server failure — see note above.
            active_shimmer_task.cancel()
            if page.views and page.views[-1] is active_skeleton:
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
        return route in ["/", "/signup"] or (route or "").startswith("/accept-invite/")

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


ft.run(main, assets_dir="assets")

"""###WEB CONFIG
import flet.fastapi as flet_fastapi
from fastapi import FastAPI, Request


# 1. Initialize a FastAPI app
app = FastAPI()

# 2. The Magic Middleware: This intercepts the outgoing web page and changes the security lock
@app.middleware("http")
async def apply_credentialless_coep(request: Request, call_next):
    response = await call_next(request)
    # Overwrite Flet's default strict header with the browser's suggested bypass
    if "Cross-Origin-Embedder-Policy" in response.headers:
        response.headers["Cross-Origin-Embedder-Policy"] = "credentialless"
    return response

current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Join that path with the "assets" folder name
absolute_assets_path = os.path.join(current_dir, "assets")

# 3. Feed the absolute path into Flet
flet_app = flet_fastapi.app(main, assets_dir=absolute_assets_path, session_timeout_seconds=86400)
app.mount("/", flet_app)
if __name__ == "__main__":
    # Grab Coolify's hidden port variable, or default to 8000 locally
    port = int(os.environ.get("PORT", 8000))

    # Start the server directly from Python, hiding it from Coolify's UI restrictions
    uvicorn.run(app, host="0.0.0.0", port=port)"""