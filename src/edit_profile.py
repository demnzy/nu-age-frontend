import asyncio
import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.auth import reset_request

async def edit_profile_view(page: ft.Page) -> ft.View:
    # ── Theme & Palette Determination ─────────────────────────────────────────
    is_dark = page.theme_mode == ft.ThemeMode.DARK
    
    CARD_BG       = "#181B24" if is_dark else "#FFFFFF"
    CARD_BG_ALT   = "#222736" if is_dark else "#F1F5F9"
    BORDER_CLR    = ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.08, ft.Colors.BLACK)
    TEXT_PRIMARY  = "#F8FAFC" if is_dark else "#0F172A"
    TEXT_MUTED    = "#94A3B8" if is_dark else "#64748B"
    DIVIDER_CLR   = ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.06, ft.Colors.BLACK)
    ICON_BG       = ft.Colors.with_opacity(0.15 if is_dark else 0.08, ft.Colors.PRIMARY)

    # ── Session & Auth Validation ─────────────────────────────────────────────
    user_data = page.session.store.get("current_user") or {}
    token = await page.shared_preferences.get("auth_token")

    if not user_data or not token:
        return _error_view(page)

    first_name = user_data.get("first_name", "")
    last_name  = user_data.get("last_name", "")
    full_name  = f"{first_name} {last_name}".strip() or "Student"
    username   = user_data.get("username", "")
    email      = user_data.get("email", "—")
    gender     = user_data.get("gender", "Rather not say")
    university = user_data.get("university") or ""
    initials   = "".join([n[0] for n in full_name.split()[:2]]).upper() if full_name else "NU"

    # ── Input Styles ──────────────────────────────────────────────────────────
    _input_style = {
        "border_color": BORDER_CLR,
        "focused_border_color": ft.Colors.PRIMARY,
        "border_radius": 12,
        "text_size": 14,
        "cursor_color": ft.Colors.PRIMARY,
        "color": TEXT_PRIMARY,
        "label_style": ft.TextStyle(color=TEXT_MUTED, size=13),
    }

    first_name_input = ft.TextField(
        label="First Name",
        value=first_name,
        prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
        expand=True,
        **_input_style,
    )
    
    last_name_input = ft.TextField(
        label="Last Name",
        value=last_name,
        prefix_icon=ft.Icons.BADGE_OUTLINED,
        expand=True,
        **_input_style,
    )
    
    username_input = ft.TextField(
        label="Username",
        value=username,
        prefix_icon=ft.Icons.ALTERNATE_EMAIL_ROUNDED,
        hint_text="e.g. tobi_learner",
        **_input_style,
    )

    university_display = ft.TextField(
        label="University / Institution (Locked)",
        value=university if university else "Not specified",
        prefix_icon=ft.Icons.ACCOUNT_BALANCE_ROUNDED,
        read_only=True,
        disabled=True,
        hint_text="Institutional affiliation cannot be changed",
        **_input_style,
    )

    gender_options = [
        ft.dropdown.Option("Male"),
        ft.dropdown.Option("Female"),
        ft.dropdown.Option("Rather not say")
    ]
    # Normalize existing value to match one of the options
    selected_gender = "Rather not say"
    if str(gender).lower() == "male":
        selected_gender = "Male"
    elif str(gender).lower() == "female":
        selected_gender = "Female"

    gender_dropdown = ft.Dropdown(
        label="Gender",
        value=selected_gender,
        options=gender_options,
        border_color=BORDER_CLR,
        focused_border_color=ft.Colors.PRIMARY,
        border_radius=12,
        text_size=14,
        color=TEXT_PRIMARY,
        label_style=ft.TextStyle(color=TEXT_MUTED, size=13),
    )

    email_display = ft.TextField(
        label="Email Address (Locked)",
        value=email,
        prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
        read_only=True,
        disabled=True,
        **_input_style,
    )

    # ── Feedback Banner ───────────────────────────────────────────────────────
    feedback = ft.Container(
        visible=False,
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        content=ft.Row(
            spacing=10,
            controls=[
                ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=18),
                ft.Text("", size=12, weight=ft.FontWeight.W_500, expand=True),
            ],
        ),
    )

    def show_feedback(message: str, is_error: bool = True):
        icon = feedback.content.controls[0]
        label = feedback.content.controls[1]
        icon.name = ft.Icons.ERROR_OUTLINE_ROUNDED if is_error else ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
        icon.color = ft.Colors.RED_400 if is_error else ft.Colors.GREEN_400
        label.value = message
        label.color = ft.Colors.RED_300 if is_error else ft.Colors.GREEN_300
        feedback.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.RED_500 if is_error else ft.Colors.GREEN_500)
        feedback.border = ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.RED_500 if is_error else ft.Colors.GREEN_500))
        feedback.visible = True
        page.update()

    def hide_feedback():
        feedback.visible = False

    # ── Save Handler ──────────────────────────────────────────────────────────
    async def handle_save(e):
        hide_feedback()

        fn = first_name_input.value.strip()
        ln = last_name_input.value.strip()
        un = username_input.value.strip()
        gen = gender_dropdown.value or "Rather not say"

        if not fn:
            show_feedback("First name cannot be empty.")
            return
        if not ln:
            show_feedback("Last name cannot be empty.")
            return
        if not un:
            show_feedback("Username cannot be empty.")
            return
        if len(un) < 3:
            show_feedback("Username must be at least 3 characters.")
            return
        if " " in un:
            show_feedback("Username cannot contain spaces.")
            return

        # Diff against current data
        updated_data = {}
        if fn != user_data.get("first_name", ""):
            updated_data["first_name"] = fn
        if ln != user_data.get("last_name", ""):
            updated_data["last_name"] = ln
        if un != user_data.get("username", ""):
            updated_data["username"] = un
        if gen != (user_data.get("gender") or "Rather not say"):
            updated_data["gender"] = gen

        if not updated_data:
            show_feedback("No changes were made.", is_error=False)
            return

        save_btn.disabled = True
        save_btn.content = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.ProgressRing(width=16, height=16, color=ft.Colors.WHITE, stroke_width=2),
                ft.Text("Saving Changes...", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
            ],
        )
        page.update()

        try:
            status, data = await reset_request(token, updated_data)

            if status == 200:
                user_data.update(updated_data)
                if hasattr(page.session.store, "set"):
                    page.session.store.set("current_user", user_data)
                elif isinstance(page.session.store, dict):
                    page.session.store["current_user"] = user_data
                elif hasattr(page.session, "set"):
                    page.session.set("current_user", user_data)
                show_feedback("Profile updated successfully! Redirecting...", is_error=False)
                await asyncio.sleep(0.6)
                page.go("/profile")
            elif status == 409:
                show_feedback("That username is already taken. Please choose another.")
            elif status == 422:
                show_feedback("Invalid input format. Please check your entries.")
            elif status == 401:
                show_feedback("Your session expired. Please sign in again.")
            else:
                err_detail = data.get("detail") if isinstance(data, dict) else None
                show_feedback(err_detail or f"Failed to update profile (code {status}).")

        except Exception as ex:
            _log_error("handle_save", ex)
            show_feedback("Could not connect to server. Please check your internet connection.")

        finally:
            save_btn.disabled = False
            save_btn.content = ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.CHECK_ROUNDED, color=ft.Colors.WHITE, size=18),
                    ft.Text("Save Changes", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                ],
            )
            page.update()

    # ── Action Buttons ────────────────────────────────────────────────────────
    save_btn = ft.FilledButton(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.CHECK_ROUNDED, color=ft.Colors.WHITE, size=18),
                ft.Text("Save Changes", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
            ],
        ),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            bgcolor=ft.Colors.PRIMARY,
            padding=ft.Padding.symmetric(vertical=16, horizontal=24)
        ),
        expand=True,
        on_click=handle_save,
    )

    cancel_btn = ft.OutlinedButton(
        "Cancel",
        icon=ft.Icons.CLOSE_ROUNDED,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding.symmetric(vertical=16, horizontal=20)
        ),
        on_click=lambda _: page.go("/profile"),
    )

    # ── Hero Profile Header (Matching LMS Standard) ───────────────────────────
    hero_gradient = ft.LinearGradient(
        begin=ft.Alignment.TOP_LEFT,
        end=ft.Alignment.BOTTOM_RIGHT,
        colors=[
            ft.Colors.PRIMARY,
            ft.Colors.SECONDARY
        ]
    )

    avatar_monogram = ft.Container(
        width=88, height=88, border_radius=44,
        bgcolor=ft.Colors.WHITE,
        alignment=ft.Alignment.CENTER,
        shadow=ft.BoxShadow(blur_radius=18, color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK), offset=ft.Offset(0, 4)),
        content=ft.Container(
            width=80, height=80, border_radius=40,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                initials, 
                size=28, 
                weight=ft.FontWeight.W_800, 
                color=ft.Colors.PRIMARY
            )
        )
    )

    header = ft.Container(
        bgcolor=ft.Colors.PRIMARY,
        gradient=hero_gradient,
        padding=ft.Padding(top=24, bottom=32, left=20, right=20),
        border_radius=ft.BorderRadius.only(bottom_left=30, bottom_right=30),
        shadow=ft.BoxShadow(blur_radius=25, color=ft.Colors.with_opacity(0.25, ft.Colors.PRIMARY), offset=ft.Offset(0, 8)),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            icon_color=ft.Colors.WHITE,
                            icon_size=20,
                            tooltip="Return to profile",
                            style=ft.ButtonStyle(
                                bgcolor={"": ft.Colors.with_opacity(0.18, ft.Colors.WHITE)},
                                shape=ft.CircleBorder()
                            ),
                            on_click=lambda _: page.go("/profile"),
                        ),
                        ft.Text(
                            "EDIT PROFILE",
                            color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE),
                            size=12,
                            weight=ft.FontWeight.W_800,
                        ),
                        ft.Container(width=40),  # Balance spacer
                    ],
                ),
                avatar_monogram,
                ft.Column([
                    ft.Text(full_name, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER),
                    ft.Text(f"@{username}" if username else email, size=12, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            ],
        ),
    )

    # ── Form Card Helper ──────────────────────────────────────────────────────
    def form_card(title: str, icon, controls: list):
        return ft.Container(
            bgcolor=CARD_BG,
            border_radius=18,
            padding=ft.Padding.all(20),
            border=ft.Border.all(1, BORDER_CLR),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            content=ft.Column(
                spacing=16,
                controls=[
                    ft.Row([
                        ft.Container(
                            width=32, height=32, border_radius=10,
                            bgcolor=ICON_BG,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, color=ft.Colors.PRIMARY, size=16)
                        ),
                        ft.Text(title.upper(), size=11, weight=ft.FontWeight.W_800, color=TEXT_MUTED)
                    ], spacing=10),
                    *controls
                ]
            )
        )

    # Responsive Name Layout
    is_mobile = (page.width or 800) < 600
    name_row = ft.Column([first_name_input, last_name_input], spacing=12) if is_mobile else ft.Row([first_name_input, last_name_input], spacing=12)

    personal_card = form_card(
        "Personal Information",
        ft.Icons.PERSON_ROUNDED,
        [
            name_row,
            gender_dropdown,
        ]
    )

    academic_card = form_card(
        "Academic & Campus Identity",
        ft.Icons.SCHOOL_ROUNDED,
        [
            username_input,
            university_display,
        ]
    )

    account_card = form_card(
        "Account Authentication",
        ft.Icons.SECURITY_ROUNDED,
        [
            email_display,
        ]
    )

    # ── Form Container Assembly ───────────────────────────────────────────────
    form_wrapper = ft.Container(
        alignment=ft.Alignment.TOP_CENTER,
        content=ft.Container(
            width=min(page.width or 800, 720),
            padding=ft.Padding.symmetric(horizontal=16, vertical=20),
            content=ft.Column(
                spacing=18,
                controls=[
                    feedback,
                    personal_card,
                    academic_card,
                    account_card,
                    ft.Row([cancel_btn, save_btn], spacing=12),
                    ft.Container(height=24),
                ],
            ),
        ),
    )

    return ft.View(
        route="/edit-profile",
        padding=0,
        bottom_appbar=get_bottom_appbar(page),
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=0,
                    controls=[header, form_wrapper],
                ),
            )
        ],
    )

# ── Error View ────────────────────────────────────────────────────────────────
def _error_view(page: ft.Page) -> ft.View:
    is_dark = page.theme_mode == ft.ThemeMode.DARK
    CARD_BG = "#181B24" if is_dark else "#FFFFFF"
    TEXT_PRIMARY = "#F8FAFC" if is_dark else "#0F172A"
    TEXT_MUTED = "#94A3B8" if is_dark else "#64748B"

    return ft.View(
        route="/edit-profile",
        padding=0,
        bottom_appbar=get_bottom_appbar(page),
        controls=[
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(32),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.Container(
                            width=64, height=64, border_radius=32,
                            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED_400),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=32, color=ft.Colors.RED_400)
                        ),
                        ft.Text("Session Not Found", size=18, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                        ft.Text("Please sign in again to access and edit your profile settings.", size=12, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                        ft.Container(height=6),
                        ft.FilledButton(
                            "Return to Login",
                            icon=ft.Icons.LOGIN_ROUNDED,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                            on_click=lambda _: page.go("/login")
                        ),
                    ],
                ),
            )
        ],
    )

def _log_error(context: str, ex: Exception):
    print(f"[ERROR] [{context}] {type(ex).__name__}: {ex}")