"""
Nu-Age Platform Super Admin Control Plane.
Provides global platform administration, user directory data table, cascading account deletion,
styled Excel spreadsheet exports, bulk email (Resend), and push notification broadcasts (Firebase FCM).
Protected by an admin lock-screen credential gate.
"""

import os
import sys
import tempfile
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import flet as ft

from src.requests.platform_admin import (
    verify_admin_credentials,
    get_platform_analytics,
    get_platform_users,
    update_user_attributes,
    delete_user_account,
    export_users_data,
    broadcast_bulk_push,
    get_platform_health,
)
from src.utils.file_opener import show_page_snackbar


def _open_file_locally(filepath: str):
    """Safely launches a downloaded file in the OS default viewer."""
    if not filepath or not os.path.exists(filepath):
        return
    try:
        if sys.platform == "win32" and hasattr(os, "startfile"):
            os.startfile(filepath)
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", filepath])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", filepath])
    except Exception as ex:
        print(f"[platform_admin] Could not open file: {ex}")


async def platform_admin_view(page: ft.Page) -> ft.View:
    """
    Constructs the Platform Super Admin View with lock-screen gate and full administrative suite.
    """
    # ── Theme & Palette System ──────────────────────────────────────────────────
    is_dark = page.theme_mode == ft.ThemeMode.DARK if hasattr(page, "theme_mode") else True

    palette = {
        "bg": "#0A0F1D" if is_dark else "#F8FAFC",
        "surface": "#111827" if is_dark else "#FFFFFF",
        "surface_variant": "#1E293B" if is_dark else "#F1F5F9",
        "card_bg": "#151F33" if is_dark else "#FFFFFF",
        "border": "#24324D" if is_dark else "#E2E8F0",
        "border_subtle": "#1B273F" if is_dark else "#F1F5F9",
        "text": "#F8FAFC" if is_dark else "#0F172A",
        "text_muted": "#94A3B8" if is_dark else "#64748B",
        "accent": "#F59E0B",        # Amber Gold
        "accent_glow": "#D97706",
        "primary": ft.Colors.PRIMARY,
        "danger": "#EF4444",
        "danger_bg": ft.Colors.with_opacity(0.12, "#EF4444"),
        "success": "#10B981",
        "success_bg": ft.Colors.with_opacity(0.12, "#10B981"),
        "info": "#0EA5E9",
        "info_bg": ft.Colors.with_opacity(0.12, "#0EA5E9"),
        "purple": "#8B5CF6",
    }

    # ── Admin Session State ──────────────────────────────────────────────────────
    admin_state = {
        "authenticated": False,
        "token": None,
        "admin_user": None,
        "active_tab": "overview",  # overview, users, broadcast, export
        "page_num": 1,
        "limit": 20,
        "total_users": 0,
        "total_pages": 1,
        "search_query": "",
        "filter_role": "all",
        "filter_verified": None,
        "sort_by": "created_desc",
        "cached_users": [],
        "cached_analytics": None,   # None = initial loading (show skeletons)
        "is_loading_analytics": False,
        "is_loading_users": False,
        "analytics_error": None,
        "users_error": None,
        "health_data": None,
        "is_exporting_excel": False,
        "is_exporting_csv": False,
    }

    # Check if page already has an elevated token in session
    session_store = getattr(page, "session", None)
    if session_store and hasattr(session_store, "store"):
        saved_admin_tok = session_store.store.get("platform_admin_token")
        saved_admin_user = session_store.store.get("platform_admin_user")
        if saved_admin_tok and saved_admin_user:
            admin_state["authenticated"] = True
            admin_state["token"] = saved_admin_tok
            admin_state["admin_user"] = saved_admin_user

    main_container = ft.Container(expand=True)
    nav_container = ft.Container()
    active_content_area = ft.Container(expand=True)
    telemetry_badge_text = ft.Text("Checking health...", size=11, color=palette["text_muted"])
    telemetry_dot = ft.Container(width=8, height=8, border_radius=4, bgcolor=palette["accent"])

    # ─────────────────────────────────────────────────────────────────────────
    # A. SKELETON LOADERS
    # ─────────────────────────────────────────────────────────────────────────

    def _skeleton_box(width: Optional[int] = None, height: int = 20, border_radius: int = 8, expand: bool = False) -> ft.Container:
        return ft.Container(
            width=width,
            height=height,
            expand=expand,
            border_radius=border_radius,
            bgcolor=palette["surface_variant"],
            animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
        )

    def _build_kpi_skeletons() -> ft.Control:
        kpi_items = []
        for _ in range(8):
            card = ft.Container(
                bgcolor=palette["card_bg"],
                border=ft.Border.all(1, palette["border"]),
                border_radius=14,
                padding=18,
                content=ft.Column(
                    spacing=10,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                _skeleton_box(width=90, height=14),
                                _skeleton_box(width=32, height=32, border_radius=8),
                            ],
                        ),
                        _skeleton_box(width=70, height=28),
                        _skeleton_box(width=110, height=12),
                    ],
                ),
            )
            kpi_items.append(card)

        return ft.Column(
            spacing=16,
            controls=[
                ft.ResponsiveRow(
                    spacing=12, run_spacing=12,
                    controls=[
                        ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=kpi_items[0]),
                        ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=kpi_items[1]),
                        ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=kpi_items[2]),
                        ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=kpi_items[3]),
                    ],
                ),
                ft.ResponsiveRow(
                    spacing=12, run_spacing=12,
                    controls=[
                        ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=kpi_items[4]),
                        ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=kpi_items[5]),
                        ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=kpi_items[6]),
                        ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=kpi_items[7]),
                    ],
                ),
            ],
        )

    def _build_user_table_skeletons() -> ft.Control:
        rows = []
        for _ in range(6):
            row = ft.Container(
                bgcolor=palette["card_bg"],
                border=ft.Border.all(1, palette["border_subtle"]),
                border_radius=10,
                padding=14,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row([
                            _skeleton_box(width=38, height=38, border_radius=19),
                            ft.Column([
                                _skeleton_box(width=140, height=14),
                                _skeleton_box(width=90, height=10),
                            ], spacing=4),
                        ], spacing=12),
                        _skeleton_box(width=120, height=12),
                        _skeleton_box(width=70, height=22, border_radius=6),
                        _skeleton_box(width=80, height=22, border_radius=6),
                        _skeleton_box(width=50, height=14),
                        _skeleton_box(width=32, height=32, border_radius=8),
                    ],
                ),
            )
            rows.append(row)
        return ft.Column(spacing=8, controls=rows)

    # ─────────────────────────────────────────────────────────────────────────
    # B. DATA FETCHERS & API SYNCHRONIZATION
    # ─────────────────────────────────────────────────────────────────────────

    async def _fetch_analytics():
        if not admin_state["token"]:
            return
        admin_state["is_loading_analytics"] = True
        admin_state["analytics_error"] = None
        if admin_state["active_tab"] == "overview":
            _render_tab_content()
            page.update()

        status_code, data = await get_platform_analytics(admin_state["token"])
        admin_state["is_loading_analytics"] = False

        if status_code == 200:
            admin_state["cached_analytics"] = data
            admin_state["total_users"] = data.get("total_users", admin_state["total_users"])
            # Also update nav badge
            nav_container.content = _build_nav_bar()
        else:
            admin_state["analytics_error"] = data.get("detail", f"Error {status_code} fetching platform metrics.")

        if admin_state["active_tab"] == "overview":
            _render_tab_content()
        page.update()

    async def _fetch_health():
        if not admin_state["token"]:
            return
        status_code, data = await get_platform_health(admin_state["token"])
        if status_code == 200:
            admin_state["health_data"] = data
            ms = data.get("database_latency_ms", "—")
            telemetry_badge_text.value = f"DB: {ms}ms | {data.get('database_status', 'healthy')}"
            telemetry_dot.bgcolor = palette["success"] if data.get("database_status") == "healthy" else palette["danger"]
        else:
            telemetry_badge_text.value = "DB: Offline"
            telemetry_dot.bgcolor = palette["danger"]
        page.update()

    _users_tab_cache = {"view": None, "roster": None, "pagination": None, "kpi_row": None}

    def _refresh_users_roster_ui():
        # Forward declaration stub, implemented in Tab 2
        pass

    async def _fetch_users():
        if not admin_state["token"]:
            return
        admin_state["is_loading_users"] = True
        admin_state["users_error"] = None
        if "search_spinner" in locals() or "search_spinner" in globals():
            try:
                search_spinner.visible = True
            except Exception:
                pass
        if admin_state["active_tab"] == "users":
            _refresh_users_roster_ui()
            page.update()

        status_code, data = await get_platform_users(
            token=admin_state["token"],
            q=admin_state["search_query"],
            role=admin_state["filter_role"],
            is_verified=admin_state["filter_verified"],
            page=admin_state["page_num"],
            limit=admin_state["limit"],
            sort_by=admin_state["sort_by"],
        )
        admin_state["is_loading_users"] = False
        if "search_spinner" in locals() or "search_spinner" in globals():
            try:
                search_spinner.visible = False
            except Exception:
                pass

        if status_code == 200:
            admin_state["cached_users"] = data.get("items", [])
            admin_state["total_pages"] = max(1, data.get("total_pages", 1))
            admin_state["total_users"] = data.get("total", admin_state["total_users"])
            nav_container.content = _build_nav_bar()
        else:
            admin_state["users_error"] = data.get("detail", f"Error {status_code} loading users.")

        if admin_state["active_tab"] == "users":
            _refresh_users_roster_ui()
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # C. LOCK-SCREEN GATE (UNAUTHENTICATED)
    # ─────────────────────────────────────────────────────────────────────────

    username_input = ft.TextField(
        label="Master Username or Email",
        hint_text="e.g. nu-admin or admin@nu-age.name.ng",
        prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        text_style=ft.TextStyle(size=14, color=palette["text"]),
        autofocus=True,
    )

    password_input = ft.TextField(
        label="Master Password",
        password=True,
        can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        text_style=ft.TextStyle(size=14, color=palette["text"]),
    )

    login_error_text = ft.Text("", size=12, color=palette["danger"], visible=False)
    login_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.WHITE, visible=False)
    login_btn_text = ft.Text("Authenticate & Unlock", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)

    async def _on_unlock_click(e=None):
        u = username_input.value.strip() if username_input.value else ""
        p = password_input.value if password_input.value else ""
        if not u or not p:
            login_error_text.value = "Please enter both username and password."
            login_error_text.visible = True
            page.update()
            return

        login_error_text.visible = False
        login_spinner.visible = True
        login_btn_text.value = "Authenticating..."
        page.update()

        status_code, data = await verify_admin_credentials(u, p)
        login_spinner.visible = False
        login_btn_text.value = "Authenticate & Unlock"

        if status_code == 200 and data.get("access_token"):
            admin_state["authenticated"] = True
            admin_state["token"] = data["access_token"]
            admin_state["admin_user"] = data
            if session_store and hasattr(session_store, "store"):
                session_store.store.set("platform_admin_token", data["access_token"])
                session_store.store.set("platform_admin_user", data)

            show_page_snackbar(
                page,
                ft.SnackBar(
                    content=ft.Row([
                        ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text(f"Welcome, {data.get('name', 'Admin')}! Super-Admin Mode Unlocked.", size=13, color=ft.Colors.WHITE),
                    ], spacing=8),
                    bgcolor=ft.Colors.GREEN_700,
                    duration=3000,
                )
            )
            _render_dashboard()
            page.update()
            # Immediately trigger data fetches
            page.run_task(_fetch_analytics)
            page.run_task(_fetch_health)
            page.run_task(_fetch_users)
        else:
            err = data.get("detail", "Access denied. Invalid administrator credentials.")
            login_error_text.value = str(err)
            login_error_text.visible = True
            page.update()

    def _build_lock_screen() -> ft.Control:
        card = ft.Container(
            width=min(440, max(300, (page.width or 400) - 32)),
            bgcolor=palette["surface"],
            border=ft.Border.all(1.2, palette["border"]),
            border_radius=22,
            padding=ft.Padding.symmetric(horizontal=28, vertical=36),
            shadow=ft.BoxShadow(
                blur_radius=30,
                color=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
                offset=ft.Offset(0, 12),
            ),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
                controls=[
                    ft.Container(
                        width=68,
                        height=68,
                        border_radius=34,
                        bgcolor=ft.Colors.with_opacity(0.15, palette["accent"]),
                        border=ft.Border.all(1.5, palette["accent"]),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED, size=34, color=palette["accent"]),
                    ),
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                        controls=[
                            ft.Text("Nu-Age Control Plane", size=22, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ft.Text("Platform Super Administrator Portal", size=12, color=palette["text_muted"]),
                        ],
                    ),
                    ft.Divider(color=palette["border"], height=12),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.LOCK_ROUNDED, size=14, color=palette["accent"]),
                            ft.Text(
                                "Enter your master credentials to unlock global platform governance.",
                                size=11,
                                color=palette["text_muted"],
                                expand=True,
                            ),
                        ], spacing=8),
                        bgcolor=palette["surface_variant"],
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        border_radius=8,
                    ),
                    username_input,
                    password_input,
                    login_error_text,
                    ft.FilledButton(
                        content=ft.Row(
                            [login_spinner, login_btn_text],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=8,
                            tight=True,
                        ),
                        style=ft.ButtonStyle(
                            bgcolor=palette["accent_glow"],
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=ft.Padding.symmetric(vertical=14),
                        ),
                        width=400,
                        on_click=_on_unlock_click,
                    ),
                    ft.TextButton(
                        "← Return to App Dashboard",
                        style=ft.ButtonStyle(color=palette["text_muted"]),
                        on_click=lambda e: page.go("/dashboard"),
                    ),
                ],
            ),
        )

        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            padding=16,
            content=card,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # D. NAVIGATION & SESSION CONTROLS
    # ─────────────────────────────────────────────────────────────────────────

    def _lock_admin_session(e=None):
        admin_state["authenticated"] = False
        admin_state["token"] = None
        admin_state["admin_user"] = None
        if session_store and hasattr(session_store, "store"):
            store = session_store.store
            if hasattr(store, "remove"):
                try:
                    store.remove("platform_admin_token")
                except Exception:
                    pass
                try:
                    store.remove("platform_admin_user")
                except Exception:
                    pass
            elif hasattr(store, "pop"):
                store.pop("platform_admin_token", None)
                store.pop("platform_admin_user", None)
        _render_dashboard()
        page.update()

    def _switch_tab(tab_name: str):
        admin_state["active_tab"] = tab_name
        nav_container.content = _build_nav_bar()
        _render_tab_content()
        page.update()
        if tab_name == "users" and (not admin_state["cached_users"] or admin_state["users_error"]):
            page.run_task(_fetch_users)
        elif tab_name == "overview" and (admin_state["cached_analytics"] is None or admin_state["analytics_error"]):
            page.run_task(_fetch_analytics)
            page.run_task(_fetch_health)

    def _build_nav_bar() -> ft.Control:
        nav_buttons = [
            ("overview", "Overview", ft.Icons.DASHBOARD_ROUNDED, None),
            ("users", "User Directory", ft.Icons.PEOPLE_ROUNDED, admin_state["total_users"] if admin_state["total_users"] > 0 else None),
            ("broadcast", "Push Broadcasts", ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED, None),
            ("export", "Export Center", ft.Icons.DOWNLOAD_ROUNDED, None),
        ]

        nav_controls = []
        for tab_key, label, ic, count_badge in nav_buttons:
            is_active = (admin_state["active_tab"] == tab_key)
            badge_control = None
            if count_badge is not None:
                badge_control = ft.Container(
                    content=ft.Text(f"{count_badge:,}", size=10, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    bgcolor=palette["surface_variant"] if not is_active else ft.Colors.with_opacity(0.3, palette["accent"]),
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=10,
                )

            row_items = [
                ft.Icon(ic, size=16, color=palette["accent"] if is_active else palette["text_muted"]),
                ft.Text(label, size=13, weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500, color=palette["text"] if is_active else palette["text_muted"]),
            ]
            if badge_control:
                row_items.append(badge_control)

            nav_controls.append(
                ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.16, palette["accent"]) if is_active else ft.Colors.TRANSPARENT,
                    border=ft.Border.all(1.2, palette["accent"] if is_active else palette["border"]),
                    border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                    ink=True,
                    on_click=lambda e, k=tab_key: _switch_tab(k),
                    content=ft.Row(row_items, spacing=8, tight=True),
                )
            )

        return ft.Container(
            content=ft.Row(
                scroll=ft.ScrollMode.HIDDEN,
                spacing=10,
                controls=nav_controls,
            ),
            padding=ft.Padding.symmetric(vertical=4),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # E. TAB 1: OVERVIEW & TELEMETRY
    # ─────────────────────────────────────────────────────────────────────────

    def _build_overview_tab() -> ft.Control:
        if admin_state["cached_analytics"] is None and admin_state["is_loading_analytics"]:
            return ft.Column([
                _build_kpi_skeletons(),
            ], expand=True, spacing=16)

        if admin_state["analytics_error"]:
            return ft.Container(
                bgcolor=palette["danger_bg"],
                border=ft.Border.all(1, palette["danger"]),
                border_radius=14,
                padding=24,
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.CLOUD_OFF_ROUNDED, color=palette["danger"], size=24),
                        ft.Text("Failed to Load Platform Telemetry", size=16, weight=ft.FontWeight.BOLD, color=palette["danger"]),
                    ], spacing=10),
                    ft.Text(str(admin_state["analytics_error"]), size=13, color=palette["text"]),
                    ft.FilledButton(
                        "Retry Telemetry Fetch",
                        icon=ft.Icons.REFRESH_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=palette["danger"], color=ft.Colors.WHITE),
                        on_click=lambda e: page.run_task(_fetch_analytics),
                    ),
                ], spacing=12),
            )

        stats = admin_state["cached_analytics"] or {}

        def _stat_box(title: str, val: Any, subtitle: str, icon, color):
            return ft.Container(
                bgcolor=palette["card_bg"],
                border=ft.Border.all(1, palette["border"]),
                border_radius=14,
                padding=18,
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(title, size=12, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                ft.Container(
                                    content=ft.Icon(icon, size=18, color=color),
                                    bgcolor=ft.Colors.with_opacity(0.12, color),
                                    padding=7,
                                    border_radius=8,
                                ),
                            ],
                        ),
                        ft.Text(f"{val:,}" if isinstance(val, (int, float)) else str(val or 0), size=26, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text(subtitle, size=11, color=palette["text_muted"]),
                    ],
                ),
            )

        total_u = stats.get("total_users", 0)
        tot_students = stats.get("total_students", 0)
        tot_teachers = stats.get("total_teachers", 0)
        tot_admins = stats.get("total_admins", 0)
        verified_u = stats.get("verified_users", 0)
        unverified_u = stats.get("unverified_users", 0)
        pct_verified = f"{round((verified_u / total_u) * 100, 1)}%" if total_u > 0 else "0%"

        row_1 = ft.ResponsiveRow(
            spacing=12, run_spacing=12,
            controls=[
                ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=_stat_box("Total Registered Users", total_u, "All-time accounts", ft.Icons.PEOPLE_ROUNDED, palette["info"])),
                ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=_stat_box("Active Learners", stats.get("active_this_week", 0), f"{stats.get('active_today', 0)} active today", ft.Icons.BOLT_ROUNDED, palette["accent"])),
                ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=_stat_box("Verified Accounts", verified_u, f"{pct_verified} trust rating", ft.Icons.VERIFIED_ROUNDED, palette["success"])),
                ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=_stat_box("Pending Verification", unverified_u, "Action required", ft.Icons.MARK_EMAIL_UNREAD_ROUNDED, palette["danger"])),
            ],
        )

        row_2 = ft.ResponsiveRow(
            spacing=12, run_spacing=12,
            controls=[
                ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=_stat_box("Students Enrolled", tot_students, "Active student profiles", ft.Icons.SCHOOL_ROUNDED, "#06B6D4")),
                ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=_stat_box("Faculty & Teachers", tot_teachers, "Instructors with courses", ft.Icons.PERSON_PIN_ROUNDED, palette["purple"])),
                ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=_stat_box("Published Courses", stats.get("total_courses", 0), f"{stats.get('total_organisations', 0)} organisations", ft.Icons.AUTO_STORIES_ROUNDED, palette["success"])),
                ft.Container(col={"xs": 12, "sm": 6, "md": 3}, content=_stat_box("Student Enrollments", stats.get("total_enrollments", 0), "Course memberships", ft.Icons.CARD_MEMBERSHIP_ROUNDED, palette["accent"])),
            ],
        )

        # Role Distribution Bar
        st_pct = (tot_students / total_u) if total_u > 0 else 0
        te_pct = (tot_teachers / total_u) if total_u > 0 else 0
        ad_pct = (tot_admins / total_u) if total_u > 0 else 0

        role_breakdown = ft.Container(
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=20,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.PIE_CHART_ROUNDED, size=18, color=palette["accent"]),
                        ft.Text("Platform User Distribution", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ], spacing=8),
                    # Segmented Progress Bar
                    ft.Container(
                        height=10,
                        border_radius=5,
                        bgcolor=palette["surface_variant"],
                        content=ft.Row(
                            spacing=2,
                            controls=[
                                ft.Container(expand=int(st_pct * 100) or 1, bgcolor="#06B6D4", border_radius=ft.BorderRadius.only(top_left=5, bottom_left=5)),
                                ft.Container(expand=int(te_pct * 100) or 1, bgcolor=palette["purple"]),
                                ft.Container(expand=int(ad_pct * 100) or 1, bgcolor=palette["accent"], border_radius=ft.BorderRadius.only(top_right=5, bottom_right=5)),
                            ],
                        ),
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_AROUND,
                        controls=[
                            ft.Row([ft.Container(width=10, height=10, border_radius=5, bgcolor="#06B6D4"), ft.Text(f"Students: {tot_students:,} ({round(st_pct*100, 1)}%)", size=12, color=palette["text_muted"])], spacing=6),
                            ft.Row([ft.Container(width=10, height=10, border_radius=5, bgcolor=palette["purple"]), ft.Text(f"Teachers: {tot_teachers:,} ({round(te_pct*100, 1)}%)", size=12, color=palette["text_muted"])], spacing=6),
                            ft.Row([ft.Container(width=10, height=10, border_radius=5, bgcolor=palette["accent"]), ft.Text(f"Admins: {tot_admins:,} ({round(ad_pct*100, 1)}%)", size=12, color=palette["text_muted"])], spacing=6),
                        ],
                    ),
                ],
            ),
        )

        # Quick Actions Card
        quick_actions = ft.Container(
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=20,
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Text("Administrative Shortcuts", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ft.Row(
                        wrap=True, spacing=10,
                        controls=[
                            ft.FilledButton("Browse User Directory", icon=ft.Icons.PERSON_SEARCH_ROUNDED, style=ft.ButtonStyle(bgcolor=palette["surface_variant"], color=palette["text"], shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: _switch_tab("users")),
                            ft.FilledButton("Download User Audit (.xlsx)", icon=ft.Icons.FILE_DOWNLOAD_ROUNDED, style=ft.ButtonStyle(bgcolor=palette["surface_variant"], color=palette["text"], shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: _switch_tab("export")),
                            ft.FilledButton("Draft Announcement", icon=ft.Icons.CAMPAIGN_ROUNDED, style=ft.ButtonStyle(bgcolor=palette["surface_variant"], color=palette["text"], shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: _switch_tab("broadcast")),
                        ],
                    ),
                ],
            ),
        )

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=16,
            controls=[
                row_1,
                row_2,
                role_breakdown,
                quick_actions,
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # F. TAB 2: USER DIRECTORY DATA TABLE
    # ─────────────────────────────────────────────────────────────────────────

    search_box = ft.TextField(
        hint_text="Search by name, username, email, university...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        border_radius=8,
        dense=True,
        border_color=palette["border"],
        text_style=ft.TextStyle(size=13, color=palette["text"]),
    )

    search_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2.5, color=palette["accent"], visible=False)
    clear_search_btn = ft.IconButton(
        icon=ft.Icons.CLEAR_ROUNDED,
        icon_size=16,
        tooltip="Clear search",
        visible=False,
    )

    role_dropdown = ft.Dropdown(
        width=135,
        label="Role",
        value="all",
        border_color=palette["border"],
        options=[
            ft.dropdown.Option("all", "All Roles"),
            ft.dropdown.Option("Student", "Students"),
            ft.dropdown.Option("Teacher", "Teachers"),
            ft.dropdown.Option("Admin", "Admins"),
        ],
    )

    verified_dropdown = ft.Dropdown(
        width=135,
        label="Verification",
        value="all",
        border_color=palette["border"],
        options=[
            ft.dropdown.Option("all", "All Accounts"),
            ft.dropdown.Option("true", "Verified"),
            ft.dropdown.Option("false", "Unverified"),
        ],
    )

    sort_dropdown = ft.Dropdown(
        width=150,
        label="Sort By",
        value="created_desc",
        border_color=palette["border"],
        options=[
            ft.dropdown.Option("created_desc", "Newest First"),
            ft.dropdown.Option("created_asc", "Oldest First"),
            ft.dropdown.Option("streak_desc", "Streak (High-Low)"),
            ft.dropdown.Option("name_asc", "Name (A-Z)"),
        ],
    )

    search_debounce_task: Optional[asyncio.Task] = None

    async def _on_filter_apply(e=None):
        nonlocal search_debounce_task
        if search_debounce_task and not search_debounce_task.done():
            search_debounce_task.cancel()
        admin_state["search_query"] = search_box.value.strip() if search_box.value else ""
        r_val = role_dropdown.value
        admin_state["filter_role"] = r_val if r_val != "all" else None
        v_val = verified_dropdown.value
        if v_val == "true":
            admin_state["filter_verified"] = True
        elif v_val == "false":
            admin_state["filter_verified"] = False
        else:
            admin_state["filter_verified"] = None
        admin_state["sort_by"] = sort_dropdown.value or "created_desc"
        admin_state["page_num"] = 1
        await _fetch_users()

    async def _on_search_changed(e=None):
        nonlocal search_debounce_task
        q_val = search_box.value or ""
        clear_search_btn.visible = bool(q_val)
        search_spinner.visible = True
        page.update()

        if search_debounce_task and not search_debounce_task.done():
            search_debounce_task.cancel()

        async def _delayed_search():
            try:
                await asyncio.sleep(0.35)
                await _on_filter_apply()
            except asyncio.CancelledError:
                pass

        search_debounce_task = asyncio.create_task(_delayed_search())

    def _on_clear_search(e=None):
        nonlocal search_debounce_task
        if search_debounce_task and not search_debounce_task.done():
            search_debounce_task.cancel()
        search_box.value = ""
        clear_search_btn.visible = False
        page.update()
        page.run_task(_on_filter_apply)

    clear_search_btn.on_click = _on_clear_search
    search_box.on_change = lambda e: page.run_task(_on_search_changed)
    search_box.on_submit = lambda e: page.run_task(_on_filter_apply)
    role_dropdown.on_change = lambda e: page.run_task(_on_filter_apply)
    verified_dropdown.on_change = lambda e: page.run_task(_on_filter_apply)
    sort_dropdown.on_change = lambda e: page.run_task(_on_filter_apply)

    async def _toggle_verify(u: dict):
        new_val = not u.get("is_verified", False)
        status_code, _ = await update_user_attributes(admin_state["token"], str(u["id"]), is_verified=new_val)
        if status_code == 200:
            show_page_snackbar(
                page,
                ft.SnackBar(
                    content=ft.Text(f"@{u['username']} standing: {'Verified' if new_val else 'Unverified'}"),
                    bgcolor=ft.Colors.GREEN_700 if new_val else ft.Colors.AMBER_700,
                )
            )
            await _fetch_users()
            await _fetch_analytics()

    async def _change_role(u: dict, new_role: str):
        status_code, _ = await update_user_attributes(admin_state["token"], str(u["id"]), role=new_role)
        if status_code == 200:
            show_page_snackbar(
                page,
                ft.SnackBar(content=ft.Text(f"Updated role for @{u['username']} to: {new_role}"), bgcolor=ft.Colors.GREEN_700)
            )
            await _fetch_users()
            await _fetch_analytics()

    def _open_user_detail_modal(u: dict):
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.BADGE_ROUNDED, color=palette["accent"], size=22),
                ft.Text(f"Account Profile: @{u['username']}", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Row([
                            ft.CircleAvatar(
                                content=ft.Text((u.get("first_name", "U")[:1] + u.get("last_name", "N")[:1]).upper(), size=14, weight=ft.FontWeight.BOLD),
                                bgcolor=palette["surface_variant"], radius=24,
                            ),
                            ft.Column([
                                ft.Text(u.get("name") or u.get("username"), size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ft.Text(u.get("email") or "No email", size=12, color=palette["text_muted"]),
                            ], spacing=2),
                        ], spacing=12),
                        ft.Divider(color=palette["border"], height=8),
                        ft.Row([ft.Text("User ID:", size=11, color=palette["text_muted"]), ft.Text(str(u.get("id")), size=11, weight=ft.FontWeight.BOLD, selectable=True)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Role:", size=11, color=palette["text_muted"]), ft.Text(str(u.get("role")), size=11, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("University:", size=11, color=palette["text_muted"]), ft.Text(str(u.get("university") or "Not specified"), size=11, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Study Streak:", size=11, color=palette["text_muted"]), ft.Text(f"{u.get('streak', 0)} Days", size=11, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Enrolled Courses:", size=11, color=palette["text_muted"]), ft.Text(str(u.get("enrolled_courses_count", 0)), size=11, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Created Courses:", size=11, color=palette["text_muted"]), ft.Text(str(u.get("created_courses_count", 0)), size=11, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Joined Nu-Age:", size=11, color=palette["text_muted"]), ft.Text(str(u.get("created_at") or "—"), size=11)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Last Active:", size=11, color=palette["text_muted"]), ft.Text(str(u.get("last_login_date") or "—"), size=11)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda e: page.pop_dialog()),
            ],
        )
        page.show_dialog(dlg)

    def _open_delete_modal(u: dict):
        confirm_input = ft.TextField(
            label=f"Type '{u['username']}' to confirm",
            border_color=palette["danger"],
            text_style=ft.TextStyle(size=13),
        )
        delete_btn = ft.FilledButton(
            "Permanently Delete Account",
            style=ft.ButtonStyle(bgcolor=palette["danger"], color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=6)),
            disabled=True,
        )

        def _on_confirm_change(e):
            delete_btn.disabled = (confirm_input.value.strip() != u["username"])
            page.update()

        confirm_input.on_change = _on_confirm_change

        async def _execute_delete(e):
            page.pop_dialog()
            status_code, data = await delete_user_account(admin_state["token"], str(u["id"]))
            if status_code == 200:
                show_page_snackbar(
                    page,
                    ft.SnackBar(
                        content=ft.Row([
                            ft.Icon(ft.Icons.DELETE_FOREVER_ROUNDED, color=ft.Colors.WHITE, size=18),
                            ft.Text(f"Account '{u['username']}' permanently purged.", color=ft.Colors.WHITE),
                        ], spacing=8),
                        bgcolor=ft.Colors.RED_700,
                        duration=3500,
                    )
                )
                await _fetch_users()
                await _fetch_analytics()
            else:
                show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Failed to delete: {data.get('detail')}"), bgcolor=ft.Colors.RED_700))

        delete_btn.on_click = lambda e: page.run_task(_execute_delete)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=palette["danger"], size=22),
                ft.Text("Confirm Account Purge", size=16, weight=ft.FontWeight.BOLD, color=palette["danger"]),
            ], spacing=8),
            content=ft.Column(
                tight=True, spacing=12,
                controls=[
                    ft.Text(f"Are you sure you want to permanently delete user '{u['name']}' (@{u['username']})?", size=13, color=palette["text"]),
                    ft.Text("This will delete all their tokens, enrollments, and submissions. This action CANNOT be undone.", size=11, color=palette["text_muted"]),
                    confirm_input,
                ],
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                delete_btn,
            ],
        )
        page.show_dialog(dlg)

    def _build_kpi_pills(tot_u, tot_students, tot_teachers, tot_admins, tot_verified):
        return [
            ft.Container(
                content=ft.Row([
                    ft.Container(width=8, height=8, border_radius=4, bgcolor=palette["accent"]),
                    ft.Text(f"Total: {tot_u:,}", size=11, weight=ft.FontWeight.BOLD, color=palette["text"]),
                ], spacing=6, tight=True),
                bgcolor=palette["surface_variant"],
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=8,
            ),
            ft.Container(
                content=ft.Row([
                    ft.Container(width=8, height=8, border_radius=4, bgcolor="#06B6D4"),
                    ft.Text(f"Students: {tot_students:,}", size=11, weight=ft.FontWeight.BOLD, color=palette["text"]),
                ], spacing=6, tight=True),
                bgcolor=ft.Colors.with_opacity(0.12, "#06B6D4"),
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=8,
            ),
            ft.Container(
                content=ft.Row([
                    ft.Container(width=8, height=8, border_radius=4, bgcolor=palette["purple"]),
                    ft.Text(f"Teachers: {tot_teachers:,}", size=11, weight=ft.FontWeight.BOLD, color=palette["text"]),
                ], spacing=6, tight=True),
                bgcolor=ft.Colors.with_opacity(0.12, palette["purple"]),
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=8,
            ),
            ft.Container(
                content=ft.Row([
                    ft.Container(width=8, height=8, border_radius=4, bgcolor=palette["accent"]),
                    ft.Text(f"Admins: {tot_admins:,}", size=11, weight=ft.FontWeight.BOLD, color=palette["text"]),
                ], spacing=6, tight=True),
                bgcolor=ft.Colors.with_opacity(0.12, palette["accent"]),
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=8,
            ),
            ft.Container(
                content=ft.Row([
                    ft.Container(width=8, height=8, border_radius=4, bgcolor=palette["success"]),
                    ft.Text(f"Verified: {tot_verified:,}", size=11, weight=ft.FontWeight.BOLD, color=palette["text"]),
                ], spacing=6, tight=True),
                bgcolor=palette["success_bg"],
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=8,
            ),
        ]

    def _build_user_card(u: dict) -> ft.Control:
        r_str = str(u.get("role", "Student"))
        if r_str.lower() == "admin":
            r_color = palette["accent"]
            r_icon = ft.Icons.SHIELD_ROUNDED
        elif r_str.lower() == "teacher":
            r_color = palette["purple"]
            r_icon = ft.Icons.PSYCHOLOGY_ROUNDED
        else:
            r_color = "#06B6D4"
            r_icon = ft.Icons.SCHOOL_ROUNDED

        is_v = bool(u.get("is_verified", False))
        fn = u.get("first_name") or ""
        ln = u.get("last_name") or ""
        full_n = u.get("name") or f"{fn} {ln}".strip() or u.get("username", "Learner")
        user_handle = u.get("username", "user")
        user_email = u.get("email") or "No email registered"
        user_uni = u.get("university") or "Independent Learner"
        user_streak = u.get("streak", 0) or 0
        user_enrolled = u.get("enrolled_courses_count", 0) or 0
        created_at_str = str(u.get("created_at") or "—")[:10]

        monogram = ((fn[:1] if fn else "") + (ln[:1] if ln else "")).upper()
        if not monogram:
            monogram = user_handle[:2].upper() if user_handle else "NU"

        def _create_role_items(user_ref=u):
            items = []
            for target_role in ("Student", "Teacher", "Admin"):
                if target_role.lower() != str(user_ref.get("role", "")).lower():
                    items.append(
                        ft.PopupMenuItem(
                            content=ft.Row([
                                ft.Icon(ft.Icons.SWAP_HORIZ_ROUNDED, size=16),
                                ft.Text(f"Switch to {target_role}", size=12),
                            ], spacing=8),
                            on_click=lambda e, tr=target_role, ur=user_ref: page.run_task(_change_role, ur, tr),
                        )
                    )
            return items

        action_menu = ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT_ROUNDED,
            tooltip="Account Operations",
            items=[
                ft.PopupMenuItem(
                    content=ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=16, color=palette["info"]),
                        ft.Text("View Full Account Dossier", size=12),
                    ], spacing=8),
                    on_click=lambda e, ur=u: _open_user_detail_modal(ur),
                ),
                ft.PopupMenuItem(
                    content=ft.Row([
                        ft.Icon(ft.Icons.VERIFIED_ROUNDED if not is_v else ft.Icons.REMOVE_MODERATOR_ROUNDED, size=16, color=ft.Colors.GREEN_400 if not is_v else ft.Colors.AMBER_400),
                        ft.Text("Verify Standing" if not is_v else "Revoke Verification", size=12),
                    ], spacing=8),
                    on_click=lambda e, ur=u: page.run_task(_toggle_verify, ur),
                ),
                *_create_role_items(u),
                ft.PopupMenuItem(
                    content=ft.Row([
                        ft.Icon(ft.Icons.DELETE_FOREVER_ROUNDED, color=palette["danger"], size=16),
                        ft.Text("Purge Account", color=palette["danger"], size=12, weight=ft.FontWeight.BOLD),
                    ], spacing=8),
                    on_click=lambda e, ur=u: _open_delete_modal(ur),
                ),
            ],
        )

        if is_v:
            verify_badge = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=12, color=ft.Colors.WHITE),
                    ft.Text("Verified", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ], spacing=4, tight=True),
                bgcolor=ft.Colors.GREEN_700,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=6,
            )
        else:
            verify_badge = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.PENDING_OUTLINED, size=12, color=palette["text_muted"]),
                    ft.Text("Unverified", size=10, color=palette["text_muted"]),
                ], spacing=4, tight=True),
                bgcolor=palette["surface_variant"],
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=6,
            )

        role_badge = ft.Container(
            content=ft.Row([
                ft.Icon(r_icon, size=12, color=r_color),
                ft.Text(r_str.title(), size=10, weight=ft.FontWeight.BOLD, color=r_color),
            ], spacing=4, tight=True),
            bgcolor=ft.Colors.with_opacity(0.14, r_color),
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=6,
        )

        return ft.Container(
            col={"xs": 12, "sm": 12, "md": 6, "lg": 6, "xl": 4},
            bgcolor=palette["surface"],
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.24, r_color)),
            border_radius=16,
            padding=16,
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row([
                                ft.CircleAvatar(
                                    content=ft.Text(monogram, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    bgcolor=r_color,
                                    radius=22,
                                ),
                                ft.Column([
                                    ft.Row([
                                        ft.Container(
                                            content=ft.Text(full_n, size=14, weight=ft.FontWeight.BOLD, color=palette["text"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                            expand=True,
                                        ),
                                        role_badge,
                                    ], spacing=6),
                                    ft.Text(f"@{user_handle}", size=12, color=palette["text_muted"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ], spacing=2, expand=True),
                            ], spacing=10, expand=True),
                            ft.Row([
                                verify_badge,
                                action_menu,
                            ], spacing=4, tight=True),
                        ],
                    ),
                    ft.Divider(color=palette["border"], height=1),
                    ft.Row([
                        ft.Icon(ft.Icons.EMAIL_OUTLINED, size=14, color=palette["text_muted"]),
                        ft.Text(user_email, size=12, color=palette["text"], expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=6),
                    ft.Row([
                        ft.Icon(ft.Icons.ACCOUNT_BALANCE_OUTLINED, size=14, color=palette["text_muted"]),
                        ft.Text(user_uni, size=11, color=palette["text_muted"], expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=6),
                    ft.Row(
                        wrap=True,
                        spacing=6,
                        controls=[
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, size=13, color=palette["accent"]),
                                    ft.Text(f"{user_streak}d Streak", size=10, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                                ], spacing=3, tight=True),
                                bgcolor=ft.Colors.with_opacity(0.12, palette["accent"]),
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=6,
                            ),
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=13, color=palette["info"]),
                                    ft.Text(f"{user_enrolled} Courses", size=10, weight=ft.FontWeight.BOLD, color=palette["info"]),
                                ], spacing=3, tight=True),
                                bgcolor=palette["info_bg"],
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=6,
                            ),
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, size=11, color=palette["text_muted"]),
                                    ft.Text(f"Joined {created_at_str}", size=10, color=palette["text_muted"]),
                                ], spacing=3, tight=True),
                                bgcolor=palette["surface_variant"],
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=6,
                            ),
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.OutlinedButton(
                                "Profile Dossier",
                                icon=ft.Icons.BADGE_ROUNDED,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    side=ft.BorderSide(1, palette["border"]),
                                ),
                                on_click=lambda e, ur=u: _open_user_detail_modal(ur),
                                expand=True,
                            ),
                            ft.FilledButton(
                                "Unverify" if is_v else "Verify",
                                icon=ft.Icons.REMOVE_MODERATOR_ROUNDED if is_v else ft.Icons.VERIFIED_ROUNDED,
                                tooltip="Revoke verified standing" if is_v else "Grant verified standing",
                                style=ft.ButtonStyle(
                                    bgcolor=palette["surface_variant"] if is_v else ft.Colors.GREEN_700,
                                    color=palette["text"] if is_v else ft.Colors.WHITE,
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                ),
                                on_click=lambda e, ur=u: page.run_task(_toggle_verify, ur),
                                expand=True,
                            ),
                        ],
                    ),
                ],
            ),
        )

    async def _prev_page(e=None):
        if admin_state["page_num"] > 1:
            admin_state["page_num"] -= 1
            await _fetch_users()

    async def _next_page(e=None):
        if admin_state["page_num"] < admin_state["total_pages"]:
            admin_state["page_num"] += 1
            await _fetch_users()

    def _build_pagination_row() -> ft.Control:
        showing_start = (admin_state["page_num"] - 1) * admin_state["limit"] + 1 if admin_state["total_users"] > 0 else 0
        showing_end = min(admin_state["page_num"] * admin_state["limit"], admin_state["total_users"])
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(f"Showing {showing_start}–{showing_end} of {admin_state['total_users']:,} accounts", size=12, color=palette["text_muted"]),
                ft.Row(
                    spacing=10,
                    controls=[
                        ft.OutlinedButton("← Previous", disabled=(admin_state["page_num"] <= 1), on_click=_prev_page),
                        ft.Text(f"Page {admin_state['page_num']} of {admin_state['total_pages']}", size=12, color=palette["text"], weight=ft.FontWeight.BOLD),
                        ft.OutlinedButton("Next →", disabled=(admin_state["page_num"] >= admin_state["total_pages"]), on_click=_next_page),
                    ],
                ),
            ],
        )

    def _reset_filters(e=None):
        nonlocal search_debounce_task
        if search_debounce_task and not search_debounce_task.done():
            search_debounce_task.cancel()
        search_box.value = ""
        clear_search_btn.visible = False
        role_dropdown.value = "all"
        verified_dropdown.value = "all"
        sort_dropdown.value = "created_desc"
        page.update()
        page.run_task(_on_filter_apply)

    def _refresh_users_roster_ui():
        if _users_tab_cache["roster"] is None:
            if admin_state["active_tab"] == "users":
                _render_tab_content()
            return

        # 1. Update KPI pills
        stats = admin_state["cached_analytics"] or {}
        tot_u = admin_state["total_users"]
        tot_students = stats.get("total_students", 0)
        tot_teachers = stats.get("total_teachers", 0)
        tot_admins = stats.get("total_admins", 0)
        tot_verified = stats.get("verified_users", 0)
        if _users_tab_cache["kpi_row"]:
            _users_tab_cache["kpi_row"].controls = _build_kpi_pills(tot_u, tot_students, tot_teachers, tot_admins, tot_verified)

        # 2. Update Roster Content
        if admin_state["is_loading_users"] and not admin_state["cached_users"]:
            _users_tab_cache["roster"].content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=60,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.ProgressRing(width=34, height=34, stroke_width=3, color=palette["accent"]),
                        ft.Text("Retrieving platform user roster...", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text("Loading accounts from the database with active filters", size=12, color=palette["text_muted"]),
                    ],
                ),
            )
        elif admin_state["users_error"]:
            _users_tab_cache["roster"].content = ft.Container(
                bgcolor=palette["danger_bg"],
                border=ft.Border.all(1, palette["danger"]),
                border_radius=14,
                padding=24,
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=palette["danger"], size=22),
                        ft.Text("Failed to retrieve user accounts.", size=15, weight=ft.FontWeight.BOLD, color=palette["danger"]),
                    ], spacing=8),
                    ft.Text(str(admin_state["users_error"]), size=13, color=palette["text"]),
                    ft.FilledButton(
                        "Retry User Fetch",
                        icon=ft.Icons.REFRESH_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=palette["danger"], color=ft.Colors.WHITE),
                        on_click=lambda e: page.run_task(_fetch_users),
                    ),
                ], spacing=12),
            )
        elif not admin_state["cached_users"]:
            _users_tab_cache["roster"].content = ft.Container(
                bgcolor=palette["card_bg"],
                border=ft.Border.all(1, palette["border"]),
                border_radius=14,
                padding=50,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.Container(
                            width=64, height=64, border_radius=32,
                            bgcolor=ft.Colors.with_opacity(0.12, palette["accent"]),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.PERSON_SEARCH_ROUNDED, size=32, color=palette["accent"]),
                        ),
                        ft.Text("No accounts matched your search criteria.", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text("Try checking your keywords or clearing role and verification filters.", size=12, color=palette["text_muted"]),
                        ft.FilledButton(
                            "Reset Filters",
                            icon=ft.Icons.FILTER_ALT_OFF_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=palette["accent_glow"], color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda e: _reset_filters(),
                        ),
                    ],
                ),
            )
        else:
            cards = [_build_user_card(u) for u in admin_state["cached_users"]]
            _users_tab_cache["roster"].content = ft.ResponsiveRow(
                spacing=14,
                run_spacing=14,
                controls=cards,
            )

        # 3. Update Pagination Bar
        if _users_tab_cache["pagination"]:
            _users_tab_cache["pagination"].content = _build_pagination_row()

    def _build_users_tab() -> ft.Control:
        if _users_tab_cache["view"] is not None:
            _refresh_users_roster_ui()
            return _users_tab_cache["view"]

        stats = admin_state["cached_analytics"] or {}
        tot_u = admin_state["total_users"]
        tot_students = stats.get("total_students", 0)
        tot_teachers = stats.get("total_teachers", 0)
        tot_admins = stats.get("total_admins", 0)
        tot_verified = stats.get("verified_users", 0)

        kpi_pills = _build_kpi_pills(tot_u, tot_students, tot_teachers, tot_admins, tot_verified)
        kpi_row = ft.Row(kpi_pills, wrap=True, spacing=8)
        _users_tab_cache["kpi_row"] = kpi_row

        header_ribbon = ft.Container(
            bgcolor=palette["surface"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=ft.Padding.symmetric(horizontal=18, vertical=14),
            content=ft.Column([
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    spacing=12,
                    controls=[
                        ft.Row([
                            ft.Container(
                                content=ft.Icon(ft.Icons.GROUPS_ROUNDED, color=palette["accent"], size=22),
                                bgcolor=ft.Colors.with_opacity(0.14, palette["accent"]),
                                padding=8,
                                border_radius=10,
                            ),
                            ft.Column([
                                ft.Text("Global User Directory", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ft.Text("Explore learner accounts, modify security roles, and verify enrollments.", size=12, color=palette["text_muted"]),
                            ], spacing=2),
                        ], spacing=10),
                        kpi_row,
                    ],
                ),
            ], spacing=10),
        )

        search_row = ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    content=ft.Row([
                        ft.Container(content=search_box, expand=True),
                        clear_search_btn,
                        search_spinner,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.REFRESH_ROUNDED,
                    tooltip="Refresh list",
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        side=ft.BorderSide(1, palette["border"]),
                    ),
                    on_click=lambda e: page.run_task(_fetch_users),
                ),
                ft.OutlinedButton(
                    "Reset",
                    icon=ft.Icons.FILTER_ALT_OFF_ROUNDED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        side=ft.BorderSide(1, palette["border"]),
                    ),
                    on_click=_reset_filters,
                ),
            ],
        )

        filters_row = ft.Row(
            wrap=True,
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.FILTER_LIST_ROUNDED, size=16, color=palette["text_muted"]),
                    ft.Text("Filters:", size=12, weight=ft.FontWeight.W_600, color=palette["text_muted"]),
                ], spacing=6, tight=True),
                role_dropdown,
                verified_dropdown,
                sort_dropdown,
            ],
        )

        filter_bar = ft.Container(
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=14,
            content=ft.Column(
                spacing=12,
                controls=[
                    search_row,
                    filters_row,
                ],
            ),
        )

        roster_container = ft.Container()
        _users_tab_cache["roster"] = roster_container

        pagination_bar = ft.Container(
            bgcolor=palette["surface"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            content=_build_pagination_row(),
        )
        _users_tab_cache["pagination"] = pagination_bar

        _refresh_users_roster_ui()

        users_view_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=14,
            controls=[
                header_ribbon,
                filter_bar,
                roster_container,
                pagination_bar,
            ],
        )
        _users_tab_cache["view"] = users_view_column
        return users_view_column

    # ─────────────────────────────────────────────────────────────────────────
    # G. TAB 3: PUSH BROADCAST CENTER (Firebase FCM)
    # ─────────────────────────────────────────────────────────────────────────

    # Push Notification inputs
    push_title_input = ft.TextField(
        label="Notification Title",
        hint_text="e.g. New Examination Schedule Ready!",
        border_color=palette["border"],
        text_style=ft.TextStyle(size=14, color=palette["text"]),
    )
    push_body_input = ft.TextField(
        label="Notification Message",
        hint_text="e.g. Hop in to review your latest course updates.",
        border_color=palette["border"],
        text_style=ft.TextStyle(size=13, color=palette["text"]),
        multiline=True,
        min_lines=3,
        max_lines=6,
    )
    push_route_input = ft.TextField(
        label="In-App Action Route (Optional)",
        value="/courses",
        hint_text="e.g. /courses or /notifications",
        border_color=palette["border"],
        text_style=ft.TextStyle(size=13, color=palette["text"]),
    )
    push_audience_dropdown = ft.Dropdown(
        label="Target Audience",
        value="all",
        border_color=palette["border"],
        options=[
            ft.dropdown.Option("all", "All Registered Devices"),
            ft.dropdown.Option("students", "Students Only"),
            ft.dropdown.Option("teachers", "Teachers Only"),
        ],
    )

    async def _dispatch_bulk_push(e=None):
        title = push_title_input.value.strip() if push_title_input.value else ""
        body = push_body_input.value.strip() if push_body_input.value else ""
        aud = push_audience_dropdown.value or "all"
        route = push_route_input.value.strip() if push_route_input.value else None

        if not title or not body:
            show_page_snackbar(page, ft.SnackBar(content=ft.Text("Please fill out notification title and message body."), bgcolor=ft.Colors.AMBER_700))
            return

        show_page_snackbar(page, ft.SnackBar(content=ft.Text("Dispatching push notifications via Firebase FCM..."), bgcolor=ft.Colors.BLUE_700))
        status_code, data = await broadcast_bulk_push(admin_state["token"], audience=aud, title=title, body=body, action_route=route)
        if status_code == 200:
            show_page_snackbar(
                page,
                ft.SnackBar(
                    content=ft.Row([
                        ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text(f"Push dispatched: {data.get('message')}", color=ft.Colors.WHITE),
                    ], spacing=8),
                    bgcolor=ft.Colors.GREEN_700,
                    duration=4000,
                )
            )
            push_title_input.value = ""
            push_body_input.value = ""
            page.update()
        else:
            show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Push failed: {data.get('detail')}"), bgcolor=ft.Colors.RED_700))

    def _build_broadcast_tab() -> ft.Control:
        stats = admin_state["cached_analytics"] or {}
        tot_u = stats.get("total_users", admin_state["total_users"])
        tot_devices = stats.get("total_device_tokens", 0)

        push_card = ft.Container(
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=24,
            content=ft.Column(
                spacing=16,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED, size=22, color=palette["accent"]),
                        ft.Text("Push Notification Multicast (Firebase Cloud Messaging)", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ], spacing=8),
                    ft.Text(
                        "Broadcast instant push alerts to registered mobile and desktop devices. Learners tapping the notification will be directed to the specified in-app route.",
                        size=13,
                        color=palette["text_muted"],
                    ),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.DEVICES_ROUNDED, size=14, color=palette["accent"]),
                            ft.Text(f"Active Device Reach: ~{tot_devices:,} registered devices across ~{tot_u:,} user accounts.", size=11, color=palette["text"]),
                        ], spacing=6),
                        bgcolor=palette["surface_variant"],
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        border_radius=8,
                    ),
                    ft.Row([push_audience_dropdown, push_route_input], spacing=12),
                    push_title_input,
                    push_body_input,
                    ft.FilledButton(
                        "Broadcast Push Notification",
                        icon=ft.Icons.NOTIFICATION_ADD_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=palette["accent_glow"],
                            color=ft.Colors.WHITE,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=20, vertical=14),
                        ),
                        on_click=_dispatch_bulk_push,
                    ),
                ],
            ),
        )

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=16,
            controls=[
                push_card,
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # H. TAB 4: EXPORT CENTER (ROBUST HANDLERS)
    # ─────────────────────────────────────────────────────────────────────────

    export_role_filter = ft.Dropdown(
        width=200,
        label="Filter Export by Role",
        value="all",
        border_color=palette["border"],
        options=[
            ft.dropdown.Option("all", "All Registered Users"),
            ft.dropdown.Option("Student", "Students Only"),
            ft.dropdown.Option("Teacher", "Teachers Only"),
            ft.dropdown.Option("Admin", "Admins Only"),
        ],
    )

    excel_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.WHITE, visible=False)
    excel_btn_label = ft.Text("Download Formatted Excel Workbook (.xlsx)", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)

    csv_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=palette["text"], visible=False)
    csv_btn_label = ft.Text("Download Plain CSV (.csv)", weight=ft.FontWeight.BOLD)

    async def _execute_excel_export(e=None):
        if admin_state["is_exporting_excel"]:
            return
        admin_state["is_exporting_excel"] = True
        excel_spinner.visible = True
        excel_btn_label.value = "Generating Excel Spreadsheet..."
        page.update()

        show_page_snackbar(
            page,
            ft.SnackBar(content=ft.Text("Generating formatted Excel (.xlsx) spreadsheet..."), bgcolor=ft.Colors.BLUE_700, duration=3000)
        )

        status_code, content_bytes, filename = await export_users_data(
            admin_state["token"],
            format="xlsx",
            role=export_role_filter.value,
        )

        admin_state["is_exporting_excel"] = False
        excel_spinner.visible = False
        excel_btn_label.value = "Download Formatted Excel Workbook (.xlsx)"
        page.update()

        if status_code == 200 and content_bytes:
            downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.exists(downloads_dir):
                downloads_dir = tempfile.gettempdir()
            target_path = os.path.join(downloads_dir, filename)

            try:
                with open(target_path, "wb") as f:
                    f.write(content_bytes)

                show_page_snackbar(
                    page,
                    ft.SnackBar(
                        content=ft.Row([
                            ft.Icon(ft.Icons.DOWNLOAD_DONE_ROUNDED, color=ft.Colors.WHITE, size=18),
                            ft.Text(f"Excel Export saved successfully: {filename}", color=ft.Colors.WHITE),
                        ], spacing=8),
                        action="Open File",
                        on_action=lambda ev: _open_file_locally(target_path),
                        bgcolor=ft.Colors.GREEN_700,
                        duration=6000,
                    )
                )
            except Exception as err:
                show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Could not save file locally: {err}"), bgcolor=ft.Colors.RED_700))
        else:
            show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Excel export failed from server (Code {status_code})."), bgcolor=ft.Colors.RED_700))

    async def _execute_csv_export(e=None):
        if admin_state["is_exporting_csv"]:
            return
        admin_state["is_exporting_csv"] = True
        csv_spinner.visible = True
        csv_btn_label.value = "Generating CSV..."
        page.update()

        status_code, content_bytes, filename = await export_users_data(
            admin_state["token"],
            format="csv",
            role=export_role_filter.value,
        )

        admin_state["is_exporting_csv"] = False
        csv_spinner.visible = False
        csv_btn_label.value = "Download Plain CSV (.csv)"
        page.update()

        if status_code == 200 and content_bytes:
            downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.exists(downloads_dir):
                downloads_dir = tempfile.gettempdir()
            target_path = os.path.join(downloads_dir, filename)

            try:
                with open(target_path, "wb") as f:
                    f.write(content_bytes)

                show_page_snackbar(
                    page,
                    ft.SnackBar(
                        content=ft.Row([
                            ft.Icon(ft.Icons.DOWNLOAD_DONE_ROUNDED, color=ft.Colors.WHITE, size=18),
                            ft.Text(f"CSV Export saved successfully: {filename}", color=ft.Colors.WHITE),
                        ], spacing=8),
                        action="Open File",
                        on_action=lambda ev: _open_file_locally(target_path),
                        bgcolor=ft.Colors.GREEN_700,
                        duration=6000,
                    )
                )
            except Exception as err:
                show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Could not save file locally: {err}"), bgcolor=ft.Colors.RED_700))
        else:
            show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"CSV export failed from server (Code {status_code})."), bgcolor=ft.Colors.RED_700))

    def _build_export_tab() -> ft.Control:
        included_fields = [
            "User ID", "Full Name", "First Name", "Last Name", "Username", "Email",
            "Phone Number", "Role", "Gender", "Verified Status", "Study Streak", "University",
            "Last Login Date", "Account Created At"
        ]
        field_chips = [
            ft.Container(
                content=ft.Text(f, size=10, color=palette["text_muted"]),
                bgcolor=palette["surface_variant"],
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=6,
            ) for f in included_fields
        ]

        return ft.Container(
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=24,
            content=ft.Column(
                spacing=18,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.TABLE_VIEW_ROUNDED, size=24, color=palette["success"]),
                        ft.Text("Platform User Audit & Data Export", size=18, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ], spacing=10),
                    ft.Text(
                        "Export a comprehensive audit log of all registered platform users. Includes 14 essential fields for institutional accreditation, data backups, and learner analytics.",
                        size=13,
                        color=palette["text_muted"],
                    ),
                    ft.Column([
                        ft.Text("AUDIT COLUMNS INCLUDED IN EXPORT:", size=11, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                        ft.Row(field_chips, wrap=True, spacing=6),
                    ], spacing=6),
                    ft.Divider(color=palette["border"], height=12),
                    ft.Row([
                        export_role_filter,
                    ]),
                    ft.Row(
                        spacing=12,
                        wrap=True,
                        controls=[
                            ft.FilledButton(
                                content=ft.Row([excel_spinner, excel_btn_label], tight=True, spacing=8),
                                icon=ft.Icons.TABLE_VIEW_ROUNDED,
                                style=ft.ButtonStyle(
                                    bgcolor=palette["success"],
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.Padding.symmetric(horizontal=18, vertical=14),
                                ),
                                on_click=_execute_excel_export,
                            ),
                            ft.OutlinedButton(
                                content=ft.Row([csv_spinner, csv_btn_label], tight=True, spacing=8),
                                icon=ft.Icons.DESCRIPTION_ROUNDED,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.Padding.symmetric(horizontal=18, vertical=14),
                                ),
                                on_click=_execute_csv_export,
                            ),
                        ],
                    ),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # I. MASTER VIEW COMPOSER
    # ─────────────────────────────────────────────────────────────────────────

    def _render_tab_content():
        if admin_state["active_tab"] == "overview":
            active_content_area.content = _build_overview_tab()
        elif admin_state["active_tab"] == "users":
            active_content_area.content = _build_users_tab()
        elif admin_state["active_tab"] == "broadcast":
            active_content_area.content = _build_broadcast_tab()
        elif admin_state["active_tab"] == "export":
            active_content_area.content = _build_export_tab()

    def _build_dashboard_suite() -> ft.Control:
        admin_user_info = admin_state["admin_user"] or {}
        admin_name = admin_user_info.get("name") or admin_user_info.get("username", "Super Admin")

        nav_container.content = _build_nav_bar()

        header_bar = ft.Container(
            bgcolor=palette["surface"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=ft.Padding.symmetric(horizontal=18, vertical=12),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    # Title & Admin Monogram
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED, size=22, color=palette["accent"]),
                            bgcolor=ft.Colors.with_opacity(0.14, palette["accent"]),
                            padding=8,
                            border_radius=10,
                        ),
                        ft.Column(
                            spacing=1,
                            controls=[
                                ft.Row([
                                    ft.Text("Nu-Age Control Plane", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                    ft.Container(
                                        content=ft.Text("SUPER ADMIN", size=9, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                                        bgcolor=ft.Colors.with_opacity(0.15, palette["accent"]),
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=4,
                                    ),
                                ], spacing=6, tight=True),
                                ft.Text(f"Logged in as {admin_name}", size=11, color=palette["text_muted"]),
                            ],
                        ),
                    ], spacing=10),
                    # Telemetry & Actions
                    ft.Row(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.Container(
                                content=ft.Row([telemetry_dot, telemetry_badge_text], spacing=6, tight=True),
                                bgcolor=palette["surface_variant"],
                                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                border_radius=8,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH_ROUNDED,
                                tooltip="Refresh Platform Telemetry",
                                on_click=lambda e: (page.run_task(_fetch_analytics), page.run_task(_fetch_health)),
                            ),
                            ft.FilledButton(
                                "Lock Admin Mode",
                                icon=ft.Icons.LOCK_RESET_ROUNDED,
                                style=ft.ButtonStyle(bgcolor=palette["surface_variant"], color=palette["text"], shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=_lock_admin_session,
                            ),
                        ],
                    ),
                ],
            ),
        )

        _render_tab_content()

        return ft.Column(
            expand=True,
            spacing=12,
            controls=[
                header_bar,
                nav_container,
                active_content_area,
            ],
        )

    def _render_dashboard():
        if admin_state["authenticated"]:
            main_container.content = _build_dashboard_suite()
            # If authenticated, auto-fetch initial data if missing
            if admin_state["cached_analytics"] is None:
                page.run_task(_fetch_analytics)
                page.run_task(_fetch_health)
            if not admin_state["cached_users"]:
                page.run_task(_fetch_users)
        else:
            main_container.content = _build_lock_screen()

    _render_dashboard()

    return ft.View(
        route="/platform-admin",
        bgcolor=palette["bg"],
        padding=16,
        controls=[main_container],
    )
