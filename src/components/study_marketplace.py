import asyncio
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
)
from src.components.study_pack_card import StudyPackCard
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
        self.active_tab = "browse"  # "browse", "my_submissions", "admin_queue"
        self.admin_pending_count = 0
        self._load_seq = 0  # guards against stale/out-of-order responses

        # UI Slots
        self.category_row: Optional[ft.Row] = None
        # No expand=True here: it sits inside a ListView (unbounded height)
        self.content_container = ft.Container()
        self.coins_badge_text = ft.Text(" Loading", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_400)

        # Build Main View Container
        self.view_root = self._build_layout()

        # Trigger Initial Fetch
        self.page.run_task(self._load_data)

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

    # ─────────────────────────────────────────────────────────────────────────
    # LAYOUT ASSEMBLY
    # ─────────────────────────────────────────────────────────────────────────
    def _build_layout(self) -> ft.Container:
        return ft.Container(
            expand=True,
            bgcolor=ft.Colors.SURFACE,
            # One ListView for everything, so the header scrolls away with the page
            content=ft.ListView(
                expand=True,
                spacing=0,
                controls=[
                    self._build_top_app_header(),
                    ft.Container(
                        padding=ft.Padding.only(left=20, right=20, top=16, bottom=24),
                        content=ft.Column(
                            spacing=18,
                            controls=[
                                self._build_hero_spotlight(),
                                self._build_search_and_filters_bar(),
                                self.content_container,
                            ],
                        ),
                    ),
                ],
            ),
        )

    def _build_publish_button(self, label: str = "Publish Pack") -> ft.Container:
        """Sleek pill-shaped emerald gradient button with a soft glow."""
        return ft.Container(
            ink=True,
            on_click=lambda _: self._open_submission_dialog(),
            tooltip="Share your own study pack with the community",
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            border_radius=ft.BorderRadius.all(20),
            gradient=ft.LinearGradient(
                colors=["#34D399", "#059669"],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.45, "#A7F3D0")),
            shadow=ft.BoxShadow(
                blur_radius=14,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.35, "#10B981"),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Row(
                tight=True,
                spacing=7,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.ADD_CIRCLE_ROUNDED, size=16, color="#022C22"),
                    ft.Text(label, size=12.5, weight=ft.FontWeight.W_800, color="#022C22"),
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
                    border_radius=ft.BorderRadius.all(20),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.4, ft.Colors.AMBER_400)),
                    tooltip="Open Platform Super Admin Console: Unified review queue & catalog manager",
                    content=ft.Row(
                        tight=True,
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED, size=16, color=ft.Colors.AMBER_400),
                            ft.Text(badge_label, size=12, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_400),
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
                border_radius=ft.BorderRadius.all(20),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_400)),
                tooltip="Your Nu-Coins balance. Tap to view Studio & Top Up",
                content=ft.Row(
                    tight=True,
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=16, color=ft.Colors.AMBER_400),
                        self.coins_badge_text,
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
        # wrap=True lets the buttons flow onto a second line on narrow screens
        self.header_actions_row = ft.Row(
            spacing=8,
            run_spacing=8,
            wrap=True,
            alignment=ft.MainAxisAlignment.END,
            controls=[],
        )
        self._update_header_actions()

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=20, vertical=12),
            border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
            content=ft.Row(
                wrap=True,  # title block and actions wrap instead of overflowing
                spacing=12,
                run_spacing=10,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.ARROW_BACK_ROUNDED,
                                icon_size=20,
                                tooltip="Return to Study Hub",
                                on_click=lambda _: self.on_navigate_back(),
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        tight=True,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            ft.Text("Study Pack Marketplace", size=17, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                                border_radius=ft.BorderRadius.all(6),
                                                bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.ON_PRIMARY),
                                                content=ft.Text("CURATED REVISION", size=7, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                                            ),
                                        ],
                                    ),
                                    ft.Text("Prebuilt Flashcard Decks, Quizzes & Exam Simulators", size=9.5, color=ft.Colors.GREY_500),
                                ],
                            ),
                        ],
                    ),
                    self.header_actions_row,
                ],
            ),
        )

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
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.PRIMARY)),
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
                                colors=[ft.Colors.with_opacity(0.35, ft.Colors.PRIMARY), ft.Colors.TRANSPARENT],
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
                                bgcolor="#FFFFFF",
                                content=ft.Row(
                                    tight=True,
                                    spacing=6,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Text("Explore Curated Packs", size=11.5, weight=ft.FontWeight.W_700, color="#064E3B"),
                                        ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=13, color="#064E3B"),
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
        # Always build brand-new controls. Re-attaching a previously detached
        # control (the old shared grid / spinner) can fail to render in Flet.
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
        title = pack.get("title", "Untitled Study Pack")
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
        dlg_width = min(self.page.width - 32, 440) if self.page.width else 420

        # ── Palette: same emerald-tinted surfaces as the publish modal ──
        BG = "#0B1A16"
        PANEL_BG = "#102620"
        PANEL_BORDER = "#1F4037"
        ACCENT = "#34D399"
        TEXT_MAIN = "#ECFDF5"
        TEXT_MUTED = "#8FB5A8"
        DARK_ON_ACCENT = "#022C22"
        AMBER = "#FBBF24"
        RED = "#F87171"

        confirm_dialog = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=22),
            bgcolor=BG,
            content_padding=ft.Padding.all(22),
        )

        # Accent for this pack: mint when free, amber when it costs coins
        tone = ACCENT if is_free else AMBER
        on_tone = DARK_ON_ACCENT if is_free else "#2B1D00"

        async def _confirm_download(btn):
            btn.disabled = True
            btn.content = ft.Row(
                tight=True,
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=on_tone),
                    ft.Text("Adding to Vault...", size=12.5, weight=ft.FontWeight.W_800, color=on_tone),
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

        # ── Header ──
        header_icon = ft.Container(
            width=44,
            height=44,
            border_radius=ft.BorderRadius.all(14),
            alignment=ft.Alignment.CENTER,
            gradient=ft.LinearGradient(
                colors=["#34D399", "#059669"] if is_free else ["#FCD34D", "#D97706"],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            content=ft.Icon(
                ft.Icons.FILE_DOWNLOAD_DONE_ROUNDED if is_free else ft.Icons.LOCK_OPEN_ROUNDED,
                size=22,
                color=on_tone,
            ),
        )
        header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        header_icon,
                        ft.Column(
                            spacing=1,
                            tight=True,
                            controls=[
                                ft.Text(
                                    "Add to Your Vault" if is_free else "Unlock Study Pack",
                                    size=16,
                                    weight=ft.FontWeight.W_800,
                                    color=TEXT_MAIN,
                                ),
                                ft.Text(
                                    "Free community pack" if is_free else "Premium community pack",
                                    size=11.5,
                                    color=TEXT_MUTED,
                                ),
                            ],
                        ),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_size=18,
                    icon_color=TEXT_MUTED,
                    on_click=lambda _: self._close_dialog(confirm_dialog),
                ),
            ],
        )

        # ── Pack info card ──
        badges = [
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=ft.Colors.with_opacity(0.14, ACCENT),
                content=ft.Text(category.upper(), size=9, weight=ft.FontWeight.W_800, color=ACCENT),
            )
        ]
        if is_official:
            badges.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.with_opacity(0.14, AMBER),
                    content=ft.Row(
                        tight=True,
                        spacing=3,
                        controls=[
                            ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=11, color=AMBER),
                            ft.Text("OFFICIAL", size=9, weight=ft.FontWeight.W_800, color=AMBER),
                        ],
                    ),
                )
            )

        info_card = ft.Container(
            padding=ft.Padding.all(14),
            border_radius=ft.BorderRadius.all(14),
            bgcolor=PANEL_BG,
            border=ft.Border.all(1, PANEL_BORDER),
            content=ft.Column(
                spacing=6,
                tight=True,
                controls=[
                    ft.Row(spacing=6, controls=badges),
                    ft.Text(title, size=15.5, weight=ft.FontWeight.W_800, color=TEXT_MAIN, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"by {creator_name}", size=11, color=TEXT_MUTED),
                    ft.Text(
                        desc or "Curated flashcards and high-yield quiz bank for targeted revision.",
                        size=11.5,
                        color=TEXT_MUTED,
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
            ),
        )

        # ── Contents: three equal stat tiles ──
        def _stat_tile(icon: str, color: str, value: str, label: str) -> ft.Container:
            return ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=8, vertical=12),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=PANEL_BG,
                border=ft.Border.all(1, PANEL_BORDER),
                content=ft.Column(
                    spacing=3,
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(icon, size=18, color=color),
                        ft.Text(value, size=15, weight=ft.FontWeight.W_800, color=TEXT_MAIN),
                        ft.Text(label, size=10, color=TEXT_MUTED),
                    ],
                ),
            )

        stats_row = ft.Row(
            spacing=10,
            controls=[
                _stat_tile(ft.Icons.STYLE_ROUNDED, ACCENT, str(fc_count), "Flashcards"),
                _stat_tile(ft.Icons.QUIZ_ROUNDED, "#22D3EE", str(q_count), "Questions"),
                _stat_tile(ft.Icons.TIMER_ROUNDED, AMBER, "Included", "Exam Sim"),
            ],
        )

        # ── Price / wallet ──
        if is_free:
            price_box = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.10, ACCENT),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.28, ACCENT)),
                content=ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18, color=ACCENT),
                        ft.Column(
                            spacing=1,
                            tight=True,
                            expand=True,
                            controls=[
                                ft.Text("Free community access", size=12, weight=ft.FontWeight.W_700, color=TEXT_MAIN),
                                ft.Text("A personal copy is added to your vault.", size=11, color=TEXT_MUTED),
                            ],
                        ),
                    ],
                ),
            )
        else:
            price_box = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=PANEL_BG,
                border=ft.Border.all(1, PANEL_BORDER),
                content=ft.Column(
                    spacing=10,
                    tight=True,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Column(
                                    spacing=1,
                                    tight=True,
                                    controls=[
                                        ft.Text("Unlock cost", size=10.5, color=TEXT_MUTED),
                                        ft.Text(f" {price_coins} Nu-Coins", size=15, weight=ft.FontWeight.W_800, color=AMBER),
                                    ],
                                ),
                                ft.Container(width=1, height=30, bgcolor=PANEL_BORDER),
                                ft.Column(
                                    spacing=1,
                                    tight=True,
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    controls=[
                                        ft.Text("Your balance", size=10.5, color=TEXT_MUTED),
                                        ft.Text(
                                            f" {self.user_coins} Coins",
                                            size=15,
                                            weight=ft.FontWeight.W_800,
                                            color=ACCENT if has_enough_coins else RED,
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        *(
                            [
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                                    border_radius=ft.BorderRadius.all(8),
                                    bgcolor=ft.Colors.with_opacity(0.10, RED),
                                    content=ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=14, color=RED),
                                            ft.Text(
                                                f"You need {price_coins - self.user_coins} more Nu-Coins to unlock this pack.",
                                                size=11,
                                                color=RED,
                                            ),
                                        ],
                                    ),
                                )
                            ] if not has_enough_coins else []
                        ),
                    ],
                ),
            )

        # ── Primary action ──
        if is_free:
            action_icon, action_label, action_bg, action_fg = ft.Icons.FILE_DOWNLOAD_ROUNDED, "Add to Vault", ACCENT, DARK_ON_ACCENT
        elif has_enough_coins:
            action_icon, action_label, action_bg, action_fg = ft.Icons.LOCK_OPEN_ROUNDED, f"Unlock for {price_coins} Coins", AMBER, "#2B1D00"
        else:
            action_icon, action_label, action_bg, action_fg = ft.Icons.STOREFRONT_ROUNDED, "Get Coins in Store", AMBER, "#2B1D00"

        if has_enough_coins:
            action_click = lambda e: self.page.run_task(_confirm_download, e.control)
        else:
            action_click = lambda _: (self._close_dialog(confirm_dialog), self.page.go("/store?tab=boosters"))

        action_btn = ft.FilledButton(
            content=ft.Row(
                tight=True,
                spacing=6,
                controls=[
                    ft.Icon(action_icon, size=16, color=action_fg),
                    ft.Text(action_label, size=12.5, weight=ft.FontWeight.W_800, color=action_fg),
                ],
            ),
            height=42,
            style=ft.ButtonStyle(
                bgcolor=action_bg,
                shape=ft.RoundedRectangleBorder(radius=21),
                padding=ft.Padding.symmetric(horizontal=20, vertical=0),
                elevation=0,
            ),
            on_click=action_click,
        )

        cancel_btn = ft.TextButton(
            content=ft.Text("Cancel", size=12.5, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
            height=42,
            on_click=lambda _: self._close_dialog(confirm_dialog),
        )

        confirm_dialog.content = ft.Container(
            width=dlg_width,
            content=ft.Column(
                tight=True,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    header,
                    info_card,
                    stats_row,
                    price_box,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        spacing=8,
                        controls=[cancel_btn, action_btn],
                    ),
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
            self.page.run_task(self._load_data)

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
                                            ft.Text("Share your material with the community", size=11.5, color=TEXT_MUTED),
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
                                "We check quality and add subject tags & cover art.",
                            ),
                            _info_tile(
                                ft.Icons.MONETIZATION_ON_ROUNDED,
                                "Earn 50 Nu-Coins",
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