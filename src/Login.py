import flet as ft
from src.requests.auth import login_request
from src.components.landing_navbar import get_landing_appbar
from src.utils.db_manager import log_daily_activity
import asyncio


def login_view(page: ft.Page):
    is_processing = False
    page.theme_mode = ft.ThemeMode.LIGHT

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
    def handle_action_click(e):
        page.pop_dialog()
        page.go("/dashboard")

    success_dialog = ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                        color=ft.Colors.PRIMARY, size=22),
                ft.Text("Login Successful!", size=18,
                        weight=ft.FontWeight.W_600),
            ],
            spacing=8,
        ),
        content=ft.Text("Welcome back to Nu Age.", size=13),
        actions=[
            ft.TextButton(
                "Go to Dashboard",
                on_click=handle_action_click,
                style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
            )
        ],
    )

    error_dialog = ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED,
                        color=ft.Colors.RED_600, size=22),
                ft.Text("Login Failed", size=18, weight=ft.FontWeight.W_600),
            ],
            spacing=8,
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

    timeout_dialog = ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.WIFI_OFF_ROUNDED,
                        color=ft.Colors.ORANGE_700, size=22),
                ft.Text("Connection Problem", size=18,
                        weight=ft.FontWeight.W_600),
            ],
            spacing=8,
        ),
        content=ft.Text(
            "Unable to reach the server. Please check your internet "
            "connection and try again.",
            size=13,
        ),
        actions=[
            ft.TextButton(
                "Dismiss",
                on_click=lambda e: page.pop_dialog(),
                style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
            )
        ],
    )

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
        Submit.text     = "Signing in…"
        clear_error()
        page.update()

        try:
            status, data = await asyncio.wait_for(
                login_request(email.value, password.value),
                timeout=15,
            )

            if status == 200:
                token = data.get("access_token")
                await page.shared_preferences.set("auth_token", token)
                log_daily_activity()
                page.show_dialog(success_dialog)

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

            elif status is not None:
                custom_message.value = (
                    f"Unexpected error, {data["detail"]} "
                )
                page.show_dialog(error_dialog)

        except asyncio.TimeoutError:
            page.show_dialog(timeout_dialog)

        except Exception as ex:
            custom_message.value = (
                "Something went wrong while connecting to the server. "
                f"Detail: {type(ex).__name__}."
            )
            page.show_dialog(error_dialog)

        finally:
            is_processing   = False
            Submit.disabled = False
            Submit.text     = "Sign In"
            page.update()

    # ── field factory ─────────────────────────────────────────────
    def field(**kwargs) -> ft.TextField:
        return ft.TextField(
            height=46,
            text_size=13,
            border_radius=8,
            border_color=ft.Colors.GREY_300,
            focused_border_color=ft.Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            on_change=validate_inputs,
            **kwargs,
        )

    # ── fields ────────────────────────────────────────────────────
    email = field(
        label="Email or Username",
        prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
        keyboard_type=ft.KeyboardType.EMAIL,
        expand=True,
    )
    password = field(
        label="Password",
        prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
        password=True,
        can_reveal_password=True,
        expand=True,
    )

    # ── submit button ─────────────────────────────────────────────
    Submit = ft.ElevatedButton(
        "Sign In",
        expand=True,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.PRIMARY,
        height=46,
        disabled=True,
        on_click=handle_submit,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            elevation=0,
        ),
    )

    # ── login card ────────────────────────────────────────────────
    login_card = ft.Container(
        width=350,
        height=530,
        padding=13,
        bgcolor=ft.Colors.WHITE,
        border_radius=16,
        shadow=ft.BoxShadow(
            blur_radius=24,
            spread_radius=0,
            color=ft.Colors.with_opacity(0.10, ft.Colors.BLACK),
            offset=ft.Offset(0, 6),
        ),
        content=ft.Column(
            controls=[
                # ── Branding ─────────────────────────────────────
                ft.Column(
                    controls=[
                        ft.CircleAvatar(
                            foreground_image_src="icon.png",
                            bgcolor=ft.Colors.GREY_100,
                            radius=32,
                        ),
                        ft.Text(
                            "Welcome back",
                            size=22,
                            weight=ft.FontWeight.W_700,
                            color=ft.Colors.GREY_900,
                        ),
                        ft.Text(
                            "Sign in to your Nu Age account.",
                            size=13,
                            color=ft.Colors.GREY_500,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                ),

                ft.Divider(height=1, color=ft.Colors.GREY_100),

                # ── Fields ───────────────────────────────────────
                ft.Container(height=20), # Spacer
                email,
                password,

                # ── Validation error ─────────────────────────────
                ft.Container(
                    content=validation_error,
                    visible=not(bool(validation_error.value)),
                    padding=ft.padding.only(left=2, top=0),
                ),

                # ── Forgot password ───────────────────────────────
                ft.Row(alignment=ft.MainAxisAlignment.CENTER,
                       visible=False,
                    controls=[
                        ft.TextButton(
                            content=ft.Text("Forgot password?"),
                            style=ft.ButtonStyle(
                                color=ft.Colors.PRIMARY,
                                padding=ft.padding.all(0),
                            ),
                        )
                    ],
                ),

                # ── Submit ────────────────────────────────────────
                ft.Row(controls=[Submit]),

                # ── Sign-up link ──────────────────────────────────
                ft.Row(
                    controls=[
                        ft.Text(
                            "Don't have an account?",
                            size=12,
                            color=ft.Colors.GREY_500,
                        ),
                        ft.TextButton(
                            "Create one",
                            on_click=lambda _: page.go("/signup"),
                            style=ft.ButtonStyle(
                                color=ft.Colors.PRIMARY,
                                padding=ft.padding.only(left=4),
                            ),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=0,
                ),
            ],
            spacing=14,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )

    # ── page layout ───────────────────────────────────────────────
    def get_view_padding():
        return (
            ft.padding.symmetric(vertical=80, horizontal=16)
            if page.width < 600
            else ft.padding.symmetric(vertical=10, horizontal=16)
        )

    view=ft.View(
        bgcolor=ft.Colors.GREY_100, # Use themed surface color for the background
        route="/",
        controls=[login_card],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        appbar=get_landing_appbar(page)
    )

    def on_page_resize(e):
        view.padding = get_view_padding()
        page.update()

    page.on_resize = on_page_resize

    return view