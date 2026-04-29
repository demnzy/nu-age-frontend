import flet as ft
from src.components.bottom_appbar import get_bottom_appbar


async def profile_view(page: ft.Page):

    # ── Data ──────────────────────────────────────────────────────────────────
    user_data  = page.session.store.get("current_user")
    first_name = user_data.get("first_name", "")
    last_name  = user_data.get("last_name", "")
    full_name  = f"{first_name} {last_name}".strip()
    email      = user_data.get("email", "—")
    username   = user_data.get("username", "—")
    gender     = user_data.get("gender", "—")
    role       = user_data.get("role", "—")

    initials = "".join([n[0] for n in full_name.split()[:2]]).upper() if full_name else "?"

    # ── Palette ───────────────────────────────────────────────────────────────
    PAGE_BG       = "#F4F6FA"
    CARD_BG       = ft.Colors.WHITE
    LABEL_COLOR   = "#9CA3AF"   # muted grey
    VALUE_COLOR   = "#111827"   # near-black
    DIVIDER_CLR   = "#F3F4F6"
    ICON_BG       = ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY)

    # ── Logout logic ──────────────────────────────────────────────────────────
    async def execute_logout(e):
        await page.shared_preferences.remove("auth_token")
        page.go("/")
        page.update()

    async def handle_logout(e):
        page.show_dialog(logout_confirmation_dialog)
        page.update()

    logout_confirmation_dialog = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=16),
        title=ft.Row([
            ft.Icon(ft.Icons.LOGOUT_ROUNDED, color=ft.Colors.RED_400, size=20),
            ft.Text("Log out?", weight=ft.FontWeight.BOLD, size=16)
        ], spacing=10),
        content=ft.Text(
            "You'll need to sign back in to access your courses and progress.",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT
        ),
        actions=[
            ft.TextButton(
                "Cancel",
                style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT),
                on_click=lambda e: page.pop_dialog()
            ),
            ft.FilledButton(
                content=ft.Text("Log out", weight=ft.FontWeight.W_600),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.RED_400,
                    color=ft.Colors.WHITE,
                    shape=ft.RoundedRectangleBorder(radius=8)
                ),
                on_click=execute_logout
            )
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        actions_padding=ft.Padding(left=16, right=16, top=0, bottom=16)
    )

    # ── Hero header ───────────────────────────────────────────────────────────
    header = ft.Container(
        bgcolor=ft.Colors.PRIMARY,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[ft.Colors.PRIMARY, ft.Colors.SECONDARY]
        ),
        padding=ft.Padding(top=50, bottom=36, left=20, right=20),
        border_radius=ft.BorderRadius(
            bottom_left=28, bottom_right=28,
            top_left=0, top_right=0
        ),
        shadow=ft.BoxShadow(
            blur_radius=20,
            color=ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY),
            offset=ft.Offset(0, 6)
        ),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                # Avatar ring
                ft.Container(
                    width=86, height=86,
                    border_radius=43,
                    bgcolor=ft.Colors.WHITE,
                    alignment=ft.Alignment.CENTER,
                    shadow=ft.BoxShadow(
                        blur_radius=16,
                        color=ft.Colors.with_opacity(0.20, ft.Colors.BLACK),
                        offset=ft.Offset(0, 4)
                    ),
                    content=ft.Container(
                        width=78, height=78,
                        border_radius=39,
                        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(
                            initials,
                            size=28,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.PRIMARY
                        )
                    )
                ),
                ft.Container(height=2),
                ft.Text(
                    full_name,
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE
                ),
                # Role pill
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=14, vertical=5),
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.WHITE),
                    border_radius=20,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.WHITE)),
                    content=ft.Text(
                        role.title(),
                        size=11,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.WHITE
                    )
                )
            ]
        )
    )

    # Overlay buttons
    header_stack = ft.Stack([
        header,
        # Logout — top left
        ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.LOGOUT_ROUNDED,
                icon_color=ft.Colors.WHITE,
                icon_size=20,
                tooltip="Log out",
                on_click=handle_logout,
                style=ft.ButtonStyle(
                    bgcolor={"": ft.Colors.with_opacity(0.18, ft.Colors.WHITE)},
                    shape=ft.CircleBorder()
                )
            ),
            top=12, left=12
        ),
        # Edit — top right
        ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.WHITE,
                icon_size=20,
                tooltip="Edit profile",
                on_click=lambda _: page.go("/edit-profile"),
                style=ft.ButtonStyle(
                    bgcolor={"": ft.Colors.with_opacity(0.18, ft.Colors.WHITE)},
                    shape=ft.CircleBorder()
                )
            ),
            top=12, right=12
        )
    ])

    # ── Info card ─────────────────────────────────────────────────────────────
    def info_row(icon, label, value, is_last=False):
        return ft.Column([
            ft.Container(
                padding=ft.Padding(left=16, right=16, top=14, bottom=14),
                content=ft.Row([
                    # Icon bubble
                    ft.Container(
                        width=38, height=38,
                        border_radius=10,
                        bgcolor=ICON_BG,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, color=ft.Colors.PRIMARY, size=18)
                    ),
                    ft.Container(width=14),
                    ft.Column([
                        ft.Text(label, size=11, color=LABEL_COLOR, weight=ft.FontWeight.W_500,
                            ),
                        ft.Text(str(value).title() if label not in ("Email", "Username") else str(value),
                                size=14, weight=ft.FontWeight.W_600, color=VALUE_COLOR)
                    ], spacing=2, tight=True, expand=True)
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
            ),
            ft.Container() if is_last else ft.Container(
                content=ft.Divider(height=1, color=DIVIDER_CLR),
                padding=ft.Padding(left=68, right=0, top=0, bottom=0)
            )
        ], spacing=0, tight=True)

    info_card = ft.Container(
        bgcolor=CARD_BG,
        border_radius=16,
        border=ft.border.all(1, ft.Colors.with_opacity(0.07, ft.Colors.BLACK)),
        shadow=ft.BoxShadow(
            blur_radius=12,
            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
            offset=ft.Offset(0, 2)
        ),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        content=ft.Column([
            info_row(ft.Icons.ALTERNATE_EMAIL_ROUNDED, "Email", email),
            info_row(ft.Icons.BADGE_OUTLINED,          "Username", username),
            info_row(
                ft.Icons.MALE if str(gender).lower() == "male" else ft.Icons.FEMALE,
                "Gender", gender
            ),
            info_row(ft.Icons.SCHOOL_OUTLINED,         "Role", role, is_last=True),
        ], spacing=0, tight=True)
    )

    # ── Section header ────────────────────────────────────────────────────────
    def section_label(text):
        return ft.Text(
            text.upper(),
            size=11,
            weight=ft.FontWeight.W_700,
            color=LABEL_COLOR
        )

    # ── Quick-action strip ────────────────────────────────────────────────────
    def quick_action(icon, label, on_click=None):
        return ft.Container(
            expand=True,
            bgcolor=CARD_BG,
            border_radius=12,
            border=ft.border.all(1, ft.Colors.with_opacity(0.07, ft.Colors.BLACK)),
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
            ink=True,
            on_click=on_click,
            padding=ft.Padding(left=12, right=12, top=14, bottom=14),
            content=ft.Column([
                ft.Container(
                    width=36, height=36,
                    border_radius=10,
                    bgcolor=ICON_BG,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, color=ft.Colors.PRIMARY, size=18)
                ),
                ft.Container(height=8),
                ft.Text(label, size=11, weight=ft.FontWeight.W_600, color=VALUE_COLOR,
                        text_align=ft.TextAlign.CENTER, max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, tight=True)
        )

    actions_row = ft.Row([
        quick_action(ft.Icons.MENU_BOOK_ROUNDED,     "My Courses",  lambda _: page.go("/courses")),
        quick_action(ft.Icons.EMOJI_EVENTS_ROUNDED,  "Certificates"),
        quick_action(ft.Icons.SETTINGS_OUTLINED,     "Settings"),
    ], spacing=12)

    # ── Body ──────────────────────────────────────────────────────────────────
    body = ft.Container(
        padding=ft.Padding(left=20, right=20, top=24, bottom=24),
        content=ft.Column(
            spacing=20,
            controls=[
                section_label("Quick Actions"),
                actions_row,
                section_label("Account Details"),
                info_card,
            ]
        )
    )

    return ft.View(
        route="/profile",
        bgcolor=PAGE_BG,
        padding=0,
        bottom_appbar=get_bottom_appbar(page),
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=0,
                    controls=[header_stack, body]
                )
            )
        ]
    )