import flet as ft
import re
from src.requests.auth import login_request
from src.components.landing_navbar import get_landing_appbar
from src.utils.db_manager import log_daily_activity
import asyncio
from src.requests.auth import send_password_reset_otp, verify_password
from src.local_db import has_any_downloaded_courses


def is_dark_mode(page: ft.Page) -> bool:
    if getattr(page, "theme_mode", None) == ft.ThemeMode.DARK:
        return True
    if getattr(page, "theme_mode", None) == ft.ThemeMode.LIGHT:
        return False
    return getattr(page, "platform_brightness", None) == ft.Brightness.DARK


def login_view(page: ft.Page):
    is_processing = False
    is_dark = is_dark_mode(page)

    # ── shared state ──────────────────────────────────────────────
    custom_message   = ft.Text("", size=13)
    validation_error = ft.Text(
        "",
        color=ft.Colors.RED_700,
        size=12,
        weight=ft.FontWeight.W_500,
    )

    # ── helpers ───────────────────────────────────────────────────
    def set_error(msg: str):
        """Show inline validation error."""
        validation_error.value = msg
        page.update()

    def clear_error():
        validation_error.value = ""
        page.update()

    # ── dialogs ───────────────────────────────────────────────────
    def _dismiss_dialog(e):
        # page.pop_dialog() only mutates dialog state — it doesn't
        # trigger a repaint on its own, so every dismiss handler needs
        # the follow-up page.update() or the dialog visually never
        # closes even though it's technically no longer "open".
        page.pop_dialog()
        page.update()

    error_dialog = ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED,
                        color=ft.Colors.RED_600, size=22),
                ft.Text("Login Failed", size=18, weight=ft.FontWeight.W_600),
            ],
            spacing=8,
            wrap=True,
        ),
        content=custom_message,
        actions=[
            ft.TextButton(
                "Dismiss",
                on_click=_dismiss_dialog,
                style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
            )
        ],
    )

    timeout_dialog = ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.WIFI_OFF_ROUNDED,
                        color=ft.Colors.ORANGE_700, size=22),
                ft.Text("Connection Problem", size=18,
                        weight=ft.FontWeight.W_600),
            ],
            spacing=8,
            wrap=True,
        ),
        content=ft.Text(
            "Please check your internet "
            "connection and try again.",
            size=13,
        ),
        actions=[
            ft.TextButton(
                "Dismiss",
                on_click=_dismiss_dialog,
                style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
            )
        ],
    )

    def _go_to_offline_courses(e):
        # Explicitly set .open = False in addition to pop_dialog() — we're
        # about to navigate to /offline, which pushes a new View on TOP of
        # this one rather than replacing it (see main.py's routing: /offline
        # goes through load_view_and_report, which appends). This login
        # view and its dialog are never torn down, just buried. If the user
        # later taps back, this same timeout_dialog instance resurfaces
        # exactly as it was — so its .open flag needs to already be False,
        # not just "popped" in whatever transient sense pop_dialog tracks.
        timeout_dialog.open = False
        page.pop_dialog()
        page.update()
        page.go("/offline")

    def _show_connectivity_dialog():
        # Rebuilt each time (rather than a static module-level actions
        # list) because whether there's anything downloaded can change
        # between one failed login attempt and the next — e.g. a course
        # finished downloading in a previous session. Checking fresh here
        # keeps this in sync with local_db.py, the same source of truth
        # main.py's error-fallback screen uses for the identical decision.
        actions = [
        ]
        if has_any_downloaded_courses(page):
            actions.insert(
                0,
                ft.TextButton(
                    "View downloaded courses",
                    icon=ft.Icons.DOWNLOAD_FOR_OFFLINE_OUTLINED,
                    on_click=_go_to_offline_courses,
                    style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
                ),
            )
        timeout_dialog.actions = actions
        page.show_dialog(timeout_dialog)

    # ── validation ────────────────────────────────────────────────
    def validate_inputs(e):
        all_filled = all(
            f and f.strip() for f in [email.value, password.value]
        )

        if not all_filled:
            validation_error.value = "Email/username and password are required."
        else:
            validation_error.value = ""

        Submit.disabled = not all_filled
        page.update()

    # ── submit handler ────────────────────────────────────────────
    async def handle_submit(e):
        nonlocal is_processing
        if is_processing:
            return

        is_processing   = True
        Submit.disabled = True
        Submit.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        clear_error()
        page.update()

        try:
            status, data = await asyncio.wait_for(
                login_request(email.value, password.value),
                timeout=15,
            )
            Submit.content = ft.Text("Sign In", size=14, weight=ft.FontWeight.W_600)
            if status == 200:
                token = data.get("access_token")
                await page.shared_preferences.set("auth_token", token)
                await page.shared_preferences.set("refresh_token", data["refresh_token"])
                log_daily_activity()
                page.go("/dashboard")

            elif status == 404:
                set_error(
                    "No account found for that email. "
                    "Please check and try again."
                )

            elif status == 403:
                set_error("Incorrect password. Please try again.")

            elif status == 429:
                set_error(
                    "Too many login attempts. Please wait a moment "
                    "before trying again."
                )

            elif status in (503, 504):
                _show_connectivity_dialog()

            elif status is not None:
                custom_message.value = (
                    f"Unexpected error, {data['detail']} "
                )
                page.show_dialog(error_dialog)

        except asyncio.TimeoutError:
            _show_connectivity_dialog()

        except Exception as ex:
            custom_message.value = (
                "Something went wrong while connecting to the server. "
                f"Detail: {type(ex).__name__}."
            )
            page.show_dialog(error_dialog)

        finally:
            is_processing   = False
            Submit.disabled = False
            Submit.content  = ft.Text("Sign In", size=14, weight=ft.FontWeight.W_600)
            page.update()

    # ── field factory ─────────────────────────────────────────────
    def field(**kwargs) -> ft.TextField:
        return ft.TextField(
            height=40,
            text_size=13,
            border_radius=10,
            border_color=ft.Colors.OUTLINE,
            focused_border_color=ft.Colors.PRIMARY,
            cursor_color=ft.Colors.PRIMARY,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            on_change=validate_inputs,
            **kwargs,
        )

    # ── fields ────────────────────────────────────────────────────
    email = field(
        label="Email or Username",
        hint_text="name@example.com",
        prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
        keyboard_type=ft.KeyboardType.EMAIL,
        expand=True,
    )
    password = field(
        label="Password",
        hint_text="••••••••••••",
        prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
        password=True,
        can_reveal_password=True,
        expand=True,
        on_submit=handle_submit,
    )

    # ── submit button ─────────────────────────────────────────────
    Submit = ft.ElevatedButton(
        content=ft.Text("Sign In", size=13, weight=ft.FontWeight.W_600),
        expand=True,
        color=ft.Colors.ON_PRIMARY,
        bgcolor=ft.Colors.PRIMARY,
        height=40,
        disabled=True,
        on_click=handle_submit,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            elevation=0,
        ),
    )
    # ── Industry-Grade Forgot Password Flow (Spacious 4-Step Wizard) ──
    resend_timer_active = False

    email_error_text = ft.Text("", color=ft.Colors.RED_600, size=11.5, text_align=ft.TextAlign.CENTER)
    otp_error_text = ft.Text("", color=ft.Colors.RED_600, size=11.5, text_align=ft.TextAlign.CENTER)
    reset_error_text = ft.Text("", color=ft.Colors.RED_600, size=11.5, text_align=ft.TextAlign.CENTER)
    password_hint_text = ft.Text("", size=11, color=ft.Colors.GREY_600, text_align=ft.TextAlign.CENTER)

    def validate_email_input(e=None):
        val = (email_request.value or "").strip()
        email_ok = bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', val))
        if not val:
            email_error_text.value = ""
            send_email_btn.disabled = True
        elif not email_ok:
            email_error_text.value = "Please enter a valid email address."
            send_email_btn.disabled = True
        else:
            email_error_text.value = ""
            send_email_btn.disabled = False
        page.update()

    def validate_otp_input(e=None):
        raw = otp_input.value or ""
        # Keep only digits, strictly up to 6
        digits = "".join(ch for ch in raw if ch.isdigit())[:6]
        if raw != digits:
            otp_input.value = digits
        otp_error_text.value = ""
        continue_to_pwd_btn.disabled = len(digits) != 6
        page.update()

    def validate_password_inputs(e=None):
        p1 = new_password_input.value or ""
        p2 = confirm_password_input.value or ""

        reset_error_text.value = ""

        if len(p1) > 0 and len(p1) < 6:
            password_hint_text.value = "Password must be at least 6 characters."
            password_hint_text.color = ft.Colors.ORANGE_700
        elif p1 and p2 and p1 != p2:
            password_hint_text.value = "Passwords do not match."
            password_hint_text.color = ft.Colors.RED_600
        elif p1 and p2 and p1 == p2 and len(p1) >= 6:
            password_hint_text.value = "Passwords match ✓"
            password_hint_text.color = ft.Colors.GREEN_700
        else:
            password_hint_text.value = ""

        is_pwd_ok = len(p1) >= 6 and p1 == p2
        reset_password_btn.disabled = not is_pwd_ok
        page.update()

    email_request = ft.TextField(
        label="Email Address",
        hint_text="e.g. name@example.com",
        prefix_icon=ft.Icons.EMAIL_OUTLINED,
        height=44,
        text_size=13.5,
        border_radius=10,
        border_color=ft.Colors.OUTLINE,
        focused_border_color=ft.Colors.PRIMARY,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        keyboard_type=ft.KeyboardType.EMAIL,
        on_change=validate_email_input,
        on_submit=lambda _: page.run_task(send_verification_email) if not send_email_btn.disabled else None,
    )

    otp_input = ft.TextField(
        text_align=ft.TextAlign.CENTER,
        text_size=20,
        keyboard_type=ft.KeyboardType.NUMBER,
        border_radius=12,
        border_color=ft.Colors.OUTLINE,
        focused_border_color=ft.Colors.PRIMARY,
        cursor_color=ft.Colors.PRIMARY,
        cursor_height=20,
        hint_text="000000",
        height=52,
        width=250,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        text_style=ft.TextStyle(letter_spacing=6, weight=ft.FontWeight.BOLD),
        on_change=validate_otp_input,
        on_submit=lambda _: switch_step(3) if not continue_to_pwd_btn.disabled else None,
    )

    new_password_input = ft.TextField(
        label="New Password",
        hint_text="At least 6 characters",
        prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
        height=44,
        text_size=13.5,
        border_radius=10,
        border_color=ft.Colors.OUTLINE,
        focused_border_color=ft.Colors.PRIMARY,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        password=True,
        can_reveal_password=True,
        on_change=validate_password_inputs,
    )

    confirm_password_input = ft.TextField(
        label="Confirm New Password",
        hint_text="Re-type new password",
        prefix_icon=ft.Icons.LOCK_RESET_ROUNDED,
        height=44,
        text_size=13.5,
        border_radius=10,
        border_color=ft.Colors.OUTLINE,
        focused_border_color=ft.Colors.PRIMARY,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        password=True,
        can_reveal_password=True,
        on_change=validate_password_inputs,
        on_submit=lambda _: page.run_task(handle_verification) if not reset_password_btn.disabled else None,
    )

    send_email_btn = ft.ElevatedButton(
        content=ft.Text("Send Recovery Code", size=13.5, weight=ft.FontWeight.W_600),
        expand=True,
        height=42,
        color=ft.Colors.ON_PRIMARY,
        bgcolor=ft.Colors.PRIMARY,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
        disabled=True,
        on_click=lambda e: page.run_task(send_verification_email),
    )

    continue_to_pwd_btn = ft.ElevatedButton(
        content=ft.Text("Continue", size=13.5, weight=ft.FontWeight.W_600),
        expand=True,
        height=42,
        color=ft.Colors.ON_PRIMARY,
        bgcolor=ft.Colors.PRIMARY,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
        disabled=True,
        on_click=lambda _: switch_step(3),
    )

    reset_password_btn = ft.ElevatedButton(
        content=ft.Text("Reset Password", size=13.5, weight=ft.FontWeight.W_600),
        expand=True,
        height=42,
        color=ft.Colors.ON_PRIMARY,
        bgcolor=ft.Colors.PRIMARY,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
        disabled=True,
        on_click=lambda e: page.run_task(handle_verification),
    )

    resend_text = ft.Text("Didn't receive code? Resend in 60s", size=12, color=ft.Colors.GREY_600)
    resend_btn = ft.TextButton(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.REFRESH_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                ft.Text("Resend code", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
            ],
            spacing=4,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        style=ft.ButtonStyle(padding=ft.Padding.all(0)),
        visible=False,
        on_click=lambda e: page.run_task(handle_resend_code),
    )

    resend_row = ft.Row(
        controls=[resend_text, resend_btn],
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        wrap=True,
    )

    def close_modal(e=None):
        nonlocal resend_timer_active
        resend_timer_active = False
        page.pop_dialog()
        page.update()

    async def start_resend_countdown():
        nonlocal resend_timer_active
        resend_timer_active = True
        resend_btn.visible = False
        resend_text.visible = True

        for sec in range(60, 0, -1):
            if not resend_timer_active:
                return
            resend_text.value = f"Didn't receive code? Resend in {sec}s"
            try:
                page.update()
            except Exception:
                return
            await asyncio.sleep(1)

        if resend_timer_active:
            resend_text.visible = False
            resend_btn.visible = True
            try:
                page.update()
            except Exception:
                pass

    async def send_verification_email(e=None):
        send_email_btn.disabled = True
        send_email_btn.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        email_error_text.value = ""
        page.update()

        target_email = (email_request.value or "").strip()
        try:
            status, data = await send_password_reset_otp(target_email)

            if status == 200:
                send_email_btn.content = ft.Text("Send Recovery Code", size=13.5, weight=ft.FontWeight.W_600)
                switch_step(2)
            elif status == 404:
                email_error_text.value = "No account found with this email address."
                send_email_btn.disabled = False
                send_email_btn.content = ft.Text("Send Recovery Code", size=13.5, weight=ft.FontWeight.W_600)
                page.update()
            else:
                err_msg = data.get("detail", "Failed to send reset code.") if isinstance(data, dict) else "Failed to send reset code."
                email_error_text.value = err_msg
                send_email_btn.disabled = False
                send_email_btn.content = ft.Text("Send Recovery Code", size=13.5, weight=ft.FontWeight.W_600)
                page.update()
        except Exception as ex:
            email_error_text.value = f"Connection error: {type(ex).__name__}"
            send_email_btn.disabled = False
            send_email_btn.content = ft.Text("Send Recovery Code", size=13.5, weight=ft.FontWeight.W_600)
            page.update()

    async def handle_resend_code(e=None):
        resend_btn.visible = False
        resend_text.visible = True
        resend_text.value = "Sending code..."
        otp_error_text.value = ""
        page.update()

        target_email = (email_request.value or "").strip()
        try:
            status, data = await send_password_reset_otp(target_email)
            if status == 200:
                page.run_task(start_resend_countdown)
            else:
                err_msg = data.get("detail", "Failed to resend code.") if isinstance(data, dict) else "Failed to resend code."
                otp_error_text.value = err_msg
                resend_text.visible = False
                resend_btn.visible = True
                page.update()
        except Exception as ex:
            otp_error_text.value = f"Connection error: {type(ex).__name__}"
            resend_text.visible = False
            resend_btn.visible = True
            page.update()

    async def handle_verification(e=None):
        reset_password_btn.disabled = True
        reset_password_btn.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        reset_error_text.value = ""
        page.update()

        try:
            status, data = await verify_password(
                email=email_request.value.strip(),
                new_password=new_password_input.value,
                otp=otp_input.value.strip(),
            )

            if status == 200:
                nonlocal resend_timer_active
                resend_timer_active = False
                switch_step(4)
            else:
                err_msg = data.get("detail", "Verification failed. Please try again.") if isinstance(data, dict) else "Verification failed."
                if "code" in err_msg.lower() or "otp" in err_msg.lower():
                    otp_error_text.value = err_msg
                    switch_step(2)
                else:
                    reset_error_text.value = err_msg
                    reset_password_btn.disabled = False
                    reset_password_btn.content = ft.Text("Reset Password", size=13.5, weight=ft.FontWeight.W_600)
                    page.update()
        except Exception as ex:
            reset_error_text.value = f"Connection error: {type(ex).__name__}"
            reset_password_btn.disabled = False
            reset_password_btn.content = ft.Text("Reset Password", size=13.5, weight=ft.FontWeight.W_600)
            page.update()

    def finish_reset_flow(e=None):
        close_modal(e)
        email.value = (email_request.value or "").strip()
        password.value = ""
        success_snack = ft.SnackBar(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                    ft.Text("Password updated! Please sign in with your new password.", color=ft.Colors.WHITE, size=12.5),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.GREEN_700,
            behavior=ft.SnackBarBehavior.FLOATING,
            duration=ft.Duration(milliseconds=4000),
        )
        if hasattr(page, "open"):
            page.open(success_snack)
        else:
            page.overlay.append(success_snack)
            success_snack.open = True
        page.update()

    finish_btn = ft.ElevatedButton(
        content=ft.Text("Sign In with New Password", size=13.5, weight=ft.FontWeight.W_600),
        expand=True,
        height=42,
        color=ft.Colors.ON_PRIMARY,
        bgcolor=ft.Colors.PRIMARY,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
        on_click=finish_reset_flow,
    )

    email_sent_info = ft.Column(
        controls=[],
        spacing=4,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # ── Step Views (Spacious, Uncluttered, Elegant) ───────────────
    step_1_view = ft.Column(
        controls=[
            ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.LOCK_RESET_ROUNDED, color=ft.Colors.PRIMARY, size=26),
                        width=56,
                        height=56,
                        border_radius=28,
                        bgcolor="#E8F7EB",
                        alignment=ft.Alignment.CENTER,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Container(height=10),
            ft.Text(
                "Forgot Password?",
                size=20,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Text(
                "Enter your account email to receive a 6-digit recovery code.",
                size=13,
                color=ft.Colors.GREY_600,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(height=16),
            email_request,
            email_error_text,
            ft.Container(height=12),
            ft.Row([send_email_btn]),
            ft.Container(height=12),
            ft.Row(
                [
                    ft.Text("Remember your password?", size=12, color=ft.Colors.GREY_600),
                    ft.TextButton(
                        "Back to Sign In",
                        on_click=close_modal,
                        style=ft.ButtonStyle(
                            color=ft.Colors.PRIMARY,
                            padding=ft.Padding.only(left=4),
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=0,
                wrap=True,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
        spacing=2,
    )

    step_2_view = ft.Column(
        controls=[
            ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.MARK_EMAIL_READ_ROUNDED, color=ft.Colors.PRIMARY, size=26),
                        width=56,
                        height=56,
                        border_radius=28,
                        bgcolor="#E8F7EB",
                        alignment=ft.Alignment.CENTER,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Container(height=10),
            ft.Text(
                "Enter Verification Code",
                size=20,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE,
                text_align=ft.TextAlign.CENTER,
            ),
            email_sent_info,
            ft.Container(height=16),
            ft.Row([otp_input], alignment=ft.MainAxisAlignment.CENTER),
            otp_error_text,
            ft.Container(height=14),
            ft.Row([continue_to_pwd_btn]),
            ft.Container(height=12),
            resend_row,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
        spacing=2,
    )

    step_3_view = ft.Column(
        controls=[
            ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.SHIELD_ROUNDED, color=ft.Colors.PRIMARY, size=26),
                        width=56,
                        height=56,
                        border_radius=28,
                        bgcolor="#E8F7EB",
                        alignment=ft.Alignment.CENTER,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Container(height=10),
            ft.Text(
                "Create New Password",
                size=20,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Text(
                "Choose a strong password with at least 6 characters.",
                size=13,
                color=ft.Colors.GREY_600,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(height=14),
            new_password_input,
            ft.Container(height=6),
            confirm_password_input,
            password_hint_text,
            reset_error_text,
            ft.Container(height=14),
            ft.Row([reset_password_btn]),
            ft.Container(height=10),
            ft.Row(
                [
                    ft.TextButton(
                        "Back to code entry",
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: switch_step(2),
                        style=ft.ButtonStyle(color=ft.Colors.GREY_600),
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                wrap=True,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
        spacing=2,
    )

    step_4_view = ft.Column(
        controls=[
            ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.PRIMARY, size=34),
                        width=64,
                        height=64,
                        border_radius=32,
                        bgcolor="#E8F7EB",
                        alignment=ft.Alignment.CENTER,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Container(height=12),
            ft.Text(
                "Password Reset Complete!",
                size=20,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(height=4),
            ft.Text(
                "Your password has been successfully updated. You can now sign in with your new credentials.",
                size=13,
                color=ft.Colors.GREY_600,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(height=18),
            ft.Row([finish_btn]),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
        spacing=2,
    )

    step_container = ft.Container(content=step_1_view)

    def get_dialog_content_width() -> int:
        w = page.width or (page.window.width if hasattr(page, "window") and page.window.width else None)
        if not w:
            ua = (getattr(page, "client_user_agent", None) or "").lower()
            if any(m in ua for m in ["android", "iphone", "ipad", "mobile"]):
                w = 360
            elif getattr(page, "platform", None) in [ft.PagePlatform.ANDROID, ft.PagePlatform.IOS]:
                w = 360
            else:
                w = 460
        if w < 500:
            return max(260, min(360, w - 48))
        return 420

    def switch_step(step: int):
        nonlocal resend_timer_active
        modal_content_container.width = get_dialog_content_width()
        if step == 1:
            resend_timer_active = False
            step_container.content = step_1_view
        elif step == 2:
            target_email = (email_request.value or "").strip()
            email_sent_info.controls = [
                ft.Text(
                    spans=[
                        ft.TextSpan("We sent a 6-digit recovery code to\n"),
                        ft.TextSpan(target_email, style=ft.TextStyle(weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)),
                    ],
                    size=12,
                    color=ft.Colors.GREY_600,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Row(
                    [
                        ft.Text("Wrong email?", size=11.5, color=ft.Colors.GREY_500),
                        ft.TextButton(
                            "Change email",
                            on_click=lambda _: switch_step(1),
                            style=ft.ButtonStyle(color=ft.Colors.PRIMARY, padding=ft.Padding.only(left=2)),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=0,
                    wrap=True,
                ),
            ]
            step_container.content = step_2_view
            page.run_task(start_resend_countdown)
        elif step == 3:
            step_container.content = step_3_view
        elif step == 4:
            step_container.content = step_4_view
        page.update()

    modal_content_container = ft.Container(
        width=get_dialog_content_width(),
        content=ft.Column(
            controls=[
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            icon_size=20,
                            icon_color=ft.Colors.GREY_500,
                            on_click=close_modal,
                            tooltip="Close",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
                step_container,
            ],
            tight=True,
            spacing=0,
        ),
        padding=ft.Padding.symmetric(horizontal=4, vertical=0),
    )

    forgot_password_dialog = ft.AlertDialog(
        modal=True,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        shape=ft.RoundedRectangleBorder(radius=20),
        content=modal_content_container,
    )

    def reset_forgot_password_modal(e=None):
        nonlocal resend_timer_active
        resend_timer_active = False

        if email.value and "@" in email.value:
            email_request.value = email.value.strip()
            validate_email_input(None)
        else:
            email_request.value = ""
            email_error_text.value = ""
            send_email_btn.disabled = True

        send_email_btn.content = ft.Text("Send Recovery Code", size=13.5, weight=ft.FontWeight.W_600)

        otp_input.value = ""
        new_password_input.value = ""
        confirm_password_input.value = ""
        password_hint_text.value = ""
        otp_error_text.value = ""
        reset_error_text.value = ""
        continue_to_pwd_btn.disabled = True
        reset_password_btn.disabled = True
        reset_password_btn.content = ft.Text("Reset Password", size=13.5, weight=ft.FontWeight.W_600)

        modal_content_container.width = get_dialog_content_width()
        switch_step(1)
        page.show_dialog(forgot_password_dialog)
    # ── Remember Me & Forgot Password ────────────────────────────
    remember_me = ft.Checkbox(
        label="Remember me",
        value=True,
        active_color=ft.Colors.PRIMARY,
        check_color=ft.Colors.WHITE,
        label_style=ft.TextStyle(size=12, color=ft.Colors.GREY_700),
    )

    forgot_password_btn = ft.TextButton(
        "Forgot Password?",
        on_click=reset_forgot_password_modal,
        style=ft.ButtonStyle(
            color=ft.Colors.PRIMARY,
            padding=ft.Padding.all(0),
        ),
    )

    # ── Offline Courses Quick Access ──────────────────────────────
    is_web = getattr(page, "web", False)
    offline_courses_btn = ft.OutlinedButton(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.DOWNLOAD_FOR_OFFLINE_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                ft.Text("Access Downloaded Courses (Offline)", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
        ),
        height=38,
        expand=True,
        visible=not is_web,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            side=ft.BorderSide(1, ft.Colors.with_opacity(0.25, ft.Colors.PRIMARY)),
            bgcolor={
                ft.ControlState.HOVERED: ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.03, ft.Colors.PRIMARY),
            },
        ),
        on_click=lambda _: page.go("/offline"),
    )

    # ── Left Hero Panel (Desktop) ─────────────────────────────────
    hero_panel = ft.Container(
        width=350,
        bgcolor="#18231E" if is_dark else "#F2FBF4",
        border_radius=ft.BorderRadius.only(top_left=20, bottom_left=20),
        padding=ft.Padding.symmetric(horizontal=20, vertical=12),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=12, color=ft.Colors.PRIMARY),
                            ft.Text("Nu Age LMS", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
                        ],
                        tight=True,
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=3),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                    border_radius=20,
                ),
                ft.Container(height=2),
                ft.Image(
                    src="login_hero.png",
                    width=210,
                    height=145,
                    fit=ft.BoxFit.CONTAIN,
                ),
                ft.Container(height=2),
                ft.Text(
                    spans=[
                        ft.TextSpan("A "),
                        ft.TextSpan(
                            "Nu",
                            style=ft.TextStyle(
                                color=ft.Colors.SECONDARY,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ),
                        ft.TextSpan(" Way to Learn"),
                    ],
                    size=17,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.ON_SURFACE,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=2,
        ),
    )

    # ── Right Form Panel ──────────────────────────────────────────
    form_content = ft.Column(
        controls=[
            # Top Branding
            ft.Row(
                [
                    ft.Image(src="icon.png", width=24, height=24, fit=ft.BoxFit.CONTAIN),
                    ft.Text("Nu Age", size=18, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                ],
                spacing=7,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Text(
                "Login",
                size=22,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE,
            ),
            ft.Text(
                "Enter your credentials to login to your account",
                size=12,
                color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_500,
            ),
            ft.Container(height=2),

            # Form Fields
            ft.Row([email]),
            ft.Container(height=2),
            ft.Row([password]),

            # Inline Validation Error
            validation_error,

            # Remember Me + Forgot Password
            ft.Row(
                [remember_me, forgot_password_btn],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),

            # Submit Button
            ft.Row(controls=[Submit]),

            # Offline Downloads Quick Access Button
            ft.Row(controls=[offline_courses_btn], visible=not is_web),

            # Sign Up Link
            ft.Row(
                controls=[
                    ft.Text(
                        "Don't have an account?",
                        size=12,
                        color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600,
                    ),
                    ft.TextButton(
                        "Sign Up",
                        on_click=lambda _: page.go("/signup"),
                        style=ft.ButtonStyle(
                            color=ft.Colors.PRIMARY,
                            padding=ft.Padding.only(left=4),
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=0,
                wrap=True,
            ),

            # Footer
            ft.Container(height=2),
            ft.Text(
                "© 2026 Nu Age Learning · All rights reserved",
                size=10,
                color=ft.Colors.GREY_500 if is_dark else ft.Colors.GREY_400,
                text_align=ft.TextAlign.CENTER,
            ),
        ],
        spacing=5,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    form_panel = ft.Container(
        width=460,
        padding=ft.Padding.symmetric(horizontal=32, vertical=14),
        alignment=ft.Alignment.CENTER,
        content=form_content,
    )

    # ── Main Login Card ───────────────────────────────────────────
    card_row = ft.Row(
        controls=[hero_panel, form_panel],
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
    )

    login_card = ft.Container(
        bgcolor=ft.Colors.SURFACE,
        border_radius=20,
        shadow=ft.BoxShadow(
            blur_radius=32,
            spread_radius=0,
            color=ft.Colors.with_opacity(0.22 if is_dark else 0.08, ft.Colors.BLACK),
            offset=ft.Offset(0, 8),
        ),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.06, ft.Colors.BLACK)),
        content=card_row,
    )

    # ── Responsive Layout Logic ───────────────────────────────────
    def get_is_desktop(w: int | None) -> bool:
        if w is not None and w > 0:
            return w >= 800
        if getattr(page, "platform", None) in [ft.PagePlatform.ANDROID, ft.PagePlatform.IOS]:
            return False
        ua = (getattr(page, "client_user_agent", None) or "").lower()
        if any(m in ua for m in ["android", "iphone", "ipad", "mobile"]):
            return False
        if hasattr(page, "window") and getattr(page.window, "width", None) and page.window.width > 0:
            return page.window.width >= 800
        return False

    def update_responsive_layout(w: int | None):
        is_dark_curr = is_dark_mode(page)
        hero_panel.bgcolor = "#18231E" if is_dark_curr else "#F2FBF4"
        login_card.border = ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark_curr else ft.Colors.with_opacity(0.06, ft.Colors.BLACK))
        if 'view' in locals():
            view.bgcolor = "#121212" if is_dark_curr else "#F8FAFC"

        is_desktop = get_is_desktop(w)
        hero_panel.visible = is_desktop

        if is_desktop:
            effective_w = w if (w and w > 0) else 900
            card_width = min(820, max(740, effective_w - 40))
            hero_width = 350
            form_width = card_width - hero_width
            login_card.width = card_width
            hero_panel.width = hero_width
            form_panel.width = form_width
            form_panel.expand = False
            form_panel.padding = ft.Padding.symmetric(horizontal=32, vertical=14)
            card_row.controls = [hero_panel, form_panel]
        else:
            effective_w = w if (w and w > 0) else 360
            card_width = min(420, max(280, effective_w - 24))
            login_card.width = card_width
            form_panel.width = None
            form_panel.expand = True
            form_panel.padding = ft.Padding.symmetric(horizontal=16, vertical=16)
            card_row.controls = [form_panel]

        if hasattr(forgot_password_dialog, "open") and forgot_password_dialog.open:
            modal_content_container.width = get_dialog_content_width()

    initial_width = page.width or (page.window.width if hasattr(page, "window") and page.window.width else None)
    update_responsive_layout(initial_width)

    def on_page_resize(e):
        w = page.width or (page.window.width if hasattr(page, "window") and page.window.width else None)
        update_responsive_layout(w)
        page.update()

    page.on_resize = on_page_resize

    view = ft.View(
        bgcolor="#121212" if is_dark else "#F8FAFC",
        route="/",
        controls=[
            ft.Container(
                content=login_card,
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(vertical=8, horizontal=12),
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
        appbar=get_landing_appbar(page, active_page="login"),
    )

    return view