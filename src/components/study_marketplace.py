import asyncio
import re
from typing import Optional, Callable, Dict, Any, List
import flet as ft

from src.requests.marketplace import (
    fetch_marketplace_packs,
    fetch_pack_detail,
    submit_study_pack,
    download_study_pack,
    toggle_like_pack,
    fetch_my_submissions,
    fetch_admin_pending_submissions,
    review_admin_submission,
    fetch_marketplace_bundles,
    download_study_bundle,
)
from src.components.study_pack_card import StudyPackCard, CATEGORY_PRESETS
from src.components.study_bundle_card import StudyBundleCard
from src.utils.file_opener import show_page_snackbar

# ── THEME PRESETS ─────────────────────────────────────────────────────────────
GRADIENT_PRESETS = {
    "emerald_teal": (ft.Colors.TEAL_700, ft.Colors.GREEN_900, ft.Icons.ECO_ROUNDED),
    "amber_rose": (ft.Colors.AMBER_800, ft.Colors.DEEP_ORANGE_800, ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED),
    "ocean_cyan": (ft.Colors.CYAN_800, ft.Colors.BLUE_900, ft.Icons.WATER_DROP_ROUNDED),
}

CATEGORIES = [
    ("All", ft.Icons.GRID_VIEW_ROUNDED),
    ("Official", ft.Icons.VERIFIED_ROUNDED),
    ("JAMB UTME", ft.Icons.WORKSPACE_PREMIUM_ROUNDED),
    ("WAEC / NECO", ft.Icons.SCHOOL_ROUNDED),
    ("Medicine", ft.Icons.LOCAL_HOSPITAL_ROUNDED),
    ("STEM", ft.Icons.TERMINAL_ROUNDED),
    ("Law", ft.Icons.GAVEL_ROUNDED),
    ("Business", ft.Icons.INSIGHTS_ROUNDED),
    ("Languages", ft.Icons.TRANSLATE_ROUNDED),
    ("Exam Prep", ft.Icons.TIMER_ROUNDED),
]


class StudyMarketplaceView:
    """
    World-Class Generation Pack Marketplace & Community Hub.
    Allows students to discover, preview, download, and publish curated study packs.
    """
    def __init__(
        self,
        page: ft.Page,
        token: str,
        user_vault_materials: List[Dict[str, Any]],
        on_pack_downloaded: Callable[[str], None],
        on_navigate_back: Callable[[], None],
        on_open_coins_modal: Optional[Callable[[], None]] = None,
        is_admin: bool = False,
    ):
        self.page = page
        self.token = token
        self.user_vault_materials = user_vault_materials or []
        self.on_pack_downloaded = on_pack_downloaded
        self.on_navigate_back = on_navigate_back
        self.on_open_coins_modal = on_open_coins_modal
        self.is_admin = is_admin

        # State
        self.active_category = "All"
        self.search_query = ""
        self.sort_by = "popular"
        self.user_coins = 100
        self.packs: List[Dict[str, Any]] = []
        self.is_loading = True
        self.active_tab = "browse"  # "browse", "bundles", "my_submissions"
        self.admin_pending_count = 0
        self._load_seq = 0  # guards against stale/out-of-order responses
        self.my_submissions: List[Dict[str, Any]] = []
        self.submissions_stats: Dict[str, Any] = {"total_packs": 0, "total_coins_earned": 0}
        self.is_loading_submissions = False

        # Study Bundles State
        self.bundles: List[Dict[str, Any]] = []
        self.is_loading_bundles = False
        self.active_bundle_category = "All"

        # UI Slots
        self.category_row: Optional[ft.Row] = None
        # No expand=True here: it sits inside a ListView (unbounded height)
        self.content_container = ft.Container()
        self.main_body_container = ft.Container()
        self.subnav_bar_container = ft.Container()
        self.coins_badge_text = ft.Text(" Loading", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_400)
        self.header_actions_row = ft.Row(
            spacing=8,
            run_spacing=8,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[],
        )

        # Build Main View Container
        self.view_root = self._build_layout()

        # Trigger Initial Fetches
        self.page.run_task(self._load_data)
        self.page.run_task(self._load_submissions_data)
        self.page.run_task(self._load_bundles_data)

    # ─────────────────────────────────────────────────────────────────────────
    # DATA LOADING
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_data(self):
        # Each call gets a unique id; only the most recent call may update the UI.
        self._load_seq += 1
        seq = self._load_seq

        self.is_loading = True
        self._render_state()

        category = self.active_category
        official_only = (category == "Official")
        cat_filter = None if category in ("All", "Official") else category

        try:
            res = await fetch_marketplace_packs(
                token=self.token,
                category=cat_filter,
                search=self.search_query,
                official_only=official_only,
                sort_by=self.sort_by,
                page=1,
                limit=30,
            )
        except Exception as ex:
            if seq != self._load_seq:
                return
            self.packs = []
            self.is_loading = False
            self._render_state()
            show_page_snackbar(self.page, f"Couldn't load packs: {ex}")
            return

        # A newer request was started while this one was in flight: drop this result.
        if seq != self._load_seq:
            return

        if isinstance(res, dict) and "error" in res and "items" not in res:
            self.packs = []
            show_page_snackbar(self.page, str(res.get("error", "Failed to load packs.")))
        else:
            self.packs = res.get("items", []) or []
            self.user_coins = res.get("user_balance", self.user_coins)
            self.coins_badge_text.value = f" {self.user_coins} Coins"

        # Render the packs immediately; don't make them wait on the admin count.
        self.is_loading = False
        self._render_state()

        if self.is_admin:
            try:
                pending_res = await fetch_admin_pending_submissions(self.token, page=1, limit=50)
                if seq == self._load_seq:
                    self.admin_pending_count = pending_res.get("total", 0)
                    self._update_header_actions()
            except Exception:
                pass

    async def _load_submissions_data(self):
        self.is_loading_submissions = True
        if self.active_tab == "my_submissions":
            self._render_state()
        try:
            res = await fetch_my_submissions(self.token)
            if isinstance(res, dict) and "error" not in res:
                self.my_submissions = res.get("items", []) or []
                self.submissions_stats = {
                    "total_packs": res.get("total_packs", len(self.my_submissions)),
                    "total_coins_earned": res.get("total_coins_earned", 0),
                }
            elif isinstance(res, dict) and res.get("items"):
                self.my_submissions = res.get("items", [])
                self.submissions_stats = {
                    "total_packs": res.get("total_packs", len(self.my_submissions)),
                    "total_coins_earned": res.get("total_coins_earned", 0),
                }
        except Exception:
            pass
        finally:
            self.is_loading_submissions = False
            self._render_state()

    async def _load_bundles_data(self):
        self.is_loading_bundles = True
        if self.active_tab == "bundles":
            self._render_state()
        try:
            cat = None if self.active_bundle_category == "All" else self.active_bundle_category
            res = await fetch_marketplace_bundles(token=self.token, category=cat)
            if isinstance(res, dict) and "bundles" in res:
                self.bundles = res.get("bundles", []) or []
        except Exception:
            self.bundles = []
        finally:
            self.is_loading_bundles = False
            if self.active_tab == "bundles":
                self._render_state()

    def _switch_tab(self, tab_name: str):
        if self.active_tab == tab_name:
            return
        self.active_tab = tab_name
        if tab_name == "my_submissions":
            self.page.run_task(self._load_submissions_data)
        elif tab_name == "bundles":
            self.page.run_task(self._load_bundles_data)
        elif tab_name == "browse":
            if not self.packs:
                self.page.run_task(self._load_data)
        self._render_state()

    # ─────────────────────────────────────────────────────────────────────────
    # LAYOUT ASSEMBLY
    # ─────────────────────────────────────────────────────────────────────────
    def _build_layout(self) -> ft.Container:
        self.subnav_bar_container = ft.Container(
            content=self._build_subnav_tabs_content()
        )
        self.main_body_container = ft.Container(
            padding=ft.Padding.only(left=20, right=20, top=16, bottom=24),
            content=ft.Column(
                spacing=18,
                controls=[
                    self._build_hero_spotlight(),
                    self._build_search_and_filters_bar(),
                    self.content_container,
                ],
            ),
        )
        return ft.Container(
            expand=True,
            bgcolor="#F8FAFC",
            # One ListView for everything, so the content scrolls cleanly
            content=ft.ListView(
                expand=True,
                spacing=0,
                controls=[
                    self.subnav_bar_container,
                    self.main_body_container,
                ],
            ),
        )

    def _build_subnav_tabs_content(self) -> ft.Control:
        is_browse = (self.active_tab == "browse")
        is_bundles = (self.active_tab == "bundles")
        is_subs = (self.active_tab == "my_submissions")
        subs_count = len(self.my_submissions)
        bundles_count = len(self.bundles)

        self._update_header_actions()

        capsule_tabs = ft.Container(
            padding=ft.Padding.all(4),
            border_radius=ft.BorderRadius.all(12),
            bgcolor="#F1F5F9",
            border=ft.Border.all(1, "#E2E8F0"),
            content=ft.Row(
                tight=True,
                spacing=4,
                controls=[
                    # Browse Store Tab
                    ft.Container(
                        ink=True,
                        on_click=lambda _: self._switch_tab("browse"),
                        padding=ft.Padding.symmetric(horizontal=14, vertical=7),
                        border_radius=ft.BorderRadius.all(9),
                        bgcolor="#FFFFFF" if is_browse else ft.Colors.TRANSPARENT,
                        shadow=ft.BoxShadow(
                            blur_radius=4,
                            spread_radius=0,
                            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                            offset=ft.Offset(0, 1),
                        ) if is_browse else None,
                        content=ft.Row(
                            tight=True,
                            spacing=6,
                            controls=[
                                ft.Icon(
                                    ft.Icons.STOREFRONT_ROUNDED,
                                    size=15,
                                    color="#059669" if is_browse else "#64748B",
                                ),
                                ft.Text(
                                    "Browse Store",
                                    size=12,
                                    weight=ft.FontWeight.W_800 if is_browse else ft.FontWeight.W_600,
                                    color="#0F172A" if is_browse else "#64748B",
                                ),
                            ],
                        ),
                    ),
                    # Exam Combos & Bundles Tab
                    ft.Container(
                        ink=True,
                        on_click=lambda _: self._switch_tab("bundles"),
                        padding=ft.Padding.symmetric(horizontal=14, vertical=7),
                        border_radius=ft.BorderRadius.all(9),
                        bgcolor="#FFFFFF" if is_bundles else ft.Colors.TRANSPARENT,
                        shadow=ft.BoxShadow(
                            blur_radius=4,
                            spread_radius=0,
                            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                            offset=ft.Offset(0, 1),
                        ) if is_bundles else None,
                        content=ft.Row(
                            tight=True,
                            spacing=6,
                            controls=[
                                ft.Icon(
                                    ft.Icons.AUTO_AWESOME_MOTION_ROUNDED,
                                    size=15,
                                    color="#6366F1" if is_bundles else "#64748B",
                                ),
                                ft.Text(
                                    "Exam Combos",
                                    size=12,
                                    weight=ft.FontWeight.W_800 if is_bundles else ft.FontWeight.W_600,
                                    color="#0F172A" if is_bundles else "#64748B",
                                ),
                                *(
                                    [
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=1.5),
                                            border_radius=ft.BorderRadius.all(10),
                                            bgcolor="#EEF2FF" if is_bundles else "#E2E8F0",
                                            border=ft.Border.all(1, "#C7D2FE" if is_bundles else "#CBD5E1"),
                                            content=ft.Text(
                                                str(bundles_count),
                                                size=10,
                                                weight=ft.FontWeight.W_800,
                                                color="#4F46E5" if is_bundles else "#475569",
                                            ),
                                        )
                                    ] if bundles_count > 0 else []
                                ),
                            ],
                        ),
                    ),
                    # My Submissions Tab
                    ft.Container(
                        ink=True,
                        on_click=lambda _: self._switch_tab("my_submissions"),
                        padding=ft.Padding.symmetric(horizontal=14, vertical=7),
                        border_radius=ft.BorderRadius.all(9),
                        bgcolor="#FFFFFF" if is_subs else ft.Colors.TRANSPARENT,
                        shadow=ft.BoxShadow(
                            blur_radius=4,
                            spread_radius=0,
                            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                            offset=ft.Offset(0, 1),
                        ) if is_subs else None,
                        content=ft.Row(
                            tight=True,
                            spacing=6,
                            controls=[
                                ft.Icon(
                                    ft.Icons.OUTBOX_ROUNDED,
                                    size=15,
                                    color="#059669" if is_subs else "#64748B",
                                ),
                                ft.Text(
                                    "My Submissions",
                                    size=12,
                                    weight=ft.FontWeight.W_800 if is_subs else ft.FontWeight.W_600,
                                    color="#0F172A" if is_subs else "#64748B",
                                ),
                                *(
                                    [
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=1.5),
                                            border_radius=ft.BorderRadius.all(10),
                                            bgcolor="#ECFDF5" if is_subs else "#E2E8F0",
                                            border=ft.Border.all(1, "#A7F3D0" if is_subs else "#CBD5E1"),
                                            content=ft.Text(
                                                str(subs_count),
                                                size=10,
                                                weight=ft.FontWeight.W_800,
                                                color="#059669" if is_subs else "#475569",
                                            ),
                                        )
                                    ] if subs_count > 0 else []
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            bgcolor="#FFFFFF",
            border=ft.Border.only(bottom=ft.BorderSide(1, "#E2E8F0")),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
                spacing=10,
                run_spacing=8,
                controls=[
                    capsule_tabs,
                    self.header_actions_row,
                ],
            ),
        )

    def _build_publish_button(self, label: str = "Publish Pack") -> ft.Container:
        """Sleek pill-shaped emerald button with high-contrast text."""
        return ft.Container(
            ink=True,
            on_click=lambda _: self._open_submission_dialog(),
            tooltip="Share your own study pack with the community",
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            border_radius=ft.BorderRadius.all(10),
            bgcolor="#059669",
            shadow=ft.BoxShadow(
                blur_radius=8,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.25, "#059669"),
                offset=ft.Offset(0, 2),
            ),
            content=ft.Row(
                tight=True,
                spacing=7,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color="#FFFFFF"),
                    ft.Text(label, size=12.5, weight=ft.FontWeight.W_800, color="#FFFFFF"),
                ],
            ),
        )

    def _update_header_actions(self):
        actions = []
        if self.is_admin:
            badge_label = f"Super Admin Console ({self.admin_pending_count})" if self.admin_pending_count > 0 else "Super Admin Console"
            actions.append(
                ft.Container(
                    ink=True,
                    on_click=lambda _: self.page.go("/platform-admin"),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor="#FEF3C7",
                    border=ft.Border.all(1, "#FDE68A"),
                    tooltip="Open Platform Super Admin Console: Unified review queue & catalog manager",
                    content=ft.Row(
                        tight=True,
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED, size=16, color="#B45309"),
                            ft.Text(badge_label, size=12, weight=ft.FontWeight.W_700, color="#92400E"),
                        ],
                    ),
                )
            )

        actions.extend([
            # Coin Balance Badge
            ft.Container(
                ink=True,
                on_click=lambda _: self.on_open_coins_modal() if self.on_open_coins_modal else None,
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=ft.BorderRadius.all(10),
                bgcolor="#FFFBEB",
                border=ft.Border.all(1.2, "#FCD34D"),
                tooltip="Your Nu-Coins balance. Tap to view Studio & Top Up",
                content=ft.Row(
                    tight=True,
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=16, color="#D97706"),
                        ft.Text(self.coins_badge_text.value, size=12, weight=ft.FontWeight.W_800, color="#92400E"),
                    ],
                ),
            ),
            # Share My Pack Button
            self._build_publish_button(),
        ])
        self.header_actions_row.controls = actions
        if hasattr(self, "page") and self.page:
            self.page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # TOP APP HEADER
    # ─────────────────────────────────────────────────────────────────────────
    def _build_top_app_header(self) -> ft.Container:
        # Redundant nested header removed; actions moved to subnav tabs bar.
        return ft.Container()


    # ─────────────────────────────────────────────────────────────────────────
    # HERO SPOTLIGHT BANNER (App Green Theme)
    # ─────────────────────────────────────────────────────────────────────────
    def _build_hero_spotlight(self) -> ft.Container:
        # 40 outer padding + 48 hero padding = 88; never wider than the screen
        hero_text_width = min(560, max(200, (self.page.width or 560) - 88))

        return ft.Container(
            padding=ft.Padding.all(24),
            border_radius=ft.BorderRadius.all(20),
            gradient=ft.LinearGradient(
                colors=["#064E3B", "#065F46", "#022C22"],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, "#34D399")),
            shadow=ft.BoxShadow(
                blur_radius=16,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.12, "#064E3B"),
                offset=ft.Offset(0, 4),
            ),
            content=ft.Stack(
                controls=[
                    # Subtle ambient glow wave on the right side
                    ft.Container(
                        alignment=ft.Alignment.TOP_RIGHT,
                        content=ft.Container(
                            width=180,
                            height=120,
                            border_radius=ft.BorderRadius.all(90),
                            gradient=ft.RadialGradient(
                                colors=[ft.Colors.with_opacity(0.35, "#34D399"), ft.Colors.TRANSPARENT],
                                center=ft.Alignment.CENTER,
                                radius=1.0,
                            ),
                        ),
                    ),
                    # Text & Action content
                    ft.Column(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.Row(
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color="#6EE7B7"),
                                    ft.Text("CURATED PEER & OFFICIAL LEARNING", size=10, weight=ft.FontWeight.W_800, color="#6EE7B7"),
                                ],
                            ),
                            ft.Text("The right choice of curated study packs", size=21, weight=ft.FontWeight.W_800, color="#FFFFFF"),
                            ft.Container(
                                width=hero_text_width,
                                content=ft.Text(
                                    "Choose from verified flashcards, quiz question banks, and exam simulators with new peer packs curated and reviewed by platform admins daily.",
                                    size=12.5,
                                    color="#D1FAE5",
                                ),
                            ),
                            ft.Container(height=6),
                            ft.Container(
                                ink=True,
                                on_click=lambda _: self._select_category("Official"),
                                padding=ft.Padding.symmetric(horizontal=18, vertical=9),
                                border_radius=ft.BorderRadius.all(20),
                                gradient=ft.LinearGradient(
                                    colors=["#34D399", "#059669"],
                                    begin=ft.Alignment.TOP_LEFT,
                                    end=ft.Alignment.BOTTOM_RIGHT,
                                ),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.4, "#A7F3D0")),
                                shadow=ft.BoxShadow(
                                    blur_radius=10,
                                    spread_radius=0,
                                    color=ft.Colors.with_opacity(0.3, "#047857"),
                                    offset=ft.Offset(0, 2),
                                ),
                                content=ft.Row(
                                    tight=True,
                                    spacing=6,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Text("Explore Curated Packs", size=11.5, weight=ft.FontWeight.W_800, color="#022C22"),
                                        ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=13, color="#022C22"),
                                    ],
                                ),
                            ),
                        ],
                    ),
                ]
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # SEARCH & CATEGORY CHIPS BAR
    # ─────────────────────────────────────────────────────────────────────────
    def _build_category_chips(self) -> List[ft.Container]:
        """Builds the category pills reflecting the current active_category."""
        chips = []
        for cat_name, cat_icon in CATEGORIES:
            is_active = (self.active_category == cat_name)
            chips.append(
                ft.Container(
                    ink=True,
                    on_click=lambda _, c=cat_name: self._select_category(c),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=7),
                    border_radius=ft.BorderRadius.all(20),
                    bgcolor=ft.Colors.PRIMARY if is_active else ft.Colors.ON_PRIMARY,
                    border=None if is_active else ft.Border.all(1, "#374151"),
                    content=ft.Row(
                        tight=True,
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(cat_icon, size=13, color="#FFFFFF" if is_active else "#9CA3AF"),
                            ft.Text(
                                cat_name,
                                size=11.5,
                                weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500,
                                color="#FFFFFF" if is_active else ft.Colors.with_opacity(0.75, ft.Colors.ON_SURFACE),
                            ),
                        ],
                    ),
                )
            )
        return chips

    def _build_search_and_filters_bar(self) -> ft.Column:
        search_field = ft.TextField(
            hint_text="Search packs by topic, title, subject, or keywords…",
            hint_style=ft.TextStyle(size=12.5, color="#6B7280"),
            text_size=13,
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=ft.BorderRadius.all(12),
            border_color="#374151",
            focused_border_color=ft.Colors.PRIMARY,
            bgcolor=ft.Colors.ON_PRIMARY,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            expand=True,
            on_submit=lambda e: self._on_search_submit(e.control.value),
        )

        # Keep a reference so the chips can be refreshed when selection changes
        self.category_row = ft.Row(
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            controls=self._build_category_chips(),
        )

        return ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    spacing=12,
                    controls=[
                        search_field,
                        ft.PopupMenuButton(
                            tooltip="Sort packs",
                            icon=ft.Icons.SORT_ROUNDED,
                            items=[
                                ft.PopupMenuItem(content=ft.Text("Most Popular"), on_click=lambda _: self._change_sort("popular")),
                                ft.PopupMenuItem(content=ft.Text("Newest Additions"), on_click=lambda _: self._change_sort("newest")),
                                ft.PopupMenuItem(content=ft.Text("Price: Free First"), on_click=lambda _: self._change_sort("price_low")),
                                ft.PopupMenuItem(content=ft.Text("Most Liked"), on_click=lambda _: self._change_sort("likes")),
                            ],
                        ),
                    ],
                ),
                self.category_row,
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # STATE RENDERING
    # ─────────────────────────────────────────────────────────────────────────
    def _build_loading_indicator(self) -> ft.Container:
        return ft.Container(
            padding=ft.Padding.symmetric(vertical=60),
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                tight=True,
                controls=[
                    ft.ProgressRing(color=ft.Colors.PRIMARY, width=36, height=36, stroke_width=3),
                    ft.Text("Discovering Curated Study Packs…", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_400),
                ],
            ),
        )

    def _render_state(self):
        # Update subnav bar tab highlights and badge counts
        if hasattr(self, "subnav_bar_container") and self.subnav_bar_container:
            self.subnav_bar_container.content = self._build_subnav_tabs_content()

        if self.active_tab == "my_submissions":
            if self.is_loading_submissions:
                self.main_body_container.content = self._build_submissions_loading()
            else:
                self.main_body_container.content = self._build_my_submissions_view()
        elif self.active_tab == "bundles":
            if self.is_loading_bundles and not self.bundles:
                self.main_body_container.content = self._build_bundles_loading()
            else:
                self.main_body_container.content = self._build_bundles_view()
        else:
            if self.is_loading:
                self.content_container.content = self._build_loading_indicator()
            elif not self.packs:
                self.content_container.content = self._build_empty_state()
            else:
                self.content_container.content = ft.ResponsiveRow(
                    spacing=16,
                    run_spacing=16,
                    controls=[self._build_pack_card(p) for p in self.packs],
                )
            self.main_body_container.content = ft.Column(
                spacing=18,
                controls=[
                    self._build_hero_spotlight(),
                    self._build_search_and_filters_bar(),
                    self.content_container,
                ],
            )

        self._update_header_actions()
        if hasattr(self, "page") and self.page:
            self.page.update()

    def _build_empty_state(self) -> ft.Container:
        return ft.Container(
            padding=ft.Padding.symmetric(vertical=60, horizontal=20),
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=48, color=ft.Colors.GREY_600),
                    ft.Text("No Study Packs Found", size=16, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                    ft.Text(
                        "Be the first to publish a study pack for this subject and earn 50 Nu-Coins!",
                        size=12.5,
                        color=ft.Colors.GREY_500,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=6),
                    self._build_publish_button("Share My Study Pack"),
                ],
            ),
        )

    def _build_bundles_loading(self) -> ft.Container:
        return ft.Container(
            padding=ft.Padding.symmetric(vertical=60),
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                tight=True,
                controls=[
                    ft.ProgressRing(color="#6366F1", width=36, height=36, stroke_width=3),
                    ft.Text("Loading Multi-Subject Exam Bundles…", size=13, weight=ft.FontWeight.W_600, color="#64748B"),
                ],
            ),
        )

    def _build_bundles_view(self) -> ft.Control:
        # Bundles Hero Banner
        banner = ft.Container(
            padding=ft.Padding.all(24),
            border_radius=ft.BorderRadius.all(20),
            gradient=ft.LinearGradient(
                colors=["#312E81", "#4338CA", "#1E1B4B"],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, "#818CF8")),
            shadow=ft.BoxShadow(
                blur_radius=16,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.18, "#312E81"),
                offset=ft.Offset(0, 4),
            ),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                wrap=True,
                spacing=16,
                controls=[
                    ft.Column(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.AUTO_AWESOME_MOTION_ROUNDED, size=15, color="#A5B4FC"),
                                    ft.Text("MULTI-SUBJECT CBT COMBOS", size=11, weight=ft.FontWeight.W_800, color="#A5B4FC"),
                                ],
                                spacing=6,
                                tight=True,
                            ),
                            ft.Text(
                                "JAMB UTME & WAEC Revision Bundles",
                                size=22,
                                weight=ft.FontWeight.W_800,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Text(
                                "Save coins and get all your required exam subjects in 1-click.\nIncludes complete past questions, CBT timers, step-by-step explanations, and diagrams.",
                                size=13,
                                color=ft.Colors.WHITE70,
                            ),
                        ],
                    ),
                    ft.ElevatedButton(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.REFRESH_ROUNDED, size=14, color="#3730A3"),
                                ft.Text("Refresh Combos", size=12, weight=ft.FontWeight.BOLD, color="#3730A3"),
                            ],
                            spacing=4,
                            tight=True,
                        ),
                        bgcolor=ft.Colors.WHITE,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=ft.BorderRadius.all(10)),
                            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                        ),
                        on_click=lambda _: self.page.run_task(self._load_bundles_data),
                    ),
                ],
            ),
        )

        if not self.bundles:
            empty_box = ft.Container(
                padding=ft.Padding.symmetric(vertical=48, horizontal=24),
                border_radius=ft.BorderRadius.all(16),
                bgcolor="#FFFFFF",
                border=ft.Border.all(1, "#E2E8F0"),
                shadow=ft.BoxShadow(
                    blur_radius=10,
                    spread_radius=0,
                    color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    tight=True,
                    controls=[
                        ft.Container(
                            width=60,
                            height=60,
                            border_radius=ft.BorderRadius.all(30),
                            bgcolor="#EEF2FF",
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.AUTO_AWESOME_MOTION_ROUNDED, size=28, color="#6366F1"),
                        ),
                        ft.Text("No Exam Bundles Available Yet", size=18, weight=ft.FontWeight.W_800, color="#0F172A"),
                        ft.Text(
                            "Curators and platform admins are preparing comprehensive multi-subject exam bundles.\nExplore individual study packs in the store meanwhile!",
                            size=13,
                            color="#64748B",
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=6),
                        ft.FilledButton(
                            content=ft.Text("Browse Single Packs", size=12.5, weight=ft.FontWeight.W_700),
                            style=ft.ButtonStyle(
                                bgcolor="#059669",
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                            ),
                            on_click=lambda _: self._switch_tab("browse"),
                        ),
                    ],
                ),
            )
            return ft.Column(spacing=18, tight=True, controls=[banner, empty_box])

        # Bundles grid
        bundles_row = ft.ResponsiveRow(
            spacing=16,
            run_spacing=16,
            controls=[
                StudyBundleCard(
                    bundle=b,
                    on_click_inspect=self._open_bundle_action,
                    on_click_download=self._open_bundle_action,
                )
                for b in self.bundles
            ],
        )

        return ft.Column(
            spacing=18,
            tight=True,
            controls=[
                banner,
                ft.Row(
                    [
                        ft.Text(
                            f"Available Exam Bundles ({len(self.bundles)})",
                            size=16,
                            weight=ft.FontWeight.W_800,
                            color="#0F172A",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                bundles_row,
            ],
        )

    def _open_bundle_action(self, bundle_input: Any):
        if isinstance(bundle_input, dict):
            bundle = bundle_input
        else:
            bundle = next((b for b in self.bundles if str(b.get("id")) == str(bundle_input)), {"id": bundle_input})

        bundle_id = str(bundle.get("id"))
        title = bundle.get("title", "Exam Combo Bundle")
        category = bundle.get("category", "JAMB UTME")
        price = bundle.get("price_coins", 0)
        orig_price = bundle.get("original_price_coins", price)
        discount = bundle.get("discount_percentage", 0)
        is_owned = bundle.get("is_owned", False)
        packs = bundle.get("packs", [])
        total_q = bundle.get("total_questions", 0)
        total_fc = bundle.get("total_flashcards", 0)

        if is_owned:
            show_page_snackbar(self.page, f"'{title}' is already in your vault!")
            return

        has_enough_coins = (self.user_coins >= price) if price > 0 else True
        dlg_width = min(self.page.width - 32, 520) if self.page.width else 480

        confirm_dialog = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=24),
            bgcolor="#FFFFFF",
            content_padding=ft.Padding.all(0),
        )

        async def _confirm_bundle_download(btn):
            btn.disabled = True
            btn.content = ft.Row(
                tight=True,
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color="#FFFFFF"),
                    ft.Text("Cloning all packs into Vault...", size=12.5, weight=ft.FontWeight.W_800, color="#FFFFFF"),
                ],
            )
            self.page.update()

            res = await download_study_bundle(self.token, bundle_id)

            self._close_dialog(confirm_dialog)

            if "error" in res:
                show_page_snackbar(self.page, res.get("error", "Failed to download study bundle."))
                return

            self.user_coins = res.get("balance_after", self.user_coins)
            if hasattr(self, "coins_badge_text") and self.coins_badge_text:
                self.coins_badge_text.value = f" {self.user_coins} Coins"

            bundle["is_owned"] = True
            for b in self.bundles:
                if str(b.get("id")) == bundle_id:
                    b["is_owned"] = True

            self._render_state()
            imported_count = len(res.get("imported_materials", []))
            show_page_snackbar(self.page, f"✨ {imported_count} study packs from '{title}' added to your Vault!")

            imported = res.get("imported_materials", [])
            target_id = res.get("bundle_material_id") or (imported[0].get("material_id") if imported else None)
            if target_id and self.on_pack_downloaded:
                self.on_pack_downloaded(target_id)

        # Themed dialog Header & Banner
        bundle_banner = bundle.get("banner_url")
        banner_dialog_hero = None
        if bundle_banner and str(bundle_banner).strip():
            banner_dialog_hero = ft.Container(
                height=130,
                border_radius=ft.BorderRadius.only(top_left=24, top_right=24),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=ft.Image(
                    src=str(bundle_banner).strip(),
                    height=130,
                    width=float("inf"),
                    fit=ft.BoxFit.COVER,
                ),
            )

        modal_header = ft.Container(
            padding=ft.Padding.symmetric(horizontal=20, vertical=18),
            border_radius=ft.BorderRadius.only(top_left=24, top_right=24) if not banner_dialog_hero else ft.BorderRadius.all(0),
            gradient=ft.LinearGradient(
                colors=["#312E81", "#4338CA"],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        [
                            ft.Container(
                                width=48,
                                height=48,
                                border_radius=ft.BorderRadius.all(14),
                                bgcolor=ft.Colors.WHITE,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.AUTO_AWESOME_MOTION_ROUNDED, size=24, color="#4338CA"),
                            ),
                            ft.Column(
                                spacing=2,
                                tight=True,
                                controls=[
                                    ft.Row(
                                        [
                                            ft.Text("EXAM COMBO", size=10, weight=ft.FontWeight.BOLD, color="#A5B4FC"),
                                            *(
                                                [
                                                    ft.Container(
                                                        content=ft.Text(f"{discount}% OFF", size=9.5, weight=ft.FontWeight.BOLD, color="#FEF08A"),
                                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                        border_radius=ft.BorderRadius.all(8),
                                                        bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
                                                    )
                                                ] if discount > 0 else []
                                            ),
                                        ],
                                        spacing=6,
                                        tight=True,
                                    ),
                                    ft.Text(
                                        title,
                                        size=17,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE,
                                        max_lines=2,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                            ),
                        ],
                        spacing=12,
                        tight=True,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_color=ft.Colors.WHITE70,
                        icon_size=20,
                        on_click=lambda _: self._close_dialog(confirm_dialog),
                    ),
                ],
            ),
        )

        # Pack item cards
        pack_items_controls = []
        for p in packs:
            p_title = p.get("title", "Study Pack")
            p_cat = p.get("category", "General")
            p_q = p.get("questions_count", 0)
            p_fc = p.get("flashcards_count", 0)
            pack_items_controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border_radius=ft.BorderRadius.all(12),
                    bgcolor="#F8FAFC",
                    border=ft.Border.all(1, "#E2E8F0"),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=16, color="#059669"),
                                    ft.Column(
                                        [
                                            ft.Text(p_title, size=13, weight=ft.FontWeight.BOLD, color="#0F172A"),
                                            ft.Text(f"{p_cat} • {p_q} Questions CBT • {p_fc} Flashcards", size=11, color="#64748B"),
                                        ],
                                        spacing=2,
                                        tight=True,
                                    ),
                                ],
                                spacing=8,
                                tight=True,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Text("INCLUDED", size=9.5, weight=ft.FontWeight.BOLD, color="#059669"),
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=ft.BorderRadius.all(8),
                                bgcolor="#ECFDF5",
                            ),
                        ],
                    ),
                )
            )

        # Aggregates row
        aggregates_row = ft.Container(
            padding=ft.Padding.all(12),
            border_radius=ft.BorderRadius.all(12),
            bgcolor="#EEF2FF",
            border=ft.Border.all(1, "#C7D2FE"),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                controls=[
                    ft.Column(
                        [
                            ft.Text(f"{len(packs)}", size=15, weight=ft.FontWeight.W_800, color="#3730A3"),
                            ft.Text("Packs Included", size=10, weight=ft.FontWeight.W_600, color="#6366F1"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                    ),
                    ft.Column(
                        [
                            ft.Text(f"{total_q}", size=15, weight=ft.FontWeight.W_800, color="#3730A3"),
                            ft.Text("Total CBT Qs", size=10, weight=ft.FontWeight.W_600, color="#6366F1"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                    ),
                    ft.Column(
                        [
                            ft.Text(f"{price} Coins", size=15, weight=ft.FontWeight.W_800, color="#3730A3"),
                            ft.Text(f"Save {discount}%", size=10, weight=ft.FontWeight.W_600, color="#059669"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                    ),
                ],
            ),
        )

        # Actions
        if price == 0:
            btn_label = "Add Entire Bundle to Vault (FREE)"
            btn_color = "#059669"
        elif has_enough_coins:
            btn_label = f"Get All {len(packs)} Packs for {price} Coins"
            btn_color = "#4338CA"
        else:
            btn_label = "Get Coins in Store"
            btn_color = "#D97706"

        def _handle_action_click(e=None):
            if has_enough_coins:
                self.page.run_task(_confirm_bundle_download, action_btn)
            else:
                self._close_dialog(confirm_dialog)
                self.page.go("/store?tab=boosters")

        action_btn = ft.FilledButton(
            content=ft.Row(
                tight=True,
                spacing=6,
                controls=[
                    ft.Icon(ft.Icons.FILE_DOWNLOAD_ROUNDED if has_enough_coins else ft.Icons.STOREFRONT_ROUNDED, size=16, color="#FFFFFF"),
                    ft.Text(btn_label, size=12.5, weight=ft.FontWeight.W_800, color="#FFFFFF"),
                ],
            ),
            style=ft.ButtonStyle(
                bgcolor=btn_color,
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding.symmetric(horizontal=18, vertical=12),
            ),
            on_click=_handle_action_click,
        )

        cancel_btn = ft.OutlinedButton(
            content=ft.Text("Cancel", size=12.5, weight=ft.FontWeight.W_600, color="#475569"),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, "#CBD5E1"),
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            ),
            on_click=lambda _: self._close_dialog(confirm_dialog),
        )

        modal_body = ft.Container(
            padding=ft.Padding.all(20),
            border_radius=ft.BorderRadius.only(bottom_left=24, bottom_right=24),
            bgcolor="#FFFFFF",
            content=ft.Column(
                spacing=14,
                tight=True,
                controls=[
                    aggregates_row,
                    ft.Text("Included Subjects & Past Question Packs:", size=13, weight=ft.FontWeight.BOLD, color="#0F172A"),
                    ft.Container(
                        height=min(220, max(60, len(pack_items_controls) * 55)),
                        content=ft.Column(
                            controls=pack_items_controls,
                            spacing=8,
                            tight=True,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        spacing=8,
                        controls=[cancel_btn, action_btn],
                    ),
                ],
            ),
        )

        confirm_dialog.content = ft.Container(
            width=dlg_width,
            content=ft.Column(
                spacing=0,
                tight=True,
                controls=[
                    *( [banner_dialog_hero] if banner_dialog_hero else [] ),
                    modal_header,
                    modal_body,
                ],
            ),
        )

        confirm_dialog.open = True
        self.page.overlay.append(confirm_dialog)
        self.page.update()

    def _build_submissions_loading(self) -> ft.Container:
        return ft.Container(
            padding=ft.Padding.symmetric(vertical=60),
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                tight=True,
                controls=[
                    ft.ProgressRing(color="#059669", width=36, height=36, stroke_width=3),
                    ft.Text("Retrieving your submissions & moderator review feedback…", size=13, weight=ft.FontWeight.W_600, color="#64748B"),
                ],
            ),
        )

    def _build_my_submissions_view(self) -> ft.Control:
        items = self.my_submissions
        total_count = len(items)
        approved_count = sum(1 for p in items if p.get("status") == "approved")
        pending_count = sum(1 for p in items if p.get("status") == "pending_review")
        rejected_count = sum(1 for p in items if p.get("status") == "rejected")
        total_coins = self.submissions_stats.get("total_coins_earned", 0)

        # 1. Clean, High-Contrast Header Card (No nested green-on-green boxes)
        header_card = ft.Container(
            padding=ft.Padding.symmetric(horizontal=20, vertical=18),
            border_radius=ft.BorderRadius.all(16),
            bgcolor="#FFFFFF",
            border=ft.Border.all(1, "#E2E8F0"),
            shadow=ft.BoxShadow(
                blur_radius=10,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
                spacing=16,
                run_spacing=12,
                controls=[
                    ft.Column(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Row(
                                spacing=6,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color="#059669"),
                                    ft.Text("CREATOR REWARDS & REVIEW HISTORY", size=10.5, weight=ft.FontWeight.W_800, color="#059669"),
                                ],
                            ),
                            ft.Text("My Study Pack Submissions", size=20, weight=ft.FontWeight.W_800, color="#0F172A"),
                            ft.Text(
                                "Track live approval status, view feedback comments on rejections, and see Nu-Coins earned.",
                                size=12.5,
                                color="#64748B",
                            ),
                        ],
                    ),
                    ft.Row(
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.OutlinedButton(
                                content=ft.Row(
                                    tight=True,
                                    spacing=6,
                                    controls=[
                                        ft.Icon(ft.Icons.REFRESH_ROUNDED, size=16, color="#475569"),
                                        ft.Text("Refresh", size=12, weight=ft.FontWeight.W_700, color="#334155"),
                                    ],
                                ),
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    side=ft.BorderSide(1, "#CBD5E1"),
                                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                ),
                                on_click=lambda _: self.page.run_task(self._load_submissions_data),
                            ),
                            ft.FilledButton(
                                content=ft.Row(
                                    tight=True,
                                    spacing=6,
                                    controls=[
                                        ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color="#FFFFFF"),
                                        ft.Text("Submit New Pack", size=12, weight=ft.FontWeight.W_800, color="#FFFFFF"),
                                    ],
                                ),
                                style=ft.ButtonStyle(
                                    bgcolor="#059669",
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                                ),
                                on_click=lambda _: self._open_submission_dialog(),
                            ),
                        ],
                    ),
                ],
            ),
        )

        # 2. Key Stats Summary Row (Using col on Container, NO expand=True)
        def _stat_card(col_span: dict, icon: str, label: str, value: str, icon_color: str, icon_bg: str):
            return ft.Container(
                col=col_span,
                padding=ft.Padding.symmetric(horizontal=16, vertical=16),
                border_radius=ft.BorderRadius.all(14),
                bgcolor="#FFFFFF",
                border=ft.Border.all(1, "#E2E8F0"),
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    spread_radius=0,
                    color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Row(
                    tight=True,
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.all(10),
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=icon_bg,
                            content=ft.Icon(icon, size=20, color=icon_color),
                        ),
                        ft.Column(
                            tight=True,
                            spacing=1,
                            controls=[
                                ft.Text(value, size=20, weight=ft.FontWeight.W_800, color="#0F172A"),
                                ft.Text(label, size=11.5, weight=ft.FontWeight.W_600, color="#64748B"),
                            ],
                        ),
                    ],
                ),
            )

        stats_row = ft.ResponsiveRow(
            spacing=12,
            run_spacing=12,
            controls=[
                _stat_card({"sm": 6, "md": 3}, ft.Icons.INVENTORY_2_ROUNDED, "Total Submitted", str(total_count), "#2563EB", "#EFF6FF"),
                _stat_card({"sm": 6, "md": 3}, ft.Icons.CHECK_CIRCLE_ROUNDED, "Live in Store", str(approved_count), "#059669", "#ECFDF5"),
                _stat_card({"sm": 6, "md": 3}, ft.Icons.HOURGLASS_TOP_ROUNDED, "Under Review", str(pending_count), "#D97706", "#FFFBEB"),
                _stat_card({"sm": 6, "md": 3}, ft.Icons.MONETIZATION_ON_ROUNDED, "Nu-Coins Earned", f"+{total_coins}", "#B45309", "#FEF3C7"),
            ],
        )

        # 3. Empty state if no submissions
        if not items:
            empty_box = ft.Container(
                padding=ft.Padding.symmetric(vertical=48, horizontal=24),
                border_radius=ft.BorderRadius.all(16),
                bgcolor="#FFFFFF",
                border=ft.Border.all(1, "#E2E8F0"),
                shadow=ft.BoxShadow(
                    blur_radius=10,
                    spread_radius=0,
                    color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    tight=True,
                    controls=[
                        ft.Container(
                            width=60,
                            height=60,
                            border_radius=ft.BorderRadius.all(30),
                            bgcolor="#ECFDF5",
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.OUTBOX_ROUNDED, size=28, color="#059669"),
                        ),
                        ft.Text("No Study Pack Submissions Yet", size=18, weight=ft.FontWeight.W_800, color="#0F172A"),
                        ft.Text(
                            "Turn your study vault flashcards and quizzes into community study packs.\nOnce reviewed and approved by moderators, your pack goes live and you earn 50+ Nu-Coins!",
                            size=13,
                            color="#64748B",
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=6),
                        ft.Row(
                            wrap=True,
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=10,
                            run_spacing=8,
                            controls=[
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=12, vertical=7),
                                    border_radius=ft.BorderRadius.all(10),
                                    bgcolor="#F8FAFC",
                                    border=ft.Border.all(1, "#E2E8F0"),
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.FOLDER_ZIP_ROUNDED, size=14, color="#059669"),
                                        ft.Text("1. Pick Vault Material", size=11.5, weight=ft.FontWeight.W_700, color="#334155"),
                                    ], spacing=6, tight=True),
                                ),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=12, vertical=7),
                                    border_radius=ft.BorderRadius.all(10),
                                    bgcolor="#F8FAFC",
                                    border=ft.Border.all(1, "#E2E8F0"),
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.RATE_REVIEW_ROUNDED, size=14, color="#2563EB"),
                                        ft.Text("2. Quick Admin Review", size=11.5, weight=ft.FontWeight.W_700, color="#334155"),
                                    ], spacing=6, tight=True),
                                ),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=12, vertical=7),
                                    border_radius=ft.BorderRadius.all(10),
                                    bgcolor="#FEF3C7",
                                    border=ft.Border.all(1, "#FDE68A"),
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=14, color="#B45309"),
                                        ft.Text("3. Earn 50 Nu-Coins", size=11.5, weight=ft.FontWeight.W_800, color="#92400E"),
                                    ], spacing=6, tight=True),
                                ),
                            ],
                        ),
                        ft.Container(height=8),
                        ft.FilledButton(
                            content=ft.Row(
                                tight=True,
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color="#FFFFFF"),
                                    ft.Text("Publish Your First Study Pack", size=12.5, weight=ft.FontWeight.W_800, color="#FFFFFF"),
                                ],
                            ),
                            style=ft.ButtonStyle(
                                bgcolor="#059669",
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                            ),
                            on_click=lambda _: self._open_submission_dialog(),
                        ),
                    ],
                ),
            )
            return ft.Column(spacing=18, tight=True, controls=[header_card, stats_row, empty_box])

        # 4. Submissions Cards List
        card_controls = []
        for pack in items:
            card_controls.append(self._build_submission_card(pack))

        return ft.Column(
            spacing=18,
            tight=True,
            controls=[
                header_card,
                stats_row,
                ft.Row([
                    ft.Text(f"Submissions & Moderation History ({total_count})", size=15, weight=ft.FontWeight.W_800, color="#0F172A"),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Column(spacing=14, tight=True, controls=card_controls),
            ],
        )

    def _build_submission_card(self, pack: Dict[str, Any]) -> ft.Container:
        pack_id = str(pack.get("id"))
        raw_title = pack.get("title", "Untitled Study Pack")
        title = re.sub(r"(?i)\s*[\[\(]\s*pack\s*import\s*[\]\)]\s*[:\-–—]?\s*", " ", raw_title)
        title = re.sub(r"(?i)^pack\s*import\s*[:\-–—]?\s*", "", title).strip() or "Study Pack"
        desc = pack.get("description", "No description provided.")
        category = pack.get("category", "General")
        status = pack.get("status", "pending_review")
        notes = (pack.get("admin_review_notes") or "").strip()
        reward_coins = pack.get("reward_coins_granted") or 0
        fc_count = pack.get("flashcards_count", 0)
        q_count = pack.get("questions_count", 0)
        downloads = pack.get("downloads_count", 0)
        likes = pack.get("likes_count", 0)
        created_at_raw = pack.get("created_at") or ""
        created_at_fmt = created_at_raw[:10] if len(created_at_raw) >= 10 else "Recently"

        # Status badge & style
        if status == "approved":
            status_color = "#065F46"
            status_bg = "#ECFDF5"
            status_border = "#10B981"
            status_icon = ft.Icons.CHECK_CIRCLE_ROUNDED
            status_text = "ACCEPTED & LIVE IN STORE"
        elif status == "rejected":
            status_color = "#991B1B"
            status_bg = "#FEF2F2"
            status_border = "#EF4444"
            status_icon = ft.Icons.ERROR_OUTLINE_ROUNDED
            status_text = "NEEDS REVISION / REJECTED"
        elif status == "hidden":
            status_color = "#92400E"
            status_bg = "#FFFBEB"
            status_border = "#F59E0B"
            status_icon = ft.Icons.VISIBILITY_OFF_ROUNDED
            status_text = "UNLISTED FROM STORE"
        else:
            status_color = "#1E40AF"
            status_bg = "#EFF6FF"
            status_border = "#3B82F6"
            status_icon = ft.Icons.HOURGLASS_TOP_ROUNDED
            status_text = "UNDER ADMIN REVIEW"

        status_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            border_radius=ft.BorderRadius.all(10),
            bgcolor=status_bg,
            border=ft.Border.all(1, status_border),
            content=ft.Row([
                ft.Icon(status_icon, size=14, color=status_color),
                ft.Text(status_text, size=11, weight=ft.FontWeight.W_800, color=status_color),
            ], spacing=6, tight=True),
        )

        reward_pill = None
        if reward_coins > 0:
            reward_pill = ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=ft.BorderRadius.all(10),
                bgcolor="#FEF3C7",
                border=ft.Border.all(1, "#F59E0B"),
                content=ft.Row([
                    ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=14, color="#B45309"),
                    ft.Text(f"+{reward_coins} Nu-Coins Earned 🎉", size=11, weight=ft.FontWeight.W_800, color="#92400E"),
                ], spacing=6, tight=True),
            )

        # Moderator feedback callout without expand=True
        feedback_callout = None
        if status == "rejected":
            feedback_callout = ft.Container(
                padding=ft.Padding.all(14),
                border_radius=ft.BorderRadius.all(12),
                bgcolor="#FEF2F2",
                border=ft.Border.all(1.2, "#FCA5A5"),
                content=ft.Column(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Row(
                            tight=True,
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.REPORT_PROBLEM_ROUNDED, size=16, color="#DC2626"),
                                ft.Text("Moderator Rejection Feedback & Notes", size=12, weight=ft.FontWeight.W_800, color="#991B1B"),
                            ],
                        ),
                        ft.Text(
                            f'"{notes}"' if notes else "Did not meet marketplace quality guidelines. Please ensure flashcard answers are comprehensive and questions are accurate before resubmitting.",
                            size=12.5,
                            color="#7F1D1D",
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.Text(
                            "Tip: You can refine your material in Study Hub and publish an updated revision for approval.",
                            size=11,
                            color="#991B1B",
                        ),
                    ],
                ),
            )
        elif status == "approved":
            feedback_callout = ft.Container(
                padding=ft.Padding.all(12),
                border_radius=ft.BorderRadius.all(12),
                bgcolor="#ECFDF5",
                border=ft.Border.all(1, "#A7F3D0"),
                content=ft.Column(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Row(
                            tight=True,
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=16, color="#059669"),
                                ft.Text("Moderator Review Feedback", size=12, weight=ft.FontWeight.W_800, color="#065F46"),
                            ],
                        ),
                        ft.Text(
                            f'"{notes}"' if notes else "Pack verified and approved for the public marketplace catalog.",
                            size=12.5,
                            color="#047857",
                        ),
                    ],
                ),
            )
        elif status == "hidden":
            feedback_callout = ft.Container(
                padding=ft.Padding.all(12),
                border_radius=ft.BorderRadius.all(12),
                bgcolor="#FFFBEB",
                border=ft.Border.all(1, "#FDE68A"),
                content=ft.Column(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Row(
                            tight=True,
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.VISIBILITY_OFF_ROUNDED, size=16, color="#D97706"),
                                ft.Text("Store Visibility Notice", size=12, weight=ft.FontWeight.W_800, color="#92400E"),
                            ],
                        ),
                        ft.Text(
                            notes or "This pack is currently unlisted from the public store catalog by administrators.",
                            size=12,
                            color="#78350F",
                        ),
                    ],
                ),
            )
        else:  # pending_review
            feedback_callout = ft.Container(
                padding=ft.Padding.all(12),
                border_radius=ft.BorderRadius.all(12),
                bgcolor="#EFF6FF",
                border=ft.Border.all(1, "#BFDBFE"),
                content=ft.Column(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Row(
                            tight=True,
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.SCHEDULE_ROUNDED, size=16, color="#2563EB"),
                                ft.Text("Moderation in Progress", size=12, weight=ft.FontWeight.W_800, color="#1E40AF"),
                            ],
                        ),
                        ft.Text(
                            "Platform admins review submissions daily for quality and clarity. Once approved, Nu-Coins will be awarded automatically.",
                            size=12,
                            color="#1E3A8A",
                        ),
                    ],
                ),
            )

        # Content metrics
        def _metric_chip(icon_str: str, text_str: str):
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=9, vertical=4),
                border_radius=ft.BorderRadius.all(8),
                bgcolor="#F8FAFC",
                border=ft.Border.all(1, "#E2E8F0"),
                content=ft.Row([
                    ft.Text(icon_str, size=12),
                    ft.Text(text_str, size=11.5, weight=ft.FontWeight.W_600, color="#334155"),
                ], spacing=4, tight=True),
            )

        metrics_controls = [
            _metric_chip("🎴", f"{fc_count} Flashcards"),
            _metric_chip("📝", f"{q_count} Quiz MCQs"),
        ]
        if status == "approved":
            metrics_controls.extend([
                _metric_chip("📥", f"{downloads} Downloads"),
                _metric_chip("❤️", f"{likes} Likes"),
            ])

        return ft.Container(
            padding=ft.Padding.all(20),
            border_radius=ft.BorderRadius.all(16),
            bgcolor="#FFFFFF",
            border=ft.Border.all(1, "#E2E8F0"),
            shadow=ft.BoxShadow(
                blur_radius=10,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            content=ft.Column(
                spacing=12,
                tight=True,
                controls=[
                    # Top Row: Category + Date + Badges
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                        spacing=8,
                        run_spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row([
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                    border_radius=ft.BorderRadius.all(6),
                                    bgcolor="#ECFDF5",
                                    border=ft.Border.all(1, "#A7F3D0"),
                                    content=ft.Text(category.upper(), size=9.5, weight=ft.FontWeight.W_800, color="#059669"),
                                ),
                                ft.Text(f"Submitted on {created_at_fmt}", size=11.5, color="#64748B"),
                            ], spacing=8, tight=True),
                            ft.Row([
                                *( [reward_pill] if reward_pill else [] ),
                                status_pill,
                            ], spacing=8, tight=True),
                        ],
                    ),
                    # Title & Description
                    ft.Column([
                        ft.Text(title, size=16.5, weight=ft.FontWeight.W_800, color="#0F172A"),
                        ft.Text(desc, size=13, color="#475569", max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=4, tight=True),
                    # Metrics row
                    ft.Row(controls=metrics_controls, spacing=8, wrap=True),
                    # Moderator Feedback Callout
                    *( [feedback_callout] if feedback_callout else [] ),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # PACK CARD COMPONENT (Dedicated StudyPackCard Component)
    # ─────────────────────────────────────────────────────────────────────────
    def _build_pack_card(self, pack: Dict[str, Any]) -> ft.Container:
        return StudyPackCard(
            pack=pack,
            on_click_preview=self._open_pack_action,
            on_toggle_like=lambda pid: self.page.run_task(self._toggle_like, pid),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # SLEEK & MODERN DOWNLOAD CONFIRMATION DIALOG
    # ─────────────────────────────────────────────────────────────────────────
    def _open_pack_action(self, pack_input: Any):
        if isinstance(pack_input, dict):
            pack = pack_input
        else:
            pack = next((p for p in self.packs if str(p.get("id")) == str(pack_input)), {"id": pack_input})

        pack_id = str(pack.get("id"))
        is_owned = pack.get("is_owned", False)
        raw_title = pack.get("title", "Untitled Study Pack")
        title = re.sub(r"(?i)\s*[\[\(]\s*pack\s*import\s*[\]\)]\s*[:\-–—]?\s*", " ", raw_title)
        title = re.sub(r"(?i)^pack\s*import\s*[:\-–—]?\s*", "", title).strip() or "Study Pack"
        category = pack.get("category", "General")
        is_official = pack.get("is_official", False)
        price_coins = pack.get("price_coins", 0)
        desc = pack.get("description", "")
        fc_count = pack.get("flashcards_count", 0)
        q_count = pack.get("questions_count", 0)
        creator = pack.get("creator", {})
        creator_name = creator.get("name", "Nu-Age Official" if is_official else "Peer Creator")

        # If already owned, navigate or notify user directly
        if is_owned:
            show_page_snackbar(self.page, f"'{title}' is already in your vault!")
            if self.on_pack_downloaded:
                self.on_pack_downloaded(pack.get("imported_material_id") or pack_id)
            return

        has_enough_coins = (self.user_coins >= price_coins) if price_coins > 0 else True
        is_free = price_coins == 0
        dlg_width = min(self.page.width - 32, 460) if self.page.width else 440

        # Theme matching category preset
        preset = CATEGORY_PRESETS.get(category)
        if not preset:
            cat_lower = str(category).lower()
            for k, v in CATEGORY_PRESETS.items():
                if k.lower() in cat_lower or cat_lower in k.lower():
                    preset = v
                    break
        if not preset:
            preset = CATEGORY_PRESETS["General"]
        c1, c2 = preset["gradient"]
        primary_color = preset["primary_color"]
        icon = preset["icon"]
        category_tag = preset.get("tag", category.upper())

        confirm_dialog = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=24),
            bgcolor="#FFFFFF",
            content_padding=ft.Padding.all(0),
        )

        async def _confirm_download(btn):
            btn.disabled = True
            btn.content = ft.Row(
                tight=True,
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color="#FFFFFF"),
                    ft.Text("Adding to Vault...", size=12.5, weight=ft.FontWeight.W_800, color="#FFFFFF"),
                ],
            )
            self.page.update()

            res = await download_study_pack(self.token, pack_id)

            # Close dialog cleanly
            self._close_dialog(confirm_dialog)

            if "error" in res:
                show_page_snackbar(self.page, res.get("error", "Failed to download pack."))
                return

            # Update coin balance
            self.user_coins = res.get("balance_after", self.user_coins)
            if hasattr(self, "coins_badge_text") and self.coins_badge_text:
                self.coins_badge_text.value = f" {self.user_coins} Coins"

            # Update owned state across marketplace packs
            pack["is_owned"] = True
            for p in self.packs:
                if str(p.get("id")) == pack_id:
                    p["is_owned"] = True

            self._render_state()
            show_page_snackbar(self.page, f"✨ '{title}' added to your Study Hub vault!")

            # Trigger hub refresh & open imported pack
            new_mat_id = res.get("imported_material_id")
            if new_mat_id and self.on_pack_downloaded:
                self.on_pack_downloaded(new_mat_id)

        # ── 1. Themed Hero Header Block ──
        squircle_icon = ft.Container(
            width=54,
            height=54,
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.WHITE,
            shadow=ft.BoxShadow(
                blur_radius=8,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(icon, size=28, color=primary_color),
        )

        # ── CBT PAST QUESTIONS DETECTION ──
        pack_data = pack.get("pack_data") or {}
        questions_list = pack_data.get("questions") or []
        exam_type = pack.get("exam_type")
        exam_year = pack.get("exam_year")

        if not exam_type:
            for q in questions_list:
                if q.get("exam_type"):
                    exam_type = q["exam_type"]
                    break
        if not exam_type:
            m = re.search(r"(?i)\b(JAMB(?:\s+UTME)?|WAEC(?:\s+WASSCE)?|NECO|POST-UTME|GCE)\b", title)
            if m:
                exam_type = m.group(1).upper()
        if not exam_year:
            m = re.search(r"\b(201\d|202\d)\b", title)
            if m:
                exam_year = int(m.group(1))

        diagrams_count = pack.get("diagrams_count")
        if diagrams_count is None:
            diagrams_count = sum(1 for q in questions_list if q.get("image_url") or q.get("has_diagram"))
        duration_minutes = pack.get("duration_minutes")

        header_tags = [
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.WHITE),
                content=ft.Text(category_tag, size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
            )
        ]

        if exam_type:
            header_tags.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.with_opacity(0.32, ft.Colors.BLACK),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.40, ft.Colors.WHITE)),
                    content=ft.Row([
                        ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=11, color="#FDE68A"),
                        ft.Text(f"{exam_type} {exam_year or ''}".strip(), size=9.5, weight=ft.FontWeight.W_800, color="#FEF3C7"),
                    ], spacing=3, tight=True),
                )
            )

        if diagrams_count > 0:
            header_tags.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                    content=ft.Row([
                        ft.Icon(ft.Icons.IMAGE_ROUNDED, size=11, color=ft.Colors.WHITE),
                        ft.Text(f"{diagrams_count} Diagrams", size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                    ], spacing=3, tight=True),
                )
            )

        if is_official:
            header_tags.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.4, ft.Colors.WHITE)),
                    content=ft.Row([
                        ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=11, color="#FDE68A"),
                        ft.Text("OFFICIAL", size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                    ], spacing=3, tight=True),
                )
            )

        modal_header = ft.Container(
            padding=ft.Padding.all(20),
            border_radius=ft.BorderRadius.only(top_left=24, top_right=24),
            gradient=ft.LinearGradient(
                colors=[c1, c2],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            content=ft.Column(
                spacing=12,
                tight=True,
                controls=[
                    # Top Row: Tags + Close button
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                expand=True,
                                content=ft.Row(spacing=6, tight=True, wrap=True, controls=header_tags),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE_ROUNDED,
                                icon_size=18,
                                icon_color=ft.Colors.WHITE,
                                tooltip="Close preview",
                                on_click=lambda _: self._close_dialog(confirm_dialog),
                            ),
                        ],
                    ),
                    # Center Row: Squircle + Title
                    ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            squircle_icon,
                            ft.Column(
                                spacing=2,
                                tight=True,
                                expand=True,
                                controls=[
                                    ft.Text(title, size=16, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text(f"Curated by {creator_name} • CBT Ready", size=11.5, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE), max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        )

        # ── 2. Content Breakdown 3-Tile Row ──
        def _content_tile(tile_icon: str, tile_color: str, value: str, label: str):
            return ft.Container(
                col={"xs": 4, "sm": 4},
                padding=ft.Padding.symmetric(horizontal=8, vertical=12),
                border_radius=ft.BorderRadius.all(12),
                bgcolor="#F8FAFC",
                border=ft.Border.all(1, "#E2E8F0"),
                content=ft.Column(
                    spacing=2,
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(tile_icon, size=20, color=tile_color),
                        ft.Text(value, size=13, weight=ft.FontWeight.W_800, color="#0F172A"),
                        ft.Text(label, size=10, weight=ft.FontWeight.W_600, color="#64748B"),
                    ],
                ),
            )

        cbt_dur = duration_minutes if duration_minutes else q_count
        if q_count > 0 and fc_count == 0:
            breakdown_row = ft.ResponsiveRow(
                spacing=8,
                run_spacing=8,
                controls=[
                    _content_tile(ft.Icons.TIMER_ROUNDED, "#D97706", f"{cbt_dur}m", "CBT Time"),
                    _content_tile(ft.Icons.IMAGE_ROUNDED, primary_color, str(diagrams_count), "Diagrams"),
                    _content_tile(ft.Icons.QUIZ_ROUNDED, "#0284C7", str(q_count), "CBT Questions"),
                ],
            )
        else:
            breakdown_row = ft.ResponsiveRow(
                spacing=8,
                run_spacing=8,
                controls=[
                    _content_tile(ft.Icons.STYLE_ROUNDED, primary_color, str(fc_count), "Flashcards"),
                    _content_tile(ft.Icons.QUIZ_ROUNDED, "#0284C7", str(q_count), "MCQ Quiz"),
                    _content_tile(ft.Icons.TIMER_ROUNDED, "#D97706", "Enabled", "Exam Sim"),
                ],
            )

        # ── 3. Description & Syllabus Overview Box ──
        desc_box = ft.Container(
            padding=ft.Padding.all(12),
            border_radius=ft.BorderRadius.all(12),
            bgcolor="#F8FAFC",
            border=ft.Border.all(1, "#E2E8F0"),
            content=ft.Column(
                spacing=6,
                tight=True,
                controls=[
                    ft.Text(
                        desc or "Complete CBT exam preparation pack with step-by-step solutions, timer benchmarks, and syllabus questions.",
                        size=12,
                        color="#475569",
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
            ),
        )

        # Sample question preview if available
        sample_q = questions_list[0] if questions_list else None
        sample_q_box = ft.Container()
        if sample_q:
            sq_text = sample_q.get("question_text") or sample_q.get("question") or ""
            sq_img = sample_q.get("image_url")
            sample_q_box = ft.Container(
                padding=ft.Padding.all(10),
                border_radius=ft.BorderRadius.all(10),
                bgcolor="#F1F5F9",
                border=ft.Border.all(1, "#E2E8F0"),
                content=ft.Column(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Row([
                            ft.Icon(ft.Icons.PREVIEW_ROUNDED, size=14, color=primary_color),
                            ft.Text("Sample CBT Question Preview:", size=11, weight=ft.FontWeight.BOLD, color="#1E293B"),
                        ], spacing=4, tight=True),
                        ft.Text(sq_text, size=11.5, color="#334155", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        *(
                            [ft.Image(src=sq_img, height=70, fit=ft.BoxFit.CONTAIN, border_radius=ft.BorderRadius.all(6))]
                            if sq_img else []
                        ),
                    ],
                ),
            )

        # ── 4. Price & Wallet Status ──
        if is_free:
            price_status_box = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border_radius=ft.BorderRadius.all(12),
                bgcolor="#ECFDF5",
                border=ft.Border.all(1, "#A7F3D0"),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18, color="#059669"),
                        ft.Column(
                            spacing=1,
                            tight=True,
                            controls=[
                                ft.Text("100% Free Peer Material", size=12, weight=ft.FontWeight.W_800, color="#065F46"),
                                ft.Text("A personal copy will be added directly to your vault.", size=11, color="#047857"),
                            ],
                        ),
                    ],
                ),
            )
        else:
            price_status_box = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                border_radius=ft.BorderRadius.all(12),
                bgcolor="#FFFBEB",
                border=ft.Border.all(1, "#FDE68A"),
                content=ft.Column(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Column([
                                    ft.Text("Unlock Cost", size=10.5, color="#78350F"),
                                    ft.Text(f"{price_coins} Nu-Coins", size=15, weight=ft.FontWeight.W_800, color="#B45309"),
                                ], spacing=1, tight=True),
                                ft.Column([
                                    ft.Text("Your Balance", size=10.5, color="#78350F"),
                                    ft.Text(
                                        f"{self.user_coins} Coins",
                                        size=15,
                                        weight=ft.FontWeight.W_800,
                                        color="#059669" if has_enough_coins else "#DC2626",
                                    ),
                                ], spacing=1, tight=True, horizontal_alignment=ft.CrossAxisAlignment.END),
                            ],
                        ),
                        *(
                            [
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                    border_radius=ft.BorderRadius.all(8),
                                    bgcolor="#FEF2F2",
                                    border=ft.Border.all(1, "#FCA5A5"),
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=13, color="#DC2626"),
                                        ft.Text(f"You need {price_coins - self.user_coins} more Nu-Coins to unlock.", size=11, color="#991B1B"),
                                    ], spacing=6, tight=True),
                                )
                            ] if not has_enough_coins else []
                        ),
                    ],
                ),
            )

        # ── 5. Action Buttons ──
        if is_free:
            action_label = "Add to My Vault"
            action_icon = ft.Icons.FILE_DOWNLOAD_ROUNDED
            action_bg = "#059669"
        elif has_enough_coins:
            action_label = f"Unlock for {price_coins} Coins"
            action_icon = ft.Icons.LOCK_OPEN_ROUNDED
            action_bg = primary_color
        else:
            action_label = "Get Coins in Store"
            action_icon = ft.Icons.STOREFRONT_ROUNDED
            action_bg = "#D97706"

        if has_enough_coins:
            action_click = lambda e: self.page.run_task(_confirm_download, e.control)
        else:
            action_click = lambda _: (self._close_dialog(confirm_dialog), self.page.go("/store?tab=boosters"))

        action_btn = ft.FilledButton(
            content=ft.Row(
                tight=True,
                spacing=6,
                controls=[
                    ft.Icon(action_icon, size=16, color="#FFFFFF"),
                    ft.Text(action_label, size=12.5, weight=ft.FontWeight.W_800, color="#FFFFFF"),
                ],
            ),
            style=ft.ButtonStyle(
                bgcolor=action_bg,
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
            ),
            on_click=action_click,
        )

        cancel_btn = ft.OutlinedButton(
            content=ft.Text("Cancel", size=12.5, weight=ft.FontWeight.W_600, color="#475569"),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, "#CBD5E1"),
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            ),
            on_click=lambda _: self._close_dialog(confirm_dialog),
        )

        modal_body = ft.Container(
            padding=ft.Padding.all(20),
            border_radius=ft.BorderRadius.only(bottom_left=24, bottom_right=24),
            bgcolor="#FFFFFF",
            content=ft.Column(
                spacing=14,
                tight=True,
                controls=[
                    breakdown_row,
                    desc_box,
                    sample_q_box,
                    price_status_box,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        spacing=10,
                        controls=[cancel_btn, action_btn],
                    ),
                ],
            ),
        )

        confirm_dialog.content = ft.Container(
            width=dlg_width,
            border_radius=ft.BorderRadius.all(24),
            bgcolor="#FFFFFF",
            content=ft.Column(
                tight=True,
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    modal_header,
                    modal_body,
                ],
            ),
        )

        confirm_dialog.open = True
        if confirm_dialog not in self.page.overlay:
            self.page.overlay.append(confirm_dialog)
        self.page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # PACK SUBMISSION MODAL (Creator Workflow - Modern Minimalist)
    # ─────────────────────────────────────────────────────────────────────────
    def _open_submission_dialog(self):
        if not self.user_vault_materials:
            show_page_snackbar(self.page, "You need at least one material in your vault to create a study pack.")
            return

        # ── Palette: deep emerald-tinted surfaces so the modal matches the app ──
        BG = "#0B1A16"
        FIELD_BG = "#102620"
        FIELD_BORDER = "#1F4037"
        ACCENT = "#34D399"
        TEXT_MAIN = "#ECFDF5"
        TEXT_MUTED = "#8FB5A8"
        DARK_ON_ACCENT = "#022C22"

        def _short(text: str, limit: int = 34) -> str:
            text = (text or "Untitled").strip()
            return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

        mat_options = [
            ft.dropdown.Option(
                key=str(m["id"]),
                text=_short(m.get("title", "Untitled")),
                content=ft.Text(
                    _short(m.get("title", "Untitled")),
                    size=12.5,
                    color=TEXT_MAIN,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            )
            for m in self.user_vault_materials
        ]
        first_title = self.user_vault_materials[0].get("title", "") if self.user_vault_materials else ""
        first_title = re.sub(r"(?i)\s*[\[\(]\s*pack\s*import\s*[\]\)]\s*[:\-–—]?\s*", " ", first_title)
        first_title = re.sub(r"(?i)^pack\s*import\s*[:\-–—]?\s*", "", first_title).strip()

        def _field_style() -> dict:
            return dict(
                bgcolor=FIELD_BG,
                border_color=FIELD_BORDER,
                focused_border_color=ACCENT,
                border_radius=12,
                text_size=13,
                dense=True,
                expand=True,
                color=TEXT_MAIN,
                label_style=ft.TextStyle(size=12, color=TEXT_MUTED),
                hint_style=ft.TextStyle(size=12, color="#4F7468"),
            )

        def _section_label(text: str) -> ft.Text:
            return ft.Text(text, size=10, weight=ft.FontWeight.W_800, color=ACCENT)

        title_input = ft.TextField(
            label="Pack title",
            value=first_title,
            hint_text="e.g., Cellular Respiration & ATP Synthesis",
            **_field_style(),
        )

        def _on_mat_change(e):
            chosen_id = selected_mat_dropdown.value
            for m in self.user_vault_materials:
                if str(m.get("id")) == chosen_id:
                    title_input.value = m.get("title", "")
                    self.page.update()
                    break

        selected_mat_dropdown = ft.Dropdown(
            label="Material from your vault",
            options=mat_options,
            value=mat_options[0].key if mat_options else None,
            on_select=_on_mat_change,
            menu_height=220,  # caps the popup height; list scrolls beyond ~5 items
            **_field_style(),
        )

        desc_input = ft.TextField(
            label="Description (optional)",
            hint_text="Briefly summarize what this pack covers for peers…",
            multiline=True,
            min_lines=3,
            max_lines=4,
            **_field_style(),
        )

        submit_dialog = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=22),
            bgcolor=BG,
            content_padding=ft.Padding.all(22),
        )

        async def _do_submit(btn):
            if not title_input.value or len(title_input.value.strip()) < 3:
                show_page_snackbar(self.page, "Please enter a valid pack title (at least 3 characters).")
                return

            btn.disabled = True
            btn.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=DARK_ON_ACCENT)
            self.page.update()

            res = await submit_study_pack(
                token=self.token,
                material_id=selected_mat_dropdown.value,
                title=title_input.value.strip(),
                description=desc_input.value.strip() if desc_input.value else "",
                category="General",
                price_coins=0,
            )

            if "error" in res:
                btn.disabled = False
                btn.content = ft.Text("Submit for Review", size=12.5, weight=ft.FontWeight.W_800, color=DARK_ON_ACCENT)
                show_page_snackbar(self.page, res["error"])
                self.page.update()
                return

            self._close_dialog(submit_dialog)
            show_page_snackbar(self.page, res.get("message", "Pack submitted for review!"))
            self._switch_tab("my_submissions")

        submit_btn = ft.FilledButton(
            content=ft.Text("Submit for Review", size=12.5, weight=ft.FontWeight.W_800, color=DARK_ON_ACCENT),
            height=42,
            style=ft.ButtonStyle(
                bgcolor=ACCENT,
                shape=ft.RoundedRectangleBorder(radius=21),
                padding=ft.Padding.symmetric(horizontal=22, vertical=0),
                elevation=0,
            ),
            on_click=lambda e: self.page.run_task(_do_submit, e.control),
        )

        cancel_btn = ft.TextButton(
            content=ft.Text("Cancel", size=12.5, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
            height=42,
            on_click=lambda _: self._close_dialog(submit_dialog),
        )

        def _info_tile(icon: str, heading: str, body: str) -> ft.Container:
            return ft.Container(
                expand=True,
                padding=ft.Padding.all(12),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.08, ACCENT),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ACCENT)),
                content=ft.Column(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(icon, size=18, color=ACCENT),
                        ft.Text(heading, size=11.5, weight=ft.FontWeight.W_700, color=TEXT_MAIN),
                        ft.Text(body, size=10.5, color=TEXT_MUTED),
                    ],
                ),
            )

        dlg_width = min(self.page.width - 32, 500) if self.page.width else 480
        submit_dialog.content = ft.Container(
            width=dlg_width,
            content=ft.Column(
                tight=True,
                spacing=16,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    # Header
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Row(
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        width=44,
                                        height=44,
                                        border_radius=ft.BorderRadius.all(14),
                                        alignment=ft.Alignment.CENTER,
                                        gradient=ft.LinearGradient(
                                            colors=["#34D399", "#059669"],
                                            begin=ft.Alignment.TOP_LEFT,
                                            end=ft.Alignment.BOTTOM_RIGHT,
                                        ),
                                        content=ft.Icon(ft.Icons.CLOUD_UPLOAD_ROUNDED, size=22, color=DARK_ON_ACCENT),
                                    ),
                                    ft.Column(
                                        spacing=1,
                                        tight=True,
                                        controls=[
                                            ft.Text("Publish a Study Pack", size=16, weight=ft.FontWeight.W_800, color=TEXT_MAIN),
                                            ft.Text("Share your material", size=10.5, color=TEXT_MUTED),
                                        ],
                                    ),
                                ],
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE_ROUNDED,
                                icon_size=18,
                                icon_color=TEXT_MUTED,
                                on_click=lambda _: self._close_dialog(submit_dialog),
                            ),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.10, ACCENT)),
                    # Form
                    ft.Column(
                        spacing=8,
                        tight=True,
                        controls=[_section_label("SOURCE MATERIAL"), selected_mat_dropdown],
                    ),
                    ft.Column(
                        spacing=8,
                        tight=True,
                        controls=[_section_label("PACK DETAILS"), title_input, desc_input],
                    ),
                    # What happens next
                    ft.Row(
                        spacing=10,
                        controls=[
                            _info_tile(
                                ft.Icons.VERIFIED_USER_ROUNDED,
                                "Admin review",
                                "We check quality and add subject tags & descriptive information",
                            ),
                            _info_tile(
                                ft.Icons.MONETIZATION_ON_ROUNDED,
                                "Earn Nu-Coins",
                                "Awarded to you once your pack is approved.",
                            ),
                        ],
                    ),
                    # Footer
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        spacing=8,
                        controls=[cancel_btn, submit_btn],
                    ),
                ],
            ),
        )

        submit_dialog.open = True
        self.page.overlay.append(submit_dialog)
        self.page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # ADMIN REVIEW QUEUE MODAL (Redirects to Unified Super Admin Console)
    # ─────────────────────────────────────────────────────────────────────────
    def _open_admin_queue_modal(self):
        self.page.go("/platform-admin")

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS & EVENT HANDLERS
    # ─────────────────────────────────────────────────────────────────────────
    def _select_category(self, cat: str):
        self.active_category = cat
        # Rebuild the pills right away so the highlight moves before data loads
        if self.category_row is not None:
            self.category_row.controls = self._build_category_chips()
            self.page.update()
        self.page.run_task(self._load_data)

    def _on_search_submit(self, query: str):
        self.search_query = query
        self.page.run_task(self._load_data)

    def _change_sort(self, sort_type: str):
        self.sort_by = sort_type
        self.page.run_task(self._load_data)

    async def _toggle_like(self, pack_id: str):
        res = await toggle_like_pack(self.token, pack_id)
        if "liked" in res:
            for p in self.packs:
                if p["id"] == pack_id:
                    p["is_liked"] = res["liked"]
                    p["likes_count"] = res["likes_count"]
            self._render_state()

    def _close_dialog(self, dlg: ft.AlertDialog):
        dlg.open = False
        self.page.update()