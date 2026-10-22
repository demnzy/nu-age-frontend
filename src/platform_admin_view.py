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
from src.components.nu_coin_icon import nu_coin_icon

from src.requests.platform_admin import (
    verify_admin_credentials,
    get_platform_analytics,
    get_platform_users,
    update_user_attributes,
    delete_user_account,
    export_users_data,
    broadcast_bulk_push,
    get_broadcast_history,
    get_platform_health,
    queue_all_lesson_audio,
    get_audio_queue_status,
    cancel_audio_queue,
    get_admin_objectives,
    create_admin_objective,
    update_admin_objective,
    delete_admin_objective,
    test_trigger_admin_objective,
)
from src.requests.marketplace import (
    fetch_admin_pending_submissions,
    review_admin_submission,
    fetch_marketplace_packs,
    update_admin_pack,
    fetch_admin_all_packs,
    toggle_admin_pack_visibility,
    delete_admin_pack,
    parse_past_questions_ai,
    parse_past_questions_file_ai,
    create_official_curated_pack,
    fetch_admin_pack_full,
    fetch_admin_all_bundles,
    create_study_bundle_admin,
    update_study_bundle_admin,
    toggle_admin_bundle_visibility,
    delete_admin_bundle,
)
from src.components.study_pack_card import CATEGORY_PRESETS, StudyPackCard
from src.components.question_curator_modal import show_question_curator_dialog
from src.components.bundle_builder_modal import show_bundle_builder_dialog
from src.requests.payments import (
    get_admin_store_products,
    create_admin_store_product,
    update_admin_store_product,
    delete_admin_store_product,
    get_admin_org_plans,
    save_admin_org_plan,
)
from src.utils.file_opener import show_page_snackbar
from src.components import study_ui as ui
from src.requests.promo import (
    get_admin_promo_codes_api,
    create_admin_promo_code_api,
    toggle_admin_promo_code_api,
    delete_admin_promo_code_api,
    get_admin_badges_api,
    create_admin_badge_api,
    update_admin_badge_api,
    delete_admin_badge_api,
    get_admin_ambassadors_api,
    invite_admin_ambassador_api,
    update_admin_ambassador_status_api,
    get_admin_ambassador_applications_api,
    approve_ambassador_application_api,
    reject_ambassador_application_api,
)
from src.requests.auth import get_universities
from src.components.badge_pill import build_glossy_badge_pill
from src.components.admin_system_panels import CategoriesPanel, SystemToolsPanel


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


# Fallback cover used when a pack has no cover image (change to your own generic PNG if needed)
DEFAULT_PACK_COVER_URL = "https://placehold.co/800x450/png"


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
        "subtext": "#94A3B8" if is_dark else "#64748B",
        "muted": "#94A3B8" if is_dark else "#64748B",
        "accent": "#F59E0B",        # Amber Gold
        "accent_glow": "#D97706",
        "primary": ft.Colors.PRIMARY,
        "danger": "#EF4444",
        "danger_bg": ft.Colors.with_opacity(0.12, "#EF4444"),
        "warning": "#F59E0B",
        "warning_bg": ft.Colors.with_opacity(0.12, "#F59E0B"),
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
        "store_products": [],
        "is_loading_store": False,
        "store_filter_cat": "all",
        "is_loading_analytics": False,
        "is_loading_users": False,
        "analytics_error": None,
        "users_error": None,
        "health_data": None,
        "broadcast_history": [],
        "is_loading_history": False,

        "is_exporting_excel": False,
        "is_exporting_csv": False,

        # Study Pack Marketplace State
        "cached_study_packs": [],
        "cached_pending_packs": [],
        "is_loading_packs": False,
        "packs_subtab": "pending",  # "pending", "approved", or "bundles"
        "packs_error": None,
        "pending_packs_count": 0,
        "cached_bundles": [],
        "is_loading_bundles": False,
        "bundles_error": None,

        # Audio Studio Batch Queue State
        "audio_queue_status": None,
        "is_loading_audio_queue": False,
        "is_triggering_audio_queue": False,
        "audio_queue_error": None,
        "audio_queue_selected_langs": {"en": True, "ha": True, "fr": True},
        "audio_queue_force": False,

        # Objectives & Milestones Studio State
        "objectives": [],
        "is_loading_objectives": False,
        "objectives_error": None,
        "objectives_stats": {"total": 0, "active": 0, "coins_distributed": 0},

        # Promo Codes, Badges & Campus Ambassadors State
        "promo_subtab": "promo_codes",  # "promo_codes", "ambassadors", or "badges"
        "promo_codes": [],
        "is_loading_promo": False,
        "promo_error": None,
        "ambassadors": [],
        "is_loading_ambassadors": False,
        "ambassadors_error": None,
        "ambassador_view_subtab": "roster",  # "roster" or "applications"
        "ambassador_applications": [],
        "is_loading_ambassador_applications": False,
        "ambassador_applications_error": None,
        "ambassador_applications_filter": "all",
        "badges_cache": [],
        "is_loading_badges": False,
        "badges_error": None,
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
    categories_panel = CategoriesPanel(page, palette, lambda: admin_state["token"])
    system_tools_panel = SystemToolsPanel(page, palette, lambda: admin_state["token"])
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

    def _refresh_history_ui():
        # Forward declaration stub, implemented in Tab 3
        pass

    async def _fetch_broadcast_history():
        if not admin_state["token"]:
            return
        admin_state["is_loading_history"] = True
        _refresh_history_ui()
        page.update()

        status_code, data = await get_broadcast_history(admin_state["token"], page=1, limit=15)
        admin_state["is_loading_history"] = False
        if status_code == 200:
            admin_state["broadcast_history"] = data.get("items", [])
        else:
            admin_state["broadcast_history"] = []
        _refresh_history_ui()
        page.update()

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

    async def _fetch_study_packs():
        if not admin_state["token"]:
            return
        admin_state["is_loading_packs"] = True
        admin_state["packs_error"] = None
        if admin_state["active_tab"] == "study_packs":
            _render_tab_content()
            page.update()

        pending_res = await fetch_admin_pending_submissions(admin_state["token"], page=1, limit=50)
        catalog_res = await fetch_admin_all_packs(admin_state["token"], page=1, limit=100)
        if "error" in catalog_res and not catalog_res.get("items"):
            catalog_res = await fetch_marketplace_packs(token=admin_state["token"], page=1, limit=50)

        admin_state["is_loading_packs"] = False
        if "error" in pending_res:
            admin_state["packs_error"] = pending_res.get("error")
        else:
            admin_state["cached_pending_packs"] = pending_res.get("items", [])
            admin_state["pending_packs_count"] = pending_res.get("total", len(admin_state["cached_pending_packs"]))

        if "error" not in catalog_res:
            admin_state["cached_study_packs"] = catalog_res.get("items", [])

        # Update nav badge
        nav_container.content = _build_nav_bar()
        if admin_state["active_tab"] == "study_packs":
            _render_tab_content()
        page.update()
        await _fetch_bundles()

    async def _fetch_bundles():
        if not admin_state["token"]:
            return
        admin_state["is_loading_bundles"] = True
        admin_state["bundles_error"] = None
        if admin_state["active_tab"] == "study_packs" and admin_state["packs_subtab"] == "bundles":
            _render_tab_content()
            page.update()

        b_res = await fetch_admin_all_bundles(admin_state["token"])
        admin_state["is_loading_bundles"] = False
        if "error" in b_res and not b_res.get("bundles"):
            admin_state["bundles_error"] = b_res.get("error")
        else:
            admin_state["cached_bundles"] = b_res.get("bundles", [])

        if admin_state["active_tab"] == "study_packs":
            _render_tab_content()
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
                            ft.Text("Nu Age Control Plane", size=22, weight=ft.FontWeight.BOLD, color=palette["text"]),
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
        elif tab_name == "broadcast":
            page.run_task(_fetch_broadcast_history)
        elif tab_name == "study_packs":
            page.run_task(_fetch_study_packs)
        elif tab_name == "store_studio":
            page.run_task(_fetch_store_products)
        elif tab_name == "audio_studio":
            page.run_task(_fetch_audio_queue_status)
            page.run_task(_audio_queue_auto_poller)
        elif tab_name == "objectives":
            page.run_task(_fetch_objectives)
        elif tab_name == "promo_ambassadors":
            page.run_task(_fetch_promo_codes)
            page.run_task(_fetch_ambassadors)
            page.run_task(_fetch_badges_cache)
            page.run_task(_fetch_ambassador_applications)
        elif tab_name == "categories":
            page.run_task(categories_panel.load)

    def _build_nav_bar() -> ft.Control:
        nav_buttons = [
            ("overview", "Overview", ft.Icons.DASHBOARD_ROUNDED, None),
            ("users", "User Directory", ft.Icons.PEOPLE_ROUNDED, admin_state["total_users"] if admin_state["total_users"] > 0 else None),
            ("store_studio", "Store Studio", ft.Icons.STORE_ROUNDED, len(admin_state["store_products"]) if admin_state["store_products"] else None),
            ("study_packs", "Study Packs", ft.Icons.STOREFRONT_ROUNDED, admin_state["pending_packs_count"] if admin_state["pending_packs_count"] > 0 else None),
            ("objectives", "Objectives", ft.Icons.MILITARY_TECH_ROUNDED, len(admin_state["objectives"]) if admin_state.get("objectives") else None),
            ("promo_ambassadors", "Promo & Ambassadors", ft.Icons.LOYALTY_ROUNDED, len(admin_state["promo_codes"]) if admin_state.get("promo_codes") else None),
            ("audio_studio", "Audio Studio", ft.Icons.GRAPHIC_EQ_ROUNDED, None),
            ("categories", "Categories", ft.Icons.CATEGORY_ROUNDED, len(categories_panel.categories) if categories_panel.categories else None),
            ("system_tools", "System Tools", ft.Icons.MONITOR_HEART_ROUNDED, None),
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
                                foreground_image_src=u.get("profile_picture_url") if (u.get("profile_picture_url") and str(u.get("profile_picture_url")).startswith("http")) else None,
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
                        ft.Row([ft.Text("Joined Nu Age:", size=11, color=palette["text_muted"]), ft.Text(str(u.get("created_at") or "—"), size=11)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
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

        async def _execute_delete(e=None):
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

        delete_btn.on_click = lambda e: page.run_task(_execute_delete, e)

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
                                    foreground_image_src=u.get("profile_picture_url") if (u.get("profile_picture_url") and str(u.get("profile_picture_url")).startswith("http")) else None,
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
    # G. TAB 3: PUSH BROADCAST MISSION CONTROL (OneSignal + FCM Multicast)
    # ─────────────────────────────────────────────────────────────────────────

    # Push Notification Form Inputs
    push_title_counter = ft.Text("0 / 65", size=11, color=palette["text_muted"])
    push_subtitle_counter = ft.Text("0 / 65", size=11, color=palette["text_muted"])
    push_body_counter = ft.Text("0 / 250", size=11, color=palette["text_muted"])

    push_title_input = ft.TextField(
        label="Notification Title *",
        hint_text="e.g. New Examination Schedule Ready!",
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        text_style=ft.TextStyle(size=14, color=palette["text"], weight=ft.FontWeight.W_600),
        max_length=65,
    )

    push_subtitle_input = ft.TextField(
        label="Notification Subtitle (Optional)",
        hint_text="e.g. Computer Science Department",
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        text_style=ft.TextStyle(size=13, color=palette["text"]),
        max_length=65,
    )

    push_body_input = ft.TextField(
        label="Notification Message Body *",
        hint_text="e.g. Tap here to review your newly updated exam timetable and venue allocations.",
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        text_style=ft.TextStyle(size=13, color=palette["text"]),
        multiline=True,
        min_lines=3,
        max_lines=5,
        max_length=250,
    )

    push_image_input = ft.TextField(
        label="Banner Image URL (Optional)",
        hint_text="e.g. https://images.unsplash.com/... or https://domain/banner.png",
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        text_style=ft.TextStyle(size=13, color=palette["text"]),
    )

    push_route_input = ft.TextField(
        label="In-App Action Route",
        value="/courses",
        hint_text="e.g. /courses, /notifications, /dashboard",
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        text_style=ft.TextStyle(size=13, color=palette["text"]),
    )

    push_button_label_input = ft.TextField(
        label="Action Button Label (Optional)",
        hint_text="e.g. View Timetable or Open App",
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        text_style=ft.TextStyle(size=13, color=palette["text"]),
    )

    push_audience_dropdown = ft.Dropdown(
        label="Target Audience",
        value="all",
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        text_style=ft.TextStyle(size=13, color=palette["text"]),
        options=[
            ft.dropdown.Option("all", "All Active Devices (Full Broadcast)"),
            ft.dropdown.Option("students", "Students Only"),
            ft.dropdown.Option("teachers", "Teachers Only"),
            ft.dropdown.Option("admins", "Platform Admins Only"),
            ft.dropdown.Option("test_me", "Direct Test to My Device (Admin ID)"),
        ],
    )

    push_priority_dropdown = ft.Dropdown(
        label="Delivery Priority & Urgency",
        value="10",
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        text_style=ft.TextStyle(size=13, color=palette["text"]),
        options=[
            ft.dropdown.Option("10", "High Priority (Heads-up popup banner)"),
            ft.dropdown.Option("5", "Normal Priority (Notification shade)"),
        ],
    )

    push_ttl_dropdown = ft.Dropdown(
        label="Message Time-To-Live (TTL)",
        value="86400",
        border_color=palette["border"],
        focused_border_color=palette["accent"],
        text_style=ft.TextStyle(size=13, color=palette["text"]),
        options=[
            ft.dropdown.Option("86400", "24 Hours (Standard Default)"),
            ft.dropdown.Option("3600", "1 Hour (Live Exam / Time-critical)"),
            ft.dropdown.Option("259200", "3 Days"),
            ft.dropdown.Option("604800", "7 Days"),
        ],
    )

    # ── Live Device Mockup Preview Controls ──────────────────────────────────
    preview_title = ft.Text(
        "New Examination Schedule Ready!",
        size=14,
        weight=ft.FontWeight.BOLD,
        color=palette["text"],
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    preview_subtitle = ft.Text(
        "",
        size=12,
        weight=ft.FontWeight.W_500,
        color=palette["accent"],
        visible=False,
    )
    preview_body = ft.Text(
        "Tap here to review your newly updated exam timetable and venue allocations on Nu-Age.",
        size=12,
        color=palette["text_muted"],
        max_lines=4,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    preview_image = ft.Image(
        src="",
        fit=ft.BoxFit.COVER,
        height=110,
        border_radius=8,
        error_content=ft.Container(),
    )
    preview_image_container = ft.Container(
        content=preview_image,
        visible=False,
        margin=ft.Margin.only(top=8, bottom=4),
        border_radius=8,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )
    preview_action_label = ft.Text("", size=11, weight=ft.FontWeight.BOLD, color=palette["accent"])
    preview_action_btn = ft.Container(
        content=preview_action_label,
        bgcolor=ft.Colors.with_opacity(0.12, palette["accent"]),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, palette["accent"])),
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        visible=False,
        margin=ft.Margin.only(top=8),
    )
    preview_meta_badge = ft.Text(
        "Target: All Devices • Route: /courses • High Priority",
        size=10,
        color=palette["text_muted"],
    )

    def _update_push_preview(e=None):
        t = push_title_input.value.strip() if push_title_input.value else ""
        s = push_subtitle_input.value.strip() if push_subtitle_input.value else ""
        b = push_body_input.value.strip() if push_body_input.value else ""
        img = push_image_input.value.strip() if push_image_input.value else ""
        btn_lbl = push_button_label_input.value.strip() if push_button_label_input.value else ""
        r = push_route_input.value.strip() if push_route_input.value else "/courses"
        aud = push_audience_dropdown.value or "all"
        prio = push_priority_dropdown.value or "10"

        push_title_counter.value = f"{len(push_title_input.value or '')} / 65"
        push_subtitle_counter.value = f"{len(push_subtitle_input.value or '')} / 65"
        push_body_counter.value = f"{len(push_body_input.value or '')} / 250"

        preview_title.value = t or "New Examination Schedule Ready!"
        if s:
            preview_subtitle.value = s
            preview_subtitle.visible = True
        else:
            preview_subtitle.visible = False

        preview_body.value = b or "Tap here to review your newly updated exam timetable and venue allocations on Nu-Age."

        if img and (img.startswith("http://") or img.startswith("https://")):
            preview_image.src = img
            preview_image_container.visible = True
        else:
            preview_image_container.visible = False

        if btn_lbl:
            preview_action_label.value = btn_lbl.upper()
            preview_action_btn.visible = True
        else:
            preview_action_btn.visible = False

        prio_label = "High Priority" if prio == "10" else "Normal Priority"
        aud_label = {
            "all": "All Devices",
            "students": "Students Only",
            "teachers": "Teachers Only",
            "admins": "Admins Only",
            "test_me": "Direct Test to Me",
        }.get(aud, aud.capitalize())

        preview_meta_badge.value = f"Target: {aud_label} • Route: {r} • {prio_label}"
        page.update()

    push_title_input.on_change = _update_push_preview
    push_subtitle_input.on_change = _update_push_preview
    push_body_input.on_change = _update_push_preview
    push_image_input.on_change = _update_push_preview
    push_route_input.on_change = _update_push_preview
    push_button_label_input.on_change = _update_push_preview
    push_audience_dropdown.on_change = _update_push_preview
    push_priority_dropdown.on_change = _update_push_preview

    def _select_route(target_route: str):
        push_route_input.value = target_route
        _update_push_preview()

    # Route preset chips
    route_chips = []
    preset_routes = [
        ("/courses", "Courses"),
        ("/notifications", "Notifications"),
        ("/dashboard", "Dashboard"),
        ("/profile", "Profile"),
        ("/exam/live", "Live Exam"),
        ("/self-study", "Self-Study"),
    ]
    for r_path, r_label in preset_routes:
        route_chips.append(
            ft.Container(
                content=ft.Text(r_label, size=11, weight=ft.FontWeight.W_500, color=palette["text"]),
                bgcolor=palette["surface_variant"],
                border=ft.Border.all(1, palette["border"]),
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                ink=True,
                on_click=lambda e, rp=r_path: _select_route(rp),
            )
        )

    # Dispatch Action Handlers
    broadcast_btn_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.WHITE, visible=False)
    test_btn_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=palette["accent"], visible=False)

    async def _execute_push_dispatch(is_test: bool = False):
        title = push_title_input.value.strip() if push_title_input.value else ""
        body = push_body_input.value.strip() if push_body_input.value else ""
        sub = push_subtitle_input.value.strip() if push_subtitle_input.value else None
        img = push_image_input.value.strip() if push_image_input.value else None
        btn_label = push_button_label_input.value.strip() if push_button_label_input.value else None
        route = push_route_input.value.strip() if push_route_input.value else "/courses"
        prio = int(push_priority_dropdown.value or "10")
        ttl = int(push_ttl_dropdown.value or "86400")

        aud = "test_me" if is_test else (push_audience_dropdown.value or "all")

        if not title:
            show_page_snackbar(page, ft.SnackBar(content=ft.Text("Please enter a notification title."), bgcolor=ft.Colors.AMBER_700))
            return
        if not body:
            show_page_snackbar(page, ft.SnackBar(content=ft.Text("Please enter a message body."), bgcolor=ft.Colors.AMBER_700))
            return

        auth_tok = admin_state.get("token")
        if not auth_tok and hasattr(page, "shared_preferences"):
            try:
                auth_tok = await page.shared_preferences.get("auth_token")
            except Exception:
                pass

        if not auth_tok:
            show_page_snackbar(page, ft.SnackBar(content=ft.Text("Super-admin authentication token missing. Please lock and unlock."), bgcolor=ft.Colors.AMBER_700))
            return

        if is_test:
            test_btn_spinner.visible = True
        else:
            broadcast_btn_spinner.visible = True
        page.update()

        try:
            status_code, data = await broadcast_bulk_push(
                token=auth_tok,
                audience=aud,
                title=title,
                body=body,
                action_route=route,
                subtitle=sub,
                image_url=img,
                action_button_label=btn_label,
                priority=prio,
                ttl_seconds=ttl,
            )

            if status_code == 200:
                msg = data.get("message", "Push notification dispatched successfully.")
                show_page_snackbar(
                    page,
                    ft.SnackBar(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                            ft.Text(msg, color=ft.Colors.WHITE),
                        ], spacing=8),
                        bgcolor=ft.Colors.GREEN_700,
                        duration=5000,
                    )
                )
                # Auto-refresh broadcast audit history
                page.run_task(_fetch_broadcast_history)
            else:
                err = data.get("detail", f"Dispatch failed (Code {status_code}).")
                show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Push failed: {err}"), bgcolor=ft.Colors.RED_700))
        except Exception as ex:
            show_page_snackbar(page, ft.SnackBar(content=ft.Text(f"Push dispatch error: {ex}"), bgcolor=ft.Colors.RED_700))
        finally:
            test_btn_spinner.visible = False
            broadcast_btn_spinner.visible = False
            page.update()

    async def _handle_send_test(e=None):
        await _execute_push_dispatch(is_test=True)

    async def _handle_send_broadcast(e=None):
        await _execute_push_dispatch(is_test=False)

    # ── History & Audit Log UI ───────────────────────────────────────────────
    history_container = ft.Container()

    def _actual_refresh_history_ui():
        if admin_state["is_loading_history"]:
            history_container.content = ft.Container(
                padding=20,
                alignment=ft.Alignment.CENTER,
                content=ft.Row([
                    ft.ProgressRing(width=20, height=20, stroke_width=2, color=palette["accent"]),
                    ft.Text("Fetching broadcast audit log...", size=12, color=palette["text_muted"]),
                ], spacing=10, tight=True),
            )
            return

        items = admin_state["broadcast_history"] or []
        if not items:
            history_container.content = ft.Container(
                padding=24,
                alignment=ft.Alignment.CENTER,
                content=ft.Column([
                    ft.Icon(ft.Icons.NOTIFICATIONS_NONE_ROUNDED, size=32, color=palette["text_muted"]),
                    ft.Text("No push notification broadcasts recorded yet.", size=13, weight=ft.FontWeight.W_500, color=palette["text"]),
                    ft.Text("Dispatches sent from the composer above will appear here with delivery telemetry.", size=11, color=palette["text_muted"]),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
            )
            return

        history_rows = []
        for rec in items:
            created_str = str(rec.get("created_at") or "")
            if "T" in created_str:
                created_str = created_str.replace("T", " ")[:16]

            st = str(rec.get("status") or "completed").lower()
            if st == "completed":
                st_color = palette["success"]
                st_bg = palette["success_bg"]
                st_label = "Delivered"
            elif st == "test":
                st_color = palette["info"]
                st_bg = palette["info_bg"]
                st_label = "Test Sent"
            else:
                st_color = palette["danger"]
                st_bg = palette["danger_bg"]
                st_label = "Failed"

            aud_val = str(rec.get("audience") or "all").capitalize()
            targeted = rec.get("targeted_devices_count", 0)
            sender = rec.get("sender_username", "admin")

            row_card = ft.Container(
                bgcolor=palette["surface_variant"],
                border=ft.Border.all(1, palette["border_subtle"]),
                border_radius=10,
                padding=12,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        # Left details
                        ft.Column(
                            spacing=4,
                            expand=True,
                            controls=[
                                ft.Row([
                                    ft.Text(rec.get("title", "Untitled Notification"), size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                    ft.Container(
                                        content=ft.Text(st_label, size=9, weight=ft.FontWeight.BOLD, color=st_color),
                                        bgcolor=st_bg,
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=4,
                                    ),
                                    ft.Container(
                                        content=ft.Text(f"Audience: {aud_val}", size=9, weight=ft.FontWeight.W_500, color=palette["text_muted"]),
                                        bgcolor=ft.Colors.with_opacity(0.08, palette["text_muted"]),
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=4,
                                    ),
                                ], spacing=8, wrap=True),
                                ft.Text(rec.get("body", ""), size=12, color=palette["text_muted"], max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Row([
                                    ft.Icon(ft.Icons.SCHEDULE_ROUNDED, size=12, color=palette["text_muted"]),
                                    ft.Text(created_str, size=11, color=palette["text_muted"]),
                                    ft.Text("•", size=11, color=palette["text_muted"]),
                                    ft.Icon(ft.Icons.ROUTE_ROUNDED, size=12, color=palette["accent"]),
                                    ft.Text(rec.get("action_route") or "/courses", size=11, color=palette["accent"]),
                                    ft.Text("•", size=11, color=palette["text_muted"]),
                                    ft.Text(f"By {sender}", size=11, color=palette["text_muted"]),
                                ], spacing=4, wrap=True),
                            ],
                        ),
                        # Right telemetry
                        ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                            spacing=2,
                            controls=[
                                ft.Text(f"~{targeted:,}", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ft.Text("recipients", size=10, color=palette["text_muted"]),
                            ],
                        ),
                    ],
                ),
            )
            history_rows.append(row_card)

        history_container.content = ft.Column(spacing=8, controls=history_rows)

    # Wire up the forward declaration
    _refresh_history_ui = _actual_refresh_history_ui

    def _build_broadcast_tab() -> ft.Control:
        stats = admin_state["cached_analytics"] or {}
        tot_u = stats.get("total_users", admin_state["total_users"])
        tot_devices = stats.get("total_device_tokens", 0)

        # ── Left: Composer Card ──────────────────────────────────────────────
        composer_card = ft.Container(
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=20,
            content=ft.Column(
                spacing=14,
                controls=[
                    # Header
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.CAMPAIGN_ROUNDED, size=20, color=palette["accent"]),
                            bgcolor=ft.Colors.with_opacity(0.12, palette["accent"]),
                            padding=8,
                            border_radius=8,
                        ),
                        ft.Column(
                            spacing=1,
                            controls=[
                                ft.Text("Push Notification Composer", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ft.Text("Multicast rich push alerts via OneSignal & Firebase FCM", size=11, color=palette["text_muted"]),
                            ],
                        ),
                    ], spacing=10),

                    # Reach Telemetry Pill
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.DEVICES_ROUNDED, size=14, color=palette["accent"]),
                            ft.Text(f"Registered Reach: ~{tot_devices:,} active devices across ~{tot_u:,} accounts.", size=11, color=palette["text"]),
                        ], spacing=6),
                        bgcolor=palette["surface_variant"],
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        border_radius=8,
                    ),

                    # Audience & Priority
                    ft.Row([
                        ft.Container(expand=2, content=push_audience_dropdown),
                        ft.Container(expand=1, content=push_priority_dropdown),
                    ], spacing=10),

                    # Title Input with live char counter
                    ft.Column([
                        ft.Row([
                            ft.Text("Title *", size=12, weight=ft.FontWeight.W_600, color=palette["text"]),
                            push_title_counter,
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        push_title_input,
                    ], spacing=4),

                    # Subtitle Input with live char counter
                    ft.Column([
                        ft.Row([
                            ft.Text("Subtitle (Optional)", size=12, weight=ft.FontWeight.W_600, color=palette["text_muted"]),
                            push_subtitle_counter,
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        push_subtitle_input,
                    ], spacing=4),

                    # Body Input with live char counter
                    ft.Column([
                        ft.Row([
                            ft.Text("Message Body *", size=12, weight=ft.FontWeight.W_600, color=palette["text"]),
                            push_body_counter,
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        push_body_input,
                    ], spacing=4),

                    # Banner Image URL
                    push_image_input,

                    # Action Route & Quick Chips
                    ft.Column([
                        ft.Text("In-App Deep Link Route", size=12, weight=ft.FontWeight.W_600, color=palette["text"]),
                        push_route_input,
                        ft.Row(
                            wrap=True,
                            spacing=6,
                            controls=[
                                ft.Text("Presets:", size=11, color=palette["text_muted"]),
                                *route_chips,
                            ],
                        ),
                    ], spacing=6),

                    # Action Button & TTL
                    ft.Row([
                        ft.Container(expand=1, content=push_button_label_input),
                        ft.Container(expand=1, content=push_ttl_dropdown),
                    ], spacing=10),

                    ft.Divider(color=palette["border"], height=8),

                    # Action Buttons Row
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.OutlinedButton(
                                content=ft.Row([
                                    test_btn_spinner,
                                    ft.Icon(ft.Icons.PHONELINK_RING_ROUNDED, size=16, color=palette["accent"]),
                                    ft.Text("Send Test to Me", size=12, color=palette["accent"], weight=ft.FontWeight.BOLD),
                                ], tight=True, spacing=6),
                                style=ft.ButtonStyle(
                                    side=ft.BorderSide(1.2, palette["accent"]),
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                                ),
                                on_click=_handle_send_test,
                            ),
                            ft.FilledButton(
                                content=ft.Row([
                                    broadcast_btn_spinner,
                                    ft.Icon(ft.Icons.SEND_ROUNDED, size=16, color=ft.Colors.WHITE),
                                    ft.Text("Broadcast Push Notification", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                                ], tight=True, spacing=6),
                                style=ft.ButtonStyle(
                                    bgcolor=palette["accent_glow"],
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.Padding.symmetric(horizontal=18, vertical=12),
                                ),
                                on_click=_handle_send_broadcast,
                            ),
                        ],
                    ),
                ],
            ),
        )

        # ── Right: Live Android Notification Shade Preview ───────────────────
        phone_preview_card = ft.Container(
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=20,
            content=ft.Column(
                spacing=14,
                controls=[
                    # Header
                    ft.Row([
                        ft.Icon(ft.Icons.PHONE_ANDROID_ROUNDED, size=18, color=palette["accent"]),
                        ft.Text("Live Android Notification Mockup", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ], spacing=8),
                    ft.Text(
                        "Real-time visual preview of how the notification renders on learner Android devices.",
                        size=11,
                        color=palette["text_muted"],
                    ),

                    # Simulated Android Phone Bezel Frame
                    ft.Container(
                        bgcolor="#0F172A" if is_dark else "#F1F5F9",
                        border=ft.Border.all(2, palette["border"]),
                        border_radius=18,
                        padding=12,
                        content=ft.Column(
                            spacing=10,
                            controls=[
                                # Android Status Bar
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text("10:00", size=11, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                                        ft.Row([
                                            ft.Icon(ft.Icons.WIFI_ROUNDED, size=12, color=palette["text_muted"]),
                                            ft.Icon(ft.Icons.SIGNAL_CELLULAR_4_BAR_ROUNDED, size=12, color=palette["text_muted"]),
                                            ft.Icon(ft.Icons.BATTERY_FULL_ROUNDED, size=12, color=palette["text_muted"]),
                                        ], spacing=4, tight=True),
                                    ],
                                ),

                                # Notification Card Inside Shade
                                ft.Container(
                                    bgcolor=palette["surface"],
                                    border=ft.Border.all(1, palette["border"]),
                                    border_radius=12,
                                    padding=12,
                                    content=ft.Column(
                                        spacing=6,
                                        controls=[
                                            # Header row: Icon, App Name, time
                                            ft.Row(
                                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                controls=[
                                                    ft.Row([
                                                        ft.Container(
                                                            width=20,
                                                            height=20,
                                                            border_radius=5,
                                                            bgcolor=palette["accent"],
                                                            alignment=ft.Alignment.CENTER,
                                                            content=ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=12, color=ft.Colors.WHITE),
                                                        ),
                                                        ft.Text("Nu-Age", size=12, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                                        ft.Text("• now", size=11, color=palette["text_muted"]),
                                                    ], spacing=6, tight=True),
                                                    ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, size=16, color=palette["text_muted"]),
                                                ],
                                            ),

                                            # Title
                                            preview_title,

                                            # Subtitle
                                            preview_subtitle,

                                            # Body
                                            preview_body,

                                            # Banner Image Container
                                            preview_image_container,

                                            # Action Button
                                            preview_action_btn,
                                        ],
                                    ),
                                ),

                                # Simulated Navigation Pill
                                ft.Container(
                                    alignment=ft.Alignment.CENTER,
                                    margin=ft.Margin.only(top=6),
                                    content=ft.Container(
                                        width=80,
                                        height=3,
                                        border_radius=2,
                                        bgcolor=palette["border"],
                                    ),
                                ),
                            ],
                        ),
                    ),

                    # Mockup Metadata Pill
                    ft.Container(
                        bgcolor=palette["surface_variant"],
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        border_radius=6,
                        content=ft.Row([
                            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=13, color=palette["accent"]),
                            preview_meta_badge,
                        ], spacing=6, tight=True),
                    ),

                    # Delivery channel info
                    ft.Text(
                        "Delivered over OneSignal REST API (external user ID targeting) and multi-channel Firebase Cloud Messaging.",
                        size=11,
                        color=palette["text_muted"],
                    ),
                ],
            ),
        )

        # ── Bottom: Audit Log & History Card ─────────────────────────────────
        history_card = ft.Container(
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=20,
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.HISTORY_ROUNDED, size=20, color=palette["accent"]),
                                ft.Column(
                                    spacing=1,
                                    controls=[
                                        ft.Text("Broadcast Audit Log & History", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                        ft.Text("Track previously dispatched notification broadcasts and delivery metrics", size=11, color=palette["text_muted"]),
                                    ],
                                ),
                            ], spacing=10),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH_ROUNDED,
                                tooltip="Refresh History",
                                on_click=lambda e: page.run_task(_fetch_broadcast_history),
                            ),
                        ],
                    ),
                    history_container,
                ],
            ),
        )

        # Build initial history UI
        _actual_refresh_history_ui()

        # Responsive layout: side-by-side on wide screens, stacked on narrow screens
        top_row = ft.ResponsiveRow(
            spacing=16,
            run_spacing=16,
            controls=[
                ft.Container(col={"xs": 12, "md": 7, "lg": 7}, content=composer_card),
                ft.Container(col={"xs": 12, "md": 5, "lg": 5}, content=phone_preview_card),
            ],
        )

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=16,
            controls=[
                top_row,
                history_card,
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
    # H2. TAB 5: STUDY PACK MARKETPLACE MANAGEMENT & UNIFIED REVIEW CONSOLE
    # ─────────────────────────────────────────────────────────────────────────

    def _build_study_packs_tab() -> ft.Control:
        subtab = admin_state["packs_subtab"]

        # Theme color palettes for gradient cards
        theme_colors_map = {
            "purple_indigo": ("#6366F1", "#8B5CF6"),
            "oceanic_blue": ("#0284C7", "#06B6D4"),
            "emerald_teal": ("#059669", "#10B981"),
            "sunset_orange": ("#EA580C", "#F59E0B"),
            "rose_amber": ("#E11D48", "#F43F5E"),
            "midnight_dark": ("#1E293B", "#334155"),
        }

        # Subtab counts
        pending_count = len(admin_state["cached_pending_packs"])
        approved_count = len(admin_state["cached_study_packs"])
        bundles_count = len(admin_state["cached_bundles"])

        def _set_subtab(st: str):
            admin_state["packs_subtab"] = st
            _render_tab_content()
            page.update()

        # Shared publisher for both AI and Manual CBT curator paths
        async def _on_publish_curated(final_data: dict):
            show_page_snackbar(page, "Publishing official curated CBT pack...")
            create_res = await create_official_curated_pack(
                token=admin_state["token"],
                title=final_data["title"],
                description=final_data.get("description") or f"Official {final_data.get('exam_type', 'CBT')} Past Questions with step-by-step solutions and diagram figures.",
                category=final_data.get("category", "General"),
                price_coins=final_data.get("price_coins", 0),
                theme_gradient=final_data.get("theme_gradient", "emerald_teal"),
                duration_minutes=final_data.get("duration_minutes", 60),
                questions=final_data["questions"],
            )
            if create_res.get("success") or create_res.get("id"):
                show_page_snackbar(page, "🎉 Curated CBT Pack published to Marketplace successfully!")
                await _fetch_study_packs()
            else:
                show_page_snackbar(page, f"Publish error: {create_res.get('error', 'Unknown')}")

        def _open_blank_cbt_curator():
            show_question_curator_dialog(
                page=page,
                initial_questions=[],
                pack_title="New Official CBT Pack",
                subject="General",
                exam_type="General CBT",
                exam_year=2025,
                initial_price_coins=0,
                initial_theme_gradient="emerald_teal",
                initial_description="Official past questions CBT practice pack with comprehensive solutions.",
                initial_duration_minutes=60,
                on_publish=lambda p_data: asyncio.create_task(_on_publish_curated(p_data)),
            )

        def _open_ai_cbt_ingest_modal():
            screen_w = page.width or 800
            screen_h = page.height or 800
            is_mobile = screen_w < 640

            subject_field = ft.TextField(label="Subject", value="Physics", dense=True, expand=True)
            exam_field = ft.TextField(label="Exam Board", value="General CBT", dense=True, width=140)
            year_field = ft.TextField(label="Exam Year", value="2024", dense=True, width=100)

            raw_text_field = ft.TextField(
                label="Extracted / Pasted Exam Questions Text",
                multiline=True,
                min_lines=6,
                max_lines=12,
                hint_text="Paste question text or upload a document file (PDF, DOCX, TXT, MD, Images)...\nExample:\n1. In the circuit shown below...\nA. 4 Ω\nB. 8 Ω\nAnswer: B",
            )

            status_text = ft.Text("", size=12, color=palette["accent"])
            uploaded_file_data = {"name": None, "bytes": None, "size_str": "", "char_count": 0}
            active_mode = ["file"]  # "file" or "text"
            show_text_preview = [False]

            # File Badge UI Elements (when a file is picked)
            file_badge_icon = ft.Icon(ft.Icons.DESCRIPTION_ROUNDED, size=24, color=palette["purple"])
            file_badge_name = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=palette["text"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
            file_badge_meta = ft.Text("", size=11, color=palette["text_muted"])
            file_badge_status = ft.Container(
                bgcolor=ui.tint(ui.C_CORRECT, 0.15),
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                content=ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=13, color=ui.C_CORRECT),
                    ft.Text("Ready for AI Processing", size=10.5, weight=ft.FontWeight.BOLD, color=ui.C_CORRECT),
                ], spacing=4, tight=True),
            )

            def _clear_uploaded_file(_=None):
                uploaded_file_data["name"] = None
                uploaded_file_data["bytes"] = None
                uploaded_file_data["size_str"] = ""
                uploaded_file_data["char_count"] = 0
                raw_text_field.value = ""
                _update_mode_ui()
                page.update()

            file_card_container = ft.Container(
                bgcolor=palette["surface"],
                border=ft.Border.all(1.2, ui.tint(palette["purple"], 0.4)),
                border_radius=10,
                padding=14,
                visible=False,
                content=ft.Row([
                    file_badge_icon,
                    ft.Column([
                        file_badge_name,
                        ft.Row([file_badge_meta, file_badge_status], spacing=8, tight=True),
                    ], spacing=3, expand=True),
                    ft.OutlinedButton(
                        "Change File",
                        icon=ft.Icons.REFRESH_ROUNDED,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            side=ft.BorderSide(1, palette["border"]),
                            color=palette["text"],
                        ),
                        on_click=lambda _: page.run_task(_pick_exam_file),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        icon_color=palette["danger"],
                        tooltip="Remove file",
                        on_click=_clear_uploaded_file,
                    ),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )

            # Clickable Empty Dropzone Container
            empty_dropzone = ft.Container(
                bgcolor=palette["surface_variant"],
                border=ft.Border.all(1.5, ui.tint(palette["purple"], 0.35)),
                border_radius=12,
                padding=ft.Padding.symmetric(horizontal=20, vertical=24),
                ink=True,
                on_click=lambda _: page.run_task(_pick_exam_file),
                content=ft.Column([
                    ft.Icon(ft.Icons.CLOUD_UPLOAD_ROUNDED, size=44, color=palette["purple"]),
                    ft.Text("Click to Upload Past Questions Document", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ft.Text(
                        "Select an exam document from your computer.\nSupports PDF, Word (.docx), Plain Text (.txt), Markdown (.md), or Exam Photos (.png, .jpg)",
                        size=11.5,
                        color=palette["text_muted"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=4),
                    ft.Row([
                        ft.FilledButton(
                            "Browse Exam File",
                            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                            style=ft.ButtonStyle(
                                bgcolor=palette["purple"],
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                            ),
                            on_click=lambda _: page.run_task(_pick_exam_file),
                        ),
                    ], alignment=ft.MainAxisAlignment.CENTER),
                ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )

            # Optional Text Preview Box under file upload
            preview_arrow = ft.Icon(ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED, size=18, color=palette["text_muted"])
            preview_text_container = ft.Container(visible=False, content=raw_text_field)

            def _toggle_preview(_=None):
                show_text_preview[0] = not show_text_preview[0]
                preview_arrow.name = ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED if show_text_preview[0] else ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED
                preview_text_container.visible = show_text_preview[0]
                page.update()

            preview_toggle_header = ft.Container(
                ink=True,
                on_click=_toggle_preview,
                padding=ft.Padding.symmetric(horizontal=6, vertical=4),
                visible=False,
                content=ft.Row([
                    ft.Icon(ft.Icons.VISIBILITY_OUTLINED, size=16, color=palette["purple"]),
                    ft.Text("Review / Edit Extracted Questions Text (Optional)", size=12, weight=ft.FontWeight.W_600, color=palette["text"]),
                    preview_arrow,
                ], spacing=6, tight=True),
            )

            # Paste Text Container (when in "text" mode)
            def _load_sample_paper():
                raw_text_field.value = (
                    "1. In the circuit diagram below, calculate the equivalent resistance between terminals X and Y.\n"
                    "A. 4 Ω\n"
                    "B. 8 Ω\n"
                    "C. 12 Ω\n"
                    "D. 16 Ω\n"
                    "Answer: B\n"
                    "Explanation: Resistors R1 (12Ω) and R2 (6Ω) are connected in parallel: (12*6)/(12+6) = 4Ω. Resistor R3 (4Ω) is in series: 4 + 4 = 8Ω.\n"
                    "Topic: Current Electricity\n\n"
                    "2. Which of the following organelles is primarily responsible for aerobic cellular respiration in eukaryotes?\n"
                    "A. Ribosome\n"
                    "B. Mitochondria\n"
                    "C. Golgi Apparatus\n"
                    "D. Lysosome\n"
                    "Answer: B\n"
                    "Explanation: Mitochondria generate most of the chemical energy needed to power the cell's biochemical reactions through ATP synthesis.\n"
                    "Topic: Cell Biology\n\n"
                    "3. A car accelerates uniformly from rest at 3 m/s² for 10 seconds. Find the total distance covered.\n"
                    "A. 150 m\n"
                    "B. 300 m\n"
                    "C. 75 m\n"
                    "D. 200 m\n"
                    "Answer: A\n"
                    "Explanation: Using s = ut + 0.5at²: since u = 0, s = 0.5 * 3 * (10)² = 0.5 * 3 * 100 = 150 m.\n"
                    "Topic: Mechanics"
                )
                page.update()

            sample_btn = ft.TextButton(
                "Load Sample Exam Paper",
                icon=ft.Icons.DESCRIPTION_OUTLINED,
                on_click=lambda _: _load_sample_paper(),
            )

            paste_mode_box = ft.Column([
                ft.Row([
                    ft.Text("Paste Unstructured Exam Questions Text:", size=12, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    sample_btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                raw_text_field,
            ], spacing=6, visible=False)

            file_mode_box = ft.Column([
                empty_dropzone,
                file_card_container,
                preview_toggle_header,
                preview_text_container,
            ], spacing=10, visible=True)

            def _update_mode_ui():
                is_file = (active_mode[0] == "file")
                file_mode_box.visible = is_file
                paste_mode_box.visible = not is_file

                has_file = bool(uploaded_file_data.get("name"))
                empty_dropzone.visible = not has_file
                file_card_container.visible = has_file
                preview_toggle_header.visible = has_file and bool(raw_text_field.value)
                if not has_file:
                    preview_text_container.visible = False
                    show_text_preview[0] = False

                # Update mode switcher pills
                mode_tab_file.bgcolor = ft.Colors.with_opacity(0.15, palette["purple"]) if is_file else ft.Colors.TRANSPARENT
                mode_tab_file.border = ft.Border.all(1.2, palette["purple"] if is_file else palette["border"])
                mode_tab_file_text.weight = ft.FontWeight.BOLD if is_file else ft.FontWeight.W_500
                mode_tab_file_text.color = palette["text"] if is_file else palette["text_muted"]
                mode_tab_file_icon.color = palette["purple"] if is_file else palette["text_muted"]

                mode_tab_text.bgcolor = ft.Colors.with_opacity(0.15, palette["purple"]) if not is_file else ft.Colors.TRANSPARENT
                mode_tab_text.border = ft.Border.all(1.2, palette["purple"] if not is_file else palette["border"])
                mode_tab_text_text.weight = ft.FontWeight.BOLD if not is_file else ft.FontWeight.W_500
                mode_tab_text_text.color = palette["text"] if not is_file else palette["text_muted"]
                mode_tab_text_icon.color = palette["purple"] if not is_file else palette["text_muted"]

            def _switch_mode(mode_val: str):
                active_mode[0] = mode_val
                _update_mode_ui()
                page.update()

            mode_tab_file_icon = ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, size=16, color=palette["purple"])
            mode_tab_file_text = ft.Text("Upload Document File", size=12.5, weight=ft.FontWeight.BOLD, color=palette["text"])
            mode_tab_file = ft.Container(
                content=ft.Row([mode_tab_file_icon, mode_tab_file_text], spacing=6, tight=True),
                bgcolor=ft.Colors.with_opacity(0.15, palette["purple"]),
                border=ft.Border.all(1.2, palette["purple"]),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                ink=True,
                on_click=lambda _: _switch_mode("file"),
            )

            mode_tab_text_icon = ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=16, color=palette["text_muted"])
            mode_tab_text_text = ft.Text("Paste Questions Text", size=12.5, weight=ft.FontWeight.W_500, color=palette["text_muted"])
            mode_tab_text = ft.Container(
                content=ft.Row([mode_tab_text_icon, mode_tab_text_text], spacing=6, tight=True),
                bgcolor=ft.Colors.TRANSPARENT,
                border=ft.Border.all(1.2, palette["border"]),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                ink=True,
                on_click=lambda _: _switch_mode("text"),
            )

            mode_switcher_row = ft.Row([mode_tab_file, mode_tab_text], spacing=8)

            async def _pick_exam_file(_=None):
                try:
                    files = await ft.FilePicker().pick_files(
                        file_type=ft.FilePickerFileType.CUSTOM,
                        allowed_extensions=["pdf", "docx", "txt", "md", "png", "jpg", "jpeg"],
                        with_data=True,
                    )
                    if not files:
                        return

                    f = files[0]
                    f_name = getattr(f, "name", None) or (os.path.basename(f.path) if getattr(f, "path", None) else "exam_document")
                    f_bytes = getattr(f, "bytes", None)
                    f_path = getattr(f, "path", None)

                    if not f_bytes and f_path:
                        try:
                            with open(f_path, "rb") as fp:
                                f_bytes = fp.read()
                        except Exception as read_err:
                            print(f"[File Read Error]: {read_err}")

                    f_size_str = ""
                    if f_bytes:
                        sz = len(f_bytes)
                        f_size_str = f"{sz / 1024:.1f} KB" if sz < 1024 * 1024 else f"{sz / (1024 * 1024):.1f} MB"

                    extracted_text = ""
                    ext = f_name.lower().split(".")[-1] if "." in f_name else ""

                    if ext == "pdf":
                        try:
                            import fitz
                            doc = fitz.open(stream=f_bytes, filetype="pdf") if f_bytes else (fitz.open(f_path) if f_path else None)
                            if doc:
                                for p in doc:
                                    extracted_text += p.get_text() + "\n"
                                doc.close()
                        except Exception as pdf_err:
                            show_page_snackbar(page, f"PDF text read: {pdf_err}")
                    elif ext == "docx":
                        try:
                            import io, zipfile, xml.etree.ElementTree as ET
                            data = f_bytes
                            if not data and f_path:
                                with open(f_path, "rb") as fp:
                                    data = fp.read()
                            if data:
                                with zipfile.ZipFile(io.BytesIO(data)) as z:
                                    xml_content = z.read("word/document.xml")
                                    tree = ET.fromstring(xml_content)
                                    texts = []
                                    for elem in tree.iter():
                                        if elem.tag.endswith('}t'):
                                            if elem.text:
                                                texts.append(elem.text)
                                        elif elem.tag.endswith('}p'):
                                            texts.append('\n')
                                    extracted_text = "".join(texts)
                        except Exception as docx_err:
                            show_page_snackbar(page, f"DOCX text read: {docx_err}")
                    elif ext in ["png", "jpg", "jpeg", "webp"]:
                        extracted_text = ""
                    else:
                        if f_bytes:
                            extracted_text = f_bytes.decode("utf-8", errors="ignore")
                        elif f_path:
                            with open(f_path, "r", encoding="utf-8", errors="ignore") as fp:
                                extracted_text = fp.read()

                    extracted_text = extracted_text.strip()
                    uploaded_file_data["name"] = f_name
                    uploaded_file_data["bytes"] = f_bytes
                    uploaded_file_data["size_str"] = f_size_str
                    uploaded_file_data["char_count"] = len(extracted_text)

                    # Update file card
                    file_badge_name.value = f_name
                    if ext == "pdf":
                        file_badge_icon.name = ft.Icons.PICTURE_AS_PDF_ROUNDED
                        file_badge_icon.color = palette["danger"]
                    elif ext in ["png", "jpg", "jpeg"]:
                        file_badge_icon.name = ft.Icons.IMAGE_ROUNDED
                        file_badge_icon.color = palette["accent"]
                    else:
                        file_badge_icon.name = ft.Icons.DESCRIPTION_ROUNDED
                        file_badge_icon.color = palette["purple"]

                    if extracted_text:
                        raw_text_field.value = extracted_text
                        file_badge_meta.value = f"{f_size_str} • {len(extracted_text):,} chars extracted"
                    elif ext in ["png", "jpg", "jpeg"]:
                        file_badge_meta.value = f"{f_size_str} • Image paper (AI Multimodal Transcription)"
                    else:
                        file_badge_meta.value = f"{f_size_str} • Ready for server parsing"

                    # Smart subject, exam, and year inference from filename
                    fn_lower = f_name.lower()
                    for subj in ["physics", "chemistry", "biology", "mathematics", "maths", "english", "economics", "government", "literature", "crk", "irk", "commerce", "accounting", "geography", "history", "civic", "agric", "computer"]:
                        if subj in fn_lower:
                            subject_field.value = "Mathematics" if subj == "maths" else ("Agricultural Science" if subj == "agric" else subj.title())
                            break
                    for ex in ["jamb", "utme", "waec", "wassce", "neco", "post-utme"]:
                        if ex in fn_lower:
                            if ex in ["jamb", "utme"]:
                                exam_field.value = "JAMB UTME"
                            elif ex in ["waec", "wassce"]:
                                exam_field.value = "WAEC WASSCE"
                            elif ex == "neco":
                                exam_field.value = "NECO SSCE"
                            break
                    import re
                    year_match = re.search(r'\b(20\d{2}|19\d{2})\b', f_name)
                    if year_match:
                        year_field.value = year_match.group(1)

                    _update_mode_ui()
                    page.update()
                except Exception as ex:
                    show_page_snackbar(page, f"File picker error: {ex}")

            parse_btn_content = ft.Row([
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.WHITE),
                ft.Text("Parse with AI Engine", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            ], spacing=6, tight=True)

            parse_btn = ft.FilledButton(
                content=parse_btn_content,
                style=ft.ButtonStyle(
                    bgcolor=palette["purple"],
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                ),
                on_click=lambda e: asyncio.create_task(_execute_parse(e)),
            )

            ingest_dlg_ref = [None]

            def _close_ingest(_=None):
                if ingest_dlg_ref[0]:
                    ingest_dlg_ref[0].open = False
                    page.update()

            async def _execute_parse(_):
                txt = (raw_text_field.value or "").strip()
                has_file = bool(uploaded_file_data.get("name") and uploaded_file_data.get("bytes"))

                if not txt and not has_file:
                    show_page_snackbar(page, "Please upload an exam document (PDF, DOCX, TXT, Images) or paste questions text.")
                    return

                status_text.value = "AI Engine is analyzing questions, diagrams & options..."
                parse_btn_content.controls[0] = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.WHITE)
                parse_btn_content.controls[1].value = "Analyzing Document..."
                parse_btn.disabled = True
                page.update()

                token = admin_state["token"]
                year_str = (year_field.value or "").strip()
                year_val = int(year_str) if year_str.isdigit() else 2024
                parsed_subj = (subject_field.value or "").strip() or "General"
                parsed_exam = (exam_field.value or "").strip() or "General CBT"

                # If text is present, parse text. If raw text empty but file uploaded, parse file.
                if txt:
                    res = await parse_past_questions_ai(
                        token=token,
                        raw_text=txt,
                        subject=parsed_subj,
                        exam_type=parsed_exam,
                        exam_year=year_val,
                    )
                else:
                    res = await parse_past_questions_file_ai(
                        token=token,
                        file_name=uploaded_file_data["name"],
                        file_bytes=uploaded_file_data["bytes"],
                        subject=parsed_subj,
                        exam_type=parsed_exam,
                        exam_year=year_val,
                    )

                if not res.get("success") and not res.get("questions"):
                    status_text.value = f"AI Extraction Failed: {res.get('error', 'Unknown error. Please check file format or try pasting text.')}"
                    status_text.color = ft.Colors.RED_400
                    parse_btn.disabled = False
                    parse_btn_content.controls[0] = ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color=ft.Colors.WHITE)
                    parse_btn_content.controls[1].value = "Analyze & Extract Questions"
                    page.update()
                    show_page_snackbar(page, f"AI Extraction Failed: {res.get('error', 'Unknown')}")
                    return

                _close_ingest()

                parsed_questions = res.get("questions", [])
                suggested_title = res.get("suggested_title") or f"{exam_field.value or 'CBT'} {year_field.value or ''} {subject_field.value or ''} CBT Pack"

                # Launch interactive Question Curator modal with AI extracted questions
                show_question_curator_dialog(
                    page=page,
                    initial_questions=parsed_questions,
                    pack_title=suggested_title,
                    subject=(subject_field.value or "").strip() or "General",
                    exam_type=(exam_field.value or "").strip() or "General CBT",
                    exam_year=year_val,
                    initial_price_coins=0,
                    initial_theme_gradient="emerald_teal",
                    initial_description=f"Official {exam_field.value or 'CBT'} Past Questions with step-by-step solutions and diagram figures.",
                    initial_duration_minutes=60,
                    on_publish=lambda p_data: asyncio.create_task(_on_publish_curated(p_data)),
                    token=token,
                )

            modal_w = min(740, int(screen_w * 0.95))
            modal_h = min(620, int(screen_h * 0.88))

            meta_inputs = (
                ft.Row([subject_field, exam_field, year_field], spacing=10)
                if not is_mobile
                else ft.Column([
                    subject_field,
                    ft.Row([exam_field, year_field], spacing=10),
                ], spacing=8)
            )

            dlg = ft.AlertDialog(
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=14),
                bgcolor=palette["card_bg"],
                title=ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.DOCUMENT_SCANNER_ROUNDED, color=palette["purple"], size=22),
                        ft.Text("AI Past Questions Ingestion", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ], tight=True, spacing=8),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, on_click=_close_ingest),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                content=ft.Container(
                    width=modal_w,
                    height=modal_h,
                    content=ft.Column([
                        ft.Container(
                            bgcolor=palette["surface_variant"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=8,
                            padding=10,
                            content=ft.Row([
                                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=palette["purple"]),
                                ft.Text(
                                    "Upload an exam document (PDF, Word DOCX, TXT, MD, Images) or paste questions text below. Our AI engine extracts questions, options A–E, solutions, topics, and diagrams into a structured CBT pack.",
                                    size=11,
                                    color=palette["text_muted"],
                                    expand=True,
                                ),
                            ], spacing=8),
                        ),
                        meta_inputs,
                        mode_switcher_row,
                        file_mode_box,
                        paste_mode_box,
                        status_text,
                    ], spacing=12, scroll=ft.ScrollMode.AUTO),
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=_close_ingest),
                    parse_btn,
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            ingest_dlg_ref[0] = dlg
            page.overlay.append(dlg)
            dlg.open = True
            page.update()


        def _open_cbt_mode_picker():
            choice_dlg_ref = [None]

            def _close_choice():
                if choice_dlg_ref[0]:
                    choice_dlg_ref[0].open = False
                    page.update()

            choice_dlg = ft.AlertDialog(
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=14),
                bgcolor=palette["card_bg"],
                title=ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=palette["purple"], size=22),
                    ft.Text("Curate Official CBT Pack", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                ], spacing=8),
                content=ft.Column([
                    ft.Text("Select your preferred preparation method for this CBT exam pack:", size=13, color=palette["text_muted"]),
                    ft.Container(height=4),
                    ft.Container(
                        bgcolor=palette["surface_variant"],
                        border=ft.Border.all(1.2, palette["purple"]),
                        border_radius=10,
                        padding=14,
                        ink=True,
                        on_click=lambda _: (_close_choice(), _open_ai_cbt_ingest_modal()),
                        content=ft.Row([
                            ft.Container(
                                content=ft.Icon(ft.Icons.DOCUMENT_SCANNER_ROUNDED, color=ft.Colors.WHITE, size=20),
                                bgcolor=palette["purple"],
                                padding=10,
                                border_radius=8,
                            ),
                            ft.Column([
                                ft.Text("AI Document & File Ingestion (Instant)", size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ft.Text("Upload exam documents (PDF, Word, TXT, MD, Images) or paste text to auto-extract with AI.", size=11, color=palette["text_muted"]),
                            ], spacing=3, expand=True),
                        ], spacing=12),
                    ),
                    ft.Container(
                        bgcolor=palette["surface_variant"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=10,
                        padding=14,
                        ink=True,
                        on_click=lambda _: (_close_choice(), _open_blank_cbt_curator()),
                        content=ft.Row([
                            ft.Container(
                                content=ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, color=palette["accent"], size=20),
                                bgcolor=ft.Colors.with_opacity(0.15, palette["accent"]),
                                padding=10,
                                border_radius=8,
                            ),
                            ft.Column([
                                ft.Text("Compose CBT Pack Manually", size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ft.Text("Build a clean exam paper question-by-question with options A-E, solutions, and custom duration.", size=11, color=palette["text_muted"]),
                            ], spacing=3, expand=True),
                        ], spacing=12),
                    ),
                ], spacing=10, tight=True),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _: _close_choice()),
                ],
            )
            choice_dlg_ref[0] = choice_dlg
            choice_dlg.open = True
            page.overlay.append(choice_dlg)
            page.update()

        # Bundle Creation & Editing Handlers
        async def _on_save_bundle(bundle_payload: dict):
            bundle_id = bundle_payload.get("id")
            if bundle_id:
                show_page_snackbar(page, "Updating study bundle...")
                res = await update_study_bundle_admin(
                    token=admin_state["token"],
                    bundle_id=str(bundle_id),
                    title=bundle_payload.get("title"),
                    description=bundle_payload.get("description"),
                    category=bundle_payload.get("category"),
                    pack_ids=bundle_payload.get("pack_ids"),
                    price_coins=bundle_payload.get("price_coins"),
                    discount_percentage=bundle_payload.get("discount_percentage"),
                    theme_gradient=bundle_payload.get("theme_gradient"),
                    banner_url=bundle_payload.get("banner_url"),
                )
                if res.get("success"):
                    show_page_snackbar(page, "🎉 Study bundle updated successfully!")
                    await _fetch_bundles()
                else:
                    show_page_snackbar(page, f"Failed to update bundle: {res.get('error', 'Unknown')}")
            else:
                show_page_snackbar(page, "Publishing new study bundle...")
                res = await create_study_bundle_admin(
                    token=admin_state["token"],
                    title=bundle_payload["title"],
                    description=bundle_payload.get("description", ""),
                    category=bundle_payload.get("category", "General"),
                    pack_ids=bundle_payload.get("pack_ids", []),
                    price_coins=bundle_payload.get("price_coins", 0),
                    discount_percentage=bundle_payload.get("discount_percentage", 0),
                    theme_gradient=bundle_payload.get("theme_gradient", "purple_indigo"),
                    banner_url=bundle_payload.get("banner_url"),
                )
                if res.get("success") or res.get("bundle_id"):
                    show_page_snackbar(page, "🎉 Study bundle created and published successfully!")
                    await _fetch_bundles()
                else:
                    show_page_snackbar(page, f"Failed to create bundle: {res.get('error', 'Unknown')}")

        def _open_bundle_builder_modal(existing_bundle=None):
            show_bundle_builder_dialog(
                page=page,
                available_packs=admin_state["cached_study_packs"],
                existing_bundle=existing_bundle,
                on_save=lambda b_data: asyncio.create_task(_on_save_bundle(b_data)),
            )

        def _build_admin_bundle_card(b: dict) -> ft.Container:
            bundle_id = str(b.get("id"))
            theme_key = b.get("theme_gradient", "purple_indigo")
            c1, c2 = theme_colors_map.get(theme_key, ("#6366F1", "#8B5CF6"))
            is_hidden = (b.get("status") == "hidden")

            admin_banner_url = b.get("banner_url")
            banner_img = None
            if admin_banner_url and str(admin_banner_url).strip():
                banner_img = ft.Container(
                    height=90,
                    border_radius=ft.BorderRadius.only(top_left=12, top_right=12),
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=ft.Image(
                        src=str(admin_banner_url).strip(),
                        height=90,
                        width=float("inf"),
                        fit=ft.BoxFit.COVER,
                    ),
                )

            banner_content = ft.Container(
                gradient=ft.LinearGradient(
                    begin=ft.Alignment.TOP_LEFT,
                    end=ft.Alignment.BOTTOM_RIGHT,
                    colors=[c1, c2],
                ),
                border_radius=ft.BorderRadius.only(top_left=12, top_right=12) if not banner_img else ft.BorderRadius.all(0),
                padding=ft.Padding.all(14),
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Text(f"{b.get('discount_percentage', 0)}% OFF", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=6,
                        ),
                        ft.Container(
                            content=ft.Row([
                                nu_coin_icon(size=12),
                                ft.Text(f"{b.get('price_coins', 0)} Coins", size=11, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                            ], spacing=3, tight=True),
                            bgcolor=palette["surface"],
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=6,
                        ),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(b.get("title", "Untitled Bundle"), size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"{b.get('category', 'General')} • {b.get('packs_count', 0)} Packs Included", size=11.5, color=ft.Colors.WHITE70),
                ], spacing=6),
            )

            async def _toggle_visibility(e):
                res = await toggle_admin_bundle_visibility(admin_state["token"], bundle_id)
                if "error" in res:
                    show_page_snackbar(page, f"Toggle visibility failed: {res['error']}")
                else:
                    show_page_snackbar(page, res.get("message", "Bundle visibility updated."))
                    await _fetch_bundles()

            def _confirm_delete_bundle():
                def _close_del():
                    del_dlg.open = False
                    page.update()

                async def _do_delete_bundle(btn):
                    btn.disabled = True
                    page.update()
                    res = await delete_admin_bundle(admin_state["token"], bundle_id)
                    _close_del()
                    if "error" in res:
                        show_page_snackbar(page, f"Deletion failed: {res['error']}")
                    else:
                        show_page_snackbar(page, res.get("message", "Bundle permanently deleted."))
                        await _fetch_bundles()

                del_dlg = ft.AlertDialog(
                    modal=True,
                    shape=ft.RoundedRectangleBorder(radius=14),
                    bgcolor=palette["card_bg"],
                    title=ft.Row([
                        ft.Icon(ft.Icons.DELETE_FOREVER_ROUNDED, color=palette["danger"], size=22),
                        ft.Text("Permanently Delete Bundle?", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ], spacing=8),
                    content=ft.Text(f"Are you sure you want to permanently delete '{b.get('title')}'? This action cannot be undone.", size=13, color=palette["text_muted"]),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _: _close_del()),
                        ft.FilledButton(
                            "Delete Bundle",
                            icon=ft.Icons.DELETE_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=palette["danger"], color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda ev: page.run_task(_do_delete_bundle, ev.control),
                        ),
                    ],
                )
                del_dlg.open = True
                page.overlay.append(del_dlg)
                page.update()

            pack_chips = []
            for p in b.get("packs", []):
                pack_chips.append(
                    ft.Container(
                        bgcolor=palette["surface_variant"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        content=ft.Text(p.get("title", ""), size=11, color=palette["text"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    )
                )

            status_pill = ft.Container(
                content=ft.Row([
                    ft.Container(width=6, height=6, border_radius=3, bgcolor=palette["warning"] if is_hidden else palette["success"]),
                    ft.Text("Hidden" if is_hidden else "Live in Store", size=10.5, weight=ft.FontWeight.BOLD, color=palette["warning"] if is_hidden else palette["success"]),
                ], spacing=5, tight=True),
                bgcolor=palette["warning_bg"] if is_hidden else palette["success_bg"],
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=6,
            )

            return ft.Container(
                col={"xs": 12, "sm": 6, "md": 4, "lg": 4},
                bgcolor=palette["card_bg"],
                border=ft.Border.all(1.2, palette["border"]),
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=ft.Column([
                    *( [banner_img] if banner_img else [] ),
                    banner_content,
                    ft.Container(
                        padding=14,
                        content=ft.Column([
                            ft.Row([
                                status_pill,
                                ft.Text(f"{b.get('downloads_count', 0)} Downloads", size=11, color=palette["text_muted"]),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Text(b.get("description") or "Multi-pack curated collection with bundled discount pricing.", size=12, color=palette["text_muted"], max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Row([
                                ft.Text(f"📚 {b.get('total_questions', 0)} Questions", size=11.5, weight=ft.FontWeight.W_600, color=palette["text"]),
                                ft.Text(f"⚡ {b.get('total_flashcards', 0)} Flashcards", size=11.5, weight=ft.FontWeight.W_600, color=palette["text"]),
                            ], spacing=10),
                            ft.Text("Constituent Study Packs:", size=11, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                            ft.Row(wrap=True, spacing=6, run_spacing=6, controls=pack_chips[:4] + ([ft.Text(f"+{len(pack_chips)-4} more", size=10, color=palette["accent"])] if len(pack_chips) > 4 else [])),
                            ft.Divider(height=1, color=palette["border"]),
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.Icons.VISIBILITY_ROUNDED if is_hidden else ft.Icons.VISIBILITY_OFF_ROUNDED,
                                    icon_color=palette["warning"] if is_hidden else palette["text_muted"],
                                    tooltip="Publish to store" if is_hidden else "Hide from store",
                                    icon_size=17,
                                    on_click=_toggle_visibility,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.EDIT_ROUNDED,
                                    icon_color=palette["accent"],
                                    tooltip="Edit Bundle Details & Packs",
                                    icon_size=17,
                                    on_click=lambda _, bundle_data=b: _open_bundle_builder_modal(existing_bundle=bundle_data),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                    icon_color=palette["danger"],
                                    tooltip="Permanently Delete Bundle",
                                    icon_size=17,
                                    on_click=lambda _: _confirm_delete_bundle(),
                                ),
                            ], alignment=ft.MainAxisAlignment.END, spacing=4),
                        ], spacing=10),
                    ),
                ], spacing=0),
            )

        subtab_bar = ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.PENDING_ACTIONS_ROUNDED, size=16, color=palette["accent"] if subtab == "pending" else palette["text_muted"]),
                    ft.Text(f"Pending Submissions ({pending_count})", size=13, weight=ft.FontWeight.BOLD if subtab == "pending" else ft.FontWeight.W_500, color=palette["text"] if subtab == "pending" else palette["text_muted"]),
                ], spacing=8, tight=True),
                bgcolor=ft.Colors.with_opacity(0.16, palette["accent"]) if subtab == "pending" else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1.2, palette["accent"] if subtab == "pending" else palette["border"]),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                ink=True,
                on_click=lambda _: _set_subtab("pending"),
            ),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.STORE_ROUNDED, size=16, color=palette["accent"] if subtab == "approved" else palette["text_muted"]),
                    ft.Text(f"Marketplace Catalog ({approved_count})", size=13, weight=ft.FontWeight.BOLD if subtab == "approved" else ft.FontWeight.W_500, color=palette["text"] if subtab == "approved" else palette["text_muted"]),
                ], spacing=8, tight=True),
                bgcolor=ft.Colors.with_opacity(0.16, palette["accent"]) if subtab == "approved" else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1.2, palette["accent"] if subtab == "approved" else palette["border"]),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                ink=True,
                on_click=lambda _: _set_subtab("approved"),
            ),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.COLLECTIONS_BOOKMARK_ROUNDED, size=16, color=palette["accent"] if subtab == "bundles" else palette["text_muted"]),
                    ft.Text(f"Study Bundles ({bundles_count})", size=13, weight=ft.FontWeight.BOLD if subtab == "bundles" else ft.FontWeight.W_500, color=palette["text"] if subtab == "bundles" else palette["text_muted"]),
                ], spacing=8, tight=True),
                bgcolor=ft.Colors.with_opacity(0.16, palette["accent"]) if subtab == "bundles" else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1.2, palette["accent"] if subtab == "bundles" else palette["border"]),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                ink=True,
                on_click=lambda _: _set_subtab("bundles"),
            ),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD_BOX_ROUNDED, size=16, color=ft.Colors.WHITE),
                    ft.Text("Compose Bundle", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ], spacing=6, tight=True),
                bgcolor=palette["accent"],
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                ink=True,
                on_click=lambda _: _open_bundle_builder_modal(),
            ),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.WHITE),
                    ft.Text("Curate CBT Pack", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ], spacing=6, tight=True),
                bgcolor=palette["purple"],
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                ink=True,
                on_click=lambda _: _open_cbt_mode_picker(),
            ),
        ], spacing=10, scroll=ft.ScrollMode.AUTO)

        # Content Area based on subtab
        if admin_state["is_loading_packs"] or admin_state["is_loading_bundles"]:
            body_content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(vertical=40),
                content=ft.Column([
                    ft.ProgressRing(width=32, height=32, stroke_width=3, color=palette["accent"]),
                    ft.Text("Synchronizing Study Content with Server…", size=12, color=palette["text_muted"]),
                ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True)
            )
        elif subtab == "pending":
            if not admin_state["cached_pending_packs"]:
                body_content = ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=60),
                    content=ft.Column([
                        ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=48, color=palette["success"]),
                        ft.Text("All Caught Up!", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text("No peer submissions are currently awaiting review.", size=12, color=palette["text_muted"]),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, tight=True)
                )
            else:
                pending_cards = []
                for pack in admin_state["cached_pending_packs"]:
                    pending_cards.append(_build_pending_pack_row(pack))
                body_content = ft.Column(spacing=12, controls=pending_cards)
        elif subtab == "bundles":
            if not admin_state["cached_bundles"]:
                body_content = ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=60),
                    content=ft.Column([
                        ft.Icon(ft.Icons.COLLECTIONS_BOOKMARK_OUTLINED, size=48, color=palette["accent"]),
                        ft.Text("No Study Bundles Created Yet", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text("Combine multiple study packs into high-value bundles with custom discounts.", size=12, color=palette["text_muted"]),
                        ft.FilledButton(
                            "+ Compose First Bundle",
                            icon=ft.Icons.ADD_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=palette["accent"], color=ft.Colors.WHITE),
                            on_click=lambda _: _open_bundle_builder_modal(),
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10, tight=True)
                )
            else:
                bundle_items = []
                for b in admin_state["cached_bundles"]:
                    bundle_items.append(_build_admin_bundle_card(b))
                body_content = ft.ResponsiveRow(spacing=16, run_spacing=16, controls=bundle_items)
        else:
            if not admin_state["cached_study_packs"]:
                body_content = ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=60),
                    content=ft.Column([
                        ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=48, color=palette["text_muted"]),
                        ft.Text("No Marketplace Packs Found", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text("Approved packs will appear here for live catalog maintenance.", size=12, color=palette["text_muted"]),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, tight=True)
                )
            else:
                catalog_items = []
                for pack in admin_state["cached_study_packs"]:
                    catalog_items.append(_build_admin_catalog_card(pack))
                body_content = ft.ResponsiveRow(spacing=16, run_spacing=16, controls=catalog_items)

        return ft.Container(
            expand=True,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=16,
                controls=[
                    # Header
                    ft.Container(
                        bgcolor=palette["card_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=14,
                        padding=20,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row([
                                    ft.Container(
                                        padding=ft.Padding.all(10),
                                        border_radius=10,
                                        bgcolor=ft.Colors.with_opacity(0.15, palette["accent"]),
                                        content=ft.Icon(ft.Icons.STOREFRONT_ROUNDED, size=24, color=palette["accent"]),
                                    ),
                                    ft.Column([
                                        ft.Text("Study Pack Marketplace Administration", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                        ft.Text("Review submissions, compose multi-pack bundles, curate CBT exams, and maintain catalog inventory.", size=12, color=palette["text_muted"]),
                                    ], spacing=2),
                                ], spacing=12),
                                ft.IconButton(
                                    icon=ft.Icons.REFRESH_ROUNDED,
                                    tooltip="Refresh Submissions, Bundles & Catalog",
                                    on_click=lambda _: page.run_task(_fetch_study_packs),
                                ),
                            ],
                        ),
                    ),
                    subtab_bar,
                    body_content,
                ],
            ),
        )

    def _build_pending_pack_row(pack: Dict[str, Any]) -> ft.Container:
        pack_id = str(pack.get("id"))
        title = pack.get("title", "Untitled")
        desc = pack.get("description", "No description provided.")
        category = pack.get("category", "General")
        creator = pack.get("creator", {})
        creator_name = creator.get("name", "Unknown Learner")
        stats = pack.get("stats", {})
        fc_count = stats.get("flashcards_count", 0)
        q_count = stats.get("questions_count", 0)

        async def _quick_approve(e):
            e.control.disabled = True
            page.update()
            res = await review_admin_submission(
                token=admin_state["token"],
                pack_id=pack_id,
                action="approve",
                reward_coins=50,
            )
            if "error" in res:
                show_page_snackbar(page, f"Approval failed: {res['error']}")
                e.control.disabled = False
                page.update()
            else:
                show_page_snackbar(page, "Study pack approved! Creator awarded 50 Nu-Coins.")
                await _fetch_study_packs()

        async def _quick_reject(e):
            e.control.disabled = True
            page.update()
            res = await review_admin_submission(
                token=admin_state["token"],
                pack_id=pack_id,
                action="reject",
                review_notes="Did not meet quality standards.",
            )
            if "error" in res:
                show_page_snackbar(page, f"Rejection failed: {res['error']}")
                e.control.disabled = False
                page.update()
            else:
                show_page_snackbar(page, "Submission rejected.")
                await _fetch_study_packs()

        return ft.Container(
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=12,
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row([
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                    border_radius=6,
                                    bgcolor=palette["surface_variant"],
                                    border=ft.Border.all(1, palette["border"]),
                                    content=ft.Text(category.upper(), size=9.5, weight=ft.FontWeight.W_800, color=palette["accent"]),
                                ),
                                ft.Text(f"Submitted by {creator_name}", size=12, color=palette["text_muted"]),
                            ], spacing=8),
                            ft.Row([
                                ft.Text(f"🎴 {fc_count} Flashcards", size=11.5, weight=ft.FontWeight.W_600, color=palette["text"]),
                                ft.Text("•", size=11, color=palette["text_muted"]),
                                ft.Text(f"📝 {q_count} Quiz MCQs", size=11.5, weight=ft.FontWeight.W_600, color=palette["text"]),
                            ], spacing=6),
                        ],
                    ),
                    ft.Column([
                        ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text(desc, size=12, color=palette["text_muted"], max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=4),
                    ft.Divider(color=palette["border"], height=1),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.FilledButton(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.AUTO_FIX_HIGH_ROUNDED, size=14, color=ft.Colors.WHITE),
                                    ft.Text("Review & Curate Pack", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ], spacing=6, tight=True),
                                style=ft.ButtonStyle(
                                    bgcolor=palette["accent"],
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                                ),
                                on_click=lambda _: _open_pack_inspector_dialog(pack, is_pending=True),
                            ),
                            ft.Row([
                                ft.OutlinedButton(
                                    "Reject",
                                    icon=ft.Icons.CLOSE_ROUNDED,
                                    style=ft.ButtonStyle(
                                        color=palette["danger"],
                                        side=ft.BorderSide(1, palette["danger"]),
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                    ),
                                    on_click=lambda e: page.run_task(_quick_reject, e),
                                ),
                                ft.FilledButton(
                                    "Quick Approve (50 Coins)",
                                    icon=ft.Icons.CHECK_ROUNDED,
                                    style=ft.ButtonStyle(
                                        bgcolor=palette["success"],
                                        color=ft.Colors.WHITE,
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                    ),
                                    on_click=lambda e: page.run_task(_quick_approve, e),
                                ),
                            ], spacing=8),
                        ],
                    ),
                ],
            ),
        )

    async def _open_existing_pack_curator(pack: Dict[str, Any]):
        pack_id = str(pack.get("id"))
        show_page_snackbar(page, f"Loading questions for '{pack.get('title')}'…")
        full_res = await fetch_admin_pack_full(admin_state["token"], pack_id)
        if "error" in full_res and not full_res.get("questions"):
            show_page_snackbar(page, f"Failed to load pack questions: {full_res.get('error')}")
            return

        async def _on_save_pack_curator_changes(updated_data: dict):
            show_page_snackbar(page, "Saving updated CBT questions & details…")
            up_res = await update_admin_pack(
                token=admin_state["token"],
                pack_id=pack_id,
                title=updated_data.get("title"),
                description=updated_data.get("description"),
                category=updated_data.get("category"),
                price_coins=updated_data.get("price_coins"),
                theme_gradient=updated_data.get("theme_gradient"),
                duration_minutes=updated_data.get("duration_minutes"),
                questions=updated_data.get("questions"),
            )
            if up_res.get("success"):
                show_page_snackbar(page, "🎉 CBT Pack questions updated successfully!")
                await _fetch_study_packs()
            else:
                show_page_snackbar(page, f"Failed to update pack: {up_res.get('error', 'Unknown')}")

        show_question_curator_dialog(
            page=page,
            initial_questions=full_res.get("questions", []),
            pack_title=full_res.get("title") or pack.get("title", ""),
            subject=full_res.get("category") or pack.get("category", "General"),
            exam_type=full_res.get("exam_type", "General CBT"),
            exam_year=full_res.get("exam_year"),
            initial_price_coins=full_res.get("price_coins", 0),
            initial_theme_gradient=full_res.get("theme_gradient", "emerald_teal"),
            initial_description=full_res.get("description", ""),
            initial_duration_minutes=full_res.get("duration_minutes", 60),
            on_publish=lambda p_data: asyncio.create_task(_on_save_pack_curator_changes(p_data)),
            token=admin_state["token"],
            save_button_label="Save & Update CBT Pack",
        )

    def _build_admin_catalog_card(pack: Dict[str, Any]) -> ft.Container:
        pack_id = str(pack.get("id"))
        status = pack.get("status", "approved")
        is_hidden = (status == "hidden")

        async def _toggle_visibility(e):
            e.control.disabled = True
            page.update()
            res = await toggle_admin_pack_visibility(admin_state["token"], pack_id)
            if "error" in res:
                show_page_snackbar(page, f"Visibility change failed: {res['error']}")
                e.control.disabled = False
                page.update()
            else:
                show_page_snackbar(page, res.get("message", "Pack visibility updated."))
                await _fetch_study_packs()

        def _confirm_delete(e):
            def _close_del_dlg():
                del_dlg.open = False
                page.update()

            async def _do_delete(btn):
                btn.disabled = True
                page.update()
                res = await delete_admin_pack(admin_state["token"], pack_id)
                _close_del_dlg()
                if "error" in res:
                    show_page_snackbar(page, f"Deletion failed: {res['error']}")
                else:
                    show_page_snackbar(page, res.get("message", "Study pack permanently deleted."))
                    await _fetch_study_packs()

            del_dlg = ft.AlertDialog(
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=16),
                bgcolor=palette["card_bg"],
                title=ft.Row([
                    ft.Icon(ft.Icons.DELETE_FOREVER_ROUNDED, color=palette["danger"], size=22),
                    ft.Text("Permanently Delete Pack?", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                ], spacing=8),
                content=ft.Text(
                    f"Are you sure you want to delete '{pack.get('title', 'this pack')}'? This will completely remove it from the catalog and vault databases. This action cannot be undone.",
                    size=13,
                    color=palette["text_muted"],
                ),
                actions=[
                    ft.TextButton(
                        content=ft.Text("Cancel", size=12.5, color=palette["text_muted"]),
                        on_click=lambda _: _close_del_dlg(),
                    ),
                    ft.FilledButton(
                        "Delete Permanently",
                        icon=ft.Icons.DELETE_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=palette["danger"], color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda ev: page.run_task(_do_delete, ev.control),
                    ),
                ],
            )
            del_dlg.open = True
            page.overlay.append(del_dlg)
            page.update()

        # Status badge indicator
        if is_hidden:
            status_badge = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.VISIBILITY_OFF_ROUNDED, size=11, color=palette["warning"]),
                    ft.Text("HIDDEN FROM STORE", size=9.5, weight=ft.FontWeight.W_800, color=palette["warning"]),
                ], spacing=4, tight=True),
                bgcolor=palette["warning_bg"],
                border=ft.Border.all(1, palette["warning"]),
                border_radius=ft.BorderRadius.all(6),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            )
        elif status == "approved":
            status_badge = ft.Container(
                content=ft.Row([
                    ft.Container(width=6, height=6, border_radius=3, bgcolor=palette["success"]),
                    ft.Text("LIVE IN STORE", size=9.5, weight=ft.FontWeight.W_800, color=palette["success"]),
                ], spacing=5, tight=True),
                bgcolor=palette["success_bg"],
                border=ft.Border.all(1, palette["success"]),
                border_radius=ft.BorderRadius.all(6),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            )
        else:
            status_badge = ft.Container(
                content=ft.Text(status.upper(), size=9.5, weight=ft.FontWeight.W_800, color=palette["text_muted"]),
                bgcolor=palette["surface_variant"],
                border=ft.Border.all(1, palette["border"]),
                border_radius=ft.BorderRadius.all(6),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            )

        return ft.Container(
            col={"sm": 12, "md": 6, "lg": 4},
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=ft.BorderRadius.all(18),
            padding=ft.Padding.all(10),
            content=ft.Column(
                spacing=10,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    # Dedicated Top Admin Command Strip (Clean separation; zero overlap with pack badges)
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                status_badge,
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.Icons.VISIBILITY_ROUNDED if is_hidden else ft.Icons.VISIBILITY_OFF_ROUNDED,
                                        icon_color=palette["warning"] if is_hidden else palette["text_muted"],
                                        bgcolor=palette["surface"],
                                        tooltip="Publish pack to live store" if is_hidden else "Hide pack from store",
                                        icon_size=16,
                                        width=32,
                                        height=32,
                                        on_click=lambda e: page.run_task(_toggle_visibility, e),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                                        icon_color=palette["purple"],
                                        bgcolor=palette["surface"],
                                        tooltip="Curate & Edit CBT Questions",
                                        icon_size=16,
                                        width=32,
                                        height=32,
                                        on_click=lambda _, p=pack: page.run_task(_open_existing_pack_curator, p),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_ROUNDED,
                                        icon_color=palette["accent"],
                                        bgcolor=palette["surface"],
                                        tooltip="Edit Title, Description & Pricing",
                                        icon_size=16,
                                        width=32,
                                        height=32,
                                        on_click=lambda _, p=pack: _open_pack_inspector_dialog(p, is_pending=False),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                        icon_color=palette["danger"],
                                        bgcolor=palette["surface"],
                                        tooltip="Permanently Delete Pack",
                                        icon_size=16,
                                        width=32,
                                        height=32,
                                        on_click=_confirm_delete,
                                    ),
                                ], spacing=4, tight=True),
                            ],
                        ),
                    ),
                    # Full Unobscured Study Pack Card
                    StudyPackCard(
                        pack=pack,
                        on_click_preview=lambda p: _open_pack_inspector_dialog(p, is_pending=False),
                    ),
                ],
            ),
        )

    def _open_pack_inspector_dialog(pack: Dict[str, Any], is_pending: bool = True):
        pack_id = str(pack.get("id"))
        category_val = [pack.get("category", "General")]

        # Cover art is no longer edited here. Keep the pack's existing cover if it
        # has one, otherwise fall back to the generic PNG so the backend always
        # receives a valid image URL.
        cover_url_to_submit = pack.get("cover_image_url") or DEFAULT_PACK_COVER_URL

        def _field_style(text_size: float = 13) -> dict:
            return dict(
                bgcolor=palette["surface"],
                border_color=palette["border"],
                focused_border_color=palette["accent"],
                border_radius=10,
                text_size=text_size,
                dense=True,
                expand=True,
                color=palette["text"],
                label_style=ft.TextStyle(size=12, color=palette["text_muted"]),
                hint_style=ft.TextStyle(size=12, color=palette["text_muted"]),
            )

        def _short(text: str, limit: int = 34) -> str:
            text = (text or "").strip()
            return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

        def _opt(key: str, label: str) -> ft.dropdown.Option:
            # Explicit text color so options stay readable on the dark menu
            return ft.dropdown.Option(
                key=key,
                text=_short(label),
                content=ft.Text(
                    _short(label),
                    size=12.5,
                    color=palette["text"],
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            )

        title_input = ft.TextField(
            label="Pack Title *",
            value=pack.get("title", ""),
            **_field_style(13),
        )

        desc_input = ft.TextField(
            label="Curated Description *",
            value=pack.get("description", ""),
            multiline=True,
            min_lines=2,
            max_lines=3,
            **_field_style(12.5),
        )

        reward_input = ft.TextField(
            label="Nu-Coin Reward to Creator",
            value="50",
            **_field_style(12),
        )

        notes_input = ft.TextField(
            label="Review Notes / Rejection Reason",
            hint_text="Feedback sent to learner in notification...",
            **_field_style(12),
        )

        category_dropdown = ft.Dropdown(
            label="Subject Category",
            value=category_val[0],
            options=[_opt(k, k) for k in CATEGORY_PRESETS.keys()],
            menu_height=220,
            **_field_style(12.5),
        )
        category_dropdown.on_select = lambda e: category_val.__setitem__(0, e.control.value)

        price_dropdown = ft.Dropdown(
            label="Pricing",
            value=str(pack.get("price_coins", 0)),
            options=[
                _opt("0", "Free (0 Coins)"),
                _opt("20", "20 Nu-Coins"),
                _opt("50", "50 Nu-Coins"),
                _opt("100", "100 Nu-Coins"),
                _opt("200", "200 Nu-Coins"),
            ],
            menu_height=220,
            **_field_style(12.5),
        )

        official_switch = ft.Switch(
            value=bool(pack.get("is_official", False)),
            active_color=palette["accent"],
        )
        official_row = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            border_radius=10,
            bgcolor=palette["surface"],
            border=ft.Border.all(1, palette["border"]),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=18, color=palette["accent"]),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                expand=True,
                                controls=[
                                    ft.Text("Official Nu Age pack", size=12.5, weight=ft.FontWeight.W_700, color=palette["text"]),
                                    ft.Text(
                                        "Shows the Official badge and lists it under the Official filter.",
                                        size=11,
                                        color=palette["text_muted"],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    official_switch,
                ],
            ),
        )

        inspector_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=palette["card_bg"],
            content_padding=ft.Padding.all(22),
            title=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.TUNE_ROUNDED, size=20, color=palette["accent"]),
                    bgcolor=ft.Colors.with_opacity(0.14, palette["accent"]),
                    padding=8,
                    border_radius=10,
                ),
                ft.Text(
                    "Review & Curate Study Pack" if is_pending else "Edit Marketplace Pack",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=palette["text"],
                ),
            ], spacing=10),
        )

        def _close_dlg():
            inspector_dlg.open = False
            page.update()

        async def _do_approve(e):
            e.control.disabled = True
            page.update()
            reward_val = 50
            try:
                reward_val = int(reward_input.value.strip())
            except Exception:
                reward_val = 50

            price_val = 0
            try:
                price_val = int(price_dropdown.value or 0)
            except Exception:
                price_val = 0

            res = await review_admin_submission(
                token=admin_state["token"],
                pack_id=pack_id,
                action="approve",
                reward_coins=reward_val,
                title=title_input.value.strip(),
                description=desc_input.value.strip(),
                category=category_dropdown.value,
                price_coins=price_val,
                cover_image_url=cover_url_to_submit,
                is_official=bool(official_switch.value),
                review_notes=notes_input.value.strip() if notes_input.value else "Approved by Admin",
            )
            _close_dlg()
            if "error" in res:
                show_page_snackbar(page, f"Approval error: {res['error']}")
            else:
                show_page_snackbar(page, "Pack approved and published to the catalog!")
                await _fetch_study_packs()

        async def _do_reject(e):
            e.control.disabled = True
            page.update()
            res = await review_admin_submission(
                token=admin_state["token"],
                pack_id=pack_id,
                action="reject",
                review_notes=notes_input.value.strip() if notes_input.value else "Did not meet quality requirements.",
            )
            _close_dlg()
            if "error" in res:
                show_page_snackbar(page, f"Rejection error: {res['error']}")
            else:
                show_page_snackbar(page, "Submission rejected.")
                await _fetch_study_packs()

        async def _do_save_existing(e):
            e.control.disabled = True
            page.update()
            price_val = 0
            try:
                price_val = int(price_dropdown.value or 0)
            except Exception:
                price_val = 0

            res = await update_admin_pack(
                token=admin_state["token"],
                pack_id=pack_id,
                title=title_input.value.strip(),
                description=desc_input.value.strip(),
                category=category_dropdown.value,
                price_coins=price_val,
                cover_image_url=cover_url_to_submit,
                is_official=bool(official_switch.value),
            )
            _close_dlg()
            if "error" in res:
                show_page_snackbar(page, f"Save error: {res['error']}")
            else:
                show_page_snackbar(page, "Pack details updated successfully!")
                await _fetch_study_packs()

        # Build actions (styled like the other buttons on this page)
        cancel_btn = ft.TextButton(
            content=ft.Text("Cancel", size=12.5, weight=ft.FontWeight.W_600, color=palette["text_muted"]),
            on_click=lambda _: _close_dlg(),
        )
        if is_pending:
            action_buttons = [
                cancel_btn,
                ft.OutlinedButton(
                    "Reject",
                    icon=ft.Icons.CLOSE_ROUNDED,
                    style=ft.ButtonStyle(
                        color=palette["danger"],
                        side=ft.BorderSide(1, palette["danger"]),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=lambda e: page.run_task(_do_reject, e),
                ),
                ft.FilledButton(
                    "Approve & Publish",
                    icon=ft.Icons.CHECK_ROUNDED,
                    style=ft.ButtonStyle(
                        bgcolor=palette["success"],
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=lambda e: page.run_task(_do_approve, e),
                ),
            ]
        else:
            is_currently_hidden = (pack.get("status") == "hidden")

            async def _dlg_toggle_visibility(e):
                _close_dlg()
                res = await toggle_admin_pack_visibility(admin_state["token"], pack_id)
                if "error" in res:
                    show_page_snackbar(page, f"Visibility change failed: {res['error']}")
                else:
                    show_page_snackbar(page, res.get("message", "Pack visibility updated."))
                    await _fetch_study_packs()

            def _dlg_confirm_delete(e):
                _close_dlg()

                def _close_del():
                    d_dlg.open = False
                    page.update()

                async def _do_del_pack(btn):
                    btn.disabled = True
                    page.update()
                    res = await delete_admin_pack(admin_state["token"], pack_id)
                    _close_del()
                    if "error" in res:
                        show_page_snackbar(page, f"Delete failed: {res['error']}")
                    else:
                        show_page_snackbar(page, res.get("message", "Pack permanently deleted."))
                        await _fetch_study_packs()

                d_dlg = ft.AlertDialog(
                    modal=True,
                    shape=ft.RoundedRectangleBorder(radius=16),
                    bgcolor=palette["card_bg"],
                    title=ft.Row([
                        ft.Icon(ft.Icons.DELETE_FOREVER_ROUNDED, color=palette["danger"], size=22),
                        ft.Text("Permanently Delete Pack?", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ], spacing=8),
                    content=ft.Text(
                        f"Are you sure you want to permanently delete '{pack.get('title', 'this pack')}'? This action cannot be undone.",
                        size=13,
                        color=palette["text_muted"],
                    ),
                    actions=[
                        ft.TextButton(
                            content=ft.Text("Cancel", size=12.5, color=palette["text_muted"]),
                            on_click=lambda _: _close_del(),
                        ),
                        ft.FilledButton(
                            "Delete Permanently",
                            icon=ft.Icons.DELETE_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=palette["danger"], color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda ev: page.run_task(_do_del_pack, ev.control),
                        ),
                    ],
                )
                d_dlg.open = True
                page.overlay.append(d_dlg)
                page.update()

            action_buttons = [
                ft.OutlinedButton(
                    "Delete Pack",
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    style=ft.ButtonStyle(
                        color=palette["danger"],
                        side=ft.BorderSide(1, palette["danger"]),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=_dlg_confirm_delete,
                ),
                ft.OutlinedButton(
                    "Publish to Store" if is_currently_hidden else "Hide from Store",
                    icon=ft.Icons.VISIBILITY_ROUNDED if is_currently_hidden else ft.Icons.VISIBILITY_OFF_ROUNDED,
                    style=ft.ButtonStyle(
                        color=palette["warning"] if not is_currently_hidden else palette["success"],
                        side=ft.BorderSide(1, palette["warning"] if not is_currently_hidden else palette["success"]),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=lambda e: page.run_task(_dlg_toggle_visibility, e),
                ),
                cancel_btn,
                ft.FilledButton(
                    "Save Pack Updates",
                    icon=ft.Icons.SAVE_ROUNDED,
                    style=ft.ButtonStyle(
                        bgcolor=palette["accent_glow"],
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=lambda e: page.run_task(_do_save_existing, e),
                ),
            ]

        dlg_width = min(page.width - 32, 540) if page.width else 500
        inspector_dlg.content = ft.Container(
            width=dlg_width,
            content=ft.Column(
                tight=True,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    title_input,
                    desc_input,
                    ft.Row([
                        ft.Container(expand=1, content=category_dropdown),
                        ft.Container(expand=1, content=price_dropdown),
                    ], spacing=10),
                    official_row,
                    # Curate CBT Questions direct action button
                    *(
                        [
                            ft.Container(
                                padding=ft.Padding.only(top=4),
                                content=ft.FilledButton(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.WHITE),
                                        ft.Text("Launch Question Curator & CBT Editor Studio", size=12.5, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                                    style=ft.ButtonStyle(
                                        bgcolor=palette["purple"],
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                                    ),
                                    on_click=lambda _: (_close_dlg(), page.run_task(_open_existing_pack_curator, pack)),
                                ),
                            )
                        ] if not is_pending else []
                    ),
                    # Additional fields if pending
                    *(
                        [
                            ft.Row([
                                ft.Container(expand=1, content=reward_input),
                                ft.Container(expand=2, content=notes_input),
                            ], spacing=10)
                        ] if is_pending else []
                    ),
                ],
            ),
        )
        inspector_dlg.actions = action_buttons
        inspector_dlg.open = True
        page.overlay.append(inspector_dlg)
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # STORE CATALOG STUDIO
    # ─────────────────────────────────────────────────────────────────────────

    async def _fetch_store_products():
        admin_state["is_loading_store"] = True
        _render_tab_content()
        page.update()
        try:
            token = admin_state.get("token") or ""
            prods = await get_admin_store_products(token)
            admin_state["store_products"] = prods or []
            # Also fetch PostgreSQL org plans
            org_plans = await get_admin_org_plans(token)
            admin_state["admin_org_plans"] = org_plans or []
        except Exception as ex:
            print(f"[STORE_STUDIO] Error fetching products: {ex}")
            show_page_snackbar(page, f"Failed to load store products: {ex}")
        finally:
            admin_state["is_loading_store"] = False
            nav_container.content = _build_nav_bar()
            _render_tab_content()
            page.update()

    def _show_store_product_dialog(prod=None):
        initial_cat = prod.get("category", "booster") if prod else "booster"
        selected_cat = [initial_cat]
        slug_manually_edited = [bool(prod)]

        # --- Base Fields ---
        name_input = ft.TextField(
            label="Product Name",
            hint_text="e.g. Institution Growth Plan, Midterm Booster",
            value=prod.get("name", "") if prod else "",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )
        id_input = ft.TextField(
            label="Product ID / Slug (Unique identifier)",
            hint_text="e.g. org_growth_annual, booster_pack",
            value=prod.get("id", "") if prod else "",
            disabled=bool(prod),
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )

        def _on_slug_change(e):
            slug_manually_edited[0] = True
        id_input.on_change = _on_slug_change

        def _on_name_change(e):
            if not prod and not slug_manually_edited[0]:
                import re
                raw = re.sub(r'[^a-zA-Z0-9\s_-]', '', name_input.value or '').strip().lower()
                id_input.value = re.sub(r'[\s-]+', '_', raw)
                try:
                    id_input.update()
                except Exception:
                    page.update()
        name_input.on_change = _on_name_change

        price_input = ft.TextField(
            label="Price (₦ NGN)",
            hint_text="e.g. 50000",
            value=str(int(prod.get("price", 1000))) if prod else "1000",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )
        badge_input = ft.TextField(
            label="Badge Tag (Optional)",
            hint_text="e.g. MOST POPULAR, INSTITUTION CHOICE, BEST VALUE",
            value=prod.get("badge") or "" if prod else "",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )
        VALID_INTERVAL_OPTIONS = [
            ("one-time", "One-Time (No renewal)"),
            ("month", "Monthly (Renews 30d)"),
            ("quarter", "Quarterly (Renews 90d)"),
            ("year", "Yearly (Renews 365d)"),
        ]

        init_interval = prod.get("interval", "one-time") if prod else ("month" if initial_cat in ("plan", "org_plan") else "one-time")
        if init_interval not in [o[0] for o in VALID_INTERVAL_OPTIONS]:
            init_interval = "month" if initial_cat in ("plan", "org_plan") else "one-time"

        interval_dd = ft.Dropdown(
            label="Billing Cycle",
            value=init_interval,
            options=[ft.dropdown.Option(k, v) for k, v in VALID_INTERVAL_OPTIONS],
            border_color=palette["border"],
            bgcolor=palette["surface"],
            text_size=12,
            disabled=(initial_cat in ("booster", "coins", "org_seats")),
            expand=True,
        )
        desc_input = ft.TextField(
            label="Short Description",
            hint_text="Engaging one or two sentence marketing summary shown to buyers.",
            multiline=True,
            min_lines=2,
            max_lines=3,
            value=prod.get("description") or "" if prod else "",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
        )
        order_input = ft.TextField(
            label="Catalog Display Order (Lower appears first)",
            value=str(prod.get("display_order", 10)) if prod else "10",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )
        features_input = ft.TextField(
            label="Marketing Feature Bullet Points (1 per line)",
            hint_text="e.g.\nAI Course Drafting Engine\nCohort CBT & Timed Exams\nUp to 50 Student Seats",
            multiline=True,
            min_lines=3,
            max_lines=5,
            value="\n".join(prod.get("features", [])) if prod else "",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
        )
        active_switch = ft.Switch(
            label="Active in Learner Storefront",
            value=prod.get("is_active", True) if prod else True,
            active_color=palette["accent"],
        )

        # --- Scholar Plan Quota Fields ---
        plan_materials_input = ft.TextField(
            label="Material Upload Slots Cap",
            hint_text="e.g. 25 for Free, 45 for Pro",
            value=str(prod.get("materials_limit", 45)) if (prod and prod.get("materials_limit") is not None) else ("45" if initial_cat == "plan" else ""),
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )
        plan_generations_input = ft.TextField(
            label="Monthly AI Generations Quota",
            hint_text="e.g. 40 for Free, 100 for Pro",
            value=str(prod.get("generations_limit", 100)) if (prod and prod.get("generations_limit") is not None) else ("100" if initial_cat == "plan" else ""),
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )
        plan_exam_input = ft.TextField(
            label="Practice Exam Simulations Quota",
            hint_text="e.g. 10 for Free, 40 for Pro",
            value=str(prod.get("exam_quota", 40)) if (prod and prod.get("exam_quota") is not None) else ("40" if initial_cat == "plan" else ""),
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )

        # --- Study Booster & Nu-Coins Fields ---
        mats_input = ft.TextField(
            label="+ Bonus Material Slots",
            value=str(prod.get("bonus_materials", 0)) if prod else "0",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )
        gens_input = ft.TextField(
            label="+ Bonus AI Generations",
            value=str(prod.get("bonus_generations", 0)) if prod else "0",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )
        coins_input = ft.TextField(
            label="+ Bonus Nu-Coins",
            value=str(prod.get("bonus_coins", 0)) if prod else "0",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )

        # --- Org Plan & Org Seats Fields ---
        max_members_input = ft.TextField(
            label="Max Student / Member Seats",
            value=str(prod.get("org_seats", 50)) if prod else "50",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )
        max_courses_input = ft.TextField(
            label="Max Hosted Courses",
            value="20",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )
        seat_count_input = ft.TextField(
            label="Additional Seats in Pack",
            value=str(prod.get("org_seats", 10)) if prod else "10",
            border_color=palette["border"],
            text_style=ft.TextStyle(color=palette["text"]),
            expand=True,
        )

        # Feature Toggles for Org Plans
        prod_feats = [f.lower() for f in prod.get("features", [])] if prod else []
        has_ai_init = any("ai course" in f or "ai drafting" in f for f in prod_feats) if prod else True
        has_cbt_init = any("cbt" in f or "exam" in f for f in prod_feats) if prod else True
        has_analytics_init = any("analytic" in f or "gradebook" in f for f in prod_feats) if prod else True
        has_branding_init = any("brand" in f or "certificate" in f for f in prod_feats) if prod else False

        ai_drafting_switch = ft.Switch(
            label="AI Course Drafting (Gemini Engine)",
            value=has_ai_init,
            active_color=palette["accent"],
        )
        cbt_switch = ft.Switch(
            label="Cohort CBT & Timed Exam Engine",
            value=has_cbt_init,
            active_color=palette["accent"],
        )
        analytics_switch = ft.Switch(
            label="Cohort Gradebook & Performance Analytics",
            value=has_analytics_init,
            active_color=palette["accent"],
        )
        branding_switch = ft.Switch(
            label="Custom Institution Branding & Certificates",
            value=has_branding_init,
            active_color=palette["accent"],
        )

        # DB Plans list dropdown
        db_plans = admin_state.get("admin_org_plans", [])
        db_options = [ft.dropdown.Option("new", "✨ Create New Plan in PostgreSQL")]
        matched_db_id = prod.get("plan_id") if prod else None
        for dp in db_plans:
            dp_id = str(dp.get("id"))
            dp_title = f"{dp.get('name', 'Plan')} (₦{int(dp.get('price', 0)):,} · {dp.get('max_members', 50)} seats · {dp.get('max_courses', 20)} courses)"
            db_options.append(ft.dropdown.Option(dp_id, dp_title))
            if prod and (prod.get("name") == dp.get("name") or prod.get("plan_id") == dp_id):
                matched_db_id = dp_id

        def _on_db_plan_selected(e):
            sel_id = getattr(getattr(e, "control", None), "value", None) or db_plan_dropdown.value or getattr(e, "data", None)
            if sel_id and sel_id != "new":
                for dp in db_plans:
                    if str(dp.get("id")) == sel_id:
                        name_input.value = dp.get("name", "")
                        price_input.value = str(int(dp.get("price", 0)))
                        max_members_input.value = str(dp.get("max_members", 50))
                        max_courses_input.value = str(dp.get("max_courses", 20))
                        if dp.get("description"):
                            desc_input.value = dp.get("description")
                        dp_feats = dp.get("features", [])
                        if dp_feats:
                            features_input.value = "\n".join(dp_feats)
                            dp_feats_lower = [f.lower() for f in dp_feats]
                            ai_drafting_switch.value = any("ai course" in f or "ai drafting" in f for f in dp_feats_lower)
                            cbt_switch.value = any("cbt" in f or "exam" in f for f in dp_feats_lower)
                            analytics_switch.value = any("analytic" in f or "gradebook" in f for f in dp_feats_lower)
                            branding_switch.value = any("brand" in f or "certif" in f for f in dp_feats_lower)
                        try:
                            edit_dlg.update()
                        except Exception:
                            page.update()
                        break

        db_plan_dropdown = ft.Dropdown(
            label="Synchronize with PostgreSQL Organisation Plan",
            options=db_options,
            value=matched_db_id if matched_db_id else "new",
            border_color=palette["border"],
            expand=True,
            on_select=_on_db_plan_selected,
        )

        # Quick Perk helper
        def _append_perk(text: str):
            curr = [l.strip() for l in (features_input.value or "").split("\n") if l.strip()]
            if text not in curr:
                curr.append(text)
                features_input.value = "\n".join(curr)
                try:
                    features_input.update()
                except Exception:
                    page.update()

        category_cards_container = ft.Container()

        def _build_category_content():
            cat = selected_cat[0]
            if cat == "plan":
                return ft.Container(
                    bgcolor=palette["surface_variant"],
                    border=ft.Border.all(1, palette["border"]),
                    border_radius=12,
                    padding=ft.Padding.all(14),
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=18, color=palette["accent"]),
                                ft.Text("Scholar Plan Entitlement Quotas & Baseline Limits", size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ], spacing=8),
                            ft.Row([plan_materials_input, plan_generations_input], spacing=10),
                            ft.Row([plan_exam_input], spacing=10),
                            ft.Text(
                                "Authoritative baseline limits for active subscribers. Upload slots persist; AI generations & exam simulation quotas reset only when the subscriber pays to renew their billing cycle.",
                                size=11,
                                color=palette["text_muted"],
                            ),
                            ft.Divider(height=1, color=palette["border"]),
                            ft.Row([
                                ft.Icon(ft.Icons.CARD_GIFTCARD_ROUNDED, size=16, color=palette["accent"]),
                                ft.Text("Optional Plan Sign-up / Renewal Bonus Perks", size=12, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ], spacing=6),
                            ft.Row([mats_input, gens_input, coins_input], spacing=10),
                        ],
                    ),
                )
            elif cat == "org_plan":
                return ft.Container(
                    bgcolor=palette["surface_variant"],
                    border=ft.Border.all(1, palette["border"]),
                    border_radius=12,
                    padding=ft.Padding.all(14),
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=18, color=palette["accent"]),
                                ft.Text("Organisation Plan Quotas & Authoritative Perks", size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ], spacing=8),
                            ft.Row([db_plan_dropdown]),
                            ft.Row([max_members_input, max_courses_input], spacing=10),
                            ft.Divider(height=1, color=palette["border"]),
                            ft.Text("Authoritative Institutional Perks:", size=11.5, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                            ft.Container(
                                padding=ft.Padding.all(10),
                                bgcolor=ft.Colors.with_opacity(0.06, palette["accent"]),
                                border_radius=8,
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, palette["accent"])),
                                content=ft.Column(
                                    spacing=4,
                                    controls=[
                                        ai_drafting_switch,
                                        ft.Text(
                                            "Allows educators to automatically generate modular courses with AI. Preexisting orgs are grandfathered; new orgs require this perk on their plan.",
                                            size=10.5,
                                            color=palette["text_muted"],
                                        ),
                                    ],
                                ),
                            ),
                            ft.Row([
                                ft.Container(expand=1, content=cbt_switch),
                                ft.Container(expand=1, content=analytics_switch),
                            ], spacing=10),
                            ft.Row([branding_switch]),
                        ],
                    ),
                )
            elif cat == "org_seats":
                return ft.Container(
                    bgcolor=palette["surface_variant"],
                    border=ft.Border.all(1, palette["border"]),
                    border_radius=12,
                    padding=ft.Padding.all(14),
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.GROUPS_ROUNDED, size=18, color=palette["accent"]),
                                ft.Text("Organisation Seat Booster Pack", size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ], spacing=8),
                            ft.Row([seat_count_input]),
                            ft.Text(
                                "Organisations purchase seat booster packs to expand their cohort capacity without changing plan tiers.",
                                size=11,
                                color=palette["text_muted"],
                            ),
                        ],
                    ),
                )
            else:
                return ft.Container(
                    bgcolor=palette["surface_variant"],
                    border=ft.Border.all(1, palette["border"]),
                    border_radius=12,
                    padding=ft.Padding.all(14),
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.TOKEN_ROUNDED, size=18, color=palette["accent"]),
                                ft.Text("Learner Balance & Quota Credits", size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ], spacing=8),
                            ft.Row([mats_input, gens_input, coins_input], spacing=10),
                            ft.Text(
                                "Credits are added on top of the student's existing account balances upon verified payment.",
                                size=11,
                                color=palette["text_muted"],
                            ),
                        ],
                    ),
                )

        category_cards_container.content = _build_category_content()

        # Category Pill Selector
        cat_meta = [
            ("plan", "Scholar Plan", ft.Icons.SCHOOL_ROUNDED),
            ("booster", "Study Booster", ft.Icons.ROCKET_LAUNCH_ROUNDED),
            ("coins", "Nu-Coins Pack", lambda: nu_coin_icon(size=15)),
            ("org_plan", "Org Plan", ft.Icons.BUSINESS_ROUNDED),
            ("org_seats", "Org Seats", ft.Icons.GROUPS_ROUNDED),
        ]

        cat_selector_row = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8)

        def _refresh_cat_pills():
            pills = []
            for c_key, c_name, c_icon in cat_meta:
                is_sel = selected_cat[0] == c_key
                icon_ctrl = c_icon() if callable(c_icon) else (c_icon if isinstance(c_icon, ft.Control) else ft.Icon(c_icon, size=15, color=ft.Colors.BLACK if is_sel else palette["text"]))
                pills.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        border_radius=8,
                        bgcolor=palette["accent"] if is_sel else palette["surface_variant"],
                        border=ft.Border.all(1, palette["accent"] if is_sel else palette["border"]),
                        ink=True,
                        on_click=lambda _, k=c_key: _select_cat(k),
                        content=ft.Row([
                            icon_ctrl,
                            ft.Text(c_name, size=11.5, weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500, color=ft.Colors.BLACK if is_sel else palette["text"]),
                        ], spacing=6, tight=True),
                    )
                )
            cat_selector_row.controls = pills

        def _select_cat(cat_key):
            selected_cat[0] = cat_key
            if cat_key in ("booster", "coins", "org_seats"):
                interval_dd.value = "one-time"
                interval_dd.disabled = True
            elif cat_key in ("plan", "org_plan"):
                interval_dd.disabled = False
                if not interval_dd.value or interval_dd.value == "one-time":
                    interval_dd.value = "month"
            _refresh_cat_pills()
            category_cards_container.content = _build_category_content()
            try:
                edit_dlg.update()
            except Exception:
                page.update()

        _refresh_cat_pills()

        # Quick Perk Suggestion Chips
        quick_chips = [
            "AI Course Drafting Engine",
            "Cohort CBT Exams & Timed Quizzes",
            "Cohort Gradebook & Performance Analytics",
            "Custom Verified Certificates",
            "+10 Additional Material Slots",
            "+25 AI Generations",
            "+50 AI Generations",
            "Credits Never Expire",
            "Priority Server Processing",
            "24/7 Dedicated Support",
        ]
        quick_chips_row = ft.Row(
            scroll=ft.ScrollMode.AUTO,
            spacing=6,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=palette["surface_variant"],
                    border=ft.Border.all(1, palette["border"]),
                    ink=True,
                    on_click=lambda _, q=chip_text: _append_perk(q),
                    content=ft.Row([
                        ft.Icon(ft.Icons.ADD_ROUNDED, size=11, color=palette["accent"]),
                        ft.Text(chip_text, size=10, color=palette["text"]),
                    ], spacing=4, tight=True),
                )
                for chip_text in quick_chips
            ],
        )

        async def _save_product(e=None):
            name_val = (name_input.value or "").strip()
            if not name_val:
                show_page_snackbar(page, "Product name is required.")
                return
            try:
                price_val = float(price_input.value.strip() or 0)
            except ValueError:
                show_page_snackbar(page, "Invalid price format.")
                return

            cat_val = selected_cat[0]
            raw_feats = [f.strip() for f in (features_input.value or "").split("\n") if f.strip()]

            # Synchronize authoritative org toggles into features list
            if cat_val == "org_plan":
                ai_perk = "AI Course Drafting Engine"
                if ai_drafting_switch.value:
                    if not any("ai course" in f.lower() or "ai drafting" in f.lower() for f in raw_feats):
                        raw_feats.insert(0, ai_perk)
                else:
                    raw_feats = [f for f in raw_feats if "ai course" not in f.lower() and "ai drafting" not in f.lower()]

                cbt_perk = "Cohort CBT Exams & Timed Quizzes"
                if cbt_switch.value:
                    if not any("cbt" in f.lower() for f in raw_feats):
                        raw_feats.append(cbt_perk)
                else:
                    raw_feats = [f for f in raw_feats if "cbt" not in f.lower()]

                analytics_perk = "Cohort Gradebook & Performance Analytics"
                if analytics_switch.value:
                    if not any("analytic" in f.lower() or "gradebook" in f.lower() for f in raw_feats):
                        raw_feats.append(analytics_perk)
                else:
                    raw_feats = [f for f in raw_feats if "analytic" not in f.lower() and "gradebook" not in f.lower()]

                branding_perk = "Custom Verified Certificates"
                if branding_switch.value:
                    if not any("certificate" in f.lower() or "brand" in f.lower() for f in raw_feats):
                        raw_feats.append(branding_perk)
                else:
                    raw_feats = [f for f in raw_feats if "certificate" not in f.lower() and "brand" not in f.lower()]

            token = admin_state.get("token") or ""
            plan_db_id = None

            # If Org Plan, save or sync with PostgreSQL 'plans' table
            if cat_val == "org_plan":
                try:
                    mems = int((max_members_input.value or "50").strip() or 50)
                    courses = int((max_courses_input.value or "20").strip() or 20)
                except ValueError:
                    mems = 50
                    courses = 20

                sel_db_plan = db_plan_dropdown.value
                db_payload = {
                    "id": sel_db_plan if (sel_db_plan and sel_db_plan != "new") else (prod.get("plan_id") if prod else None),
                    "name": name_val,
                    "description": (desc_input.value or "").strip() or None,
                    "price": price_val,
                    "max_members": mems,
                    "max_courses": courses,
                    "features": raw_feats,
                }
                db_res = await save_admin_org_plan(token, db_payload)
                if "error" in db_res:
                    show_page_snackbar(page, f"Warning: Failed to save DB plan: {db_res['error']}")
                elif db_res.get("id"):
                    plan_db_id = str(db_res["id"])

            materials_limit_val = None
            generations_limit_val = None
            exam_quota_val = None

            if cat_val == "plan":
                try:
                    if (plan_materials_input.value or "").strip():
                        materials_limit_val = int(plan_materials_input.value.strip())
                except ValueError:
                    materials_limit_val = None
                try:
                    if (plan_generations_input.value or "").strip():
                        generations_limit_val = int(plan_generations_input.value.strip())
                except ValueError:
                    generations_limit_val = None
                try:
                    if (plan_exam_input.value or "").strip():
                        exam_quota_val = int(plan_exam_input.value.strip())
                except ValueError:
                    exam_quota_val = None

            payload = {
                "id": (id_input.value or "").strip() or None,
                "name": name_val,
                "category": cat_val,
                "price": price_val,
                "badge": (badge_input.value or "").strip() or None,
                "description": (desc_input.value or "").strip() or None,
                "interval": (interval_dd.value or "one-time").strip(),
                "materials_limit": materials_limit_val,
                "generations_limit": generations_limit_val,
                "exam_quota": exam_quota_val,
                "bonus_materials": int((mats_input.value or "").strip() or 0) if cat_val != "org_plan" else 0,
                "bonus_generations": int((gens_input.value or "").strip() or 0) if cat_val != "org_plan" else 0,
                "bonus_coins": int((coins_input.value or "").strip() or 0) if cat_val != "org_plan" else 0,
                "org_seats": (
                    int((max_members_input.value or "50").strip() or 50)
                    if cat_val == "org_plan"
                    else (int((seat_count_input.value or "10").strip() or 10) if cat_val == "org_seats" else 0)
                ),
                "display_order": int((order_input.value or "").strip() or 0),
                "features": raw_feats,
                "is_active": active_switch.value,
                "plan_id": (id_input.value or "").strip() if cat_val == "plan" else (plan_db_id or (prod.get("plan_id") if prod else None)),
            }

            if prod:
                res = await update_admin_store_product(token, prod["id"], payload)
            else:
                res = await create_admin_store_product(token, payload)

            if "error" in res:
                show_page_snackbar(page, f"Error: {res['error']}")
                return

            edit_dlg.open = False
            page.update()
            show_page_snackbar(page, f"Store product '{name_val}' saved successfully!")
            await _fetch_store_products()

        dialog_width = min(740, max(360, int((page.width or 800) * 0.92)))

        edit_dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=palette["surface"],
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.STOREFRONT_ROUNDED, color=palette["accent"], size=22),
                        ft.Text("Edit Store Product" if prod else "Create Store Product", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ], spacing=8, tight=True),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_color=palette["text_muted"], on_click=lambda _: (setattr(edit_dlg, "open", False), page.update())),
                ],
            ),
            content=ft.Container(
                width=dialog_width,
                content=ft.Column(
                    tight=True,
                    spacing=14,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        # 1. Category Bar
                        ft.Column(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Text("Product Category:", size=11.5, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                                cat_selector_row,
                            ],
                        ),
                        # 2. Basic Info Card
                        ft.Container(
                            bgcolor=palette["surface_variant"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=ft.Padding.all(14),
                            content=ft.Column(
                                spacing=12,
                                controls=[
                                    ft.Row([name_input, id_input], spacing=10),
                                    ft.Row([price_input, interval_dd, badge_input], spacing=10),
                                ],
                            ),
                        ),
                        # 3. Dynamic Category Configuration Card
                        category_cards_container,
                        # 4. Catalog Display & Marketing Card
                        ft.Container(
                            bgcolor=palette["surface_variant"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=ft.Padding.all(14),
                            content=ft.Column(
                                spacing=12,
                                controls=[
                                    desc_input,
                                    ft.Row([order_input, ft.Container(content=active_switch, padding=ft.Padding.only(top=8))], spacing=10),
                                    features_input,
                                    ft.Column(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.Text("Quick Add Perks:", size=11, color=palette["text_muted"]),
                                            quick_chips_row,
                                        ],
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=palette["text_muted"]), on_click=lambda _: (setattr(edit_dlg, "open", False), page.update())),
                ft.FilledButton(
                    "Save Product",
                    icon=ft.Icons.SAVE_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=palette["accent_glow"], color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda _: page.run_task(_save_product),
                ),
            ],
        )
        page.overlay.append(edit_dlg)
        edit_dlg.open = True
        page.update()

    def _build_store_studio_tab() -> ft.Control:
        prods = admin_state.get("store_products") or []
        is_loading = admin_state.get("is_loading_store", False)
        current_cat_filter = admin_state.get("store_filter_cat", "all")

        # Category Filter Bar with Horizontal Scrolling
        categories = [
            ("all", "All Products"),
            ("plan", "Scholar Plans"),
            ("booster", "Study Boosters"),
            ("coins", "Nu-Coins Packs"),
            ("org_plan", "Org Plans"),
            ("org_seats", "Org Seats"),
        ]
        cat_chips = []
        for c_id, c_label in categories:
            is_active = current_cat_filter == c_id
            cat_chips.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=8,
                    bgcolor=palette["accent"] if is_active else palette["surface_variant"],
                    border=ft.Border.all(1, palette["accent"] if is_active else palette["border"]),
                    ink=True,
                    on_click=lambda _, cid=c_id: (admin_state.update({"store_filter_cat": cid}), _render_tab_content(), page.update()),
                    content=ft.Text(
                        c_label,
                        size=11.5,
                        weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500,
                        color=ft.Colors.BLACK if is_active else palette["text_muted"],
                    ),
                )
            )

        header = ft.Container(
            bgcolor=palette["surface"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=ft.Padding.all(18),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                wrap=True,
                spacing=12,
                controls=[
                    ft.Column(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Row(
                                spacing=8,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.STORE_ROUNDED, size=20, color=palette["accent"]),
                                    ft.Text("Store Catalog Studio", size=18, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ],
                            ),
                            ft.Text(
                                "Live catalog of learner subscriptions, study boosters, Nu-Coins, and organisation plans.",
                                size=12,
                                color=palette["text_muted"],
                            ),
                        ],
                    ),
                    ft.Row(
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.REFRESH_ROUNDED,
                                icon_color=palette["accent"],
                                tooltip="Refresh Products & Plans",
                                on_click=lambda _: page.run_task(_fetch_store_products),
                            ),
                            ft.FilledButton(
                                "Create Product",
                                icon=ft.Icons.ADD_ROUNDED,
                                style=ft.ButtonStyle(
                                    bgcolor=palette["accent_glow"],
                                    color=ft.Colors.WHITE,
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                ),
                                on_click=lambda _: _show_store_product_dialog(None),
                            ),
                        ],
                    ),
                ],
            ),
        )

        filtered_prods = prods
        if current_cat_filter != "all":
            filtered_prods = [p for p in prods if p.get("category") == current_cat_filter]

        if is_loading:
            body = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(60),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.ProgressRing(width=32, height=32, stroke_width=3, color=palette["accent"]),
                        ft.Text("Loading store catalog from database…", size=13, color=palette["text_muted"]),
                    ],
                ),
            )
        elif not filtered_prods:
            body = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(60),
                bgcolor=palette["surface"],
                border=ft.Border.all(1, palette["border"]),
                border_radius=14,
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.Icon(ft.Icons.SHOPPING_BAG_OUTLINED, size=48, color=palette["text_muted"]),
                        ft.Text("No Products in this Category", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text("Click '+ Create Product' above to add items to the store.", size=12, color=palette["text_muted"]),
                    ],
                ),
            )
        else:
            cards = []
            for p in filtered_prods:
                p_id = p.get("id")
                raw_cat = p.get("category") or ""
                p_cat = raw_cat.replace("_", " ").upper()
                p_badge = p.get("badge")
                p_active = p.get("is_active", True)
                p_price = float(p.get("price") or 0)

                async def _toggle_active(prod_item=p):
                    token = admin_state.get("token") or ""
                    new_val = not prod_item.get("is_active", True)
                    await update_admin_store_product(token, prod_item["id"], {"name": prod_item["name"], "category": prod_item["category"], "price": prod_item["price"], "is_active": new_val})
                    await _fetch_store_products()

                async def _confirm_delete(prod_item=p):
                    del_dlg = ft.AlertDialog(
                        title=ft.Text("Delete Product?"),
                        content=ft.Text(f"Are you sure you want to delete '{prod_item['name']}' from the store catalog?"),
                        actions=[
                            ft.TextButton("Cancel", on_click=lambda _: (setattr(del_dlg, "open", False), page.update())),
                            ft.FilledButton(
                                "Delete",
                                style=ft.ButtonStyle(bgcolor=palette["danger"]),
                                on_click=lambda _: page.run_task(_execute_delete, prod_item["id"], del_dlg),
                            ),
                        ],
                    )
                    page.overlay.append(del_dlg)
                    del_dlg.open = True
                    page.update()

                async def _execute_delete(pid, dlg):
                    dlg.open = False
                    page.update()
                    token = admin_state.get("token") or ""
                    await delete_admin_store_product(token, pid)
                    show_page_snackbar(page, f"Product deleted successfully.")
                    await _fetch_store_products()

                perks = []
                if p.get("category") == "plan":
                    if p.get("materials_limit") is not None:
                        perks.append(f"{p['materials_limit']} Upload Slots")
                    if p.get("generations_limit") is not None:
                        perks.append(f"{p['generations_limit']} Gens/mo")
                    if p.get("exam_quota") is not None:
                        perks.append(f"{p['exam_quota']} Exams/mo")
                if p.get("bonus_generations"):
                    perks.append(f"+{p['bonus_generations']} AI Gens")
                if p.get("bonus_materials"):
                    perks.append(f"+{p['bonus_materials']} Materials")
                if p.get("bonus_coins"):
                    perks.append(f"+{p['bonus_coins']} Nu-Coins")
                if p.get("org_seats"):
                    perks.append(f"+{p['org_seats']} Org Seats")

                # Detect AI Drafting perk in features
                p_features = p.get("features", [])
                has_ai_draft = any("ai course" in f.lower() or "ai drafting" in f.lower() for f in p_features)
                if has_ai_draft:
                    perks.append("🤖 AI Drafting")
                if any("cbt" in f.lower() for f in p_features):
                    perks.append("📝 CBT Engine")

                card = ft.Container(
                    bgcolor=palette["surface"],
                    border=ft.Border.all(1, palette["accent"] if p_badge else palette["border"]),
                    border_radius=12,
                    padding=ft.Padding.all(16),
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                                border_radius=4,
                                                bgcolor=palette["surface_variant"],
                                                content=ft.Text(p_cat, size=9.5, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                                            ),
                                            *(
                                                [
                                                    ft.Container(
                                                        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                                        border_radius=4,
                                                        bgcolor=ft.Colors.with_opacity(0.12, palette["accent_glow"]),
                                                        content=ft.Text(p_badge, size=9.5, weight=ft.FontWeight.BOLD, color=palette["accent_glow"]),
                                                    )
                                                ] if p_badge else []
                                            ),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                border_radius=4,
                                                bgcolor=palette["success_bg"] if p_active else palette["danger_bg"],
                                                content=ft.Text("LIVE" if p_active else "INACTIVE", size=9, weight=ft.FontWeight.BOLD, color=palette["success"] if p_active else palette["danger"]),
                                            ),
                                            ft.Switch(
                                                value=p_active,
                                                active_color=palette["accent"],
                                                on_change=lambda _, p_item=p: page.run_task(_toggle_active, p_item),
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        tight=True,
                                        controls=[
                                            ft.Text(p.get("name", "Product"), size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                            ft.Text(f"ID: {p_id}", size=11, color=palette["text_muted"], font_family="monospace"),
                                        ],
                                    ),
                                    ft.Text(f"₦{p_price:,.2f}", size=17, weight=ft.FontWeight.W_900, color=palette["accent"]),
                                ],
                            ),
                            ft.Text(p.get("description") or "", size=11.5, color=palette["text_muted"]),
                            *(
                                [
                                    ft.Row(
                                        scroll=ft.ScrollMode.AUTO,
                                        spacing=6,
                                        controls=[
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                                border_radius=6,
                                                bgcolor=palette["surface_variant"],
                                                content=ft.Text(pk, size=10.5, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                            )
                                            for pk in perks
                                        ],
                                    )
                                ] if perks else []
                            ),
                            ft.Divider(height=1, color=palette["border"]),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                spacing=8,
                                controls=[
                                    ft.TextButton(
                                        content=ft.Row([ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, size=14, color=palette["danger"]), ft.Text("Delete", size=11.5, color=palette["danger"])], spacing=4),
                                        on_click=lambda _, p_item=p: page.run_task(_confirm_delete, p_item),
                                    ),
                                    ft.FilledButton(
                                        content=ft.Row([ft.Icon(ft.Icons.EDIT_ROUNDED, size=14, color=ft.Colors.WHITE), ft.Text("Edit Product", size=11.5, color=ft.Colors.WHITE)], spacing=4),
                                        style=ft.ButtonStyle(bgcolor=palette["accent_glow"], shape=ft.RoundedRectangleBorder(radius=6)),
                                        on_click=lambda _, p_item=p: _show_store_product_dialog(p_item),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
                cards.append(card)

            body = ft.Column(spacing=12, controls=cards)

        return ft.Container(
            expand=True,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=16,
                controls=[
                    header,
                    ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8, controls=cat_chips),
                    body,
                    ft.Container(height=40),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # H2. TAB: AUDIO NARRATION STUDIO & BATCH QUEUE
    # ─────────────────────────────────────────────────────────────────────────

    async def _fetch_audio_queue_status():
        tok = admin_state.get("token")
        if not tok:
            return
        admin_state["is_loading_audio_queue"] = True
        code, data = await get_audio_queue_status(tok)
        admin_state["is_loading_audio_queue"] = False
        if code == 200:
            admin_state["audio_queue_status"] = data
            admin_state["audio_queue_error"] = None
        else:
            admin_state["audio_queue_error"] = data.get("detail", "Failed to fetch audio queue metrics.")
        if admin_state["active_tab"] == "audio_studio":
            _render_tab_content()
            try:
                page.update()
            except Exception:
                pass

    async def _audio_queue_auto_poller():
        """Smooth background poller that refreshes metrics while active queue runs."""
        while admin_state.get("active_tab") == "audio_studio" and admin_state.get("authenticated"):
            await _fetch_audio_queue_status()
            q_status = (admin_state.get("audio_queue_status") or {}).get("status", "idle")
            if q_status != "running":
                break
            await asyncio.sleep(2.0)

    async def _on_trigger_batch_audio_queue(e=None):
        tok = admin_state.get("token")
        if not tok:
            show_page_snackbar(page, "Authentication token missing.")
            return

        selected_langs = [
            code for code, is_sel in admin_state["audio_queue_selected_langs"].items() if is_sel
        ]
        if not selected_langs:
            show_page_snackbar(page, "Please select at least one language to generate.")
            return

        admin_state["is_triggering_audio_queue"] = True
        if admin_state["active_tab"] == "audio_studio":
            _render_tab_content()
            page.update()

        code, resp = await queue_all_lesson_audio(
            token=tok,
            languages=selected_langs,
            force_regenerate=admin_state["audio_queue_force"],
        )
        admin_state["is_triggering_audio_queue"] = False

        if code == 200:
            msg = resp.get("message") or "Audio batch queue triggered successfully!"
            show_page_snackbar(page, msg)
            admin_state["audio_queue_status"] = resp
            page.run_task(_audio_queue_auto_poller)
        elif code == 409:
            show_page_snackbar(page, "An audio generation queue is already running.")
            page.run_task(_audio_queue_auto_poller)
        else:
            err = resp.get("detail") or "Failed to initiate batch audio queue."
            show_page_snackbar(page, f"Error: {err}")

        if admin_state["active_tab"] == "audio_studio":
            _render_tab_content()
            page.update()

    async def _on_cancel_audio_queue(e=None):
        tok = admin_state.get("token")
        if not tok:
            return
        code, resp = await cancel_audio_queue(tok)
        msg = resp.get("message") or "Cancellation signal sent."
        show_page_snackbar(page, msg)
        await _fetch_audio_queue_status()

    def _build_audio_studio_tab() -> ft.Control:
        status_data = admin_state.get("audio_queue_status") or {}
        cov = status_data.get("coverage") or {}
        status_str = status_data.get("status", "idle").upper()

        # Header
        header = ft.Container(
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=20,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=12,
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.GRAPHIC_EQ_ROUNDED, size=24, color=palette["accent"]),
                                bgcolor=ft.Colors.with_opacity(0.14, palette["accent"]),
                                padding=10,
                                border_radius=12,
                            ),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text("Lesson Audio Narration Studio", size=18, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                    ft.Text("Batch synthesize lesson voiceovers with real-time progress and automatic skipping of existing DB rows.", size=12, color=palette["text_muted"]),
                                ],
                            ),
                        ],
                    ),
                    ft.FilledButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.REFRESH_ROUNDED, size=14, color=palette["text"]),
                            ft.Text("Refresh Metrics", size=12, color=palette["text"]),
                        ], spacing=6, tight=True),
                        style=ft.ButtonStyle(bgcolor=palette["surface_variant"], shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda _: page.run_task(_fetch_audio_queue_status),
                    ),
                ],
            ),
        )

        # Language Coverage Cards
        tot_lessons = cov.get("total_narratable_lessons", 0)
        en_c = cov.get("en", 0)
        ha_c = cov.get("ha", 0)
        fr_c = cov.get("fr", 0)
        en_pct = cov.get("en_pct", 0.0)
        ha_pct = cov.get("ha_pct", 0.0)
        fr_pct = cov.get("fr_pct", 0.0)

        def _cov_card(lang_name: str, count: int, pct: float, color: str, col_span: int = 3):
            return ft.Container(
                col={"xs": 12, "sm": 6, "md": col_span},
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
                                ft.Text(lang_name, size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ft.Container(
                                    content=ft.Text(f"{pct}%", size=11, weight=ft.FontWeight.BOLD, color=color),
                                    bgcolor=ft.Colors.with_opacity(0.14, color),
                                    padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                                    border_radius=6,
                                ),
                            ],
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            controls=[
                                ft.Text(f"{count:,}", size=24, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ft.Text(f"of {tot_lessons:,} lessons", size=11, color=palette["text_muted"]),
                            ],
                        ),
                        ft.ProgressBar(
                            value=min(1.0, max(0.0, pct / 100.0)),
                            color=color,
                            bgcolor=palette["surface_variant"],
                            border_radius=ft.BorderRadius.all(3),
                        ),
                    ],
                ),
            )

        coverage_row = ft.ResponsiveRow(
            spacing=12, run_spacing=12,
            controls=[
                ft.Container(
                    col={"xs": 12, "sm": 6, "md": 3},
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
                                    ft.Text("Narratable Content", size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                    ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=18, color=palette["info"]),
                                ],
                            ),
                            ft.Text(f"{tot_lessons:,}", size=24, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ft.Text("Eligible lessons (text, notes, steps)", size=11, color=palette["text_muted"]),
                        ],
                    ),
                ),
                _cov_card("English Narration", en_c, en_pct, palette["success"]),
                _cov_card("Hausa Narration", ha_c, ha_pct, palette["accent"]),
                _cov_card("French Narration", fr_c, fr_pct, palette["purple"]),
            ],
        )

        # Trigger & Live Control Grid
        # Left Panel: Trigger Form
        def _on_lang_checkbox(code: str, val: bool):
            admin_state["audio_queue_selected_langs"][code] = val

        def _on_force_checkbox(val: bool):
            admin_state["audio_queue_force"] = val

        lang_checks = ft.Row(
            spacing=12,
            controls=[
                ft.Checkbox(
                    label="English (EN)",
                    value=admin_state["audio_queue_selected_langs"].get("en", True),
                    on_change=lambda e: _on_lang_checkbox("en", e.control.value),
                    fill_color=palette["accent"],
                ),
                ft.Checkbox(
                    label="Hausa (HA)",
                    value=admin_state["audio_queue_selected_langs"].get("ha", True),
                    on_change=lambda e: _on_lang_checkbox("ha", e.control.value),
                    fill_color=palette["accent"],
                ),
                ft.Checkbox(
                    label="French (FR)",
                    value=admin_state["audio_queue_selected_langs"].get("fr", True),
                    on_change=lambda e: _on_lang_checkbox("fr", e.control.value),
                    fill_color=palette["accent"],
                ),
            ],
        )

        force_check = ft.Checkbox(
            label="Force re-generation (Overwrite existing DB cache)",
            value=admin_state.get("audio_queue_force", False),
            on_change=lambda e: _on_force_checkbox(e.control.value),
            fill_color=palette["danger"],
        )

        trigger_btn = ft.FilledButton(
            content=ft.Row(
                [
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.WHITE)
                    if admin_state["is_triggering_audio_queue"]
                    else ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=18, color=ft.Colors.WHITE),
                    ft.Text(
                        "Starting Queue..." if admin_state["is_triggering_audio_queue"] else "Queue Audio Generation for All Lessons",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
                tight=True,
            ),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding.symmetric(vertical=14, horizontal=20),
            ),
            disabled=admin_state["is_triggering_audio_queue"] or status_str == "RUNNING",
            on_click=_on_trigger_batch_audio_queue,
        )

        trigger_card = ft.Container(
            col={"xs": 12, "md": 5},
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=20,
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED_ROUNDED, size=18, color=palette["accent"]),
                        ft.Text("Queue Audio Generation", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ], spacing=8),
                    ft.Text(
                        "Runs bulk speech synthesis. Any lesson + language combination that already has a cache row in PostgreSQL is automatically skipped.",
                        size=12,
                        color=palette["text_muted"],
                    ),
                    ft.Divider(height=1, color=palette["border"]),
                    ft.Text("Target Languages:", size=12, weight=ft.FontWeight.W_600, color=palette["text"]),
                    lang_checks,
                    force_check,
                    ft.Container(height=6),
                    trigger_btn,
                ],
            ),
        )

        # Right Panel: Real-Time Queue Monitor
        total_tasks = status_data.get("total_tasks", 0)
        skipped_count = status_data.get("skipped_existing", 0)
        queued_count = status_data.get("queued_tasks", 0)
        completed_count = status_data.get("completed_tasks", 0)
        failed_count = status_data.get("failed_tasks", 0)
        active_task = status_data.get("active_task")
        recent_logs = status_data.get("recent_logs", [])

        processed = skipped_count + completed_count + failed_count
        progress_val = min(1.0, max(0.0, processed / max(1, total_tasks))) if total_tasks > 0 else 0.0

        status_badge_color = {
            "RUNNING": palette["accent"],
            "COMPLETED": palette["success"],
            "CANCELLED": palette["danger"],
            "IDLE": palette["text_muted"],
        }.get(status_str, palette["text_muted"])

        status_badge = ft.Container(
            content=ft.Text(status_str, size=10, weight=ft.FontWeight.BOLD, color=status_badge_color),
            bgcolor=ft.Colors.with_opacity(0.14, status_badge_color),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=6,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, status_badge_color)),
        )

        def _metric_box(label: str, val: int, col: str):
            return ft.Container(
                bgcolor=palette["surface_variant"],
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                content=ft.Column(
                    spacing=2,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(f"{val:,}", size=16, weight=ft.FontWeight.BOLD, color=col),
                        ft.Text(label, size=10, color=palette["text_muted"]),
                    ],
                ),
            )

        active_ticker = ft.Container(
            bgcolor=palette["surface_variant"],
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=14, height=14, stroke_width=2, color=palette["accent"])
                    if status_str == "RUNNING"
                    else ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=16, color=palette["success"]),
                    ft.Text(
                        f"Synthesizing [{active_task.get('language', '').upper()}]: '{active_task.get('title', 'Lesson')}'"
                        if active_task and status_str == "RUNNING"
                        else ("Queue worker is active..." if status_str == "RUNNING" else "Audio synthesis engine is idle."),
                        size=12,
                        weight=ft.FontWeight.W_500,
                        color=palette["text"],
                        expand=True,
                    ),
                ],
            ),
        )

        cancel_btn = ft.OutlinedButton(
            content=ft.Row([
                ft.Icon(ft.Icons.STOP_ROUNDED, size=14, color=palette["danger"]),
                ft.Text("Cancel Queue", size=12, color=palette["danger"]),
            ], spacing=6, tight=True),
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, palette["danger"]),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            disabled=status_str != "RUNNING",
            on_click=_on_cancel_audio_queue,
        )

        monitor_card = ft.Container(
            col={"xs": 12, "md": 7},
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=20,
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.SPEED_ROUNDED, size=18, color=palette["accent"]),
                                ft.Text("Live Queue Monitor", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ], spacing=8),
                            status_badge,
                        ],
                    ),
                    ft.Column(
                        spacing=4,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(f"Progress: {round(progress_val * 100, 1)}%", size=11, color=palette["text_muted"], weight=ft.FontWeight.BOLD),
                                    ft.Text(f"{processed:,} / {total_tasks:,} tasks processed", size=11, color=palette["text_muted"]),
                                ],
                            ),
                            ft.ProgressBar(
                                value=progress_val,
                                color=palette["success"] if status_str == "COMPLETED" else palette["accent"],
                                bgcolor=palette["surface_variant"],
                                border_radius=ft.BorderRadius.all(3),
                            ),
                        ],
                    ),
                    ft.Row(
                        scroll=ft.ScrollMode.AUTO,
                        spacing=8,
                        controls=[
                            _metric_box("Total Tasks", total_tasks, palette["text"]),
                            _metric_box("Skipped (Cached)", skipped_count, palette["success"]),
                            _metric_box("Queued", queued_count, palette["info"]),
                            _metric_box("Completed", completed_count, palette["success"]),
                            _metric_box("Failed", failed_count, palette["danger"] if failed_count > 0 else palette["text_muted"]),
                        ],
                    ),
                    active_ticker,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        controls=[cancel_btn],
                    ),
                ],
            ),
        )

        # Recent Activity Stream
        log_items = []
        if recent_logs:
            for line in recent_logs:
                is_err = "failed" in line.lower() or "error" in line.lower()
                is_gen = "generated" in line.lower()
                ic = ft.Icons.ERROR_OUTLINE_ROUNDED if is_err else (ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED if is_gen else ft.Icons.INFO_OUTLINE_ROUNDED)
                col = palette["danger"] if is_err else (palette["success"] if is_gen else palette["text_muted"])
                log_items.append(
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ic, size=14, color=col),
                            ft.Text(line, size=11.5, color=palette["text"], expand=True),
                        ],
                    )
                )
        else:
            log_items.append(
                ft.Text("No recent batch activity recorded.", size=12, color=palette["text_muted"], italic=True)
            )

        activity_card = ft.Container(
            bgcolor=palette["card_bg"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=20,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, size=18, color=palette["accent"]),
                        ft.Text("Recent Synthesis Activity", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ], spacing=8),
                    ft.Divider(height=1, color=palette["border"]),
                    ft.Container(
                        height=160,
                        content=ft.ListView(
                            controls=log_items,
                            spacing=8,
                        ),
                    ),
                ],
            ),
        )

        return ft.Container(
            expand=True,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=16,
                controls=[
                    header,
                    coverage_row,
                    ft.ResponsiveRow(spacing=12, run_spacing=12, controls=[trigger_card, monitor_card]),
                    activity_card,
                    ft.Container(height=40),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # OBJECTIVES & MILESTONES STUDIO
    # ─────────────────────────────────────────────────────────────────────────

    async def _fetch_objectives():
        if not admin_state["token"]:
            return
        admin_state["is_loading_objectives"] = True
        _render_tab_content()
        page.update()

        status, data = await get_admin_objectives(admin_state["token"])
        if status == 200:
            admin_state["objectives"] = data.get("objectives", [])
            admin_state["objectives_stats"] = {
                "total": data.get("total_objectives", 0),
                "active": data.get("total_active", 0),
                "coins_distributed": data.get("total_coins_distributed", 0),
            }
            admin_state["objectives_error"] = None
        else:
            admin_state["objectives_error"] = data.get("detail", "Failed to load platform objectives.")

        admin_state["is_loading_objectives"] = False
        nav_container.content = _build_nav_bar()
        _render_tab_content()
        page.update()

    def _open_objective_modal(existing_obj: Optional[dict] = None):
        is_edit = existing_obj is not None

        CATEGORIES = [
            ("courses", "Courses", ft.Icons.SCHOOL_ROUNDED),
            ("streaks", "Streaks", ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED),
            ("self_study", "Self-Study", ft.Icons.PSYCHOLOGY_ROUNDED),
            ("duels", "Duels", ft.Icons.SPORTS_ESPORTS_ROUNDED),
            ("sharing", "Community", ft.Icons.SHARE_ROUNDED),
            ("general", "General", ft.Icons.MILITARY_TECH_ROUNDED),
        ]

        METRIC_TAXONOMY = [
            ("courses", "finish_course", "Finish Course / Certification", "courses", "Course Conqueror", "Complete all modules and achieve final course certification."),
            ("courses", "finish_module", "Finish Curriculum Module", "modules", "Module Achiever", "Complete and pass an individual curriculum module."),
            ("streaks", "login_streak", "Daily Login Streak", "days", "Unstoppable Learner", "Maintain a consecutive daily study streak."),
            ("self_study", "practice_questions", "Practice Questions Answered", "questions", "Quiz Master", "Answer practice questions across any subjects in the self study hub."),
            ("self_study", "study_time", "Focused Study Time (Minutes)", "minutes", "Study Marathon", "Log focused study sessions in the study hub."),
            ("duels", "win_duel", "Academic Duels Won", "duels", "Arena Champion", "Win head-to-head academic duels against study partners."),
            ("sharing", "share_pack", "Study Packs Shared", "packs", "Knowledge Beacon", "Publish and share your custom study packs with the learning community."),
            ("general", "general", "General Platform Milestone", "count", "Community Achiever", "General learning platform milestone."),
        ]

        obj_data = existing_obj or {}
        init_cat = obj_data.get("category", "courses") if is_edit else "courses"
        if not any(c[0] == init_cat for c in CATEGORIES):
            init_cat = "courses"

        init_metric = (obj_data.get("metric_event") or obj_data.get("code")) if is_edit else "finish_course"
        valid_initial_metrics = [m[1] for m in METRIC_TAXONOMY if m[0] == init_cat]
        if init_metric not in valid_initial_metrics:
            init_metric = valid_initial_metrics[0]

        selected_state = {
            "cat": init_cat,
            "metric": init_metric,
        }

        active_meta = next((m for m in METRIC_TAXONOMY if m[1] == init_metric), METRIC_TAXONOMY[0])
        init_unit = obj_data.get("target_unit") if is_edit else active_meta[3]

        code_ctrl = ft.TextField(
            label="Objective Code",
            value=obj_data.get("code", "") if is_edit else "finish_course_1",
            read_only=is_edit,
            hint_text="e.g. login_streak_7d",
            border_radius=8,
            border_color=palette["border"],
            bgcolor=palette["surface"],
            text_size=12,
        )
        title_ctrl = ft.TextField(
            label="Title",
            value=obj_data.get("title", "") if is_edit else "Course Conqueror",
            hint_text="e.g. Course Conqueror",
            border_radius=8,
            border_color=palette["border"],
            bgcolor=palette["surface"],
            text_size=12,
        )
        desc_ctrl = ft.TextField(
            label="Description",
            value=obj_data.get("description", "") if is_edit else "Complete all modules and achieve final course certification.",
            hint_text="e.g. Complete all modules and achieve final course certification.",
            multiline=True,
            min_lines=2,
            border_radius=8,
            border_color=palette["border"],
            bgcolor=palette["surface"],
            text_size=12,
        )

        target_unit_ctrl = ft.TextField(
            label="Target Unit (Locked to Metric)",
            value=init_unit,
            read_only=True,
            border_radius=8,
            border_color=palette["border"],
            bgcolor=palette["surface"],
            text_size=12,
        )
        target_val_ctrl = ft.TextField(
            label="Target Value",
            value=str(obj_data.get("target_value", 1)) if is_edit else "1",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            border_color=palette["border"],
            bgcolor=palette["surface"],
            text_size=12,
        )
        reward_ctrl = ft.TextField(
            label="Nu-Coin Reward",
            value=str(obj_data.get("coin_reward", 50)) if is_edit else "50",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            border_color=palette["border"],
            bgcolor=palette["surface"],
            text_size=12,
        )
        badge_reward_options = [
            ft.dropdown.Option(key="", text="No Badge Awarded (Coins Only)"),
            ft.dropdown.Option(key="streak_master", text="🔥 Streak Master"),
            ft.dropdown.Option(key="century_club", text="💯 Century Club"),
            ft.dropdown.Option(key="duo_kings", text="👑 Duo Kings"),
            ft.dropdown.Option(key="campus_ambassador", text="🎓 Campus Ambassador"),
            ft.dropdown.Option(key="verified_tutor", text="📚 Verified Tutor"),
            ft.dropdown.Option(key="beta_pioneer", text="⚡ Beta Pioneer"),
        ]
        known_badge_keys = {"", "streak_master", "century_club", "duo_kings", "campus_ambassador", "verified_tutor", "beta_pioneer"}
        for b in admin_state.get("badges_cache", []):
            b_slug = b.get("slug")
            if b_slug and b_slug not in known_badge_keys:
                known_badge_keys.add(b_slug)
                badge_reward_options.append(ft.dropdown.Option(key=b_slug, text=f"🎖️ {b.get('name', b_slug)}"))

        cur_badge_slug = str(obj_data.get("badge_reward_slug") or "")
        badge_reward_ctrl = ft.Dropdown(
            label="Badge Reward (Optional Honor)",
            value=cur_badge_slug if any(o.key == cur_badge_slug for o in badge_reward_options) else "",
            options=badge_reward_options,
            border_radius=8,
            border_color=palette["border"],
            bgcolor=palette["surface"],
            text_size=12,
        )
        is_active_ctrl = ft.Switch(
            label="Active Milestone",
            value=obj_data.get("is_active", True) if is_edit else True,
            active_color=palette["primary"],
        )

        user_customized_code = False
        def _on_code_change(e):
            nonlocal user_customized_code
            user_customized_code = True

        code_ctrl.on_change = _on_code_change

        dlg: Optional[ft.AlertDialog] = None

        def _get_unit_abbrev(unit: str) -> str:
            return "d" if unit == "days" else ("m" if unit == "minutes" else ("q" if unit == "questions" else ""))

        ALL_DEFAULT_TITLES = {m[4] for m in METRIC_TAXONOMY}
        ALL_DEFAULT_DESCS = {m[5] for m in METRIC_TAXONOMY}

        cat_chip_widgets: Dict[str, ft.Container] = {}
        metric_chip_widgets: Dict[str, ft.Container] = {}

        def _sync_ui():
            cur_cat = selected_state["cat"]
            cur_metric = selected_state["metric"]

            # 1. Update Category Chips
            for cat_k, chip in cat_chip_widgets.items():
                is_active = (cat_k == cur_cat)
                chip.bgcolor = ft.Colors.with_opacity(0.18, palette["primary"]) if is_active else palette["surface"]
                chip.border = ft.Border.all(1.5 if is_active else 1.0, palette["primary"] if is_active else palette["border"])
                chip.content.controls[0].color = palette["primary"] if is_active else palette["text_muted"]
                chip.content.controls[1].color = palette["text"] if is_active else palette["text_muted"]
                chip.content.controls[1].weight = ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL

            # 2. Update Metric Chips
            active_metric_tuple = None
            for m_tuple in METRIC_TAXONOMY:
                m_cat, m_code, m_label, m_unit, m_title, m_desc = m_tuple
                chip = metric_chip_widgets[m_code]
                is_visible = (m_cat == cur_cat)
                is_selected = (m_code == cur_metric)
                chip.visible = is_visible
                if is_selected:
                    active_metric_tuple = m_tuple

                chip.bgcolor = ft.Colors.with_opacity(0.18, palette["accent"]) if is_selected else palette["surface"]
                chip.border = ft.Border.all(1.5 if is_selected else 1.0, palette["accent"] if is_selected else palette["border"])
                chip.content.controls[0].name = ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED if is_selected else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED
                chip.content.controls[0].color = palette["accent"] if is_selected else palette["text_muted"]
                chip.content.controls[1].color = palette["text"] if is_selected else palette["text_muted"]
                chip.content.controls[1].weight = ft.FontWeight.BOLD if is_selected else ft.FontWeight.NORMAL

            # 3. Synchronize Unit and Recommended Metadata
            if active_metric_tuple:
                _, _, _, m_unit, m_title, m_desc = active_metric_tuple
                target_unit_ctrl.value = m_unit
                if not is_edit:
                    t_val = target_val_ctrl.value.strip() or "1"
                    u_abbrev = _get_unit_abbrev(m_unit)
                    if not user_customized_code:
                        code_ctrl.value = f"{cur_metric}_{t_val}{u_abbrev}".rstrip("_")
                    if not title_ctrl.value.strip() or title_ctrl.value in ALL_DEFAULT_TITLES:
                        title_ctrl.value = m_title
                    if not desc_ctrl.value.strip() or desc_ctrl.value in ALL_DEFAULT_DESCS:
                        desc_ctrl.value = m_desc

            if dlg is not None:
                try:
                    dlg.update()
                except Exception:
                    page.update()

        def _select_category(cat_k: str):
            selected_state["cat"] = cat_k
            valid_metrics = [m[1] for m in METRIC_TAXONOMY if m[0] == cat_k]
            if selected_state["metric"] not in valid_metrics:
                selected_state["metric"] = valid_metrics[0]
            _sync_ui()

        def _select_metric(m_code: str):
            selected_state["metric"] = m_code
            _sync_ui()

        def _on_target_val_change(e=None):
            if not is_edit and not user_customized_code:
                cur_metric = selected_state["metric"]
                active_metric_tuple = next((m for m in METRIC_TAXONOMY if m[1] == cur_metric), METRIC_TAXONOMY[0])
                m_unit = active_metric_tuple[3]
                t_val = target_val_ctrl.value.strip() or "1"
                u_abbrev = _get_unit_abbrev(m_unit)
                code_ctrl.value = f"{cur_metric}_{t_val}{u_abbrev}".rstrip("_")
                if dlg is not None:
                    try:
                        dlg.update()
                    except Exception:
                        page.update()

        target_val_ctrl.on_change = _on_target_val_change

        # Build Interactive Category Chips
        for cat_k, cat_label, cat_icon in CATEGORIES:
            cat_chip_widgets[cat_k] = ft.Container(
                content=ft.Row([
                    ft.Icon(cat_icon, size=15),
                    ft.Text(cat_label, size=11),
                ], tight=True, spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                border_radius=8,
                animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                on_click=lambda e, k=cat_k: _select_category(k),
            )

        # Build Interactive Metric Event Chips
        for m_tuple in METRIC_TAXONOMY:
            m_cat, m_code, m_label, m_unit, _, _ = m_tuple
            metric_chip_widgets[m_code] = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED, size=14),
                    ft.Text(m_label, size=11),
                    ft.Container(
                        content=ft.Text(f"unit: {m_unit}", size=10, weight=ft.FontWeight.W_500, color=palette["accent"]),
                        bgcolor=ft.Colors.with_opacity(0.12, palette["accent"]),
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    ),
                ], tight=True, spacing=8),
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=8,
                animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                on_click=lambda e, code=m_code: _select_metric(code),
            )

        # Initial UI synchronization
        _sync_ui()

        modal_error = ft.Text("", size=11, color=palette["danger"], visible=False)
        modal_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=palette["accent"], visible=False)

        async def _submit_form(e=None):
            clean_code = code_ctrl.value.strip().lower()
            clean_title = title_ctrl.value.strip()
            clean_desc = desc_ctrl.value.strip()
            if not clean_code or not clean_title:
                modal_error.value = "Code and Title are required."
                modal_error.visible = True
                dlg.update()
                return

            try:
                t_val = int(target_val_ctrl.value.strip())
                r_val = int(reward_ctrl.value.strip())
            except ValueError:
                modal_error.value = "Target Value and Reward must be valid integers."
                modal_error.visible = True
                dlg.update()
                return

            modal_spinner.visible = True
            modal_error.visible = False
            submit_btn.disabled = True
            dlg.update()

            payload = {
                "code": clean_code,
                "title": clean_title,
                "description": clean_desc,
                "category": selected_state["cat"],
                "metric_event": selected_state["metric"],
                "target_value": t_val,
                "target_unit": target_unit_ctrl.value or "count",
                "coin_reward": r_val,
                "badge_reward_slug": badge_reward_ctrl.value.strip() if (badge_reward_ctrl.value and badge_reward_ctrl.value.strip()) else None,
                "icon": "EMOJI_TROPHY",
                "is_active": is_active_ctrl.value,
            }

            if is_edit:
                code_or_id = existing_obj.get("id") or existing_obj["code"]
                st, res = await update_admin_objective(admin_state["token"], code_or_id, payload)
            else:
                st, res = await create_admin_objective(admin_state["token"], payload)

            if st in (200, 201):
                dlg.open = False
                page.update()
                show_page_snackbar(page, f"Objective '{clean_title}' saved successfully.")
                await _fetch_objectives()
            else:
                modal_spinner.visible = False
                submit_btn.disabled = False
                modal_error.value = res.get("detail", "Error saving objective.")
                modal_error.visible = True
                dlg.update()

        submit_btn = ft.ElevatedButton(
            content=ft.Row([modal_spinner, ft.Text("Save Objective" if is_edit else "Create Objective", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)], tight=True, spacing=6),
            bgcolor=palette["accent"],
            height=38,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
            on_click=lambda e: page.run_task(_submit_form, e),
        )

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=palette["card_bg"],
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.MILITARY_TECH_ROUNDED, color=palette["accent"], size=20),
                        ft.Text("Edit Objective" if is_edit else "New Platform Objective", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
                    ], tight=True, spacing=8),
                    ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=lambda _: (setattr(dlg, "open", False), page.update())),
                ],
            ),
            content=ft.Container(
                width=500,
                height=560,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                    spacing=12,
                    controls=[
                        # Section 1: Category Chips
                        ft.Column([
                            ft.Text("Category", size=11, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                            ft.Row(
                                wrap=True,
                                spacing=6,
                                run_spacing=6,
                                controls=list(cat_chip_widgets.values()),
                            ),
                        ], spacing=6),

                        # Section 2: Metric Event Chips
                        ft.Column([
                            ft.Text("Metric Trigger Event (Predefined Backend Tracking)", size=11, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                            ft.Column(
                                spacing=6,
                                controls=list(metric_chip_widgets.values()),
                            ),
                        ], spacing=6),

                        # Section 3: Target Value, Unit, Reward & Honor Badge
                        ft.Row([
                            ft.Container(target_val_ctrl, expand=2),
                            ft.Container(target_unit_ctrl, expand=2),
                            ft.Container(reward_ctrl, expand=2),
                        ], spacing=10),
                        badge_reward_ctrl,

                        # Section 4: Title & Description
                        title_ctrl,
                        desc_ctrl,

                        # Section 5: Unique Code & Active Switch
                        code_ctrl,
                        is_active_ctrl,
                        modal_error,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(dlg, "open", False), page.update())),
                submit_btn,
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def _prompt_delete_objective(obj: dict):
        obj_id = obj.get("id") or obj["code"]
        title = obj.get("title", "Objective")

        delete_dlg: Optional[ft.AlertDialog] = None

        async def _do_delete(permanent: bool):
            if delete_dlg is not None:
                delete_dlg.open = False
                page.update()
            st, res = await delete_admin_objective(admin_state["token"], obj_id, permanent=permanent)
            if st == 200:
                show_page_snackbar(page, res.get("message", "Objective updated."))
                await _fetch_objectives()
            else:
                show_page_snackbar(page, f"Error: {res.get('detail', 'Could not delete')}")

        delete_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor=palette["card_bg"],
            title=ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=palette["danger"], size=22),
                ft.Text("Delete / Archive Objective", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
            ], tight=True, spacing=8),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Text(f"How do you want to handle '{title}' (`{obj.get('code')}`)?", size=13, weight=ft.FontWeight.W_600, color=palette["text"]),
                        ft.Text(
                            "• Deactivate: Disables the objective for learners while preserving historical progress and completion records.\n\n"
                            "• Permanently Delete: Completely deletes the objective from the database and removes all learner progress records.",
                            size=11.5,
                            color=palette["text_muted"],
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(delete_dlg, "open", False), page.update())),
                ft.OutlinedButton(
                    "Deactivate Only",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda _: page.run_task(_do_delete, False),
                ),
                ft.ElevatedButton(
                    "Permanently Delete",
                    bgcolor=palette["danger"],
                    color=ft.Colors.WHITE,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                    on_click=lambda _: page.run_task(_do_delete, True),
                ),
            ],
        )
        page.overlay.append(delete_dlg)
        delete_dlg.open = True
        page.update()

    async def _handle_test_trigger_objective(obj: dict):
        obj_id = obj.get("id") or obj["code"]
        st, res = await test_trigger_admin_objective(admin_state["token"], obj_id)
        if st == 200:
            show_page_snackbar(page, f"🏆 Test Alert Sent! Check notifications to test claiming +{obj.get('coin_reward')} coins.")
            try:
                from src.services.notification_service import sync_learner_notifications
                await sync_learner_notifications(page, force=True)
            except Exception as ex:
                print(f"[Admin] sync_learner_notifications error: {ex}")
            await _fetch_objectives()
        else:
            show_page_snackbar(page, f"Error triggering test: {res.get('detail', 'Failed')}")

    def _build_objectives_tab() -> ft.Control:
        # Header Row
        header = ft.Container(
            bgcolor=palette["surface"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=ft.Padding.symmetric(horizontal=18, vertical=14),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
                spacing=12,
                controls=[
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.MILITARY_TECH_ROUNDED, size=24, color=palette["accent"]),
                            bgcolor=ft.Colors.with_opacity(0.14, palette["accent"]),
                            padding=10,
                            border_radius=12,
                        ),
                        ft.Column(
                            spacing=2,
                            tight=True,
                            controls=[
                                ft.Text("Learning Platform Objectives Studio", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ft.Text("Configure gamified learning milestones, progress quotas, and Nu-Coin rewards across the platform.", size=11, color=palette["text_muted"]),
                            ],
                        ),
                    ], spacing=12, tight=True),
                    ft.Row(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.OutlinedButton(
                                content=ft.Row([ft.Icon(ft.Icons.REFRESH_ROUNDED, size=15), ft.Text("Refresh", size=12)], tight=True, spacing=4),
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=lambda _: page.run_task(_fetch_objectives),
                            ),
                            ft.ElevatedButton(
                                content=ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=ft.Colors.WHITE), ft.Text("Create Objective", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)], tight=True, spacing=6),
                                bgcolor=palette["accent"],
                                height=38,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                                on_click=lambda _: _open_objective_modal(None),
                            ),
                        ],
                    ),
                ],
            ),
        )

        stats = admin_state.get("objectives_stats", {})
        kpis = ft.ResponsiveRow(
            spacing=12,
            run_spacing=12,
            controls=[
                ft.Container(
                    col={"xs": 12, "sm": 6, "md": 4},
                    bgcolor=palette["card_bg"],
                    border=ft.Border.all(1, palette["border"]),
                    border_radius=12,
                    padding=16,
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                ft.Text("Configured Objectives", size=12, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                ft.Icon(ft.Icons.FORMAT_LIST_BULLETED_ROUNDED, size=16, color=palette["accent"]),
                            ]),
                            ft.Text(f"{stats.get('total', len(admin_state['objectives'])):,}", size=22, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ft.Text(f"{stats.get('active', 0)} currently active for learners", size=10.5, color=palette["success"]),
                        ],
                    ),
                ),
                ft.Container(
                    col={"xs": 12, "sm": 6, "md": 4},
                    bgcolor=palette["card_bg"],
                    border=ft.Border.all(1, palette["border"]),
                    border_radius=12,
                    padding=16,
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                ft.Text("Total Nu-Coins Distributed", size=12, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                nu_coin_icon(size=18),
                            ]),
                            ft.Text(f"{stats.get('coins_distributed', 0):,} Coins", size=22, weight=ft.FontWeight.BOLD, color=palette["warning"]),
                            ft.Text("Awarded via claimed learning milestones", size=10.5, color=palette["text_muted"]),
                        ],
                    ),
                ),
                ft.Container(
                    col={"xs": 12, "sm": 6, "md": 4},
                    bgcolor=palette["card_bg"],
                    border=ft.Border.all(1, palette["border"]),
                    border_radius=12,
                    padding=16,
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                ft.Text("Reward Claim Mode", size=12, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED, size=16, color=palette["info"]),
                            ]),
                            ft.Text("Push & In-App Alerts", size=22, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ft.Text("1-Tap claiming directly from notification", size=10.5, color=palette["info"]),
                        ],
                    ),
                ),
            ],
        )

        if admin_state["is_loading_objectives"]:
            body_content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=40,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.ProgressRing(color=palette["accent"], width=32, height=32, stroke_width=3),
                        ft.Text("Loading platform objectives...", size=12, color=palette["text_muted"]),
                    ],
                ),
            )
        elif admin_state["objectives_error"]:
            body_content = ft.Container(
                bgcolor=palette["card_bg"],
                border=ft.Border.all(1, palette["border"]),
                border_radius=14,
                padding=24,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=32, color=palette["danger"]),
                        ft.Text("Failed to load objectives", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text(admin_state["objectives_error"], size=11, color=palette["text_muted"]),
                        ft.ElevatedButton("Retry", on_click=lambda _: page.run_task(_fetch_objectives)),
                    ],
                ),
            )
        elif not admin_state["objectives"]:
            body_content = ft.Container(
                bgcolor=palette["card_bg"],
                border=ft.Border.all(1, palette["border"]),
                border_radius=14,
                padding=36,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.Icon(ft.Icons.MILITARY_TECH_ROUNDED, size=36, color=palette["text_muted"]),
                        ft.Text("No objectives configured yet", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text("Create your first platform objective to motivate students with dynamic coin rewards.", size=11, color=palette["text_muted"]),
                        ft.Container(height=8),
                        ft.ElevatedButton(
                            "Create First Objective",
                            bgcolor=palette["accent"],
                            color=ft.Colors.WHITE,
                            on_click=lambda _: _open_objective_modal(None),
                        ),
                    ],
                ),
            )
        else:
            current_filter = admin_state.get("objectives_filter", "all")

            def _change_filter(f_val):
                admin_state["objectives_filter"] = f_val
                _render_tab_content()
                page.update()

            all_objs = admin_state["objectives"]
            active_objs = [o for o in all_objs if o.get("is_active", True)]
            inactive_objs = [o for o in all_objs if not o.get("is_active", True)]

            if current_filter == "active":
                displayed_objs = active_objs
            elif current_filter == "inactive":
                displayed_objs = inactive_objs
            else:
                displayed_objs = all_objs

            filter_bar = ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    ft.Container(
                        content=ft.Text(f"All ({len(all_objs)})", size=11, weight=ft.FontWeight.W_600 if current_filter == "all" else ft.FontWeight.NORMAL, color=palette["text"] if current_filter == "all" else palette["text_muted"]),
                        bgcolor=ft.Colors.with_opacity(0.18, palette["accent"]) if current_filter == "all" else palette["surface"],
                        border=ft.Border.all(1, palette["accent"] if current_filter == "all" else palette["border"]),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        on_click=lambda _: _change_filter("all"),
                    ),
                    ft.Container(
                        content=ft.Text(f"Active ({len(active_objs)})", size=11, weight=ft.FontWeight.W_600 if current_filter == "active" else ft.FontWeight.NORMAL, color=palette["success"] if current_filter == "active" else palette["text_muted"]),
                        bgcolor=ft.Colors.with_opacity(0.18, palette["success"]) if current_filter == "active" else palette["surface"],
                        border=ft.Border.all(1, palette["success"] if current_filter == "active" else palette["border"]),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        on_click=lambda _: _change_filter("active"),
                    ),
                    ft.Container(
                        content=ft.Text(f"Archived ({len(inactive_objs)})", size=11, weight=ft.FontWeight.W_600 if current_filter == "inactive" else ft.FontWeight.NORMAL, color=palette["danger"] if current_filter == "inactive" else palette["text_muted"]),
                        bgcolor=ft.Colors.with_opacity(0.18, palette["danger"]) if current_filter == "inactive" else palette["surface"],
                        border=ft.Border.all(1, palette["danger"] if current_filter == "inactive" else palette["border"]),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        on_click=lambda _: _change_filter("inactive"),
                    ),
                ],
            )

            cards = []
            for obj in displayed_objs:
                is_active = obj.get("is_active", True)
                category = obj.get("category", "general")
                target_str = f"{obj.get('target_value', 1)} {obj.get('target_unit', 'count')}"
                c_count = obj.get("completions_count", 0)
                cl_count = obj.get("claimed_count", 0)
                coins_awarded = obj.get("total_coins_awarded", 0)

                card = ft.Container(
                    col={"xs": 12, "sm": 6, "md": 6, "lg": 4},
                    bgcolor=palette["card_bg"],
                    border=ft.Border.all(1, palette["accent"] if is_active else palette["border"]),
                    border_radius=14,
                    padding=16,
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row([
                                        ft.Container(
                                            content=ft.Text(str(category).upper(), size=9, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                                            bgcolor=ft.Colors.with_opacity(0.12, palette["accent"]),
                                            padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                                            border_radius=6,
                                        ),
                                        ft.Container(
                                            content=ft.Text(f"`{obj.get('code')}`", size=10, font_family="monospace", color=palette["text_muted"]),
                                            bgcolor=palette["surface"],
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=4,
                                        ),
                                        ft.Container(
                                            content=ft.Text(f"⚡ {obj.get('metric_event', 'general')}", size=9, weight=ft.FontWeight.W_600, color=palette["info"]),
                                            bgcolor=ft.Colors.with_opacity(0.12, palette["info"]),
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=4,
                                        ),
                                    ], spacing=6, tight=True),
                                    ft.Container(
                                        content=ft.Text("ACTIVE" if is_active else "INACTIVE", size=9, weight=ft.FontWeight.BOLD, color=palette["success"] if is_active else palette["text_muted"]),
                                        bgcolor=ft.Colors.with_opacity(0.12, palette["success"] if is_active else palette["surface"]),
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=4,
                                    ),
                                ],
                            ),
                            ft.Column(
                                spacing=3,
                                controls=[
                                    ft.Text(obj.get("title", ""), size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                    ft.Text(obj.get("description", ""), size=11, color=palette["text_muted"], max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ],
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Container(
                                        content=ft.Row([
                                            ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=13, color=palette["info"]),
                                            ft.Text(f"Target: {target_str}", size=11, color=palette["text"]),
                                        ], tight=True, spacing=4),
                                    ),
                                    ft.Container(
                                        content=ft.Row([
                                            nu_coin_icon(size=14),
                                            ft.Text(f"+{obj.get('coin_reward', 0)} Coins", size=11.5, weight=ft.FontWeight.BOLD, color=palette["warning"]),
                                        ], tight=True, spacing=4),
                                        bgcolor=ft.Colors.with_opacity(0.10, palette["warning"]),
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                        border_radius=6,
                                    ),
                                ],
                            ),
                            ft.Divider(height=1, color=palette["border"]),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(f"{c_count} finished • {cl_count} claimed ({coins_awarded:,} 🪙)", size=10, color=palette["text_muted"]),
                                    ft.Row(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.IconButton(
                                                icon=ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED,
                                                icon_size=15,
                                                icon_color=palette["accent"],
                                                tooltip="Test Completion Alert",
                                                on_click=lambda _, o=obj: page.run_task(_handle_test_trigger_objective, o),
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.EDIT_ROUNDED,
                                                icon_size=15,
                                                icon_color=palette["info"],
                                                tooltip="Edit Objective",
                                                on_click=lambda _, o=obj: _open_objective_modal(o),
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.DELETE_ROUNDED,
                                                icon_size=15,
                                                icon_color=palette["danger"],
                                                tooltip="Deactivate / Delete",
                                                on_click=lambda _, o=obj: _prompt_delete_objective(o),
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
                cards.append(card)

            cards_grid = ft.ResponsiveRow(spacing=12, run_spacing=12, controls=cards)
            body_content = ft.Column(spacing=12, controls=[filter_bar, cards_grid])

        return ft.Container(
            expand=True,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=16,
                controls=[
                    header,
                    kpis,
                    body_content,
                    ft.Container(height=40),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # PROMO CODES & CAMPUS AMBASSADORS STUDIO
    # ─────────────────────────────────────────────────────────────────────────

    async def _fetch_promo_codes():
        if not admin_state["token"]:
            return
        admin_state["is_loading_promo"] = True
        _render_tab_content()
        page.update()

        st, codes = await get_admin_promo_codes_api(admin_state["token"])
        if st == 200:
            admin_state["promo_codes"] = codes
            admin_state["promo_error"] = None
        else:
            admin_state["promo_error"] = "Failed to load promo codes."

        admin_state["is_loading_promo"] = False
        nav_container.content = _build_nav_bar()
        _render_tab_content()
        page.update()

    async def _fetch_ambassadors():
        if not admin_state["token"]:
            return
        admin_state["is_loading_ambassadors"] = True
        _render_tab_content()
        page.update()

        st, ambs = await get_admin_ambassadors_api(admin_state["token"])
        if st == 200:
            admin_state["ambassadors"] = ambs
            admin_state["ambassadors_error"] = None
        else:
            admin_state["ambassadors_error"] = "Failed to load campus ambassadors."

        admin_state["is_loading_ambassadors"] = False
        _render_tab_content()
        page.update()

    async def _fetch_ambassador_applications():
        if not admin_state["token"]:
            return
        admin_state["is_loading_ambassador_applications"] = True
        if admin_state.get("promo_subtab") == "ambassadors":
            _render_tab_content()
            page.update()

        st, apps = await get_admin_ambassador_applications_api(
            admin_state["token"],
            admin_state.get("ambassador_applications_filter")
        )
        if st == 200:
            admin_state["ambassador_applications"] = apps
            admin_state["ambassador_applications_error"] = None
        else:
            admin_state["ambassador_applications_error"] = "Failed to load ambassador applications."

        admin_state["is_loading_ambassador_applications"] = False
        if admin_state.get("promo_subtab") == "ambassadors":
            _render_tab_content()
            page.update()


    async def _fetch_badges_cache():
        if not admin_state["token"]:
            return
        admin_state["is_loading_badges"] = True
        if admin_state.get("promo_subtab") == "badges":
            _render_tab_content()
            page.update()

        st, badges = await get_admin_badges_api(admin_state["token"])
        if st == 200:
            admin_state["badges_cache"] = badges
            admin_state["badges_error"] = None
        else:
            admin_state["badges_error"] = "Failed to load honor badges."

        admin_state["is_loading_badges"] = False
        if admin_state.get("promo_subtab") == "badges":
            _render_tab_content()
            page.update()

    async def _toggle_promo_code_active(code_id: str):
        st, res = await toggle_admin_promo_code_api(admin_state["token"], code_id)
        if st == 200:
            show_page_snackbar(page, res.get("message", "Promo code status updated."))
            await _fetch_promo_codes()
        else:
            show_page_snackbar(page, f"Error: {res.get('detail', 'Could not toggle status')}")

    def _prompt_delete_promo_code(code: dict):
        cid = str(code.get("id"))
        c_name = code.get("code", "Promo Code")
        del_dlg = None

        async def _confirm_del(e):
            nonlocal del_dlg
            if del_dlg:
                del_dlg.open = False
                page.update()
            st, res = await delete_admin_promo_code_api(admin_state["token"], cid)
            if st == 200:
                show_page_snackbar(page, f"Promo code '{c_name}' removed.")
                await _fetch_promo_codes()
            else:
                show_page_snackbar(page, f"Error: {res.get('detail', 'Failed to delete')}")

        del_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor=palette["card_bg"],
            title=ft.Row([
                ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color=palette["danger"], size=20),
                ft.Text(f"Delete Code '{c_name}'?", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
            ], tight=True, spacing=8),
            content=ft.Text("This will permanently remove this promo code from circulation.", size=12, color=palette["text_muted"]),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(del_dlg, "open", False), page.update())),
                ft.ElevatedButton("Delete", bgcolor=palette["danger"], color=ft.Colors.WHITE, on_click=lambda e: page.run_task(_confirm_del, e)),
            ],
        )
        page.overlay.append(del_dlg)
        del_dlg.open = True
        page.update()

    def _prompt_delete_badge(badge: dict):
        bid = str(badge.get("id"))
        b_name = badge.get("name", "Honor Badge")
        del_dlg = None

        async def _confirm_del(e):
            nonlocal del_dlg
            if del_dlg:
                del_dlg.open = False
                page.update()
            st, res = await delete_admin_badge_api(admin_state["token"], bid)
            if st == 200:
                show_page_snackbar(page, f"Badge '{b_name}' deleted.")
                await _fetch_badges_cache()
            else:
                show_page_snackbar(page, f"Error: {res.get('detail', 'Failed to delete badge')}")

        del_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor=palette["card_bg"],
            title=ft.Row([
                ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color=palette["danger"], size=20),
                ft.Text(f"Delete Badge '{b_name}'?", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
            ], tight=True, spacing=8),
            content=ft.Text("This will permanently delete this badge and revoke it from all members who earned it.", size=12, color=palette["text_muted"]),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(del_dlg, "open", False), page.update())),
                ft.ElevatedButton("Delete", bgcolor=palette["danger"], color=ft.Colors.WHITE, on_click=lambda e: page.run_task(_confirm_del, e)),
            ],
        )
        page.overlay.append(del_dlg)
        del_dlg.open = True
        page.update()

    def _get_badge_icon_options():
        return [
            # Honors & Excellence
            ft.dropdown.Option(key="STAR_ROUNDED", text="⭐ Star / Excellence"),
            ft.dropdown.Option(key="WORKSPACE_PREMIUM_ROUNDED", text="🎖️ Premium Ribbon / Elite"),
            ft.dropdown.Option(key="MILITARY_TECH_ROUNDED", text="🏅 Military Medal / Valor"),
            ft.dropdown.Option(key="EMOJI_EVENTS_ROUNDED", text="🏆 Trophy / Champion"),
            ft.dropdown.Option(key="DIAMOND_ROUNDED", text="💎 Diamond / Prestige"),
            ft.dropdown.Option(key="SHIELD_ROUNDED", text="🛡️ Shield / Guardian"),
            ft.dropdown.Option(key="VERIFIED_ROUNDED", text="✅ Verified / Official"),
            ft.dropdown.Option(key="AUTO_AWESOME_ROUNDED", text="✨ Sparkles / Magic"),
            ft.dropdown.Option(key="LOCAL_FIRE_DEPARTMENT_ROUNDED", text="🔥 Fire / Hot Streak"),
            ft.dropdown.Option(key="BOLT_ROUNDED", text="⚡ Lightning Bolt / Velocity"),

            # Academic & Intellect
            ft.dropdown.Option(key="SCHOOL_ROUNDED", text="🎓 Graduation Cap / Scholar"),
            ft.dropdown.Option(key="MENU_BOOK_ROUNDED", text="📖 Open Book / Reader"),
            ft.dropdown.Option(key="AUTO_STORIES_ROUNDED", text="📚 Storyteller / Archives"),
            ft.dropdown.Option(key="PSYCHOLOGY_ROUNDED", text="🧠 Brain / Mind"),
            ft.dropdown.Option(key="LIGHTBULB_ROUNDED", text="💡 Lightbulb / Innovation"),
            ft.dropdown.Option(key="SCIENCE_ROUNDED", text="🔬 Science / Research"),

            # Community & Leadership
            ft.dropdown.Option(key="CAMPAIGN_ROUNDED", text="📢 Megaphone / Ambassador"),
            ft.dropdown.Option(key="GROUPS_ROUNDED", text="👥 Team / Collaboration"),
            ft.dropdown.Option(key="HANDSHAKE_ROUNDED", text="🤝 Partnership / Diplomat"),
            ft.dropdown.Option(key="PUBLIC_ROUNDED", text="🌍 Globe / Global Outreach"),
            ft.dropdown.Option(key="VOLUNTEER_ACTIVISM_ROUNDED", text="💖 Care / Community Helper"),
            ft.dropdown.Option(key="CELEBRATION_ROUNDED", text="🎉 Party Popper / Celebration"),
            ft.dropdown.Option(key="FORUM_ROUNDED", text="💬 Forum / Conversation"),

            # Tech, Mastery & Velocity
            ft.dropdown.Option(key="CODE_ROUNDED", text="💻 Code / Developer"),
            ft.dropdown.Option(key="TERMINAL_ROUNDED", text="⌨️ Terminal / Engineer"),
            ft.dropdown.Option(key="ROCKET_LAUNCH_ROUNDED", text="🚀 Rocket / Trailblazer"),
            ft.dropdown.Option(key="SPEED_ROUNDED", text="⏱️ Speedometer / Rapid"),
            ft.dropdown.Option(key="CALCULATE_ROUNDED", text="🧮 Calculator / Math Wizard"),
            ft.dropdown.Option(key="FITNESS_CENTER_ROUNDED", text="🏋️ Dumbbell / Hard Worker"),
            ft.dropdown.Option(key="FAVORITE_ROUNDED", text="❤️ Heart / Patron"),
            ft.dropdown.Option(key="EXPLORE_ROUNDED", text="🧭 Compass / Pioneer"),
            ft.dropdown.Option(key="SECURITY_ROUNDED", text="🔐 Security / Sentinel"),
            ft.dropdown.Option(key="TRENDING_UP_ROUNDED", text="📈 Growth / Rising Star"),
            ft.dropdown.Option(key="LEADERBOARD_ROUNDED", text="📊 Podium / Leaderboard"),
        ]

    def _open_create_badge_modal():
        slug_ctrl = ft.TextField(label="Badge Slug", hint_text="e.g. campus_ambassador, math_wizard", border_radius=8, bgcolor=palette["surface"], text_size=12)
        name_ctrl = ft.TextField(label="Badge Name", hint_text="e.g. Campus Ambassador, Math Wizard", border_radius=8, bgcolor=palette["surface"], text_size=12)
        desc_ctrl = ft.TextField(label="Description", hint_text="Criteria or honors for earning this badge", multiline=True, min_lines=2, border_radius=8, bgcolor=palette["surface"], text_size=12)

        icon_options = _get_badge_icon_options()
        icon_dropdown = ft.Dropdown(
            label="Badge Icon",
            value="STAR_ROUNDED",
            options=icon_options,
            border_radius=8,
            bgcolor=palette["surface"],
            text_size=12,
        )
        color_ctrl = ft.TextField(label="Primary Color Hex", value="#4CAF50", border_radius=8, bgcolor=palette["surface"], text_size=12)
        grad_start_ctrl = ft.TextField(label="Gradient Start Hex (Optional)", hint_text="e.g. #4CAF50", border_radius=8, bgcolor=palette["surface"], text_size=12)
        grad_end_ctrl = ft.TextField(label="Gradient End Hex (Optional)", hint_text="e.g. #2E7D32", border_radius=8, bgcolor=palette["surface"], text_size=12)
        is_auto_ctrl = ft.Switch(label="Automated (Awarded by engine milestones)", value=False, active_color=palette["primary"])

        modal_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=palette["accent"], visible=False)
        modal_error = ft.Text("", size=11, color=palette["danger"], visible=False)
        dlg = None

        async def _submit_create_badge(e):
            clean_slug = slug_ctrl.value.strip().lower()
            clean_name = name_ctrl.value.strip()
            if not clean_slug or not clean_name:
                modal_error.value = "Badge slug and name are required."
                modal_error.visible = True
                dlg.update()
                return

            modal_spinner.visible = True
            modal_error.visible = False
            submit_btn.disabled = True
            dlg.update()

            payload = {
                "slug": clean_slug,
                "name": clean_name,
                "description": desc_ctrl.value.strip() or None,
                "icon": icon_dropdown.value or "STAR_ROUNDED",
                "color_hex": color_ctrl.value.strip() or "#4CAF50",
                "gradient_start": grad_start_ctrl.value.strip() or None,
                "gradient_end": grad_end_ctrl.value.strip() or None,
                "is_automated": is_auto_ctrl.value,
            }

            st, res = await create_admin_badge_api(admin_state["token"], payload)
            if st in (200, 201):
                dlg.open = False
                page.update()
                show_page_snackbar(page, f"Badge '{clean_name}' created successfully!")
                await _fetch_badges_cache()
            else:
                modal_spinner.visible = False
                submit_btn.disabled = False
                modal_error.value = res.get("detail", "Error creating badge.")
                modal_error.visible = True
                dlg.update()

        submit_btn = ft.ElevatedButton(
            content=ft.Row([modal_spinner, ft.Text("Create Badge", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)], tight=True, spacing=6),
            bgcolor=palette["accent"],
            height=38,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: page.run_task(_submit_create_badge, e),
        )

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=palette["card_bg"],
            title=ft.Row([
                ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=palette["accent"], size=20),
                ft.Text("New Honor Badge", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
            ], tight=True, spacing=8),
            content=ft.Container(
                width=480,
                height=500,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    spacing=12,
                    controls=[
                        slug_ctrl,
                        name_ctrl,
                        desc_ctrl,
                        icon_dropdown,
                        color_ctrl,
                        ft.Row([
                            ft.Container(grad_start_ctrl, expand=1),
                            ft.Container(grad_end_ctrl, expand=1),
                        ], spacing=8),
                        is_auto_ctrl,
                        modal_error,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(dlg, "open", False), page.update())),
                submit_btn,
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def _open_edit_badge_modal(badge: dict):
        bid = str(badge.get("id"))
        name_ctrl = ft.TextField(label="Badge Name", value=badge.get("name", ""), border_radius=8, bgcolor=palette["surface"], text_size=12)
        desc_ctrl = ft.TextField(label="Description", value=badge.get("description", "") or "", multiline=True, min_lines=2, border_radius=8, bgcolor=palette["surface"], text_size=12)

        icon_options = _get_badge_icon_options()
        cur_icon = badge.get("icon", "STAR_ROUNDED")
        if not any(o.key == cur_icon for o in icon_options):
            icon_options.append(ft.dropdown.Option(key=cur_icon, text=cur_icon))

        icon_dropdown = ft.Dropdown(
            label="Badge Icon",
            value=cur_icon,
            options=icon_options,
            border_radius=8,
            bgcolor=palette["surface"],
            text_size=12,
        )
        color_ctrl = ft.TextField(label="Primary Color Hex", value=badge.get("color_hex", "#4CAF50"), border_radius=8, bgcolor=palette["surface"], text_size=12)
        grad_start_ctrl = ft.TextField(label="Gradient Start Hex (Optional)", value=badge.get("gradient_start", "") or "", border_radius=8, bgcolor=palette["surface"], text_size=12)
        grad_end_ctrl = ft.TextField(label="Gradient End Hex (Optional)", value=badge.get("gradient_end", "") or "", border_radius=8, bgcolor=palette["surface"], text_size=12)
        is_auto_ctrl = ft.Switch(label="Automated (Awarded by engine milestones)", value=bool(badge.get("is_automated", False)), active_color=palette["primary"])

        modal_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=palette["accent"], visible=False)
        modal_error = ft.Text("", size=11, color=palette["danger"], visible=False)
        dlg = None

        async def _submit_edit_badge(e):
            clean_name = name_ctrl.value.strip()
            if not clean_name:
                modal_error.value = "Badge name cannot be empty."
                modal_error.visible = True
                dlg.update()
                return

            modal_spinner.visible = True
            modal_error.visible = False
            save_btn.disabled = True
            dlg.update()

            payload = {
                "name": clean_name,
                "description": desc_ctrl.value.strip() or None,
                "icon": icon_dropdown.value or "STAR_ROUNDED",
                "color_hex": color_ctrl.value.strip() or "#4CAF50",
                "gradient_start": grad_start_ctrl.value.strip() or None,
                "gradient_end": grad_end_ctrl.value.strip() or None,
                "is_automated": is_auto_ctrl.value,
            }

            st, res = await update_admin_badge_api(admin_state["token"], bid, payload)
            if st == 200:
                dlg.open = False
                page.update()
                show_page_snackbar(page, f"Badge '{clean_name}' updated successfully!")
                await _fetch_badges_cache()
            else:
                modal_spinner.visible = False
                save_btn.disabled = False
                modal_error.value = res.get("detail", "Error updating badge.")
                modal_error.visible = True
                dlg.update()

        save_btn = ft.ElevatedButton(
            content=ft.Row([modal_spinner, ft.Text("Save Changes", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)], tight=True, spacing=6),
            bgcolor=palette["accent"],
            height=38,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: page.run_task(_submit_edit_badge, e),
        )

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=palette["card_bg"],
            title=ft.Row([
                ft.Icon(ft.Icons.EDIT_ROUNDED, color=palette["accent"], size=20),
                ft.Text(f"Edit Badge: {badge.get('slug')}", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
            ], tight=True, spacing=8),
            content=ft.Container(
                width=480,
                height=480,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    spacing=12,
                    controls=[
                        name_ctrl,
                        desc_ctrl,
                        icon_dropdown,
                        color_ctrl,
                        ft.Row([
                            ft.Container(grad_start_ctrl, expand=1),
                            ft.Container(grad_end_ctrl, expand=1),
                        ], spacing=8),
                        is_auto_ctrl,
                        modal_error,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(dlg, "open", False), page.update())),
                save_btn,
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def _open_create_promo_code_modal():
        code_ctrl = ft.TextField(label="Promo Code", hint_text="e.g. WELCOME2026, UNILAG_DROP", border_radius=8, bgcolor=palette["surface"], text_size=12)
        desc_ctrl = ft.TextField(label="Campaign Description", hint_text="e.g. Orientation week welcome grant", border_radius=8, bgcolor=palette["surface"], text_size=12)
        coins_ctrl = ft.TextField(label="Nu-Coins", value="100", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8, bgcolor=palette["surface"], text_size=12)
        ai_credits_ctrl = ft.TextField(label="AI Credits", value="5", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8, bgcolor=palette["surface"], text_size=12)
        trial_days_ctrl = ft.TextField(label="Pro Trial Days", value="0", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8, bgcolor=palette["surface"], text_size=12)

        # Populate strictly from dynamic database cache - zero hardcoded mocks
        badge_options = [ft.dropdown.Option(key="", text="No Badge Awarded")]
        for b in admin_state.get("badges_cache", []):
            b_slug = b.get("slug")
            if b_slug:
                badge_options.append(ft.dropdown.Option(key=b_slug, text=f"🎖️ {b.get('name', b_slug)}"))

        badge_dropdown = ft.Dropdown(
            label="Bonus Honor Badge (Optional)",
            value="",
            options=badge_options,
            border_radius=8,
            bgcolor=palette["surface"],
            text_size=12,
        )

        uni_scope_dropdown = ft.Dropdown(
            label="Scoped University (Optional - Restricts usage to this university)",
            value="",
            options=[ft.dropdown.Option(key="", text="All Universities (Global / Unrestricted)")],
            border_radius=8,
            bgcolor=palette["surface"],
            text_size=12,
        )

        async def _load_uni_scope_async():
            try:
                res = await get_universities()
                if isinstance(res, list) and res:
                    u_opts = [ft.dropdown.Option(key="", text="All Universities (Global / Unrestricted)")]
                    for u in res:
                        u_name = u if isinstance(u, str) else u.get("name")
                        if u_name:
                            u_opts.append(ft.dropdown.Option(key=u_name, text=u_name))
                    uni_scope_dropdown.options = u_opts
                    if dlg and getattr(dlg, "open", False):
                        uni_scope_dropdown.update()
            except Exception:
                pass

        page.run_task(_load_uni_scope_async)

        max_uses_ctrl = ft.TextField(label="Max Total Uses (Leave blank for Unlimited)", hint_text="e.g. 500", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8, bgcolor=palette["surface"], text_size=12)
        is_active_ctrl = ft.Switch(label="Active Immediately", value=True, active_color=palette["primary"])

        modal_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=palette["accent"], visible=False)
        modal_error = ft.Text("", size=11, color=palette["danger"], visible=False)
        dlg = None

        async def _submit_promo(e):
            clean_code = code_ctrl.value.strip().upper()
            if not clean_code:
                modal_error.value = "Promo code string cannot be empty."
                modal_error.visible = True
                dlg.update()
                return

            modal_spinner.visible = True
            modal_error.visible = False
            submit_btn.disabled = True
            dlg.update()

            scoped_uni = uni_scope_dropdown.value if uni_scope_dropdown.value else None
            payload = {
                "code": clean_code,
                "description": desc_ctrl.value.strip() or None,
                "rewards": {
                    "coins": int(coins_ctrl.value.strip() or 0),
                    "ai_credits": int(ai_credits_ctrl.value.strip() or 0),
                    "trial_days": int(trial_days_ctrl.value.strip() or 0),
                    "badge_slug": badge_dropdown.value or None,
                    "scoped_university": scoped_uni,
                },
                "scoped_university": scoped_uni,
                "max_uses": int(max_uses_ctrl.value.strip()) if max_uses_ctrl.value.strip() else None,
                "is_active": is_active_ctrl.value,
            }

            st, res = await create_admin_promo_code_api(admin_state["token"], payload)
            if st in (200, 201):
                dlg.open = False
                page.update()
                show_page_snackbar(page, f"Promo code '{clean_code}' created successfully!")
                await _fetch_promo_codes()
            else:
                modal_spinner.visible = False
                submit_btn.disabled = False
                modal_error.value = res.get("detail", "Error creating promo code.")
                modal_error.visible = True
                dlg.update()

        submit_btn = ft.ElevatedButton(
            content=ft.Row([modal_spinner, ft.Text("Create Code", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)], tight=True, spacing=6),
            bgcolor=palette["accent"],
            height=38,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: page.run_task(_submit_promo, e),
        )

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=palette["card_bg"],
            title=ft.Row([
                ft.Icon(ft.Icons.LOYALTY_ROUNDED, color=palette["accent"], size=20),
                ft.Text("New Multi-Reward Promo Code", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
            ], tight=True, spacing=8),
            content=ft.Container(
                width=480,
                height=500,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    spacing=12,
                    controls=[
                        code_ctrl,
                        desc_ctrl,
                        ft.Text("Reward Grants", size=11, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                        ft.Row([
                            ft.Container(coins_ctrl, expand=1),
                            ft.Container(ai_credits_ctrl, expand=1),
                            ft.Container(trial_days_ctrl, expand=1),
                        ], spacing=8),
                        badge_dropdown,
                        ft.Text("Campus Scope & Limits", size=11, weight=ft.FontWeight.BOLD, color=palette["text_muted"]),
                        uni_scope_dropdown,
                        max_uses_ctrl,
                        is_active_ctrl,
                        modal_error,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(dlg, "open", False), page.update())),
                submit_btn,
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def _open_invite_ambassador_modal():
        email_ctrl = ft.TextField(
            label="Candidate Account Email",
            hint_text="Registered learner's account email (e.g. student@university.edu.ng)",
            border_radius=8,
            bgcolor=palette["surface"],
            text_size=12,
        )

        uni_options = [
            ft.dropdown.Option(key="University of Lagos (UNILAG)", text="University of Lagos (UNILAG)"),
            ft.dropdown.Option(key="University of Ibadan (UI)", text="University of Ibadan (UI)"),
            ft.dropdown.Option(key="Obafemi Awolowo University (OAU)", text="Obafemi Awolowo University (OAU)"),
            ft.dropdown.Option(key="Ahmadu Bello University (ABU)", text="Ahmadu Bello University (ABU)"),
            ft.dropdown.Option(key="University of Nigeria, Nsukka (UNN)", text="University of Nigeria, Nsukka (UNN)"),
            ft.dropdown.Option(key="University of Benin (UNIBEN)", text="University of Benin (UNIBEN)"),
            ft.dropdown.Option(key="University of Ilorin (UNILORIN)", text="University of Ilorin (UNILORIN)"),
            ft.dropdown.Option(key="Covenant University", text="Covenant University"),
            ft.dropdown.Option(key="Lagos State University (LASU)", text="Lagos State University (LASU)"),
            ft.dropdown.Option(key="Federal University of Technology, Akure (FUTA)", text="FUTA"),
        ]
        uni_dropdown = ft.Dropdown(
            label="Nigerian University / Institution",
            value="University of Lagos (UNILAG)",
            options=uni_options,
            border_radius=8,
            bgcolor=palette["surface"],
            text_size=12,
        )

        async def _load_universities_async():
            try:
                res = await get_universities()
                if isinstance(res, list) and res:
                    u_opts = []
                    for u in res:
                        u_name = u if isinstance(u, str) else u.get("name")
                        if u_name:
                            u_opts.append(ft.dropdown.Option(key=u_name, text=u_name))
                    if u_opts:
                        uni_dropdown.options = u_opts
                        if dlg and getattr(dlg, "open", False):
                            uni_dropdown.update()
            except Exception:
                pass

        page.run_task(_load_universities_async)

        notes_ctrl = ft.TextField(
            label="Internal Notes / Outreach Strategy",
            hint_text="e.g. Faculty lead for tech hackathons and exam study groups",
            multiline=True,
            min_lines=2,
            border_radius=8,
            bgcolor=palette["surface"],
            text_size=12,
        )

        # Assigned Promo Code Dropdown
        promo_options = [ft.dropdown.Option(key="", text="None (Assign later or distribute directly)")]
        for p in admin_state.get("promo_codes", []):
            p_code = p.get("code")
            p_id = str(p.get("id"))
            if p_code and p_id:
                p_desc = p.get("description") or "Promo"
                promo_options.append(ft.dropdown.Option(key=p_id, text=f"🏷️ {p_code} ({p_desc[:25]})"))

        promo_dropdown = ft.Dropdown(
            label="Assigned Promo Code (Optional)",
            value="",
            options=promo_options,
            border_radius=8,
            bgcolor=palette["surface"],
            text_size=12,
        )

        modal_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=palette["accent"], visible=False)
        modal_error = ft.Text("", size=11, color=palette["danger"], visible=False)
        dlg = None

        async def _submit_invite(e):
            c_email = email_ctrl.value.strip()
            if not c_email or "@" not in c_email:
                modal_error.value = "A valid registered learner email address is required."
                modal_error.visible = True
                dlg.update()
                return

            modal_spinner.visible = True
            modal_error.visible = False
            invite_btn.disabled = True
            dlg.update()

            payload = {
                "email": c_email,
                "university": uni_dropdown.value or "Campus Partner",
                "notes": notes_ctrl.value.strip() or None,
            }
            if promo_dropdown.value:
                payload["assigned_promo_code_id"] = promo_dropdown.value

            st, res = await invite_admin_ambassador_api(admin_state["token"], payload)
            if st in (200, 201):
                dlg.open = False
                page.update()
                show_page_snackbar(page, f"Invitation sent to {c_email}! Acceptance link delivered via email.")
                await _fetch_ambassadors()
            else:
                modal_spinner.visible = False
                invite_btn.disabled = False
                modal_error.value = res.get("detail", "Error sending invitation.")
                modal_error.visible = True
                dlg.update()

        invite_btn = ft.ElevatedButton(
            content=ft.Row([modal_spinner, ft.Text("Send Invitation", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)], tight=True, spacing=6),
            bgcolor=palette["accent"],
            height=38,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: page.run_task(_submit_invite, e),
        )

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=palette["card_bg"],
            title=ft.Row([
                ft.Icon(ft.Icons.SCHOOL_ROUNDED, color=palette["accent"], size=20),
                ft.Text("Invite Campus Ambassador", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
            ], tight=True, spacing=8),
            content=ft.Container(
                width=480,
                height=420,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    spacing=12,
                    controls=[
                        email_ctrl,
                        uni_dropdown,
                        promo_dropdown,
                        notes_ctrl,
                        modal_error,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(dlg, "open", False), page.update())),
                invite_btn,
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def _build_promo_ambassadors_tab() -> ft.Control:
        cur_subtab = admin_state.get("promo_subtab", "promo_codes")

        def _switch_sub(sub_k: str):
            admin_state["promo_subtab"] = sub_k
            _render_tab_content()
            page.update()

        # Top Subtab Selector Bar
        subtab_bar = ft.Container(
            bgcolor=palette["surface"],
            border=ft.Border.all(1, palette["border"]),
            border_radius=14,
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
                spacing=12,
                controls=[
                    ft.Row([
                        ft.Container(
                            content=ft.Text("Promo Codes & Drops", size=12, weight=ft.FontWeight.BOLD if cur_subtab == "promo_codes" else ft.FontWeight.NORMAL, color=palette["text"] if cur_subtab == "promo_codes" else palette["text_muted"]),
                            bgcolor=ft.Colors.with_opacity(0.18, palette["accent"]) if cur_subtab == "promo_codes" else ft.Colors.TRANSPARENT,
                            border=ft.Border.all(1, palette["accent"] if cur_subtab == "promo_codes" else palette["border"]),
                            border_radius=8,
                            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                            ink=True,
                            on_click=lambda _: _switch_sub("promo_codes"),
                        ),
                        ft.Container(
                            content=ft.Text("Campus Ambassadors", size=12, weight=ft.FontWeight.BOLD if cur_subtab == "ambassadors" else ft.FontWeight.NORMAL, color=palette["text"] if cur_subtab == "ambassadors" else palette["text_muted"]),
                            bgcolor=ft.Colors.with_opacity(0.18, palette["accent"]) if cur_subtab == "ambassadors" else ft.Colors.TRANSPARENT,
                            border=ft.Border.all(1, palette["accent"] if cur_subtab == "ambassadors" else palette["border"]),
                            border_radius=8,
                            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                            ink=True,
                            on_click=lambda _: _switch_sub("ambassadors"),
                        ),
                        ft.Container(
                            content=ft.Text("Honor Badges", size=12, weight=ft.FontWeight.BOLD if cur_subtab == "badges" else ft.FontWeight.NORMAL, color=palette["text"] if cur_subtab == "badges" else palette["text_muted"]),
                            bgcolor=ft.Colors.with_opacity(0.18, palette["accent"]) if cur_subtab == "badges" else ft.Colors.TRANSPARENT,
                            border=ft.Border.all(1, palette["accent"] if cur_subtab == "badges" else palette["border"]),
                            border_radius=8,
                            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                            ink=True,
                            on_click=lambda _: _switch_sub("badges"),
                        ),
                    ], spacing=8, tight=True),
                    ft.Row(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.OutlinedButton(
                                content=ft.Row([ft.Icon(ft.Icons.REFRESH_ROUNDED, size=15), ft.Text("Refresh", size=12)], tight=True, spacing=4),
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=lambda _: (
                                    page.run_task(_fetch_promo_codes) if cur_subtab == "promo_codes"
                                    else (page.run_task(_fetch_ambassadors) if cur_subtab == "ambassadors" else page.run_task(_fetch_badges_cache))
                                ),
                            ),
                            ft.ElevatedButton(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=ft.Colors.WHITE),
                                    ft.Text(
                                        "Create Promo Code" if cur_subtab == "promo_codes"
                                        else ("Invite Ambassador" if cur_subtab == "ambassadors" else "Create Badge"),
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE,
                                    )
                                ], tight=True, spacing=6),
                                bgcolor=palette["accent"],
                                height=38,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                                on_click=lambda _: (
                                    _open_create_promo_code_modal() if cur_subtab == "promo_codes"
                                    else (_open_invite_ambassador_modal() if cur_subtab == "ambassadors" else _open_create_badge_modal())
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        )

        if cur_subtab == "promo_codes":
            all_codes = admin_state.get("promo_codes", [])
            active_codes = [c for c in all_codes if c.get("is_active", True)]
            total_uses = sum(c.get("times_used", 0) for c in all_codes)

            kpi_row = ft.ResponsiveRow(
                spacing=12,
                run_spacing=12,
                controls=[
                    ft.Container(
                        col={"xs": 12, "sm": 4},
                        bgcolor=palette["card_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=12,
                        padding=16,
                        content=ft.Column([
                            ft.Text("Total Promo Codes", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                            ft.Text(f"{len(all_codes):,}", size=22, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ft.Text("Campaign & campus drops", size=10, color=palette["text_muted"]),
                        ], spacing=4),
                    ),
                    ft.Container(
                        col={"xs": 12, "sm": 4},
                        bgcolor=palette["card_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=12,
                        padding=16,
                        content=ft.Column([
                            ft.Text("Active Codes", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                            ft.Text(f"{len(active_codes):,}", size=22, weight=ft.FontWeight.BOLD, color=palette["success"]),
                            ft.Text("Currently redeemable by learners", size=10, color=palette["success"]),
                        ], spacing=4),
                    ),
                    ft.Container(
                        col={"xs": 12, "sm": 4},
                        bgcolor=palette["card_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=12,
                        padding=16,
                        content=ft.Column([
                            ft.Text("Total Redemptions", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                            ft.Text(f"{total_uses:,}", size=22, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                            ft.Text("Rewards successfully claimed", size=10, color=palette["accent"]),
                        ], spacing=4),
                    ),
                ],
            )

            if admin_state.get("is_loading_promo"):
                body = ft.Container(padding=40, alignment=ft.Alignment.CENTER, content=ft.ProgressRing(color=palette["accent"], stroke_width=3))
            elif not all_codes:
                body = ft.Container(
                    bgcolor=palette["card_bg"],
                    border=ft.Border.all(1, palette["border"]),
                    border_radius=14,
                    padding=36,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column([
                        ft.Icon(ft.Icons.LOYALTY_ROUNDED, size=36, color=palette["text_muted"]),
                        ft.Text("No Promo Codes Yet", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text("Create promo codes to distribute rewards to students or empower campus ambassadors.", size=11, color=palette["text_muted"]),
                        ft.Container(height=8),
                        ft.ElevatedButton("Create Promo Code", bgcolor=palette["accent"], color=ft.Colors.WHITE, on_click=lambda _: _open_create_promo_code_modal()),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                )
            else:
                code_cards = []
                for c in all_codes:
                    c_id = str(c.get("id"))
                    is_act = c.get("is_active", True)
                    rewards = c.get("rewards") or {}
                    reward_chips = []
                    if rewards.get("coins"):
                        reward_chips.append(ft.Text(f"🪙 {rewards['coins']} Coins", size=11, color=palette["accent"], weight=ft.FontWeight.BOLD))
                    if rewards.get("ai_credits"):
                        reward_chips.append(ft.Text(f"⚡ {rewards['ai_credits']} AI Credits", size=11, color=palette["info"], weight=ft.FontWeight.BOLD))
                    if rewards.get("trial_days"):
                        reward_chips.append(ft.Text(f"📅 {rewards['trial_days']}d Pro Trial", size=11, color=palette["success"], weight=ft.FontWeight.BOLD))
                    if rewards.get("badge_slug"):
                        reward_chips.append(ft.Text(f"🎖️ {rewards['badge_slug']}", size=11, color=ft.Colors.AMBER_500, weight=ft.FontWeight.BOLD))

                    scoped_uni = c.get("scoped_university") or rewards.get("scoped_university")
                    if scoped_uni:
                        reward_chips.append(ft.Text(f"🏛️ {scoped_uni}", size=11, color=palette["purple"], weight=ft.FontWeight.BOLD))

                    max_u = c.get("max_uses")
                    limit_str = f"{c.get('times_used', 0)} / {max_u if max_u else '∞'}"

                    card = ft.Container(
                        col={"xs": 12, "md": 6},
                        bgcolor=palette["card_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=12,
                        padding=16,
                        content=ft.Column([
                            ft.Row([
                                ft.Row([
                                    ft.Container(
                                        content=ft.Text(c.get("code", "PROMO"), size=13, weight=ft.FontWeight.W_900, color=palette["accent"]),
                                        bgcolor=ft.Colors.with_opacity(0.14, palette["accent"]),
                                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                                        border_radius=8,
                                        border=ft.Border.all(1, palette["accent"]),
                                    ),
                                    ft.Text(c.get("description") or "Platform promo drop", size=11, color=palette["text_muted"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ], spacing=8, tight=True, expand=True),
                                ft.Row([
                                    ft.Switch(value=is_act, active_color=palette["primary"], on_change=lambda e, cid=c_id: page.run_task(_toggle_promo_code_active, cid)),
                                    ft.IconButton(icon=ft.Icons.DELETE_ROUNDED, icon_size=15, icon_color=palette["danger"], on_click=lambda _, cd=c: _prompt_delete_promo_code(cd)),
                                ], spacing=4, tight=True),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Row(reward_chips, spacing=8, wrap=True) if reward_chips else ft.Text("No attached rewards", size=11, color=palette["text_muted"]),
                            ft.Row([
                                ft.Text(f"Usage: {limit_str}", size=10.5, color=palette["text_muted"]),
                                ft.Text(f"Scope: {scoped_uni or 'All Universities'}", size=10.5, color=palette["text_muted"]),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ], spacing=10),
                    )
                    code_cards.append(card)

                body = ft.ResponsiveRow(spacing=12, run_spacing=12, controls=code_cards)

        elif cur_subtab == "ambassadors":
            amb_mode = admin_state.get("ambassador_view_subtab", "roster")
            ambs = admin_state.get("ambassadors", [])
            apps = admin_state.get("ambassador_applications", [])
            pending_apps = [ap for ap in apps if ap.get("status") == "pending"]

            def _switch_amb_mode(mode_k: str):
                admin_state["ambassador_view_subtab"] = mode_k
                _render_tab_content()
                page.update()

            def _set_app_filter(flt: str):
                admin_state["ambassador_applications_filter"] = flt
                page.run_task(_fetch_ambassador_applications)

            # Sub-mode navigation bar
            mode_toggle_bar = ft.Container(
                bgcolor=palette["card_bg"],
                border=ft.Border.all(1, palette["border"]),
                border_radius=10,
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                content=ft.Row([
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.GROUPS_ROUNDED, size=15, color=palette["accent"] if amb_mode == "roster" else palette["text_muted"]),
                            ft.Text(f"Campus Reps & Invites ({len(ambs)})", size=12, weight=ft.FontWeight.BOLD if amb_mode == "roster" else ft.FontWeight.NORMAL, color=palette["text"] if amb_mode == "roster" else palette["text_muted"]),
                        ], tight=True, spacing=6),
                        bgcolor=ft.Colors.with_opacity(0.15, palette["accent"]) if amb_mode == "roster" else ft.Colors.TRANSPARENT,
                        border=ft.Border.all(1, palette["accent"] if amb_mode == "roster" else ft.Colors.TRANSPARENT),
                        border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        ink=True,
                        on_click=lambda _: _switch_amb_mode("roster"),
                    ),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.ASSIGNMENT_IND_ROUNDED, size=15, color=palette["accent"] if amb_mode == "applications" else palette["text_muted"]),
                            ft.Text(f"Applications Review ({len(pending_apps)} New / {len(apps)} Total)", size=12, weight=ft.FontWeight.BOLD if amb_mode == "applications" else ft.FontWeight.NORMAL, color=palette["text"] if amb_mode == "applications" else palette["text_muted"]),
                            ft.Container(
                                visible=len(pending_apps) > 0,
                                bgcolor=palette["warning"],
                                border_radius=10,
                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                content=ft.Text(f"{len(pending_apps)}", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                            ),
                        ], tight=True, spacing=6),
                        bgcolor=ft.Colors.with_opacity(0.15, palette["accent"]) if amb_mode == "applications" else ft.Colors.TRANSPARENT,
                        border=ft.Border.all(1, palette["accent"] if amb_mode == "applications" else ft.Colors.TRANSPARENT),
                        border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        ink=True,
                        on_click=lambda _: _switch_amb_mode("applications"),
                    ),
                ], spacing=8, tight=True),
            )

            if amb_mode == "roster":
                active_ambs = [a for a in ambs if a.get("status") == "active"]
                pending_ambs = [a for a in ambs if a.get("status") == "pending" or a.get("status") == "invited"]
                total_students_ref = sum(a.get("students_referred_count", 0) for a in ambs)

                kpi_row = ft.ResponsiveRow(
                    spacing=12,
                    run_spacing=12,
                    controls=[
                        ft.Container(
                            col={"xs": 12, "sm": 3},
                            bgcolor=palette["card_bg"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=16,
                            content=ft.Column([
                                ft.Text("Total Ambassadors", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                ft.Text(f"{len(ambs):,}", size=22, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ft.Text("Enrolled campus reps", size=10, color=palette["text_muted"]),
                            ], spacing=4),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 3},
                            bgcolor=palette["card_bg"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=16,
                            content=ft.Column([
                                ft.Text("Active Reps", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                ft.Text(f"{len(active_ambs):,}", size=22, weight=ft.FontWeight.BOLD, color=palette["success"]),
                                ft.Text("Actively onboarding students", size=10, color=palette["success"]),
                            ], spacing=4),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 3},
                            bgcolor=palette["card_bg"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=16,
                            content=ft.Column([
                                ft.Text("Pending Invites", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                ft.Text(f"{len(pending_ambs):,}", size=22, weight=ft.FontWeight.BOLD, color=palette["warning"]),
                                ft.Text("Invitation email dispatched", size=10, color=palette["warning"]),
                            ], spacing=4),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 3},
                            bgcolor=palette["card_bg"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=16,
                            content=ft.Column([
                                ft.Text("Total Referrals", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                ft.Text(f"{total_students_ref:,}", size=22, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                                ft.Text("Students joined via reps", size=10, color=palette["accent"]),
                            ], spacing=4),
                        ),
                    ],
                )

                if admin_state.get("is_loading_ambassadors"):
                    body = ft.Container(padding=40, alignment=ft.Alignment.CENTER, content=ft.ProgressRing(color=palette["accent"], stroke_width=3))
                elif not ambs:
                    body = ft.Container(
                        bgcolor=palette["card_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=14,
                        padding=36,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column([
                            ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=36, color=palette["text_muted"]),
                            ft.Text("No Campus Ambassadors Enrolled Yet", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ft.Text("Invite student leaders from universities across Nigeria to represent Nu Age.", size=11, color=palette["text_muted"]),
                            ft.Container(height=8),
                            ft.ElevatedButton("Invite Campus Ambassador", bgcolor=palette["accent"], color=ft.Colors.WHITE, on_click=lambda _: _open_invite_ambassador_modal()),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    )
                else:
                    amb_cards = []
                    for a in ambs:
                        a_id = str(a.get("id"))
                        a_status = a.get("status", "invited")
                        is_active = a_status == "active"
                        is_pending = a_status in ("pending", "invited")
                        status_color = palette["success"] if is_active else (palette["warning"] if is_pending else palette["danger"])

                        async def _change_amb_status(aid, new_st):
                            st, res = await update_admin_ambassador_status_api(admin_state["token"], aid, new_st)
                            if st == 200:
                                show_page_snackbar(page, "Ambassador status updated.")
                                await _fetch_ambassadors()
                            else:
                                show_page_snackbar(page, f"Error: {res.get('detail', 'Could not update status')}")

                        card = ft.Container(
                            col={"xs": 12, "md": 6},
                            bgcolor=palette["card_bg"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=16,
                            content=ft.Column([
                                ft.Row([
                                    ft.Row([
                                        ft.CircleAvatar(
                                            radius=18,
                                            bgcolor=ft.Colors.with_opacity(0.15, palette["accent"]),
                                            content=ft.Text((a.get("name") or a.get("email") or "U")[:2].upper(), size=11, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                                        ),
                                        ft.Column([
                                            ft.Text(a.get("name") or a.get("user_name") or "Registered Learner", size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                            ft.Text(a.get("email", ""), size=11, color=palette["text_muted"]),
                                        ], spacing=2, tight=True),
                                    ], spacing=8, tight=True),
                                    ft.Container(
                                        content=ft.Text(a_status.upper(), size=9, weight=ft.FontWeight.BOLD, color=status_color),
                                        bgcolor=ft.Colors.with_opacity(0.12, status_color),
                                        border=ft.Border.all(1, status_color),
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                        border_radius=6,
                                    ),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([
                                    ft.Icon(ft.Icons.ACCOUNT_BALANCE_ROUNDED, size=13, color=palette["text_muted"]),
                                    ft.Text(a.get("university", "Nigerian University"), size=11, color=palette["text"]),
                                ], spacing=6, tight=True),
                                ft.Row([
                                    ft.Text(f"Code: {a.get('promo_code') or a.get('referral_code') or '—'}", size=11, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                                    ft.Text(f"Referrals: {a.get('students_referred_count', 0)} students", size=11, color=palette["text_muted"]),
                                    ft.Text(f"Earnings: {a.get('total_coins_earned', 0)} Coins", size=11, color=ft.Colors.AMBER_500),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([
                                    ft.OutlinedButton(
                                        "Suspend" if is_active else "Activate",
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                                        on_click=lambda _, aid=a_id, nst=("suspended" if is_active else "active"): page.run_task(_change_amb_status, aid, nst),
                                    ),
                                ], alignment=ft.MainAxisAlignment.END),
                            ], spacing=10),
                        )
                        amb_cards.append(card)

                    body = ft.ResponsiveRow(spacing=12, run_spacing=12, controls=amb_cards)

                body = ft.Column([mode_toggle_bar, kpi_row, body], spacing=14)

            else:
                # APPLICATIONS SUB-MODE
                cur_filter = admin_state.get("ambassador_applications_filter", "all")
                all_apps = apps
                filtered_apps = [ap for ap in apps if cur_filter == "all" or ap.get("status") == cur_filter]
                app_pending_count = sum(1 for ap in all_apps if ap.get("status") == "pending")
                app_approved_count = sum(1 for ap in all_apps if ap.get("status") == "approved")
                app_rejected_count = sum(1 for ap in all_apps if ap.get("status") == "rejected")

                kpi_row = ft.ResponsiveRow(
                    spacing=12,
                    run_spacing=12,
                    controls=[
                        ft.Container(
                            col={"xs": 12, "sm": 3},
                            bgcolor=palette["card_bg"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=16,
                            content=ft.Column([
                                ft.Text("Total Applications", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                ft.Text(f"{len(all_apps):,}", size=22, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                ft.Text("Form submissions from website", size=10, color=palette["text_muted"]),
                            ], spacing=4),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 3},
                            bgcolor=palette["card_bg"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=16,
                            content=ft.Column([
                                ft.Text("Pending Review", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                ft.Text(f"{app_pending_count:,}", size=22, weight=ft.FontWeight.BOLD, color=palette["warning"]),
                                ft.Text("Awaiting verification & decision", size=10, color=palette["warning"]),
                            ], spacing=4),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 3},
                            bgcolor=palette["card_bg"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=16,
                            content=ft.Column([
                                ft.Text("Approved & Invited", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                ft.Text(f"{app_approved_count:,}", size=22, weight=ft.FontWeight.BOLD, color=palette["success"]),
                                ft.Text("Invitation email delivered", size=10, color=palette["success"]),
                            ], spacing=4),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 3},
                            bgcolor=palette["card_bg"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=16,
                            content=ft.Column([
                                ft.Text("Rejected", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                                ft.Text(f"{app_rejected_count:,}", size=22, weight=ft.FontWeight.BOLD, color=palette["danger"]),
                                ft.Text("Did not meet criteria", size=10, color=palette["danger"]),
                            ], spacing=4),
                        ),
                    ],
                )

                # Filter buttons
                filter_bar = ft.Row([
                    ft.Container(
                        content=ft.Text("All Submissions", size=11, weight=ft.FontWeight.BOLD if cur_filter == "all" else ft.FontWeight.NORMAL, color=palette["text"] if cur_filter == "all" else palette["text_muted"]),
                        bgcolor=ft.Colors.with_opacity(0.12, palette["accent"]) if cur_filter == "all" else ft.Colors.TRANSPARENT,
                        border=ft.Border.all(1, palette["accent"] if cur_filter == "all" else palette["border"]),
                        border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        ink=True,
                        on_click=lambda _: _set_app_filter("all"),
                    ),
                    ft.Container(
                        content=ft.Text(f"Pending ({app_pending_count})", size=11, weight=ft.FontWeight.BOLD if cur_filter == "pending" else ft.FontWeight.NORMAL, color=palette["warning"] if cur_filter == "pending" else palette["text_muted"]),
                        bgcolor=ft.Colors.with_opacity(0.12, palette["warning"]) if cur_filter == "pending" else ft.Colors.TRANSPARENT,
                        border=ft.Border.all(1, palette["warning"] if cur_filter == "pending" else palette["border"]),
                        border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        ink=True,
                        on_click=lambda _: _set_app_filter("pending"),
                    ),
                    ft.Container(
                        content=ft.Text(f"Approved ({app_approved_count})", size=11, weight=ft.FontWeight.BOLD if cur_filter == "approved" else ft.FontWeight.NORMAL, color=palette["success"] if cur_filter == "approved" else palette["text_muted"]),
                        bgcolor=ft.Colors.with_opacity(0.12, palette["success"]) if cur_filter == "approved" else ft.Colors.TRANSPARENT,
                        border=ft.Border.all(1, palette["success"] if cur_filter == "approved" else palette["border"]),
                        border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        ink=True,
                        on_click=lambda _: _set_app_filter("approved"),
                    ),
                    ft.Container(
                        content=ft.Text(f"Rejected ({app_rejected_count})", size=11, weight=ft.FontWeight.BOLD if cur_filter == "rejected" else ft.FontWeight.NORMAL, color=palette["danger"] if cur_filter == "rejected" else palette["text_muted"]),
                        bgcolor=ft.Colors.with_opacity(0.12, palette["danger"]) if cur_filter == "rejected" else ft.Colors.TRANSPARENT,
                        border=ft.Border.all(1, palette["danger"] if cur_filter == "rejected" else palette["border"]),
                        border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        ink=True,
                        on_click=lambda _: _set_app_filter("rejected"),
                    ),
                ], spacing=6, tight=True)

                if admin_state.get("is_loading_ambassador_applications"):
                    app_body = ft.Container(padding=40, alignment=ft.Alignment.CENTER, content=ft.ProgressRing(color=palette["accent"], stroke_width=3))
                elif not filtered_apps:
                    app_body = ft.Container(
                        bgcolor=palette["card_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=14,
                        padding=36,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column([
                            ft.Icon(ft.Icons.INBOX_ROUNDED, size=36, color=palette["text_muted"]),
                            ft.Text("No Applications Found", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ft.Text("Public submissions from https://nu-age.name.ng/ambassadors will appear here.", size=11, color=palette["text_muted"]),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    )
                else:
                    app_cards = []
                    for ap in filtered_apps:
                        ap_id = str(ap.get("id"))
                        ap_st = ap.get("status", "pending")
                        is_on_plat = bool(ap.get("is_on_platform"))
                        courses_cnt = ap.get("courses_enrolled_count", 0)
                        coins_cnt = ap.get("coins_balance", 0)
                        streak_cnt = ap.get("streak", 0)
                        reg_date = ap.get("registered_at", "")[:10] if ap.get("registered_at") else "—"
                        app_date = ap.get("created_at", "")[:10] if ap.get("created_at") else "—"

                        st_color = palette["warning"] if ap_st == "pending" else (palette["success"] if ap_st == "approved" else palette["danger"])

                        # Action handlers
                        async def _approve_app(appid):
                            show_page_snackbar(page, "Approving application and delivering invitation...")
                            st, res = await approve_ambassador_application_api(admin_state["token"], appid)
                            if st in (200, 201):
                                show_page_snackbar(page, res.get("message", "Application approved! Invitation dispatched."))
                                await _fetch_ambassador_applications()
                                await _fetch_ambassadors()
                            else:
                                show_page_snackbar(page, f"Error: {res.get('detail', 'Could not approve application.')}")

                        async def _reject_app(appid):
                            st, res = await reject_ambassador_application_api(admin_state["token"], appid)
                            if st == 200:
                                show_page_snackbar(page, "Application rejected.")
                                await _fetch_ambassador_applications()
                            else:
                                show_page_snackbar(page, f"Error: {res.get('detail', 'Could not reject application.')}")

                        # Platform stats pill
                        if is_on_plat:
                            platform_box = ft.Container(
                                bgcolor=ft.Colors.with_opacity(0.10, palette["success"]),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, palette["success"])),
                                border_radius=8,
                                padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                                content=ft.Column([
                                    ft.Row([
                                        ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=14, color=palette["success"]),
                                        ft.Text(f"Registered Learner (@{ap.get('username') or 'learner'})", size=11, weight=ft.FontWeight.BOLD, color=palette["success"]),
                                    ], spacing=6, tight=True),
                                    ft.Row([
                                        ft.Text(f"📚 {courses_cnt} Course(s)", size=10.5, color=palette["text"]),
                                        ft.Text(f"🪙 {coins_cnt} Coins", size=10.5, color=ft.Colors.AMBER_500),
                                        ft.Text(f"🔥 {streak_cnt}d Streak", size=10.5, color=palette["accent"]),
                                        ft.Text(f"Joined {reg_date}", size=10.5, color=palette["text_muted"]),
                                    ], spacing=10, wrap=True),
                                ], spacing=4),
                            )
                        else:
                            platform_box = ft.Container(
                                bgcolor=ft.Colors.with_opacity(0.10, palette["warning"]),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, palette["warning"])),
                                border_radius=8,
                                padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                                content=ft.Row([
                                    ft.Icon(ft.Icons.PERSON_SEARCH_ROUNDED, size=15, color=palette["warning"]),
                                    ft.Column([
                                        ft.Text("Not on Nu Age Platform Yet", size=11, weight=ft.FontWeight.BOLD, color=palette["warning"]),
                                        ft.Text("Applicant will receive download & registration instructions with invitation.", size=10, color=palette["text_muted"]),
                                    ], spacing=2, tight=True),
                                ], spacing=8, tight=True),
                            )

                        # Motivation notes quote
                        notes_txt = ap.get("notes")
                        notes_box = None
                        if notes_txt:
                            notes_box = ft.Container(
                                bgcolor=ft.Colors.with_opacity(0.05, palette["text"]),
                                border_radius=6,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                                content=ft.Text(f'"{notes_txt}"', size=11, italic=True, color=palette["text_muted"], max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                            )

                        # Action buttons
                        if ap_st == "pending":
                            action_row = ft.Row([
                                ft.OutlinedButton(
                                    content=ft.Text("Reject", size=11, color=palette["danger"]),
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                                    on_click=lambda _, aid=ap_id: page.run_task(_reject_app, aid),
                                ),
                                ft.ElevatedButton(
                                    content=ft.Row([ft.Icon(ft.Icons.SEND_ROUNDED, size=13, color=ft.Colors.WHITE), ft.Text("Approve & Invite", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)], tight=True, spacing=4),
                                    bgcolor=palette["accent"],
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                                    on_click=lambda _, aid=ap_id: page.run_task(_approve_app, aid),
                                ),
                            ], spacing=8, alignment=ft.MainAxisAlignment.END)
                        elif ap_st == "approved":
                            action_row = ft.Row([
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=15, color=palette["success"]),
                                ft.Text("Invitation Sent", size=11, weight=ft.FontWeight.BOLD, color=palette["success"]),
                            ], spacing=6, alignment=ft.MainAxisAlignment.END)
                        else:
                            action_row = ft.Row([
                                ft.Icon(ft.Icons.CANCEL_ROUNDED, size=15, color=palette["danger"]),
                                ft.Text("Application Rejected", size=11, color=palette["danger"]),
                            ], spacing=6, alignment=ft.MainAxisAlignment.END)

                        card = ft.Container(
                            col={"xs": 12, "md": 6},
                            bgcolor=palette["card_bg"],
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=12,
                            padding=16,
                            content=ft.Column([
                                ft.Row([
                                    ft.Row([
                                        ft.CircleAvatar(
                                            radius=18,
                                            bgcolor=ft.Colors.with_opacity(0.15, palette["accent"]),
                                            content=ft.Text((ap.get("full_name") or "A")[:2].upper(), size=11, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                                        ),
                                        ft.Column([
                                            ft.Text(ap.get("full_name", "Applicant"), size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                            ft.Text(ap.get("email", ""), size=11, color=palette["text_muted"]),
                                        ], spacing=2, tight=True),
                                    ], spacing=8, tight=True),
                                    ft.Container(
                                        content=ft.Text(ap_st.upper(), size=9, weight=ft.FontWeight.BOLD, color=st_color),
                                        bgcolor=ft.Colors.with_opacity(0.12, st_color),
                                        border=ft.Border.all(1, st_color),
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                        border_radius=6,
                                    ),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                platform_box,
                                ft.Row([
                                    ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=13, color=palette["text_muted"]),
                                    ft.Text(f"{ap.get('university', '—')} • {ap.get('department', '—')} ({ap.get('level', '—')})", size=11, color=palette["text"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                                ], spacing=6),
                                ft.Row([
                                    ft.Text(f"📞 {ap.get('phone') or 'No phone provided'}", size=10.5, color=palette["text_muted"]),
                                    ft.Text(f"Applied: {app_date}", size=10.5, color=palette["text_muted"]),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                notes_box if notes_box else ft.Container(),
                                action_row,
                            ], spacing=10),
                        )
                        app_cards.append(card)

                    app_body = ft.ResponsiveRow(spacing=12, run_spacing=12, controls=app_cards)

                body = ft.Column([mode_toggle_bar, kpi_row, filter_bar, app_body], spacing=14)

        else:
            # Honor Badges Subtab
            badges = admin_state.get("badges_cache", [])
            automated_count = sum(1 for b in badges if b.get("is_automated"))
            custom_count = len(badges) - automated_count

            kpi_row = ft.ResponsiveRow(
                spacing=12,
                run_spacing=12,
                controls=[
                    ft.Container(
                        col={"xs": 12, "sm": 4},
                        bgcolor=palette["card_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=12,
                        padding=16,
                        content=ft.Column([
                            ft.Text("Total Honor Badges", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                            ft.Text(f"{len(badges):,}", size=22, weight=ft.FontWeight.BOLD, color=palette["text"]),
                            ft.Text("Registered platform badges", size=10, color=palette["text_muted"]),
                        ], spacing=4),
                    ),
                    ft.Container(
                        col={"xs": 12, "sm": 4},
                        bgcolor=palette["card_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=12,
                        padding=16,
                        content=ft.Column([
                            ft.Text("Automated Badges", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                            ft.Text(f"{automated_count:,}", size=22, weight=ft.FontWeight.BOLD, color=palette["success"]),
                            ft.Text("Awarded via engine milestones", size=10, color=palette["success"]),
                        ], spacing=4),
                    ),
                    ft.Container(
                        col={"xs": 12, "sm": 4},
                        bgcolor=palette["card_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=12,
                        padding=16,
                        content=ft.Column([
                            ft.Text("Custom Badges", size=11, color=palette["text_muted"], weight=ft.FontWeight.W_600),
                            ft.Text(f"{custom_count:,}", size=22, weight=ft.FontWeight.BOLD, color=palette["accent"]),
                            ft.Text("Manually or promo assigned", size=10, color=palette["accent"]),
                        ], spacing=4),
                    ),
                ],
            )

            if admin_state.get("is_loading_badges"):
                body = ft.Container(padding=40, alignment=ft.Alignment.CENTER, content=ft.ProgressRing(color=palette["accent"], stroke_width=3))
            elif not badges:
                body = ft.Container(
                    bgcolor=palette["card_bg"],
                    border=ft.Border.all(1, palette["border"]),
                    border_radius=14,
                    padding=36,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column([
                        ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, size=36, color=palette["text_muted"]),
                        ft.Text("No Honor Badges Registered Yet", size=14, weight=ft.FontWeight.BOLD, color=palette["text"]),
                        ft.Text("Create custom or automated honor badges to recognize student achievements.", size=11, color=palette["text_muted"]),
                        ft.Container(height=8),
                        ft.ElevatedButton("Create Honor Badge", bgcolor=palette["accent"], color=ft.Colors.WHITE, on_click=lambda _: _open_create_badge_modal()),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                )
            else:
                badge_cards = []
                for b in badges:
                    b_id = str(b.get("id"))
                    is_auto = bool(b.get("is_automated", False))
                    b_color = b.get("color_hex") or palette["accent"]
                    icon_name = b.get("icon", "STAR_ROUNDED")
                    badge_icon = getattr(ft.Icons, icon_name, ft.Icons.STAR_ROUNDED)

                    card = ft.Container(
                        col={"xs": 12, "md": 6},
                        bgcolor=palette["card_bg"],
                        border=ft.Border.all(1, palette["border"]),
                        border_radius=12,
                        padding=16,
                        content=ft.Column([
                            ft.Row([
                                ft.Row([
                                    ft.Container(
                                        content=ft.Icon(badge_icon, size=20, color=ft.Colors.WHITE),
                                        bgcolor=b_color,
                                        width=38,
                                        height=38,
                                        border_radius=10,
                                        alignment=ft.Alignment.CENTER,
                                    ),
                                    ft.Column([
                                        ft.Text(b.get("name", "Badge"), size=13, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                        ft.Text(f"slug: {b.get('slug', '')}", size=11, color=palette["text_muted"]),
                                    ], spacing=2, tight=True),
                                ], spacing=10, tight=True, expand=True),
                                ft.Container(
                                    content=ft.Text("AUTOMATED" if is_auto else "CUSTOM", size=9, weight=ft.FontWeight.BOLD, color=palette["success"] if is_auto else palette["accent"]),
                                    bgcolor=ft.Colors.with_opacity(0.12, palette["success"] if is_auto else palette["accent"]),
                                    border=ft.Border.all(1, palette["success"] if is_auto else palette["accent"]),
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                    border_radius=6,
                                ),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Text(b.get("description") or "Honor badge for platform learners.", size=11.5, color=palette["text_muted"], max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Row([
                                ft.Row([
                                    ft.Container(width=12, height=12, bgcolor=b_color, border_radius=6),
                                    ft.Text(b_color, size=10.5, color=palette["text_muted"]),
                                ], spacing=6, tight=True),
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_ROUNDED,
                                        icon_size=16,
                                        icon_color=palette["accent"],
                                        tooltip="Edit Badge",
                                        on_click=lambda _, bg=b: _open_edit_badge_modal(bg),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_ROUNDED,
                                        icon_size=16,
                                        icon_color=palette["danger"],
                                        tooltip="Delete Badge",
                                        on_click=lambda _, bg=b: _prompt_delete_badge(bg),
                                    ),
                                ], spacing=2, tight=True),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ], spacing=10),
                    )
                    badge_cards.append(card)

                body = ft.ResponsiveRow(spacing=12, run_spacing=12, controls=badge_cards)

        return ft.Container(
            expand=True,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=16,
                controls=[
                    subtab_bar,
                    kpi_row,
                    body,
                    ft.Container(height=40),
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
        elif admin_state["active_tab"] == "store_studio":
            active_content_area.content = _build_store_studio_tab()
        elif admin_state["active_tab"] == "study_packs":
            active_content_area.content = _build_study_packs_tab()
        elif admin_state["active_tab"] == "objectives":
            active_content_area.content = _build_objectives_tab()
        elif admin_state["active_tab"] == "promo_ambassadors":
            active_content_area.content = _build_promo_ambassadors_tab()
        elif admin_state["active_tab"] == "audio_studio":
            active_content_area.content = _build_audio_studio_tab()
        elif admin_state["active_tab"] == "categories":
            active_content_area.content = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, controls=[categories_panel.control])
        elif admin_state["active_tab"] == "system_tools":
            active_content_area.content = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, controls=[system_tools_panel.control])
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
                                    ft.Text("Nu Age Control Plane", size=15, weight=ft.FontWeight.BOLD, color=palette["text"]),
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
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    expand=True,
                    padding=16,
                    content=main_container,
                ),
            )
        ],
    )