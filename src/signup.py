import flet as ft
from src.requests.auth import signup_request, get_universities, verify_email_request
from src.components.landing_navbar import get_landing_appbar
from src.requests.organisations import join_org
import re
import uuid


def is_dark_mode(page: ft.Page) -> bool:
    if getattr(page, "theme_mode", None) == ft.ThemeMode.DARK:
        return True
    if getattr(page, "theme_mode", None) == ft.ThemeMode.LIGHT:
        return False
    return getattr(page, "platform_brightness", None) == ft.Brightness.DARK


def Signup_view(page: ft.Page):
    is_processing = False
    is_dark = is_dark_mode(page)

    # ── shared state ──────────────────────────────────────────────
    custom_message = ft.Text("", size=12)
    validation_error = ft.Text(
        "",
        color=ft.Colors.RED_700,
        size=12,
        weight=ft.FontWeight.W_500,
    )

    # ── validation ───────────────────────────────────────────────
    def validate_inputs(e):
        required = [
            first_name.value, last_name.value,
            email.value, username.value,
            password.value, confirm_password.value,
        ]
        all_filled = all(f and f.strip() for f in required)
        passwords_match = password.value == confirm_password.value
        terms_accepted = terms_checkbox.value
        email_ok = bool(re.match(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            email.value or ""
        ))

        def is_valid_uuid(val: str):
            try:
                uuid.UUID(val)
                return True
            except ValueError:
                return False

        org_val = organisation_id.value.strip() if organisation_id.value else ""

        if not all_filled:
            validation_error.value = "All required fields must be completed."
        elif not email_ok:
            validation_error.value = "Please enter a valid email address."
        elif not passwords_match:
            validation_error.value = "Passwords do not match."
        elif not terms_accepted:
            validation_error.value = "You must accept the Terms & Privacy Policy."
        elif org_val and not is_valid_uuid(org_val):
            validation_error.value = "You must input a valid Org ID. Please try again."
        else:
            validation_error.value = ""

        Submit.disabled = validation_error.value != ""
        page.update()

    # ── dialog helpers ────────────────────────────────────────────
    def handle_action_click(e):
        page.pop_dialog()
        page.go("/")

    # ── signup handler ────────────────────────────────────────────
    async def handle_signup(e):
        nonlocal is_processing
        if is_processing:
            return

        is_processing = True
        Submit.disabled = True
        Submit.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        page.update()

        try:
            payload = dict(
                email=email.value,
                username=username.value,
                password=password.value,
                first_name=first_name.value,
                last_name=last_name.value,
                gender=gender_selection.value,
                role=role_selection.value,
                university=University.value if University.value else None,
            )

            org_val = organisation_id.value.strip() if organisation_id.value else ""

            status, data = await signup_request(**payload)

            if status == 200:
                if org_val:
                    user_id = data.get("id")
                    if user_id:
                        org_status = await join_org(org_val, user_id)
                        if isinstance(org_status, dict):
                            has_error = org_status.get("status") is False or "error" in org_status
                            if has_error:
                                err_msg = org_status.get("error", "Invalid Organization ID.")
                                validation_error.value = f"Signup Successful, but failed to join Org: {err_msg}. Proceed to Login"
                                page.update()
                                return
                        else:
                            validation_error.value = "Signup Successful, but a system error prevented joining the Org. Proceed to Login"
                            page.update()
                            Submit.disabled = False
                            return

                page.show_dialog(otp_dialog)

            elif status == 409:
                detail = data.get("detail", "")
                validation_error.value = (
                    "Username already taken."
                    if "Username" in detail
                    else "Email already registered."
                )
                page.update()
            else:
                custom_message.value = f"Error {status}: {data}"
                page.show_dialog(error_dialog)

        finally:
            is_processing = False
            Submit.disabled = False
            Submit.content = ft.Text("Create Account", size=14, weight=ft.FontWeight.W_600)
            page.update()

    # ── dialogs ───────────────────────────────────────────────────
    success_dialog = ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                ft.Text("Account Created!", size=18, weight=ft.FontWeight.W_600),
            ],
            spacing=8,
            wrap=True,
        ),
        content=ft.Text("Your account is ready. Please log in to continue.", size=14),
        actions=[
            ft.TextButton(
                "Go to Login",
                on_click=handle_action_click,
                style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
            )
        ],
    )

    error_dialog = ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_600, size=22),
                ft.Text("Signup Failed", size=18, weight=ft.FontWeight.W_600),
            ],
            spacing=8,
            wrap=True,
        ),
        content=custom_message,
        actions=[
            ft.TextButton(
                "Dismiss",
                on_click=lambda e: page.pop_dialog(),
                style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
            )
        ],
    )

    # ── OTP Verification Dialog & Logic ─────────────────────────────
    otp_error_text = ft.Text("", color=ft.Colors.RED_600, size=12, text_align=ft.TextAlign.CENTER)

    otp_input = ft.TextField(
        width=250,
        height=55,
        text_align=ft.TextAlign.CENTER,
        text_size=20,
        keyboard_type=ft.KeyboardType.NUMBER,
        max_length=6,
        border_radius=10,
        border_color=ft.Colors.GREY_300,
        focused_border_color=ft.Colors.PRIMARY,
        cursor_color=ft.Colors.PRIMARY,
        cursor_height=20,
        counter=" ",
        hint_text="_ _ _ _ _ _",
    )

    async def handle_verification(e):
        otp_btn.disabled = True
        otp_btn.text = "Verifying..."
        otp_error_text.value = ""
        page.update()

        status, data = await verify_email_request(email.value, otp_input.value)

        if status == 200:
            otp_btn.text = "Success!"
            page.pop_dialog()
            page.go("/")
        else:
            otp_error_text.value = data.get("detail", "Verification failed. Please try again.")
            otp_btn.disabled = False
            otp_btn.text = "Verify Account"
            page.update()

    otp_btn = ft.ElevatedButton(
        "Verify Account",
        width=250,
        height=44,
        color=ft.Colors.ON_PRIMARY,
        bgcolor=ft.Colors.PRIMARY,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
        on_click=handle_verification,
    )

    otp_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.MARK_EMAIL_READ_ROUNDED, color=ft.Colors.PRIMARY, size=24),
                ft.Text("Verify your Email", size=18, weight=ft.FontWeight.W_700),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            wrap=True,
        ),
        content=ft.Container(
            width=280,
            content=ft.Column(
                [
                    ft.Text(
                        "We sent a 6-digit code to your email. Enter it below to activate your account.",
                        size=13,
                        color=ft.Colors.ON_SURFACE,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=8),
                    ft.Row([otp_input], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Row([otp_error_text], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(height=8),
                    ft.Row([otp_btn], alignment=ft.MainAxisAlignment.CENTER),
                ],
                tight=True,
                spacing=4,
            ),
        ),
    )

    # ── field style factory ───────────────────────────────────────
    def field(**kwargs) -> ft.TextField:
        cfg = {
            "height": 40,
            "text_size": 13,
            "border_radius": 10,
            "border_color": ft.Colors.OUTLINE,
            "focused_border_color": ft.Colors.PRIMARY,
            "cursor_color": ft.Colors.PRIMARY,
            "label_style": ft.TextStyle(size=11.5, color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600),
            "hint_style": ft.TextStyle(size=11, color=ft.Colors.GREY_500 if is_dark else ft.Colors.GREY_400),
            "content_padding": ft.Padding.symmetric(horizontal=12, vertical=8),
            "on_change": validate_inputs,
        }
        cfg.update(kwargs)
        return ft.TextField(**cfg)

    # ── fields ────────────────────────────────────────────────────
    first_name = field(
        label="First Name",
        hint_text="e.g. Alex",
        prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
        expand=True,
    )
    last_name = field(
        label="Last Name",
        hint_text="e.g. Morgan",
        prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
        expand=True,
    )
    email = field(
        label="Email Address",
        hint_text="name@example.com",
        prefix_icon=ft.Icons.EMAIL_OUTLINED,
        keyboard_type=ft.KeyboardType.EMAIL,
        expand=True,
    )
    username = field(
        label="Username",
        hint_text="username",
        prefix_icon=ft.Icons.ALTERNATE_EMAIL_ROUNDED,
        expand=True,
    )
    password = field(
        label="Password",
        hint_text="••••••••••••",
        prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
        password=True,
        can_reveal_password=True,
        expand=True,
    )
    confirm_password = field(
        label="Confirm Password",
        hint_text="••••••••••••",
        prefix_icon=ft.Icons.LOCK_RESET_ROUNDED,
        password=True,
        can_reveal_password=True,
        expand=True,
    )

    organisation_id = field(
        label="Organisation (optional)",
        label_style=ft.TextStyle(size=10.5, color=ft.Colors.GREY_500),
        hint_text="Enter org UUID (optional)",
        hint_style=ft.TextStyle(size=10, color=ft.Colors.GREY_400),
        prefix_icon=ft.Icons.CORPORATE_FARE_ROUNDED,
        expand=True,
    )

    # University dropdown with restored primary color menu styling
    University = ft.Dropdown(
        enable_search=True,
        enable_filter=True,
        editable=True,
        menu_height=250,
        label="University (optional)",
        label_style=ft.TextStyle(size=10.5, color=ft.Colors.GREY_500),
        hint_text="Select university (optional)",
        hint_style=ft.TextStyle(size=10, color=ft.Colors.GREY_400),
        height=40,
        text_size=13,
        border_radius=10,
        border_color=ft.Colors.OUTLINE,
        focused_border_color=ft.Colors.PRIMARY,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        expand=True,
        options=[],
        disabled=True,
        menu_style=ft.MenuStyle(bgcolor=ft.Colors.PRIMARY),
        leading_icon=ft.Icons.SCHOOL_OUTLINED,
    )

    # Background task to fetch and populate university options
    async def load_universities():
        try:
            universities_data = await get_universities()
            if page.route != "/signup":
                return

            if isinstance(universities_data, dict) and "error" in universities_data:
                err_msg = universities_data.get("error", "Failed to connect.")
                error_snack = ft.SnackBar(
                    content=ft.Text(f"Could not load universities: {err_msg}", color=ft.Colors.ON_PRIMARY),
                    bgcolor=ft.Colors.RED_600,
                    behavior=ft.SnackBarBehavior.FLOATING,
                    duration=ft.Duration(milliseconds=4000),
                )
                if hasattr(page, "open"):
                    page.open(error_snack)
                else:
                    page.overlay.append(error_snack)
                    error_snack.open = True

                University.options = []
                University.hint_text = "Failed to load universities"
                University.disabled = True

            elif isinstance(universities_data, list):
                # Restored primary color dropdown options formatting
                University.options = [
                    ft.dropdown.Option(
                        key=uni.get("name", ""),
                        content=ft.Text(uni.get("name", ""), color=ft.Colors.ON_PRIMARY),
                    )
                    for uni in universities_data if uni.get("name")
                ]
                University.hint_text = "Select university (optional)"
                University.disabled = False

        except Exception as e:
            University.hint_text = "Failed to load universities"
            University.disabled = True

        try:
            if University.page:
                University.update()
            else:
                page.update()
        except RuntimeError:
            pass

    page.run_task(load_universities)

    # ── role radio group ──────────────────────────────────────────
    role_selection = ft.RadioGroup(
        content=ft.Row(
            [
                ft.Radio(value="Student", label="Student"),
                ft.Radio(value="Teacher", label="Instructor"),
            ],
            spacing=8,
            wrap=True,
        ),
        value="Student",
    )

    # ── gender radio group ────────────────────────────────────────
    gender_selection = ft.RadioGroup(
        content=ft.Row(
            [
                ft.Radio(value="Male", label="Male"),
                ft.Radio(value="Female", label="Female"),
            ],
            spacing=8,
            wrap=True,
        ),
        value="Male",
    )

    # Role and Gender selector cards
    role_box = ft.Container(
        content=ft.Column(
            [
                ft.Text("Role", size=10.5, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_700),
                role_selection,
            ],
            spacing=1,
            tight=True,
        ),
        border=ft.Border.all(1, ft.Colors.GREY_300),
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        expand=True,
    )

    gender_box = ft.Container(
        content=ft.Column(
            [
                ft.Text("Gender", size=10.5, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_700),
                gender_selection,
            ],
            spacing=1,
            tight=True,
        ),
        border=ft.Border.all(1, ft.Colors.GREY_300),
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        expand=True,
    )

    # ── terms checkbox ────────────────────────────────────
    terms_checkbox = ft.Checkbox(
        value=False,
        on_change=validate_inputs,
        active_color=ft.Colors.PRIMARY,
    )

    terms_row = ft.Row(
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=0,
        controls=[
            terms_checkbox,
            ft.Container(
                content=ft.Text(
                    size=11.5,
                    color=ft.Colors.GREY_300 if is_dark else ft.Colors.GREY_700,
                    spans=[
                        ft.TextSpan("I have read and accept the "),
                        ft.TextSpan(
                            "Privacy Policy",
                            url="https://privacy.nu-age.name.ng",
                            style=ft.TextStyle(
                                color=ft.Colors.PRIMARY,
                                weight=ft.FontWeight.W_600,
                                decoration=ft.TextDecoration.UNDERLINE,
                            ),
                        ),
                    ],
                ),
                expand=True,
            ),
        ],
    )

    # ── submit button ─────────────────────────────────────────────
    Submit = ft.ElevatedButton(
        content=ft.Text("Create Account", size=13, weight=ft.FontWeight.W_600),
        expand=True,
        color=ft.Colors.ON_PRIMARY,
        bgcolor=ft.Colors.PRIMARY,
        height=40,
        disabled=True,
        on_click=handle_signup,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            elevation=0,
        ),
    )

    # ── Circular App Logo for Hero Panel ─────────────────────────
    circular_logo = ft.Container(
        content=ft.CircleAvatar(
            foreground_image_src="icon.png",
            radius=36,
            bgcolor=ft.Colors.WHITE,
        ),
        shape=ft.BoxShape.CIRCLE,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        alignment=ft.Alignment.CENTER,
        shadow=ft.BoxShadow(
            blur_radius=16,
            spread_radius=0,
            color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
        border=ft.Border.all(2, ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)),
    )

    # ── Left Hero Panel (Desktop) ─────────────────────────────────
    hero_panel = ft.Container(
        width=310,
        bgcolor="#18231E" if is_dark else "#F2FBF4",
        border_radius=ft.BorderRadius.only(top_left=20, bottom_left=20),
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
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
                ft.Container(height=4),
                ft.Image(
                    src="signup_hero.png",
                    width=210,
                    height=145,
                    fit=ft.BoxFit.CONTAIN,
                ),
                ft.Container(height=4),
                ft.Text(
                    spans=[
                        ft.TextSpan("Join the "),
                        ft.TextSpan(
                            "Nu",
                            style=ft.TextStyle(
                                color=ft.Colors.SECONDARY,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ),
                        ft.TextSpan(" Generation"),
                    ],
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.ON_SURFACE,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Start learning today with interactive courses and 100% offline access.",
                    size=11,
                    color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=6),
                # Value props
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                                ft.Text("Free access to interactive courses", size=11, color=ft.Colors.GREY_300 if is_dark else ft.Colors.GREY_700),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                                ft.Text("100% offline study with local storage", size=11, color=ft.Colors.GREY_300 if is_dark else ft.Colors.GREY_700),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                                ft.Text("Personalized quizzes and certificates", size=11, color=ft.Colors.GREY_300 if is_dark else ft.Colors.GREY_700),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                    ],
                    spacing=6,
                    tight=True,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=3,
        ),
    )

    # ── Right Form Content Controls ───────────────────────────────
    header_branding = ft.Row(
        [
            ft.Image(src="icon.png", width=24, height=24, fit=ft.BoxFit.CONTAIN),
            ft.Text("Nu Age", size=18, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
        ],
        spacing=7,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    header_text = ft.Column(
        [
            ft.Text(
                "Create Account",
                size=22,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE,
            ),
            ft.Text(
                "Join Nu Age and start learning today.",
                size=12,
                color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_500,
            ),
        ],
        spacing=1,
        tight=True,
    )

    signin_link_row = ft.Row(
        controls=[
            ft.Text(
                "Already have an account?",
                size=12,
                color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600,
            ),
            ft.TextButton(
                "Sign In",
                on_click=lambda _: page.go("/"),
                style=ft.ButtonStyle(
                    color=ft.Colors.PRIMARY,
                    padding=ft.Padding.only(left=4),
                ),
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=0,
        wrap=True,
    )

    footer_text = ft.Text(
        "© 2026 Nu Age Learning · All rights reserved",
        size=10,
        color=ft.Colors.GREY_500 if is_dark else ft.Colors.GREY_400,
        text_align=ft.TextAlign.CENTER,
    )

    # Generates responsive field list: 2-column paired rows on desktop, full-width single-column rows on mobile
    def get_form_controls(is_desktop: bool):
        if is_desktop:
            field_rows = [
                ft.Row([first_name, last_name], spacing=12),
                ft.Row([email, username], spacing=12),
                ft.Row([password, confirm_password], spacing=12),
                ft.Row([role_box, gender_box], spacing=12),
                ft.Row([organisation_id, University], spacing=12),
            ]
        else:
            # Clean single-column layout on mobile: full width per field, zero bleeding off
            field_rows = [
                ft.Row([first_name]),
                ft.Row([last_name]),
                ft.Row([email]),
                ft.Row([username]),
                ft.Row([password]),
                ft.Row([confirm_password]),
                ft.Row([role_box]),
                ft.Row([gender_box]),
                ft.Row([organisation_id]),
                ft.Row([University]),
            ]

        return [
            header_branding,
            header_text,
            *field_rows,
            validation_error,
            terms_row,
            ft.Row(controls=[Submit]),
            signin_link_row,
            footer_text,
        ]

    form_content = ft.Column(
        controls=[],
        spacing=5,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    form_panel = ft.Container(
        width=690,
        padding=ft.Padding.symmetric(horizontal=32, vertical=14),
        alignment=ft.Alignment.CENTER,
        content=form_content,
    )

    # ── Main Signup Card ──────────────────────────────────────────
    card_row = ft.Row(
        controls=[hero_panel, form_panel],
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
    )

    signup_card = ft.Container(
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
            return w >= 920
        if getattr(page, "platform", None) in [ft.PagePlatform.ANDROID, ft.PagePlatform.IOS]:
            return False
        ua = (getattr(page, "client_user_agent", None) or "").lower()
        if any(m in ua for m in ["android", "iphone", "ipad", "mobile"]):
            return False
        if hasattr(page, "window") and getattr(page.window, "width", None) and page.window.width > 0:
            return page.window.width >= 920
        return False

    def update_responsive_layout(w: int | None):
        is_dark_curr = is_dark_mode(page)
        hero_panel.bgcolor = "#18231E" if is_dark_curr else "#F2FBF4"
        signup_card.border = ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark_curr else ft.Colors.with_opacity(0.06, ft.Colors.BLACK))
        if 'view' in locals():
            view.bgcolor = "#121212" if is_dark_curr else "#F8FAFC"

        is_desktop = get_is_desktop(w)
        hero_panel.visible = is_desktop
        form_content.controls = get_form_controls(is_desktop)

        if is_desktop:
            effective_w = w if (w and w > 0) else 960
            card_width = min(1000, max(880, effective_w - 40))
            hero_width = 310
            form_width = card_width - hero_width
            signup_card.width = card_width
            hero_panel.width = hero_width
            form_panel.width = form_width
            form_panel.expand = False
            form_panel.padding = ft.Padding.symmetric(horizontal=32, vertical=14)
            card_row.controls = [hero_panel, form_panel]
        else:
            effective_w = w if (w and w > 0) else 360
            card_width = min(480, max(280, effective_w - 24))
            signup_card.width = card_width
            form_panel.width = None
            form_panel.expand = True
            form_panel.padding = ft.Padding.symmetric(horizontal=14, vertical=16)
            card_row.controls = [form_panel]

    initial_width = page.width or (page.window.width if hasattr(page, "window") and page.window.width else None)
    update_responsive_layout(initial_width)

    def on_page_resize(e):
        w = page.width or (page.window.width if hasattr(page, "window") and page.window.width else None)
        update_responsive_layout(w)
        page.update()

    page.on_resize = on_page_resize

    view = ft.View(
        route="/signup",
        bgcolor="#121212" if is_dark else "#F8FAFC",
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                content=signup_card,
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(vertical=8, horizontal=12),
            )
        ],
        appbar=get_landing_appbar(page, active_page="signup"),
    )
    return view