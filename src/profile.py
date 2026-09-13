import flet as ft
import urllib.parse
import asyncio
from datetime import datetime
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.auth import logout_request
from src.requests.enrollments import get_enrollments


def get_profile_palette(is_dark: bool) -> dict:
    """Central palette tokens for the profile view."""
    return {
        "card_bg": "#181B24" if is_dark else "#FFFFFF",
        "card_bg_alt": "#222736" if is_dark else "#F1F5F9",
        "border_clr": ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
        "text_primary": "#F8FAFC" if is_dark else "#0F172A",
        "text_muted": "#94A3B8" if is_dark else "#64748B",
        "divider_clr": ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
        "icon_bg": ft.Colors.with_opacity(0.15 if is_dark else 0.08, ft.Colors.PRIMARY),
        "theme_icon_bg": ft.Colors.with_opacity(0.14, ft.Colors.AMBER_400 if is_dark else ft.Colors.INDIGO_400),
        "theme_icon_color": ft.Colors.AMBER_400 if is_dark else ft.Colors.INDIGO_400,
        "theme_icon": ft.Icons.DARK_MODE_ROUNDED if is_dark else ft.Icons.LIGHT_MODE_ROUNDED,
        "theme_sub": "Dark Mode Enabled" if is_dark else "Light Mode Enabled",
    }


async def profile_view(page: ft.Page):
    # ── Initial Loading Socket ────────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.ProgressRing(color=ft.Colors.PRIMARY, stroke_width=3),
    )

    # ── Cached Enrollments ───────────────────────────────────────────────────
    cached_enrollments = None

    # ── Logout Modal Handler ──────────────────────────────────────────────────
    async def execute_logout(e):
        try:
            page.pop_dialog()
        except Exception:
            pass
        refresh_token = await page.shared_preferences.get("refresh_token")
        if refresh_token:
            try:
                await logout_request(refresh_token)
            except Exception:
                pass
        await page.shared_preferences.remove("refresh_token")
        await page.shared_preferences.remove("auth_token")
        page.go("/")
        page.update()

    def create_logout_dialog(is_dark: bool) -> ft.AlertDialog:
        p = get_profile_palette(is_dark)
        return ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=p["card_bg"],
            title=ft.Row([
                ft.Container(
                    width=36, height=36, border_radius=18,
                    bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.RED_400),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.LOGOUT_ROUNDED, color=ft.Colors.RED_400, size=18)
                ),
                ft.Text("Log Out from Nu-Age?", weight=ft.FontWeight.BOLD, size=16, color=p["text_primary"])
            ], spacing=12),
            content=ft.Text(
                "You will need to sign back in with your credentials to resume your courses and study streaks.",
                size=13,
                color=p["text_muted"]
            ),
            actions=[
                ft.TextButton(
                    "Cancel", 
                    style=ft.ButtonStyle(color=p["text_muted"]), 
                    on_click=lambda e: page.pop_dialog()
                ),
                ft.FilledButton(
                    "Log out", 
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.RED_500, 
                        color=ft.Colors.WHITE, 
                        shape=ft.RoundedRectangleBorder(radius=10)
                    ), 
                    on_click=execute_logout
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            actions_padding=ft.Padding(left=16, right=16, top=0, bottom=16)
        )

    # ── Main Loader Function ──────────────────────────────────────────────────
    async def load_profile():
        nonlocal cached_enrollments

        # ── Theme & Palette Determination ─────────────────────────────────────
        is_dark = page.theme_mode == ft.ThemeMode.DARK
        palette = get_profile_palette(is_dark)

        async def handle_logout_click(e):
            current_dark = page.theme_mode == ft.ThemeMode.DARK
            page.show_dialog(create_logout_dialog(current_dark))
            page.update()

        user_data  = page.session.store.get("current_user") or {}
        first_name = user_data.get("first_name", "")
        last_name  = user_data.get("last_name", "")
        full_name  = f"{first_name} {last_name}".strip() or "Student"
        email      = user_data.get("email", "—")
        username   = user_data.get("username", "—")
        gender     = user_data.get("gender", "—")
        role       = user_data.get("role", "student")
        university = user_data.get("university") or ""
        streak     = user_data.get("streak", 0) or 0
        is_verified = user_data.get("is_verified", False)

        # Parse joined date safely
        created_at_raw = user_data.get("created_at")
        joined_str = "Active Student"
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

        # Fetch enrollments on initial load
        if cached_enrollments is None:
            token = await page.shared_preferences.get("auth_token")
            try:
                cached_enrollments = await asyncio.wait_for(get_enrollments(token, None), timeout=12)
                if not isinstance(cached_enrollments, list):
                    cached_enrollments = []
            except Exception:
                cached_enrollments = []
                
        enrolled_list = cached_enrollments
        active_count = len(enrolled_list)
        finished_count = sum(1 for c in enrolled_list if (c.get("progress", 0) or 0) >= 100)
        velocity_pct = round((finished_count / active_count) * 100) if active_count > 0 else (100 if finished_count > 0 else 0)

        # ── 1. Hero Profile Banner (Primary Brand Gradient) ───────────────────
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
                bgcolor=ft.Colors.GREEN_400,
                border=ft.Border.all(2, ft.Colors.WHITE),
                bottom=2, right=2,
                tooltip="Online Learner"
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
                # Top Actions Bar
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.LOGOUT_ROUNDED,
                        icon_color=ft.Colors.WHITE,
                        icon_size=19,
                        tooltip="Log out",
                        style=ft.ButtonStyle(
                            bgcolor={"": ft.Colors.with_opacity(0.18, ft.Colors.WHITE)},
                            shape=ft.CircleBorder()
                        ),
                        on_click=handle_logout_click
                    ),
                    ft.Text("STUDENT PROFILE", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE)),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_ROUNDED,
                        icon_color=ft.Colors.WHITE,
                        icon_size=19,
                        tooltip="Edit profile",
                        style=ft.ButtonStyle(
                            bgcolor={"": ft.Colors.with_opacity(0.18, ft.Colors.WHITE)},
                            shape=ft.CircleBorder()
                        ),
                        on_click=lambda _: page.go("/edit-profile")
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                ft.Container(height=12),
                
                # Monogram + Names
                ft.Column([
                    avatar_stack,
                    ft.Container(height=6),
                    ft.Text(full_name, size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER),
                    ft.Text(f"@{username}" if username != "—" else email, size=12, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                    ft.Container(height=6),
                    ft.Row(meta_chips, alignment=ft.MainAxisAlignment.CENTER, wrap=True, spacing=8),
                    ft.Container(height=2),
                    ft.Text(joined_str, size=11, color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE))
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=3)
            ], spacing=0)
        )

        # ── 2. Bento Learning Grid ────────────────────────────────────────────
        # Registered bento references for instant, smooth in-place theme updating
        bento_registry = []

        def bento_kpi_card(icon, icon_color, value, label, subtitle):
            sub_text = ft.Text(subtitle, size=9, weight=ft.FontWeight.W_600, color=palette["text_muted"])
            sub_pill = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=10,
                bgcolor=palette["card_bg_alt"],
                animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                content=sub_text,
            )
            val_text = ft.Text(str(value), size=22, weight=ft.FontWeight.W_800, color=palette["text_primary"])
            lbl_text = ft.Text(label, size=11, weight=ft.FontWeight.W_600, color=palette["text_muted"])
            
            box = ft.Container(
                expand=True,
                bgcolor=palette["card_bg"],
                border_radius=18,
                padding=ft.Padding.all(16),
                border=ft.Border.all(1, palette["border_clr"]),
                shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 4)),
                animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            width=38, height=38, border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.14, icon_color),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, color=icon_color, size=20)
                        ),
                        sub_pill,
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=4),
                    val_text,
                    lbl_text,
                ], spacing=2)
            )
            bento_registry.append({
                "box": box,
                "sub_pill": sub_pill,
                "sub_text": sub_text,
                "val_text": val_text,
                "lbl_text": lbl_text,
            })
            return box

        card_streak   = bento_kpi_card(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, ft.Colors.ORANGE_500, f"{streak}d", "Momentum", "Streak")
        card_enrolled = bento_kpi_card(ft.Icons.AUTO_STORIES_ROUNDED, ft.Colors.INDIGO_400, active_count, "Enrolled", "Courses")
        card_finished = bento_kpi_card(ft.Icons.EMOJI_EVENTS_ROUNDED, ft.Colors.GREEN_400, finished_count, "Completed", "Mastery")
        card_velocity = bento_kpi_card(ft.Icons.BOLT_ROUNDED, ft.Colors.PURPLE_400, f"{velocity_pct}%", "Completion", "Rate")

        # Responsive Layout: 2x2 for mobile (< 650px), 4 across for desktop
        is_mobile = (page.width or 800) < 650
        if is_mobile:
            stats_layout = ft.Column([
                ft.Row([card_streak, card_enrolled], spacing=12),
                ft.Row([card_finished, card_velocity], spacing=12)
            ], spacing=12)
        else:
            stats_layout = ft.Row([card_streak, card_enrolled, card_finished, card_velocity], spacing=14)

        # ── 3. Appearance / Instant Theme Switcher Card ───────────────────────
        theme_card_icon = ft.Icon(
            palette["theme_icon"],
            color=palette["theme_icon_color"],
            size=20,
        )
        theme_icon_box = ft.Container(
            width=40, height=40, border_radius=12,
            bgcolor=palette["theme_icon_bg"],
            alignment=ft.Alignment.CENTER,
            content=theme_card_icon,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        theme_title = ft.Text(
            "Theme Appearance",
            size=13, weight=ft.FontWeight.BOLD,
            color=palette["text_primary"],
        )
        theme_subtitle = ft.Text(
            palette["theme_sub"],
            size=11,
            color=palette["text_muted"],
        )

        async def on_toggle_theme(e):
            new_is_dark = theme_switch.value
            
            # 1. Apply new palette tokens in-place immediately (0ms delay, no re-layout)
            apply_theme_palette(new_is_dark)

            # 2. Sync global theme in main.py without duplicate render
            toggle_fn = page.data.get("toggle_dark_mode") if isinstance(page.data, dict) else None
            if toggle_fn:
                try:
                    await toggle_fn(target_is_dark=new_is_dark, trigger_update=False)
                except TypeError:
                    await toggle_fn()
            else:
                page.theme_mode = ft.ThemeMode.DARK if new_is_dark else ft.ThemeMode.LIGHT
                page.bgcolor = "#121212" if new_is_dark else ft.Colors.SURFACE

            # 3. Single unified update: instant, seamless, zero flicker
            page.update()

        theme_switch = ft.Switch(
            value=is_dark,
            active_color=ft.Colors.PRIMARY,
            on_change=on_toggle_theme,
        )

        theme_card = ft.Container(
            bgcolor=palette["card_bg"],
            border_radius=18,
            padding=ft.Padding.symmetric(horizontal=18, vertical=14),
            border=ft.Border.all(1, palette["border_clr"]),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            content=ft.Row([
                theme_icon_box,
                ft.Column([
                    theme_title,
                    theme_subtitle,
                ], spacing=2, expand=True),
                theme_switch,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)
        )

        # ── 4. Quick LMS Action Shortcuts ─────────────────────────────────────
        shortcut_registry = []

        def lms_quick_tile(icon, icon_color, title, route):
            t_title = ft.Text(title, size=10, weight=ft.FontWeight.BOLD, color=palette["text_primary"])
            t_chev  = ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=16, color=palette["text_muted"])

            box = ft.Container(
                expand=True,
                bgcolor=palette["card_bg"],
                border_radius=16,
                border=ft.Border.all(1, palette["border_clr"]),
                padding=ft.Padding.all(10),
                shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
                animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                ink=True,
                on_click=lambda _: page.go(route),
                content=ft.Row([
                    ft.Container(
                        width=38, height=38, border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.12, icon_color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, color=icon_color, size=16)
                    ),
                    ft.Column([
                        t_title,
                    ], expand=True),
                    t_chev,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
            )
            shortcut_registry.append({
                "box": box,
                "title": t_title,
                "chevron": t_chev,
            })
            return box

        shortcuts_grid = ft.Column([
            ft.Row([
                lms_quick_tile(ft.Icons.BOOK_ROUNDED, ft.Colors.INDIGO_400, "My Courses", "/courses"),
                lms_quick_tile(ft.Icons.STYLE_ROUNDED, ft.Colors.PURPLE_400, "Study Hub", "/self-study")
            ], spacing=12),
            ft.Row([
                lms_quick_tile(ft.Icons.PEOPLE_ROUNDED, ft.Colors.TEAL_400, "My Network",  "/network"),
                lms_quick_tile(ft.Icons.FORUM_ROUNDED, ft.Colors.LIGHT_BLUE_400, "Nu-Chat",  "/nu-chat")
            ], spacing=12)
        ], spacing=12)

        # ── 5. Account & Academic Details Card ─────────────────────────────────
        account_registry = []
        divider_registry = []

        def detail_item(icon, label, value, is_last=False):
            i_box = ft.Container(
                width=36, height=36, border_radius=10,
                bgcolor=palette["icon_bg"],
                alignment=ft.Alignment.CENTER,
                animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                content=ft.Icon(icon, color=ft.Colors.PRIMARY, size=18)
            )
            lbl = ft.Text(label, size=10, weight=ft.FontWeight.W_600, color=palette["text_muted"])
            val = ft.Text(str(value), size=13, weight=ft.FontWeight.W_600, color=palette["text_primary"])
            account_registry.append({"icon_box": i_box, "label": lbl, "value": val})

            div = ft.Divider(height=1, color=palette["divider_clr"])
            if not is_last:
                divider_registry.append(div)

            return ft.Column([
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    content=ft.Row([
                        i_box,
                        ft.Column([lbl, val], spacing=2, expand=True)
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)
                ),
                ft.Container() if is_last else ft.Container(content=div, padding=ft.Padding(left=64, right=16, top=0, bottom=0))
            ], spacing=0)

        details_list = [
            (ft.Icons.ALTERNATE_EMAIL_ROUNDED, "Email Address", email),
            (ft.Icons.BADGE_ROUNDED, "Username", f"@{username}" if username != "—" else "—"),
            (ft.Icons.ACCOUNT_BALANCE_ROUNDED, "University / College", university if university else "Not specified"),
            (ft.Icons.PERSON_OUTLINE_ROUNDED, "Gender", gender.title() if gender != "—" else "Not specified"),
            (ft.Icons.VERIFIED_USER_OUTLINED, "Account Standing", "Active & Verified" if is_verified else "Active Student")
        ]

        detail_controls = [detail_item(d[0], d[1], d[2], idx == len(details_list) - 1) for idx, d in enumerate(details_list)]

        account_card = ft.Container(
            bgcolor=palette["card_bg"],
            border_radius=18,
            border=ft.Border.all(1, palette["border_clr"]),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Column(detail_controls, spacing=0)
        )

        # ── 6. Refer & Earn CTA ───────────────────────────────────────────────
        async def open_whatsapp(e):
            msg = (
                "Just found Nu-Age and it's honestly a game changer for studying! "
                "It has curated courses, an AI tutor and peer study network!\n\n"
                "Check it out 👉 https://nu-age.name.ng\n\n"
                "Pro tip: Join and connect with other students to boost your momentum!"
            )
            encoded = urllib.parse.quote(msg)
            await page.launch_url(f"https://wa.me/?text={encoded}")

        referral_card = ft.Container(
            ink=True,
            on_click=open_whatsapp,
            border_radius=18,
            padding=ft.Padding.all(18),
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                colors=["#F59E0B", "#EA580C"]
            ),
            shadow=ft.BoxShadow(blur_radius=14, color=ft.Colors.with_opacity(0.25, ft.Colors.ORANGE_700), offset=ft.Offset(0, 5)),
            content=ft.Row([
                ft.Container(
                    width=44, height=44, border_radius=14,
                    bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.CARD_GIFTCARD_ROUNDED, color=ft.Colors.WHITE, size=24)
                ),
                ft.Column([
                    ft.Text("Refer & Earn Study Perks", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                    ft.Text("Share Nu-Age with classmates on WhatsApp to unlock perks.", size=11, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE))
                ], spacing=2, expand=True),
                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=ft.Colors.WHITE, size=20)
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)
        )

        # ── Section Heading Helper ────────────────────────────────────────────
        heading_registry = []

        def section_heading(title, icon=None):
            h_text = ft.Text(title.upper(), size=11, weight=ft.FontWeight.W_800, color=palette["text_muted"])
            heading_registry.append(h_text)
            return ft.Row([
                ft.Icon(icon, size=14, color=ft.Colors.PRIMARY) if icon else ft.Container(),
                h_text,
            ], spacing=6)

        # ── In-Place Palette Updater (Zero Rebuild, Seamless Cross-Fade) ───────
        def apply_theme_palette(dark: bool):
            p = get_profile_palette(dark)

            # 1. Update Bento KPI cards
            for c in bento_registry:
                c["box"].bgcolor = p["card_bg"]
                c["box"].border = ft.Border.all(1, p["border_clr"])
                c["sub_pill"].bgcolor = p["card_bg_alt"]
                c["sub_text"].color = p["text_muted"]
                c["val_text"].color = p["text_primary"]
                c["lbl_text"].color = p["text_muted"]

            # 2. Update Theme Switcher Card
            theme_card.bgcolor = p["card_bg"]
            theme_card.border = ft.Border.all(1, p["border_clr"])
            theme_icon_box.bgcolor = p["theme_icon_bg"]
            theme_card_icon.name = p["theme_icon"]
            theme_card_icon.color = p["theme_icon_color"]
            theme_title.color = p["text_primary"]
            theme_subtitle.value = p["theme_sub"]
            theme_subtitle.color = p["text_muted"]
            theme_switch.value = dark

            # 3. Update Shortcut Tiles
            for t in shortcut_registry:
                t["box"].bgcolor = p["card_bg"]
                t["box"].border = ft.Border.all(1, p["border_clr"])
                t["title"].color = p["text_primary"]
                t["chevron"].color = p["text_muted"]

            # 4. Update Account Card
            account_card.bgcolor = p["card_bg"]
            account_card.border = ft.Border.all(1, p["border_clr"])
            for itm in account_registry:
                itm["icon_box"].bgcolor = p["icon_bg"]
                itm["label"].color = p["text_muted"]
                itm["value"].color = p["text_primary"]
            for div in divider_registry:
                div.color = p["divider_clr"]

            # 5. Update Section Headings
            for h in heading_registry:
                h.color = p["text_muted"]

        # ── Content Assembly ──────────────────────────────────────────────────
        main_content = ft.Container(
            alignment=ft.Alignment.TOP_CENTER,
            content=ft.Container(
                width=min(page.width or 800, 780),
                padding=ft.Padding.symmetric(horizontal=16, vertical=20),
                content=ft.Column([
                    referral_card,
                    ft.Container(height=4),
                    ft.Column([section_heading("Learning Momentum", ft.Icons.QUERY_STATS_ROUNDED), stats_layout], spacing=10),
                    ft.Container(height=4),
                    ft.Column([section_heading("Quick Hub Shortcuts", ft.Icons.GRID_VIEW_ROUNDED), shortcuts_grid], spacing=10),
                    ft.Container(height=4),
                    ft.Column([section_heading("Account & Academic Details", ft.Icons.BADGE_ROUNDED), account_card], spacing=10),
                    ft.Container(height=4),
                    ft.Column([section_heading("System Settings", ft.Icons.TUNE_ROUNDED), theme_card], spacing=10),
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

    page.run_task(load_profile)

    return ft.View(
        route="/profile",
        padding=0,
        bottom_appbar=get_bottom_appbar(page),
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket
            )
        ]
    )