import flet as ft
from src.requests.auth import reset_request


async def edit_profile_view(page: ft.Page) -> ft.View:

    # =========================================================
    # SECTION 1: DATA & AUTH
    # =========================================================
    try:
        user_data = page.session.store.get("current_user")
        if not user_data:
            raise ValueError("No user session found.")
    except Exception as ex:
        _log_error("session_load", ex)
        return _error_view()

    try:
        token = await page.shared_preferences.get("auth_token")
        if not token:
            raise ValueError("Missing auth token.")
    except Exception as ex:
        _log_error("auth_token", ex)
        return _error_view()

    # =========================================================
    # SECTION 2: FORM CONTROLS
    # =========================================================
    _input_style = {
        "border_color": ft.Colors.OUTLINE_VARIANT,
        "focused_border_color": ft.Colors.PRIMARY,
        "border_radius": 10,
        "text_size": 14,
    }

    first_name_input = ft.TextField(
        label="First Name",
        value=user_data.get("first_name", ""),
        **_input_style,
    )
    last_name_input = ft.TextField(
        label="Last Name",
        value=user_data.get("last_name", ""),
        **_input_style,
    )
    username_input = ft.TextField(
        label="Username",
        value=user_data.get("username", ""),
        **_input_style,
    )

    # Inline feedback — hidden until needed
    feedback = ft.Container(
        visible=False,
        border_radius=8,
        padding=ft.padding.symmetric(horizontal=12, vertical=10),
        content=ft.Row(
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=16),
                ft.Text("", size=12, expand=True),
            ],
        ),
    )

    def show_feedback(message: str, is_error: bool = True):
        icon    = feedback.content.controls[0]
        label   = feedback.content.controls[1]
        icon.name  = ft.Icons.ERROR_OUTLINE_ROUNDED if is_error else ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
        icon.color = ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700
        label.value = message
        label.color = ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700
        feedback.bgcolor = ft.Colors.RED_50 if is_error else ft.Colors.GREEN_50
        feedback.visible = True
        page.update()

    def hide_feedback():
        feedback.visible = False

    # =========================================================
    # SECTION 3: VALIDATION
    # =========================================================
    def _validate() -> str | None:
        """Returns an error message string, or None if valid."""
        if not first_name_input.value.strip():
            return "First name cannot be empty."
        if not last_name_input.value.strip():
            return "Last name cannot be empty."
        username = username_input.value.strip()
        if not username:
            return "Username cannot be empty."
        if len(username) < 3:
            return "Username must be at least 3 characters."
        if " " in username:
            return "Username cannot contain spaces."
        return None

    # =========================================================
    # SECTION 4: SAVE HANDLER
    # =========================================================
    async def handle_save(e):
        hide_feedback()

        # Validate first
        validation_error = _validate()
        if validation_error:
            show_feedback(validation_error)
            return

        # Diff — only send changed fields
        updated_data = {
            key: value.strip()
            for key, value in {
                "first_name": first_name_input.value,
                "last_name":  last_name_input.value,
                "username":   username_input.value,
            }.items()
            if value.strip() != user_data.get(key, "")
        }

        if not updated_data:
            show_feedback("No changes detected.", is_error=False)
            return

        # Loading state
        save_btn.disabled = True
        save_btn.content  = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY),
                ft.Text("Saving…", color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.W_600),
            ],
        )
        page.update()

        try:
            status, data = await reset_request(token, updated_data)

            if status == 200:
                user_data.update(updated_data)
                page.session.store.set("current_user", user_data)
                page.go("/profile")
            elif status == 409:
                show_feedback("That username is already taken.")
            elif status == 422:
                show_feedback("Invalid data. Please check your inputs.")
            elif status == 401:
                show_feedback("Session expired. Please log in again.")
            else:
                show_feedback(f"Failed to update profile (error {status}). Please try again.")

        except Exception as ex:
            _log_error("handle_save", ex)
            show_feedback("Something went wrong. Please check your connection.")

        finally:
            save_btn.disabled = False
            save_btn.content  = ft.Text(
                "Save Changes",
                color=ft.Colors.ON_PRIMARY,
                weight=ft.FontWeight.W_600,
            )
            page.update()

    # =========================================================
    # SECTION 5: SAVE BUTTON
    # =========================================================
    save_btn = ft.ElevatedButton(
        content=ft.Text(
            "Save Changes",
            color=ft.Colors.ON_PRIMARY,
            weight=ft.FontWeight.W_600,
        ),
        bgcolor=ft.Colors.PRIMARY,
        height=50,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
        on_click=handle_save,
    )

    # =========================================================
    # SECTION 6: AVATAR (display only — no upload)
    # =========================================================
    full_name  = f"{user_data.get("first_name")} {user_data.get("last_name")}".strip() or "Unknown Learner"
    initials = "".join([n[0] for n in full_name.split()[:2]]).upper()
    avatar = ft.Container(
        width=90,
        height=90,
        border_radius=45,
        bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.ON_PRIMARY),
        border=ft.border.all(3, ft.Colors.with_opacity(0.30, ft.Colors.ON_PRIMARY)),
        alignment=ft.Alignment(0, 0),
        content=ft.Text(
            initials,
            size=32,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.ON_PRIMARY,
        ),
    )

    # =========================================================
    # SECTION 7: LAYOUT
    # =========================================================
    header = ft.Container(
        bgcolor=ft.Colors.PRIMARY,
        padding=ft.Padding(top=10, bottom=30, left=20, right=20),
        border_radius=ft.BorderRadius(
            top_left=0, top_right=0, bottom_left=30, bottom_right=30
        ),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.IconButton(
                            ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                            icon_color=ft.Colors.ON_PRIMARY,
                            on_click=lambda _: page.go("/profile"),
                        ),
                        ft.Text(
                            "Edit Profile",
                            color=ft.Colors.ON_PRIMARY,
                            size=18,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Container(width=40),  # balance
                    ],
                ),
                avatar,
            ],
        ),
    )

    form = ft.Container(
        padding=ft.padding.all(24),
        expand=True,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=16,
            controls=[
                first_name_input,
                last_name_input,
                username_input,
                feedback,
                ft.Container(height=4),
                save_btn,
            ],
        ),
    )

    return ft.View(
        route="/edit-profile",
        padding=0,
        bgcolor=ft.Colors.SURFACE,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=0,
                    controls=[header, form],
                ),
            )
        ],
    )


# =========================================================
# SECTION 8: UTILITIES
# =========================================================
def _error_view() -> ft.View:
    return ft.View(
        route="/edit-profile",
        bgcolor=ft.Colors.SURFACE,
        controls=[
            ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=52, color=ft.Colors.ERROR),
                        ft.Text(
                            "Could not load profile. Please try again.",
                            color=ft.Colors.ERROR,
                            size=15,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )
        ],
    )


def _log_error(context: str, ex: Exception):
    print(f"[ERROR] [{context}] {type(ex).__name__}: {ex}")