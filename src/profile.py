import os
import flet as ft
import urllib.parse
import asyncio
from datetime import datetime
from src.components.bottom_appbar import get_bottom_appbar, NotificationManager
from src.requests.auth import logout_request, logout_all_devices_request
from src.requests.enrollments import get_enrollments
from src.theme.typography import build_typography_switcher_button
from src.components.badge_pill import build_glossy_badge_pill
from src.requests.promo import redeem_promo_code_api, get_my_badges_api, equip_primary_badge_api
from src.utils.file_opener import show_page_snackbar
from src.requests.auth import upload_avatar_request, remove_avatar_request
from src.services.auth_session import AuthSession
import base64


def _is_platform_super_admin(username: str, email: str = "") -> bool:
    """Checks whether the logged in user is the platform super admin (username == 'nu-admin')."""
    return (username or "").strip().lower() == "nu-admin"


def _is_dark_mode(page: ft.Page) -> bool:
    if hasattr(page, "theme_mode") and page.theme_mode is not None:
        return page.theme_mode != ft.ThemeMode.LIGHT
    return True


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
    is_dark = _is_dark_mode(page)

    # ── Initial Loading Socket ────────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
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
        try:
            from src.services.auth_session import AuthSession
            AuthSession.get_instance(page).set_logging_out(True)
        except Exception:
            pass
        refresh_token = await page.shared_preferences.get("refresh_token")
        if refresh_token:
            try:
                await logout_request(refresh_token)
            except Exception as ex:
                print(f"[Logout] Server logout notification error: {ex!r}")

        # 1. Clear tokens and cached user preferences in shared preferences
        for key in ["refresh_token", "auth_token", "user_id", "user_role", "user_interests", "daily_study_goal"]:
            try:
                await page.shared_preferences.remove(key)
            except Exception:
                pass

        # 2. Clear all transient in-memory session data
        try:
            from src.utils.session_utils import clear_session_store
            clear_session_store(page)
        except Exception:
            pass

        try:
            from src.services.auth_session import AuthSession
            await AuthSession.get_instance(page).clear_tokens()
        except Exception:
            pass

        # 3. Clear reactive notification badges & cache
        try:
            NotificationManager.clear_all()
        except Exception:
            pass

        # Unbind push notification identity
        try:
            from src.services.push_notification_service import unbind_user_push_identity
            page.run_task(unbind_user_push_identity, page)
        except Exception:
            pass

        # 4. Refresh persistent navigation bar for logged-out state
        nav_bar = getattr(page, "persistent_nav_bar", None)
        if nav_bar:
            try:
                nav_bar.refresh()
            except Exception:
                pass

        page.go("/login")
        page.update()

    async def execute_logout_all(e):
        try:
            page.pop_dialog()
        except Exception:
            pass
        token = await page.shared_preferences.get("auth_token")
        if token:
            try:
                status, data = await logout_all_devices_request(token)
                if status in (200, 201):
                    revoked = data.get("revoked_count", 0) if isinstance(data, dict) else 0
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Logged out from all devices ({revoked} sessions revoked)."),
                        bgcolor=ft.Colors.GREEN_700
                    )
                    page.snack_bar.open = True
                    page.update()
                else:
                    err_msg = data.get("detail", "Failed to revoke sessions on server.") if isinstance(data, dict) else "Error"
                    print(f"[LogoutAll] Server response: {status} {err_msg}")
            except Exception as ex:
                print(f"[LogoutAll] Request error: {ex!r}")

        # Local cleanup & logout
        await execute_logout(e)

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
                ft.Text("Log Out from Nu Age?", weight=ft.FontWeight.BOLD, size=16, color=p["text_primary"])
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

    def create_logout_all_dialog(is_dark: bool) -> ft.AlertDialog:
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
                    content=ft.Icon(ft.Icons.DEVICES_ROUNDED, color=ft.Colors.RED_400, size=18)
                ),
                ft.Text("Log Out All Devices?", weight=ft.FontWeight.BOLD, size=16, color=p["text_primary"])
            ], spacing=12),
            content=ft.Text(
                "This will invalidate all active refresh tokens and sign you out across all browsers and devices. You will need to sign back in everywhere.",
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
                    "Log Out Everywhere", 
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.RED_600, 
                        color=ft.Colors.WHITE, 
                        shape=ft.RoundedRectangleBorder(radius=10)
                    ), 
                    on_click=execute_logout_all
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            actions_padding=ft.Padding(left=16, right=16, top=0, bottom=16)
        )

    # ── Main Loader Function ──────────────────────────────────────────────────
    async def load_profile():
        nonlocal cached_enrollments

        # ── Theme & Palette Determination ─────────────────────────────────────
        is_dark = _is_dark_mode(page)
        palette = get_profile_palette(is_dark)

        async def handle_logout_click(e):
            current_dark = page.theme_mode == ft.ThemeMode.DARK
            page.show_dialog(create_logout_dialog(current_dark))
            page.update()

        async def handle_logout_all_click(e):
            current_dark = page.theme_mode == ft.ThemeMode.DARK
            page.show_dialog(create_logout_all_dialog(current_dark))
            page.update()

        try:
            from src.utils.session_utils import get_session_user, set_session_value
            user_data = get_session_user(page)
        except Exception:
            user_data = {}

        token = await page.shared_preferences.get("auth_token") if hasattr(page, "shared_preferences") and page.shared_preferences else ""
        if (not user_data or not user_data.get("id")) and token:
            try:
                from src.requests.auth import get_current_user_request
                status, u_info = await asyncio.wait_for(get_current_user_request(token), timeout=2.5)
                if status == 200 and isinstance(u_info, dict):
                    user_data = u_info
                    set_session_value(page, "current_user", user_data)
            except Exception:
                pass

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

        # Fetch enrollments and subscription status on initial load
        sub_info = {}
        token = await page.shared_preferences.get("auth_token") if hasattr(page, "shared_preferences") and page.shared_preferences else ""
        if cached_enrollments is None and token:
            try:
                cached_enrollments = await asyncio.wait_for(get_enrollments(token, None), timeout=3.5)
                if not isinstance(cached_enrollments, list):
                    cached_enrollments = []
            except Exception:
                cached_enrollments = []

        if token:
            try:
                from src.requests.subscription import get_subscription_status
                sub_res = await asyncio.wait_for(get_subscription_status(token), timeout=2.0)
                if isinstance(sub_res, dict) and "plan_id" in sub_res:
                    sub_info = sub_res
            except Exception:
                pass
                
        enrolled_list = cached_enrollments or []
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

        profile_picture_url = user_data.get("profile_picture_url")
        has_avatar = bool(profile_picture_url and isinstance(profile_picture_url, str) and profile_picture_url.startswith("http"))
        async def _apply_avatar_result(status, data, ok_msg):
            if status == 200 and isinstance(data, dict):
                merged = dict(user_data)
                merged["profile_picture_url"] = data.get("profile_picture_url")
                try:
                    set_session_value(page, "current_user", merged)
                except Exception:
                    pass
                show_page_snackbar(page, ok_msg)
                await load_profile()
            else:
                detail = data.get("detail") if isinstance(data, dict) else None
                show_page_snackbar(page, detail or "Could not update profile photo.")

        async def _change_avatar(ev=None):
            sheet.open = False
            page.update()
            try:
                files = await ft.FilePicker().pick_files(
                    allow_multiple=False,
                    file_type=ft.FilePickerFileType.IMAGE,
                    with_data=True,
                )
            except Exception:
                show_page_snackbar(page, "Could not open file picker.")
                return
            if not files:
                return
            picked = files[0]
            if not picked.bytes:
                show_page_snackbar(page, "Failed to read image data. Try another image.")
                return
            if len(picked.bytes) > 5 * 1024 * 1024:
                show_page_snackbar(page, "Image exceeds maximum 5MB limit.")
                return
            show_page_snackbar(page, "Uploading photo…")
            b64 = base64.b64encode(picked.bytes).decode("utf-8")
            status, data = await upload_avatar_request(token, b64, picked.name or "avatar.jpg")
            await _apply_avatar_result(status, data, "Profile photo updated.")

        async def _remove_avatar(ev=None):
            sheet.open = False
            page.update()
            status, data = await remove_avatar_request(token)
            await _apply_avatar_result(status, data, "Profile photo removed.")

        def _go_edit(ev=None):
            sheet.open = False
            page.update()
            page.go("/edit-profile")

        sheet = ft.BottomSheet(
            content=ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=12),
                content=ft.Column(
                    tight=True,
                    spacing=0,
                    controls=[
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.PHOTO_CAMERA_ROUNDED, color=ft.Colors.PRIMARY),
                            title=ft.Text("Change photo"),
                            on_click=lambda ev: page.run_task(_change_avatar, ev),
                        ),
                        ft.ListTile(
                            visible=has_avatar,
                            leading=ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color=ft.Colors.ERROR),
                            title=ft.Text("Remove photo", color=ft.Colors.ERROR),
                            on_click=lambda ev: page.run_task(_remove_avatar, ev),
                        ),
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.EDIT_ROUNDED),
                            title=ft.Text("Edit profile"),
                            on_click=_go_edit,
                        ),
                    ],
                ),
            ),
        )

        def _open_avatar_sheet(ev=None):
            if sheet not in page.overlay:
                page.overlay.append(sheet)
            sheet.open = True
            page.update()

        avatar_monogram = ft.Container(
            width=92, height=92, border_radius=46,
            bgcolor=ft.Colors.WHITE,
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(blur_radius=18, color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK), offset=ft.Offset(0, 4)),
            content=ft.CircleAvatar(
                radius=42,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                foreground_image_src=profile_picture_url if has_avatar else None,
                content=ft.Text(
                    initials, 
                    size=30, 
                    weight=ft.FontWeight.W_800, 
                    color=ft.Colors.PRIMARY
                )
            ),
            ink=True,
            tooltip="Change or remove photo",
            on_click=_open_avatar_sheet,
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

        primary_badge = user_data.get("primary_badge")
        name_badge_container = ft.Container(
            content=build_glossy_badge_pill(primary_badge, is_mobile=False, max_width=140, max_chars=16)
            if (primary_badge and isinstance(primary_badge, dict))
            else None,
            visible=bool(primary_badge and isinstance(primary_badge, dict)),
            animate_scale=ft.Animation(320, ft.AnimationCurve.EASE_OUT_BACK),
            animate_opacity=ft.Animation(260, ft.AnimationCurve.EASE_IN_OUT),
            scale=1.0,
            opacity=1.0,
        )

        name_row = ft.Row(
            controls=[
                ft.Text(full_name, size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER),
                name_badge_container,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            wrap=True,
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
    bgcolor={ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.18, ft.Colors.WHITE)},
    shape=ft.CircleBorder()
),
                        on_click=handle_logout_click
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_ROUNDED,
                        icon_color=ft.Colors.WHITE,
                        icon_size=19,
                        tooltip="Edit profile",
                        style=ft.ButtonStyle(
    bgcolor={ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.18, ft.Colors.WHITE)},
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
                    name_row,
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

            # Instantly update BottomAppBar colors to match new mode
            try:
                from src.components.bottom_appbar import BottomAppBarThemeManager
                BottomAppBarThemeManager.notify_theme_changed(new_is_dark)
            except Exception:
                pass

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

        font_switcher_btn = build_typography_switcher_button(
            page,
            on_preset_changed=lambda _: (apply_theme_palette(page.theme_mode == ft.ThemeMode.DARK), page.update()),
            button_height=30,
        )

        theme_card = ft.Container(
            bgcolor=palette["card_bg"],
            border_radius=18,
            padding=ft.Padding.symmetric(horizontal=18, vertical=14),
            border=ft.Border.all(1, palette["border_clr"]),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            content=ft.Row([
                theme_icon_box,
                ft.Column([
                    theme_title,
                    theme_subtitle,
                ], spacing=2, expand=True),
                font_switcher_btn,
                theme_switch,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
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

        # ── Nu-Age Store & Learning Plan Billing Card ─────────────────────────
        plan_label = sub_info.get("label") or "Free Tier"
        mat_remaining = sub_info.get("materials_remaining")
        gen_remaining = sub_info.get("generations_remaining")
        bonus_mats = sub_info.get("bonus_materials", 0)
        
        mat_str = f"{mat_remaining} uploads left" if mat_remaining is not None else "Unlimited uploads"
        gen_str = f"{gen_remaining} AI generations left" if gen_remaining is not None else "Unlimited AI generations"
        if bonus_mats:
            mat_str += f" (+{bonus_mats} booster slots)"

        store_title = ft.Text("Learning Plan & Study Quotas", size=13, weight=ft.FontWeight.BOLD, color=palette["text_primary"])
        store_sub = ft.Text(f"{plan_label} • {mat_str} • {gen_str}", size=11, color=palette["text_muted"])

        store_billing_card = ft.Container(
            ink=True,
            on_click=lambda _: page.go("/store?back=/profile"),
            border_radius=18,
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)),
            bgcolor=palette["card_bg"],
            padding=ft.Padding.all(16),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            content=ft.Row([
                ft.Container(
                    width=42, height=42, border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.STOREFRONT_ROUNDED, color=ft.Colors.PRIMARY, size=22)
                ),
                ft.Column([
                    ft.Row([
                        store_title,
                        ft.Container(
                            content=ft.Text(plan_label.upper(), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                            padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                            border_radius=5,
                        ),
                    ], spacing=6, tight=True, wrap=True),
                    store_sub
                ], spacing=3, expand=True),
                ft.ElevatedButton(
                    content=ft.Row(
                        tight=True,
                        spacing=4,
                        controls=[
                            ft.Text("Store", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                            ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=13, color=ft.Colors.WHITE),
                        ],
                    ),
                    bgcolor=ft.Colors.PRIMARY,
                    height=34,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                    on_click=lambda _: page.go("/store?back=/profile"),
                )
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)
        )

        shortcuts_grid = ft.Column([
            ft.Row([
                lms_quick_tile(ft.Icons.BOOK_ROUNDED, ft.Colors.INDIGO_400, "My Courses", "/courses"),
                lms_quick_tile(ft.Icons.STYLE_ROUNDED, ft.Colors.PURPLE_400, "Study Hub", "/self-study")
            ], spacing=12),
            ft.Row([
                lms_quick_tile(ft.Icons.STOREFRONT_ROUNDED, ft.Colors.AMBER_500, "Store & Plans", "/store?back=/profile"),
                lms_quick_tile(ft.Icons.PEOPLE_ROUNDED, ft.Colors.TEAL_400, "My Network",  "/network"),
            ], spacing=12),
            ft.Row([
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
        ]

        detail_controls = [detail_item(d[0], d[1], d[2], idx == len(details_list) - 1) for idx, d in enumerate(details_list)]

        account_card = ft.Container(
            bgcolor=palette["card_bg"],
            border_radius=18,
            border=ft.Border.all(1, palette["border_clr"]),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Column(detail_controls, spacing=0)
        )

        # ── 6. Refer & Earn CTA ───────────────────────────────────────────────
        async def open_whatsapp(e):
            msg = (
                "Just found Nu Age and it's honestly a game changer for studying! "
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
                    ft.Text("Share Nu Age with classmates on WhatsApp to unlock perks.", size=11, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE))
                ], spacing=2, expand=True),
                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=ft.Colors.WHITE, size=20)
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)
        )

        # ── 7. Redeem Promo Code Card & Interactive Modal ─────────────────────
        promo_title = ft.Text("Redeem Promo Code", size=13, weight=ft.FontWeight.BOLD, color=palette["text_primary"])
        promo_sub = ft.Text("Enter voucher or campus ambassador codes for study perks & coins.", size=11, color=palette["text_muted"])

        async def _open_redeem_promo_modal(e=None):
            dlg_box = [None]
            cur_p = get_profile_palette(_is_dark_mode(page))
            code_input = ft.TextField(
                label="Promo Code",
                hint_text="e.g. WELCOME2026",
                capitalization=ft.TextCapitalization.CHARACTERS,
                border_radius=10,
                focused_border_color=ft.Colors.PRIMARY,
                color=cur_p["text_primary"],
                label_style=ft.TextStyle(color=cur_p["text_muted"]),
                bgcolor=cur_p["card_bg_alt"],
                autofocus=True,
            )
            submit_btn = ft.ElevatedButton(
                "Redeem",
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.WHITE,
                    shape=ft.RoundedRectangleBorder(radius=10),
                ),
            )

            async def _do_redeem(ev=None):
                clean_c = (code_input.value or "").strip().upper()
                if not clean_c:
                    show_page_snackbar(page, "Please enter a promo code.")
                    return

                submit_btn.disabled = True
                submit_btn.content = ft.ProgressRing(width=16, height=16, stroke_width=2.5, color=ft.Colors.WHITE)
                page.update()

                tok = await AuthSession.for_page(page).get_access_token()
                if not tok and hasattr(page, "shared_preferences") and page.shared_preferences:
                    tok = await page.shared_preferences.get("auth_token")

                status_c, res_data = await redeem_promo_code_api(tok, clean_c)

                submit_btn.disabled = False
                submit_btn.content = ft.Text("Redeem")

                if status_c == 200:
                    if dlg_box[0]:
                        dlg_box[0].open = False
                        page.update()
                    rewards = res_data.get("rewards", {})
                    coins_g = rewards.get("coins", 0)
                    trial_g = rewards.get("trial", {}).get("trial_days") if rewards.get("trial") else None
                    msg_txt = f"🎉 Successfully redeemed {clean_c}!"
                    if coins_g:
                        msg_txt += f" (+{coins_g} Nu-Coins)"
                    if trial_g:
                        msg_txt += f" (+{trial_g}d Pro Trial)"
                    badge_info = rewards.get("badge")
                    if badge_info and isinstance(badge_info, dict):
                        msg_txt += f" Unlocked '{badge_info.get('name')}' badge!"
                    show_page_snackbar(page, msg_txt)
                    # Refresh badges shelf
                    page.run_task(load_badges)
                else:
                    err_msg = res_data.get("detail") if isinstance(res_data, dict) else "Could not redeem code."
                    show_page_snackbar(page, f"Redemption failed: {err_msg}")
                page.update()

            submit_btn.on_click = lambda ev: page.run_task(_do_redeem, ev)

            def _close_dlg(ev=None):
                if dlg_box[0]:
                    dlg_box[0].open = False
                    page.update()

            dlg = ft.AlertDialog(
                bgcolor=cur_p["card_bg"],
                title=ft.Row([
                    ft.Icon(ft.Icons.CARD_GIFTCARD_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                    ft.Text("Redeem Promo Code", size=16, weight=ft.FontWeight.BOLD, color=cur_p["text_primary"]),
                ], spacing=8),
                content=ft.Column([
                    ft.Text("Enter your voucher code or campus ambassador discount code:", size=12, color=cur_p["text_muted"]),
                    ft.Container(height=6),
                    code_input,
                ], tight=True, spacing=6),
                actions=[
                    ft.TextButton("Cancel", on_click=_close_dlg),
                    submit_btn,
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                shape=ft.RoundedRectangleBorder(radius=16),
            )
            dlg_box[0] = dlg
            if dlg not in page.overlay:
                page.overlay.append(dlg)
            dlg.open = True
            page.update()

        promo_redeem_card = ft.Container(
            ink=True,
            on_click=lambda e: page.run_task(_open_redeem_promo_modal, e),
            border_radius=18,
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)),
            bgcolor=palette["card_bg"],
            padding=ft.Padding.all(16),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
            content=ft.Row([
                ft.Container(
                    width=42, height=42, border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.CONFIRMATION_NUMBER_ROUNDED, color=ft.Colors.PRIMARY, size=22)
                ),
                ft.Column([
                    promo_title,
                    promo_sub,
                ], spacing=3, expand=True),
                ft.ElevatedButton(
                    content=ft.Row([
                        ft.Text("Redeem", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                        ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=13, color=ft.Colors.WHITE),
                    ], tight=True, spacing=4),
                    bgcolor=ft.Colors.PRIMARY,
                    height=34,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                    on_click=lambda e: page.run_task(_open_redeem_promo_modal, e),
                )
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)
        )

        # ── 8. Glossy Badges & Honors Shelf ───────────────────────────────────
        badges_shelf_col = ft.Column(spacing=8)
        badges_registry = []

        async def load_badges():
            badges_registry.clear()
            cur_p = get_profile_palette(_is_dark_mode(page))
            tok = await AuthSession.for_page(page).get_access_token()
            if not tok and hasattr(page, "shared_preferences") and page.shared_preferences:
                tok = await page.shared_preferences.get("auth_token")
            if not tok:
                return
            st_code, b_list = await get_my_badges_api(tok)
            if not isinstance(b_list, list) or not b_list:
                empty_icon = ft.Icon(ft.Icons.MILITARY_TECH_ROUNDED, size=20, color=cur_p["text_muted"])
                empty_text = ft.Text("Redeem promo codes, complete learning objectives, or hit study streaks to unlock exclusive badges!", size=11.5, color=cur_p["text_muted"], expand=True)
                empty_box = ft.Container(
                    padding=ft.Padding.all(14),
                    border_radius=14,
                    bgcolor=cur_p["card_bg_alt"],
                    border=ft.Border.all(1, cur_p["border_clr"]),
                    content=ft.Row([
                        empty_icon,
                        empty_text,
                    ], spacing=10)
                )
                badges_registry.append({
                    "type": "empty",
                    "box": empty_box,
                    "icon": empty_icon,
                    "text": empty_text,
                })
                badges_shelf_col.controls = [empty_box]
                page.update()
                return

            badge_tiles = []
            for b in b_list:
                b_id = b.get("id")
                b_name = b.get("name") or "Learner"
                b_color = b.get("color_hex") or "#4CAF50"
                b_desc = b.get("description") or ""
                b_is_pri = b.get("is_primary", False)
                b_icon_str = str(b.get("icon") or "STAR_ROUNDED").upper()
                b_icon_data = getattr(ft.Icons, b_icon_str, ft.Icons.STAR_ROUNDED)

                async def _equip_badge(ev=None, badge_target=None, badge_name=None):
                    if isinstance(badge_target, dict):
                        target_dict = badge_target
                    else:
                        t_id = str(badge_target or b_id)
                        target_dict = next((item for item in b_list if str(item.get("id")) == t_id), None)
                        if not target_dict:
                            target_dict = {"id": t_id, "name": badge_name or b_name, "color_hex": b_color, "icon": b_icon_str}

                    target_id = target_dict.get("id")
                    target_display_name = target_dict.get("name") or "Badge"

                    tok_now = await AuthSession.for_page(page).get_access_token()
                    if not tok_now and hasattr(page, "shared_preferences") and page.shared_preferences:
                        tok_now = await page.shared_preferences.get("auth_token")
                    st, res = await equip_primary_badge_api(tok_now, target_id)
                    if st == 200:
                        show_page_snackbar(page, f"Equipped '{target_display_name}' as your primary badge!")

                        # Instantly animate and swap the badge pill next to the name
                        if name_badge_container:
                            try:
                                # 1. Smoothly pop out / scale down
                                name_badge_container.scale = 0.25
                                name_badge_container.opacity = 0.0
                                name_badge_container.update()
                                await asyncio.sleep(0.14)

                                # 2. Swap in the newly equipped badge pill
                                new_badge_dict = dict(target_dict)
                                new_badge_dict["is_primary"] = True
                                user_data["primary_badge"] = new_badge_dict
                                name_badge_container.content = build_glossy_badge_pill(
                                    new_badge_dict, is_mobile=False, max_width=140, max_chars=16
                                )
                                name_badge_container.visible = True

                                # 3. Pop and bounce back in with spring animation
                                name_badge_container.scale = 1.0
                                name_badge_container.opacity = 1.0
                                name_badge_container.update()
                            except Exception:
                                pass

                        # Reload badges shelf to reflect new primary status
                        page.run_task(load_badges)
                    else:
                        show_page_snackbar(page, "Failed to equip badge.")

                action_widget = ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=13, color=ft.Colors.GREEN_400),
                        ft.Text("EQUIPPED", size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.GREEN_400)
                    ], spacing=3, tight=True),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_400),
                    border=ft.Border.all(0.8, ft.Colors.with_opacity(0.3, ft.Colors.GREEN_400)),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                ) if b_is_pri else ft.TextButton(
                    "Equip",
                    style=ft.ButtonStyle(
                        color=cur_p["text_primary"],
                        shape=ft.RoundedRectangleBorder(radius=6),
                    ),
                    on_click=lambda ev, cur_dict=b: page.run_task(_equip_badge, ev, cur_dict)
                )

                b_title = ft.Text(b_name, size=12.5, weight=ft.FontWeight.W_800, color=cur_p["text_primary"])
                b_desc_ctrl = ft.Text(b_desc, size=10.5, color=cur_p["text_muted"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)

                card = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=14,
                    bgcolor=cur_p["card_bg"],
                    border=ft.Border.all(1.2, ft.Colors.with_opacity(0.4 if b_is_pri else 0.15, b_color)),
                    shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.12 if b_is_pri else 0.04, b_color), offset=ft.Offset(0, 2)),
                    content=ft.Row([
                        ft.Container(
                            width=36, height=36, border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.14, b_color),
                            border=ft.Border.all(0.8, ft.Colors.with_opacity(0.3, b_color)),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(b_icon_data, size=18, color=b_color),
                        ),
                        ft.Column([
                            ft.Row([
                                b_title,
                                ft.Container(
                                    content=ft.Text("BADGE", size=8.5, weight=ft.FontWeight.W_800, color=b_color),
                                    bgcolor=ft.Colors.with_opacity(0.12, b_color),
                                    padding=ft.Padding.symmetric(horizontal=5, vertical=1.5),
                                    border_radius=4,
                                ),
                            ], spacing=6, tight=True),
                            b_desc_ctrl,
                        ], spacing=2, expand=True),
                        action_widget,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
                )
                badges_registry.append({
                    "type": "card",
                    "box": card,
                    "title": b_title,
                    "desc": b_desc_ctrl,
                    "action": action_widget,
                })
                badge_tiles.append(card)

            badges_shelf_col.controls = badge_tiles
            page.update()

        badges_shelf_card = ft.Container(
            content=badges_shelf_col,
            padding=ft.Padding.only(bottom=4),
        )
        page.run_task(load_badges)

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
            if theme_switch.value != dark:
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

            # 6. Update Admin Card text
            admin_title.color = p["text_primary"]
            admin_sub.color = p["text_muted"]

            # 7. Update Security Card
            security_card.bgcolor = p["card_bg"]
            security_card.border = ft.Border.all(1, p["border_clr"])
            security_title.color = p["text_primary"]
            security_sub.color = p["text_muted"]

            # 8. Update Store & Billing Card
            store_billing_card.bgcolor = p["card_bg"]
            store_title.color = p["text_primary"]
            store_sub.color = p["text_muted"]

            # 9. Update Promo Redeem Card
            promo_redeem_card.bgcolor = p["card_bg"]
            promo_title.color = p["text_primary"]
            promo_sub.color = p["text_muted"]

            # 10. Update Badges Shelf
            for b_item in badges_registry:
                if b_item.get("type") == "card":
                    b_item["box"].bgcolor = p["card_bg"]
                    b_item["title"].color = p["text_primary"]
                    b_item["desc"].color = p["text_muted"]
                    act = b_item.get("action")
                    if isinstance(act, ft.TextButton) and hasattr(act, "style") and act.style:
                        act.style = ft.ButtonStyle(
                            color=p["text_primary"],
                            shape=ft.RoundedRectangleBorder(radius=6),
                        )
                elif b_item.get("type") == "empty":
                    b_item["box"].bgcolor = p["card_bg_alt"]
                    b_item["box"].border = ft.Border.all(1, p["border_clr"])
                    b_item["icon"].color = p["text_muted"]
                    b_item["text"].color = p["text_muted"]

        # Super Admin Control Plane Access Card (Locked by default, verified via credentials)
        admin_title = ft.Text("Platform Super Admin Panel", size=13, weight=ft.FontWeight.BOLD, color=palette["text_primary"])
        admin_sub = ft.Text("User management, Excel export, bulk messaging & platform analytics.", size=11, color=palette["text_muted"])
        admin_card = ft.Container(
            ink=True,
            on_click=lambda _: page.go("/platform-admin"),
            border_radius=16,
            border=ft.Border.all(1.2, ft.Colors.AMBER_400),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_500),
            padding=ft.Padding.all(16),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.1, ft.Colors.AMBER_700), offset=ft.Offset(0, 3)),
            content=ft.Row([
                ft.Container(
                    width=42, height=42, border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.AMBER_500),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED, color=ft.Colors.AMBER_500, size=22)
                ),
                ft.Column([
                    ft.Row([
                        admin_title,
                        ft.Container(
                            content=ft.Text("RESTRICTED", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_500),
                            bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER_500),
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            border_radius=4,
                        ),
                    ], spacing=6, tight=True),
                    admin_sub
                ], spacing=2, expand=True),
                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=ft.Colors.AMBER_500, size=20)
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)
        )

        # ── Security & Sessions Card ──────────────────────────────────────────
        security_title = ft.Text("Log Out All Devices", size=13, weight=ft.FontWeight.BOLD, color=palette["text_primary"])
        security_sub = ft.Text("Revoke active sessions and sign out across all browsers and devices.", size=11, color=palette["text_muted"])
        security_card = ft.Container(
            ink=True,
            on_click=handle_logout_all_click,
            border_radius=16,
            border=ft.Border.all(1, palette["border_clr"]),
            bgcolor=palette["card_bg"],
            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
            content=ft.Row([
                ft.Container(
                    width=38, height=38, border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED_400),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.DEVICES_ROUNDED, color=ft.Colors.RED_400, size=18)
                ),
                ft.Column([
                    security_title,
                    security_sub
                ], spacing=2, expand=True),
                ft.Container(
                    content=ft.Row([
                        ft.Text("Log Out All", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.RED_400),
                        ft.Icon(ft.Icons.LOGOUT_ROUNDED, color=ft.Colors.RED_400, size=14),
                    ], spacing=4, tight=True),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.RED_400),
                )
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)
        )

        # ── Content Assembly ──────────────────────────────────────────────────
        is_super_admin = _is_platform_super_admin(username, email)

        content_items = [
            referral_card,
            ft.Container(height=4),
            promo_redeem_card,
            ft.Container(height=4),
            ft.Column([section_heading("Honors & Badges", ft.Icons.MILITARY_TECH_ROUNDED), badges_shelf_card], spacing=10),
            ft.Container(height=4),
            ft.Column([section_heading("Learning Momentum", ft.Icons.QUERY_STATS_ROUNDED), stats_layout], spacing=10),
            ft.Container(height=4),
            ft.Column([section_heading("Learning Plan & Store", ft.Icons.STOREFRONT_ROUNDED), store_billing_card], spacing=10),
            ft.Container(height=4),
            ft.Column([section_heading("Quick Hub Shortcuts", ft.Icons.GRID_VIEW_ROUNDED), shortcuts_grid], spacing=10),
            ft.Container(height=4),
            ft.Column([section_heading("Account & Academic Details", ft.Icons.BADGE_ROUNDED), account_card], spacing=10),
            ft.Container(height=4),
            ft.Column([section_heading("Security & Sessions", ft.Icons.SECURITY_ROUNDED), security_card], spacing=10),
        ]

        if is_super_admin:
            content_items.extend([
                ft.Container(height=4),
                ft.Column([section_heading("Administration & Security", ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED), admin_card], spacing=10),
            ])

        content_items.extend([
            ft.Container(height=4),
            ft.Column([section_heading("System Settings", ft.Icons.TUNE_ROUNDED), theme_card], spacing=10),
            ft.Container(height=24),
        ])

        main_content = ft.Container(
            alignment=ft.Alignment.TOP_CENTER,
            content=ft.Container(
                width=min(page.width or 800, 780),
                padding=ft.Padding.symmetric(horizontal=16, vertical=20),
                content=ft.Column(content_items, spacing=18)
            )
        )

        content_socket.content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[
                hero_banner,
                main_content
            ]
        )
        try:
            content_socket.update()
        except Exception:
            try:
                page.update()
            except Exception:
                pass

    async def _safe_load_profile():
        try:
            await load_profile()
        except Exception as ex:
            print(f"[profile_view] Error executing load_profile: {ex!r}")
            content_socket.content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=24,
                content=ft.Column([
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.AMBER_400, size=48),
                    ft.Text("Could not load profile", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("Please check your connection and try again.", size=13, color=ft.Colors.GREY_500),
                    ft.ElevatedButton("Retry", on_click=lambda _: page.go("/profile")),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)
            )
            try:
                content_socket.update()
            except Exception:
                try:
                    page.update()
                except Exception:
                    pass

    page.run_task(_safe_load_profile)

    return ft.View(
        route="/profile",
        padding=0,
        bgcolor="#121212" if is_dark else ft.Colors.SURFACE,
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket
            )
        ]
    )