import asyncio

import flet as ft
from src.components.study_flashcards import build_flashcard_session
from src.components.study_quiz import build_quiz
from src.components.study_exam import build_exam


from src.requests.study import (
    get_due_cards,
    upload_material,
    get_materials,
    get_quiz_questions,
    get_exam_questions,
    generate_from_materials,
    check_generation_status
    
)


# Backend sends limits, but we map UI colors here on the frontend
from src.requests.subscription import get_subscription_status

# Backend sends limits, but we map UI colors here on the frontend
PLAN_COLORS = {
    "free": ft.Colors.PRIMARY,
    "pro": ft.Colors.PURPLE_600,
    "unlimited": ft.Colors.ORANGE_600,
    "default": ft.Colors.PRIMARY
}


# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _section_label(text: str) -> ft.Text:
    return ft.Text(
        text.upper(),
        size=10.5,
        weight=ft.FontWeight.W_800,
        color=ft.Colors.GREY_500,
    )


def _card(content, padding=16) -> ft.Container:
    return ft.Container(
        bgcolor=ft.Colors.SURFACE,
        border_radius=ft.BorderRadius.all(14),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
        width=float('inf'),
        padding=padding,
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        ),
        content=content,
    )


def _pill(label, bg, fg) -> ft.Container:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=9, vertical=3),
        bgcolor=bg,
        border_radius=ft.BorderRadius.all(10),
        content=ft.Text(label, size=10, color=fg, weight=ft.FontWeight.W_700),
    )


def _loading(label="Loading…") -> ft.Container:
    c = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
            tight=True,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=38, height=38, stroke_width=3),
                ft.Text(
                    label,
                    size=13.5,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.with_opacity(0.75, ft.Colors.ON_SURFACE),
                ),
            ],
        ),
    )
    c._is_loading = True
    return c


def _error_screen(message: str, on_retry) -> ft.Container:
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        padding=32,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=44, color=ft.Colors.ORANGE_400),
                ft.Text("Couldn't load data", size=15, weight=ft.FontWeight.W_600,
                        color=ft.Colors.ON_SURFACE),
                ft.Text(message, size=12, color=ft.Colors.GREY_400,
                        text_align=ft.TextAlign.CENTER),
                ft.Container(height=4),
                ft.ElevatedButton(
                    "Retry", bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY, height=40,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10), elevation=0
                    ),
                    on_click=lambda _: on_retry(),
                ),
            ],
        ),
    )


def _limit_bar(label: str, used: int, limit: int | None,
               bar_color=ft.Colors.PRIMARY, icon=None) -> ft.Column:
    if limit is None:
        fraction     = 0.0
        value_label  = f"{used} / ∞"
        warn         = False
    else:
        fraction    = min(used / limit, 1.0)
        value_label = f"{used} / {limit}"
        warn        = fraction >= 0.8

    bar_color_final = ft.Colors.RED_400 if warn else bar_color

    return ft.Column(
        spacing=4,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=5,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(icon, size=12, color=bar_color_final) if icon else ft.Container(),
                            ft.Text(
                                label,
                                size=10.5,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.ON_SURFACE,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                        ],
                    ),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=6, vertical=1.5),
                        border_radius=ft.BorderRadius.all(5),
                        bgcolor=ft.Colors.with_opacity(0.10, bar_color_final),
                        content=ft.Text(value_label, size=9.5, color=bar_color_final, weight=ft.FontWeight.W_700),
                    ),
                ],
            ),
            ft.ProgressBar(
                value=fraction,
                color=bar_color_final,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                height=4.5,
                border_radius=ft.BorderRadius.all(3),
            ),
            ft.Text(
                "⚠ Approaching limit — upgrade for more" if warn and limit else "",
                size=9,
                color=ft.Colors.ORANGE_600,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                visible=warn and limit is not None,
            ),
        ],
    )


def format_material_title(raw_title: str) -> str:
    """Format material title to clean sentence case for UI display while preserving the raw string/id for backend calls."""
    if not raw_title or not isinstance(raw_title, str):
        return "Untitled document"
    
    title = raw_title.strip()
    
    # Handle URLs gracefully
    if title.startswith("http://") or title.startswith("https://"):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(title)
            netloc = parsed.netloc.replace("www.", "")
            path_parts = [p for p in parsed.path.split("/") if p]
            if path_parts:
                last_segment = path_parts[-1].replace("-", " ").replace("_", " ")
                if "." in last_segment:
                    last_segment = last_segment.rsplit(".", 1)[0]
                return f"{netloc}: {last_segment.capitalize()}"
            return f"Web: {netloc}"
        except Exception:
            return title

    # Strip common file extensions if present for presentation
    lower = title.lower()
    for ext in [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md", ".json"]:
        if lower.endswith(ext):
            title = title[:-len(ext)]
            break

    # Replace underscores and isolate words
    import re
    cleaned = title.replace("_", " ")
    cleaned = re.sub(r"(?i)\bsm-2\b", "SM-2", cleaned)
    cleaned = re.sub(r"(?<!\bSM)-", " ", cleaned)
    words = cleaned.split()
    if not words:
        return "Untitled document"

    # Recognized acronyms to preserve in uppercase
    acronyms = {"ai", "ml", "api", "url", "pdf", "dna", "rna", "atp", "sm2", "sm-2", "ui", "ux", "id", "os", "it", "cs", "sql", "http", "https"}

    formatted_words = []
    for i, word in enumerate(words):
        w_lower = word.lower().strip(".,:;!?()")
        if w_lower in acronyms:
            formatted_words.append(word.upper())
        elif i == 0:
            formatted_words.append(word.capitalize())
        else:
            formatted_words.append(word.lower())

    result = " ".join(formatted_words)
    return result if result else "Untitled document"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN VIEW
# ─────────────────────────────────────────────────────────────────────────────
async def self_study_view(page: ft.Page):
    visible_trigger=True
    token          = await page.shared_preferences.get("auth_token")

    # ── shared state ──────────────────────────────────────────────────────────
    state = {
        "materials":         [],
        "due_cards":         [],
        "all_due_cards":     [],
        "exam_submit_fn":    None,
        "on_hub":            True,
        "sidebar_open":      False,
        "selected_mat_ids":  set(),
        "was_desktop":       True,
        "generating_mats":   set(),
        "search_query":      "",
        # Dynamic limits (defaults before fetch)
        "plan_id":           "free",
        "plan_label":        "Loading",
        "mat_used":          0,
        "poll_strikes":      {},
        "mat_lim":           5,
        "gen_used":          0,
        "gen_lim":           10,
    }

    # ─────────────────────────────────────────────────────────────────────────
    # APP BAR
    # ─────────────────────────────────────────────────────────────────────────
    sidebar_toggle = ft.IconButton(
        icon=ft.Icons.MENU_OPEN_ROUNDED,
        icon_color=ft.Colors.ON_PRIMARY,
        tooltip="Toggle sidebar",
    )

    app_bar = ft.AppBar(
        bgcolor=ft.Colors.PRIMARY,
        title=ft.Text("Study Hub", color=ft.Colors.ON_PRIMARY,
                      weight=ft.FontWeight.W_700, size=17),
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.ON_PRIMARY,
            on_click=lambda _: page.go("/dashboard"),
        ),
        actions=[sidebar_toggle],
        elevation=0,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN CONTENT SOCKET
    # ─────────────────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────
    # MAIN CONTENT SOCKET (Fixed Single-Tree Layout)
    # ─────────────────────────────────────────────────────────────────────────
    content_socket = ft.Container(expand=True, content=_loading("Loading Study Hub…"))
    
    main_content_wrapper = ft.Container(
        expand=True, 
        content=content_socket,
        padding=0, 
        margin=0
    )
    
    mobile_overlay = ft.Container(
        left=0, right=0, top=0, bottom=0,
        bgcolor=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE),
        visible=False,
    )

    # We use a persistent Stack. Controls are NEVER re-parented, which prevents Flet DOM tearing!
    body_host = ft.Stack(
        expand=True,
        controls=[
            main_content_wrapper,
            mobile_overlay,
            # sidebar_container is appended at boot
        ]
    )
    # ─────────────────────────────────────────────────────────────────────────
    # SIDEBAR
    # ─────────────────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────
    # SIDEBAR
    # ─────────────────────────────────────────────────────────────────────────
    def _create_badge_control():
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
            border_radius=ft.BorderRadius.all(8),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.PRIMARY)),
            bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
            content=ft.Text("FREE", size=9, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
        )

    sidebar_plan_badge = _create_badge_control()
    modal_plan_badge = _create_badge_control()

    sidebar_materials_col = ft.Column(spacing=6, controls=[])
    bars_col = ft.Column(spacing=10, controls=[])

    # Extract the upgrade banner so we can toggle it dynamically
    sidebar_upgrade_banner = ft.Container(
        visible=False, width=float("inf"), border_radius=ft.BorderRadius.all(10),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.ORANGE_500)),
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ORANGE_500),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(spacing=6, controls=[
                    ft.Icon(ft.Icons.BOLT_ROUNDED, color=ft.Colors.ORANGE_600, size=14),
                    ft.Text("Unlock Pro", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.ORANGE_700),
                ]),
                ft.Text("50 materials · 100 AI generations / month", size=10, color=ft.Colors.GREY_500),
                ft.ElevatedButton(
                    content=ft.Row(
                        tight=True, spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=12, color=ft.Colors.ON_PRIMARY),
                            ft.Text("Upgrade Plan (coming soon!)", size=11, color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.W_600),
                        ],
                    ),
                    bgcolor=ft.Colors.ORANGE_500, height=32, width=float("inf"),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                ),
            ],
        ),
    )

    def _refresh_plan_ui():
        color = PLAN_COLORS.get(state["plan_id"], PLAN_COLORS["default"])
        label = (state.get("plan_label") or "Free").upper()
        
        # 1. Update Both Badges with High-Contrast Text & Crisp Border
        for badge in (sidebar_plan_badge, modal_plan_badge):
            badge.bgcolor = ft.Colors.with_opacity(0.14, color)
            badge.border = ft.Border.all(1, ft.Colors.with_opacity(0.40, color))
            badge.content.value = label
            badge.content.color = color
        
        # 2. Update Progress Bars
        bars_col.controls = [
            _limit_bar("Materials", state["mat_used"], state["mat_lim"], ft.Colors.TEAL_600, icon=ft.Icons.DESCRIPTION_OUTLINED),
            _limit_bar("Generations", state["gen_used"], state["gen_lim"], ft.Colors.PURPLE_600, icon=ft.Icons.AUTO_AWESOME_OUTLINED),
        ]
        
        # 3. Disable Action Buttons dynamically if defined
        upload_at_limit = (state["mat_lim"] is not None and state["mat_used"] >= state["mat_lim"])
        gen_at_limit = (state["gen_lim"] is not None and state["gen_used"] >= state["gen_lim"])
        if "upload_btn_sidebar" in locals():
            upload_btn_sidebar.disabled = upload_at_limit
            upload_btn_sidebar.opacity = 0.4 if upload_at_limit else 1.0
        if "generate_btn_sidebar" in locals():
            generate_btn_sidebar.disabled = gen_at_limit
            generate_btn_sidebar.opacity = 0.4 if gen_at_limit else 1.0
        
        # 4. Toggle Free Nudge
        sidebar_upgrade_banner.visible = (state["plan_id"] == "free")

    def _current_selected_ids():
        """Read the live sidebar selection at call-time (not a stale snapshot)."""
        clean_ids = sorted([str(m).strip() for m in state["selected_mat_ids"] if str(m).strip()])
        return clean_ids or None

    async def _sync_material_selection(target_id=None, toggle=True, clear_all=False, select_all=False):
        if clear_all:
            state["selected_mat_ids"].clear()
        elif select_all:
            for m in state.get("materials", []):
                state["selected_mat_ids"].add(m["id"])
        elif target_id:
            if toggle:
                if target_id in state["selected_mat_ids"]:
                    state["selected_mat_ids"].discard(target_id)
                else:
                    state["selected_mat_ids"].add(target_id)

        # 1. Immediate optimistic UI feedback across sidebar & hub
        sel_ids = {str(m).strip() for m in state["selected_mat_ids"] if str(m).strip()}
        all_cards = state.get("all_due_cards") or []
        if sel_ids and all_cards:
            matched_cards = [
                c for c in all_cards
                if (c.get("material_id") and str(c.get("material_id")).strip() in sel_ids)
                or (c.get("source_material_id") and str(c.get("source_material_id")).strip() in sel_ids)
            ]
            if matched_cards or any((c.get("material_id") or c.get("source_material_id")) for c in all_cards):
                state["due_cards"] = matched_cards
        elif not sel_ids and all_cards:
            state["due_cards"] = list(all_cards)

        due_cnt = len(state.get("due_cards", []))
        if "sidebar_due_text" in state and state["sidebar_due_text"]:
            state["sidebar_due_text"].value = f"{due_cnt} due"
            try: state["sidebar_due_text"].update()
            except Exception: pass

        _refresh_sidebar_materials()
        if state.get("on_hub"):
            content_socket.content = _build_hub(state.get("due_cards", []), state.get("materials", []))
            page.update()

        # 2. Fetch live due cards scoped to the new selection from backend
        try:
            live_cards = await asyncio.wait_for(
                get_due_cards(token, _current_selected_ids()),
                timeout=15
            )
            if not isinstance(live_cards, Exception):
                state["due_cards"] = live_cards or []
                if not _current_selected_ids():
                    state["all_due_cards"] = list(state["due_cards"])

                due_cnt = len(state["due_cards"])
                if "sidebar_due_text" in state and state["sidebar_due_text"]:
                    state["sidebar_due_text"].value = f"{due_cnt} due"
                    try: state["sidebar_due_text"].update()
                    except Exception: pass

                if state.get("on_hub"):
                    content_socket.content = _build_hub(state["due_cards"], state.get("materials", []))
                    page.update()
        except Exception as ex:
            print(f"[STUDY] Error syncing due cards: {ex}")

    def _on_search_materials(e):
        state["search_query"] = (e.control.value or "").strip().lower()
        _refresh_sidebar_materials()
        page.update()

    def _select_all_materials(e):
        page.run_task(_sync_material_selection, select_all=True)

    def _clear_selected_materials(e):
        page.run_task(_sync_material_selection, clear_all=True)

    # Pinned quick counters for sidebar overview
    state["sidebar_due_text"] = ft.Text("—", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY)
    state["sidebar_vault_text"] = ft.Text("—", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_600)

    def _refresh_sidebar_materials():
        sidebar_materials_col.controls.clear()
        mats = state["materials"]
        query = state.get("search_query", "")
        if query:
            mats = [
                m for m in mats
                if query in m.get("title", "").lower()
                or query in format_material_title(m.get("title", "")).lower()
            ]

        if not mats:
            sidebar_materials_col.controls.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=16),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                        controls=[
                            ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=24, color=ft.Colors.GREY_400),
                            ft.Text(
                                "No materials found" if query else "Vault is empty",
                                size=11,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.GREY_600,
                            ),
                            ft.Text(
                                "Try another search" if query else "Upload notes or PDF to start",
                                size=9.5,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                    ),
                )
            )
            return

        for mat in mats:
            mat_id = mat["id"]
            raw_title = mat.get("title", "Untitled Document")
            display_title = format_material_title(raw_title)
            stype = mat.get("source_type", "text").lower()

            if "pdf" in stype or raw_title.lower().endswith(".pdf"):
                m_icon = ft.Icons.PICTURE_AS_PDF_ROUNDED
                m_color = ft.Colors.RED_400
                m_tag = "PDF"
            elif "url" in stype:
                m_icon = ft.Icons.LINK_ROUNDED
                m_color = ft.Colors.TEAL_400
                m_tag = "URL"
            else:
                m_icon = ft.Icons.DESCRIPTION_ROUNDED
                m_color = ft.Colors.BLUE_400
                m_tag = "NOTE"

            is_selected = mat_id in state["selected_mat_ids"]

            chip = ft.Container(
                border_radius=ft.BorderRadius.all(8),
                border=ft.Border.all(
                    1.2 if is_selected else 1,
                    ft.Colors.with_opacity(0.35, ft.Colors.PRIMARY) if is_selected else ft.Colors.with_opacity(0.09, ft.Colors.ON_SURFACE),
                ),
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_selected else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                padding=ft.Padding.symmetric(horizontal=8, vertical=7),
                ink=True,
                data=mat_id,
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=26,
                            height=26,
                            border_radius=ft.BorderRadius.all(6),
                            bgcolor=ft.Colors.with_opacity(0.12, m_color),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(m_icon, color=m_color, size=14),
                        ),
                        ft.Column(
                            spacing=1,
                            expand=True,
                            controls=[
                                ft.Text(
                                    display_title,
                                    size=11,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.ON_SURFACE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    m_tag,
                                    size=8.5,
                                    color=ft.Colors.GREY_500,
                                    weight=ft.FontWeight.W_500,
                                ),
                            ],
                        ),
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if is_selected else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                            color=ft.Colors.PRIMARY if is_selected else ft.Colors.GREY_400,
                            size=15,
                        ),
                    ],
                ),
            )

            def _toggle(e, mid=mat_id):
                page.run_task(_sync_material_selection, target_id=mid)

            chip.on_click = _toggle
            sidebar_materials_col.controls.append(chip)

    material_search_field = ft.TextField(
        hint_text="Search...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        dense=True,
        text_size=11,
        height=34,
        border_radius=ft.BorderRadius.all(8),
        border_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        on_change=_on_search_materials,
    )

    # ── Minimalist Modern Action Tiles ───────────────────────────────────────
    upload_action_tile = ft.Container(
        expand=True,
        height=52,
        border_radius=ft.BorderRadius.all(10),
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.11, ft.Colors.ON_SURFACE)),
        padding=ft.Padding.symmetric(horizontal=9, vertical=6),
        ink=True,
        on_click=lambda _: _open_upload_modal(),
        tooltip="Upload notes, PDFs, or slides",
        content=ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=30,
                    height=30,
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, size=16, color=ft.Colors.ON_SURFACE),
                ),
                ft.Column(
                    spacing=1,
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Text("Upload", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE, max_lines=1),
                        ft.Text("PDF · Notes", size=8.5, color=ft.Colors.GREY_500, max_lines=1),
                    ],
                ),
            ],
        ),
    )

    generate_action_tile = ft.Container(
        expand=True,
        height=52,
        border_radius=ft.BorderRadius.all(10),
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.24, ft.Colors.PRIMARY)),
        padding=ft.Padding.symmetric(horizontal=9, vertical=6),
        ink=True,
        on_click=lambda _: _open_generate_panel(),
        tooltip="AI generate flashcards, quizzes & exams",
        content=ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=30,
                    height=30,
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.16, ft.Colors.PRIMARY),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                ),
                ft.Column(
                    spacing=1,
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Text("AI Gen", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY, max_lines=1),
                        ft.Text("Auto-Pack", size=8.5, color=ft.Colors.with_opacity(0.85, ft.Colors.PRIMARY), max_lines=1),
                    ],
                ),
            ],
        ),
    )

    upload_btn_sidebar = upload_action_tile
    generate_btn_sidebar = generate_action_tile

    def _sidebar_header(icon, label, trailing=None):
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=2, vertical=4),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=6,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(icon, color=ft.Colors.PRIMARY, size=13),
                            ft.Text(
                                label.upper(),
                                size=10,
                                weight=ft.FontWeight.W_700,
                                color=ft.Colors.GREY_500,
                            ),
                        ],
                    ),
                    trailing or ft.Container(),
                ],
            ),
        )

    # ── Slim Icon Rail (54px) ────────────────────────────────────────────────
    def _rail_icon_btn(icon, tooltip, on_click, is_active=False):
        return ft.Container(
            width=36,
            height=36,
            border_radius=ft.BorderRadius.all(8),
            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY) if is_active else ft.Colors.TRANSPARENT,
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(
                icon,
                size=17,
                color=ft.Colors.PRIMARY if is_active else ft.Colors.with_opacity(0.65, ft.Colors.ON_SURFACE),
            ),
            ink=True,
            tooltip=tooltip,
            on_click=on_click,
        )

    def _show_shortcuts_dialog():
        dlg_w = min(page.width - 40, 420) if page.width else 380
        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.LIGHTBULB_OUTLINED, color=ft.Colors.PRIMARY, size=20),
                    ft.Text("Self-Study Hub Tips", size=15, weight=ft.FontWeight.W_700),
                ],
            ),
            content=ft.Container(
                width=dlg_w,
                content=ft.Column(
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=8,
                    controls=[
                        ft.Text("• Filter topics using the materials list in the sidebar.", size=12),
                        ft.Text("• Active materials scope all flashcards, quizzes, and mock exams.", size=12),
                        ft.Text("• Launch Flashcards, Quizzes, or Full Exam Simulations directly per material card.", size=12),
                        ft.Text("• Space: Flip flashcard / Advance session.", size=12),
                        ft.Text("• 1, 2, 3, 4: Rate flashcard recall (Again, Hard, Good, Easy).", size=12),
                        ft.Text("• Tap 'Studio & Quotas' to upload materials and AI synthesize study decks.", size=12),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Got it", on_click=lambda e: _close_shortcuts_dialog(dlg))
            ],
        )
        def _close_shortcuts_dialog(d):
            d.open = False
            page.update()
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def _open_studio_modal():
        def _close_studio(e):
            studio_dlg.open = False
            page.update()

        def _launch_upload(e):
            studio_dlg.open = False
            page.update()
            _open_upload_modal()

        def _launch_generate(e):
            studio_dlg.open = False
            page.update()
            _open_generate_panel()

        at_mat_lim = state["mat_lim"] is not None and state["mat_used"] >= state["mat_lim"]
        at_gen_lim = state["gen_lim"] is not None and state["gen_used"] >= state["gen_lim"]

        studio_upload_tile = ft.Container(
            expand=True,
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(14),
            ink=not at_mat_lim,
            disabled=at_mat_lim,
            opacity=0.45 if at_mat_lim else 1.0,
            on_click=_launch_upload,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=ft.BorderRadius.all(8),
                                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, color=ft.Colors.ON_SURFACE, size=18),
                            ),
                            ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=14, color=ft.Colors.GREY_400),
                        ],
                    ),
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text("Upload Material", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text("PDFs, slides & notes", size=10, color=ft.Colors.GREY_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                    ),
                ],
            ),
        )

        studio_gen_tile = ft.Container(
            expand=True,
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.PRIMARY),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.24, ft.Colors.PRIMARY)),
            padding=ft.Padding.all(14),
            ink=not at_gen_lim,
            disabled=at_gen_lim,
            opacity=0.45 if at_gen_lim else 1.0,
            on_click=_launch_generate,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=ft.BorderRadius.all(8),
                                bgcolor=ft.Colors.with_opacity(0.16, ft.Colors.PRIMARY),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                            ),
                            ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                        ],
                    ),
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text("AI Synthesis", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text("Auto-pack cards & quiz", size=10, color=ft.Colors.with_opacity(0.85, ft.Colors.PRIMARY), max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                    ),
                ],
            ),
        )

        _refresh_plan_ui()

        dialog_w = min(page.width - 32, 450) if page.width else 420

        studio_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=ft.BorderRadius.all(8),
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                controls=[
                                    ft.Text("Studio & Quotas", size=15.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                    ft.Text("Uploads, AI generation & limits", size=10, color=ft.Colors.GREY_500),
                                ],
                            ),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        icon_color=ft.Colors.GREY_400,
                        tooltip="Close",
                        on_click=_close_studio,
                    ),
                ],
            ),
            content=ft.Container(
                width=dialog_w,
                content=ft.Column(
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=14,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row(
                                        spacing=7,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.STARS_ROUNDED, size=16, color=PLAN_COLORS.get(state["plan_id"], ft.Colors.PRIMARY)),
                                            ft.Text(f"Plan: {state['plan_label'].title()}", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                        ],
                                    ),
                                    modal_plan_badge,
                                ],
                            ),
                        ),
                        _section_label("CREATIVE STUDIO"),
                        ft.Row(
                            spacing=10,
                            controls=[
                                studio_upload_tile,
                                studio_gen_tile,
                            ],
                        ),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        _section_label("PLAN QUOTAS & USAGE"),
                        bars_col,
                        sidebar_upgrade_banner,
                    ],
                ),
            ),
            actions=[],
        )
        page.overlay.append(studio_dlg)
        studio_dlg.open = True
        page.update()

    sidebar_rail = ft.Container(
        width=54,
        bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
        border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
        padding=ft.Padding.symmetric(vertical=12, horizontal=6),
        content=ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=0,
            controls=[
                # Top brand icon & navigation shortcuts
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                    controls=[
                        # 3D Brand Cube
                        ft.Container(
                            width=36,
                            height=36,
                            border_radius=ft.BorderRadius.all(10),
                            gradient=ft.LinearGradient(
                                begin=ft.Alignment.TOP_LEFT,
                                end=ft.Alignment.BOTTOM_RIGHT,
                                colors=[ft.Colors.PRIMARY, ft.Colors.SECONDARY],
                            ),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.WHITE, size=18),
                            tooltip="Self-Study Hub",
                            ink=True,
                            on_click=lambda _: go_hub(),
                        ),
                        ft.Container(height=4),
                        _rail_icon_btn(ft.Icons.SPACE_DASHBOARD_ROUNDED, "Hub Home", lambda _: go_hub(), is_active=True),
                        _rail_icon_btn(ft.Icons.STYLE_ROUNDED, "Flashcards", lambda _: page.run_task(_start_flashcards, _current_selected_ids())),
                        _rail_icon_btn(ft.Icons.QUIZ_ROUNDED, "Quick Quiz", lambda _: page.run_task(_start_quiz, _current_selected_ids())),
                        _rail_icon_btn(ft.Icons.TIMER_OUTLINED, "Exam Simulator", lambda _: page.run_task(_start_exam, _current_selected_ids())),
                        ft.Container(
                            width=22,
                            height=1,
                            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE),
                            margin=ft.Padding.symmetric(vertical=4),
                        ),
                        _rail_icon_btn(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, "Studio & Quotas", lambda _: _open_studio_modal()),
                    ],
                ),
                # Bottom rail items (Help, Collapse)
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        _rail_icon_btn(
                            ft.Icons.HELP_OUTLINE_ROUNDED,
                            "Keyboard Shortcuts & Tips",
                            lambda _: _show_shortcuts_dialog(),
                        ),
                        _rail_icon_btn(
                            ft.Icons.KEYBOARD_DOUBLE_ARROW_LEFT_ROUNDED,
                            "Collapse Sidebar",
                            lambda _: _toggle_sidebar(None),
                        ),
                    ],
                ),
            ],
        ),
    )

    # ── Pinned Quick Overview items ──────────────────────────────────────────
    def _on_click_review_queue(e):
        if state.get("on_hub"):
            page.run_task(_start_flashcards, _current_selected_ids())
        else:
            go_hub()

    def _on_click_vault_pinned(e):
        if not state.get("on_hub"):
            go_hub()

    def _pinned_row(icon, title, badge_control, on_click):
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            border_radius=ft.BorderRadius.all(8),
            ink=True,
            on_click=on_click,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=8,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(icon, size=15, color=ft.Colors.with_opacity(0.65, ft.Colors.ON_SURFACE)),
                            ft.Text(
                                title,
                                size=11.5,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.ON_SURFACE,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                        ],
                    ),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                        content=badge_control,
                    ),
                ],
            ),
        )

    # ── Minimalist Sidebar Footer (Pinned to bottom of pane) ─────────────────
    sidebar_footer = ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
        ink=True,
        on_click=lambda _: _toggle_sidebar(None),
        tooltip="Collapse sidebar",
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.KEYBOARD_DOUBLE_ARROW_LEFT_ROUNDED, size=15, color=ft.Colors.GREY_500),
                        ft.Text("Collapse sidebar", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600),
                    ],
                ),
                ft.Icon(ft.Icons.CHEVRON_LEFT_ROUNDED, size=16, color=ft.Colors.GREY_400),
            ],
        ),
    )

    # ── Expanded Content Pane ────────────────────────────────────────────────
    sidebar_pane = ft.Container(
        expand=True,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                # Top Header (Pinned)
                ft.Container(
                    padding=ft.Padding.only(left=14, right=14, top=14, bottom=10),
                    border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE))),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=8,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                                    ft.Text("Study Studio", size=14.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                ],
                            ),
                            ft.Container(),
                        ],
                    ),
                ),
                # Middle scrollable content
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        spacing=10,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=10),
                                content=ft.Column(
                                    spacing=12,
                                    controls=[
                                        # ── SECTION 1: SIDEBAR NAVIGATION MENU ─────────────────────
                                        _pinned_row(
                                            ft.Icons.STYLE_ROUNDED,
                                            "Review Queue",
                                            state["sidebar_due_text"],
                                            _on_click_review_queue,
                                        ),
                                        _pinned_row(
                                            ft.Icons.FOLDER_SPECIAL_ROUNDED,
                                            "Vault Overview",
                                            state["sidebar_vault_text"],
                                            _on_click_vault_pinned,
                                        ),
                                        _pinned_row(
                                            ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                                            "Studio & Quotas",
                                            sidebar_plan_badge,
                                            lambda _: _open_studio_modal(),
                                        ),

                                        # ── SECTION 2: DEDICATED STUDY MATERIALS ───────────────────
                                        ft.Container(
                                            padding=ft.Padding.only(top=4),
                                            content=ft.Column(
                                                spacing=8,
                                                controls=[
                                                    ft.Row(
                                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                        controls=[
                                                            ft.Row(
                                                                spacing=6,
                                                                tight=True,
                                                                controls=[
                                                                    ft.Icon(ft.Icons.AUTO_STORIES_OUTLINED, size=13, color=ft.Colors.GREY_600),
                                                                    ft.Text("STUDY MATERIALS", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.GREY_600),
                                                                ],
                                                            ),
                                                            ft.Row(
                                                                spacing=0,
                                                                tight=True,
                                                                controls=[
                                                                    ft.TextButton(
                                                                        "All",
                                                                        style=ft.ButtonStyle(
                                                                            color=ft.Colors.PRIMARY,
                                                                            padding=ft.Padding.symmetric(horizontal=4, vertical=0),
                                                                        ),
                                                                        on_click=_select_all_materials,
                                                                    ),
                                                                    ft.Text("·", size=10, color=ft.Colors.GREY_400),
                                                                    ft.TextButton(
                                                                        "Clear",
                                                                        style=ft.ButtonStyle(
                                                                            color=ft.Colors.GREY_500,
                                                                            padding=ft.Padding.symmetric(horizontal=4, vertical=0),
                                                                        ),
                                                                        on_click=_clear_selected_materials,
                                                                    ),
                                                                ],
                                                            ),
                                                        ],
                                                    ),
                                                    material_search_field,
                                                    sidebar_materials_col,
                                                ],
                                            ),
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),
                ),
                # Bottom Minimal Collapse Footer (Pinned)
                sidebar_footer,
            ],
        ),
    )

    # ── Dual-Pane Sidebar Container ──────────────────────────────────────────
    sidebar_container = ft.Container(
        width=320,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE))),
        shadow=ft.BoxShadow(
            blur_radius=12,
            color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
            offset=ft.Offset(2, 0),
        ),
        content=ft.Row(
            spacing=0,
            expand=True,
            controls=[
                sidebar_rail,
                sidebar_pane,
            ],
        ),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # MOBILE & DESKTOP RESPONSIVE LAYOUT
    # ─────────────────────────────────────────────────────────────────────────
    # Pin the sidebar securely inside the Stack
    sidebar_container.left = 0
    sidebar_container.top = 0
    sidebar_container.bottom = 0
    
    # Wire the overlay and inject the sidebar into our persistent Stack
    mobile_overlay.on_click = lambda _: _toggle_sidebar(None)
    body_host.controls.append(sidebar_container)

    def update_layout(e=None):
        is_desktop = page.width >= 800 if page.width else True
        
        # Auto-close sidebar when shrinking from desktop to mobile
        if e is not None and not is_desktop and state.get("was_desktop", True): 
            state["sidebar_open"] = False
        
        state["was_desktop"] = is_desktop
        sidebar_toggle.icon = ft.Icons.MENU_OPEN_ROUNDED if state["sidebar_open"] else ft.Icons.MENU_ROUNDED

        if is_desktop:
            target_width = 320 if state["sidebar_open"] else 54
            sidebar_container.width = target_width
            sidebar_container.visible = True
            sidebar_rail.visible = True
            sidebar_pane.visible = state["sidebar_open"]
            mobile_overlay.visible = False
            sidebar_container.shadow = None
            
            # Push content right (54px rail or 320px full sidebar)
            main_content_wrapper.padding = ft.Padding.only(left=target_width)
        else:
            target_width = min((page.width * 0.88 if page.width else 300), 320)
            sidebar_container.width = target_width
            sidebar_container.shadow = ft.BoxShadow(blur_radius=20, color=ft.Colors.BLACK26)
            sidebar_container.visible = state["sidebar_open"]
            sidebar_rail.visible = False
            sidebar_pane.visible = True
            mobile_overlay.visible = state["sidebar_open"]
            
            # Content takes full screen; sidebar overlays it
            main_content_wrapper.padding = ft.Padding.only(left=0)

        # Dynamically scale hero banner if on hub
        if callable(state.get("update_hero_responsive")):
            try:
                state["update_hero_responsive"]()
            except Exception:
                pass

        page.update()

    def _toggle_sidebar(e=None):
        state["sidebar_open"] = not state["sidebar_open"]
        update_layout()

    sidebar_toggle.on_click = _toggle_sidebar
    page.on_resize = update_layout

    # ─────────────────────────────────────────────────────────────────────────
    # NAV HELPERS
    # ─────────────────────────────────────────────────────────────────────────
    def _set_appbar(title: str, on_back):
        app_bar.title = ft.Text(title, color=ft.Colors.ON_PRIMARY,
                                weight=ft.FontWeight.W_700, size=17)
        app_bar.leading = ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.ON_PRIMARY,
            on_click=lambda _: on_back(),
        )

    def _lock_exam_ui(locked: bool):
        """Prevent leaving/navigating away mid-exam without confirming."""
        state["exam_locked"] = locked
        sidebar_toggle.disabled = locked
        if locked and state["sidebar_open"]:
            state["sidebar_open"] = False
            update_layout()
        # Best-effort: ask the browser/OS to prompt before closing the tab.
        # Support for this varies by Flet version/platform, so failures
        # here are non-fatal.
        try:
            page.window.prevent_close = locked
            page.update()
        except Exception:
            pass
        page.update()

    def go_hub(label_or_e="Loading Study Hub…"):
        label = label_or_e if isinstance(label_or_e, str) else "Loading Study Hub…"
        state["on_hub"] = True
        _reset_keyboard()
        _lock_exam_ui(False)
        _set_appbar("Study Hub", lambda: page.go("/dashboard"))
        content_socket.content = _loading(label)
        page.update()
        page.run_task(_load_hub)

    def go_flashcards(cards: list):
        state["on_hub"] = False
        _set_appbar("Flashcards", go_hub)
        content_socket.content = _build_flashcard_session(cards)
        page.update()

    def go_quiz(questions: list):
        state["on_hub"] = False
        _set_appbar("Quick Quiz", go_hub)
        content_socket.content = _build_quiz(questions)
        page.update()

    def _confirm_exit_exam():
        def _submit_and_leave(e):
            exit_dlg.open = False
            page.update()
            submit_fn = state.get("exam_submit_fn")
            if submit_fn:
                submit_fn()
            else:
                go_hub("Returning to Study Hub…")

        def _exit_without_submit(e):
            exit_dlg.open = False
            page.update()
            go_hub("Returning to Study Hub…")

        def _cancel(e):
            exit_dlg.open = False
            page.update()

        exit_dlg_w = min(page.width - 44, 380) if page.width else 360
        exit_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=20),
            bgcolor=ft.Colors.SURFACE,
            content_padding=ft.Padding.all(18 if (page.width and page.width < 450) else 24),
            content=ft.Container(
                width=exit_dlg_w,
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16,
                    controls=[
                        # Concentric glowing timer badge
                        ft.Container(
                            width=58,
                            height=58,
                            border_radius=ft.BorderRadius.all(29),
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_600),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Container(
                                width=42,
                                height=42,
                                border_radius=ft.BorderRadius.all(21),
                                bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER_600),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.TIMER_ROUNDED, color=ft.Colors.AMBER_600, size=22),
                            ),
                        ),
                        ft.Column(
                            tight=True,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=6,
                            controls=[
                                ft.Text(
                                    "Submit & End Exam?",
                                    size=18,
                                    weight=ft.FontWeight.W_800,
                                    color=ft.Colors.ON_SURFACE,
                                    text_align=ft.TextAlign.CENTER,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    "You have an active exam in progress. Leaving now will automatically submit your answered questions and generate your final score report.",
                                    size=12,
                                    color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                            border_radius=ft.BorderRadius.all(10),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY)),
                            content=ft.Row(
                                tight=True,
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                                    ft.Text(
                                        "Answers recorded & graded instantly",
                                        size=11,
                                        weight=ft.FontWeight.W_600,
                                        color=ft.Colors.PRIMARY,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                            ),
                        ),
                        ft.Container(height=4),
                        ft.Row(
                            spacing=8,
                            wrap=True,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.OutlinedButton(
                                    content=ft.Text("Continue Exam", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                                    height=38,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                        padding=ft.Padding.symmetric(horizontal=14, vertical=0),
                                        side=ft.BorderSide(1, ft.Colors.with_opacity(0.16, ft.Colors.ON_SURFACE)),
                                    ),
                                    on_click=_cancel,
                                ),
                                ft.ElevatedButton(
                                    content=ft.Row(
                                        tight=True,
                                        spacing=6,
                                        controls=[
                                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=15, color=ft.Colors.WHITE),
                                            ft.Text("Submit & Exit", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                        ],
                                    ),
                                    height=38,
                                    bgcolor=ft.Colors.ORANGE_600,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                        elevation=0,
                                        padding=ft.Padding.symmetric(horizontal=16, vertical=0),
                                    ),
                                    on_click=_submit_and_leave,
                                ),
                            ],
                        ),
                        ft.TextButton(
                            "Exit to Hub without submitting",
                            style=ft.ButtonStyle(
                                color=ft.Colors.GREY_500,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            ),
                            on_click=_exit_without_submit,
                        ),
                    ],
                ),
            ),
        )
        page.overlay.append(exit_dlg)
        exit_dlg.open = True
        page.update()

    def _on_exam_back():
        if state.get("exam_locked", True):
            _confirm_exit_exam()
        else:
            go_hub()

    def go_exam(questions: list, duration_seconds: int | None = None):
        state["on_hub"] = False
        _set_appbar("Exam Simulator", _on_exam_back)
        content_socket.content = _build_exam(questions, duration_seconds)
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # HUB — load + layout
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_hub():
        if not getattr(content_socket.content, "_is_loading", False):
            content_socket.content = _loading("Loading Study Hub…")
            page.update()
        try:
            results = await asyncio.gather(
                asyncio.wait_for(get_due_cards(token, _current_selected_ids()), timeout=6),
                asyncio.wait_for(get_materials(token),  timeout=6),
                asyncio.wait_for(get_subscription_status(token), timeout=6),
                asyncio.sleep(0.35),
                return_exceptions=True,
            )
            due_cards = results[0]
            materials = results[1]
            sub_status = results[2]
            if isinstance(due_cards, Exception): due_cards = []
            if isinstance(materials, Exception): materials = []
            
            # Inject Live Subscription Limits
            if not isinstance(sub_status, Exception) and isinstance(sub_status, dict):
                state["plan_id"]    = sub_status.get("plan_id") or "free"
                state["plan_label"] = sub_status.get("label") or "Free"
                state["mat_used"]   = sub_status.get("materials_used", 0)
                state["mat_lim"]    = sub_status.get("materials_limit", 5)
                state["gen_used"]   = sub_status.get("generations_used", 0)
                state["gen_lim"]    = sub_status.get("generations_limit", 10)

            state["materials"] = materials or []
            state["all_due_cards"] = list(due_cards or [])
            state["due_cards"] = due_cards or []

            # Update pinned quick counts
            due_cnt = len(due_cards or [])
            mat_cnt = len(materials or [])
            if "sidebar_due_text" in state and state["sidebar_due_text"]:
                state["sidebar_due_text"].value = f"{due_cnt} due"
                try:
                    state["sidebar_due_text"].update()
                except Exception:
                    pass
            if "sidebar_vault_text" in state and state["sidebar_vault_text"]:
                state["sidebar_vault_text"].value = f"{mat_cnt} items"
                try:
                    state["sidebar_vault_text"].update()
                except Exception:
                    pass

            _refresh_sidebar_materials()
            _refresh_plan_ui()

            state["on_hub"] = True
            try:
                content_socket.content = _build_hub(due_cards or [], materials or [])
            except Exception as ex:
                import traceback
                print(f"[_load_hub: _build_hub failed]: {ex}")
                traceback.print_exc()
                content_socket.content = _error_screen(
                    "Something went wrong loading your hub.",
                    lambda: page.run_task(_load_hub),
                )
            page.update()
            
        except Exception as ex:
            import traceback
            print(f"[_load_hub error]: {ex}")
            traceback.print_exc()
            # Even on error, render hub with cached/empty state instead of locking user out
            state["on_hub"] = True
            try:
                content_socket.content = _build_hub(state.get("due_cards", []), state.get("materials", []))
            except Exception as ex2:
                print(f"[_load_hub: _build_hub also failed]: {ex2}")
                traceback.print_exc()
                content_socket.content = _error_screen(
                    "Something went wrong loading your hub.",
                    lambda: page.run_task(_load_hub),
                )
            page.update()
    async def _start_flashcards(material_ids: list | None = None):
        content_socket.content = _loading("Fetching your due cards…")
        page.update()
        try:
            # NOTE: get_due_cards must accept an optional material_ids filter
            # (same convention as get_quiz_questions / get_exam_questions).
            # If src/requests/study.py's get_due_cards doesn't yet take a
            # second argument, add one there — otherwise this still pulls
            # every due card regardless of topic.
            cards = await asyncio.wait_for(
                get_due_cards(token, material_ids), timeout=15
            )
            if not cards:
                content_socket.content = _nothing_due_screen()
                page.update()
                return
            go_flashcards(cards)
        except Exception as ex:
            content_socket.content = _error_screen(
                f"Couldn't fetch cards ({type(ex).__name__}).",
                on_retry=lambda: page.run_task(_start_flashcards),
            )
            page.update()

    async def _start_quiz(material_ids: list | None = None):
        content_socket.content = _loading("Building your quiz…")
        page.update()
        try:
            questions = await asyncio.wait_for(
                get_quiz_questions(token, material_ids), timeout=15
            )
            go_quiz(questions or [])
        except Exception as ex:
            content_socket.content = _error_screen(
                f"Couldn't load quiz ({type(ex).__name__}).",
                on_retry=lambda: page.run_task(_start_quiz),
            )
            page.update()

    async def _start_exam(material_ids: list | None = None):
        content_socket.content = _loading("Setting up your exam…")
        page.update()
        try:
            result = await asyncio.wait_for(
                get_exam_questions(token, material_ids), timeout=15
            )
            # Prefer a server-provided time limit (e.g. get_exam_questions
            # returning {"questions": [...], "duration_seconds": N}) so the
            # timer reflects however the exam was actually configured,
            # instead of always falling back to a fixed local formula.
            if isinstance(result, dict):
                questions = result.get("questions") or []
                duration_seconds = result.get("duration_seconds")
            else:
                questions = result or []
                duration_seconds = None
            go_exam(questions, duration_seconds)
        except Exception as ex:
            content_socket.content = _error_screen(
                f"Couldn't load exam ({type(ex).__name__}).",
                on_retry=lambda: page.run_task(_start_exam),
            )
            page.update()

    def _nothing_due_screen() -> ft.Container:
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            padding=32,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    ft.Icon(ft.Icons.CELEBRATION_ROUNDED,
                            size=52, color=ft.Colors.ORANGE_300),
                    ft.Text("You're all caught up!", size=18,
                            weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                    ft.Text("No cards are due for review right now.\n"
                            "Check back later or add new material.",
                            size=13, color=ft.Colors.GREY_400,
                            text_align=ft.TextAlign.CENTER),
                    ft.ElevatedButton(
                        "Back to Hub", bgcolor=ft.Colors.PRIMARY,
                        color=ft.Colors.ON_PRIMARY, height=42,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10), elevation=0
                        ),
                        on_click=lambda _: go_hub(),
                    ),
                ],
            ),
        )
    # ─────────────────────────────────────────────────────────────────────────
    # SIDEBAR & GENERATION STATUS
    # ─────────────────────────────────────────────────────────────────────────
    def _create_generation_banner():
        is_gen = bool(state.get("generating_mats"))
        s_icon = ft.Icon(
            ft.Icons.AUTORENEW_ROUNDED if is_gen else ft.Icons.CHECK_CIRCLE_ROUNDED,
            color=ft.Colors.BLUE_700 if is_gen else ft.Colors.GREEN_700,
            size=13,
        )
        s_text = ft.Text(
            "AI: Generating..." if is_gen else "AI: Synced",
            size=10.5,
            weight=ft.FontWeight.W_700,
            color=ft.Colors.BLUE_800 if is_gen else ft.Colors.GREEN_800,
        )
        banner = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            bgcolor=ft.Colors.BLUE_50 if is_gen else ft.Colors.GREEN_50,
            border_radius=ft.BorderRadius.all(16),
            border=ft.Border.all(1, ft.Colors.BLUE_300 if is_gen else ft.Colors.GREEN_300),
            content=ft.Row(
                spacing=5,
                tight=True,
                controls=[s_icon, s_text],
            ),
        )
        state["generation_banner"] = banner
        state["gen_status_icon"] = s_icon
        state["gen_status_text"] = s_text
        return banner

    async def _poll_generation_status():
        while True:
            await asyncio.sleep(4)
            
            # Kill the ghost loop if user leaves page
            if page.route != "/self-study":
                break

            try:
                mats_to_check = list(state.get("generating_mats", set()))
                is_generating_anything = False
                
                if mats_to_check:
                    print(f"\n[POLLER] 📡 Checking {len(mats_to_check)} materials: {mats_to_check}")
                    done_mats = []
                    
                    for mat_id in mats_to_check:
                        raw_result = await check_generation_status(token, mat_id)
                        
                        is_active = False
                        if isinstance(raw_result, dict):
                            is_active = raw_result.get("status") == "processing"
                            
                        if is_active:
                            is_generating_anything = True
                            state["poll_strikes"][mat_id] = 0
                        else:
                            strikes = state["poll_strikes"].get(mat_id, 0) + 1
                            if strikes >= 3:
                                done_mats.append(mat_id)
                                state["poll_strikes"].pop(mat_id, None)
                            else:
                                state["poll_strikes"][mat_id] = strikes
                                is_generating_anything = True
                            
                    for m in done_mats:
                        state["generating_mats"].discard(m)
                        
                    # --- LIVE SYNC THE DASHBOARD WHEN GENERATION FINISHES ---
                    if done_mats:
                        try:
                            live_cards = await get_due_cards(token, _current_selected_ids())
                            new_count = len(live_cards)
                            
                            if state.get("sidebar_due_text") and state["sidebar_due_text"].page:
                                state["sidebar_due_text"].value = f"{new_count} due"
                                state["sidebar_due_text"].update()

                            if state.get("live_due_text") and state["live_due_text"].page:
                                state["live_due_text"].value = str(new_count)
                                if state.get("live_streak_text"):
                                    state["live_streak_text"].value = "Keep your streak going! 🔥" if new_count > 0 else "All caught up for today! ❄️"
                                if state.get("live_fc_pill"):
                                    state["live_fc_pill"].value = f"{new_count} due" if new_count > 0 else "All caught up"
                                    
                                state["live_due_text"].update()
                                if state.get("live_streak_text"): state["live_streak_text"].update()
                                if state.get("live_fc_pill"): state["live_fc_pill"].update()
                        except Exception as ex:
                            print(f"[POLLER] ❌ Error syncing live cards: {ex}")
                else:
                    pass
                
                # --- UPDATE THE UI ---
                banner = state.get("generation_banner")
                s_icon = state.get("gen_status_icon")
                s_text = state.get("gen_status_text")
                if banner and s_icon and s_text:
                    if is_generating_anything:
                        banner.bgcolor = ft.Colors.BLUE_50
                        banner.border = ft.Border.all(1, ft.Colors.BLUE_300)
                        s_icon.name = ft.Icons.AUTORENEW_ROUNDED
                        s_icon.color = ft.Colors.BLUE_700
                        s_text.value = "AI: Generating..."
                        s_text.color = ft.Colors.BLUE_800
                    else:
                        banner.bgcolor = ft.Colors.GREEN_50
                        banner.border = ft.Border.all(1, ft.Colors.GREEN_300)
                        s_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                        s_icon.color = ft.Colors.GREEN_700
                        s_text.value = "AI: Synced"
                        s_text.color = ft.Colors.GREEN_800
                
                    if banner.page:
                        banner.update() 
                    
            except Exception as e:
                if "Control must be added to the page first" not in str(e):
                    print(f"[POLLER] ❌ Error during polling: {type(e).__name__} - {e}")

    # ── hub layout ────────────────────────────────────────────────────────────
    def _build_hub(due_cards: list, materials: list) -> ft.Column:
        due_count = len(due_cards)

        is_mobile = bool(page.width and page.width < 768)
        is_small = bool(page.width and page.width < 450)

        # Controls stored in state for live poller updates
        state["live_due_text"] = ft.Text(
            str(due_count),
            size=20 if is_small else (21 if is_mobile else 24),
            weight=ft.FontWeight.W_800,
            color=ft.Colors.WHITE,
        )
        state["live_streak_text"] = ft.Text(
            "Keep your streak going! 🔥" if due_count > 0 else "All caught up for today! ❄️",
            size=12 if is_small else (12.5 if is_mobile else 14),
            weight=ft.FontWeight.W_600,
            color=ft.Colors.with_opacity(0.92, ft.Colors.WHITE),
        )

        hero_title = ft.Text(
            "Smart Study Command Center",
            size=17 if is_small else (18.5 if is_mobile else 21),
            weight=ft.FontWeight.W_800,
            color=ft.Colors.WHITE,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        hero_action_icon = ft.Icon(
            ft.Icons.PLAY_ARROW_ROUNDED if due_count > 0 else ft.Icons.BOLT_ROUNDED,
            size=16 if is_mobile else 18,
            color=ft.Colors.PRIMARY,
        )
        hero_action_label = ft.Text(
            f"Review {due_count} Due Cards" if due_count > 0 else "Practice Quick Quiz",
            size=12 if is_small else (12.5 if is_mobile else 13),
            weight=ft.FontWeight.W_700,
            color=ft.Colors.PRIMARY,
        )
        hero_action_btn = ft.ElevatedButton(
            content=ft.Row(
                spacing=6,
                tight=True,
                controls=[hero_action_icon, hero_action_label],
            ),
            bgcolor=ft.Colors.WHITE,
            height=36 if is_mobile else 38,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=0,
                padding=ft.Padding.symmetric(horizontal=14 if is_mobile else 16, vertical=0),
            ),
            on_click=lambda _: page.run_task(
                _start_flashcards if due_count > 0 else _start_quiz,
                _current_selected_ids(),
            ),
        )

        badge_circle_dim = 42 if is_small else (44 if is_mobile else 50)
        queue_circle = ft.Container(
            width=badge_circle_dim,
            height=badge_circle_dim,
            bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.WHITE),
            border_radius=ft.BorderRadius.all(badge_circle_dim // 2),
            alignment=ft.Alignment.CENTER,
            content=state["live_due_text"],
        )

        queue_title_text = ft.Text(
            "Review Queue",
            size=12 if is_small else (12.5 if is_mobile else 13),
            weight=ft.FontWeight.W_700,
            color=ft.Colors.WHITE,
        )
        queue_subtitle_text = ft.Text(
            f"{len(materials)} materials active",
            size=10.5 if is_small else 11,
            color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE),
        )

        queue_card = ft.Container(
            padding=ft.Padding.symmetric(
                horizontal=12 if is_small else (14 if is_mobile else 16),
                vertical=10 if is_small else (10 if is_mobile else 12),
            ),
            bgcolor=ft.Colors.with_opacity(0.16, ft.Colors.WHITE),
            border_radius=ft.BorderRadius.all(13 if is_mobile else 14),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
            content=ft.Row(
                spacing=12 if is_mobile else 14,
                tight=True,
                controls=[
                    queue_circle,
                    ft.Column(
                        spacing=2,
                        tight=True,
                        controls=[
                            queue_title_text,
                            queue_subtitle_text,
                        ],
                    ),
                ],
            ),
        )

        queue_col_container = ft.Container(
            col={"xs": 12, "md": 4},
            alignment=ft.Alignment.CENTER_LEFT if is_mobile else ft.Alignment.CENTER_RIGHT,
            content=queue_card,
        )

        top_engine_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=9 if is_small else 10, vertical=4),
            bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.WHITE),
            border_radius=ft.BorderRadius.all(12),
            content=ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=12 if is_small else 13, color=ft.Colors.WHITE),
                    ft.Text(
                        "SM-2 COGNITIVE ENGINE",
                        size=9.5 if is_small else 10,
                        weight=ft.FontWeight.W_800,
                        color=ft.Colors.WHITE,
                    ),
                ],
            ),
        )

        top_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
            spacing=8,
            run_spacing=8,
            controls=[
                top_engine_badge,
                _create_generation_banner(),
            ],
        )

        hero_banner = ft.Container(
            border_radius=ft.BorderRadius.all(14 if is_small else (16 if is_mobile else 18)),
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.PRIMARY,
                    ft.Colors.SECONDARY,
                ],
            ),
            padding=ft.Padding.symmetric(
                horizontal=13 if is_small else (16 if is_mobile else 22),
                vertical=13 if is_small else (16 if is_mobile else 22),
            ),
            shadow=ft.BoxShadow(
                blur_radius=12 if is_mobile else 16,
                color=ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY),
                offset=ft.Offset(0, 4 if is_mobile else 6),
            ),
            content=ft.Column(
                spacing=12 if is_mobile else 16,
                controls=[
                    top_row,
                    ft.ResponsiveRow(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        run_spacing=12,
                        controls=[
                            ft.Container(
                                col={"xs": 12, "md": 8},
                                content=ft.Column(
                                    spacing=5 if is_mobile else 6,
                                    controls=[
                                        hero_title,
                                        state["live_streak_text"],
                                        ft.Container(height=2 if is_mobile else 4),
                                        hero_action_btn,
                                    ],
                                ),
                            ),
                            queue_col_container,
                        ],
                    ),
                ],
            ),
        )

        def _update_hero_responsive():
            cur_mobile = bool(page.width and page.width < 768)
            cur_small = bool(page.width and page.width < 450)

            hero_banner.padding = ft.Padding.symmetric(
                horizontal=13 if cur_small else (16 if cur_mobile else 22),
                vertical=13 if cur_small else (16 if cur_mobile else 22),
            )
            hero_banner.border_radius = ft.BorderRadius.all(14 if cur_small else (16 if cur_mobile else 18))
            if hero_banner.shadow:
                hero_banner.shadow.blur_radius = 12 if cur_mobile else 16
                hero_banner.shadow.offset = ft.Offset(0, 4 if cur_mobile else 6)

            hero_title.size = 17 if cur_small else (18.5 if cur_mobile else 21)
            state["live_streak_text"].size = 12 if cur_small else (12.5 if cur_mobile else 14)
            state["live_due_text"].size = 20 if cur_small else (21 if cur_mobile else 24)

            hero_action_icon.size = 16 if cur_mobile else 18
            hero_action_label.size = 12 if cur_small else (12.5 if cur_mobile else 13)
            hero_action_btn.height = 36 if cur_mobile else 38
            if hero_action_btn.style:
                hero_action_btn.style.padding = ft.Padding.symmetric(
                    horizontal=14 if cur_mobile else 16, vertical=0
                )

            new_circle_dim = 42 if cur_small else (44 if cur_mobile else 50)
            queue_circle.width = new_circle_dim
            queue_circle.height = new_circle_dim
            queue_circle.border_radius = ft.BorderRadius.all(new_circle_dim // 2)

            queue_title_text.size = 12 if cur_small else (12.5 if cur_mobile else 13)
            queue_subtitle_text.size = 10.5 if cur_small else 11

            queue_card.padding = ft.Padding.symmetric(
                horizontal=12 if cur_small else (14 if cur_mobile else 16),
                vertical=10 if cur_small else (10 if cur_mobile else 12),
            )

            queue_col_container.alignment = (
                ft.Alignment.CENTER_LEFT if cur_mobile else ft.Alignment.CENTER_RIGHT
            )

        state["update_hero_responsive"] = _update_hero_responsive

        sel_count = len(state["selected_mat_ids"])

        def _clear_filter_and_rebuild(e):
            page.run_task(_sync_material_selection, clear_all=True)

        if sel_count > 0:
            context_scope_bar = ft.Container(
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.PRIMARY)),
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                content=ft.ResponsiveRow(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    run_spacing=8,
                    controls=[
                        ft.Container(
                            col={"xs": 12, "sm": 8},
                            content=ft.Row(
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        width=28, height=28,
                                        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY),
                                        border_radius=ft.BorderRadius.all(14),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(ft.Icons.FILTER_LIST_ROUNDED, color=ft.Colors.PRIMARY, size=16),
                                    ),
                                    ft.Column(
                                        spacing=1,
                                        tight=True,
                                        controls=[
                                            ft.Text(
                                                f"Focus Mode: {sel_count} material{'s' if sel_count > 1 else ''} selected",
                                                size=12.5,
                                                weight=ft.FontWeight.W_700,
                                                color=ft.Colors.PRIMARY,
                                            ),
                                            ft.Text(
                                                "Practice sessions are scoped to your selected materials.",
                                                size=11,
                                                color=ft.Colors.with_opacity(0.8, ft.Colors.PRIMARY),
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 4},
                            alignment=ft.Alignment.CENTER_RIGHT if page.width and page.width >= 600 else ft.Alignment.CENTER_LEFT,
                            content=ft.TextButton(
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.ALL_INCLUSIVE_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                                        ft.Text("Use All Materials", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                    ],
                                ),
                                style=ft.ButtonStyle(
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                ),
                                on_click=_clear_filter_and_rebuild,
                            ),
                        ),
                    ],
                ),
            )
        else:
            context_scope_bar = ft.Container(
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.symmetric(horizontal=14, vertical=9),
                content=ft.ResponsiveRow(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    run_spacing=8,
                    controls=[
                        ft.Container(
                            col={"xs": 12, "sm": 8},
                            content=ft.Row(
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.ALL_INCLUSIVE_ROUNDED, color=ft.Colors.GREY_500, size=16),
                                    ft.Text(
                                        f"Scope: Global Knowledge Vault ({len(materials)} material{'s' if len(materials) != 1 else ''} active)",
                                        size=12,
                                        weight=ft.FontWeight.W_600,
                                        color=ft.Colors.ON_SURFACE,
                                    ),
                                ],
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 4},
                            alignment=ft.Alignment.CENTER_RIGHT if page.width and page.width >= 600 else ft.Alignment.CENTER_LEFT,
                            content=ft.TextButton(
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.TUNE_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                                        ft.Text("Filter Topics", size=11.5, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
                                    ],
                                ),
                                on_click=lambda _: _toggle_sidebar(None),
                            ),
                        ),
                    ],
                ),
            )

        def bento_card(
            col_spec,
            icon,
            title,
            subtitle,
            badge_label,
            badge_bg,
            badge_fg,
            description,
            feature_tags,
            accent_color,
            cta_text,
            on_tap,
        ):
            badge_control = _pill(badge_label, badge_bg, badge_fg)
            if title == "Flashcards":
                state["live_fc_pill"] = badge_control.content

            tag_controls = [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    border_radius=ft.BorderRadius.all(6),
                    content=ft.Text(tag, size=9.5, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600),
                )
                for tag in feature_tags
            ]

            return ft.Container(
                col=col_spec,
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(16),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(18),
                ink=True,
                on_click=lambda _: on_tap(),
                shadow=ft.BoxShadow(
                    blur_radius=12,
                    color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                    offset=ft.Offset(0, 4),
                ),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=44, height=44,
                                    bgcolor=ft.Colors.with_opacity(0.12, accent_color),
                                    border_radius=ft.BorderRadius.all(12),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(icon, color=accent_color, size=22),
                                ),
                                badge_control,
                            ],
                        ),
                        ft.Column(
                            spacing=3,
                            tight=True,
                            controls=[
                                ft.Text(title, size=16, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                ft.Text(subtitle, size=11, weight=ft.FontWeight.W_600, color=accent_color),
                            ],
                        ),
                        ft.Text(
                            description,
                            size=11.5,
                            color=ft.Colors.GREY_500,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Row(
                            spacing=6,
                            wrap=True,
                            controls=tag_controls,
                        ),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text(cta_text, size=12, weight=ft.FontWeight.W_700, color=accent_color),
                                ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16, color=accent_color),
                            ],
                        ),
                    ],
                ),
            )

        study_modes_grid = ft.ResponsiveRow(
            spacing=14,
            run_spacing=14,
            controls=[
                bento_card(
                    col_spec={"xs": 12, "sm": 6, "md": 4},
                    icon=ft.Icons.STYLE_ROUNDED,
                    title="Flashcards",
                    subtitle="Adaptive Spaced Repetition",
                    badge_label=f"{due_count} due" if due_count else "All caught up",
                    badge_bg=ft.Colors.PURPLE_50,
                    badge_fg=ft.Colors.PURPLE_700,
                    description="SuperMemo-2 system schedules reviews based on your recall accuracy.",
                    feature_tags=["SM-2 Engine", "Active Recall"],
                    accent_color=ft.Colors.PURPLE_500,
                    cta_text="Review Deck",
                    on_tap=lambda: page.run_task(_start_flashcards, _current_selected_ids()),
                ),
                bento_card(
                    col_spec={"xs": 12, "sm": 6, "md": 4},
                    icon=ft.Icons.BOLT_ROUNDED,
                    title="Quick Quiz",
                    subtitle="Bite-Sized Comprehension",
                    badge_label="Instant Feedback",
                    badge_bg=ft.Colors.TEAL_50,
                    badge_fg=ft.Colors.TEAL_700,
                    description="Targeted drills with explanations and instant rationale breakdown.",
                    feature_tags=["Instant Check", "Low Stakes"],
                    accent_color=ft.Colors.TEAL_600,
                    cta_text="Launch Quiz",
                    on_tap=lambda: page.run_task(_start_quiz, _current_selected_ids()),
                ),
                bento_card(
                    col_spec={"xs": 12, "sm": 12, "md": 4},
                    icon=ft.Icons.TIMER_OUTLINED,
                    title="Exam Simulator",
                    subtitle="Simulated Test Environment",
                    badge_label="Timed Mock",
                    badge_bg=ft.Colors.ORANGE_50,
                    badge_fg=ft.Colors.ORANGE_700,
                    description="Full-length timed exam simulation with comprehensive scoring and result breakdown.",
                    feature_tags=["Timed Mode", "Score Report"],
                    accent_color=ft.Colors.ORANGE_600,
                    cta_text="Begin Exam",
                    on_tap=lambda: page.run_task(_start_exam, _current_selected_ids()),
                ),
            ],
        )

        studio_card = ft.Container(
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(18),
            shadow=ft.BoxShadow(
                blur_radius=10,
                color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.ResponsiveRow(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                run_spacing=12,
                controls=[
                    ft.Container(
                        col={"xs": 12, "md": 7},
                        content=ft.Row(
                            spacing=14,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=44, height=44,
                                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                                    border_radius=ft.BorderRadius.all(12),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                                ),
                                ft.Column(
                                    spacing=3,
                                    tight=True,
                                    controls=[
                                        ft.Text("Supercharge Your Study Stack", size=14.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                        ft.Text(
                                            "Add notes, slides, or docs to generate customized study materials",
                                            size=11.5,
                                            color=ft.Colors.GREY_500,
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "md": 5},
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.END if page.width and page.width >= 768 else ft.MainAxisAlignment.START,
                            spacing=8,
                            wrap=True,
                            controls=[
                                ft.OutlinedButton(
                                    content=ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                                            ft.Text("Upload Material", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                        ],
                                    ),
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                        side=ft.BorderSide(1, ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)),
                                        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                                    ),
                                    on_click=lambda _: _open_upload_modal(),
                                ),
                                ft.ElevatedButton(
                                    content=ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.BOLT_ROUNDED, size=16, color=ft.Colors.WHITE),
                                            ft.Text("Generate AI Pack", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                        ],
                                    ),
                                    bgcolor=ft.Colors.PRIMARY,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                        elevation=0,
                                        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                                    ),
                                    on_click=lambda _: _open_generate_panel(),
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        recent_materials = materials[:6] if materials else []

        if not materials:
            vault_content = ft.Container(
                bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                border_radius=ft.BorderRadius.all(14),
                padding=ft.Padding.symmetric(horizontal=20, vertical=28),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Container(
                            width=46, height=46,
                            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                            border_radius=ft.BorderRadius.all(12),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, color=ft.Colors.PRIMARY, size=24),
                        ),
                        ft.Text("Your Knowledge Vault is Empty", size=14, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                        ft.Text(
                            "Upload lecture slides, notes, or web articles to generate study decks and quizzes.",
                            size=12,
                            color=ft.Colors.GREY_500,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=4),
                        ft.ElevatedButton(
                            content=ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.ADD_ROUNDED, size=15, color=ft.Colors.WHITE),
                                    ft.Text("Upload First Material", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                ],
                            ),
                            bgcolor=ft.Colors.PRIMARY,
                            height=36,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=9), elevation=0),
                            on_click=lambda _: _open_upload_modal(),
                        ),
                    ],
                ),
            )
        else:
            vault_cards = []
            for mat in recent_materials:
                mid = mat.get("id")
                if mid is None:
                    continue
                mtitle = mat.get("title") or "Untitled Document"
                display_title = format_material_title(mtitle)
                stype = (mat.get("source_type") or "text").lower()

                if "pdf" in stype or mtitle.lower().endswith(".pdf"):
                    m_icon = ft.Icons.PICTURE_AS_PDF_ROUNDED
                    m_color = ft.Colors.RED_400
                    m_tag = "PDF"
                elif "url" in stype:
                    m_icon = ft.Icons.LINK_ROUNDED
                    m_color = ft.Colors.TEAL_400
                    m_tag = "URL"
                else:
                    m_icon = ft.Icons.DESCRIPTION_ROUNDED
                    m_color = ft.Colors.BLUE_400
                    m_tag = "NOTES"

                is_in_focus = mid in state["selected_mat_ids"]

                def _toggle_mat_from_hub(e, target_id=mid):
                    page.run_task(_sync_material_selection, target_id=target_id)

                mat_card = ft.Container(
                    col={"xs": 12, "sm": 6, "md": 4},
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY) if is_in_focus else ft.Colors.SURFACE,
                    border_radius=ft.BorderRadius.all(14),
                    border=ft.Border.all(
                        1.5 if is_in_focus else 1,
                        ft.Colors.PRIMARY if is_in_focus else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                    ),
                    padding=ft.Padding.all(14),
                    shadow=ft.BoxShadow(
                        blur_radius=8,
                        color=ft.Colors.with_opacity(0.06 if is_in_focus else 0.03, ft.Colors.PRIMARY if is_in_focus else ft.Colors.BLACK),
                        offset=ft.Offset(0, 2),
                    ),
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Container(
                                ink=True,
                                border_radius=ft.BorderRadius.all(8),
                                on_click=_toggle_mat_from_hub,
                                tooltip="Click to toggle material selection",
                                content=ft.Column(
                                    spacing=8,
                                    controls=[
                                        ft.Row(
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            controls=[
                                                ft.Row(
                                                    spacing=8,
                                                    tight=True,
                                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                    controls=[
                                                        ft.Container(
                                                            width=30, height=30,
                                                            bgcolor=ft.Colors.with_opacity(0.12, m_color),
                                                            border_radius=ft.BorderRadius.all(8),
                                                            alignment=ft.Alignment.CENTER,
                                                            content=ft.Icon(m_icon, color=m_color, size=16),
                                                        ),
                                                        ft.Container(
                                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                            bgcolor=ft.Colors.with_opacity(0.08, m_color),
                                                            border_radius=ft.BorderRadius.all(6),
                                                            content=ft.Text(m_tag, size=9, weight=ft.FontWeight.W_700, color=m_color),
                                                        ),
                                                    ],
                                                ),
                                                ft.IconButton(
                                                    icon=ft.Icons.CHECK_CIRCLE_ROUNDED if is_in_focus else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                                                    icon_color=ft.Colors.PRIMARY if is_in_focus else ft.Colors.GREY_400,
                                                    icon_size=18,
                                                    tooltip="Toggle in Focus Mode",
                                                    on_click=_toggle_mat_from_hub,
                                                ),
                                            ],
                                        ),
                                        ft.Text(
                                            display_title,
                                            size=12.5,
                                            weight=ft.FontWeight.W_700,
                                            color=ft.Colors.PRIMARY if is_in_focus else ft.Colors.ON_SURFACE,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                    ],
                                ),
                            ),
                            ft.Row(
                                spacing=6,
                                wrap=True,
                                controls=[
                                    ft.OutlinedButton(
                                        content=ft.Row(
                                            spacing=4, tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.STYLE_ROUNDED, size=13, color=ft.Colors.PURPLE_500),
                                                ft.Text("Cards", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.PURPLE_500),
                                            ],
                                        ),
                                        height=30,
                                        style=ft.ButtonStyle(
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=0),
                                            shape=ft.RoundedRectangleBorder(radius=7),
                                            side=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.PURPLE_500)),
                                        ),
                                        on_click=lambda _, target_id=mid: page.run_task(_start_flashcards, [target_id]),
                                    ),
                                    ft.OutlinedButton(
                                        content=ft.Row(
                                            spacing=4, tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.BOLT_ROUNDED, size=13, color=ft.Colors.TEAL_600),
                                                ft.Text("Quiz", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.TEAL_600),
                                            ],
                                        ),
                                        height=30,
                                        style=ft.ButtonStyle(
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=0),
                                            shape=ft.RoundedRectangleBorder(radius=7),
                                            side=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.TEAL_600)),
                                        ),
                                        on_click=lambda _, target_id=mid: page.run_task(_start_quiz, [target_id]),
                                    ),
                                    ft.OutlinedButton(
                                        content=ft.Row(
                                            spacing=4, tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.TIMER_OUTLINED, size=13, color=ft.Colors.ORANGE_500),
                                                ft.Text("Exam", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ORANGE_500),
                                            ],
                                        ),
                                        height=30,
                                        style=ft.ButtonStyle(
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=0),
                                            shape=ft.RoundedRectangleBorder(radius=7),
                                            side=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.ORANGE_500)),
                                        ),
                                        on_click=lambda _, target_id=mid: page.run_task(_start_exam, [target_id]),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
                vault_cards.append(mat_card)

            vault_content = ft.ResponsiveRow(
                spacing=12,
                run_spacing=12,
                controls=vault_cards,
            )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(
                        horizontal=14 if (page.width and page.width < 500) else 24,
                        vertical=18,
                    ),
                    content=ft.Column(
                        spacing=18,
                        controls=[
                            hero_banner,
                            context_scope_bar,
                            _section_label("STUDY MODES"),
                            study_modes_grid,
                            _section_label("CREATIVE STUDIO"),
                            studio_card,
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    _section_label("MY STUDY VAULT"),
                                    ft.TextButton(
                                        "Manage in sidebar →",
                                        style=ft.ButtonStyle(
                                            padding=ft.Padding.symmetric(horizontal=4, vertical=0),
                                            color=ft.Colors.PRIMARY,
                                        ),
                                        on_click=lambda _: _toggle_sidebar(None),
                                    ) if len(materials) > 0 else ft.Container(),
                                ],
                            ),
                            vault_content,
                            ft.Container(height=32),
                        ],
                    ),
                ),
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # UPLOAD MODAL
    # ─────────────────────────────────────────────────────────────────────────
    def _open_upload_modal():
        selected_file_bytes = None
        selected_file_name  = None

        at_limit = state["mat_lim"] is not None and state["mat_used"] >= state["mat_lim"]

        title_field = ft.TextField(
            label="Topic Title *",
            hint_text="e.g. Biology Ch. 4 - Cell Division",
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            expand= True
        )

        text_field = ft.TextField(
            label="Paste Notes / Content",
            hint_text="Paste lecture summaries, transcriptions, notes, or articles...",
            multiline=True,
            min_lines=5,
            max_lines=9,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            expand= True
        )

        error_text  = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False)
        status_text = ft.Text("", color=ft.Colors.TEAL_600, size=12, visible=False)

        error_box = ft.Container(
            visible=False,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.RED_400),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.RED_400)),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_400, size=16),
                    error_text,
                ],
            ),
        )

        status_box = ft.Container(
            visible=False,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.TEAL_500),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.TEAL_500)),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.TEAL_600, size=16),
                    status_text,
                ],
            ),
        )

        limit_warning = ft.Container(
            visible=at_limit,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.RED_400),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.RED_400)),
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=ft.Colors.RED_400, size=18),
                    ft.Text(
                        "Limit Reached! Upgrade your plan to add more materials.",
                        size=11.5,
                        color=ft.Colors.RED_700,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
            ),
        )

        def remove_selected_file(e=None):
            nonlocal selected_file_bytes, selected_file_name
            selected_file_bytes = None
            selected_file_name = None
            update_dropzone_ui()
            page.update()

        file_dropzone = ft.Container()

        def update_dropzone_ui():
            if selected_file_bytes and selected_file_name:
                size_kb = len(selected_file_bytes) / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
                is_pdf = selected_file_name.lower().endswith(".pdf")
                fmt_tag = "PDF" if is_pdf else ("TXT" if selected_file_name.lower().endswith(".txt") else "DOC")
                fmt_color = ft.Colors.RED_400 if is_pdf else ft.Colors.BLUE_400
                fmt_icon = ft.Icons.PICTURE_AS_PDF_ROUNDED if is_pdf else ft.Icons.DESCRIPTION_ROUNDED

                file_dropzone.content = ft.Container(
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
                    border=ft.Border.all(1.5, ft.Colors.PRIMARY),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=12,
                                tight=True,
                                controls=[
                                    ft.Container(
                                        width=36, height=36,
                                        bgcolor=ft.Colors.with_opacity(0.12, fmt_color),
                                        border_radius=8,
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(fmt_icon, color=fmt_color, size=20),
                                    ),
                                    ft.Column(
                                        spacing=2,
                                        tight=True,
                                        controls=[
                                            ft.Text(
                                                selected_file_name,
                                                size=12.5,
                                                weight=ft.FontWeight.W_700,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                            ft.Row(
                                                spacing=6,
                                                tight=True,
                                                controls=[
                                                    ft.Container(
                                                        padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                                                        bgcolor=ft.Colors.with_opacity(0.1, fmt_color),
                                                        border_radius=4,
                                                        content=ft.Text(fmt_tag, size=8.5, weight=ft.FontWeight.W_800, color=fmt_color),
                                                    ),
                                                    ft.Text(size_str, size=10.5, color=ft.Colors.GREY_500),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE_ROUNDED,
                                icon_size=18,
                                icon_color=ft.Colors.GREY_500,
                                tooltip="Remove file",
                                on_click=remove_selected_file,
                            ),
                        ],
                    ),
                )
            else:
                file_dropzone.content = ft.Container(
                    border_radius=12,
                    border=ft.Border.all(1.5, ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY)),
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=22),
                    ink=True,
                    on_click=pick_file,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Container(
                                width=44, height=44,
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                                border_radius=12,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.CLOUD_UPLOAD_ROUNDED, color=ft.Colors.PRIMARY, size=24),
                            ),
                            ft.Text("Click to browse document", size=13, weight=ft.FontWeight.W_700),
                            ft.Text("PDF, TXT, or Markdown supported", size=11, color=ft.Colors.GREY_500),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=6,
                                controls=[
                                    ft.Container(bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED_400), border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=2), content=ft.Text("PDF", size=9, weight=ft.FontWeight.W_800, color=ft.Colors.RED_600)),
                                    ft.Container(bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_400), border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=2), content=ft.Text("TXT", size=9, weight=ft.FontWeight.W_800, color=ft.Colors.BLUE_600)),
                                    ft.Container(bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.TEAL_400), border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=2), content=ft.Text("MD", size=9, weight=ft.FontWeight.W_800, color=ft.Colors.TEAL_600)),
                                ],
                            ),
                        ],
                    ),
                )

        async def pick_file(e):
            nonlocal selected_file_bytes, selected_file_name
            try:
                files = await ft.FilePicker().pick_files(
                    allow_multiple=False,
                    allowed_extensions=["pdf", "txt", "md"],
                    with_data=True,
                )
                if files:
                    selected_file_bytes = files[0].bytes
                    selected_file_name  = files[0].name
                    if not (title_field.value or "").strip():
                        cleaned_name = selected_file_name
                        for ext in [".pdf", ".txt", ".md"]:
                            if cleaned_name.lower().endswith(ext):
                                cleaned_name = cleaned_name[:-len(ext)]
                        title_field.value = cleaned_name.replace("_", " ").title()
                    error_box.visible = False
                    update_dropzone_ui()
                    page.update()
            except Exception:
                error_text.value = "File picker failed — paste text instead."
                error_box.visible = True
                page.update()

        update_dropzone_ui()

        # Tab Segmented Switcher (File vs Text)
        mode_state = {"tab": "file"}

        tab_file_icon = ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, size=15, color=ft.Colors.PRIMARY)
        tab_file_text = ft.Text("Upload File", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY)
        tab_file_btn = ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(vertical=8),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
            alignment=ft.Alignment.CENTER,
            ink=True,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=6,
                controls=[tab_file_icon, tab_file_text],
            ),
        )

        tab_text_icon = ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=16, color=ft.Colors.GREY_500)
        tab_text_text = ft.Text("Paste Text", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_500)
        tab_text_btn = ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(vertical=8),
            border_radius=8,
            bgcolor=ft.Colors.TRANSPARENT,
            alignment=ft.Alignment.CENTER,
            ink=True,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=6,
                controls=[tab_text_icon, tab_text_text],
            ),
        )

        file_section = ft.Container(content=file_dropzone, visible=True)
        text_section = ft.Container(content=text_field, visible=False)

        def switch_mode(tab: str):
            mode_state["tab"] = tab
            is_file = tab == "file"
            tab_file_btn.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_file else ft.Colors.TRANSPARENT
            tab_file_text.color = ft.Colors.PRIMARY if is_file else ft.Colors.GREY_500
            tab_file_text.weight = ft.FontWeight.W_700 if is_file else ft.FontWeight.W_500
            tab_file_icon.color = ft.Colors.PRIMARY if is_file else ft.Colors.GREY_500

            tab_text_btn.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if not is_file else ft.Colors.TRANSPARENT
            tab_text_text.color = ft.Colors.PRIMARY if not is_file else ft.Colors.GREY_500
            tab_text_text.weight = ft.FontWeight.W_700 if not is_file else ft.FontWeight.W_500
            tab_text_icon.color = ft.Colors.PRIMARY if not is_file else ft.Colors.GREY_500

            file_section.visible = is_file
            text_section.visible = not is_file
            page.update()

        tab_file_btn.on_click = lambda _: switch_mode("file")
        tab_text_btn.on_click = lambda _: switch_mode("text")

        mode_switcher = ft.Container(
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=4,
            content=ft.Row(spacing=4, controls=[tab_file_btn, tab_text_btn]),
        )

        async def submit_upload(e):
            nonlocal selected_file_bytes, selected_file_name
            if at_limit:
                return
            if not (title_field.value or "").strip():
                error_text.value = "Please give this material a title."
                error_box.visible = True
                page.update()
                return
            if not (text_field.value or "").strip() and not selected_file_bytes:
                error_text.value = "Please paste notes or upload a file."
                error_box.visible = True
                page.update()
                return

            error_box.visible  = False
            status_box.visible = False
            submit_btn.disabled = True
            submit_btn.content  = ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=8,
                controls=[
                    ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY, stroke_width=2),
                    ft.Text("Uploading...", color=ft.Colors.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600),
                ],
            )
            page.update()

            try:
                result = await asyncio.wait_for(
                    upload_material(
                        token,
                        title=title_field.value.strip(),
                        text=text_field.value or None,
                        file_bytes=selected_file_bytes,
                        file_name=selected_file_name,
                    ),
                    timeout=30,
                )
                cards_count = len(result.get("cards", []))
                status_text.value = "✓ Uploaded! Go ahead and start studying!"
                status_box.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text(
                    "Upload Another",
                    color=ft.Colors.ON_PRIMARY,
                    size=13,
                    weight=ft.FontWeight.W_600,
                )

                new_mat = {
                    "id": result.get("material_id", f"mat_{len(state['materials'])+1}"),
                    "title": title_field.value.strip(),
                    "source_type": "pdf" if selected_file_bytes else "text",
                    "created_at": "2025-08-27",
                }
                state["materials"].append(new_mat)
                state["mat_used"] += 1
                
                if state.get("sidebar_vault_text"):
                    state["sidebar_vault_text"].value = f"{len(state['materials'])} items"
                    try:
                        state["sidebar_vault_text"].update()
                    except Exception:
                        pass

                _refresh_sidebar_materials()
                _refresh_plan_ui()

                title_field.value   = ""
                text_field.value    = ""
                selected_file_bytes = None
                selected_file_name  = None
                update_dropzone_ui()
                page.update()

            except asyncio.TimeoutError:
                error_text.value = "Upload timed out. Check your connection."
                error_box.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text("Upload", color=ft.Colors.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600)
                page.update()
            except Exception as ex:
                error_text.value = f"Upload failed ({type(ex).__name__})."
                error_box.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text("Upload", color=ft.Colors.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600)
                page.update()

        submit_btn = ft.ElevatedButton(
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=6,
                controls=[
                    ft.Icon(ft.Icons.UPLOAD_ROUNDED, size=16, color=ft.Colors.WHITE),
                    ft.Text("Upload Material", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_700),
                ],
            ),
            bgcolor=ft.Colors.PRIMARY,
            expand=True,
            height=44,
            disabled=at_limit,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=0,
            ),
            on_click=submit_upload,
        )

        def close_modal(e):
            modal.open = False
            page.update()

        up_w = min(page.width - 32, 480) if page.width else 440
        up_h = min(page.height - 180, 480) if page.height else 440
        modal = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Container(
                                width=34, height=34,
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                                border_radius=ft.BorderRadius.all(10),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                controls=[
                                    ft.Text(
                                        "Upload Study Material",
                                        size=15.5,
                                        weight=ft.FontWeight.W_700,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        "Add notes or docs to your knowledge vault",
                                        size=11,
                                        color=ft.Colors.GREY_500,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        icon_color=ft.Colors.GREY_400,
                        on_click=close_modal,
                    ),
                ],
            ),
            content=ft.Container(
                width=up_w,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    height=up_h,
                    spacing=14,
                    controls=[
                        limit_warning,
                        _section_label("TOPIC TITLE"),
                        title_field,
                        _section_label("MATERIAL CONTENT"),
                        mode_switcher,
                        file_section,
                        text_section,
                        error_box,
                        status_box,
                        ft.Container(height=2),
                        ft.Row(controls=[submit_btn]),
                    ],
                ),
            ),
            actions=[],
        )
        page.overlay.append(modal)
        modal.open = True
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # GENERATE PANEL
    # ─────────────────────────────────────────────────────────────────────────
    def _open_generate_panel():
        gen_remaining = (state["gen_lim"] - state["gen_used"]) if state["gen_lim"] is not None else None
        at_gen_limit  = state["gen_lim"] is not None and state["gen_used"] >= state["gen_lim"]

        cb_flashcards = ft.Checkbox(label="Flashcards (SRS cards)", value=True, visible=False)
        cb_quiz       = ft.Checkbox(label="Quick Quiz questions", value=False, visible=False)
        cb_exam       = ft.Checkbox(label="Exam questions", value=False, visible=False)

        gen_error  = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False)
        gen_status = ft.Text("", color=ft.Colors.TEAL_600, size=12, visible=False)

        gen_error_box = ft.Container(
            visible=False,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.RED_400),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.RED_400)),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_400, size=16),
                    gen_error,
                ],
            ),
        )

        gen_status_box = ft.Container(
            visible=False,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.TEAL_500),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.TEAL_500)),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.TEAL_600, size=16),
                    gen_status,
                ],
            ),
        )

        mats = state["materials"]
        panel_selected: set = set(state["selected_mat_ids"])

        counter_chip_text = ft.Text(
            f"{len(panel_selected)} of {len(mats)} selected",
            size=10.5,
            weight=ft.FontWeight.W_700,
            color=ft.Colors.PRIMARY,
        )
        counter_chip = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
            border_radius=ft.BorderRadius.all(6),
            content=counter_chip_text,
        )

        tile_refs = {}

        def update_mat_tile(mid):
            if mid not in tile_refs:
                return
            is_sel = mid in panel_selected
            cont, icon_ctrl = tile_refs[mid]
            cont.bgcolor = ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_sel else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE)
            cont.border = ft.Border.all(
                1.5 if is_sel else 1,
                ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            )
            icon_ctrl.name = ft.Icons.CHECK_CIRCLE_ROUNDED if is_sel else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED
            icon_ctrl.color = ft.Colors.PRIMARY if is_sel else ft.Colors.GREY_400

        def toggle_mat(mid):
            if mid in panel_selected:
                panel_selected.remove(mid)
            else:
                panel_selected.add(mid)
            update_mat_tile(mid)
            counter_chip_text.value = f"{len(panel_selected)} of {len(mats)} selected"
            page.update()

        def select_all_mats(e):
            for m in mats:
                panel_selected.add(m["id"])
                update_mat_tile(m["id"])
            counter_chip_text.value = f"{len(panel_selected)} of {len(mats)} selected"
            page.update()

        def clear_all_mats(e):
            panel_selected.clear()
            for m in mats:
                update_mat_tile(m["id"])
            counter_chip_text.value = f"0 of {len(mats)} selected"
            page.update()

        mat_card_controls = []
        for mat in mats:
            mid = mat["id"]
            is_sel = mid in panel_selected
            raw_title = mat.get("title", "Untitled")
            display_title = format_material_title(raw_title)
            stype = (mat.get("source_type") or "text").lower()

            if "pdf" in stype or raw_title.lower().endswith(".pdf"):
                m_icon = ft.Icons.PICTURE_AS_PDF_ROUNDED
                m_color = ft.Colors.RED_400
                m_tag = "PDF"
            elif "url" in stype:
                m_icon = ft.Icons.LINK_ROUNDED
                m_color = ft.Colors.TEAL_400
                m_tag = "URL"
            else:
                m_icon = ft.Icons.DESCRIPTION_ROUNDED
                m_color = ft.Colors.BLUE_400
                m_tag = "NOTES"

            check_icon = ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if is_sel else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                color=ft.Colors.PRIMARY if is_sel else ft.Colors.GREY_400,
                size=18,
            )

            tile = ft.Container(
                border_radius=ft.BorderRadius.all(10),
                padding=ft.Padding.symmetric(horizontal=12, vertical=9),
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_sel else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                border=ft.Border.all(
                    1.5 if is_sel else 1,
                    ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                ),
                ink=True,
                on_click=lambda _, target_id=mid: toggle_mat(target_id),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=10,
                            tight=True,
                            controls=[
                                ft.Container(
                                    width=28, height=28,
                                    bgcolor=ft.Colors.with_opacity(0.12, m_color),
                                    border_radius=ft.BorderRadius.all(7),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(m_icon, color=m_color, size=15),
                                ),
                                ft.Column(
                                    spacing=1,
                                    tight=True,
                                    controls=[
                                        ft.Text(display_title, size=12, weight=ft.FontWeight.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(m_tag, size=9, weight=ft.FontWeight.W_700, color=m_color),
                                    ],
                                ),
                            ],
                        ),
                        check_icon,
                    ],
                ),
            )
            tile_refs[mid] = (tile, check_icon)
            mat_card_controls.append(tile)

        # 3 Bento-Style Output Format Cards
        def output_type_card(icon, title, desc, accent_color, cb_control):
            def toggle_card(e):
                cb_control.value = not cb_control.value
                update_card_ui()
                page.update()

            def update_card_ui():
                is_active = bool(cb_control.value)
                card_box.bgcolor = ft.Colors.with_opacity(0.08, accent_color) if is_active else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE)
                card_box.border = ft.Border.all(
                    1.5 if is_active else 1,
                    accent_color if is_active else ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                )
                status_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED if is_active else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED
                status_icon.color = accent_color if is_active else ft.Colors.GREY_400

            status_icon = ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if cb_control.value else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                color=accent_color if cb_control.value else ft.Colors.GREY_400,
                size=18,
            )

            card_box = ft.Container(
                border_radius=ft.BorderRadius.all(11),
                padding=ft.Padding.symmetric(horizontal=12, vertical=9),
                bgcolor=ft.Colors.with_opacity(0.08, accent_color) if cb_control.value else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                border=ft.Border.all(
                    1.5 if cb_control.value else 1,
                    accent_color if cb_control.value else ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                ),
                ink=True,
                on_click=toggle_card,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=10,
                            tight=True,
                            controls=[
                                ft.Container(
                                    width=32, height=32,
                                    bgcolor=ft.Colors.with_opacity(0.12, accent_color),
                                    border_radius=ft.BorderRadius.all(8),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(icon, color=accent_color, size=17),
                                ),
                                ft.Column(
                                    spacing=1,
                                    tight=True,
                                    controls=[
                                        ft.Text(title, size=12.5, weight=ft.FontWeight.W_700),
                                        ft.Text(desc, size=10.5, color=ft.Colors.GREY_500),
                                    ],
                                ),
                            ],
                        ),
                        status_icon,
                    ],
                ),
            )
            return card_box

        out_flashcards = output_type_card(ft.Icons.STYLE_ROUNDED, "Flashcards", "Spaced Repetition Deck (SM-2 active recall)", ft.Colors.PURPLE_400, cb_flashcards)
        out_quiz = output_type_card(ft.Icons.BOLT_ROUNDED, "Quick Quiz", "Targeted Drills with Instant Rationales", ft.Colors.TEAL_500, cb_quiz)
        out_exam = output_type_card(ft.Icons.TIMER_OUTLINED, "Exam Simulator", "Full-Length Timed Test with Score Breakdown", ft.Colors.ORANGE_500, cb_exam)

        gen_btn = ft.ElevatedButton(
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=6,
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.WHITE),
                    ft.Text("Generate AI Content", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_700),
                ],
            ),
            bgcolor=ft.Colors.PURPLE_500,
            expand=True,
            height=44,
            disabled=at_gen_limit,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=0,
            ),
        )

        async def do_generate(e):
            selected_types = []
            if cb_flashcards.value: selected_types.append("flashcards")
            if cb_quiz.value:       selected_types.append("quiz")
            if cb_exam.value:       selected_types.append("exam")

            if not selected_types:
                gen_error.value = "Select at least one output type."
                gen_error_box.visible = True
                page.update()
                return

            mat_ids = list(panel_selected) or [m["id"] for m in mats]
            if not mat_ids:
                gen_error.value = "Upload at least one material first."
                gen_error_box.visible = True
                page.update()
                return

            gen_error_box.visible  = False
            gen_status_box.visible = False
            gen_btn.disabled   = True
            gen_btn.content    = ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=8,
                controls=[
                    ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY, stroke_width=2),
                    ft.Text("Queuing AI Tasks…", color=ft.Colors.ON_PRIMARY, size=12, weight=ft.FontWeight.W_600),
                ],
            )
            page.update()

            for m_id in mat_ids:
                state["generating_mats"].add(m_id)
                state["poll_strikes"][m_id] = 0

            try:
                result = await asyncio.wait_for(
                    generate_from_materials(token, mat_ids, selected_types),
                    timeout=30,
                )
                
                state["gen_used"] += 1
                _refresh_plan_ui()
                
                gen_status.value   = "✓ Tasks queued! AI is generating in the background."
                gen_status_box.visible = True
                gen_btn.disabled   = False
                gen_btn.content    = ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=6,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.WHITE),
                        ft.Text("Generate AI Content", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_700),
                    ],
                )
                page.update()

            except asyncio.TimeoutError:
                gen_error.value   = "Server request timed out. Try again."
                gen_error_box.visible = True
                gen_btn.disabled  = False
                gen_btn.content   = ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=6,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.WHITE),
                        ft.Text("Generate AI Content", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_700),
                    ],
                )
                for m_id in mat_ids: state["generating_mats"].discard(m_id)
                page.update()
                
            except Exception as ex:
                gen_error.value   = "Failed to queue tasks, please try again."
                gen_error_box.visible = True
                gen_btn.disabled  = False
                gen_btn.content   = ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=6,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.WHITE),
                        ft.Text("Generate AI Content", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_700),
                    ],
                )
                for m_id in mat_ids: state["generating_mats"].discard(m_id)
                page.update()

        gen_btn.on_click = do_generate

        remaining_chip = ft.Container(
            visible=state["gen_lim"] is not None and not at_gen_limit,
            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PURPLE_400),
            border_radius=ft.BorderRadius.all(6),
            content=ft.Text(
                f"{gen_remaining} remaining" if gen_remaining is not None else "",
                size=10,
                weight=ft.FontWeight.W_700,
                color=ft.Colors.PURPLE_700,
            ),
        )

        quota_box = ft.Container(
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("AI GENERATION QUOTA", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.GREY_500),
                            remaining_chip,
                        ],
                    ),
                    ft.ProgressBar(
                        value=min(1.0, (state["gen_used"] / state["gen_lim"])) if state["gen_lim"] else 0.0,
                        color=ft.Colors.PURPLE_400,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_400),
                        height=5,
                        border_radius=ft.BorderRadius.all(3),
                    ) if state["gen_lim"] else ft.Container(),
                    ft.Text(
                        f"{state['gen_used']} of {state['gen_lim']} generations used this period" if state["gen_lim"] else f"{state['gen_used']} generated",
                        size=10.5,
                        color=ft.Colors.GREY_500,
                    ),
                ],
            ),
        )

        limit_row = ft.Container(
            visible=at_gen_limit,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.RED_400),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.RED_400)),
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=ft.Colors.RED_400, size=18),
                    ft.Text(
                        "Limit Reached! Upgrade your plan to generate more.",
                        size=11.5,
                        color=ft.Colors.RED_700,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
            ),
        )

        def close_generate_modal(e):
            modal.open = False
            page.update()

        gen_w = min(page.width - 32, 480) if page.width else 440
        gen_h = min(page.height - 180, 500) if page.height else 460

        materials_list_content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=6,
            controls=mat_card_controls if mat_card_controls else [
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=20),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                        controls=[
                            ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=24, color=ft.Colors.GREY_400),
                            ft.Text("No materials in vault yet", size=12, color=ft.Colors.GREY_400),
                        ],
                    ),
                )
            ],
        )

        materials_container = ft.Container(
            height=160,
            border_radius=ft.BorderRadius.all(12),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
            padding=6,
            content=materials_list_content,
        )

        materials_header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=8,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        _section_label("SELECT SOURCE MATERIALS"),
                        counter_chip,
                    ],
                ),
                ft.Row(
                    spacing=2,
                    tight=True,
                    controls=[
                        ft.TextButton(
                            "Select All",
                            style=ft.ButtonStyle(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                visual_density=ft.VisualDensity.COMPACT,
                            ),
                            on_click=select_all_mats,
                        ) if len(mats) > 0 else ft.Container(),
                        ft.TextButton(
                            "Clear",
                            style=ft.ButtonStyle(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                visual_density=ft.VisualDensity.COMPACT,
                            ),
                            on_click=clear_all_mats,
                        ) if len(mats) > 0 else ft.Container(),
                    ],
                ),
            ],
        )

        modal = ft.AlertDialog(
            modal=False, 
            shape=ft.RoundedRectangleBorder(radius=18),
            on_dismiss=close_generate_modal,
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Container(
                                width=34, height=34,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_400),
                                border_radius=ft.BorderRadius.all(10),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PURPLE_400, size=18),
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                controls=[
                                    ft.Text("Generate Study Content", size=15.5, weight=ft.FontWeight.W_700),
                                    ft.Text("Create cards, quizzes & exams with AI", size=11, color=ft.Colors.GREY_500),
                                ],
                            ),
                        ],
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        icon_color=ft.Colors.GREY_400,
                        on_click=close_generate_modal,
                    ),
                ],
            ),
            content=ft.Container(
                width=gen_w,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    height=gen_h,
                    spacing=14,
                    controls=[
                        limit_row,
                        quota_box,
                        materials_header,
                        materials_container,
                        _section_label("CHOOSE OUTPUT FORMATS"),
                        ft.Column(
                            spacing=8,
                            controls=[out_flashcards, out_quiz, out_exam],
                        ),
                        gen_error_box,
                        gen_status_box,
                        ft.Container(height=2),
                        ft.Row(controls=[gen_btn]),
                    ],
                ),
            ),
            actions=[],
        )
        page.overlay.append(modal)
        modal.open = True
        page.update()


    # ─────────────────────────────────────────────────────────────────────────
    # STUDY SESSIONS
    #
    # Flashcards / quiz / exam now live in dedicated modules under
    # src/components/, all sharing one design system (study_ui.py) instead of
    # each re-implementing cards, progress bars and results screens.
    # These wrappers preserve the original signatures, so go_flashcards /
    # go_quiz / go_exam below are untouched.
    # ─────────────────────────────────────────────────────────────────────────

    def _reset_keyboard():
        """Sessions install their own shortcuts; drop them back on the hub."""
        try:
            page.on_keyboard_event = None
        except Exception:
            pass

    def _build_flashcard_session(cards: list):
        return build_flashcard_session(
            page,
            cards,
            token=token,
            on_exit=go_hub,
            on_restart=lambda: page.run_task(_start_flashcards, _current_selected_ids()),
        )

    def _build_quiz(questions: list):
        return build_quiz(
            page,
            questions,
            on_exit=go_hub,
            on_restart=lambda: page.run_task(_start_quiz, _current_selected_ids()),
        )

    def _build_exam(questions: list, duration_seconds: int | None = None):
        return build_exam(
            page,
            questions,
            duration_seconds,
            on_exit=go_hub,
            on_restart=lambda: page.run_task(_start_exam, _current_selected_ids()),
            on_lock=_lock_exam_ui,
            on_register_submit=lambda fn: state.update({"exam_submit_fn": fn}),
        )


    # ─────────────────────────────────────────────────────────────────────────
    # BOOT
    # ─────────────────────────────────────────────────────────────────────────
    content_socket.content = _loading("Loading Study Hub…")
    _refresh_plan_ui()
    update_layout()
    page.run_task(_load_hub)
    page.run_task(_poll_generation_status)

    return ft.View(
        route="/self-study",
        appbar=app_bar,
        bgcolor=ft.Colors.ON_PRIMARY,
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=body_host # Passed directly, no extra column wrappers needed
            )
        ],
    )