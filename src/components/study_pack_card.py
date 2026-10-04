import flet as ft
from typing import Dict, Any, Callable, Optional


# ── CURATED SUBJECT THEME PRESETS ──
CATEGORY_PRESETS = {
    "Medicine": {
        "gradient": ("#065F46", "#047857"),
        "icon": ft.Icons.LOCAL_HOSPITAL_ROUNDED,
        "accent": "#059669",
        "tag": "MEDICINE & HEALTH",
    },
    "STEM": {
        "gradient": ("#0369A1", "#0284C7"),
        "icon": ft.Icons.TERMINAL_ROUNDED,
        "accent": "#0284C7",
        "tag": "STEM & COMPUTING",
    },
    "Law": {
        "gradient": ("#B45309", "#D97706"),
        "icon": ft.Icons.GAVEL_ROUNDED,
        "accent": "#D97706",
        "tag": "LAW & JUSTICE",
    },
    "Business": {
        "gradient": ("#0F766E", "#0D9488"),
        "icon": ft.Icons.TRENDING_UP_ROUNDED,
        "accent": "#0D9488",
        "tag": "BUSINESS & FINANCE",
    },
    "Languages": {
        "gradient": ("#BE123C", "#E11D48"),
        "icon": ft.Icons.TRANSLATE_ROUNDED,
        "accent": "#E11D48",
        "tag": "LANGUAGES & LINGUISTICS",
    },
    "Exam Prep": {
        "gradient": ("#047857", "#10B981"),
        "icon": ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
        "accent": "#059669",
        "tag": "EXAM PREP & LICENSURE",
    },
    "General": {
        "gradient": ("#065F46", "#10B981"),
        "icon": ft.Icons.AUTO_AWESOME_ROUNDED,
        "accent": "#059669",
        "tag": "GENERAL REVISION",
    }
}


class StudyPackCard(ft.Container):
    """
    World-Class Educational Revision Pack Card.
    Features:
    - Split Card Architecture (Tactile colored header block + Crisp white body).
    - Top Emblem Badge with Category Theme Icon.
    - High-Yield Metric Pills for Flashcards, MCQs, and Exam Simulator.
    - Clear pricing & high-contrast Action CTA button.
    """
    def __init__(
        self,
        pack: Dict[str, Any],
        on_click_preview: Optional[Callable[[Any], None]] = None,
        on_toggle_like: Optional[Callable[[str], None]] = None,
    ):
        self.pack = pack
        self.pack_id = str(pack.get("id"))
        self.on_click_preview = on_click_preview
        self.on_toggle_like = on_toggle_like

        super().__init__(
            col={"sm": 12, "md": 6, "lg": 4},
            bgcolor="#FFFFFF",
            border_radius=ft.BorderRadius.all(18),
            border=ft.Border.all(1, "#E2E8F0"),
            padding=ft.Padding.all(0),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ink=True,
            on_click=self._handle_card_click,
            content=self._build_card_content(),
        )

    def _handle_card_click(self, _):
        if self.on_click_preview:
            try:
                self.on_click_preview(self.pack)
            except TypeError:
                self.on_click_preview(self.pack_id)

    def _build_header_banner(self, category: str, is_official: bool, cover_url: Optional[str]) -> ft.Container:
        preset = CATEGORY_PRESETS.get(category, CATEGORY_PRESETS["General"])
        c1, c2 = preset["gradient"]
        accent = preset["accent"]
        icon = preset["icon"]
        tag_text = preset.get("tag", category.upper())

        # Top Badges
        badges = [
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.BLACK),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.WHITE)),
                content=ft.Text(tag_text, size=9, weight=ft.FontWeight.W_800, color="#FFFFFF"),
            ),
        ]

        if is_official:
            badges.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.with_opacity(0.85, "#78350F"),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.6, "#FCD34D")),
                    content=ft.Row(
                        tight=True,
                        spacing=3,
                        controls=[
                            ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=11, color="#FBBF24"),
                            ft.Text("OFFICIAL", size=9, weight=ft.FontWeight.W_800, color="#FEF3C7"),
                        ],
                    ),
                )
            )
        else:
            badges.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=7, vertical=4),
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.BLACK),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.WHITE)),
                    content=ft.Row(
                        tight=True,
                        spacing=3,
                        controls=[
                            ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=10, color="#FFFFFF"),
                            ft.Text("COMMUNITY", size=8.5, weight=ft.FontWeight.W_700, color="#FFFFFF"),
                        ],
                    ),
                )
            )

        # Center Emblem Badge
        center_emblem = ft.Container(
            width=50,
            height=50,
            border_radius=ft.BorderRadius.all(25),
            bgcolor="#FFFFFF",
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(icon, size=26, color=accent),
        )

        return ft.Container(
            height=125,
            width=float("inf"),
            gradient=ft.LinearGradient(
                colors=[c1, c2],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            content=ft.Column(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    # Top Badges Row
                    ft.Container(
                        padding=ft.Padding.only(left=12, right=12, top=10),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=badges,
                        ),
                    ),
                    # Center Emblem
                    ft.Container(
                        alignment=ft.Alignment.CENTER,
                        padding=ft.Padding.only(bottom=12),
                        content=center_emblem,
                    ),
                ],
            ),
        )

    def _build_card_content(self) -> ft.Column:
        pack = self.pack
        title = pack.get("title", "Untitled Pack")
        desc = pack.get("description", "")
        category = pack.get("category", "General")
        is_official = pack.get("is_official", False)
        price_coins = pack.get("price_coins", 0)
        is_owned = pack.get("is_owned", False)
        downloads_count = pack.get("downloads_count", 0)
        fc_count = pack.get("flashcards_count", 0)
        q_count = pack.get("questions_count", 0)
        cover_url = pack.get("cover_image_url")

        creator = pack.get("creator", {})
        creator_name = creator.get("name", "Nu-Age Official" if is_official else "Peer Creator")

        # Price / Action Button
        if is_owned:
            price_widget = ft.Column(
                spacing=1,
                tight=True,
                controls=[
                    ft.Row(
                        tight=True,
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=15, color="#059669"),
                            ft.Text("In Vault", size=13.5, weight=ft.FontWeight.W_800, color="#059669"),
                        ],
                    ),
                    ft.Text("Ready to Practice", size=10, color="#64748B"),
                ],
            )
            action_btn = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=ft.BorderRadius.all(8),
                bgcolor="#ECFDF5",
                border=ft.Border.all(1, "#10B981"),
                content=ft.Row(
                    tight=True,
                    spacing=4,
                    controls=[
                        ft.Text("Open", size=11, weight=ft.FontWeight.W_700, color="#059669"),
                        ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=12, color="#059669"),
                    ],
                ),
            )
        elif price_coins == 0:
            price_widget = ft.Column(
                spacing=1,
                tight=True,
                controls=[
                    ft.Text("FREE", size=15, weight=ft.FontWeight.W_900, color="#059669"),
                    ft.Text("Open Access", size=10, color="#64748B"),
                ],
            )
            action_btn = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=6.5),
                border_radius=ft.BorderRadius.all(8),
                bgcolor="#059669",
                content=ft.Row(
                    tight=True,
                    spacing=4,
                    controls=[
                        ft.Icon(ft.Icons.FILE_DOWNLOAD_ROUNDED, size=13, color="#FFFFFF"),
                        ft.Text("Get Pack", size=11.5, weight=ft.FontWeight.W_700, color="#FFFFFF"),
                    ],
                ),
            )
        else:
            price_widget = ft.Column(
                spacing=1,
                tight=True,
                controls=[
                    ft.Row(
                        tight=True,
                        spacing=3,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=14, color="#D97706"),
                            ft.Text(f"{price_coins}", size=15, weight=ft.FontWeight.W_900, color="#D97706"),
                        ],
                    ),
                    ft.Text("Nu-Coins", size=10, color="#64748B"),
                ],
            )
            action_btn = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=6.5),
                border_radius=ft.BorderRadius.all(8),
                bgcolor="#059669",
                content=ft.Row(
                    tight=True,
                    spacing=4,
                    controls=[
                        ft.Icon(ft.Icons.LOCK_OPEN_ROUNDED, size=13, color="#FFFFFF"),
                        ft.Text("Unlock", size=11.5, weight=ft.FontWeight.W_700, color="#FFFFFF"),
                    ],
                ),
            )

        return ft.Column(
            spacing=0,
            tight=True,
            controls=[
                # 1. Header Banner
                self._build_header_banner(category, is_official, cover_url),

                # 2. Clean White Card Body
                ft.Container(
                    padding=ft.Padding.all(14),
                    bgcolor="#FFFFFF",
                    content=ft.Column(
                        spacing=8,
                        tight=True,
                        controls=[
                            # Title
                            ft.Text(
                                title,
                                size=14.5,
                                weight=ft.FontWeight.W_800,
                                color="#0F172A",
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            # Creator Attribution
                            ft.Row(
                                spacing=5,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(
                                        ft.Icons.VERIFIED_USER_ROUNDED if is_official else ft.Icons.ACCOUNT_CIRCLE_ROUNDED,
                                        size=13,
                                        color="#059669" if is_official else "#64748B",
                                    ),
                                    ft.Text(
                                        f"by {creator_name}",
                                        size=11,
                                        color="#64748B",
                                        weight=ft.FontWeight.W_600,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                            ),
                            # Description Synopsis
                            ft.Text(
                                desc or "Curated flashcards, high-yield quiz bank, and exam simulator for rapid revision.",
                                size=11.5,
                                color="#64748B",
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            # Educational Breakdown Pill Badges
                            ft.Row(
                                spacing=6,
                                wrap=True,
                                controls=[
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                                        border_radius=ft.BorderRadius.all(6),
                                        bgcolor="#F0FDF4",
                                        border=ft.Border.all(1, "#BBF7D0"),
                                        content=ft.Row(
                                            tight=True,
                                            spacing=4,
                                            controls=[
                                                ft.Icon(ft.Icons.STYLE_ROUNDED, size=11, color="#166534"),
                                                ft.Text(f"{fc_count} Cards", size=10, weight=ft.FontWeight.W_700, color="#166534"),
                                            ],
                                        ),
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                                        border_radius=ft.BorderRadius.all(6),
                                        bgcolor="#F0F9FF",
                                        border=ft.Border.all(1, "#BAE6FD"),
                                        content=ft.Row(
                                            tight=True,
                                            spacing=4,
                                            controls=[
                                                ft.Icon(ft.Icons.QUIZ_ROUNDED, size=11, color="#075985"),
                                                ft.Text(f"{q_count} MCQs", size=10, weight=ft.FontWeight.W_700, color="#075985"),
                                            ],
                                        ),
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                                        border_radius=ft.BorderRadius.all(6),
                                        bgcolor="#FEF3C7",
                                        border=ft.Border.all(1, "#FDE68A"),
                                        content=ft.Row(
                                            tight=True,
                                            spacing=4,
                                            controls=[
                                                ft.Icon(ft.Icons.TIMER_ROUNDED, size=11, color="#92400E"),
                                                ft.Text("Exam Sim", size=10, weight=ft.FontWeight.W_700, color="#92400E"),
                                            ],
                                        ),
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=3),
                                        border_radius=ft.BorderRadius.all(6),
                                        bgcolor="#F8FAFC",
                                        border=ft.Border.all(1, "#E2E8F0"),
                                        content=ft.Row(
                                            tight=True,
                                            spacing=3,
                                            controls=[
                                                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=11, color="#64748B"),
                                                ft.Text(f"{downloads_count}", size=10, weight=ft.FontWeight.W_600, color="#64748B"),
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                            ft.Divider(height=1, color="#F1F5F9"),
                            # Footer: Price on left, Action Button on right
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    price_widget,
                                    action_btn,
                                ],
                            ),
                        ],
                    ),
                ),
            ],
        )
