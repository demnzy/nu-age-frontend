import flet as ft
import asyncio
from datetime import datetime
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.auth import get_member_profile

async def member_profile_view(page: ft.Page, identifier: str):
    # ── Theme & Palette Determination ─────────────────────────────────────────
    is_dark = page.theme_mode == ft.ThemeMode.DARK
    
    PAGE_BG       = "#0F1117" if is_dark else "#F8FAFC"
    CARD_BG       = "#181B24" if is_dark else "#FFFFFF"
    CARD_BG_ALT   = "#222736" if is_dark else "#F1F5F9"
    BORDER_CLR    = ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.08, ft.Colors.BLACK)
    TEXT_PRIMARY  = "#F8FAFC" if is_dark else "#0F172A"
    TEXT_MUTED    = "#94A3B8" if is_dark else "#64748B"
    DIVIDER_CLR   = ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.06, ft.Colors.BLACK)
    ICON_BG       = ft.Colors.with_opacity(0.15 if is_dark else 0.08, ft.Colors.PRIMARY)

    # ── Initial Loading Socket ────────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.ProgressRing(color=ft.Colors.PRIMARY, stroke_width=3)
    )

    def handle_back(e):
        if len(page.views) > 1:
            page.views.pop()
            page.update()
        else:
            page.go("/network")

    # ── Async Data Fetcher & Renderer ─────────────────────────────────────────
    async def load_profile():
        token = await page.shared_preferences.get("auth_token")
        try:
            user_data = await asyncio.wait_for(get_member_profile(token, identifier), timeout=12)
        except Exception:
            user_data = {"error": "Connection timed out"}

        if not user_data or "error" in user_data or not isinstance(user_data, dict):
            content_socket.content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(32),
                content=ft.Column([
                    ft.Container(
                        width=64, height=64, border_radius=32,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED_400),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.PERSON_OFF_ROUNDED, size=32, color=ft.Colors.RED_400)
                    ),
                    ft.Text("Learner Not Found", size=18, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                    ft.Text("We couldn't retrieve this member's profile or they may have left the platform.", size=12, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=8),
                    ft.FilledButton(
                        "Return to Student Network",
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                        on_click=lambda _: page.go("/network")
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
            )
            page.update()
            return

        first_name = user_data.get("first_name", "")
        last_name  = user_data.get("last_name", "")
        full_name  = f"{first_name} {last_name}".strip() or "Learner"
        email      = user_data.get("email", "—")
        username   = user_data.get("username", "—")
        gender     = user_data.get("gender", "—")
        role       = user_data.get("role", "member")
        university = user_data.get("university") or ""
        streak     = user_data.get("streak", 0) or 0
        is_verified = user_data.get("is_verified", False)
        
        active_count = user_data.get("active_count", 0) or 0
        finished_count = user_data.get("finished_count", 0) or 0
        velocity_pct = round((finished_count / active_count) * 100) if active_count > 0 else (100 if finished_count > 0 else 0)

        # Parse joined date
        created_at_raw = user_data.get("created_at")
        joined_str = "Active Learner"
        if created_at_raw:
            try:
                if isinstance(created_at_raw, str):
                    dt = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                    joined_str = f"Member since {dt.strftime('%B %Y')}"
                elif isinstance(created_at_raw, datetime):
                    joined_str = f"Member since {created_at_raw.strftime('%B %Y')}"
            except Exception:
                pass

        initials = "".join([n[0] for n in full_name.split()[:2]]).upper() if full_name else "NU"

        # ── 1. Hero Header (Primary Brand Gradient) ───────────────────────────
        hero_gradient = ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[
                ft.Colors.PRIMARY,
                ft.Colors.SECONDARY
            ]
        )

        avatar_monogram = ft.Container(
            width=92, height=92, border_radius=46,
            bgcolor=ft.Colors.WHITE,
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(blur_radius=18, color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK), offset=ft.Offset(0, 4)),
            content=ft.Container(
                width=84, height=84, border_radius=42,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                alignment=ft.Alignment.CENTER,
                content=ft.Text(
                    initials, 
                    size=30, 
                    weight=ft.FontWeight.W_800, 
                    color=ft.Colors.PRIMARY
                )
            )
        )

        verified_badge = ft.Container(
            width=24, height=24, border_radius=12,
            bgcolor=ft.Colors.BLUE_500,
            alignment=ft.Alignment.CENTER,
            border=ft.Border.all(2, ft.Colors.WHITE),
            content=ft.Icon(ft.Icons.CHECK_ROUNDED, size=14, color=ft.Colors.WHITE),
            tooltip="Verified Student"
        )

        avatar_stack = ft.Stack([
            avatar_monogram,
            ft.Container(content=verified_badge, bottom=2, right=2) if is_verified else ft.Container(
                width=22, height=22, border_radius=11,
                bgcolor=ft.Colors.GREEN_500,
                border=ft.Border.all(2, "#111827" if is_dark else "#FFFFFF"),
                bottom=2, right=2,
                tooltip="Active Peer"
            )
        ])

        role_chip = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=4),
            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.WHITE)),
            content=ft.Row([
                ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=13, color=ft.Colors.WHITE),
                ft.Text(role.title(), size=11, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE)
            ], spacing=6, tight=True)
        )

        meta_chips = [role_chip]
        if university:
            meta_chips.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=4),
                    bgcolor=ft.Colors.with_opacity(0.16, ft.Colors.WHITE),
                    border_radius=14,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
                    content=ft.Row([
                        ft.Icon(ft.Icons.ACCOUNT_BALANCE_ROUNDED, size=12, color=ft.Colors.WHITE),
                        ft.Text(university, size=11, weight=ft.FontWeight.W_500, color=ft.Colors.WHITE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                    ], spacing=5, tight=True)
                )
            )

        hero_banner = ft.Container(
            bgcolor=ft.Colors.PRIMARY,
            gradient=hero_gradient,
            border_radius=ft.BorderRadius.only(bottom_left=32, bottom_right=32),
            padding=ft.Padding(left=20, right=20, top=36, bottom=36),
            shadow=ft.BoxShadow(blur_radius=25, color=ft.Colors.with_opacity(0.25, ft.Colors.PRIMARY), offset=ft.Offset(0, 8)),
            content=ft.Column([
                # Top Back Bar
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        icon_color=ft.Colors.WHITE,
                        icon_size=20,
                        tooltip="Go back",
                        style=ft.ButtonStyle(
                            bgcolor={"": ft.Colors.with_opacity(0.18, ft.Colors.WHITE)},
                            shape=ft.CircleBorder()
                        ),
                        on_click=handle_back
                    ),
                    ft.Text("PEER PROFILE", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                    ft.Container(width=40)  # Spacer for balance
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                ft.Container(height=12),
                
                # Monogram + Names
                ft.Column([
                    avatar_stack,
                    ft.Container(height=6),
                    ft.Text(full_name, size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER),
                    ft.Text(f"@{username}" if username != "—" else email, size=12, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
                    ft.Container(height=6),
                    ft.Row(meta_chips, alignment=ft.MainAxisAlignment.CENTER, wrap=True, spacing=8),
                    ft.Container(height=2),
                    ft.Text(joined_str, size=11, color=ft.Colors.with_opacity(0.65, ft.Colors.WHITE))
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=3)
            ], spacing=0)
        )

        # ── 2. Action Interaction Bar ─────────────────────────────────────────
        async def share_profile(e):
            share_url = f"https://nu-age.name.ng/member/{identifier}"
            try:
                await page.set_clipboard(share_url)
                page.show_dialog(
                    ft.SnackBar(
                        content=ft.Text("Profile link copied to clipboard!"),
                        bgcolor=ft.Colors.INDIGO_600,
                        duration=2500
                    )
                )
            except Exception:
                page.show_dialog(
                    ft.SnackBar(
                        content=ft.Text(f"Share link: {share_url}"),
                        duration=3000
                    )
                )
            page.update()

        action_bar = ft.Row([
            ft.FilledButton(
                "Message Learner",
                icon=ft.Icons.CHAT_BUBBLE_ROUNDED,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.Padding.symmetric(horizontal=18, vertical=12)
                ),
                expand=True,
                on_click=lambda _: page.go("/nu-chat")
            ),
            ft.OutlinedButton(
                "Share",
                icon=ft.Icons.SHARE_ROUNDED,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.Padding.symmetric(horizontal=18, vertical=12)
                ),
                on_click=share_profile
            )
        ], spacing=12)

        # ── 3. 4-Card Bento Learning Grid ─────────────────────────────────────
        def bento_kpi_card(icon, icon_color, value, label, subtitle, delay):
            return ft.Container(
                expand=True,
                bgcolor=CARD_BG,
                border_radius=18,
                padding=ft.Padding.all(16),
                border=ft.Border.all(1, BORDER_CLR),
                shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 4)),
                opacity=0,
                offset=ft.Offset(0, 0.15),
                animate_opacity=ft.Animation(450, ft.AnimationCurve.DECELERATE),
                animate_offset=ft.Animation(450, ft.AnimationCurve.DECELERATE),
                data=delay,
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            width=38, height=38, border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.14, icon_color),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, color=icon_color, size=20)
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=10,
                            bgcolor=CARD_BG_ALT,
                            content=ft.Text(subtitle, size=9, weight=ft.FontWeight.W_600, color=TEXT_MUTED)
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=4),
                    ft.Text(str(value), size=22, weight=ft.FontWeight.W_800, color=TEXT_PRIMARY),
                    ft.Text(label, size=11, weight=ft.FontWeight.W_600, color=TEXT_MUTED)
                ], spacing=2)
            )

        card_streak   = bento_kpi_card(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, ft.Colors.ORANGE_500, f"{streak}d", "Momentum", "Streak", 0.0)
        card_enrolled = bento_kpi_card(ft.Icons.AUTO_STORIES_ROUNDED, ft.Colors.INDIGO_400, active_count, "Enrolled", "Courses", 0.08)
        card_finished = bento_kpi_card(ft.Icons.EMOJI_EVENTS_ROUNDED, ft.Colors.GREEN_400, finished_count, "Completed", "Mastery", 0.16)
        card_velocity = bento_kpi_card(ft.Icons.BOLT_ROUNDED, ft.Colors.PURPLE_400, f"{velocity_pct}%", "Completion", "Rate", 0.24)

        is_mobile = (page.width or 800) < 650
        if is_mobile:
            stats_layout = ft.Column([
                ft.Row([card_streak, card_enrolled], spacing=12),
                ft.Row([card_finished, card_velocity], spacing=12)
            ], spacing=12)
        else:
            stats_layout = ft.Row([card_streak, card_enrolled, card_finished, card_velocity], spacing=14)

        # ── 4. Collaborative Study Callout ────────────────────────────────────
        collab_card = ft.Container(
            bgcolor=CARD_BG,
            border_radius=18,
            padding=ft.Padding.all(18),
            border=ft.Border.all(1, BORDER_CLR),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            content=ft.Row([
                ft.Container(
                    width=46, height=46, border_radius=14,
                    bgcolor=ICON_BG,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.GROUPS_ROUNDED, color=ft.Colors.PRIMARY, size=24)
                ),
                ft.Column([
                    ft.Text(f"Study with {first_name or 'Learner'}", size=14, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                    ft.Text("Compare progress, test flashcard recall, or discuss course topics in Nu-Chat.", size=11, color=TEXT_MUTED)
                ], spacing=2, expand=True),
                ft.FilledButton(
                    "Chat",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _: page.go("/nu-chat")
                )
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)
        )

        # ── 5. Learner Details Card ───────────────────────────────────────────
        def detail_item(icon, label, value, is_last=False):
            return ft.Column([
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    content=ft.Row([
                        ft.Container(
                            width=36, height=36, border_radius=10,
                            bgcolor=ICON_BG,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, color=ft.Colors.PRIMARY, size=18)
                        ),
                        ft.Column([
                            ft.Text(label, size=10, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
                            ft.Text(str(value), size=13, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY)
                        ], spacing=2, expand=True)
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)
                ),
                ft.Container() if is_last else ft.Container(content=ft.Divider(height=1, color=DIVIDER_CLR), padding=ft.Padding(left=64, right=16, top=0, bottom=0))
            ], spacing=0)

        details_list = [
            (ft.Icons.BADGE_ROUNDED, "Username", f"@{username}" if username != "—" else "—"),
            (ft.Icons.ACCOUNT_BALANCE_ROUNDED, "University / College", university if university else "Not specified"),
            (ft.Icons.SCHOOL_ROUNDED, "Academic Role", role.title()),
            (ft.Icons.PERSON_OUTLINE_ROUNDED, "Gender", gender.title() if gender != "—" else "Not specified"),
            (ft.Icons.VERIFIED_USER_OUTLINED, "Platform Status", "Verified Peer" if is_verified else "Active Student")
        ]

        detail_controls = [detail_item(d[0], d[1], d[2], idx == len(details_list) - 1) for idx, d in enumerate(details_list)]

        account_card = ft.Container(
            bgcolor=CARD_BG,
            border_radius=18,
            border=ft.Border.all(1, BORDER_CLR),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Column(detail_controls, spacing=0)
        )

        def section_heading(title, icon=None):
            return ft.Row([
                ft.Icon(icon, size=14, color=ft.Colors.PRIMARY) if icon else ft.Container(),
                ft.Text(title.upper(), size=11, weight=ft.FontWeight.W_800, color=TEXT_MUTED)
            ], spacing=6)

        # ── Main Assembly ─────────────────────────────────────────────────────
        main_content = ft.Container(
            alignment=ft.Alignment.TOP_CENTER,
            content=ft.Container(
                width=min(page.width or 800, 780),
                padding=ft.Padding.symmetric(horizontal=16, vertical=20),
                content=ft.Column([
                    action_bar,
                    ft.Container(height=4),
                    ft.Column([section_heading("Learning Momentum", ft.Icons.QUERY_STATS_ROUNDED), stats_layout], spacing=10),
                    ft.Container(height=4),
                    ft.Column([section_heading("Collaborative Study", ft.Icons.GROUPS_ROUNDED), collab_card], spacing=10),
                    ft.Container(height=4),
                    ft.Column([section_heading("Academic Background", ft.Icons.BADGE_ROUNDED), account_card], spacing=10),
                    ft.Container(height=24)
                ], spacing=18)
            )
        )

        content_socket.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[
                hero_banner,
                main_content
            ]
        )
        page.update()

        # Trigger stagger animations
        for card in [card_streak, card_enrolled, card_finished, card_velocity]:
            await asyncio.sleep(card.data)
            card.opacity = 1
            card.offset = ft.Offset(0, 0)
            page.update()

    page.run_task(load_profile)

    return ft.View(
        route=f"/member/{identifier}",
        bgcolor=PAGE_BG,
        padding=0,
        bottom_appbar=get_bottom_appbar(page),
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket
            )
        ]
    )