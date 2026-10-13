import re
import flet as ft
from typing import Dict, Any, Callable, Optional


# ── CURATED SUBJECT THEME PRESETS ──
# Inspired by modern edtech card palettes: vibrant, friendly, high-contrast
CATEGORY_PRESETS = {
    "JAMB UTME": {
        "primary_color": "#059669",
        "gradient": ("#10B981", "#047857"),
        "icon": ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
        "accent": "#065F46",
        "tag": "JAMB UTME CBT",
    },
    "WAEC / NECO": {
        "primary_color": "#2563EB",
        "gradient": ("#3B82F6", "#1D4ED8"),
        "icon": ft.Icons.SCHOOL_ROUNDED,
        "accent": "#1E40AF",
        "tag": "WAEC & NECO SSCE",
    },
    "WAEC WASSCE": {
        "primary_color": "#2563EB",
        "gradient": ("#3B82F6", "#1D4ED8"),
        "icon": ft.Icons.SCHOOL_ROUNDED,
        "accent": "#1E40AF",
        "tag": "WAEC WASSCE",
    },
    "NECO SSCE": {
        "primary_color": "#0284C7",
        "gradient": ("#0EA5E9", "#0369A1"),
        "icon": ft.Icons.AUTO_STORIES_ROUNDED,
        "accent": "#075985",
        "tag": "NECO SSCE",
    },
    "Medicine": {
        "primary_color": "#0D9488",
        "gradient": ("#0D9488", "#059669"),
        "icon": ft.Icons.LOCAL_HOSPITAL_ROUNDED,
        "accent": "#047857",
        "tag": "MEDICINE & HEALTH",
    },
    "STEM": {
        "primary_color": "#6366F1",
        "gradient": ("#6366F1", "#4F46E5"),
        "icon": ft.Icons.TERMINAL_ROUNDED,
        "accent": "#4338CA",
        "tag": "STEM & COMPUTING",
    },
    "Law": {
        "primary_color": "#8B5CF6",
        "gradient": ("#8B5CF6", "#7C3AED"),
        "icon": ft.Icons.GAVEL_ROUNDED,
        "accent": "#6D28D9",
        "tag": "LAW & JUSTICE",
    },
    "Business": {
        "primary_color": "#F59E0B",
        "gradient": ("#F59E0B", "#D97706"),
        "icon": ft.Icons.TRENDING_UP_ROUNDED,
        "accent": "#B45309",
        "tag": "BUSINESS & FINANCE",
    },
    "Languages": {
        "primary_color": "#E11D48",
        "gradient": ("#E11D48", "#BE123C"),
        "icon": ft.Icons.TRANSLATE_ROUNDED,
        "accent": "#9F1239",
        "tag": "LANGUAGES & LINGUISTICS",
    },
    "Exam Prep": {
        "primary_color": "#0284C7",
        "gradient": ("#0284C7", "#0369A1"),
        "icon": ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
        "accent": "#075985",
        "tag": "EXAM PREP & LICENSURE",
    },
    "General": {
        "primary_color": "#059669",
        "gradient": ("#10B981", "#059669"),
        "icon": ft.Icons.AUTO_AWESOME_ROUNDED,
        "accent": "#047857",
        "tag": "GENERAL REVISION",
    },
}


class StudyPackCard(ft.Container):
    """
    World-Class Educational Revision Pack Card.
    Inspired by clean, tactile edtech classes design:
    - Vibrant, themed rounded container per subject category.
    - Signature elevated white squircle container on left with large topic icon.
    - Clean top metadata header (Category tag + Price/Vault status pill).
    - Bold, ultra-crisp white title and educational breakdown metrics.
    - Crisp white action button with tactile elevation and community stats.
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

        category = pack.get("category", "General")
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
        primary = preset["primary_color"]

        super().__init__(
            col={"sm": 12, "md": 6, "lg": 4},
            border_radius=ft.BorderRadius.all(22),
            gradient=ft.LinearGradient(
                colors=[c1, c2],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.WHITE)),
            shadow=ft.BoxShadow(
                blur_radius=14,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.18, primary),
                offset=ft.Offset(0, 4),
            ),
            padding=ft.Padding.symmetric(horizontal=18, vertical=16),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ink=True,
            on_click=self._handle_card_click,
            content=self._build_card_content(preset),
        )

    def _handle_card_click(self, _):
        if self.on_click_preview:
            try:
                self.on_click_preview(self.pack)
            except TypeError:
                self.on_click_preview(self.pack_id)

    def _build_card_content(self, preset: Dict[str, Any]) -> ft.Column:
        pack = self.pack
        raw_title = pack.get("title", "Untitled Pack")
        title = re.sub(r"(?i)\s*[\[\(]\s*pack\s*import\s*[\]\)]\s*[:\-–—]?\s*", " ", raw_title)
        title = re.sub(r"(?i)^pack\s*import\s*[:\-–—]?\s*", "", title).strip() or "Study Pack"
        is_official = pack.get("is_official", False)
        price_coins = pack.get("price_coins", 0)
        is_owned = pack.get("is_owned", False)
        is_creator = pack.get("is_creator", False)
        downloads_count = pack.get("downloads_count", 0)
        likes_count = pack.get("likes_count", 0)
        fc_count = pack.get("flashcards_count", 0)
        q_count = pack.get("questions_count", 0)

        creator = pack.get("creator", {})
        creator_name = creator.get("name", "Nu-Age Official" if is_official else "Peer Creator")
        primary_color = preset["primary_color"]
        category_tag = preset.get("tag", "STUDY PACK")

        # ── CBT PAST QUESTIONS METADATA DETECTION ──
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
            m = re.search(r"(?i)\b(JAMB(?:\s+UTME)?|WAEC(?:\s+WASSCE)?|NECO|POST-UTME|GCE|SAT|GRE|GMAT)\b", title)
            if m:
                exam_type = m.group(1).upper()
        if not exam_year:
            m = re.search(r"\b(201\d|202\d)\b", title)
            if m:
                exam_year = int(m.group(1))

        is_cbt_pack = bool(
            exam_type
            or (q_count > 0 and fc_count == 0)
            or "cbt" in str(category_tag).lower()
            or bool(re.search(r"(?i)\b(CBT|JAMB|WAEC|NECO|UTME|WASSCE|SSCE|POST-UTME|SAT|GRE|GMAT)\b", title))
        )

        diagrams_count = pack.get("diagrams_count")
        if diagrams_count is None:
            diagrams_count = sum(1 for q in questions_list if q.get("image_url") or q.get("has_diagram"))
        duration_minutes = pack.get("duration_minutes")

        # ── 1. TOP METADATA ROW ──
        # Left Tags: Category Tag + Exam Badge + Diagram Badge
        left_tags = [
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=9, vertical=4),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.WHITE),
                content=ft.Text(
                    "CBT EXAM PAPER" if is_cbt_pack else category_tag,
                    size=9.5,
                    weight=ft.FontWeight.W_800,
                    color=ft.Colors.WHITE,
                ),
            )
        ]

        if exam_type:
            exam_label = f"{exam_type} {exam_year or ''}".strip()
            left_tags.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.32, ft.Colors.BLACK),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.40, ft.Colors.WHITE)),
                    content=ft.Row([
                        ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=11, color="#FDE68A"),
                        ft.Text(exam_label, size=9.5, weight=ft.FontWeight.W_800, color="#FEF3C7"),
                    ], spacing=4, tight=True),
                )
            )

        if diagrams_count > 0:
            left_tags.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=7, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                    content=ft.Row([
                        ft.Icon(ft.Icons.IMAGE_ROUNDED, size=10, color=ft.Colors.WHITE),
                        ft.Text(f"{diagrams_count}", size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                    ], spacing=3, tight=True),
                )
            )

        cat_tag_row = ft.Row(spacing=5, tight=True, wrap=True, expand=True, controls=left_tags)

        # Right: Pricing / Ownership status pill
        if is_owned:
            status_pill = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.WHITE,
                content=ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=11, color="#059669"),
                    ft.Text("IN VAULT", size=9.5, weight=ft.FontWeight.W_800, color="#059669"),
                ], spacing=3, tight=True),
            )
            btn_text = "Open Cockpit" if is_cbt_pack else "Open"
            btn_icon = ft.Icons.ARROW_FORWARD_ROUNDED
        elif is_creator:
            status_pill = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.50, "#A7F3D0")),
                content=ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=11, color="#A7F3D0"),
                    ft.Text("CREATED BY YOU", size=9.5, weight=ft.FontWeight.W_800, color="#A7F3D0"),
                ], spacing=3, tight=True),
            )
            btn_text = "Inspect Paper" if is_cbt_pack else "Inspect Pack"
            btn_icon = ft.Icons.VISIBILITY_ROUNDED
        elif is_official:
            status_pill = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.WHITE)),
                content=ft.Row([
                    ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=11, color="#FDE68A"),
                    ft.Text("OFFICIAL", size=9.5, weight=ft.FontWeight.W_800, color="#FEF3C7"),
                ], spacing=3, tight=True),
            )
            btn_text = ("Take CBT" if price_coins == 0 else f"{price_coins} Coins") if is_cbt_pack else ("Get Pack" if price_coins == 0 else f"{price_coins} Coins")
            btn_icon = ft.Icons.FILE_DOWNLOAD_ROUNDED if price_coins == 0 else ft.Icons.LOCK_OPEN_ROUNDED
        elif price_coins == 0:
            status_pill = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.WHITE),
                content=ft.Text("FREE ACCESS", size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
            )
            btn_text = "Take CBT" if is_cbt_pack else "Get Pack"
            btn_icon = ft.Icons.FILE_DOWNLOAD_ROUNDED
        else:
            status_pill = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                content=ft.Row([
                    ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=11, color="#FDE68A"),
                    ft.Text(f"{price_coins} COINS", size=9.5, weight=ft.FontWeight.W_800, color="#FDE68A"),
                ], spacing=3, tight=True),
            )
            btn_text = f"{price_coins} Coins"
            btn_icon = ft.Icons.LOCK_OPEN_ROUNDED

        top_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[cat_tag_row, status_pill],
        )

        # ── 2. CENTER CONTENT BLOCK: White Squircle Badge + Info Column ──
        squircle_icon = ft.Icons.WORKSPACE_PREMIUM_ROUNDED if is_cbt_pack else preset["icon"]
        squircle_badge = ft.Container(
            width=64,
            height=64,
            border_radius=ft.BorderRadius.all(18),
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(2, ft.Colors.with_opacity(0.35, primary_color)) if is_cbt_pack else None,
            shadow=ft.BoxShadow(
                blur_radius=10,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.14, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(squircle_icon, size=32, color=primary_color),
        )

        cbt_dur = duration_minutes if duration_minutes else q_count
        cbt_benchmark_text = (
            f"⏱ {q_count} Questions • {cbt_dur} Mins CBT"
            if is_cbt_pack else
            f"{fc_count} Cards • {q_count} Practice Qs"
        )

        info_column = ft.Column(
            spacing=3,
            tight=True,
            controls=[
                ft.Text(
                    title,
                    size=16,
                    weight=ft.FontWeight.W_800,
                    color=ft.Colors.WHITE,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    cbt_benchmark_text,
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.with_opacity(0.92, ft.Colors.WHITE),
                ),
                ft.Text(
                    f"by {creator_name} • CBT Exam Ready",
                    size=11,
                    color=ft.Colors.with_opacity(0.78, ft.Colors.WHITE),
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
        )

        body_row = ft.Row(
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
            controls=[
                squircle_badge,
                ft.Container(content=info_column, expand=True),
            ],
        )

        # ── 3. BOTTOM ROW: Social Stats + Tactile White CTA Pill ──
        social_stats = ft.Row(
            tight=True,
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=13, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                ft.Text(f"{downloads_count}", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                ft.Container(width=4),
                ft.Icon(ft.Icons.FAVORITE_ROUNDED, size=12, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                ft.Text(f"{likes_count}", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
            ],
        )

        cta_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=6),
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.WHITE,
            shadow=ft.BoxShadow(
                blur_radius=6,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            content=ft.Row(
                tight=True,
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(btn_text, size=11.5, weight=ft.FontWeight.W_800, color=primary_color),
                    ft.Icon(btn_icon, size=13, color=primary_color),
                ],
            ),
        )

        bottom_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[social_stats, cta_pill],
        )

        return ft.Column(
            spacing=12,
            tight=True,
            controls=[
                top_row,
                body_row,
                bottom_row,
            ],
        )
