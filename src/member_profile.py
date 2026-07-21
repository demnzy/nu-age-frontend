import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.auth import get_member_profile

async def member_profile_view(page: ft.Page, identifier: str):

    # ── Palette ───────────────────────────────────────────────────────────────
    PAGE_BG       = ft.Colors.ON_PRIMARY    # Adapts to your dark/light background
    CARD_BG       = ft.Colors.SURFACE         # Pulls #FAFAFA in Light, #121212 in Dark
    LABEL_COLOR   = ft.Colors.ON_SURFACE_VARIANT # Native muted text color
    VALUE_COLOR   = ft.Colors.ON_SURFACE        # Pulls #1A1A1A in Light, #E8E8E8 in Dark
    DIVIDER_CLR   = ft.Colors.OUTLINE_VARIANT   # Native subtle divider color
    ICON_BG       = ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) # Keep this! PRIMARY is already adaptive.

    # ── Initial Loading Socket ────────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.ProgressRing(color=ft.Colors.PRIMARY, stroke_width=3)
    )
    def _go_back(e):
            if len(page.views) > 1:
                page.views.pop()
                page.update()
    # ── Async Data Fetcher & Renderer ─────────────────────────────────────────
    async def load_profile():
        token = await page.shared_preferences.get("auth_token")
        try:
            user_data = await get_member_profile(token, identifier)
        except Exception as e:
            content_socket.content = ft.Column(
                [
                    ft.Icon(ft.Icons.PERSON_OFF_OUTLINED, size=48, color=ft.Colors.GREY_400),
                    ft.Text("User not found.", color=ft.Colors.GREY_600, weight=ft.FontWeight.BOLD)
                ],
                alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
            page.update()
            return

        # Safe extraction
        first_name = user_data.get("first_name", "")
        last_name  = user_data.get("last_name", "")
        full_name  = f"{first_name} {last_name}".strip() or "Unknown Learner"
        email      = user_data.get("email", "—")
        username   = user_data.get("username", "—")
        gender     = user_data.get("gender", "—")
        role       = user_data.get("role", "member")
        university = user_data.get("university")
        streak     = user_data.get("streak", 0)

        initials = "".join([n[0] for n in full_name.split()[:2]]).upper() if full_name else "?"

        # ── Hero header ───────────────────────────────────────────────────────
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
                            blur_radius=16, color=ft.Colors.with_opacity(0.20, ft.Colors.BLACK), offset=ft.Offset(0, 4)
                        ),
                        content=ft.Container(
                            width=78, height=78, border_radius=39, bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text(initials, size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)
                        )
                    ),
                    ft.Container(height=2),
                    ft.Text(full_name, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    # Role pill
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=14, vertical=5),
                        bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.WHITE),
                        border_radius=20, border=ft.border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.WHITE)),
                        content=ft.Text(role.title(), size=11, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE)
                    )
                ]
            )
        )
        
        # Back Button Overlay
        header_stack = ft.Stack([
            header,
            ft.Container(
                content=ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    icon_color=ft.Colors.WHITE,
                    icon_size=20,
                    tooltip="Go back",
                    on_click=lambda _: page.go("/dashboard"), # Route back to wherever they came from
                    style=ft.ButtonStyle(
                        bgcolor={"": ft.Colors.with_opacity(0.18, ft.Colors.WHITE)},
                        shape=ft.CircleBorder()
                    )
                ),
                top=12, left=12
            )
        ])

        # ── Dynamic Info Card ─────────────────────────────────────────────────
        def info_row(icon, label, value, is_last=False):
            return ft.Column([
                ft.Container(
                    padding=ft.Padding(left=16, right=16, top=14, bottom=14),
                    content=ft.Row([
                        ft.Container(
                            width=38, height=38, border_radius=10, bgcolor=ICON_BG, alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, color=ft.Colors.PRIMARY, size=18)
                        ),
                        ft.Container(width=14),
                        ft.Column([
                            ft.Text(label, size=11, color=LABEL_COLOR, weight=ft.FontWeight.W_500),
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

        # Build list of rows based on available data
        rows_data = [
            (ft.Icons.ALTERNATE_EMAIL_ROUNDED, "Email", email),
            (ft.Icons.BADGE_OUTLINED, "Username", username),
            (ft.Icons.MALE if str(gender).lower() == "male" else ft.Icons.FEMALE, "Gender", gender),
        ]
        
        # Inject optional fields
        if university:
            rows_data.append((ft.Icons.ACCOUNT_BALANCE_ROUNDED, "University", university))
        if streak and int(streak) > 0:
            rows_data.append((ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, "Learning Streak", f"{streak} day" if streak ==1 else f"{streak} days"))

        row_controls = []
        for index, row_info in enumerate(rows_data):
            is_last = index == len(rows_data) - 1
            row_controls.append(info_row(row_info[0], row_info[1], row_info[2], is_last))

        info_card = ft.Container(
            bgcolor=CARD_BG,
            border_radius=16, border=ft.border.all(1, ft.Colors.with_opacity(0.07, ft.Colors.BLACK)),
            shadow=ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Column(row_controls, spacing=0, tight=True)
        )

        # ── Body Assembly ─────────────────────────────────────────────────────
        body = ft.Container(
            padding=ft.Padding(left=20, right=20, top=24, bottom=24),
            content=ft.Column(
                spacing=20,
                controls=[
                    ft.Text("USER DETAILS", size=11, weight=ft.FontWeight.W_700, color=LABEL_COLOR),
                    info_card,
                ]
            )
        )

        # Swap the loading spinner out for the fully rendered layout
        content_socket.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[header_stack, body]
        )
        page.update()

    # ── Boot ──────────────────────────────────────────────────────────────────
    page.run_task(load_profile)

    return ft.View(
        route=f"/profile/{identifier}",
        bgcolor=PAGE_BG,
        padding=0,
        bottom_appbar=get_bottom_appbar(page),
        controls=[
                content_socket
            
        ]
    )