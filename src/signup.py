import asyncio
import flet as ft
from src.requests.auth import signup_request, get_universities, verify_email_request, resend_verification_otp_request
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

    # ── State Machine: "persona" | "form" | "otp" | "confirmation" ──
    stage = "persona"
    selected_persona = "student"  # "student" | "teacher" | "admin"
    selected_focus_topics = set(["Software & Web"])

    # ── Shared Messages & Validation ──────────────────────────────
    custom_message = ft.Text("", size=12)
    validation_error = ft.Text(
        "",
        color=ft.Colors.RED_700,
        size=12,
        weight=ft.FontWeight.W_500,
    )

    # ── Focus Topics by Persona ───────────────────────────────────
    PERSONA_TOPICS = {
        "student": [
            "Software & Web",
            "Data & AI",
            "Mobile Apps",
            "Cloud & DevOps",
            "Business & Finance",
            "STEM & Math",
        ],
        "teacher": [
            "Computer Science",
            "Engineering",
            "Higher Education",
            "Mathematics",
            "Business Studies",
            "Vocational Training",
        ],
        "admin": [
            "University / College",
            "Polytechnic",
            "Corporate Academy",
            "Tech Bootcamp",
            "Government Training",
        ],
    }

    # ── Field Style Factory ───────────────────────────────────────
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
            "on_change": lambda e: validate_inputs(e),
        }
        cfg.update(kwargs)
        return ft.TextField(**cfg)

    # ── Form Input Fields ─────────────────────────────────────────
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

    # Role-Specific Contextual Fields
    organisation_id = field(
        label="Organisation UUID (optional)",
        label_style=ft.TextStyle(size=10.5, color=ft.Colors.GREY_500),
        hint_text="Enter org UUID if invited",
        hint_style=ft.TextStyle(size=10, color=ft.Colors.GREY_400),
        prefix_icon=ft.Icons.CORPORATE_FARE_ROUNDED,
        expand=True,
    )

    specialization_field = field(
        label="Faculty or Department (optional)",
        label_style=ft.TextStyle(size=10.5, color=ft.Colors.GREY_500),
        hint_text="e.g. Computer Science & Engineering",
        hint_style=ft.TextStyle(size=10, color=ft.Colors.GREY_400),
        prefix_icon=ft.Icons.LOCAL_LIBRARY_ROUNDED,
        expand=True,
    )

    # University dropdown with search
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

    async def load_universities():
        try:
            universities_data = await get_universities()
            if page.route != "/signup":
                return

            if isinstance(universities_data, dict) and "error" in universities_data:
                University.options = []
                University.hint_text = "Failed to load universities"
                University.disabled = True
            elif isinstance(universities_data, list):
                University.options = [
                    ft.dropdown.Option(
                        key=uni.get("name", ""),
                        content=ft.Text(uni.get("name", ""), color=ft.Colors.ON_PRIMARY),
                    )
                    for uni in universities_data if uni.get("name")
                ]
                University.hint_text = "Select university (optional)"
                University.disabled = False
        except Exception:
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

    # ── Terms & Conditions Checkbox ───────────────────────────────
    terms_checkbox = ft.Checkbox(
        value=False,
        on_change=lambda e: validate_inputs(e),
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

    # ── Input Validation ──────────────────────────────────────────
    def validate_inputs(e=None):
        required = [
            first_name.value, last_name.value,
            email.value, username.value,
            password.value, confirm_password.value,
        ]
        all_filled = all(f and f.strip() for f in required)
        passwords_match = (password.value or "") == (confirm_password.value or "")
        terms_accepted = bool(terms_checkbox.value)
        email_ok = bool(re.match(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            (email.value or "").strip()
        ))

        org_val = (organisation_id.value or "").strip()

        def is_valid_uuid(val: str):
            try:
                uuid.UUID(val)
                return True
            except ValueError:
                return False

        if not all_filled:
            validation_error.value = "All required fields must be completed."
        elif not email_ok:
            validation_error.value = "Please enter a valid email address."
        elif len(password.value or "") < 6:
            validation_error.value = "Password must be at least 6 characters."
        elif not passwords_match:
            validation_error.value = "Passwords do not match."
        elif not terms_accepted:
            validation_error.value = "You must accept the Terms & Privacy Policy."
        elif org_val and not is_valid_uuid(org_val):
            validation_error.value = "Invalid Organisation ID. Must be a valid UUID."
        else:
            validation_error.value = ""

        Submit.disabled = validation_error.value != ""
        page.update()

    # ── Submit Button ─────────────────────────────────────────────
    Submit = ft.ElevatedButton(
        content=ft.Text("Create Account", size=13, weight=ft.FontWeight.W_600),
        expand=True,
        color=ft.Colors.ON_PRIMARY,
        bgcolor=ft.Colors.PRIMARY,
        height=40,
        disabled=True,
        on_click=lambda e: page.run_task(handle_signup, e),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            elevation=0,
        ),
    )

    # ── Signup Request Handler ────────────────────────────────────
    async def handle_signup(e):
        nonlocal is_processing, stage
        if is_processing:
            return

        is_processing = True
        Submit.disabled = True
        Submit.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        page.update()

        try:
            # Backend constraint: role="Student" is accepted for public registration.
            # Instructor/Admin accounts are assigned or joined via invite codes.
            payload = dict(
                email=(email.value or "").strip(),
                username=(username.value or "").strip(),
                password=password.value or "",
                first_name=(first_name.value or "").strip(),
                last_name=(last_name.value or "").strip(),
                gender="Rather not say",
                role="Student",
                university=University.value if University.value else None,
            )

            org_val = (organisation_id.value or "").strip()

            status, data = await signup_request(**payload)

            if status == 200:
                if org_val:
                    user_id = data.get("id")
                    if user_id:
                        try:
                            await join_org(org_val, user_id)
                        except Exception:
                            pass

                stage = "otp"
                refresh_view()
                page.run_task(start_otp_countdown)

            elif status == 409:
                detail = data.get("detail", "") if isinstance(data, dict) else ""
                validation_error.value = (
                    "Username already taken."
                    if "username" in str(detail).lower()
                    else "Email is already registered. Please sign in instead."
                )
                page.update()
            else:
                detail_msg = data.get("detail", "Signup failed. Please try again.") if isinstance(data, dict) else str(data)
                validation_error.value = f"Error: {detail_msg}"
                page.update()

        finally:
            is_processing = False
            Submit.disabled = False
            Submit.content = ft.Text("Create Account", size=13, weight=ft.FontWeight.W_600)
            page.update()

    # ── Stage 3: OTP Verification Controls ────────────────────────
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
        nonlocal stage
        otp_btn.disabled = True
        otp_btn.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        otp_error_text.value = ""
        page.update()

        target_email = (email.value or "").strip()
        target_otp = (otp_input.value or "").strip()

        status, data = await verify_email_request(target_email, target_otp)

        if status == 200:
            stage = "confirmation"
            refresh_view()
        else:
            otp_error_text.value = data.get("detail", "Verification failed. Please check the code and try again.")
            otp_btn.disabled = False
            otp_btn.content = ft.Text("Verify & Activate Account", size=13, weight=ft.FontWeight.W_600)
            page.update()

    otp_btn = ft.ElevatedButton(
        content=ft.Text("Verify & Activate Account", size=13, weight=ft.FontWeight.W_600),
        width=260,
        height=42,
        color=ft.Colors.ON_PRIMARY,
        bgcolor=ft.Colors.PRIMARY,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
        on_click=lambda e: page.run_task(handle_verification, e),
    )

    resend_status_text = ft.Text("", size=11, color=ft.Colors.PRIMARY, text_align=ft.TextAlign.CENTER)

    async def handle_resend_otp(e):
        resend_btn.disabled = True
        resend_status_text.value = "Sending new code..."
        resend_status_text.color = ft.Colors.PRIMARY
        page.update()

        target = (email.value or "").strip()
        status, data = await resend_verification_otp_request(target)
        if status == 200:
            resend_status_text.value = "New code sent! Check inbox & spam folder."
            resend_status_text.color = ft.Colors.GREEN_600
        else:
            resend_status_text.value = data.get("detail", "Failed to resend code.")
            resend_status_text.color = ft.Colors.RED_600
        page.update()

        await start_otp_countdown()

    async def start_otp_countdown():
        resend_btn.disabled = True
        for remaining in range(30, 0, -1):
            if stage != "otp":
                return
            resend_btn.text = f"Resend code ({remaining}s)"
            page.update()
            await asyncio.sleep(1)

        if stage == "otp":
            resend_btn.disabled = False
            resend_btn.text = "Resend code"
            page.update()

    resend_btn = ft.TextButton(
        "Didn't receive email? Resend code",
        on_click=lambda e: page.run_task(handle_resend_otp, e),
        style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
    )

    # ── Stage 4: Post-Confirmation Proceed to Login Handler ────────
    async def handle_proceed_to_login(e):
        identifier = (username.value or email.value or "").strip()
        if identifier:
            setattr(page, "_prefill_login_identifier", identifier)
            if hasattr(page, "session") and hasattr(page.session, "store"):
                try:
                    page.session.store.set("prefill_login_identifier", identifier)
                except Exception:
                    pass
            try:
                await page.shared_preferences.set("prefill_login_identifier", identifier)
            except Exception:
                pass
        page.go("/")

    # ── Stage Builders ────────────────────────────────────────────

    def build_persona_stage():
        """Stage 1: Pre-Signup Persona Assessment & Focus Selection."""
        def make_persona_card(key: str, icon_name: str, title: str, subtitle: str, badge_text: str | None = None):
            is_selected = selected_persona == key
            card_border = ft.Border.all(
                2 if is_selected else 1,
                ft.Colors.PRIMARY if is_selected else (ft.Colors.OUTLINE if is_dark else ft.Colors.GREY_300)
            )
            card_bg = (
                ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY)
                if is_selected
                else (ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE) if is_dark else ft.Colors.WHITE)
            )

            def on_card_click(e):
                nonlocal selected_persona
                selected_persona = key
                selected_focus_topics.clear()
                topics = PERSONA_TOPICS.get(key, [])
                if topics:
                    selected_focus_topics.add(topics[0])
                refresh_view()

            radio_icon = ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if is_selected else ft.Icons.RADIO_BUTTON_UNCHECKED,
                color=ft.Colors.PRIMARY if is_selected else ft.Colors.GREY_400,
                size=20,
            )

            badge_widget = None
            if badge_text:
                badge_widget = ft.Container(
                    content=ft.Text(badge_text, size=9.5, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                    bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
                    border_radius=12,
                )

            return ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(icon_name, color=ft.Colors.PRIMARY if is_selected else ft.Colors.ON_SURFACE, size=24),
                            width=44,
                            height=44,
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(title, size=13.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                        badge_widget or ft.Container(),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Text(
                                    subtitle,
                                    size=11,
                                    color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600,
                                ),
                            ],
                            spacing=2,
                            tight=True,
                            expand=True,
                        ),
                        radio_icon,
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                border=card_border,
                border_radius=12,
                bgcolor=card_bg,
                on_click=on_card_click,
                animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            )

        student_card = make_persona_card(
            "student",
            ft.Icons.SCHOOL_ROUNDED,
            "Learner & Student",
            "Learn in-demand skills, test code in live sandboxes, and study 24/7 with Nu-AI Tutor.",
            "POPULAR",
        )
        teacher_card = make_persona_card(
            "teacher",
            ft.Icons.PSYCHOLOGY_ALT_ROUNDED,
            "Instructor & Educator",
            "Build visual courses, host proctored cohort exams, auto-grade quizzes, and mentor students.",
        )
        admin_card = make_persona_card(
            "admin",
            ft.Icons.CORPORATE_FARE_ROUNDED,
            "Institution Administrator",
            "Manage campus faculties, invite student rosters, monitor telemetry, and mint credentials.",
        )

        # Focus topic selection chips
        available_topics = PERSONA_TOPICS.get(selected_persona, [])
        topic_chips = []
        for t in available_topics:
            is_active = t in selected_focus_topics

            def toggle_topic(e, topic=t):
                if topic in selected_focus_topics:
                    if len(selected_focus_topics) > 1:
                        selected_focus_topics.remove(topic)
                else:
                    selected_focus_topics.add(topic)
                refresh_view()

            chip = ft.Container(
                content=ft.Text(
                    t,
                    size=11,
                    weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400,
                    color=ft.Colors.PRIMARY if is_active else (ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_700),
                ),
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=16,
                border=ft.Border.all(
                    1,
                    ft.Colors.PRIMARY if is_active else (ft.Colors.OUTLINE if is_dark else ft.Colors.GREY_300)
                ),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_active else ft.Colors.TRANSPARENT,
                on_click=toggle_topic,
            )
            topic_chips.append(chip)

        def proceed_to_form(e):
            nonlocal stage
            stage = "form"
            refresh_view()

        return [
            ft.Row(
                [
                    ft.Image(src="icon.png", width=24, height=24, fit=ft.BoxFit.CONTAIN),
                    ft.Text("Nu Age", size=18, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                ],
                spacing=7,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Column(
                [
                    ft.Text("Choose Your Nu-Age Experience", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text("Select your primary role to tailor your workspace and curriculum.", size=12, color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600),
                ],
                spacing=2,
                tight=True,
            ),
            ft.Container(height=4),
            student_card,
            teacher_card,
            admin_card,
            ft.Container(height=6),
            ft.Text(
                "Primary Interests / Focus Areas (tap to select):",
                size=11,
                weight=ft.FontWeight.W_600,
                color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_700,
            ),
            ft.Row(topic_chips, wrap=True, spacing=6, run_spacing=6),
            ft.Container(height=10),
            ft.ElevatedButton(
                content=ft.Row(
                    [
                        ft.Text("Continue to Registration", size=13, weight=ft.FontWeight.W_600),
                        ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=6,
                ),
                color=ft.Colors.ON_PRIMARY,
                bgcolor=ft.Colors.PRIMARY,
                height=42,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                on_click=proceed_to_form,
            ),
            ft.Row(
                [
                    ft.Text("Already have an account?", size=12, color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600),
                    ft.TextButton(
                        "Sign In",
                        on_click=lambda _: page.go("/"),
                        style=ft.ButtonStyle(color=ft.Colors.PRIMARY, padding=ft.Padding.only(left=4)),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=0,
            ),
        ]

    def build_form_stage(is_desktop: bool):
        """Stage 2: Minimal Branching Registration Form."""
        role_label = "Student" if selected_persona == "student" else ("Instructor" if selected_persona == "teacher" else "Administrator")
        role_icon = ft.Icons.SCHOOL_ROUNDED if selected_persona == "student" else (ft.Icons.PSYCHOLOGY_ALT_ROUNDED if selected_persona == "teacher" else ft.Icons.CORPORATE_FARE_ROUNDED)

        def switch_persona(e):
            nonlocal stage
            stage = "persona"
            refresh_view()

        persona_badge = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(role_icon, size=13, color=ft.Colors.PRIMARY),
                    ft.Text(f"{role_label} Mode", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                    ft.Container(width=4),
                    ft.Text("Change", size=10.5, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500),
                ],
                tight=True,
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=16,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)),
            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
            on_click=switch_persona,
        )

        role_info_banner = None
        if selected_persona == "teacher":
            role_info_banner = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=16, color=ft.Colors.AMBER_700),
                        ft.Text(
                            "Instructor accounts are provisioned via Institution invites. You can register your account now and link your invite code below.",
                            size=11,
                            color=ft.Colors.AMBER_900 if not is_dark else ft.Colors.AMBER_200,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_700),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.AMBER_700)),
            )
        elif selected_persona == "admin":
            role_info_banner = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.APARTMENT_ROUNDED, size=16, color=ft.Colors.BLUE_700),
                        ft.Text(
                            "Institution Admins manage departments and invite student rosters. Enter your organization invite code if available.",
                            size=11,
                            color=ft.Colors.BLUE_900 if not is_dark else ft.Colors.BLUE_200,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLUE_700),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.BLUE_700)),
            )

        if is_desktop:
            field_rows = [
                ft.Row([first_name, last_name], spacing=12),
                ft.Row([email, username], spacing=12),
                ft.Row([password, confirm_password], spacing=12),
            ]
            if selected_persona == "student":
                field_rows.append(ft.Row([University], spacing=12))
            elif selected_persona == "teacher":
                field_rows.append(ft.Row([specialization_field, organisation_id], spacing=12))
            else:
                field_rows.append(ft.Row([organisation_id], spacing=12))
        else:
            field_rows = [
                ft.Row([first_name]),
                ft.Row([last_name]),
                ft.Row([email]),
                ft.Row([username]),
                ft.Row([password]),
                ft.Row([confirm_password]),
            ]
            if selected_persona == "student":
                field_rows.append(ft.Row([University]))
            elif selected_persona == "teacher":
                field_rows.append(ft.Row([specialization_field]))
                field_rows.append(ft.Row([organisation_id]))
            else:
                field_rows.append(ft.Row([organisation_id]))

        controls = [
            ft.Row(
                [
                    ft.Row(
                        [
                            ft.Image(src="icon.png", width=22, height=22, fit=ft.BoxFit.CONTAIN),
                            ft.Text("Nu Age", size=17, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    persona_badge,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Column(
                [
                    ft.Text("Create Your Account", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text("Enter your essential details to activate your workspace.", size=12, color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_500),
                ],
                spacing=1,
                tight=True,
            ),
        ]

        if role_info_banner:
            controls.append(role_info_banner)

        controls.extend(field_rows)
        controls.append(validation_error)
        controls.append(terms_row)
        controls.append(ft.Row(controls=[Submit]))
        controls.append(
            ft.Row(
                [
                    ft.Text("Already have an account?", size=12, color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600),
                    ft.TextButton(
                        "Sign In",
                        on_click=lambda _: page.go("/"),
                        style=ft.ButtonStyle(color=ft.Colors.PRIMARY, padding=ft.Padding.only(left=4)),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=0,
            )
        )
        return controls

    def build_otp_stage():
        """Stage 3: 6-Digit Email OTP Verification."""
        target_email = (email.value or "").strip()

        def go_back_to_form(e):
            nonlocal stage
            stage = "form"
            refresh_view()

        return [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.MARK_EMAIL_READ_ROUNDED, color=ft.Colors.PRIMARY, size=36),
                            width=64,
                            height=64,
                            border_radius=32,
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Text("Verify Your Email", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            "We sent a 6-digit confirmation code to:",
                            size=12.5,
                            color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(
                            content=ft.Text(target_email, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=5),
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                            border_radius=8,
                        ),
                        ft.Container(height=6),
                        ft.Row([otp_input], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([otp_error_text], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Container(height=4),
                        ft.Row([otp_btn], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Container(height=4),
                        ft.Row([resend_status_text], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([resend_btn], alignment=ft.MainAxisAlignment.CENTER),
                        ft.TextButton(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=14, color=ft.Colors.GREY_500),
                                    ft.Text("Incorrect email? Edit details", size=12, color=ft.Colors.GREY_500),
                                ],
                                tight=True,
                                spacing=4,
                            ),
                            on_click=go_back_to_form,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                    tight=True,
                ),
                padding=ft.Padding.symmetric(vertical=10),
            )
        ]

    def build_confirmation_stage():
        """Stage 4: Post-OTP Account Verified & Welcome Screen."""
        first_n = (first_name.value or "").strip()
        user_n = (username.value or "").strip()
        user_em = (email.value or "").strip()

        role_label = "Student / Learner" if selected_persona == "student" else ("Instructor / Educator" if selected_persona == "teacher" else "Institution Administrator")
        role_icon = ft.Icons.SCHOOL_ROUNDED if selected_persona == "student" else (ft.Icons.PSYCHOLOGY_ALT_ROUNDED if selected_persona == "teacher" else ft.Icons.CORPORATE_FARE_ROUNDED)

        # Persona-tailored checklist highlights
        if selected_persona == "student":
            perks = [
                ("Nu-AI Socratic Tutor", "Ready 24/7 to guide you through lessons & exercises."),
                ("Offline Study Mode", "Download full courses and code sandboxes locally."),
                ("Discussion & Squads", "Connect with peers, share notes, and collaborate."),
            ]
        elif selected_persona == "teacher":
            perks = [
                ("Visual Course Studio", "Design interactive lessons, quizzes, and code labs."),
                ("Proctored Cohort Exams", "Schedule timed exams with auto-grading & telemetry."),
                ("Student Analytics", "Track drop-off bottlenecks and assignment mastery."),
            ]
        else:
            perks = [
                ("Campus Organization", "Configure faculties, departments, and roles."),
                ("Roster Onboarding", "Invite cohorts in bulk with cryptographic join links."),
                ("Learning Telemetry", "Monitor campus-wide engagement and issue credentials."),
            ]

        perk_rows = []
        for perk_title, perk_desc in perks:
            perk_rows.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600, size=18),
                        ft.Column(
                            [
                                ft.Text(perk_title, size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                ft.Text(perk_desc, size=11, color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600),
                            ],
                            spacing=1,
                            tight=True,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            )

        proceed_btn = ft.ElevatedButton(
            content=ft.Row(
                [
                    ft.Text("Proceed to Sign In", size=13, weight=ft.FontWeight.W_600),
                    ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=6,
            ),
            width=280,
            height=44,
            color=ft.Colors.ON_PRIMARY,
            bgcolor=ft.Colors.PRIMARY,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
            on_click=lambda e: page.run_task(handle_proceed_to_login, e),
        )

        return [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600, size=52),
                            width=76,
                            height=76,
                            border_radius=38,
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Text("Account Verified & Ready!", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            f"Welcome to Nu-Age, {first_n}!",
                            size=13,
                            color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=4),
                        # Summary Card
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.CircleAvatar(
                                        content=ft.Text(
                                            (first_n[:1] or user_n[:1] or "N").upper(),
                                            weight=ft.FontWeight.BOLD,
                                            size=15,
                                            color=ft.Colors.ON_PRIMARY,
                                        ),
                                        radius=20,
                                        bgcolor=ft.Colors.PRIMARY,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(f"@{user_n}", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                            ft.Text(user_em, size=11, color=ft.Colors.GREY_500),
                                        ],
                                        spacing=2,
                                        tight=True,
                                        expand=True,
                                    ),
                                    ft.Container(
                                        content=ft.Row(
                                            [
                                                ft.Icon(role_icon, size=12, color=ft.Colors.PRIMARY),
                                                ft.Text(role_label.split(" ")[0], size=10.5, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                                            ],
                                            tight=True,
                                            spacing=4,
                                        ),
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                        border_radius=12,
                                    ),
                                ],
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                            width=320,
                        ),
                        ft.Container(height=8),
                        # Tailored Perks
                        ft.Container(
                            content=ft.Column(perk_rows, spacing=8, tight=True),
                            width=320,
                            padding=ft.Padding.symmetric(horizontal=4),
                        ),
                        ft.Container(height=10),
                        ft.Row([proceed_btn], alignment=ft.MainAxisAlignment.CENTER),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                    tight=True,
                ),
                padding=ft.Padding.symmetric(vertical=8),
            )
        ]

    # ── Left Hero Panel (Desktop) ─────────────────────────────────
    hero_headline = ft.Text(
        spans=[
            ft.TextSpan("Join the "),
            ft.TextSpan("Nu", style=ft.TextStyle(color=ft.Colors.SECONDARY, weight=ft.FontWeight.BOLD)),
            ft.TextSpan(" Generation"),
        ],
        size=18,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.ON_SURFACE,
        text_align=ft.TextAlign.CENTER,
    )

    hero_subtitle = ft.Text(
        "Start learning today with interactive courses and 100% offline access.",
        size=11,
        color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600,
        text_align=ft.TextAlign.CENTER,
    )

    hero_bullets_col = ft.Column(
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
    )

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
                hero_headline,
                hero_subtitle,
                ft.Container(height=6),
                hero_bullets_col,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=3,
        ),
    )

    # ── Form Content Container ────────────────────────────────────
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
        border=ft.Border.all(
            1,
            ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.06, ft.Colors.BLACK)
        ),
        content=card_row,
    )

    # ── Layout & Responsive Sync ──────────────────────────────────
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

    def refresh_view():
        w = page.width or (page.window.width if hasattr(page, "window") and page.window.width else None)
        update_responsive_layout(w)
        page.update()

    def update_responsive_layout(w: int | None):
        is_dark_curr = is_dark_mode(page)
        hero_panel.bgcolor = "#18231E" if is_dark_curr else "#F2FBF4"
        signup_card.border = ft.Border.all(
            1,
            ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark_curr else ft.Colors.with_opacity(0.06, ft.Colors.BLACK)
        )
        if 'view' in locals():
            view.bgcolor = "#121212" if is_dark_curr else "#F8FAFC"

        is_desktop = get_is_desktop(w)
        hero_panel.visible = is_desktop

        # Dynamically switch controls by stage
        if stage == "persona":
            form_content.controls = build_persona_stage()
        elif stage == "form":
            form_content.controls = build_form_stage(is_desktop)
        elif stage == "otp":
            form_content.controls = build_otp_stage()
        elif stage == "confirmation":
            form_content.controls = build_confirmation_stage()

        # Update hero panel content based on stage
        if stage == "persona":
            hero_subtitle.value = "Personalize your learning journey or institutional workspace from day one."
        elif stage == "form":
            hero_subtitle.value = "Start learning today with interactive courses and 100% offline access."
        elif stage == "otp":
            hero_subtitle.value = "Secure cryptographic 2-step verification ensures your learning credentials remain safe."
        elif stage == "confirmation":
            hero_subtitle.value = "Your Nu-Age account and 24/7 AI Study Tutor are primed and ready."

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

    def _set_stage_for_test(new_stage: str):
        nonlocal stage
        stage = new_stage
        refresh_view()

    view._test_set_stage = _set_stage_for_test
    return view