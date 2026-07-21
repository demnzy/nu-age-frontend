import asyncio
import flet as ft
import uvicorn
from src.Login import login_view
from src.course_analytics import course_analytics_view
from src.signup import Signup_view
from src.dashboard import dashboard_view
from src.requests.auth import get_current_user_request
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
import os


async def main(page: ft.Page):
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
            page.views.pop()             # Remove the current view from the stack
            top_view = page.views[-1]    # Look at the view underneath it
            page.go(top_view.route)      # Navigate to that route

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
        ),
        page_transitions=ft.PageTransitionsTheme(
            android="fadeUpwards",
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
            scrim="#302D2D",          # Subtle borders
        ),
        page_transitions=ft.PageTransitionsTheme(
            android="fadeUpwards",
            ios="cupertino",
        ),
    )
    splash_logo = ft.Image(
        src="Nu age new logo.png",
        width=400, height=600, fit="contain",
    )

    # --- 2. FORCE LIGHT MODE ---

    # ─────────────────────────────────────────────
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

    def _error_fallback_view(route: str, ex: Exception) -> ft.View:
        """A visible error screen used whenever a view fails to load —
        whether it raised an exception or silently returned nothing. Ensures
        the user always sees *something* explaining the failure, with a way
        to retry, instead of a dead blank screen."""

        def retry(e):
            page.go(route)

        return ft.View(
            route=route,
            controls=[
                ft.Column(
                    [
                        ft.Icon(ft.Icons.WIFI_OFF, color=ft.Colors.ERROR, size=40),
                        ft.Text("This page couldn't load.", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(str(ex) or type(ex).__name__, size=12, color=ft.Colors.OUTLINE),
                        ft.FilledButton("Retry", on_click=retry),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                    expand=True,
                )
            ],
            padding=20,
        )

    def shimmer_box(radius=12):
        """A single placeholder rectangle. Its opacity gets pulsed by the
        shimmer loop below to create the animated shimmer effect."""
        return ft.Container(
            expand=True,
            border_radius=radius,
            bgcolor=ft.Colors.OUTLINE,
            animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
            opacity=0.35,
        )

    def skeleton_view(route: str, rows: int = 5) -> ft.View:
        """Full-screen shimmer placeholder shown instantly while the real
        view loads. Fills the available width/height with evenly spaced
        rectangles so it never looks sparse or blank on any screen size.
        Swapped out for the real ft.View once its data finishes fetching."""
        boxes = [shimmer_box() for _ in range(rows)]
        boxes.append( ft.Container(
            expand=True,
            border_radius=3,
            bgcolor=ft.Colors.OUTLINE,
            animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
            opacity=0.35,
        ))

        skeleton_column = ft.Column(
            controls=boxes,
            spacing=14,
            expand=True,
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        )

        view = ft.View(
            route=route,
            controls=[
                ft.Container(
                    content=skeleton_column,
                    expand=True,
                    padding=20,
                )
            ],
            padding=0,
        )
        # Stash the boxes on the view so the shimmer loop can find and
        # animate them without needing a separate registry.
        view.data = boxes
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

        on_failure(route, ex) -> bool, if given, is called when the view
        fails to load. It should push whatever should be shown instead
        (typically: restore the previous view) directly onto page.views,
        and return True if it did so (meaning load_view should NOT also
        push its own dedicated error screen) or False if there was nothing
        to fall back to (meaning load_view should show the error screen)."""
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
                fell_back = on_failure(route, ex)

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
    async def route_change(e):
        try:
            await _route_change_inner()
        except Exception as ex:
            # Absolute last line of defense: nothing that happens while
            # building/loading a view should ever be allowed to escape
            # route_change uncaught — an uncaught exception here crashes
            # Flet's session bootstrap itself (AttributeError on a None
            # session), not just this one navigation.
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
                # If even the fallback error view fails to render, there's
                # nothing more we can safely do from here.
                pass

    async def _route_change_inner():
        # Remember what was on screen before this navigation, so that if
        # the new route fails to load we can restore it (with an error
        # dialog on top) instead of leaving the user on a dead-end error
        # page or a blank screen.
        previous_view = page.views[-1] if page.views else None

        page.views.clear()
        troute = ft.TemplateRoute(page.route)

        def is_public_route(route):
            return route in ["/", "/signup"] or route.startswith("/accept-invite/")

        def show_error_dialog(message: str = "Network error, please try again", title: str = None):
            """Sleek, non-blocking error notice shown after falling back to
            the previous view. Uses a SnackBar (not a modal AlertDialog) so
            the view underneath stays fully interactable — the user can keep
            tapping around immediately, the notice just floats on top and
            dismisses itself."""
            snack = ft.SnackBar(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.WIFI_OFF, color=ft.Colors.ON_PRIMARY, size=20),
                        ft.Text(message, color=ft.Colors.ON_PRIMARY),
                    ],
                    spacing=10,
                    tight=True,
                ),
                bgcolor=ft.Colors.ERROR,
                duration=3000,  # ms — auto-dismisses, no action needed from the user
                behavior=ft.SnackBarBehavior.FLOATING,
                shape=ft.RoundedRectangleBorder(radius=10),
                margin=ft.margin.only(left=20, right=20, bottom=20),
            )
            page.overlay.append(snack)
            snack.open = True
            page.update()

        def restore_previous_or_fallback(route: str, ex: Exception):
            """On failure: if we have a previous view to go back to, restore
            it (caller shows a dialog on top). Otherwise — e.g. this was the
            very first view of the session — show the dedicated error
            fallback screen since there's nothing to fall back to."""
            if previous_view is not None:
                page.views.append(previous_view)
                # page.route currently points at the route that just failed
                # to load (e.g. "/courses"), but the view actually on screen
                # is the previous one (e.g. "/dashboard"). Keep them in sync
                # so back-navigation (on_view_pop) and any future route
                # comparisons aren't looking at a stale/wrong route.
                page.route = previous_view.route
                return True
            else:
                page.views.append(_error_fallback_view(route, ex))
                return False

        # Tracks whether the last load_view() call fell back to a previous
        # view (vs. showing the dedicated error screen) so we know whether
        # to also pop up an explanatory dialog afterwards.
        failure_state = {"fell_back": False, "ex": None}

        def on_view_failure(route: str, ex: Exception) -> bool:
            fell_back = restore_previous_or_fallback(route, ex)
            failure_state["fell_back"] = fell_back
            failure_state["ex"] = ex
            return fell_back

        async def load_view_and_report(coro, route: str, skel=None, shimmer=None):
            """Thin wrapper around load_view() that also shows the
            'something went wrong' dialog afterwards if it fell back to the
            previous view, so the user understands why the screen didn't
            change even though nothing crashed loudly."""
            failure_state["fell_back"] = False
            failure_state["ex"] = None
            await load_view(coro, route, skel, shimmer, on_failure=on_view_failure)
            if failure_state["fell_back"]:
                show_error_dialog("Network error, please try again")

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
                dlg.open = False
                page.update()
                if redirect_to_login:
                    page.go("/")

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
            page.dialog = dlg
            dlg.open = True
            page.update()

            # Auto-dismiss/redirect after a few seconds if they don't tap the button
            await asyncio.sleep(auto_redirect_seconds)
            if dlg.open:
                close_dialog()

        if not is_public_route(page.route):
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
                page.views.pop()
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
                fell_back = restore_previous_or_fallback(page.route, ex)
                page.update()
                if fell_back:
                    show_error_dialog("Network error, please try again")
                else:
                    await show_session_expired_dialog(
                        f"Couldn't reach the server: {ex}",
                        auto_redirect_seconds=6,
                        title="Connection error",
                        redirect_to_login=False,
                    )
                return

            if status == 200:
                page.session.store.set("current_user", user_data)
            elif status in (401, 403):
                # Genuinely expired/invalid token — safe to clear it.
                shimmer_task.cancel()
                page.views.pop()
                await page.shared_preferences.remove("auth_token")
                await show_session_expired_dialog(
                    "Your session has ended. Please log in again to continue."
                )
                return
            else:
                # Some other backend error (500, 503, etc). The token might
                # still be valid — don't destroy it. Fall back to whatever
                # was on screen before, rather than a dead-end dialog.
                shimmer_task.cancel()
                page.views.pop()
                server_ex = RuntimeError(f"Server error {status}")
                fell_back = restore_previous_or_fallback(page.route, server_ex)
                page.update()
                if fell_back:
                    show_error_dialog("Network error, please try again")
                else:
                    await show_session_expired_dialog(
                        f"Something went wrong (error {status}). Please try again.",
                        auto_redirect_seconds=6,
                        title="Server error",
                        redirect_to_login=False,
                    )
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
        if page.route == "/dashboard":
            await load_view_and_report(dashboard_view(page), page.route, active_skeleton, active_shimmer_task)
        elif page.route == "/":
            page.views.append(login_view(page))
        elif page.route == "/login":
            page.views.append(login_view(page))
        elif page.route == "/signup":
            page.views.append(Signup_view(page))
        elif page.route == "/profile":
            await load_view_and_report(profile_view(page), page.route, active_skeleton, active_shimmer_task)
        elif page.route == "/courses":
            await load_view_and_report(courses_view(page), page.route, active_skeleton, active_shimmer_task)
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
        # --- NEW: Dynamic Organization Courses Route ---
        elif troute.match("/organisations/:org_id/courses"):
            # Extracts the ID from the URL and passes it to the view
            await load_view_and_report(create_courses_view(page, troute.org_id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/courses/:course_id/manage"):
            # Extracts the ID from the URL and passes it to the view
            await load_view_and_report(course_builder_view(page, troute.course_id), page.route, active_skeleton, active_shimmer_task)
        elif troute.match("/courses/:course_id/view"):
            # Extracts the ID from the URL and passes it to the view
            await load_view_and_report(course_learner_view(page, troute.course_id), page.route, active_skeleton, active_shimmer_task)
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
        elif page.route.startswith("/courses/"):
            route_parts = page.route.split("/")
            # Check if we have at least: / , courses , id
            if len(route_parts) > 2:
                course_id = route_parts[2]

                # Check if the name exists at index 3, else use None
                course_name = route_parts[3] if len(route_parts) > 3 else None

                # Pass both to your view function
                await load_view_and_report(
                    course_details_view(page, course_id, course_name), page.route,
                    active_skeleton, active_shimmer_task,
                )
            elif active_skeleton is not None:
                # No sub-route matched, but we already pushed a skeleton
                # during the auth check — don't leave it stuck on screen.
                active_shimmer_task.cancel()
        elif active_skeleton is not None:
            # Protected route matched none of the branches above — clean up
            # the skeleton so it doesn't sit there shimmering forever.
            active_shimmer_task.cancel()

        saved_mode = await page.shared_preferences.get("dark_mode")
        await apply_theme(saved_mode == "true")
        page.update()

    page.on_route_change = route_change

    # --- THE FIX ---
    # Previously this unconditionally overwrote page.route with "/dashboard"
    # or "/", which destroyed real deep links (e.g. /accept-invite/<uuid>
    # from an email) before route_change ever saw them. Now we only apply
    # that default when there's no real route to honor (fresh load with no
    # path, or bare "/").
    if not page.route or page.route == "/":
        page.route = "/dashboard" if await page.shared_preferences.get("auth_token") else "/"

    await route_change(None)


#ft.run(main, assets_dir="assets")

###WEB CONFIG
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
    uvicorn.run(app, host="0.0.0.0", port=port)