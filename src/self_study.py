import asyncio
import time
import re
import flet as ft
from src.components.study_flashcards import build_flashcard_session
from src.components.study_quiz import build_quiz
from src.components.study_exam import build_exam
from src.components.deck_inspector import open_deck_inspector
from src.components.study_marketplace import StudyMarketplaceView
from src.components.study_partner_cockpit import build_study_partner_cockpit
from src.components.dashboard_duo_section import build_dashboard_duo_section


from src.requests.study import (
    get_due_cards,
    upload_material,
    get_materials,
    get_quiz_questions,
    get_exam_questions,
    generate_from_materials,
    check_generation_status,
    import_youtube_material,
    get_youtube_recommendations,
    delete_study_material,
)
from src.requests.chats import ask_ai_tutor_api
from src.requests.study_partners import (
    get_active_partnership,
    share_study_pack_api,
    log_partnership_study_activity_api,
)
from src.utils.file_opener import safe_set_clipboard, show_page_snackbar
from src.components.adaptive_video_player import AdaptiveVideoPlayer
from src.utils.youtube import (
    is_youtube_url,
    is_youtube_search_url,
    extract_youtube_search_query,
    extract_youtube_id,
    get_youtube_thumbnail_url,
)
from src.services.ai_tutor_session import (
    get_material_tutor_history,
    append_material_tutor_message,
    clear_material_tutor_history,
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
    lbl = ft.Text(
        label,
        size=13.5,
        weight=ft.FontWeight.W_600,
        color=ft.Colors.with_opacity(0.75, ft.Colors.ON_SURFACE),
    )
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
                lbl,
            ],
        ),
    )
    c._is_loading = True
    c._lbl_text = lbl
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


def clean_pack_import_tag(title: str) -> str:
    """Strip [pack import] or (pack import) prefixes, suffixes, or bracketed labels from material titles."""
    if not title or not isinstance(title, str):
        return ""
    import re
    t = re.sub(r"(?i)\s*[\[\(]\s*pack\s*import\s*[\]\)]\s*[:\-–—]?\s*", " ", title)
    t = re.sub(r"(?i)^pack\s*import\s*[:\-–—]?\s*", "", t)
    return t.strip()


def format_material_title(raw_title: str) -> str:
    """Format material title to clean sentence case for UI display while preserving the raw string/id for backend calls."""
    if not raw_title or not isinstance(raw_title, str):
        return "Untitled document"
    
    title = clean_pack_import_tag(raw_title)
    if not title:
        return "Study pack"
    
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
    user_role      = await page.shared_preferences.get("user_role")

    # ── shared state ──────────────────────────────────────────────────────────
    state = {
        "user_role":         user_role or "student",
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
        "hub_load_version":  0,
        "poller_id":         0,
        # Dynamic limits (defaults before fetch)
        "plan_id":           "free",
        "plan_label":        "Loading",
        "mat_used":          0,
        "poll_strikes":      {},
        "mat_lim":           5,
        "gen_used":          0,
        "gen_lim":           10,
        "active_material":   None,
        "active_material_cards": [],
        "material_ai_chat":  [],
        "is_ai_generating":  False,
    }

    # ─────────────────────────────────────────────────────────────────────────
    # APP BAR
    # ─────────────────────────────────────────────────────────────────────────
    sidebar_toggle = ft.IconButton(
        icon=ft.Icons.MENU_OPEN_ROUNDED,
        icon_color=ft.Colors.ON_SURFACE,
        tooltip="Toggle sidebar",
    )

    def _handle_back_click(e=None):
        if state.get("is_offline"):
            page.go("/offline")
        else:
            page.go("/dashboard")

    async def _handle_sync_all_vault(e=None):
        nonlocal token
        curr_token = token or (await page.shared_preferences.get("auth_token"))
        if not curr_token:
            show_page_snackbar(page, "Please log in to sync your study vault.")
            return

        is_online = False
        try:
            from src.requests.auth import get_current_user_request
            status, _ = await asyncio.wait_for(get_current_user_request(curr_token), timeout=4.0)
            if status == 200:
                is_online = True
                token = curr_token
        except Exception:
            is_online = False

        if not is_online:
            show_page_snackbar(page, "Cannot sync while offline. Please connect to the internet.")
            return

        state["is_offline"] = False
        from src.progress_sync import sync_offline_progress
        from src.download_manager import download_all_study_materials

        show_page_snackbar(page, "Syncing study vault & uploading offline reviews…")
        # 1. Push any queued offline reviews & progress
        try:
            await sync_offline_progress(page)
        except Exception as sync_p_err:
            print(f"[_handle_sync_all_vault sync_offline_progress error]: {sync_p_err}")

        # 2. Pull down fresh materials, cards and questions
        res = await download_all_study_materials(page, curr_token)
        m_cnt = res.get("materials", 0)
        c_cnt = res.get("cards", 0)
        q_cnt = res.get("questions", 0)
        show_page_snackbar(page, f"Vault synced: {m_cnt} items, {c_cnt} cards & {q_cnt} questions cached offline.")
        await _load_hub()

    offline_status_badge = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=ft.BorderRadius.all(8),
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER if state.get("is_offline") else ft.Colors.GREEN),
        content=ft.Row(
            spacing=4,
            tight=True,
            controls=[
                ft.Icon(
                    ft.Icons.WIFI_OFF_ROUNDED if state.get("is_offline") else ft.Icons.WIFI_ROUNDED,
                    size=12,
                    color=ft.Colors.AMBER_800 if state.get("is_offline") else ft.Colors.GREEN_700,
                ),
                ft.Text(
                    "Offline" if state.get("is_offline") else "Online",
                    size=10,
                    weight=ft.FontWeight.W_800,
                    color=ft.Colors.AMBER_900 if state.get("is_offline") else ft.Colors.GREEN_800,
                ),
            ],
        ),
    )

    offline_library_btn = ft.IconButton(
        icon=ft.Icons.DOWNLOAD_DONE_ROUNDED,
        icon_size=19,
        icon_color=ft.Colors.ON_SURFACE,
        tooltip="Offline Library",
        on_click=lambda _: page.go("/offline"),
    )

    sync_vault_btn = ft.IconButton(
        icon=ft.Icons.SYNC_ROUNDED,
        icon_size=19,
        icon_color=ft.Colors.PRIMARY,
        tooltip="Sync Vault Offline",
        visible=not state.get("is_offline") and bool(token),
        on_click=lambda _: page.run_task(_handle_sync_all_vault),
    )

    app_bar = ft.AppBar(
        bgcolor=ft.Colors.SURFACE,
        title=ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text("Study Hub", color=ft.Colors.ON_SURFACE,
                              weight=ft.FontWeight.W_700, size=17),
                offline_status_badge,
            ],
        ),
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.ON_SURFACE,
            on_click=_handle_back_click,
        ),
        actions=[sync_vault_btn, offline_library_btn, sidebar_toggle],
        elevation=0,
        elevation_on_scroll=0,
        shadow_color=ft.Colors.TRANSPARENT,
        force_material_transparency=False,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN CONTENT SOCKET
    # ─────────────────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────
    # MAIN CONTENT SOCKET (Fixed Single-Tree Layout)
    # ─────────────────────────────────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        content=_loading("Loading Study Hub…"),
        opacity=1,
        offset=ft.Offset(0, 0),
        animate_opacity=ft.Animation(350, ft.AnimationCurve.DECELERATE),
        animate_offset=ft.Animation(350, ft.AnimationCurve.DECELERATE),
    )

    def _set_loading(label="Loading…"):
        curr = content_socket.content
        if curr and getattr(curr, "_is_loading", False) and hasattr(curr, "_lbl_text") and curr._lbl_text:
            curr._lbl_text.value = label
            try:
                curr._lbl_text.update()
            except Exception:
                page.update()
        else:
            content_socket.content = _loading(label)
            page.update()
    
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
    def _create_badge_control(compact: bool = False):
        icon_size = 9 if compact else 10
        text_size = 8 if compact else 9
        icon_ctrl = ft.Icon(ft.Icons.SHIELD_OUTLINED, size=icon_size, color=ft.Colors.with_opacity(0.65, ft.Colors.ON_SURFACE))
        text_ctrl = ft.Text(
            "FREE",
            size=text_size,
            weight=ft.FontWeight.W_800,
            color=ft.Colors.with_opacity(0.80, ft.Colors.ON_SURFACE),
            max_lines=1,
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=6 if compact else 8, vertical=2 if compact else 2.5),
            border_radius=ft.BorderRadius.all(999),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
            bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            content=ft.Row(
                tight=True,
                spacing=3 if compact else 4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[icon_ctrl, text_ctrl],
            ),
        )
        badge.data = {"icon": icon_ctrl, "text": text_ctrl, "icon_size": icon_size}
        return badge

    sidebar_plan_badge = _create_badge_control()
    modal_plan_badge = _create_badge_control(compact=True)

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
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(spacing=6, controls=[
                            ft.Icon(ft.Icons.BOLT_ROUNDED, color=ft.Colors.ORANGE_600, size=14),
                            ft.Text("Unlock Pro Scholar", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.ORANGE_700),
                        ]),
                        ft.Text("₦2,500/mo", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.ORANGE_800),
                    ],
                ),
                ft.Text("45 materials · 100 AI decks · 40 mock exams / month", size=10, color=ft.Colors.GREY_500),
                ft.ElevatedButton(
                    content=ft.Row(
                        tight=True, spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.HOURGLASS_EMPTY_ROUNDED, size=12, color=ft.Colors.WHITE),
                            ft.Text("Pro Plans Coming Soon", size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.W_700),
                        ],
                    ),
                    bgcolor=ft.Colors.GREY_600, height=32, width=float("inf"),
                    disabled=True,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                ),
            ],
        ),
    )

    def _refresh_plan_ui():
        plan_id = str(state.get("plan_id") or "free").lower()
        raw_label = str(state.get("plan_label") or "Free").strip()
        label = raw_label.upper()

        is_pro = "pro" in plan_id or "scholar" in plan_id
        is_unlimited = "unlimited" in plan_id or "enterprise" in plan_id

        # 1. Update Both Badges with High-End Styling
        for badge in (sidebar_plan_badge, modal_plan_badge):
            icon_ctrl = badge.data.get("icon") if getattr(badge, "data", None) else None
            text_ctrl = badge.data.get("text") if getattr(badge, "data", None) else None

            if not icon_ctrl or not text_ctrl:
                continue

            text_ctrl.value = label if len(label) <= 14 else label[:13] + "…"

            if is_pro:
                # Pro Scholar: Radiant violet/indigo gradient capsule with amber sparkle star
                badge.gradient = ft.LinearGradient(
                    begin=ft.Alignment.TOP_LEFT,
                    end=ft.Alignment.BOTTOM_RIGHT,
                    colors=[ft.Colors.PURPLE_600, ft.Colors.INDIGO_700],
                )
                badge.bgcolor = None
                badge.border = ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.PURPLE_300))
                badge.shadow = ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=6,
                    color=ft.Colors.with_opacity(0.30, ft.Colors.PURPLE_700),
                    offset=ft.Offset(0, 1.5),
                )
                icon_ctrl.name = ft.Icons.AUTO_AWESOME_ROUNDED
                icon_ctrl.color = ft.Colors.AMBER_300
                icon_ctrl.size = badge.data.get("icon_size", 10)
                text_ctrl.color = ft.Colors.WHITE
            elif is_unlimited:
                # Unlimited: Radiant warm amber/orange gradient capsule
                badge.gradient = ft.LinearGradient(
                    begin=ft.Alignment.TOP_LEFT,
                    end=ft.Alignment.BOTTOM_RIGHT,
                    colors=[ft.Colors.AMBER_600, ft.Colors.ORANGE_700],
                )
                badge.bgcolor = None
                badge.border = ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_300))
                badge.shadow = ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=6,
                    color=ft.Colors.with_opacity(0.30, ft.Colors.ORANGE_700),
                    offset=ft.Offset(0, 1.5),
                )
                icon_ctrl.name = ft.Icons.ALL_INCLUSIVE_ROUNDED
                icon_ctrl.color = ft.Colors.WHITE
                icon_ctrl.size = badge.data.get("icon_size", 10)
                text_ctrl.color = ft.Colors.WHITE
            else:
                # Free: Sleek modern neutral capsule with shield icon
                badge.gradient = None
                badge.shadow = None
                badge.bgcolor = ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE)
                badge.border = ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE))
                icon_ctrl.name = ft.Icons.SHIELD_OUTLINED
                icon_ctrl.color = ft.Colors.with_opacity(0.65, ft.Colors.ON_SURFACE)
                icon_ctrl.size = badge.data.get("icon_size", 10)
                text_ctrl.color = ft.Colors.with_opacity(0.80, ft.Colors.ON_SURFACE)
        
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
        """Read the live sidebar/material selection at call-time.
        Strict Single-Material Invariant: If a material is active, practice targets only that material.
        Otherwise (on Hub), practice targets all due cards across the vault."""
        if state.get("active_material") and state["active_material"].get("id"):
            return [str(state["active_material"]["id"])]
        clean_ids = sorted([str(m).strip() for m in state.get("selected_mat_ids", set()) if str(m).strip()])
        return clean_ids or None

    async def _sync_material_selection(target_id=None, toggle=True, clear_all=False, select_all=False):
        if clear_all:
            state["selected_mat_ids"].clear()
            state["active_material"] = None
        elif select_all:
            if state.get("materials"):
                # Under the single-material invariant, select the first material
                state["active_material"] = state["materials"][0]
                state["selected_mat_ids"] = {state["materials"][0]["id"]}
        elif target_id:
            for m in state.get("materials", []):
                if str(m.get("id")) == str(target_id):
                    state["active_material"] = m
                    state["selected_mat_ids"] = {m["id"]}
                    break

        _refresh_sidebar_materials()
        if state.get("on_hub"):
            if state.get("active_material"):
                content_socket.content = _build_material_cockpit(state["active_material"], state.get("due_cards", []))
            else:
                content_socket.content = _build_hub(state.get("due_cards", []), state.get("materials", []))
            page.update()

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
                    if state.get("active_material"):
                        content_socket.content = _build_material_cockpit(state["active_material"], state["due_cards"])
                    else:
                        content_socket.content = _build_hub(state["due_cards"], state.get("materials", []))
                    page.update()
        except Exception as ex:
            print(f"[STUDY] Error syncing due cards: {ex}")

    def _on_search_materials(e):
        state["search_query"] = (e.control.value or "").strip().lower()
        _refresh_sidebar_materials()
        page.update()

    def _select_all_materials(e=None):
        if state.get("materials"):
            page.run_task(_open_material_cockpit, state["materials"][0])

    def _clear_selected_materials(e=None):
        page.run_task(_back_to_hub)

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

            is_active = state.get("active_material") and str(state["active_material"].get("id")) == str(mat_id)

            if is_active:
                border_style = ft.Border.all(1.5, ft.Colors.PRIMARY)
                bg_style = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)
                trailing_control = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.PRIMARY,
                    content=ft.Text("ACTIVE", size=8.5, color=ft.Colors.WHITE, weight=ft.FontWeight.W_800),
                )
            else:
                border_style = ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))
                bg_style = ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE)
                trailing_control = ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=16, color=ft.Colors.GREY_400)

            chip = ft.Container(
                border_radius=ft.BorderRadius.all(10),
                border=border_style,
                bgcolor=bg_style,
                padding=ft.Padding.symmetric(horizontal=9, vertical=8),
                ink=True,
                data=mat_id,
                tooltip=f"Study {display_title}",
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=28,
                            height=28,
                            border_radius=ft.BorderRadius.all(7),
                            bgcolor=ft.Colors.with_opacity(0.14, m_color),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(m_icon, color=m_color, size=15),
                        ),
                        ft.Column(
                            spacing=1,
                            expand=True,
                            controls=[
                                ft.Text(
                                    display_title,
                                    size=11.5,
                                    weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_600,
                                    color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Text(
                                            m_tag,
                                            size=8.5,
                                            color=ft.Colors.PRIMARY if is_active else ft.Colors.GREY_500,
                                            weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500,
                                        ),
                                        ft.Text("· Active", size=8.5, color=ft.Colors.PRIMARY, weight=ft.FontWeight.W_600) if is_active else ft.Container(),
                                    ],
                                ),
                            ],
                        ),
                        trailing_control,
                    ],
                ),
            )

            def _select_material(e, m=mat):
                # Instantly reflect active status on the tapped card
                state["active_material"] = m
                state["selected_mat_ids"] = {m["id"]}
                _refresh_sidebar_materials()
                if not state.get("was_desktop", True) and state.get("sidebar_open"):
                    _toggle_sidebar()
                page.run_task(_open_material_cockpit, m)

            chip.on_click = _select_material
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

        # Drop-in replacement for your existing `studio_dlg = ft.AlertDialog(...)` block.
        # It still uses your existing names: _close_studio, dialog_w, modal_plan_badge,
        # _section_label, studio_upload_tile, studio_gen_tile, bars_col, page.
        # Colors come from the theme (PRIMARY / SURFACE / ON_SURFACE), so light and
        # dark mode both keep working.

        def _benefit_row(text: str) -> ft.Row:
            return ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=14, color=ft.Colors.ORANGE_400),
                    ft.Text(text, size=11.5, color=ft.Colors.with_opacity(0.8, ft.Colors.ON_SURFACE)),
                ],
            )

        studio_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=22),
            bgcolor=ft.Colors.SURFACE,
            title_padding=ft.Padding.only(left=22, right=12, top=18, bottom=0),
            content_padding=ft.Padding.only(left=22, right=22, top=14, bottom=22),
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=12,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=40,
                                height=40,
                                border_radius=ft.BorderRadius.all(13),
                                alignment=ft.Alignment.CENTER,
                                gradient=ft.LinearGradient(
                                    colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.65, ft.Colors.PRIMARY)],
                                    begin=ft.Alignment.TOP_LEFT,
                                    end=ft.Alignment.BOTTOM_RIGHT,
                                ),
                                content=ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=ft.Colors.ON_PRIMARY, size=20),
                            ),
                            ft.Column(
                                spacing=1,
                                expand=True,
                                tight=True,
                                controls=[
                                    ft.Text("Studio & Quotas", size=16, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text("Uploads, AI generation & limits", size=11, color=ft.Colors.GREY_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
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
                    spacing=16,
                    controls=[
                        # ── Subscription plan card ──
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                            border_radius=ft.BorderRadius.all(14),
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.PRIMARY)),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row(
                                        spacing=10,
                                        expand=True,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            ft.Container(
                                                width=32,
                                                height=32,
                                                border_radius=ft.BorderRadius.all(10),
                                                bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY),
                                                alignment=ft.Alignment.CENTER,
                                                content=ft.Icon(ft.Icons.CARD_MEMBERSHIP_ROUNDED, size=17, color=ft.Colors.PRIMARY),
                                            ),
                                            ft.Column(
                                                spacing=1,
                                                tight=True,
                                                expand=True,
                                                controls=[
                                                    ft.Text("Subscription plan", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                                    ft.Text("Your current tier", size=10.5, color=ft.Colors.GREY_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                                ],
                                            ),
                                        ],
                                    ),
                                    ft.Container(width=8),
                                    modal_plan_badge,
                                ],
                            ),
                        ),

                        # ── Creative studio ──
                        ft.Column(
                            spacing=8,
                            tight=True,
                            controls=[
                                _section_label("CREATIVE STUDIO"),
                                ft.Row(
                                    spacing=10,
                                    controls=[
                                        studio_upload_tile,
                                        studio_gen_tile,
                                    ],
                                ),
                            ],
                        ),

                        # ── Quotas & usage ──
                        ft.Column(
                            spacing=8,
                            tight=True,
                            controls=[
                                _section_label("PLAN QUOTAS & USAGE"),
                                ft.Container(
                                    padding=ft.Padding.all(14),
                                    border_radius=ft.BorderRadius.all(14),
                                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                                    content=bars_col,
                                ),
                            ],
                        ),

                        # ── Actions ──
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.FilledButton(
                                    content=ft.Row(
                                        tight=True,
                                        spacing=6,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        controls=[
                                            ft.Icon(ft.Icons.BOLT_ROUNDED, size=15, color=ft.Colors.AMBER_400),
                                            ft.Text("Top Up", size=11.5, color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.W_700),
                                        ],
                                    ),
                                    height=40,
                                    disabled=True,
                                    opacity=0.45,
                                    tooltip="Coming soon",
                                    expand=True,
                                    style=ft.ButtonStyle(
                                        bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.AMBER),
                                        side=ft.BorderSide(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_400)),
                                        shape=ft.RoundedRectangleBorder(radius=20),
                                        elevation=0,
                                    ),
                                    on_click=lambda _: (_close_studio(None), page.go("/store?tab=boosters")),
                                ),
                                ft.FilledButton(
                                    content=ft.Row(
                                        tight=True,
                                        spacing=6,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        controls=[
                                            ft.Icon(ft.Icons.STOREFRONT_ROUNDED, size=15, color=ft.Colors.ON_PRIMARY),
                                            ft.Text("Open Store", size=11.5, color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.W_800),
                                        ],
                                    ),
                                    height=40,
                                    disabled=True,
                                    opacity=0.45,
                                    tooltip="Coming soon",
                                    expand=True,
                                    style=ft.ButtonStyle(
                                        bgcolor=ft.Colors.PRIMARY,
                                        shape=ft.RoundedRectangleBorder(radius=20),
                                        elevation=0,
                                    ),
                                    on_click=lambda _: (_close_studio(None), page.go("/store?tab=plans")),
                                ),
                            ],
                        ),

                        # ── Pro upsell ──
                        ft.Container(
                            border_radius=ft.BorderRadius.all(16),
                            padding=ft.Padding.all(14),
                            gradient=ft.LinearGradient(
                                colors=[
                                    ft.Colors.with_opacity(0.16, ft.Colors.ORANGE_500),
                                    ft.Colors.with_opacity(0.05, ft.Colors.ORANGE_500),
                                ],
                                begin=ft.Alignment.TOP_LEFT,
                                end=ft.Alignment.BOTTOM_RIGHT,
                            ),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.ORANGE_500)),
                            content=ft.Column(
                                spacing=10,
                                tight=True,
                                controls=[
                                    ft.Row(
                                        spacing=10,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            ft.Container(
                                                width=32,
                                                height=32,
                                                border_radius=ft.BorderRadius.all(10),
                                                bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.ORANGE_500),
                                                alignment=ft.Alignment.CENTER,
                                                content=ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, size=17, color=ft.Colors.ORANGE_400),
                                            ),
                                            ft.Text("Unlock Pro Scholar Quotas", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ORANGE_400),
                                        ],
                                    ),
                                    _benefit_row("45 material slots"),
                                    _benefit_row("100 AI synthesis decks per month"),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(vertical=9),
                                        border_radius=ft.BorderRadius.all(10),
                                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Row(
                                            tight=True,
                                            spacing=6,
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            controls=[
                                                ft.Icon(ft.Icons.HOURGLASS_EMPTY_ROUNDED, size=13, color=ft.Colors.GREY_500),
                                                ft.Text("Upgrade plans coming soon", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500),
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                        ),
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
                        _rail_icon_btn(ft.Icons.STOREFRONT_ROUNDED, "Pack Store & Hub", lambda _: go_marketplace()),
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

    def _pinned_row(icon, title, badge_control=None, on_click=None, is_active=False):
        if badge_control is not None:
            if isinstance(badge_control, ft.Container):
                badge_box = badge_control
            else:
                badge_box = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE),
                    content=badge_control,
                )
        else:
            badge_box = ft.Container()

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=7),
            border_radius=ft.BorderRadius.all(8),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_active else None,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)) if is_active else None,
            ink=True,
            on_click=on_click,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=9,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(icon, size=16, color=ft.Colors.PRIMARY if is_active else ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE)),
                            ft.Text(
                                title,
                                size=12,
                                weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_600,
                                color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                        ],
                    ),
                    badge_box,
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
                    padding=ft.Padding.symmetric(horizontal=14, vertical=11),
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
                            ft.IconButton(
                                ft.Icons.ADD_ROUNDED,
                                icon_size=19,
                                icon_color=ft.Colors.PRIMARY,
                                tooltip="Upload New Material",
                                on_click=lambda _: _open_upload_modal(),
                            ),
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
                                    spacing=10,
                                    controls=[
                                        # ── SECTION 1: SIDEBAR NAVIGATION MENU ─────────────────────
                                        _pinned_row(
                                            ft.Icons.SPACE_DASHBOARD_ROUNDED,
                                            "Hub Home",
                                            badge_control=None,
                                            on_click=lambda _: page.run_task(_back_to_hub) if (not state.get("on_hub") or state.get("active_material")) else None,
                                        ),
                                        _pinned_row(
                                            ft.Icons.STOREFRONT_ROUNDED,
                                            "Pack Store & Hub",
                                            badge_control=None,
                                            on_click=lambda _: go_marketplace(),
                                        ),
                                        _pinned_row(
                                            ft.Icons.STYLE_ROUNDED,
                                            "Review Due Cards",
                                            badge_control=state["sidebar_due_text"],
                                            on_click=_on_click_review_queue,
                                        ),
                                        _pinned_row(
                                            ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                                            "Studio & Limits",
                                            badge_control=sidebar_plan_badge,
                                            on_click=lambda _: _open_studio_modal(),
                                        ),

                                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),

                                        # ── SECTION 2: DEDICATED STUDY MATERIALS ───────────────────
                                        ft.Container(
                                            padding=ft.Padding.only(top=2),
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
                                                                    ft.Icon(ft.Icons.FOLDER_SPECIAL_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                                                                    ft.Text("MATERIALS VAULT", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.GREY_600),
                                                                ],
                                                            ),
                                                            state["sidebar_vault_text"],
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
        app_bar.title = ft.Text(title, color=ft.Colors.ON_SURFACE,
                                weight=ft.FontWeight.W_700, size=17)
        def _on_back_wrapper(e=None):
            if callable(on_back):
                try:
                    on_back()
                except TypeError:
                    on_back(e)

        app_bar.leading = ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.ON_SURFACE,
            on_click=_on_back_wrapper,
        )
        sidebar_toggle.visible = state.get("on_hub", True)

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
        page.route = "/self-study?offline=true" if state.get("is_offline") else "/self-study"
        state["on_hub"] = True
        state["active_material"] = None
        state["selected_mat_ids"] = set()
        _refresh_sidebar_materials()
        _reset_keyboard()
        _lock_exam_ui(False)
        _set_appbar("Study Hub", _handle_back_click)
        _set_loading(label)
        page.run_task(_load_hub, False, None)

    def _exit_study_session(label="Returning…"):
        _lock_exam_ui(False)
        _reset_keyboard()

        # Report study session activity to accountability partner
        start_t = state.get("session_start_time")
        if start_t and token:
            elapsed_seconds = int(time.time() - start_t)
            elapsed_mins = max(1, elapsed_seconds // 60)
            state["session_start_time"] = None
            async def _report_partner_activity():
                try:
                    p_res = await get_active_partnership(token)
                    if p_res and p_res.get("has_partnership"):
                        p_list = p_res.get("partnerships") or ([p_res.get("partnership")] if p_res.get("partnership") else [])
                        for p in p_list:
                            if p and p.get("id"):
                                await log_partnership_study_activity_api(
                                    token=token,
                                    partnership_id=str(p["id"]),
                                    minutes_spent=elapsed_mins,
                                    questions_completed=max(1, elapsed_mins * 2),
                                )
                except Exception as ex:
                    print(f"[_report_partner_activity] error: {ex}")
            page.run_task(_report_partner_activity)

        active_mat = state.get("active_material")
        if active_mat:
            state["on_hub"] = False
            display_title = format_material_title(active_mat.get("title", ""))
            _set_appbar(display_title, go_hub)
            page.run_task(_open_material_cockpit, active_mat, False)
        else:
            go_hub(label if isinstance(label, str) else "Loading Study Hub…")

    def go_flashcards(cards: list):
        state["on_hub"] = False
        state["session_start_time"] = time.time()
        _set_appbar("Flashcards", _exit_study_session)
        content_socket.content = _build_flashcard_session(cards)
        page.update()

    def go_quiz(questions: list):
        state["on_hub"] = False
        state["session_start_time"] = time.time()
        _set_appbar("Quick Quiz", _exit_study_session)
        content_socket.content = _build_quiz(questions)
        page.update()

    def _confirm_delete_material(mat: dict):
        mtitle = mat.get("title") or "Untitled Document"
        display_title = format_material_title(mtitle)
        is_pack = (mat.get("source_type") or "").lower() == "pack_import"
        mat_id = str(mat.get("id"))

        async def _execute_delete(btn):
            btn.disabled = True
            btn.content = ft.Row(
                tight=True,
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.WHITE),
                    ft.Text("Removing...", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                ],
            )
            page.update()

            res = await delete_study_material(token, mat_id)
            del_dlg.open = False
            page.update()

            if "error" in res:
                show_page_snackbar(page, f"Could not remove: {res['error']}")
            else:
                show_page_snackbar(page, f"'{display_title}' removed from vault.")
                state["materials"] = [m for m in state.get("materials", []) if str(m.get("id")) != mat_id]
                go_hub("Refreshing Study Hub…")

        def _cancel_delete(_):
            del_dlg.open = False
            page.update()

        del_dlg_w = min(page.width - 44, 400) if page.width else 380
        del_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=20),
            bgcolor=ft.Colors.SURFACE,
            content_padding=ft.Padding.all(22),
            content=ft.Container(
                width=del_dlg_w,
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.Container(
                            width=54,
                            height=54,
                            border_radius=ft.BorderRadius.all(27),
                            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.RED_600),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.DELETE_FOREVER_ROUNDED, color=ft.Colors.RED_500, size=26),
                        ),
                        ft.Column(
                            tight=True,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=6,
                            controls=[
                                ft.Text(
                                    "Remove Downloaded Pack?" if is_pack else "Delete Study Material?",
                                    size=17,
                                    weight=ft.FontWeight.W_800,
                                    color=ft.Colors.ON_SURFACE,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                    f"Are you sure you want to remove '{display_title}' from your vault? All its flashcards and quiz questions will be removed from your personal practice schedule.",
                                    size=12,
                                    color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                        ),
                        ft.Container(height=4),
                        ft.Row(
                            spacing=10,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.OutlinedButton(
                                    "Cancel",
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                                    ),
                                    on_click=_cancel_delete,
                                ),
                                ft.ElevatedButton(
                                    content=ft.Row(
                                        tight=True,
                                        spacing=6,
                                        controls=[
                                            ft.Icon(ft.Icons.DELETE_ROUNDED, size=15, color=ft.Colors.WHITE),
                                            ft.Text("Remove from Vault", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                        ],
                                    ),
                                    bgcolor=ft.Colors.RED_600,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                                    ),
                                    on_click=lambda e: page.run_task(_execute_delete, e.control),
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        )
        page.overlay.append(del_dlg)
        del_dlg.open = True
        page.update()

    def _confirm_exit_exam():
        def _submit_and_leave(e):
            exit_dlg.open = False
            page.update()
            submit_fn = state.get("exam_submit_fn")
            if submit_fn:
                submit_fn()
            else:
                _exit_study_session("Returning from exam…")

        def _exit_without_submit(e):
            exit_dlg.open = False
            page.update()
            _exit_study_session("Returning from exam…")

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
                            "Exit without submitting",
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
        if state.get("exam_locked", False):
            _confirm_exit_exam()
        else:
            _exit_study_session()

    def go_exam(questions: list, duration_seconds: int | None = None):
        state["on_hub"] = False
        _set_appbar("CBT Exam Simulator", _on_exam_back)
        from src.components.cbt_exam_engine import build_cbt_exam_view

        user_info = state.get("user") or {}
        cand_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip() or "Student Candidate"

        ex_type = "JAMB UTME"
        ex_year = None
        for q in questions:
            if q.get("exam_type"):
                ex_type = str(q["exam_type"]).upper()
            if q.get("exam_year"):
                try:
                    ex_year = int(q["exam_year"])
                except Exception:
                    pass
            if ex_type and ex_year:
                break

        exam_title = "CBT Examination"
        active_mat_id = None
        if state.get("active_material"):
            exam_title = state["active_material"].get("title", exam_title)
            active_mat_id = str(state["active_material"].get("id") or "")
        elif questions and questions[0].get("material_id"):
            active_mat_id = str(questions[0].get("material_id") or "")

        content_socket.content = build_cbt_exam_view(
            page=page,
            questions=questions,
            duration_seconds=duration_seconds,
            exam_title=exam_title,
            exam_type=ex_type,
            exam_year=ex_year,
            candidate_name=cand_name,
            material_id=active_mat_id,
            on_exit=_exit_study_session,
            on_restart=lambda: page.run_task(_start_exam, _current_selected_ids()),
        )
        page.update()

    def go_marketplace():
        state["on_hub"] = False
        state["active_material"] = None
        _set_appbar("Study Pack Marketplace", go_hub)
        user_role_str = str(state.get("user_role", "")).upper()
        is_admin_user = ("ADMIN" in user_role_str)

        def _on_pack_imported(imported_mat_id: str):
            page.run_task(_load_hub, False, imported_mat_id)

        marketplace_view = StudyMarketplaceView(
            page=page,
            token=token,
            user_vault_materials=state.get("materials", []),
            on_pack_downloaded=_on_pack_imported,
            on_navigate_back=go_hub,
            on_open_coins_modal=_open_studio_modal,
            is_admin=is_admin_user,
        )
        content_socket.content = marketplace_view.view_root
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # HUB — load + layout
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_hub(silent: bool = False, target_mat_id: str | None = None):
        state["hub_load_version"] = state.get("hub_load_version", 0) + 1
        current_version = state["hub_load_version"]

        has_rendered_content = content_socket.content and not getattr(content_socket.content, "_is_loading", False)
        if not silent and not has_rendered_content:
            _set_loading("Loading Study Hub…" if not target_mat_id else "Opening study pack…")

        from src.local_db import (
            get_offline_study_materials,
            get_offline_due_cards,
            save_study_material_offline,
            has_any_downloaded_study_materials,
        )

        is_offline_req = bool(
            (page.route and ("offline=true" in page.route or page.route.startswith("/self-study/offline")))
            or not token
        )
        is_offline_mode = is_offline_req
        due_cards = []
        materials = []

        if not is_offline_mode and token:
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

                if isinstance(due_cards, Exception) or isinstance(materials, Exception):
                    # Network failure — fallback to offline mode if local materials exist
                    if has_any_downloaded_study_materials(page):
                        is_offline_mode = True
                    else:
                        if isinstance(due_cards, Exception): due_cards = []
                        if isinstance(materials, Exception): materials = []
                else:
                    state["is_offline"] = False
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
            except Exception as net_ex:
                print(f"[_load_hub network exception]: {net_ex}")
                if has_any_downloaded_study_materials(page):
                    is_offline_mode = True

        if is_offline_mode:
            state["is_offline"] = True
            offline_mats = get_offline_study_materials(page)
            offline_cards = get_offline_due_cards(page=page)
            state["materials"] = offline_mats
            state["due_cards"] = offline_cards
            state["all_due_cards"] = list(offline_cards)
            due_cards = offline_cards
            materials = offline_mats

        # Track generating materials so polling resumes after page reload
        for m in (materials or []):
            st = str(m.get("status") or "").lower()
            if st in ("processing", "queued", "pending", "in_progress"):
                state.setdefault("generating_mats", set()).add(str(m.get("id")))

        # Concurrency guard: if a newer _load_hub was dispatched while awaiting, discard this stale run
        if current_version != state.get("hub_load_version"):
            return

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
            # Check route query parameters or explicit target_mat_id for deep linking
            resolved_mat_id = target_mat_id
            target_action = None
            if not resolved_mat_id and page.route and "?" in page.route:
                import urllib.parse
                parsed_params = dict(urllib.parse.parse_qsl(page.route.split("?", 1)[1]))
                resolved_mat_id = parsed_params.get("mat_id") or parsed_params.get("material_id")
                target_action = parsed_params.get("action")

            if resolved_mat_id:
                # Clean the route immediately to prevent infinite back-to-hub loops
                page.route = "/self-study?offline=true" if is_offline_mode else "/self-study"
                if target_action == "flashcards":
                    return await _start_flashcards([resolved_mat_id])
                elif target_action == "quiz":
                    return await _start_quiz([resolved_mat_id])
                elif target_action == "exam":
                    return await _start_exam([resolved_mat_id])
                else:
                    target_mat = next((m for m in (materials or []) if str(m.get("id")) == str(resolved_mat_id)), None)
                    if target_mat:
                        return await _open_material_cockpit(target_mat, skip_spinner=True)

            if state.get("active_material"):
                target_ui = _build_material_cockpit(state["active_material"], state.get("active_material_cards") or [])
            else:
                target_ui = _build_hub(due_cards or [], materials or [])

            content_socket.opacity = 0
            content_socket.offset = ft.Offset(0, 0.03)
            page.update()
            await asyncio.sleep(0.04)
            content_socket.content = target_ui
            content_socket.opacity = 1
            content_socket.offset = ft.Offset(0, 0)
        except Exception as ex:
            import traceback
            print(f"[_load_hub: build view failed]: {ex}")
            traceback.print_exc()
            content_socket.content = _error_screen(
                "Something went wrong loading your hub.",
                lambda: page.run_task(_load_hub, False, None),
            )
        page.update()

    async def _start_flashcards(material_ids: list | None = None):
        _set_loading("Fetching your due cards…")

        # Offline or missing token
        if state.get("is_offline") or not token:
            from src.local_db import get_offline_due_cards
            cards = get_offline_due_cards(material_ids=material_ids, all_cards=bool(material_ids), page=page)
            if not cards:
                cards = get_offline_due_cards(page=page, all_cards=True)
            if not cards:
                content_socket.content = _nothing_due_screen()
                page.update()
                return
            go_flashcards(cards)
            return

        try:
            cards = await asyncio.wait_for(
                get_due_cards(token, material_ids), timeout=15
            )
            if not cards:
                from src.local_db import get_offline_due_cards
                cards = get_offline_due_cards(material_ids=material_ids, all_cards=True, page=page)
            if not cards:
                content_socket.content = _nothing_due_screen()
                page.update()
                return
            go_flashcards(cards)
        except Exception as ex:
            from src.local_db import get_offline_due_cards
            cards = get_offline_due_cards(material_ids=material_ids, all_cards=True, page=page)
            if cards:
                go_flashcards(cards)
            else:
                content_socket.content = _error_screen(
                    f"Couldn't fetch cards ({type(ex).__name__}).",
                    on_retry=lambda: page.run_task(_start_flashcards),
                )
                page.update()

    async def _start_quiz(material_ids: list | None = None):
        _set_loading("Building your quiz…")

        # Offline or missing token
        if state.get("is_offline") or not token:
            from src.local_db import get_offline_quiz_questions
            questions = get_offline_quiz_questions(material_ids=material_ids, limit=10, page=page)
            if not questions and material_ids:
                questions = get_offline_quiz_questions(page=page, limit=10)
            go_quiz(questions or [])
            return

        try:
            questions = await asyncio.wait_for(
                get_quiz_questions(token, material_ids), timeout=15
            )
            if not questions:
                from src.local_db import get_offline_quiz_questions
                questions = get_offline_quiz_questions(material_ids=material_ids, limit=10, page=page)
            go_quiz(questions or [])
        except Exception as ex:
            from src.local_db import get_offline_quiz_questions
            questions = get_offline_quiz_questions(material_ids=material_ids, limit=10, page=page)
            if questions:
                go_quiz(questions)
            else:
                content_socket.content = _error_screen(
                    f"Couldn't load quiz ({type(ex).__name__}).",
                    on_retry=lambda: page.run_task(_start_quiz),
                )
                page.update()

    async def _start_exam(material_ids: list | None = None):
        _set_loading("Setting up your exam…")

        calc_limit = max(50, len(material_ids) * 45) if material_ids else 50
        # Offline or missing token
        if state.get("is_offline") or not token:
            from src.local_db import get_offline_exam_questions
            result = get_offline_exam_questions(material_ids=material_ids, limit=calc_limit, page=page)
            if not result.get("questions") and material_ids:
                result = get_offline_exam_questions(page=page, limit=calc_limit)
            go_exam(result.get("questions") or [], result.get("duration_seconds"))
            return

        try:
            result = await asyncio.wait_for(
                get_exam_questions(token, material_ids, limit=calc_limit), timeout=15
            )
            if isinstance(result, dict):
                questions = result.get("questions") or []
                duration_seconds = result.get("duration_seconds")
            else:
                questions = result or []
                duration_seconds = None
            if not questions:
                from src.local_db import get_offline_exam_questions
                result = get_offline_exam_questions(material_ids=material_ids, limit=calc_limit, page=page)
                questions = result.get("questions") or []
                duration_seconds = result.get("duration_seconds")
            go_exam(questions, duration_seconds)
        except Exception as ex:
            from src.local_db import get_offline_exam_questions
            result = get_offline_exam_questions(material_ids=material_ids, limit=calc_limit, page=page)
            if result.get("questions"):
                go_exam(result.get("questions"), result.get("duration_seconds"))
            else:
                content_socket.content = _error_screen(
                    f"Couldn't load exam ({type(ex).__name__}).",
                    on_retry=lambda: page.run_task(_start_exam),
                )
                page.update()

    def _nothing_due_screen() -> ft.Container:
        _set_appbar("Flashcards", _exit_study_session)
        is_off = bool(state.get("is_offline"))
        has_active_mat = bool(state.get("active_material"))
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            padding=32,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    ft.Icon(
                        ft.Icons.STYLE_OUTLINED if is_off else ft.Icons.CELEBRATION_ROUNDED,
                        size=52,
                        color=ft.Colors.PRIMARY if is_off else ft.Colors.ORANGE_300,
                    ),
                    ft.Text(
                        "No Flashcards Available Offline" if is_off else "You're all caught up!",
                        size=18,
                        weight=ft.FontWeight.W_700,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    ft.Text(
                        "This study material has no flashcards cached for offline practice.\nConnect to the internet to download it."
                        if is_off
                        else "No cards are due for review right now.\nCheck back later or add new material.",
                        size=13,
                        color=ft.Colors.GREY_400,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.ElevatedButton(
                        "Back to Cockpit" if has_active_mat else "Back to Hub",
                        bgcolor=ft.Colors.PRIMARY,
                        color=ft.Colors.ON_PRIMARY,
                        height=42,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10), elevation=0
                        ),
                        on_click=lambda _: _exit_study_session(),
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
        state["poller_id"] = state.get("poller_id", 0) + 1
        my_poller_id = state["poller_id"]
        while True:
            await asyncio.sleep(4)
            
            # Kill ghost loops if newer poller started or user left self-study
            if my_poller_id != state.get("poller_id"):
                break
            if not page.route or not page.route.startswith("/self-study"):
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
                            
                            def _safe_update(c, val):
                                if c and getattr(c, "page", None):
                                    c.value = val
                                    try:
                                        c.update()
                                    except BaseException:
                                        pass

                            _safe_update(state.get("sidebar_due_text"), f"{new_count} due")
                            _safe_update(state.get("live_due_text"), str(new_count))
                            _safe_update(state.get("live_streak_text"), "Keep your streak going! 🔥" if new_count > 0 else "All caught up for today! ❄️")
                            _safe_update(state.get("live_fc_pill"), f"{new_count} due" if new_count > 0 else "All caught up")
                        except BaseException as ex:
                            if "Control must be added to the page first" not in str(ex):
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
                
                    if banner and getattr(banner, "page", None):
                        try:
                            banner.update()
                        except BaseException:
                            pass
                    
            except BaseException as e:
                if "Control must be added to the page first" not in str(e):
                    print(f"[POLLER] ❌ Error during polling: {type(e).__name__} - {e}")

    # ── hub layout ────────────────────────────────────────────────────────────
    # ── Cockpit & Material Focus Transitions ─────────────────────────────────
    async def _open_material_cockpit(mat: dict, skip_spinner: bool = False):
        state["active_material"] = mat
        state["selected_mat_ids"] = {mat["id"]}
        _refresh_sidebar_materials()
        display_title = format_material_title(mat.get("title", ""))

        # 1. Full view rebuild with clean loading spinner
        if not skip_spinner:
            _set_loading(f"Opening {display_title}…")

        # 2. Fetch scoped due cards for this material
        if state.get("is_offline") or not token:
            from src.local_db import get_offline_due_cards
            scoped_cards = get_offline_due_cards([mat["id"]], all_cards=True, page=page)
        else:
            try:
                scoped_cards = await asyncio.wait_for(
                    get_due_cards(token, [mat["id"]]),
                    timeout=10,
                )
            except Exception:
                from src.local_db import get_offline_due_cards
                scoped_cards = get_offline_due_cards([mat["id"]], all_cards=True, page=page)

        # 3. Restore persisted AI tutor conversation for this material
        try:
            persisted_chat = await get_material_tutor_history(page, mat["id"])
        except Exception:
            persisted_chat = []

        state["active_material_cards"] = scoped_cards or []
        state["material_ai_chat"] = list(persisted_chat) if persisted_chat else []

        # 4. Render Material Study Cockpit
        _set_appbar(display_title, go_hub)
        content_socket.content = _build_material_cockpit(mat, scoped_cards or [])
        _refresh_sidebar_materials()
        page.update()

    async def _back_to_hub(e=None):
        page.route = "/self-study?offline=true" if state.get("is_offline") else "/self-study"
        state["active_material"] = None
        state["selected_mat_ids"] = set()
        _refresh_sidebar_materials()
        _set_loading("Loading Study Hub…")
        await _load_hub()

    def _build_material_cockpit(mat: dict, scoped_cards: list) -> ft.Column:
        mid = mat.get("id")
        mtitle = mat.get("title") or "Untitled Document"
        display_title = format_material_title(mtitle)
        stype = (mat.get("source_type") or "text").lower()
        is_mobile = bool(page.width and page.width < 768)
        is_small = bool(page.width and page.width < 450)
        due_count = len(scoped_cards)

        is_cbt_bundle = (stype == "cbt_bundle" or "combo:" in mtitle.lower() or "bundle" in stype)
        is_cbt_pack = (
            is_cbt_bundle
            or stype in ("cbt", "cbt_pack")
            or "cbt" in stype
            or str(mat.get("source_type", "")).lower() in ("cbt", "cbt_pack")
            or mat.get("is_cbt") is True
            or (due_count == 0 and bool(re.search(r"(?i)\b(JAMB|WAEC|NECO|UTME|WASSCE|SSCE|POST-UTME|SAT|GRE|GMAT|CBT)\b", mtitle)))
        )

        q_count = 0
        if is_cbt_pack:
            try:
                from src.local_db import get_local_db
                db_inst = get_local_db(page)
                r_cnt = db_inst.execute("SELECT COUNT(*) FROM downloaded_study_questions WHERE material_id = ?", (str(mid),)).fetchone()
                if r_cnt and r_cnt[0]:
                    q_count = r_cnt[0]
            except Exception:
                pass
            if q_count == 0 and mat.get("questions_count"):
                try:
                    q_count = int(mat.get("questions_count"))
                except Exception:
                    pass

        if is_cbt_bundle:
            fmt_icon = ft.Icons.AUTO_AWESOME_MOTION_ROUNDED
            fmt_color = ft.Colors.AMBER_600
            fmt_tag = "CBT Exam Combo"
        elif is_cbt_pack:
            fmt_icon = ft.Icons.WORKSPACE_PREMIUM_ROUNDED
            fmt_color = ft.Colors.PRIMARY
            fmt_tag = "Official CBT Exam"
        elif "pdf" in stype or mtitle.lower().endswith(".pdf"):
            fmt_icon = ft.Icons.PICTURE_AS_PDF_ROUNDED
            fmt_color = ft.Colors.RED_500
            fmt_tag = "PDF Document"
        elif "url" in stype:
            fmt_icon = ft.Icons.LINK_ROUNDED
            fmt_color = ft.Colors.TEAL_600
            fmt_tag = "Web / Video"
        else:
            fmt_icon = ft.Icons.DESCRIPTION_ROUNDED
            fmt_color = ft.Colors.BLUE_500
            fmt_tag = "Study Notes"

        mat_status = str(mat.get("status") or "completed").lower()
        is_generating = mat_status in ("processing", "queued", "pending", "in_progress")
        current_status = [mat_status]
        progress_val = [int(mat.get("progress_percent") or (15 if is_generating else 100))]
        stage_val = [str(mat.get("stage") or ("Analyzing material & generating study deck..." if is_generating else "AI Study Engine Ready"))]

        # Top Bar: Status Badge & Refresh Button
        status_badge_icon = ft.Icon(
            ft.Icons.AUTO_AWESOME_ROUNDED if is_generating else ft.Icons.CHECK_CIRCLE_ROUNDED,
            size=12,
            color=ft.Colors.AMBER_800 if is_generating else ft.Colors.GREEN_700,
        )
        status_badge_text = ft.Text(
            f"{progress_val[0]}% Generating" if is_generating else "Engine Ready",
            size=8,
            weight=ft.FontWeight.W_800,
            color=ft.Colors.AMBER_800 if is_generating else ft.Colors.GREEN_700,
        )
        status_badge_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=ft.BorderRadius.all(8),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_700 if is_generating else ft.Colors.GREEN_700),
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[status_badge_icon, status_badge_text],
            ),
        )

        refresh_icon = ft.Icon(ft.Icons.REFRESH_ROUNDED, size=15, color=ft.Colors.PRIMARY)
        refresh_spinner = ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.PRIMARY, visible=False)
        refresh_btn = ft.Container(
            content=ft.Stack(
                alignment=ft.Alignment.CENTER,
                controls=[refresh_icon, refresh_spinner],
            ),
            ink=True,
            border_radius=ft.BorderRadius.all(8),
            padding=ft.Padding.all(6),
            tooltip="Refresh AI Generation Status",
            on_click=lambda _: page.run_task(_on_cockpit_refresh),
        )

        # 1. Top Bar: Back Button, Status Badge, Refresh Button & Format Tag
        back_label = "Back" if is_small or (page.width and page.width < 500) else "Back to Study Hub"

        if is_cbt_pack:
            top_bar_right = [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.12, fmt_color),
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(fmt_icon, size=13, color=fmt_color),
                            ft.Text(fmt_tag.upper(), size=8.5, weight=ft.FontWeight.W_800, color=fmt_color),
                        ],
                    ),
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    icon_color=ft.Colors.RED_400,
                    icon_size=18,
                    tooltip="Remove from Vault",
                    on_click=lambda _: _confirm_delete_material(mat),
                ),
            ]
        else:
            top_bar_right = [
                ft.OutlinedButton(
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=13, color=ft.Colors.PURPLE_600),
                            ft.Text("Generate AI", size=10.5, weight=ft.FontWeight.W_700, color=ft.Colors.PURPLE_700),
                        ],
                    ),
                    style=ft.ButtonStyle(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        side=ft.BorderSide(1, ft.Colors.with_opacity(0.35, ft.Colors.PURPLE_400)),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    tooltip="Generate more flashcards, quizzes or mock exams with AI",
                    on_click=lambda _: _open_generate_panel(mat),
                ),
                status_badge_container,
                refresh_btn,
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.12, fmt_color),
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(fmt_icon, size=13, color=fmt_color),
                            ft.Text(fmt_tag, size=8, weight=ft.FontWeight.W_800, color=fmt_color),
                        ],
                    ),
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    icon_color=ft.Colors.RED_400,
                    icon_size=18,
                    tooltip="Remove from Vault",
                    on_click=lambda _: _confirm_delete_material(mat),
                ),
            ]

        top_bar = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
            spacing=8,
            controls=[
                ft.TextButton(
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=15),
                            ft.Text(back_label, size=12.5, weight=ft.FontWeight.W_700),
                        ],
                    ),
                    on_click=lambda _: page.run_task(_back_to_hub),
                ),
                ft.Row(
                    spacing=6,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=top_bar_right,
                ),
            ],
        )

        # 2. Material Info Banner: accent strip on the left, title, short status pill
        if is_cbt_bundle:
            info_pill_color = ft.Colors.AMBER_600
            info_pill_value = "Multi-Subject CBT Exam Combo"
            info_pill_icon = ft.Icons.AUTO_AWESOME_MOTION_ROUNDED
        elif is_cbt_pack:
            info_pill_color = ft.Colors.PRIMARY
            info_pill_value = f"{q_count} Questions • Timed Simulation Ready" if q_count else "Official CBT Paper Ready"
            info_pill_icon = ft.Icons.VERIFIED_ROUNDED
        elif is_generating:
            info_pill_color = ft.Colors.AMBER_700
            info_pill_value = "Generating study deck…"
            info_pill_icon = ft.Icons.AUTO_AWESOME_ROUNDED
        else:
            info_pill_color = ft.Colors.PURPLE_600
            info_pill_value = f"{due_count} flashcards due" if due_count else "Deck ready"
            info_pill_icon = ft.Icons.STYLE_ROUNDED

        cockpit_info_icon = ft.Icon(
            info_pill_icon,
            size=13,
            color=info_pill_color,
        )
        cockpit_due_text = ft.Text(
            info_pill_value,
            size=11.5,
            weight=ft.FontWeight.W_700,
            color=info_pill_color,
        )
        cockpit_info_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            border_radius=ft.BorderRadius.all(999),
            bgcolor=ft.Colors.with_opacity(0.12, info_pill_color),
            content=ft.Row(
                spacing=6,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[cockpit_info_icon, cockpit_due_text],
            ),
        )
        progress_bar = ft.ProgressBar(
            value=progress_val[0] / 100.0,
            color=ft.Colors.AMBER_600,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
            height=5,
            border_radius=ft.BorderRadius.all(3),
            visible=is_generating,
        )
        stage_text = ft.Text(
            stage_val[0],
            size=11,
            color=ft.Colors.AMBER_700,
            weight=ft.FontWeight.W_600,
            visible=is_generating,
        )

        # The accent strip is a separate positioned control inside a Stack. A single
        # Border with a different colored left side can't be combined with rounded
        # corners, so this keeps the radius clean and the accent flush to the edge.
        info_banner = ft.Container(
            width=float("inf"),
            border_radius=ft.BorderRadius.all(16),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.10, fmt_color),
                    ft.Colors.SURFACE,
                ],
            ),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Stack(
                controls=[
                    ft.Container(
                        width=float("inf"),
                        padding=ft.Padding.only(left=24, right=16, top=16, bottom=16),
                        content=ft.Column(
                            spacing=12,
                            tight=True,
                            controls=[
                                ft.Row(
                                    spacing=12,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Container(
                                            width=44,
                                            height=44,
                                            border_radius=ft.BorderRadius.all(12),
                                            bgcolor=ft.Colors.with_opacity(0.14, fmt_color),
                                            alignment=ft.Alignment.CENTER,
                                            content=ft.Icon(fmt_icon, size=22, color=fmt_color),
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            tight=True,
                                            expand=True,
                                            controls=[
                                                ft.Text(
                                                    fmt_tag.upper(),
                                                    size=9.5,
                                                    weight=ft.FontWeight.W_800,
                                                    color=fmt_color,
                                                ),
                                                ft.Text(
                                                    display_title,
                                                    size=17 if is_mobile else 20,
                                                    weight=ft.FontWeight.W_800,
                                                    color=ft.Colors.ON_SURFACE,
                                                    max_lines=2,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Row(tight=True, controls=[cockpit_info_pill]),
                                progress_bar,
                                stage_text,
                            ],
                        ),
                    ),
                    # Accent strip pinned to the left edge, full height
                    ft.Container(left=0, top=0, bottom=0, width=6, bgcolor=fmt_color),
                ],
            ),
        )

        # 3. Dedicated Study Actions Row
        fc_metric_text = ft.Text(f"{due_count} Due" if due_count else "Deck Ready", size=9.5, weight=ft.FontWeight.W_700, color=ft.Colors.PURPLE_600)

        def _action_card(title, subtitle, metric_ctrl_or_text, icon, color, cta_text, on_click):
            m_ctrl = metric_ctrl_or_text if isinstance(metric_ctrl_or_text, ft.Control) else ft.Text(str(metric_ctrl_or_text), size=9.5, weight=ft.FontWeight.W_700, color=color)
            return ft.Container(
                col={"xs": 12, "sm": 6, "md": 6, "lg": 3},
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(14),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(14),
                ink=True,
                on_click=on_click,
                content=ft.Column(
                    spacing=10,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Container(
                                    width=36,
                                    height=36,
                                    bgcolor=ft.Colors.with_opacity(0.12, color),
                                    border_radius=ft.BorderRadius.all(10),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(icon, size=18, color=color),
                                ),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                    border_radius=ft.BorderRadius.all(6),
                                    bgcolor=ft.Colors.with_opacity(0.08, color),
                                    content=m_ctrl,
                                ),
                            ],
                        ),
                        ft.Column(
                            spacing=2,
                            tight=True,
                            controls=[
                                ft.Text(title, size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                ft.Text(subtitle, size=11, color=ft.Colors.GREY_500, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ],
                        ),
                        ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Text(cta_text, size=11.5, weight=ft.FontWeight.W_700, color=color),
                                ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=14, color=color),
                            ],
                        ),
                    ],
                ),
            )

        if is_cbt_pack:
            # Query longitudinal attempt history for progress tracking
            from src.local_db import get_exam_attempts
            past_attempts = get_exam_attempts(material_id=mid, page=page)
            attempts_info_row = None
            if past_attempts:
                best_pct = max((a.get("percentage") or 0.0) for a in past_attempts)
                last_attempt = past_attempts[-1]
                last_pct = last_attempt.get("percentage") or 0.0
                attempts_info_row = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)),
                    content=ft.Row([
                        ft.Icon(ft.Icons.INSIGHTS_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                        ft.Text(f"{len(past_attempts)} Attempt(s)", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                        ft.Container(width=4),
                        ft.Text(f"Latest: {last_pct:.0f}%", size=11.5, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                        ft.Text("•", size=11, color=ft.Colors.GREY_500),
                        ft.Text(f"Personal Best: {best_pct:.0f}%", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                    ], spacing=6, tight=True, wrap=True, alignment=ft.MainAxisAlignment.START),
                )

            btn_cbt = ft.FilledButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=20),
                    ft.Text("Launch Official CBT Simulation", size=14, weight=ft.FontWeight.W_800),
                ], spacing=8, tight=True, alignment=ft.MainAxisAlignment.CENTER),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.Padding.symmetric(horizontal=24, vertical=16),
                ),
                on_click=lambda _: page.run_task(_start_exam, [mid]),
            )

            actions_bar = ft.Column(
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH if is_mobile else ft.CrossAxisAlignment.START,
                controls=[
                    *( [attempts_info_row] if attempts_info_row else [] ),
                    btn_cbt,
                ],
            )

            study_actions = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(16),
                border=ft.Border.all(1.4, ft.Colors.with_opacity(0.35, ft.Colors.PRIMARY)),
                padding=ft.Padding.all(18),
                content=ft.Column(
                    spacing=14,
                    controls=[
                        ft.Row(
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=44,
                                    height=44,
                                    border_radius=ft.BorderRadius.all(12),
                                    gradient=ft.LinearGradient(
                                        colors=[ft.Colors.PRIMARY, ft.Colors.SECONDARY],
                                        begin=ft.Alignment.TOP_LEFT,
                                        end=ft.Alignment.BOTTOM_RIGHT,
                                    ),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(ft.Icons.SCHOOL_ROUNDED, color=ft.Colors.ON_PRIMARY, size=24),
                                ),
                                ft.Column(
                                    spacing=2,
                                    tight=True,
                                    expand=True,
                                    controls=[
                                        ft.Text("CBT Examination Simulator Mode", size=15, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                        ft.Text("Official timed exam paper with question matrix, dockable calculator & performance analytics", size=12, color=ft.Colors.GREY_500),
                                    ],
                                ),
                            ],
                        ),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        actions_bar,
                    ],
                ),
            )
        else:
            study_actions = ft.ResponsiveRow(
                spacing=10,
                run_spacing=10,
                controls=[
                    _action_card(
                        "Flashcards",
                        "Active recall deck for this material",
                        fc_metric_text,
                        ft.Icons.STYLE_ROUNDED,
                        ft.Colors.PURPLE_600,
                        "Practice Deck",
                        lambda _: page.run_task(_start_flashcards, [mid]),
                    ),
                    _action_card(
                        "Browse Deck",
                        "View all Q&As without testing",
                        "Q&A View",
                        ft.Icons.AUTO_STORIES_ROUNDED,
                        ft.Colors.INDIGO_600,
                        "Inspect Deck",
                        lambda _: open_deck_inspector(page, token, material=mat),
                    ),
                    _action_card(
                        "Quick Quiz",
                        "Targeted comprehension questions",
                        "Instant Check",
                        ft.Icons.BOLT_ROUNDED,
                        ft.Colors.TEAL_600,
                        "Launch Quiz",
                        lambda _: page.run_task(_start_quiz, [mid]),
                    ),
                    _action_card(
                        "Mock Exam",
                        "Timed exam simulation with score report",
                        "Timed Simulator",
                        ft.Icons.TIMER_OUTLINED,
                        ft.Colors.ORANGE_600,
                        "Begin Exam",
                        lambda _: page.run_task(_start_exam, [mid]),
                    ),
                ],
            )

        def _update_cockpit_status_ui(status_data: dict):
            st = str(status_data.get("status") or "completed").lower()
            current_status[0] = st
            gen = bool(status_data.get("is_generating", st in ("processing", "queued", "pending", "in_progress")))
            pct = int(status_data.get("progress_percent") or (100 if not gen else 50))
            stage = str(status_data.get("stage") or ("AI Study Engine Ready" if not gen else "Generating..."))
            fc_count = status_data.get("flashcards_count")

            progress_val[0] = pct
            stage_val[0] = stage

            if gen:
                status_badge_icon.name = ft.Icons.AUTO_AWESOME_ROUNDED
                status_badge_icon.color = ft.Colors.AMBER_800
                status_badge_text.value = f"{pct}% Generating"
                status_badge_text.color = ft.Colors.AMBER_800
                status_badge_container.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_700)

                progress_bar.value = pct / 100.0
                progress_bar.visible = True
                stage_text.value = stage
                stage_text.visible = True
                cockpit_due_text.value = "Generating study deck…"
                cockpit_due_text.color = ft.Colors.AMBER_700
                cockpit_info_icon.name = ft.Icons.AUTO_AWESOME_ROUNDED
                cockpit_info_icon.color = ft.Colors.AMBER_700
                cockpit_info_pill.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_700)
            else:
                status_badge_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                status_badge_icon.color = ft.Colors.GREEN_700
                status_badge_text.value = "Engine Ready"
                status_badge_text.color = ft.Colors.GREEN_700
                status_badge_container.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_700)

                progress_bar.visible = False
                stage_text.visible = False
                ready_cnt = fc_count if fc_count is not None else len(scoped_cards)
                cockpit_due_text.value = f"{ready_cnt} flashcards ready"
                cockpit_due_text.color = ft.Colors.PURPLE_600
                cockpit_info_icon.name = ft.Icons.STYLE_ROUNDED
                cockpit_info_icon.color = ft.Colors.PURPLE_600
                cockpit_info_pill.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_600)

            page.update()

        is_refreshing_status = [False]

        async def _on_cockpit_refresh(e=None):
            if is_refreshing_status[0]:
                return
            is_refreshing_status[0] = True
            refresh_icon.visible = False
            refresh_spinner.visible = True
            page.update()
            try:
                stat_res = await check_generation_status(token, mid)
                if stat_res and not stat_res.get("error"):
                    _update_cockpit_status_ui(stat_res)
                    if not stat_res.get("is_generating") and stat_res.get("status") == "completed":
                        try:
                            fresh_cards = await get_due_cards(token, [mid])
                            state["active_material_cards"] = fresh_cards or []
                            fc_metric_text.value = f"{len(fresh_cards)} Due" if fresh_cards else "Deck Ready"
                        except Exception:
                            pass
                        show_page_snackbar(page, "AI Study Engine is ready!")
                else:
                    show_page_snackbar(page, "Could not refresh status.")
            except Exception as ex:
                print(f"[COCKPIT] Refresh error: {ex}")
            finally:
                refresh_icon.visible = True
                refresh_spinner.visible = False
                is_refreshing_status[0] = False
                page.update()

        async def _auto_poll_cockpit_status():
            while state.get("active_material", {}).get("id") == mid and current_status[0] in ("processing", "queued", "pending", "in_progress"):
                await asyncio.sleep(4)
                if state.get("active_material", {}).get("id") != mid:
                    break
                if is_refreshing_status[0]:
                    continue
                try:
                    stat_res = await check_generation_status(token, mid)
                    if stat_res and not stat_res.get("error"):
                        _update_cockpit_status_ui(stat_res)
                        if not stat_res.get("is_generating") and stat_res.get("status") == "completed":
                            try:
                                fresh_cards = await get_due_cards(token, [mid])
                                state["active_material_cards"] = fresh_cards or []
                                fc_metric_text.value = f"{len(fresh_cards)} Due" if fresh_cards else "Deck Ready"
                            except Exception:
                                pass
                            show_page_snackbar(page, "AI Study Engine is ready!")
                            break
                except Exception:
                    pass

        if is_generating and not is_cbt_pack:
            page.run_task(_auto_poll_cockpit_status)

        # 4. Pedagogical AI Document Tutor
        ai_chat_messages = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, auto_scroll=True)
        ai_input_tf = ft.TextField(
            hint_text=f"Ask a question about {display_title}...",
            border=ft.InputBorder.NONE,
            text_size=13,
            multiline=True,
            min_lines=1,
            max_lines=4,
            expand=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )
        ai_send_btn = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            icon_size=18,
            icon_color=ft.Colors.PRIMARY,
            tooltip="Send question",
        )
        ai_spinner = ft.ProgressRing(width=18, height=18, stroke_width=2.5, color=ft.Colors.PRIMARY, visible=False)

        # Welcome initial bubble from Owl Companion
        welcome_bubble = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
            border_radius=ft.BorderRadius.all(12),
            padding=ft.Padding.all(12),
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Image(src="study_owl_mascot.png", width=26, height=26, fit=ft.BoxFit.CONTAIN),
                    ft.Column(
                        spacing=3,
                        tight=True,
                        expand=True,
                        controls=[
                            ft.Text("Nu Owl", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                            ft.Text(
                                f"I've read through {display_title}! Ask me any questions, or tap a prompt below to test your understanding.",
                                size=12,
                                color=ft.Colors.ON_SURFACE,
                            ),
                        ],
                    ),
                ],
            ),
        )
        ai_chat_messages.controls.append(welcome_bubble)

        async def _launch_external_url(target_url: str):
            try:
                await page.launch_url(target_url)
            except Exception as ex:
                print(f"[STUDY] external launch_url failed: {ex}")

        def _open_youtube_player_overlay(video_url: str, title: str = "Educational Video"):
            clean_url = str(video_url or "").strip()
            if not clean_url:
                return

            is_mob = bool(page.width and page.width < 768)
            screen_w = getattr(page, "width", None) or 360
            screen_h = getattr(page, "height", None) or 640

            if is_mob:
                dialog_w = min(screen_w - 24, 400)
                dialog_h = max(190, min(int(screen_h * 0.38), 240))
            else:
                dialog_w = min(screen_w - 48, 720)
                dialog_h = min(screen_h - 120, 440)

            is_search = is_youtube_search_url(clean_url)
            effective_title = title
            if is_search:
                sq = extract_youtube_search_query(clean_url)
                if sq:
                    effective_title = f"YouTube: {sq}"

            player = AdaptiveVideoPlayer(
                media_url=clean_url,
                title=effective_title,
                autoplay=True,
                border_radius=12,
            )

            def _close_overlay(e=None):
                overlay_dlg.open = False
                page.update()

            overlay_dlg = ft.AlertDialog(
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=18),
                bgcolor="#0A0C10",
                title=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=8,
                            expand=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED_ROUNDED, color=ft.Colors.RED_500, size=20),
                                ft.Text(
                                    effective_title,
                                    size=14,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.WHITE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=4,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
                                    icon_size=18,
                                    icon_color=ft.Colors.GREY_400,
                                    tooltip="Open in YouTube",
                                    on_click=lambda _: page.run_task(_launch_external_url, clean_url),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE_ROUNDED,
                                    icon_size=18,
                                    icon_color=ft.Colors.GREY_400,
                                    tooltip="Close player",
                                    on_click=_close_overlay,
                                ),
                            ],
                        ),
                    ],
                ),
                content=ft.Container(
                    width=dialog_w,
                    height=dialog_h,
                    alignment=ft.Alignment.CENTER,
                    content=player,
                ),
            )

            page.overlay.append(overlay_dlg)
            overlay_dlg.open = True
            page.update()

        async def _open_link(target_url: str):
            try:
                if is_youtube_url(target_url) or is_youtube_search_url(target_url):
                    _open_youtube_player_overlay(target_url, "Recommended Tutorial")
                else:
                    await page.launch_url(target_url)
            except Exception as launch_err:
                print(f"[STUDY] launch_url failed: {launch_err}")

        def _extract_youtube_links(text: str) -> list:
            import re
            if not text:
                return []
            found = []
            seen_urls = set()
            # 1. Match Markdown links [label](url)
            md_matches = re.findall(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", text)
            for label, url in md_matches:
                clean_u = url.strip()
                if ("youtube.com" in clean_u or "youtu.be" in clean_u) and clean_u not in seen_urls:
                    seen_urls.add(clean_u)
                    found.append({"title": label.strip(), "url": clean_u})
            # 2. Match raw YouTube URLs in plain text
            raw_matches = re.findall(r"(https?://(?:www\.|m\.)?(?:youtube\.com/[^\s\)]+|youtu\.be/[a-zA-Z0-9_-]{11}[^\s\)]*))", text)
            for url in raw_matches:
                clean_url = url.rstrip(".,;!?()")
                if clean_url not in seen_urls and ("youtube.com" in clean_url or "youtu.be" in clean_url):
                    seen_urls.add(clean_url)
                    found.append({"title": "Recommended Video Tutorial", "url": clean_url})
            return found

        def _render_youtube_rec_card(label: str, url: str):
            vid_id = extract_youtube_id(url)
            thumb_url = get_youtube_thumbnail_url(vid_id, quality="hq") if vid_id else ""
            is_mob = bool(page.width and page.width < 768)

            return ft.Container(
                margin=ft.Padding.only(top=6),
                border_radius=ft.BorderRadius.all(12),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.RED_400)),
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.RED_50),
                padding=ft.Padding.all(10),
                content=ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        # Thumbnail or play icon
                        ft.Container(
                            width=64 if is_mob else 80,
                            height=36 if is_mob else 45,
                            border_radius=ft.BorderRadius.all(8),
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                            bgcolor=ft.Colors.BLACK,
                            content=ft.Stack(
                                controls=[
                                    ft.Image(
                                        src=thumb_url,
                                        fit=ft.BoxFit.COVER,
                                        width=80,
                                        height=45,
                                        error_content=ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED_ROUNDED, color=ft.Colors.RED_500, size=24),
                                    ) if thumb_url else ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED_ROUNDED, color=ft.Colors.RED_500, size=24),
                                    ft.Container(
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color=ft.Colors.WHITE, size=18),
                                    ),
                                ],
                            ),
                            ink=True,
                            on_click=lambda _: _open_youtube_player_overlay(url, label or "Recommended Tutorial"),
                        ),
                        # Video Info & Actions
                        ft.Column(
                            spacing=4,
                            expand=True,
                            tight=True,
                            controls=[
                                ft.Text(
                                    label or "Recommended YouTube Tutorial",
                                    size=12,
                                    weight=ft.FontWeight.W_700,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Row(
                                    spacing=6,
                                    controls=[
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                            border_radius=ft.BorderRadius.all(6),
                                            bgcolor=ft.Colors.RED_600,
                                            ink=True,
                                            on_click=lambda _: _open_youtube_player_overlay(url, label or "Recommended Tutorial"),
                                            content=ft.Row(
                                                spacing=4,
                                                tight=True,
                                                controls=[
                                                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=13, color=ft.Colors.WHITE),
                                                    ft.Text("Watch in App", size=10.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                                ],
                                            ),
                                        ),
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                            border_radius=ft.BorderRadius.all(6),
                                            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
                                            ink=True,
                                            on_click=lambda _: page.run_task(_launch_external_url, url),
                                            content=ft.Row(
                                                spacing=4,
                                                tight=True,
                                                controls=[
                                                    ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=11, color=ft.Colors.ON_SURFACE),
                                                    ft.Text("YouTube", size=10.5, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                                                ],
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            )

        def _assistant_bubble(reply_text: str):
            yt_links = _extract_youtube_links(reply_text)
            bubble_controls = [
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Image(src="study_owl_mascot.png", width=18, height=18, fit=ft.BoxFit.CONTAIN),
                                ft.Text("Nu-AI Owl Tutor", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                            ],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.COPY_ROUNDED,
                            icon_size=13,
                            tooltip="Copy response",
                            on_click=lambda _, t=reply_text: page.run_task(safe_set_clipboard, page, t),
                        ),
                    ],
                ),
                ft.Markdown(
                    reply_text,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    on_tap_link=lambda e: page.run_task(_open_link, e.data),
                ),
            ]

            for item in yt_links:
                bubble_controls.append(_render_youtube_rec_card(item["title"], item["url"]))

            return ft.Container(
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                border_radius=ft.BorderRadius.all(12),
                padding=ft.Padding.all(12),
                content=ft.Column(
                    spacing=6,
                    tight=True,
                    controls=bubble_controls,
                ),
            )

        # Mobile-safe bubble width calculation
        screen_w = getattr(page, "width", None) or 390
        user_bubble_max_w = min(460, max(200, int(screen_w * 0.74)))

        def _user_bubble(user_text: str):
            bubble_w = min(user_bubble_max_w, max(80, int(len(user_text) * 8.5) + 36))
            return ft.Row(
                alignment=ft.MainAxisAlignment.END,
                controls=[
                    ft.Container(
                        bgcolor=ft.Colors.PRIMARY,
                        border_radius=ft.BorderRadius.all(14),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        width=bubble_w,
                        content=ft.Text(
                            user_text,
                            size=12,
                            color=ft.Colors.WHITE,
                            no_wrap=False,
                            selectable=True,
                        ),
                    ),
                ],
            )

        # Load any existing history for this session
        for msg in state.get("material_ai_chat", []):
            role = msg.get("role")
            text = msg.get("text", "")
            if role == "user":
                ai_chat_messages.controls.append(_user_bubble(text))
            else:
                ai_chat_messages.controls.append(_assistant_bubble(text))

        async def _clear_tutor_chat(e=None):
            await clear_material_tutor_history(page, mid)
            state["material_ai_chat"] = []
            ai_chat_messages.controls.clear()
            ai_chat_messages.controls.append(welcome_bubble)
            page.update()
            show_page_snackbar(page, "AI Tutor chat history cleared.")

        clear_chat_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
            icon_size=15,
            icon_color=ft.Colors.GREY_500,
            tooltip="Clear Chat History",
            on_click=lambda _: page.run_task(_clear_tutor_chat),
        )

        async def _send_ai_query(query_text: str):
            clean_q = (query_text or "").strip()
            if not clean_q or state.get("is_ai_generating"):
                return
            ai_input_tf.value = ""
            state["is_ai_generating"] = True
            ai_send_btn.visible = False
            ai_spinner.visible = True
            page.update()

            # Append user message with bounded mobile width
            state.setdefault("material_ai_chat", []).append({"role": "user", "text": clean_q})
            await append_material_tutor_message(page, mid, "user", clean_q)
            ai_chat_messages.controls.append(_user_bubble(clean_q))

            # Typing indicator bubble
            typing_indicator = ft.Container(
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
                border_radius=ft.BorderRadius.all(12),
                padding=ft.Padding.all(10),
                content=ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.PRIMARY),
                        ft.Text("Thinking and grounding in document…", size=11, color=ft.Colors.GREY_500),
                    ],
                ),
            )
            ai_chat_messages.controls.append(typing_indicator)
            page.update()

            # Call ask_ai_tutor_api
            mat_text = mat.get("content") or mat.get("pasted_text") or mat.get("extracted_text") or display_title
            conv_history = [
                {"role": m["role"], "content": m["text"]}
                for m in state.get("material_ai_chat", [])[:-1]
            ]
            try:
                res = await ask_ai_tutor_api(
                    token=token,
                    query=clean_q,
                    course_title="Self-Study Hub",
                    module_title=display_title,
                    lesson_title=display_title,
                    lesson_content=str(mat_text)[:6000],
                    conversation_history=conv_history,
                    is_assessment=False,
                    material_id=str(mid) if mid else None,
                )
                reply = res.get("reply") or res.get("message") or "I couldn't process that query. Please try again."
            except Exception as ex:
                reply = f"Couldn't reach the AI tutor right now: {ex}"

            # Remove typing indicator and append AI response
            if typing_indicator in ai_chat_messages.controls:
                ai_chat_messages.controls.remove(typing_indicator)
            state["material_ai_chat"].append({"role": "assistant", "text": reply})
            await append_material_tutor_message(page, mid, "assistant", reply)
            ai_chat_messages.controls.append(_assistant_bubble(reply))

            state["is_ai_generating"] = False
            ai_send_btn.visible = True
            ai_spinner.visible = False
            page.update()

        ai_send_btn.on_click = lambda _: page.run_task(_send_ai_query, ai_input_tf.value)
        ai_input_tf.on_submit = lambda _: page.run_task(_send_ai_query, ai_input_tf.value)

        # Quick Prompt Chips
        prompt_chips = [
            ("✨ Summarize concepts", "Please summarize the core concepts and key ideas from this document in concise bullet points."),
            ("🎬 Recommend YouTube Videos", f"Recommend YouTube tutorial videos to master '{display_title}'."),
            ("❓ Quiz me with a question", "Ask me a conceptual question based on this document to test my understanding."),
            ("💡 Explain in simple terms", "Explain the most important idea in this document like I'm a beginner."),
            ("📝 3 key takeaways", "What are the 3 most crucial takeaways or formulas I need to remember from this document?"),
        ]

        chips_row = ft.Row(
            spacing=6,
            scroll=ft.ScrollMode.HIDDEN,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=ft.BorderRadius.all(14),
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY)),
                    ink=True,
                    on_click=lambda _, prompt=p_val: page.run_task(_send_ai_query, prompt),
                    content=ft.Text(p_lbl, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
                )
                for p_lbl, p_val in prompt_chips
            ],
        )

        page_h = getattr(page, "height", None) or 800
        if is_mobile:
            dynamic_chat_h = max(190, min(240, int(page_h * 0.45)))
        else:
            dynamic_chat_h = max(230, min(340, int(page_h * 0.47)))

        tutor_state = {
            "is_minimized": False,
            "is_maximized": False,
        }

        minimized_badge = ft.Container(
            visible=False,
            padding=ft.Padding.symmetric(horizontal=7, vertical=2),
            border_radius=ft.BorderRadius.all(999),
            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
            content=ft.Text("Minimized · Tap to expand", size=7, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
        )

        chat_container = ft.Container(
            height=dynamic_chat_h,
            animate=ft.Animation(220, ft.AnimationCurve.EASE_OUT),
            content=ai_chat_messages,
        )

        if state.get("is_offline"):
            tutor_body = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=16),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=24, color=ft.Colors.AMBER_700),
                        ft.Column(
                            spacing=3,
                            tight=True,
                            expand=True,
                            controls=[
                                ft.Text("AI Tutor Offline", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                ft.Text(
                                    "Document chat and AI coaching require an internet connection. Flashcards, quizzes, and exams remain fully active.",
                                    size=11.5,
                                    color=ft.Colors.GREY_600,
                                ),
                            ],
                        ),
                    ],
                ),
            )
        else:
            tutor_body = ft.Column(
                spacing=10,
                visible=True,
                controls=[
                    chat_container,
                    chips_row,
                    ft.Container(
                        border_radius=ft.BorderRadius.all(12),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ai_input_tf,
                                ai_send_btn,
                                ai_spinner,
                            ],
                        ),
                    ),
                ],
            )

        def _toggle_tutor_minimize(e=None):
            tutor_state["is_minimized"] = not tutor_state["is_minimized"]
            is_min = tutor_state["is_minimized"]

            tutor_body.visible = not is_min
            minimized_badge.visible = is_min
            minimize_btn.icon = ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED if is_min else ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
            minimize_btn.tooltip = "Expand Tutor" if is_min else "Minimize / Collapse Tutor"
            fullscreen_btn.visible = not is_min
            ai_tutor_card.padding = ft.Padding.symmetric(horizontal=16, vertical=10) if is_min else ft.Padding.all(16)
            page.update()

        def _toggle_tutor_maximize(e=None):
            if tutor_state["is_minimized"]:
                tutor_state["is_minimized"] = False
                tutor_body.visible = True
                minimized_badge.visible = False
                minimize_btn.icon = ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
                minimize_btn.tooltip = "Minimize / Collapse Tutor"
                fullscreen_btn.visible = True
                ai_tutor_card.padding = ft.Padding.all(16)

            tutor_state["is_maximized"] = not tutor_state["is_maximized"]
            is_max = tutor_state["is_maximized"]

            fullscreen_btn.icon = ft.Icons.FULLSCREEN_EXIT_ROUNDED if is_max else ft.Icons.FULLSCREEN_ROUNDED
            fullscreen_btn.tooltip = "Exit Fullscreen" if is_max else "Maximize / Focus Mode"

            page_h_now = getattr(page, "height", None) or 800
            if is_max:
                chat_container.height = max(420, min(680, int(page_h_now * 0.72)))
            else:
                chat_container.height = dynamic_chat_h

            page.update()

        minimize_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_UP_ROUNDED,
            icon_size=18,
            icon_color=ft.Colors.GREY_500,
            tooltip="Minimize / Collapse Tutor",
            style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            on_click=_toggle_tutor_minimize,
        )

        fullscreen_btn = ft.IconButton(
            icon=ft.Icons.FULLSCREEN_ROUNDED,
            icon_size=18,
            icon_color=ft.Colors.GREY_500,
            tooltip="Maximize / Focus Mode",
            style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            on_click=_toggle_tutor_maximize,
        )

        ai_tutor_card = ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=ft.BorderRadius.all(16),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            shadow=ft.BoxShadow(
                blur_radius=10,
                color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Container(
                        ink=True,
                        on_click=lambda _: _toggle_tutor_minimize() if tutor_state["is_minimized"] else None,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    expand=True,
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Container(
                                            width=32,
                                            height=32,
                                            border_radius=ft.BorderRadius.all(16),
                                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                            alignment=ft.Alignment.CENTER,
                                            content=ft.Image(src="study_owl_mascot.png", width=22, height=22, fit=ft.BoxFit.CONTAIN),
                                        ),
                                        ft.Column(
                                            spacing=1,
                                            tight=True,
                                            expand=True,
                                            controls=[
                                                ft.Row(
                                                    spacing=6,
                                                    tight=True,
                                                    controls=[
                                                        ft.Text("Study Tutor", size=13.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                                        minimized_badge,
                                                    ],
                                                ),
                                                ft.Text(
                                                    "Grounded educational dialogue with this upload",
                                                    size=8.5,
                                                    color=ft.Colors.GREY_500,
                                                    max_lines=1,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    spacing=2,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        fullscreen_btn,
                                        minimize_btn,
                                        clear_chat_btn,
                                    ],
                                ),
                            ],
                        ),
                    ),
                    tutor_body,
                ],
            ),
        )

        # Trigger initial query if handed off from hero Gemini prompt box (only for non-CBT materials)
        init_q = state.pop("initial_material_query", None)
        if init_q and not is_cbt_pack:
            page.run_task(_send_ai_query, init_q)

        # Helper: CBT Longitudinal Attempt History View
        def _build_cbt_trajectory_view(attempts_list: list):
            if not attempts_list:
                return ft.Container(
                    bgcolor=ft.Colors.SURFACE,
                    border_radius=ft.BorderRadius.all(14),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                    padding=ft.Padding.symmetric(horizontal=20, vertical=24),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.FACT_CHECK_OUTLINED, size=36, color=ft.Colors.GREY_400),
                            ft.Text("No Exam Sittings Recorded Yet", size=13.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                            ft.Text(
                                "Launch the simulation to establish your baseline score and track your trajectory over time.",
                                size=11.5,
                                color=ft.Colors.GREY_500,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                    ),
                )

            attempt_rows = []
            for idx, att in enumerate(reversed(attempts_list), 1):
                pct = att.get("percentage") or 0.0
                sc = att.get("score") or 0
                tot = att.get("total") or 0
                dur = att.get("time_spent_seconds") or 0
                mins, secs = divmod(dur, 60)
                time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
                iso_dt = att.get("attempted_at", "")
                date_str = iso_dt[:10] if iso_dt else "Recent"
                grade = att.get("grade") or ("PASS" if pct >= 50 else "NEEDS REVIEW")

                pct_color = ft.Colors.GREEN_600 if pct >= 70 else (ft.Colors.AMBER_700 if pct >= 50 else ft.Colors.RED_500)

                attempt_rows.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Container(
                                            width=28,
                                            height=28,
                                            border_radius=ft.BorderRadius.all(14),
                                            bgcolor=ft.Colors.with_opacity(0.12, pct_color),
                                            alignment=ft.Alignment.CENTER,
                                            content=ft.Text(f"#{len(attempts_list) - idx + 1}", size=10, weight=ft.FontWeight.W_800, color=pct_color),
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            tight=True,
                                            controls=[
                                                ft.Text(f"{sc}/{tot} Correct ({pct:.1f}%)", size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                                ft.Text(f"{date_str} • Time spent: {time_str}", size=10.5, color=ft.Colors.GREY_500),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                    border_radius=ft.BorderRadius.all(6),
                                    bgcolor=ft.Colors.with_opacity(0.12, pct_color),
                                    content=ft.Text(str(grade).upper(), size=9.5, weight=ft.FontWeight.W_800, color=pct_color),
                                ),
                            ],
                        ),
                    )
                )

            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(14),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(14),
                content=ft.Column(
                    spacing=8,
                    controls=attempt_rows[:5],
                ),
            )

        # Helper: CBT Hotkeys & Instructions Blueprint
        def _build_cbt_blueprint_view():
            hotkeys = [
                ("[N] or [→]", "Next Question"),
                ("[P] or [←]", "Previous Question"),
                ("[A] - [E] or [1]-[5]", "Select Option"),
                ("[F] or [R]", "Flag for Review"),
                ("[C]", "Calculator"),
                ("[S]", "Submit Exam"),
            ]
            chips = [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=5),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=5, vertical=2),
                                border_radius=ft.BorderRadius.all(4),
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                content=ft.Text(hk, size=10, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                            ),
                            ft.Text(desc, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                        ],
                    ),
                )
                for hk, desc in hotkeys
            ]

            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(14),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(14),
                content=ft.Column(
                    spacing=10,
                    controls=[
                        ft.Row(
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.KEYBOARD_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                ft.Text("CBT Terminal Hotkeys & Instructions", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                        ft.Text(
                            "Official examination terminal with mathematical formula markdown support, dockable calculations, and instant option recording.",
                            size=11,
                            color=ft.Colors.GREY_500,
                        ),
                        ft.Row(wrap=True, spacing=8, run_spacing=8, controls=chips),
                    ],
                ),
            )

        if is_cbt_bundle:
            bundle_meta = {}
            try:
                content_str = mat.get("content", "")
                if content_str and content_str.strip().startswith("{"):
                    bundle_meta = json.loads(content_str)
            except Exception:
                bundle_meta = {}

            banner_url = bundle_meta.get("banner_url") or mat.get("banner_url")
            item_ids = bundle_meta.get("item_ids") or []
            item_titles = bundle_meta.get("item_titles") or []

            if banner_url and str(banner_url).strip():
                bundle_hero_header = ft.Container(
                    width=float("inf"),
                    height=160 if is_mobile else 210,
                    border_radius=ft.BorderRadius.all(16),
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    content=ft.Stack(
                        fit=ft.StackFit.EXPAND,
                        controls=[
                            ft.Image(src=banner_url, fit=ft.BoxFit.COVER),
                            ft.Container(
                                gradient=ft.LinearGradient(
                                    begin=ft.Alignment.TOP_CENTER,
                                    end=ft.Alignment.BOTTOM_CENTER,
                                    colors=[
                                        ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
                                        ft.Colors.with_opacity(0.85, ft.Colors.BLACK),
                                    ],
                                ),
                                padding=ft.Padding.all(18),
                                alignment=ft.Alignment.BOTTOM_LEFT,
                                content=ft.Column(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                            border_radius=ft.BorderRadius.all(6),
                                            bgcolor=ft.Colors.AMBER_500,
                                            content=ft.Text("OFFICIAL CBT COMBO", size=9.5, weight=ft.FontWeight.W_900, color=ft.Colors.BLACK),
                                        ),
                                        ft.Text(display_title, size=18 if is_mobile else 22, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                                        ft.Text(f"{len(item_ids)} Subject Papers • Full Multi-Subject Sequential Sitting", size=11.5, color=ft.Colors.WHITE70),
                                    ],
                                ),
                            ),
                        ],
                    ),
                )
            else:
                bundle_hero_header = info_banner

            btn_seq_launch = ft.FilledButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED_ROUNDED, size=22),
                    ft.Text("Launch Full Sequential Sitting", size=14.5, weight=ft.FontWeight.W_900),
                ], spacing=8, tight=True, alignment=ft.MainAxisAlignment.CENTER),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.Padding.symmetric(horizontal=24, vertical=16),
                ),
                on_click=lambda _: page.run_task(_start_exam, item_ids if item_ids else [mid]),
            )

            bundle_launch_card = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(16),
                border=ft.Border.all(1.4, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_600)),
                padding=ft.Padding.all(18),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=44,
                                    height=44,
                                    border_radius=ft.BorderRadius.all(12),
                                    gradient=ft.LinearGradient(
                                        colors=[ft.Colors.AMBER_600, ft.Colors.ORANGE_700],
                                        begin=ft.Alignment.TOP_LEFT,
                                        end=ft.Alignment.BOTTOM_RIGHT,
                                    ),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(ft.Icons.AUTO_AWESOME_MOTION_ROUNDED, color=ft.Colors.WHITE, size=24),
                                ),
                                ft.Column(
                                    spacing=2,
                                    tight=True,
                                    expand=True,
                                    controls=[
                                        ft.Text("Sequential Examination Simulation", size=15, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                        ft.Text("Sit all constituent subject exams in a single continuous timed sitting with subject switcher tabs", size=11.5, color=ft.Colors.GREY_500),
                                    ],
                                ),
                            ],
                        ),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        btn_seq_launch,
                    ],
                ),
            )

            subject_cards = []
            for s_id, s_title in (zip(item_ids, item_titles) if (item_ids and item_titles) else [(mid, display_title)]):
                clean_s_title = clean_pack_import_tag(format_material_title(s_title))
                subject_cards.append(
                    ft.Container(
                        bgcolor=ft.Colors.SURFACE,
                        border_radius=ft.BorderRadius.all(12),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Icon(ft.Icons.DESCRIPTION_ROUNDED, size=20, color=ft.Colors.PRIMARY),
                                        ft.Column(
                                            spacing=2,
                                            tight=True,
                                            controls=[
                                                ft.Text(clean_s_title, size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                                ft.Text("Individual Examination Paper", size=11, color=ft.Colors.GREY_500),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.OutlinedButton(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=14),
                                        ft.Text("Practice Subject", size=11.5, weight=ft.FontWeight.W_700),
                                    ], spacing=4, tight=True),
                                    on_click=lambda _, i=s_id: page.run_task(_start_exam, [i]),
                                    style=ft.ButtonStyle(
                                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                    ),
                                ),
                            ],
                        ),
                    )
                )

            constituent_section = ft.Column(spacing=8, controls=subject_cards)

            from src.local_db import get_exam_attempts
            past_attempts = get_exam_attempts(material_id=mid, page=page)

            return ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=0,
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(
                            horizontal=14 if is_small else 24,
                            vertical=16,
                        ),
                        content=ft.Column(
                            spacing=16,
                            controls=[
                                top_bar,
                                bundle_hero_header,
                                _section_label("SEQUENTIAL SITTING"),
                                bundle_launch_card,
                                _section_label("CONSTITUENT EXAM PAPERS"),
                                constituent_section,
                                _section_label("ATTEMPT HISTORY & SCORE TRAJECTORY"),
                                _build_cbt_trajectory_view(past_attempts),
                                _section_label("EXAMINATION BLUEPRINT & HOTKEYS"),
                                _build_cbt_blueprint_view(),
                                ft.Container(height=32),
                            ],
                        ),
                    ),
                ],
            )
        elif is_cbt_pack:
            from src.local_db import get_exam_attempts
            past_attempts = get_exam_attempts(material_id=mid, page=page)
            return ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=0,
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(
                            horizontal=14 if is_small else 24,
                            vertical=16,
                        ),
                        content=ft.Column(
                            spacing=16,
                            controls=[
                                top_bar,
                                info_banner,
                                _section_label("CBT EXAMINATION TERMINAL"),
                                study_actions,
                                _section_label("ATTEMPT HISTORY & SCORE TRAJECTORY"),
                                _build_cbt_trajectory_view(past_attempts),
                                _section_label("EXAMINATION BLUEPRINT & HOTKEYS"),
                                _build_cbt_blueprint_view(),
                                ft.Container(height=32),
                            ],
                        ),
                    ),
                ],
            )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(
                        horizontal=14 if is_small else 24,
                        vertical=16,
                    ),
                    content=ft.Column(
                        spacing=16,
                        controls=[
                            top_bar,
                            info_banner,
                            _section_label("PRACTICE & SIMULATION"),
                            study_actions,
                            _section_label("SOCRATIC AI TUTOR"),
                            ai_tutor_card,
                            ft.Container(height=32),
                        ],
                    ),
                ),
            ],
        )

    # ── hub layout ────────────────────────────────────────────────────────────
    def _build_hub(due_cards: list, materials: list) -> ft.Column:
        due_count = len(due_cards)
        is_mobile = bool(page.width and page.width < 768)
        is_small = bool(page.width and page.width < 450)

        # Poller references kept safely in state for background poller updates
        state["live_due_text"] = ft.Text(str(due_count), visible=False)
        state["live_streak_text"] = ft.Text("", visible=False)
        state["live_fc_pill"] = ft.Text(f"{due_count} due", visible=False)
        state["update_hero_responsive"] = lambda: None

        # 1. Hero Mascot & Title ("What shall we Study?")
        mascot_img = ft.Image(
            src="study_owl_mascot.png",
            width=92 if is_small else (102 if is_mobile else 114),
            height=92 if is_small else (102 if is_mobile else 114),
            fit=ft.BoxFit.CONTAIN,
        )

        title_header = ft.Column(
            spacing=2,
            tight=True,
            controls=[
                ft.Text(
                    "What shall we",
                    size=16 if is_small else (18 if is_mobile else 20),
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.with_opacity(0.85, ft.Colors.ON_SURFACE),
                ),
                ft.Text(
                    "Study?",
                    size=28 if is_small else (32 if is_mobile else 38),
                    weight=ft.FontWeight.W_900,
                    color=ft.Colors.ON_SURFACE,
                ),
            ],
        )

        hero_row = ft.Row(
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16 if is_mobile else 20,
            controls=[
                mascot_img,
                title_header,
            ],
        )

        # 2. Gemini-on-Chrome Style Grounded Prompt Box
        gemini_selected = {"mat": materials[0] if materials else None}

        # Dynamic material chip & send button
        gemini_chip_icon = ft.Icon(
            ft.Icons.DESCRIPTION_ROUNDED if gemini_selected["mat"] else ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
            size=14,
            color=ft.Colors.PRIMARY if gemini_selected["mat"] else ft.Colors.AMBER_800,
        )
        gemini_chip_label = ft.Text(
            format_material_title(gemini_selected["mat"]["title"]) if gemini_selected["mat"] else "Select Study Material *",
            size=11.5,
            weight=ft.FontWeight.W_700,
            color=ft.Colors.PRIMARY if gemini_selected["mat"] else ft.Colors.AMBER_900,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        gemini_chip_arrow = ft.Icon(
            ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
            size=14,
            color=ft.Colors.PRIMARY if gemini_selected["mat"] else ft.Colors.AMBER_800,
        )

        def _open_material_picker_sheet():
            if not materials:
                _open_upload_modal(initial_mode="file")
                return

            def _select_mat(m):
                gemini_selected["mat"] = m
                _update_gemini_ui()
                sheet.open = False
                page.update()

            sheet = ft.BottomSheet(
                content=ft.Container(
                    padding=ft.Padding.symmetric(horizontal=18, vertical=16),
                    bgcolor=ft.Colors.SURFACE,
                    border_radius=ft.BorderRadius.all(18),
                    content=ft.Column(
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.ATTACH_FILE_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                                            ft.Text("Select Material for AI Grounding", size=15, weight=ft.FontWeight.W_800),
                                        ],
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.CLOSE_ROUNDED,
                                        icon_size=18,
                                        on_click=lambda _: (setattr(sheet, "open", False), page.update()),
                                    ),
                                ],
                            ),
                            ft.Text("Choose which note or document your AI tutor should analyze and reference:", size=11.5, color=ft.Colors.GREY_600),
                            ft.Container(
                                height=min(len(materials) * 56 + 10, 260),
                                content=ft.Column(
                                    scroll=ft.ScrollMode.AUTO,
                                    controls=[
                                        ft.ListTile(
                                            leading=ft.Icon(
                                                ft.Icons.CHECK_CIRCLE_ROUNDED if gemini_selected.get("mat") and gemini_selected["mat"].get("id") == m.get("id") else ft.Icons.DESCRIPTION_OUTLINED,
                                                color=ft.Colors.PRIMARY if gemini_selected.get("mat") and gemini_selected["mat"].get("id") == m.get("id") else ft.Colors.GREY_600,
                                            ),
                                            title=ft.Text(format_material_title(m.get("title", "Untitled")), size=13, weight=ft.FontWeight.W_700),
                                            subtitle=ft.Text(f"Source: {(m.get('source_type') or 'text').upper()}", size=11, color=ft.Colors.GREY_500),
                                            on_click=lambda _, mat_obj=m: _select_mat(mat_obj),
                                        )
                                        for m in materials
                                    ],
                                ),
                            ),
                        ],
                    ),
                )
            )
            page.overlay.append(sheet)
            sheet.open = True
            page.update()

        gemini_chip_container = ft.Container(
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY if gemini_selected["mat"] else ft.Colors.AMBER_400),
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            ink=True,
            on_click=lambda _: _open_material_picker_sheet(),
            content=ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    gemini_chip_icon,
                    gemini_chip_label,
                    gemini_chip_arrow,
                ],
            ),
        )

        gemini_send_icon = ft.IconButton(
            icon=ft.Icons.ARROW_UPWARD_ROUNDED,
            icon_size=16,
            icon_color=ft.Colors.WHITE if gemini_selected["mat"] else ft.Colors.GREY_400,
            bgcolor=ft.Colors.PRIMARY if gemini_selected["mat"] else ft.Colors.with_opacity(0.12, ft.Colors.GREY_400),
            disabled=gemini_selected["mat"] is None,
            tooltip="Send to AI Tutor" if gemini_selected["mat"] else "Select a study material above to enable AI",
            on_click=lambda _: _on_submit_gemini_query(),
        )

    

        def _update_gemini_ui():
            has_mat = gemini_selected.get("mat") is not None
            if has_mat:
                m_title = format_material_title(gemini_selected["mat"].get("title", ""))
                gemini_chip_icon.name = ft.Icons.DESCRIPTION_ROUNDED
                gemini_chip_icon.color = ft.Colors.PRIMARY
                gemini_chip_label.value = m_title
                gemini_chip_label.color = ft.Colors.PRIMARY
                gemini_chip_arrow.color = ft.Colors.PRIMARY
                gemini_chip_container.bgcolor = ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY)
                gemini_send_icon.disabled = False
                gemini_send_icon.icon_color = ft.Colors.WHITE
                gemini_send_icon.bgcolor = ft.Colors.PRIMARY
                gemini_send_icon.tooltip = "Send to AI Tutor"
            else:
                gemini_chip_icon.name = ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED
                gemini_chip_icon.color = ft.Colors.AMBER_800
                gemini_chip_label.value = "Select Study Material *"
                gemini_chip_label.color = ft.Colors.AMBER_900
                gemini_chip_arrow.color = ft.Colors.AMBER_800
                gemini_chip_container.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.AMBER_300)
                gemini_send_icon.disabled = True
                gemini_send_icon.icon_color = ft.Colors.GREY_400
                gemini_send_icon.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.GREY_400)
                gemini_send_icon.tooltip = "Select a study material above to enable AI"
            page.update()

        def _on_submit_gemini_query():
            if not gemini_selected.get("mat"):
                show_page_snackbar(page, "Please select a study material first!")
                return
            clean_q = (gemini_tf.value or "").strip()
            if not clean_q:
                clean_q = "Summarize the key concepts and quiz my understanding of this document."
            state["initial_material_query"] = clean_q
            page.run_task(_open_material_cockpit, gemini_selected["mat"])

        gemini_tf = ft.TextField(
            hint_text="Ask Nu-AI about this document, summarize key concepts, or quiz me…",
            border=ft.InputBorder.NONE,
            multiline=True,
            min_lines=2,
            max_lines=3,
            text_size=12.5 if is_small else 13,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            on_submit=lambda _: _on_submit_gemini_query(),
            expand=True
        )

        gemini_box = ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=ft.BorderRadius.all(18),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY)),
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=4,
                tight=True,
                controls=[
                    # Attachment Chip row at the top (Gemini on Chrome style)
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=6,
                                tight=True,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text("Grounding:", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600),
                                    gemini_chip_container,
                                ],
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=ft.BorderRadius.all(8),
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=11, color=ft.Colors.PRIMARY),
                                        ft.Text("Nu-AI", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                                    ],
                                ),
                            ),
                        ],
                    ),
                    gemini_tf,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            gemini_send_icon,
                        ],
                    ),
                ],
            ),
        )

        if state.get("is_offline"):
            offline_hub_banner = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(18),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.AMBER)),
                padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                shadow=ft.BoxShadow(
                    blur_radius=12,
                    color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                    offset=ft.Offset(0, 3),
                ),
                content=ft.Column(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    tight=True,
                                    controls=[
                                        ft.Container(
                                            width=32,
                                            height=32,
                                            border_radius=ft.BorderRadius.all(8),
                                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER),
                                            alignment=ft.Alignment.CENTER,
                                            content=ft.Icon(ft.Icons.CLOUD_OFF_ROUNDED, size=18, color=ft.Colors.AMBER_700),
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            tight=True,
                                            controls=[
                                                ft.Text("Offline Vault Active", size=13.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                                ft.Text("Flashcards, Quizzes & Exams work offline", size=11, color=ft.Colors.GREY_600),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.ElevatedButton(
                                    content=ft.Row(
                                        spacing=5,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.FOLDER_SPECIAL_ROUNDED, size=13, color=ft.Colors.WHITE),
                                            ft.Text("Offline Library", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                        ],
                                    ),
                                    bgcolor=ft.Colors.PRIMARY,
                                    height=32,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                                    on_click=lambda _: page.go("/offline"),
                                ),
                            ],
                        ),
                    ],
                ),
            )
            top_box = offline_hub_banner
        else:
            top_box = gemini_box

        if is_mobile:
            hero_section = ft.Column(
                spacing=14,
                controls=[
                    hero_row,
                    top_box,
                ],
            )
        else:
            hero_section = ft.Row(
                spacing=20,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(content=hero_row, width=280),
                    ft.Container(content=top_box, expand=True),
                ],
            )

        # 3. Quick Action Grid (2 rows x 3 columns)
        def _open_more_sheet():
            sheet = ft.BottomSheet(
                content=ft.Container(
                    padding=ft.Padding.all(20),
                    bgcolor=ft.Colors.SURFACE,
                    border_radius=ft.BorderRadius.all(18),
                    content=ft.Column(
                        spacing=12,
                        tight=True,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("More Study Options", size=16, weight=ft.FontWeight.W_800),
                                    ft.IconButton(
                                        icon=ft.Icons.CLOSE_ROUNDED,
                                        icon_size=18,
                                        on_click=lambda _: (setattr(sheet, "open", False), page.update()),
                                    ),
                                ],
                            ),
                            ft.ListTile(
                                leading=ft.Icon(ft.Icons.BOLT_ROUNDED, color=ft.Colors.TEAL_600),
                                title=ft.Text("Quick Quiz", weight=ft.FontWeight.W_700),
                                subtitle=ft.Text("Instant bite-sized comprehension drills (Offline Ready)"),
                                on_click=lambda _: (setattr(sheet, "open", False), page.update(), page.run_task(_start_quiz, _current_selected_ids())),
                            ),
                            ft.ListTile(
                                leading=ft.Icon(ft.Icons.TIMER_OUTLINED, color=ft.Colors.ORANGE_600),
                                title=ft.Text("Exam Simulator", weight=ft.FontWeight.W_700),
                                subtitle=ft.Text("Timed mock exam with detailed score report (Offline Ready)"),
                                on_click=lambda _: (setattr(sheet, "open", False), page.update(), page.run_task(_start_exam, _current_selected_ids())),
                            ),
                            ft.ListTile(
                                leading=ft.Icon(ft.Icons.STOREFRONT_ROUNDED, color=ft.Colors.PURPLE_600),
                                visible=False,
                                title=ft.Text("Store & Quotas", weight=ft.FontWeight.W_700),
                                subtitle=ft.Text("Upgrade plans or get non-expiring AI generation packs"),
                                on_click=lambda _: (setattr(sheet, "open", False), page.update(), page.go("/store")),
                            ),
                            ft.ListTile(
                                leading=ft.Icon(ft.Icons.FOLDER_SPECIAL_ROUNDED, color=ft.Colors.PRIMARY),
                                title=ft.Text("Manage Vault", weight=ft.FontWeight.W_700),
                                subtitle=ft.Text("View all uploaded materials and filter topics"),
                                on_click=lambda _: (setattr(sheet, "open", False), page.update(), _toggle_sidebar(None)),
                            ),
                        ],
                    ),
                )
            )
            page.overlay.append(sheet)
            sheet.open = True
            page.update()

        def _quick_action_btn(icon, label, on_click, disabled=False, tooltip=None):
            return ft.Container(
                col={"xs": 4, "sm": 4, "md": 4},
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(16),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.symmetric(horizontal=8 if is_small else 12, vertical=12 if is_small else 14),
                ink=not disabled,
                opacity=0.45 if disabled else 1.0,
                on_click=None if disabled else on_click,
                tooltip=tooltip,
                shadow=ft.BoxShadow(
                    blur_radius=6,
                    color=ft.Colors.with_opacity(0.02, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6 if is_small else 8,
                    controls=[
                        ft.Icon(icon, size=16 if is_small else 18, color=ft.Colors.ON_SURFACE),
                        ft.Text(label, size=11.5 if is_small else 12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                    ],
                ),
            )

        is_hub_offline = bool(state.get("is_offline"))
        offline_prompt_msg = "Requires an active internet connection. Flashcards, quizzes, and exams are ready offline."

        def _guard_offline_action(fn):
            if is_hub_offline:
                show_page_snackbar(page, offline_prompt_msg)
            else:
                fn()

        quick_actions_grid = ft.ResponsiveRow(
            spacing=8 if is_small else 10,
            run_spacing=8 if is_small else 10,
            controls=[
                _quick_action_btn(
                    ft.Icons.ARROW_UPWARD_ROUNDED, "Upload",
                    lambda _: _guard_offline_action(lambda: _open_upload_modal(initial_mode="file")),
                    disabled=is_hub_offline,
                    tooltip=offline_prompt_msg if is_hub_offline else "Upload notes or slides",
                ),
                _quick_action_btn(
                    ft.Icons.CAMERA_ALT_OUTLINED, "Photo",
                    lambda _: _guard_offline_action(lambda: _open_upload_modal(initial_mode="photo")),
                    disabled=is_hub_offline,
                    tooltip=offline_prompt_msg if is_hub_offline else "Scan lecture photo or whiteboard",
                ),
                _quick_action_btn(
                    ft.Icons.FOLDER_OUTLINED, "Deck",
                    lambda _: page.run_task(_start_flashcards, _current_selected_ids()),
                    tooltip="Study flashcard decks (Offline Ready)",
                ),
                _quick_action_btn(
                    ft.Icons.PLAY_CIRCLE_OUTLINE_ROUNDED, "YouTube",
                    lambda _: _guard_offline_action(lambda: _open_youtube_modal()),
                    disabled=is_hub_offline,
                    tooltip=offline_prompt_msg if is_hub_offline else "Import educational YouTube video",
                ),
                _quick_action_btn(
                    ft.Icons.DESCRIPTION_OUTLINED, "Paste",
                    lambda _: _guard_offline_action(lambda: _open_upload_modal(initial_mode="paste")),
                    disabled=is_hub_offline,
                    tooltip=offline_prompt_msg if is_hub_offline else "Paste study text or transcript",
                ),
                _quick_action_btn(
                    ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, "More",
                    lambda _: _open_more_sheet(),
                    tooltip="Quick Quiz, Exam Sim & options",
                ),
            ],
        )

        pack_hub_banner = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            border_radius=ft.BorderRadius.all(14),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            ink=True,
            on_click=lambda _: go_marketplace(),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.all(8),
                                border_radius=ft.BorderRadius.all(10),
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                content=ft.Icon(ft.Icons.STOREFRONT_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                            ),
                            ft.Column(
                                spacing=2,
                                tight=True,
                                controls=[
                                    ft.Row(
                                        spacing=6,
                                        controls=[
                                            ft.Text("Get Curated Study Packs from Peers", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=5, vertical=1.5),
                                                border_radius=ft.BorderRadius.all(5),
                                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER),
                                                content=ft.Text("EARN COINS", size=6.5, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_400),
                                            ),
                                        ],
                                    ),
                                    ft.Text("Download curated study items", size=11, color=ft.Colors.GREY_500),
                                ],
                            ),
                        ],
                    ),
                    ft.Icon(ft.Icons.ARROW_FORWARD_IOS_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                ],
            ),
        )

        from src.local_db import is_study_material_downloaded, delete_offline_study_material
        from src.download_manager import download_study_material

        async def _download_mat_offline(m: dict, btn_ref: ft.IconButton | None = None, badge_info: tuple | None = None):
            nonlocal token
            curr_token = token or (await page.shared_preferences.get("auth_token"))
            if not curr_token:
                show_page_snackbar(page, "Please connect online to download study materials.")
                return
            token = curr_token
            mid = str(m.get("id"))
            m_title = format_material_title(m.get("title", ""))

            if btn_ref:
                btn_ref.disabled = True
                btn_ref.icon = ft.Icons.HOURGLASS_EMPTY_ROUNDED
                btn_ref.tooltip = "Downloading…"
                try:
                    btn_ref.update()
                except Exception:
                    page.update()

            show_page_snackbar(page, f"Downloading '{m_title}' for offline use…")
            ok = await download_study_material(page, curr_token, m)
            if ok:
                show_page_snackbar(page, f"Saved '{m_title}' for offline study!")
                if btn_ref:
                    btn_ref.disabled = False
                    btn_ref.icon = ft.Icons.OFFLINE_PIN_ROUNDED
                    btn_ref.icon_color = ft.Colors.GREEN_600
                    btn_ref.tooltip = "Saved offline (tap to remove offline copy)"
                    btn_ref.on_click = lambda e, mat=m: page.run_task(_remove_mat_offline, mat, btn_ref, badge_info)
                    try:
                        btn_ref.update()
                    except Exception:
                        pass
                if badge_info and badge_info[0]:
                    b_cont, b_icon, b_txt = badge_info
                    b_cont.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.GREEN)
                    b_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                    b_icon.color = ft.Colors.GREEN_700
                    b_txt.value = "Offline"
                    b_txt.color = ft.Colors.GREEN_700
                    try:
                        b_cont.update()
                    except Exception:
                        pass
            else:
                if btn_ref:
                    btn_ref.disabled = False
                    btn_ref.icon = ft.Icons.FILE_DOWNLOAD_OUTLINED
                    btn_ref.tooltip = "Save for offline study"
                    try:
                        btn_ref.update()
                    except Exception:
                        pass
                show_page_snackbar(page, f"Failed to download '{m_title}'. Please verify your connection.")

        async def _remove_mat_offline(m: dict, btn_ref: ft.IconButton | None = None, badge_info: tuple | None = None):
            mid = str(m.get("id"))
            if btn_ref:
                btn_ref.disabled = True
                btn_ref.icon = ft.Icons.HOURGLASS_EMPTY_ROUNDED
                btn_ref.tooltip = "Removing…"
                try:
                    btn_ref.update()
                except Exception:
                    pass

            delete_offline_study_material(mid, page=page)
            show_page_snackbar(page, f"Removed offline copy of '{format_material_title(m.get('title', ''))}'.")

            if btn_ref:
                btn_ref.disabled = False
                btn_ref.icon = ft.Icons.FILE_DOWNLOAD_OUTLINED
                btn_ref.icon_color = ft.Colors.GREY_600
                btn_ref.tooltip = "Save for offline study"
                btn_ref.on_click = lambda e, mat=m: page.run_task(_download_mat_offline, mat, btn_ref, badge_info)
                try:
                    btn_ref.update()
                except Exception:
                    pass
            if badge_info and badge_info[0]:
                b_cont, b_icon, b_txt = badge_info
                b_cont.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.GREY_400)
                b_icon.name = ft.Icons.CLOUD_QUEUE_ROUNDED
                b_icon.color = ft.Colors.GREY_600
                b_txt.value = "Cloud"
                b_txt.color = ft.Colors.GREY_600
                try:
                    b_cont.update()
                except Exception:
                    pass

        async def _share_material_with_partner(mat_item):
            if not token:
                show_page_snackbar(page, "Please log in to share study packs!")
                return
            p_res = await get_active_partnership(token)
            if p_res.get("is_offline"):
                show_page_snackbar(page, "You are currently offline. Connect to the internet to share study packs!")
                return
            if not p_res or not p_res.get("has_partnership"):
                show_page_snackbar(page, "Pair up with a study partner first to share packs! Go to Study Network to connect.")
                return

            partnerships = p_res.get("partnerships") or ([p_res.get("partnership")] if p_res.get("partnership") else [])
            if not partnerships:
                show_page_snackbar(page, "No active Duo Streaks found. Connect with a study partner in the Study Network!")
                return

            pack_id = mat_item.get("pack_id") or mat_item.get("id")
            pack_title = clean_pack_import_tag(format_material_title(mat_item.get("title") or "Study Pack"))

            share_dlg = [None]
            def _close_dlg(e=None):
                if share_dlg[0]:
                    share_dlg[0].open = False
                    page.update()

            partners_col = ft.Column(spacing=10, tight=True, scroll=ft.ScrollMode.AUTO)
            for p_item in partnerships:
                p_id = str(p_item.get("id") or "")
                p_info = p_item.get("partner", {})
                p_first = p_info.get("first_name", "Partner")
                p_full = f"{p_first} {p_info.get('last_name', '')}".strip()
                p_streak = p_item.get("duo_streak", 0)
                p_exam = p_item.get("target_exam") or "General Exam"
                p_uni = p_info.get("university") or ""
                p_initials = f"{p_first[:1]}{(p_info.get('last_name') or '')[:1]}".upper()

                action_btn = ft.ElevatedButton(
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.SEND_ROUNDED, size=13, color=ft.Colors.WHITE),
                            ft.Text("Share", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                        ],
                    ),
                    bgcolor=ft.Colors.PRIMARY,
                    height=32,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                )

                async def _do_send_share(partner_id=p_id, partner_name=p_first, btn_ref=action_btn):
                    btn_ref.disabled = True
                    btn_ref.content = ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.WHITE)
                    page.update()
                    res = await share_study_pack_api(token, partner_id, str(pack_id))
                    if res.get("status") == "success":
                        show_page_snackbar(page, f"Shared '{pack_title[:22]}' with {partner_name}! 🎉 +20🪙 on accept")
                        _close_dlg()
                    else:
                        show_page_snackbar(page, res.get("error", "Failed to share study pack."))
                        btn_ref.disabled = False
                        btn_ref.content = ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.SEND_ROUNDED, size=13, color=ft.Colors.WHITE),
                                ft.Text("Share", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                            ],
                        )
                        page.update()

                action_btn.on_click = (lambda pid=p_id, pn=p_first, b=action_btn: lambda _: page.run_task(_do_send_share, pid, pn, b))()

                partners_col.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    tight=True,
                                    expand=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.CircleAvatar(
                                            content=ft.Text(p_initials, size=12, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                            radius=18,
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            tight=True,
                                            expand=True,
                                            controls=[
                                                ft.Text(p_full, size=13, weight=ft.FontWeight.W_700, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                                ft.Row(
                                                    spacing=8,
                                                    tight=True,
                                                    controls=[
                                                        ft.Container(
                                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                            border_radius=ft.BorderRadius.all(6),
                                                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ORANGE),
                                                            content=ft.Text(f"🔥 {p_streak}d streak", size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.ORANGE_800),
                                                        ),
                                                        ft.Text(f"🎯 {p_exam}", size=10, color=ft.Colors.GREY_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                                    ],
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                action_btn,
                            ],
                        ),
                    )
                )

            share_dlg[0] = ft.AlertDialog(
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=18),
                bgcolor=ft.Colors.SURFACE,
                title=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_SHARED_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                                ft.Text("Share Study Pack", size=15, weight=ft.FontWeight.W_800),
                            ],
                        ),
                        ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=_close_dlg),
                    ],
                ),
                content=ft.Container(
                    width=460,
                    content=ft.Column(
                        spacing=12,
                        tight=True,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                border_radius=ft.BorderRadius.all(10),
                                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                                content=ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                        ft.Text(f"Sharing: {pack_title}", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                                    ],
                                ),
                            ),
                            ft.Text("Choose which Duo Streak partner to share this pack with:", size=11.5, color=ft.Colors.GREY_500),
                            ft.Container(
                                height=min(320, max(80, len(partnerships) * 72)),
                                content=partners_col,
                            ),
                        ],
                    ),
                ),
                actions=[ft.TextButton("Cancel", on_click=_close_dlg)],
            )
            page.overlay.append(share_dlg[0])
            share_dlg[0].open = True
            page.update()

        def _render_jump_card(mat: dict):
            mtitle = mat.get("title") or "Untitled Document"
            display_title = clean_pack_import_tag(format_material_title(mtitle)) or "Study Pack"
            stype = (mat.get("source_type") or "text").lower()
            mid = str(mat.get("id"))
            is_downloaded = is_study_material_downloaded(mid, page=page)

            is_cbt_bundle = (stype == "cbt_bundle" or "combo:" in mtitle.lower() or "bundle" in stype)
            is_cbt = (
                is_cbt_bundle
                or stype in ("cbt", "cbt_pack")
                or "cbt" in stype
                or mat.get("is_cbt") is True
                or bool(re.search(r"(?i)\b(CBT|JAMB|WAEC|NECO|UTME|WASSCE|SSCE|POST-UTME|SAT|GRE|GMAT)\b", mtitle))
            )
            is_pack = (stype == "pack_import") and not is_cbt

            if is_cbt_bundle:
                sub_label = "🏆 CBT Exam Combo"
                badge_color = ft.Colors.AMBER_600
                badge_icon = ft.Icons.AUTO_AWESOME_MOTION_ROUNDED
            elif is_cbt:
                sub_label = "🎯 CBT Exam"
                badge_color = ft.Colors.INDIGO_900
                badge_icon = ft.Icons.WORKSPACE_PREMIUM_ROUNDED
            elif is_pack:
                sub_label = "📦 Study Pack"
                badge_color = ft.Colors.GREEN_600
                badge_icon = ft.Icons.STOREFRONT_ROUNDED
            elif "pdf" in stype or mtitle.lower().endswith(".pdf"):
                sub_label = "PDF Notes"
                badge_color = ft.Colors.RED_500
                badge_icon = ft.Icons.PICTURE_AS_PDF_ROUNDED
            elif "url" in stype:
                sub_label = "Web / Video"
                badge_color = ft.Colors.TEAL_600
                badge_icon = ft.Icons.LINK_ROUNDED
            else:
                sub_label = "Quiz & Cards"
                badge_color = ft.Colors.PURPLE_500
                badge_icon = ft.Icons.STYLE_ROUNDED

            circle_badge = ft.Container(
                width=38,
                height=38,
                border_radius=ft.BorderRadius.all(19),
                bgcolor=ft.Colors.with_opacity(0.12, badge_color),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(badge_icon, size=18, color=badge_color),
            )

            status_icon = ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if is_downloaded else ft.Icons.CLOUD_QUEUE_ROUNDED,
                size=10,
                color=ft.Colors.GREEN_700 if is_downloaded else ft.Colors.GREY_600,
            )
            status_text = ft.Text(
                "Offline" if is_downloaded else "Cloud",
                size=9.5,
                weight=ft.FontWeight.W_700,
                color=ft.Colors.GREEN_700 if is_downloaded else ft.Colors.GREY_600,
            )
            offline_status_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN if is_downloaded else ft.Colors.GREY_400),
                content=ft.Row(
                    spacing=3,
                    tight=True,
                    controls=[status_icon, status_text],
                ),
            )
            badge_info = (offline_status_badge, status_icon, status_text)

            # Direct action chips on card for instant study
            if is_cbt_bundle:
                def _launch_bundle(m=mat):
                    item_ids = []
                    try:
                        content_str = m.get("content", "")
                        if content_str and content_str.strip().startswith("{"):
                            meta = json.loads(content_str)
                            item_ids = meta.get("item_ids", [])
                    except Exception:
                        item_ids = []
                    page.run_task(_start_exam, item_ids if item_ids else [m.get("id")])

                action_chips = ft.Row(
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                            border_radius=ft.BorderRadius.all(6),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                            ink=True,
                            tooltip="Launch Full Sequential Exam Sitting",
                            on_click=lambda _, m=mat: _launch_bundle(m),
                            content=ft.Row(
                                spacing=3,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=12, color=ft.Colors.AMBER_700),
                                    ft.Text("Sequential", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_700),
                                ],
                            ),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                            border_radius=ft.BorderRadius.all(6),
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                            ink=True,
                            tooltip="Open Combo Cockpit",
                            on_click=lambda _, m=mat: page.run_task(_open_material_cockpit, m),
                            content=ft.Row(
                                spacing=3,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.DASHBOARD_ROUNDED, size=12, color=ft.Colors.PRIMARY),
                                    ft.Text("Cockpit", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                ],
                            ),
                        ),
                    ],
                )
            elif is_cbt:
                action_chips = ft.Row(
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                            border_radius=ft.BorderRadius.all(6),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                            ink=True,
                            tooltip="Launch Official CBT Simulation",
                            on_click=lambda _, i=mid: page.run_task(_start_exam, [i]),
                            content=ft.Row(
                                spacing=3,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=12, color=ft.Colors.PRIMARY),
                                    ft.Text("Take CBT", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                                ],
                            ),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                            border_radius=ft.BorderRadius.all(6),
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.TEAL),
                            ink=True,
                            tooltip="Open Exam Cockpit",
                            on_click=lambda _, m=mat: page.run_task(_open_material_cockpit, m),
                            content=ft.Row(
                                spacing=3,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.ANALYTICS_OUTLINED, size=12, color=ft.Colors.TEAL_700),
                                    ft.Text("Cockpit", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.TEAL_700),
                                ],
                            ),
                        ),
                    ],
                )
            else:
                action_chips = ft.Row(
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                            border_radius=ft.BorderRadius.all(6),
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                            ink=True,
                            tooltip="Review Flashcards",
                            on_click=lambda _, i=mid: page.run_task(_start_flashcards, [i]),
                            content=ft.Row(
                                spacing=3,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.STYLE_ROUNDED, size=11, color=ft.Colors.PRIMARY),
                                    ft.Text("Cards", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                ],
                            ),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                            border_radius=ft.BorderRadius.all(6),
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.TEAL),
                            ink=True,
                            tooltip="Take Quick Quiz",
                            on_click=lambda _, i=mid: page.run_task(_start_quiz, [i]),
                            content=ft.Row(
                                spacing=3,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.BOLT_ROUNDED, size=11, color=ft.Colors.TEAL_700),
                                    ft.Text("Quiz", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.TEAL_700),
                                ],
                            ),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                            border_radius=ft.BorderRadius.all(6),
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ORANGE),
                            ink=True,
                            tooltip="Run Exam Simulator",
                            on_click=lambda _, i=mid: page.run_task(_start_exam, [i]),
                            content=ft.Row(
                                spacing=3,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.TIMER_OUTLINED, size=11, color=ft.Colors.ORANGE_700),
                                    ft.Text("Exam", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.ORANGE_700),
                                ],
                            ),
                        ),
                    ],
                )

            # Offline toggle / download button
            if is_downloaded:
                offline_btn = ft.IconButton(
                    icon=ft.Icons.OFFLINE_PIN_ROUNDED,
                    icon_size=17,
                    icon_color=ft.Colors.GREEN_600,
                    tooltip="Saved offline (tap to remove offline copy)",
                    on_click=lambda e, m=mat: page.run_task(_remove_mat_offline, m, e.control, badge_info),
                )
            elif not is_hub_offline:
                offline_btn = ft.IconButton(
                    icon=ft.Icons.FILE_DOWNLOAD_OUTLINED,
                    icon_size=17,
                    icon_color=ft.Colors.GREY_600,
                    tooltip="Save for offline study",
                    on_click=lambda e, m=mat: page.run_task(_download_mat_offline, m, e.control, badge_info),
                )
            else:
                offline_btn = ft.Container(width=0, height=0)

            card_border = ft.Border.all(
                1.4 if (is_cbt or is_cbt_bundle) else 1,
                ft.Colors.with_opacity(0.35, ft.Colors.AMBER_600) if is_cbt_bundle
                else (ft.Colors.with_opacity(0.35, ft.Colors.INDIGO) if is_cbt
                else ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE))
            )

            # Tapping triggers full view loading spinner and opens cockpit!
            return ft.Container(
                col={"xs": 12, "sm": 6, "md": 4},
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(16),
                border=card_border,
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                ink=True,
                on_click=lambda _, m=mat: page.run_task(_open_material_cockpit, m),
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Column(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    tight=True,
                                    expand=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        circle_badge,
                                        ft.Column(
                                            spacing=2,
                                            tight=True,
                                            expand=True,
                                            controls=[
                                                ft.Text(
                                                    display_title,
                                                    size=13,
                                                    weight=ft.FontWeight.W_800,
                                                    color=ft.Colors.ON_SURFACE,
                                                    max_lines=1,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                                ft.Row(
                                                    spacing=6,
                                                    tight=True,
                                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                    controls=[
                                                        ft.Text(
                                                            sub_label,
                                                            size=11,
                                                            weight=ft.FontWeight.W_600,
                                                            color=badge_color if is_pack else ft.Colors.GREY_500,
                                                        ),
                                                        offline_status_badge,
                                                    ],
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    spacing=0,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        offline_btn,
                                        ft.IconButton(
                                            icon=ft.Icons.SHARE_ROUNDED,
                                            icon_size=16,
                                            icon_color=ft.Colors.PRIMARY,
                                            tooltip="Share with Study Partner",
                                            on_click=lambda e, m=mat: page.run_task(_share_material_with_partner, m),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                            icon_size=16,
                                            icon_color=ft.Colors.GREY_500,
                                            tooltip="Remove from Vault",
                                            on_click=lambda e, m=mat: _confirm_delete_material(m),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        # Direct Action Chips row at bottom
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                action_chips,
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                    border_radius=ft.BorderRadius.all(12),
                                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN),
                                    content=ft.Row(
                                        spacing=2,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=13, color=ft.Colors.GREEN_700),
                                            ft.Text("Open", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.GREEN_700),
                                        ],
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
            )

        uploaded_materials = [m for m in materials if (m.get("source_type") or "").lower() != "pack_import"]
        downloaded_packs = [m for m in materials if (m.get("source_type") or "").lower() == "pack_import"]

        partner_cockpit = build_study_partner_cockpit(
            page=page,
            token=token,
            available_materials=materials,
            on_refresh=lambda: page.run_task(_load_hub),
        )

        sections_controls = [
            hero_section,
            partner_cockpit,
            quick_actions_grid,
            pack_hub_banner,
        ]

        if not materials:
            if is_hub_offline:
                empty_vault = ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                    border_radius=ft.BorderRadius.all(16),
                    padding=ft.Padding.symmetric(horizontal=20, vertical=26),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Container(
                                width=44,
                                height=44,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                                border_radius=ft.BorderRadius.all(12),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, color=ft.Colors.AMBER_600, size=22),
                            ),
                            ft.Text("No Offline Study Materials", size=15, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                            ft.Text(
                                "You haven't downloaded any flashcard decks or question sets for offline use.\nConnect to the internet to download materials from your study vault.",
                                size=12,
                                color=ft.Colors.GREY_500,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=6),
                            ft.Row(
                                spacing=10,
                                alignment=ft.MainAxisAlignment.CENTER,
                                controls=[
                                    ft.ElevatedButton(
                                        content=ft.Row(
                                            spacing=6,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.DOWNLOAD_DONE_ROUNDED, size=15, color=ft.Colors.WHITE),
                                                ft.Text("Offline Library", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                            ],
                                        ),
                                        bgcolor=ft.Colors.PRIMARY,
                                        height=36,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=9), elevation=0),
                                        on_click=lambda _: page.go("/offline"),
                                    ),
                                    ft.OutlinedButton(
                                        content=ft.Row(
                                            spacing=6,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.SYNC_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                                                ft.Text("Try Syncing Vault", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                            ],
                                        ),
                                        height=36,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=9)),
                                        on_click=lambda _: page.run_task(_handle_sync_all_vault),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            else:
                empty_vault = ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                    border_radius=ft.BorderRadius.all(16),
                    padding=ft.Padding.symmetric(horizontal=20, vertical=26),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Container(
                                width=44,
                                height=44,
                                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
                                border_radius=ft.BorderRadius.all(12),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                            ),
                            ft.Text("No materials added yet", size=14, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                            ft.Text(
                                "Upload lecture notes, slides, or download curated study packs from the marketplace.",
                                size=12,
                                color=ft.Colors.GREY_500,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=4),
                            ft.Row(
                                spacing=10,
                                alignment=ft.MainAxisAlignment.CENTER,
                                controls=[
                                    ft.ElevatedButton(
                                        content=ft.Row(
                                            spacing=6,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.ADD_ROUNDED, size=15, color=ft.Colors.WHITE),
                                                ft.Text("Add Notes", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                            ],
                                        ),
                                        bgcolor=ft.Colors.PRIMARY,
                                        height=36,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=9), elevation=0),
                                        on_click=lambda _: _guard_offline_action(lambda: _open_upload_modal(initial_mode="file")),
                                    ),
                                    ft.OutlinedButton(
                                        content=ft.Row(
                                            spacing=6,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.STOREFRONT_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                                                ft.Text("Explore Marketplace", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                            ],
                                        ),
                                        height=36,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=9)),
                                        on_click=lambda _: go_marketplace(),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            sections_controls.append(empty_vault)
        else:
            # 1. Downloaded Study Packs Section (Separation of concerns)
            if downloaded_packs:
                pack_header = ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=8,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.STOREFRONT_ROUNDED, size=18, color=ft.Colors.GREEN_600),
                                ft.Text(f"Downloaded Study Packs ({len(downloaded_packs)})", size=16 if is_small else 18, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                        ft.TextButton(
                            "Marketplace",
                            style=ft.ButtonStyle(color=ft.Colors.GREEN_700),
                            on_click=lambda _: go_marketplace(),
                        ),
                    ],
                )
                pack_grid = ft.ResponsiveRow(
                    spacing=10,
                    run_spacing=10,
                    controls=[_render_jump_card(m) for m in downloaded_packs],
                )
                sections_controls.extend([
                    pack_header,
                    pack_grid,
                    ft.Container(height=8),
                ])

            # 2. My Study Materials & Notes Section
            if uploaded_materials:
                mat_header = ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=8,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                                ft.Text(f"My Uploads & Study Notes ({len(uploaded_materials)})", size=16 if is_small else 18, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                        ft.TextButton(
                            "View all",
                            style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
                            on_click=lambda _: _toggle_sidebar(None),
                        ),
                    ],
                )
                mat_grid = ft.ResponsiveRow(
                    spacing=10,
                    run_spacing=10,
                    controls=[_render_jump_card(m) for m in uploaded_materials],
                )
                sections_controls.extend([
                    mat_header,
                    mat_grid,
                ])

        sections_controls.append(ft.Container(height=32))

        return ft.Column(
            key="self_study_hub_scroll_column",
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(
                        horizontal=14 if is_small else 24,
                        vertical=18,
                    ),
                    content=ft.Column(
                        spacing=18,
                        controls=sections_controls,
                    ),
                ),
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # YOUTUBE MODAL
    # ─────────────────────────────────────────────────────────────────────────
    def _open_youtube_modal():
        at_limit = state["mat_lim"] is not None and state["mat_used"] >= state["mat_lim"]

        url_field = ft.TextField(
            label="YouTube Video Link *",
            hint_text="e.g. https://www.youtube.com/watch?v=... or youtu.be/...",
            prefix_icon=ft.Icons.PLAY_CIRCLE_FILL_ROUNDED,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        )

        title_field = ft.TextField(
            label="Custom Title (Optional)",
            hint_text="e.g. Intro to Machine Learning",
            prefix_icon=ft.Icons.TITLE_ROUNDED,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        )

        error_text = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False)
        loading_ring = ft.ProgressRing(width=16, height=16, stroke_width=2.5, color=ft.Colors.WHITE, visible=False)
        submit_btn_text = ft.Text("Import & Analyze Video", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_PRIMARY)

        submit_btn = ft.ElevatedButton(
            content=ft.Row(
                tight=True,
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    loading_ring,
                    submit_btn_text,
                ],
            ),
            bgcolor=ft.Colors.PRIMARY,
            height=42,
            disabled=at_limit,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=0,
            ),
        )

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=18),
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=8,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED_ROUNDED, color=ft.Colors.RED_500, size=22),
                            ft.Text("Study with YouTube", size=15.5, weight=ft.FontWeight.W_800, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        on_click=lambda _: _close_yt_dlg(),
                    ),
                ],
            ),
            content=ft.Container(
                width=min(page.width - 32, 400) if page.width else 380,
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    controls=[
                        ft.Text(
                            "Paste any educational YouTube video link. We extract its core context and synthesize structured study notes for flashcards, quizzes, and your AI tutor.",
                            size=12,
                            color=ft.Colors.GREY_600,
                        ),
                        url_field,
                        title_field,
                        error_text,
                        ft.Container(
                            visible=at_limit,
                            padding=ft.Padding.all(10),
                            border_radius=8,
                            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED_400),
                            content=ft.Text("Material limit reached. Upgrade plan to add more.", size=11, color=ft.Colors.RED_700),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_yt_dlg()),
                submit_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        def _close_yt_dlg():
            dlg.open = False
            page.update()

        async def _do_import(e):
            raw_url = (url_field.value or "").strip()
            if not raw_url:
                error_text.value = "Please enter a valid YouTube link."
                error_text.visible = True
                page.update()
                return

            error_text.visible = False
            loading_ring.visible = True
            submit_btn_text.value = "Analyzing video & generating notes…"
            submit_btn.disabled = True
            page.update()

            res = await import_youtube_material(token, raw_url, (title_field.value or "").strip() or None)
            if "error" in res:
                error_text.value = str(res["error"])
                error_text.visible = True
                loading_ring.visible = False
                submit_btn_text.value = "Import & Analyze Video"
                submit_btn.disabled = False
                page.update()
                return

            _close_yt_dlg()
            show_page_snackbar(page, "YouTube video imported and study generation initiated!")

            # Promptly count towards student quotas in state
            state["mat_used"] = (state.get("mat_used") or 0) + 1
            state["gen_used"] = (state.get("gen_used") or 0) + 1
            new_mid = str(res.get("material_id"))
            if new_mid and new_mid != "None":
                state.setdefault("generating_mats", set()).add(new_mid)

            if state.get("sidebar_vault_text"):
                state["sidebar_vault_text"].value = f"{len(state.get('materials', [])) + 1} items"
                try:
                    state["sidebar_vault_text"].update()
                except Exception:
                    pass

            _refresh_sidebar_materials()
            _refresh_plan_ui()

            # Reload materials and immediately open in Cockpit
            mats = await get_materials(token)
            if isinstance(mats, list) and mats:
                state["materials"] = mats
                _refresh_sidebar_materials()
                target_mat = next((m for m in mats if str(m.get("id")) == new_mid), mats[0])
                await _open_material_cockpit(target_mat)
            else:
                await _load_hub()

        submit_btn.on_click = lambda e: page.run_task(_do_import, e)
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # UPLOAD MODAL
    # ─────────────────────────────────────────────────────────────────────────
    def _open_upload_modal(initial_mode="file", prefill_title=""):
        selected_file_bytes = None
        selected_file_name  = None
        selected_extra_files: list = []  # list of (name, bytes)

        at_limit = state["mat_lim"] is not None and state["mat_used"] >= state["mat_lim"]

        is_text_start = initial_mode in ("paste", "text", "url")
        is_url_mode = initial_mode == "url"
        is_photo_mode = initial_mode == "photo"

        title_field = ft.TextField(
            label="Resource Title or URL *" if is_url_mode else ("Photo / Notes Title *" if is_photo_mode else "Topic Title *"),
            value=prefill_title or "",
            hint_text="e.g. YouTube Video, Article URL, or Topic" if is_url_mode else ("e.g. Whiteboard Notes, Lecture Slide" if is_photo_mode else "e.g. Biology Ch. 4 - Cell Division"),
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            expand=True
        )

        text_field = ft.TextField(
            label="Video Transcript / Web Content" if is_url_mode else "Paste Notes / Content",
            hint_text="Paste article text, video transcription, or summaries..." if is_url_mode else "Paste lecture summaries, transcriptions, notes, or articles...",
            multiline=True,
            min_lines=5,
            max_lines=9,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            expand=True
        )

        error_text  = ft.Text("", color=ft.Colors.RED_700, size=12, visible=True, expand=True)
        status_text = ft.Text("", color=ft.Colors.TEAL_600, size=12, visible=True, expand=True)

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
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=8,
                        tight=True,
                        expand=True,
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=ft.Colors.RED_400, size=18),
                            ft.Text(
                                "Limit reached! Top-up or upgrade to add more.",
                                size=11.5,
                                color=ft.Colors.RED_700,
                                weight=ft.FontWeight.W_600,
                                expand=True,
                            ),
                        ],
                    ),
                    ft.TextButton(
                        "Visit Store",
                        visible=False,
                        style=ft.ButtonStyle(
                            color=ft.Colors.RED_700,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=0),
                        ),
                        on_click=lambda _: ((setattr(modal, "open", False), page.update()) if 'modal' in locals() else None, page.go("/store?tab=boosters")),
                    ),
                ],
            ),
        )

        def remove_selected_file(e=None):
            nonlocal selected_file_bytes, selected_file_name, selected_extra_files
            selected_file_bytes = None
            selected_file_name = None
            selected_extra_files = []
            update_dropzone_ui()
            page.update()

        file_dropzone = ft.Container()

        def update_dropzone_ui():
            if selected_file_bytes and selected_file_name:
                total_files_count = 1 + len(selected_extra_files)
                total_bytes = len(selected_file_bytes) + sum(len(b) for _, b in selected_extra_files)
                size_kb = total_bytes / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
                is_img = any(selected_file_name.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"])
                is_pdf = selected_file_name.lower().endswith(".pdf")
                fmt_tag = f"{total_files_count} PHOTOS" if (is_img and total_files_count > 1) else ("PHOTO" if is_img else ("PDF" if is_pdf else "TXT"))
                fmt_color = ft.Colors.PURPLE_400 if is_img else (ft.Colors.RED_400 if is_pdf else ft.Colors.BLUE_400)
                fmt_icon = ft.Icons.CAMERA_ALT_ROUNDED if is_img else (ft.Icons.PICTURE_AS_PDF_ROUNDED if is_pdf else ft.Icons.DESCRIPTION_ROUNDED)

                display_name = f"{selected_file_name} (+{len(selected_extra_files)} more)" if selected_extra_files else selected_file_name

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
                                                display_name,
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
                                tooltip="Remove files",
                                on_click=remove_selected_file,
                            ),
                        ],
                    ),
                )
            else:
                dropzone_title = "Click to browse study photos (up to 6)" if is_photo_mode else "Click to browse document"
                dropzone_sub = "PNG, JPG, or WEBP (handwritten notes, slides)" if is_photo_mode else "PDF, TXT, or Markdown supported"
                dropzone_icon = ft.Icons.ADD_A_PHOTO_ROUNDED if is_photo_mode else ft.Icons.CLOUD_UPLOAD_ROUNDED

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
                                content=ft.Icon(dropzone_icon, color=ft.Colors.PRIMARY, size=24),
                            ),
                            ft.Text(dropzone_title, size=13, weight=ft.FontWeight.W_700),
                            ft.Text(dropzone_sub, size=11, color=ft.Colors.GREY_500),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=6,
                                controls=[
                                    ft.Container(bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PURPLE_400), border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=2), content=ft.Text("PHOTO / NOTES", size=9, weight=ft.FontWeight.W_800, color=ft.Colors.PURPLE_600)) if is_photo_mode else ft.Container(bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED_400), border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=2), content=ft.Text("PDF", size=9, weight=ft.FontWeight.W_800, color=ft.Colors.RED_600)),
                                    ft.Container(bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_400), border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=2), content=ft.Text("TXT", size=9, weight=ft.FontWeight.W_800, color=ft.Colors.BLUE_600)),
                                    ft.Container(bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.TEAL_400), border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=2), content=ft.Text("MD", size=9, weight=ft.FontWeight.W_800, color=ft.Colors.TEAL_600)),
                                ],
                            ),
                        ],
                    ),
                )

        async def pick_file(e):
            nonlocal selected_file_bytes, selected_file_name, selected_extra_files
            try:
                allowed_ext = ["png", "jpg", "jpeg", "webp"] if is_photo_mode else ["pdf", "txt", "md", "png", "jpg", "jpeg", "webp"]
                files = await ft.FilePicker().pick_files(
                    allow_multiple=is_photo_mode,
                    allowed_extensions=allowed_ext,
                    with_data=True,
                )
                if files:
                    selected_file_bytes = files[0].bytes
                    selected_file_name  = files[0].name
                    selected_extra_files = [(f.name, f.bytes) for f in files[1:6]]
                    if not (title_field.value or "").strip():
                        cleaned_name = selected_file_name
                        for ext in [".png", ".jpg", ".jpeg", ".webp", ".pdf", ".txt", ".md"]:
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
        mode_state = {"tab": "text" if is_text_start else "file"}

        tab_file_icon = ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, size=15, color=ft.Colors.GREY_500 if is_text_start else ft.Colors.PRIMARY)
        tab_file_text = ft.Text("Upload File", size=12, weight=ft.FontWeight.W_500 if is_text_start else ft.FontWeight.W_700, color=ft.Colors.GREY_500 if is_text_start else ft.Colors.PRIMARY)
        tab_file_btn = ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(vertical=8),
            border_radius=8,
            bgcolor=ft.Colors.TRANSPARENT if is_text_start else ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
            alignment=ft.Alignment.CENTER,
            ink=True,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=6,
                controls=[tab_file_icon, tab_file_text],
            ),
        )

        tab_text_icon = ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=16, color=ft.Colors.PRIMARY if is_text_start else ft.Colors.GREY_500)
        tab_text_text = ft.Text("Paste Text", size=12, weight=ft.FontWeight.W_700 if is_text_start else ft.FontWeight.W_500, color=ft.Colors.PRIMARY if is_text_start else ft.Colors.GREY_500)
        tab_text_btn = ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(vertical=8),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_text_start else ft.Colors.TRANSPARENT,
            alignment=ft.Alignment.CENTER,
            ink=True,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=6,
                controls=[tab_text_icon, tab_text_text],
            ),
        )

        file_section = ft.Container(content=file_dropzone, visible=not is_text_start)
        text_section = ft.Container(content=text_field, visible=is_text_start)

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
            nonlocal selected_file_bytes, selected_file_name, selected_extra_files
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
                is_img_upload = selected_file_name and any(selected_file_name.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"])
                result = await asyncio.wait_for(
                    upload_material(
                        token,
                        title=title_field.value.strip(),
                        text=text_field.value or None,
                        file_bytes=selected_file_bytes,
                        file_name=selected_file_name,
                        extra_files=selected_extra_files if selected_extra_files else None,
                    ),
                    timeout=60 if is_img_upload else 30,
                )
                new_mat = {
                    "id": result.get("material_id", f"mat_{len(state['materials'])+1}"),
                    "title": title_field.value.strip(),
                    "source_type": "photo" if is_img_upload else ("pdf" if selected_file_bytes else "text"),
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
                selected_extra_files = []
                update_dropzone_ui()

                # Dismiss modal and automatically transition to study cockpit for this new material
                modal.open = False
                page.update()
                show_page_snackbar(page, f"Uploaded '{new_mat['title']}'! Opening study cockpit…")
                page.run_task(_open_material_cockpit, new_mat)

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
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=32, height=32,
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                                border_radius=ft.BorderRadius.all(8),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, color=ft.Colors.PRIMARY, size=17),
                            ),
                            ft.Column(
                                spacing=1,
                                expand=True,
                                tight=True,
                                controls=[
                                    ft.Text(
                                        "Upload Study Material",
                                        size=15,
                                        weight=ft.FontWeight.W_700,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        "Add notes or docs to vault",
                                        size=10.5,
                                        color=ft.Colors.GREY_500,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
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
    def _open_generate_panel(target_material: dict | None = None):
        gen_remaining = (state["gen_lim"] - state["gen_used"]) if state["gen_lim"] is not None else None
        at_gen_limit  = state["gen_lim"] is not None and state["gen_used"] >= state["gen_lim"]

        mats = state.get("materials", [])
        chosen_mat = None
        if target_material and isinstance(target_material, dict):
            chosen_mat = target_material
        elif state.get("active_material"):
            chosen_mat = state["active_material"]
        elif mats:
            chosen_mat = mats[0]

        if not chosen_mat:
            show_page_snackbar(page, "Upload study notes or a PDF to your vault first before generating AI content!")
            _open_upload_modal()
            return

        cb_flashcards = ft.Checkbox(label="Flashcards (SRS cards)", value=True, visible=False)
        cb_quiz       = ft.Checkbox(label="Quick Quiz questions", value=False, visible=False)
        cb_exam       = ft.Checkbox(label="Exam questions", value=False, visible=False)

        gen_error = ft.Text("", color=ft.Colors.RED_700, size=12, visible=True)

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

        selected_target = [chosen_mat]
        target_tile_refs = {}

        def update_target_ui():
            cur_id = selected_target[0]["id"]
            for m in mats:
                mid = m["id"]
                if mid in target_tile_refs:
                    is_cur = (mid == cur_id)
                    cont, icon_ctrl = target_tile_refs[mid]
                    cont.bgcolor = ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_cur else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE)
                    cont.border = ft.Border.all(
                        1.5 if is_cur else 1,
                        ft.Colors.PRIMARY if is_cur else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                    )
                    icon_ctrl.name = ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED if is_cur else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED
                    icon_ctrl.color = ft.Colors.PRIMARY if is_cur else ft.Colors.GREY_400

        def select_target_mat(m):
            selected_target[0] = m
            update_target_ui()
            page.update()

        mat_card_controls = []
        for mat in mats:
            mid = mat["id"]
            is_cur = (selected_target[0]["id"] == mid)
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

            radio_icon = ft.Icon(
                ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED if is_cur else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                color=ft.Colors.PRIMARY if is_cur else ft.Colors.GREY_400,
                size=18,
            )

            tile = ft.Container(
                border_radius=ft.BorderRadius.all(10),
                padding=ft.Padding.symmetric(horizontal=12, vertical=9),
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_cur else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                border=ft.Border.all(
                    1.5 if is_cur else 1,
                    ft.Colors.PRIMARY if is_cur else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                ),
                ink=True,
                on_click=lambda _, m=mat: select_target_mat(m),
                content=ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=28, height=28,
                            bgcolor=ft.Colors.with_opacity(0.12, m_color),
                            border_radius=ft.BorderRadius.all(7),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(m_icon, color=m_color, size=15),
                        ),
                        # expand=True lets the title column take the leftover width,
                        # so long titles wrap / ellipsize instead of overflowing.
                        ft.Column(
                            spacing=1,
                            tight=True,
                            expand=True,
                            controls=[
                                ft.Text(
                                    display_title,
                                    size=12,
                                    weight=ft.FontWeight.W_600,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(m_tag, size=9, weight=ft.FontWeight.W_700, color=m_color),
                            ],
                        ),
                        radio_icon,
                    ],
                ),
            )
            target_tile_refs[mid] = (tile, radio_icon)
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
                            expand=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
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
                                    expand=True,
                                    controls=[
                                        ft.Text(title, size=12.5, weight=ft.FontWeight.W_700, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(desc, size=10.5, color=ft.Colors.GREY_500, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                    ],
                                ),
                            ],
                        ),
                        status_icon,
                    ],
                ),
            )
            return card_box

        out_flashcards = output_type_card(ft.Icons.STYLE_ROUNDED, "Flashcards", "Spaced Repetition Deck", ft.Colors.PURPLE_400, cb_flashcards)
        out_quiz = output_type_card(ft.Icons.BOLT_ROUNDED, "Quick Quiz", "Targeted Drills.Instant Feedback", ft.Colors.TEAL_500, cb_quiz)
        out_exam = output_type_card(ft.Icons.TIMER_OUTLINED, "Exam Simulator", "Full-Length Timed Test", ft.Colors.ORANGE_500, cb_exam)

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

            target = selected_target[0]
            if not target or not target.get("id"):
                gen_error.value = "Please select a material first."
                gen_error_box.visible = True
                page.update()
                return

            gen_error_box.visible = False
            gen_btn.disabled = True
            gen_btn.content = ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=8,
                controls=[
                    ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY, stroke_width=2),
                    ft.Text("Queuing AI Tasks…", color=ft.Colors.ON_PRIMARY, size=12, weight=ft.FontWeight.W_600),
                ],
            )
            page.update()

            t_id = target["id"]
            state["generating_mats"].add(t_id)
            state["poll_strikes"][t_id] = 0

            try:
                result = await asyncio.wait_for(
                    generate_from_materials(token, [t_id], selected_types),
                    timeout=30,
                )
                state["gen_used"] += 1
                _refresh_plan_ui()

                # Dismiss modal immediately so user is never stuck with a lingering checkmark
                modal.open = False
                page.update()

                title_disp = format_material_title(target.get("title", "document"))
                show_page_snackbar(page, f"✓ AI Generation queued for '{title_disp}'! Deck is generating in background.")

                # Switch directly into this material's cockpit so the user sees live generation progress
                page.run_task(_open_material_cockpit, target)

            except asyncio.TimeoutError:
                gen_error.value = "Server request timed out. Try again."
                gen_error_box.visible = True
                gen_btn.disabled = False
                gen_btn.content = ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=6,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.WHITE),
                        ft.Text("Generate AI Content", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_700),
                    ],
                )
                state["generating_mats"].discard(t_id)
                page.update()

            except Exception as ex:
                gen_error.value = f"Failed to queue tasks ({type(ex).__name__})."
                gen_error_box.visible = True
                gen_btn.disabled = False
                gen_btn.content = ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=6,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.WHITE),
                        ft.Text("Generate AI Content", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_700),
                    ],
                )
                state["generating_mats"].discard(t_id)
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
        gen_h = min(page.height - 180, 520) if page.height else 460

        materials_list_content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=6,
            controls=mat_card_controls,
        )

        materials_container = ft.Container(
            height=min(160, max(64, len(mat_card_controls) * 64)),
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
                _section_label("TARGET STUDY MATERIAL"),
            ],
        )

        modal = ft.AlertDialog(
            modal=False, 
            shape=ft.RoundedRectangleBorder(radius=18),
            on_dismiss=close_generate_modal,
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=32, height=32,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_400),
                                border_radius=ft.BorderRadius.all(8),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PURPLE_400, size=17),
                            ),
                            ft.Column(
                                spacing=1,
                                expand=True,
                                tight=True,
                                controls=[
                                    ft.Text("Generate Study Content", size=15, weight=ft.FontWeight.W_700, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text("Create cards, quizzes & exams with AI", size=10.5, color=ft.Colors.GREY_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
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
            on_exit=_exit_study_session,
            on_restart=lambda: page.run_task(_start_flashcards, _current_selected_ids()),
            material=state.get("active_material"),
        )

    def _build_quiz(questions: list):
        return build_quiz(
            page,
            questions,
            on_exit=_exit_study_session,
            on_restart=lambda: page.run_task(_start_quiz, _current_selected_ids()),
        )

    def _build_exam(questions: list, duration_seconds: int | None = None):
        return build_exam(
            page,
            questions,
            duration_seconds,
            on_exit=_exit_study_session,
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
    page.run_task(_load_hub, False, None)
    page.run_task(_poll_generation_status)

    return ft.View(
        route="/self-study",
        appbar=app_bar,
        bgcolor=ft.Colors.SURFACE,
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=body_host # Passed directly, no extra column wrappers needed
            )
        ],
    )