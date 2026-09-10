import asyncio

import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
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
    "free": ft.Colors.ON_PRIMARY,
    "pro": ft.Colors.PURPLE_400,
    "unlimited": ft.Colors.ORANGE_400,
    "default": ft.Colors.PRIMARY
}


# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _section_label(text: str) -> ft.Text:
    return ft.Text(text, size=11, weight=ft.FontWeight.W_600,
                   color=ft.Colors.BLACK)


def _card(content, padding=16) -> ft.Container:
    return ft.Container(
        bgcolor=ft.Colors.SURFACE,
        border_radius=14,
        border=ft.Border.all(1, ft.Colors.GREY_200),
        width=float('inf'),
        padding=padding,
        shadow=ft.BoxShadow(
            blur_radius=6,
            color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        ),
        content=content,
    )


def _pill(label, bg, fg) -> ft.Container:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=9, vertical=3),
        bgcolor=bg, border_radius=10,
        content=ft.Text(label, size=10, color=fg, weight=ft.FontWeight.W_600),
    )


def _loading(label="Loading…") -> ft.Container:
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=32, height=32),
                ft.Text(label, size=13, color=ft.Colors.GREY_400),
            ],
        ),
    )


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
               bar_color=ft.Colors.PRIMARY) -> ft.Column:
    if limit is None:
        fraction     = 0.0
        value_label  = f"{used}  /  ∞"
        warn         = False
    else:
        fraction    = min(used / limit, 1.0)
        value_label = f"{used}  /  {limit}"
        warn        = fraction >= 0.8

    bar_color_final = ft.Colors.RED_400 if warn else bar_color

    return ft.Column(
        spacing=4,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(label, size=11, color=ft.Colors.GREY_600),
                    ft.Text(value_label, size=11, color=ft.Colors.GREY_500,
                            weight=ft.FontWeight.W_600),
                ],
            ),
            ft.ProgressBar(
                value=fraction,
                color=bar_color_final,
                bgcolor=ft.Colors.GREY_100,
                height=5,
                border_radius=4,
                expand=True,
            ),
            ft.Text(
                "⚠ Approaching limit — upgrade for more" if warn and limit else "",
                size=10,
                color=ft.Colors.ORANGE_600,
                visible=warn and limit is not None,
            ),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN VIEW
# ─────────────────────────────────────────────────────────────────────────────
async def self_study_view(page: ft.Page):
    visible_trigger=True
    app_bar_bottom = get_bottom_appbar(page)
    token          = await page.shared_preferences.get("auth_token")

    # ── shared state ──────────────────────────────────────────────────────────
    state = {
        "materials":         [],
        "on_hub":            True,
        "sidebar_open":      False,
        "selected_mat_ids":  set(),
        "was_desktop":       True,
        "generating_mats":   set(),
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
    plan_badge = ft.Container(
        width=60, height=22,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=8,
        content=ft.Text("", size=8, weight=ft.FontWeight.W_700),
    )

    sidebar_materials_col = ft.Column(spacing=6, controls=[])
    bars_col = ft.Column(spacing=10, controls=[])

    # Extract the upgrade banner so we can toggle it dynamically
    sidebar_upgrade_banner = ft.Container(
        visible=False, width=float("inf"), border_radius=10,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.ORANGE_400)),
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ORANGE_400),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(spacing=6, controls=[
                    ft.Icon(ft.Icons.BOLT_ROUNDED, color=ft.Colors.ORANGE_500, size=14),
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
                    bgcolor=ft.Colors.ORANGE_500, height=32, expand=True,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                ),
            ],
        ),
    )

    def _refresh_plan_ui():
        color = PLAN_COLORS.get(state["plan_id"], PLAN_COLORS["default"])
        
        # 1. Update Badge
        plan_badge.bgcolor = ft.Colors.with_opacity(0.12, color)
        plan_badge.content.value = state["plan_label"].upper()
        plan_badge.content.color = color
        
        # 2. Update Progress Bars
        bars_col.controls = [
            _limit_bar("Materials", state["mat_used"], state["mat_lim"], ft.Colors.TEAL_400),
            _limit_bar("Generations", state["gen_used"], state["gen_lim"], ft.Colors.PURPLE_400),
        ]
        
        # 3. Disable Action Buttons dynamically
        upload_btn_sidebar.disabled = (state["mat_lim"] is not None and state["mat_used"] >= state["mat_lim"])
        generate_btn_sidebar.disabled = (state["gen_lim"] is not None and state["gen_used"] >= state["gen_lim"])
        
        # 4. Toggle Free Nudge
        sidebar_upgrade_banner.visible = (state["plan_id"] == "free")

    def _current_selected_ids():
        """Read the live sidebar selection at call-time (not a stale snapshot)."""
        return list(state["selected_mat_ids"]) or None

    def _refresh_sidebar_materials():
        sidebar_materials_col.controls.clear()
        mats = state["materials"]
        if not mats:
            sidebar_materials_col.controls.append(
                ft.Text("Upload materials to get started.", size=15, color=ft.Colors.BLACK,align=ft.Alignment(0,0))
            )
            return

        icon_map = {
            "pdf":  (ft.Icons.PICTURE_AS_PDF_ROUNDED, ft.Colors.ON_SURFACE),
            "text": (ft.Icons.TEXT_SNIPPET_OUTLINED,  ft.Colors.ON_SURFACE),
            "url":  (ft.Icons.LINK_ROUNDED,            ft.Colors.ON_SURFACE),
        }

        for mat in mats:
            mat_id = mat["id"]
            icon, color = icon_map.get(mat.get("source_type", "text"),
                                       (ft.Icons.DESCRIPTION_OUTLINED, ft.Colors.ON_SURFACE))

            is_selected = mat_id in state["selected_mat_ids"]
            chip = ft.Container(
                height=40,
                border_radius=8,
                border=ft.Border.all(
                    1.5,
                    ft.Colors.PRIMARY if is_selected else ft.Colors.ON_PRIMARY
                ),
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY)
                if is_selected else ft.Colors.SURFACE,
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                ink=True,
                data=mat_id,
                content=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(icon, color=color, size=14),
                        ft.Text(mat.get("title", "Untitled"), size=13,
                                color=ft.Colors.ON_SURFACE, expand=True,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if is_selected
                            else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                            color=ft.Colors.PRIMARY if is_selected else ft.Colors.GREY_300,
                            size=14,
                        ),
                    ],
                ),
            )

            def _toggle(e, mid=mat_id):
                if mid in state["selected_mat_ids"]:
                    state["selected_mat_ids"].discard(mid)
                else:
                    state["selected_mat_ids"].add(mid)
                _refresh_sidebar_materials()
                # Keep the "Studying from N selected material(s)" hint and
                # due-card count in sync if the hub is currently visible.
                # (Study-mode buttons themselves always read the live
                # selection at click-time via _current_selected_ids(),
                # regardless of whether the hub has been re-rendered.)
                if state.get("on_hub"):
                    page.run_task(_load_hub)
                else:
                    page.update()

            chip.on_click = _toggle
            sidebar_materials_col.controls.append(chip)

    upload_btn_sidebar = ft.ElevatedButton(
        content=ft.Row(
            tight=True, spacing=6,
            controls=[
                ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, size=14, color=ft.Colors.ON_PRIMARY),
                ft.Text("Upload", size=10, color=ft.Colors.ON_PRIMARY,
                        weight=ft.FontWeight.W_600),
            ],
        ),
        bgcolor=ft.Colors.PRIMARY,
        expand=True, height=33,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8), elevation=0
        ),
        on_click=lambda _: _open_upload_modal(),
        disabled=True, # Handled dynamically by _refresh_plan_ui()
    )

    generate_btn_sidebar = ft.ElevatedButton(
        content=ft.Row(
            tight=True, spacing=6,
            controls=[
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color=ft.Colors.ON_PRIMARY),
                ft.Text("Generate", size=10, color=ft.Colors.ON_PRIMARY,
                        weight=ft.FontWeight.W_600),
            ],
        ),
        bgcolor=ft.Colors.PURPLE_400,
        expand=True, height=33,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8), elevation=0
        ),
        on_click=lambda _: _open_generate_panel(),
        disabled=True, # Handled dynamically by _refresh_plan_ui()
    )

    # THE FIX: Increased Sidebar Width to 280px for better visibility
    # ── section header helper ─────────────────────────────────────────────────
    def _sidebar_header(icon, label, trailing=None):
        return ft.Container(
            border_radius=12,
            padding=ft.Padding.only(left=14, right=10, top=10, bottom=10),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_PRIMARY)),
            gradient=ft.LinearGradient(
                begin=ft.Alignment.CENTER_LEFT,
                end=ft.Alignment.CENTER_RIGHT,
                colors=[ft.Colors.PRIMARY, ft.Colors.SECONDARY],
            ),
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=30, height=30,
                                bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.ON_PRIMARY),
                                border_radius=8,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(icon, color=ft.Colors.ON_PRIMARY, size=16),
                            ),
                            ft.Text(
                                label,
                                size=14,
                                weight=ft.FontWeight.W_700,
                                color=ft.Colors.ON_PRIMARY,
                            ),
                        ],
                    ),
                    trailing or ft.Container(),
                ],
            ),
        )

    sidebar_container = ft.Container(
        width=330,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.GREY_200)),
        shadow=ft.BoxShadow(
            blur_radius=12,
            color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            offset=ft.Offset(2, 0),
        ),
        content=ft.Column(
            spacing=0,
            controls=[
                # ── Scrollable body ───────────────────────────────────────────
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        spacing=0,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.symmetric(
                                    horizontal=12, vertical=12
                                ),
                                content=ft.Column(
                                    spacing=12,
                                    controls=[

                                        # ── Materials section ─────────────────
                                        _sidebar_header(
                                            ft.Icons.FOLDER_OUTLINED,
                                            "My Materials",
                                            trailing=ft.Container(
                                                width=40, height=22,
                                                bgcolor=ft.Colors.with_opacity(
                                                    0.2, ft.Colors.ON_PRIMARY),
                                                border_radius=6,
                                                alignment=ft.Alignment.CENTER,
                                                content=plan_badge,
                                            ),
                                        ),

                                        # Material chips list
                                        ft.Container(
                                            height=220,
                                            content=ft.Column(
                                                scroll=ft.ScrollMode.AUTO,
                                                spacing=4,
                                                controls=[sidebar_materials_col],
                                            ),
                                        ),

                                        # ── Upload + Generate buttons ─────────
                                        ft.Row(
                                            spacing=8,
                                            controls=[
                                                upload_btn_sidebar,
                                                generate_btn_sidebar,
                                            ],
                                        ),

                                        ft.Divider(height=1, color=ft.Colors.GREY_100),

                                        # ── Plan Usage section ────────────────
                                        _sidebar_header(
                                            ft.Icons.WORKSPACE_PREMIUM_OUTLINED,
                                            "Plan Usage",
                                        ),

                                        bars_col,

                                        # ── Upgrade banner (free plan only) ──
                                        # ── Upgrade banner (free plan only) ──
                                        sidebar_upgrade_banner,

                                        ft.Container(height=8),
                                    ],
                                ),
                            )
                        ],
                    ),
                ),
            ],
        ),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # THE FIX: MOBILE & DESKTOP RESPONSIVE LAYOUT
    # ─────────────────────────────────────────────────────────────────────────
    def update_layout(e=None):
        is_desktop = page.width >= 800 if page.width else True
        
        # Auto-collapse on mobile initially if not explicitly toggled
        if e is not None and not is_desktop and state.get("was_desktop", True):
            state["sidebar_open"] = False
            
        state["was_desktop"] = is_desktop

        sidebar_toggle.icon = ft.Icons.MENU_OPEN_ROUNDED if state["sidebar_open"] else ft.Icons.MENU_ROUNDED

        if is_desktop:
            sidebar_container.shadow = None
            body_host.content = ft.Row(
                expand=True,
                spacing=0,
                controls=[
                    sidebar_container if state["sidebar_open"] else ft.Container(),
                    ft.VerticalDivider(width=1, color=ft.Colors.GREY_200) if state["sidebar_open"] else ft.Container(),
                    content_socket,
                ],
            )
        else:
            # On Mobile, the sidebar overlays the screen via a Stack so it doesn't squash the quiz/content
            sidebar_container.shadow = ft.BoxShadow(blur_radius=15, color=ft.Colors.BLACK26)
            
            controls_list = [content_socket]
            if state["sidebar_open"]:
                overlay_dismiss = ft.Container(expand=True, bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.BLACK), on_click=_toggle_sidebar)
                controls_list.append(
                    ft.Row(
                        expand=True,
                        spacing=0,
                        controls=[sidebar_container, overlay_dismiss]
                    )
                )
            body_host.content = ft.Stack(expand=True, controls=controls_list)
            
        page.update()

    def _toggle_sidebar(e):
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

    def go_hub():
        state["on_hub"] = True
        _reset_keyboard()
        _lock_exam_ui(False)
        _set_appbar("Study Hub", lambda: page.go("/dashboard"))
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

    def go_exam(questions: list, duration_seconds: int | None = None):
        state["on_hub"] = False
        _set_appbar("Exam Simulator", go_hub)
        content_socket.content = _build_exam(questions, duration_seconds)
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # HUB — load + layout
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_hub():
        content_socket.content = _loading("Loading Study Hub…")
        page.update()
        try:
            due_cards, materials, sub_status = await asyncio.gather(
                asyncio.wait_for(get_due_cards(token, _current_selected_ids()), timeout=15),
                asyncio.wait_for(get_materials(token),  timeout=15),
                asyncio.wait_for(get_subscription_status(token), timeout=15),
                return_exceptions=True,
            )
            if isinstance(due_cards, Exception): due_cards = []
            if isinstance(materials, Exception): materials = []
            
            # Inject Live Subscription Limits
            if not isinstance(sub_status, Exception):
                state["plan_id"]    = sub_status.get("plan_id", "free")
                state["plan_label"] = sub_status.get("label", "Free")
                state["mat_used"]   = sub_status.get("materials_used", 0)
                state["mat_lim"]    = sub_status.get("materials_limit", 5)
                state["gen_used"]   = sub_status.get("generations_used", 0)
                state["gen_lim"]    = sub_status.get("generations_limit", 10)

            state["materials"] = materials or []
            _refresh_sidebar_materials()
            _refresh_plan_ui()

            # THE FIX: Bring back the rendering step!
            content_socket.content = _build_hub(due_cards or [], materials or [])
            page.update()
            
        except Exception as ex:
            content_socket.content = _error_screen(
                f"Hub failed to load ({type(ex).__name__}).",
                on_retry=lambda: page.run_task(_load_hub),
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
    gen_status_text = ft.Text("Status: All good!", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.GREEN_700)
    gen_status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600, size=16)
    
    generation_banner = ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        bgcolor=ft.Colors.GREEN_50,
        border_radius=10,
        border=ft.Border.all(1, ft.Colors.GREEN_200),
        content=ft.Row(
            spacing=8,
            controls=[gen_status_icon, gen_status_text]
        )
    )

    async def _poll_generation_status():
        while True:
            await asyncio.sleep(4) # Aligned with your prompt's 4-second request
            
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
                        # Ping your backend: /materials/{material_id}/status
                        raw_result = await check_generation_status(token, mat_id)
                        
                        # Check exact string match from your API
                        is_active = False
                        if isinstance(raw_result, dict):
                            is_active = raw_result.get("status") == "processing"
                            
                        if is_active:
                            is_generating_anything = True
                            state["poll_strikes"][mat_id] = 0 # Reset strikes
                        else:
                            # Give it 3 strikes in case of backend DB latency
                            strikes = state["poll_strikes"].get(mat_id, 0) + 1
                            if strikes >= 3:
                                done_mats.append(mat_id)
                                state["poll_strikes"].pop(mat_id, None)
                            else:
                                state["poll_strikes"][mat_id] = strikes
                                is_generating_anything = True # Keep UI active
                            
                    # Remove finished materials from the tracker
                    for m in done_mats:
                        state["generating_mats"].discard(m)
                        
                    # --- LIVE SYNC THE DASHBOARD WHEN GENERATION FINISHES ---
                    if done_mats:
                        try:
                            live_cards = await get_due_cards(token, _current_selected_ids())
                            new_count = len(live_cards)
                            
                            # Only update if the user is currently looking at the Hub screen!
                            if state.get("live_due_text") and state["live_due_text"].page:
                                state["live_due_text"].value = str(new_count)
                                if state.get("live_streak_text"):
                                    state["live_streak_text"].value = "Keep your streak going! 🔥" if new_count > 0 else "It's cold in here! ❄️"
                                if state.get("live_fc_pill"):
                                    state["live_fc_pill"].value = f"{new_count} due" if new_count > 0 else "All done"
                                    
                                # Push only these specific elements to the screen silently
                                state["live_due_text"].update()
                                if state.get("live_streak_text"): state["live_streak_text"].update()
                                if state.get("live_fc_pill"): state["live_fc_pill"].update()
                        except Exception as ex:
                            print(f"[POLLER] ❌ Error syncing live cards: {ex}")
                    # --------------------------------------------------------
                    
                else:
                    pass
                
                # --- UPDATE THE UI ---
                if is_generating_anything:
                    generation_banner.bgcolor = ft.Colors.BLUE_50
                    generation_banner.border = ft.Border.all(1, ft.Colors.BLUE_200)
                    gen_status_icon.name = ft.Icons.AUTORENEW_ROUNDED
                    gen_status_icon.color = ft.Colors.BLUE_600
                    gen_status_text.value = "Status: Generating..."
                    gen_status_text.color = ft.Colors.BLUE_700
                else:
                    generation_banner.bgcolor = ft.Colors.GREEN_50
                    generation_banner.border = ft.Border.all(1, ft.Colors.GREEN_200)
                    gen_status_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                    gen_status_icon.color = ft.Colors.GREEN_600
                    gen_status_text.value = "Status: All good!"
                    gen_status_text.color = ft.Colors.GREEN_700
                
                # Safely update UI
                if generation_banner.page:
                    generation_banner.update() 
                    
            except Exception as e:
                # Keep logs clean from Flet mounting errors
                if "Control must be added to the page first" not in str(e):
                    print(f"[POLLER] ❌ Error during polling: {type(e).__name__} - {e}")
    # ── hub layout ────────────────────────────────────────────────────────────
    def _build_hub(due_cards: list, materials: list) -> ft.Column:
        due_count = len(due_cards)

        # --- THE FIX: STORE THESE CONTROLS IN STATE FOR TARGETED UPDATES ---
        state["live_due_text"] = ft.Text(str(due_count), size=22, weight=ft.FontWeight.W_700, color=ft.Colors.ON_PRIMARY)
        state["live_streak_text"] = ft.Text("Keep your streak going! 🔥" if due_count > 0 else "It's cold in here! ❄️", size=16, weight=ft.FontWeight.W_700, color=ft.Colors.ON_PRIMARY)

        mastery_banner = ft.Container(
            border_radius=14,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[ft.Colors.PRIMARY, ft.Colors.SECONDARY],
            ),
            padding=ft.Padding.symmetric(horizontal=20, vertical=16),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=4, expand=True,
                        controls=[
                            ft.Text("Knowledge Mastery", size=12,
                                    color=ft.Colors.with_opacity(0.85, ft.Colors.ON_PRIMARY)),
                            state["live_streak_text"], # Injecting the live streak text
                            ft.Container(height=4),
                            
                        ],
                        
                    ),
                    generation_banner,
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                        controls=[
                            ft.Container(
                                width=56, height=56,
                                bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.ON_PRIMARY),
                                border_radius=28,
                                alignment=ft.Alignment.CENTER,
                                content=state["live_due_text"], # Injecting the live number text
                            ),
                            ft.Text("cards due", size=10,
                                    color=ft.Colors.with_opacity(0.8, ft.Colors.ON_PRIMARY)),
                        ],
                    ),
                ],
            ),
        )

        def mode_card(icon, title, subtitle, badge_label, badge_bg, badge_fg,
                      on_tap, accent):
            
            # --- THE FIX: CATCH THE FLASHCARD PILL TEXT ---
            badge_control = _pill(badge_label, badge_bg, badge_fg)
            if title == "Flashcards":
                state["live_fc_pill"] = badge_control.content # Save the Text inside the pill

            return ft.Container(
                col={"xs": 12, "sm": 4},
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.GREY_200),
                padding=16,
                ink=True,
                on_click=lambda _: on_tap(),
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                    offset=ft.Offset(0, 3),
                ),
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Container(
                                    width=42, height=42,
                                    bgcolor=ft.Colors.with_opacity(0.1, accent),
                                    border_radius=12,
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(icon, color=accent, size=20),
                                ),
                                badge_control, # Injecting the modified badge
                            ],
                        ),
                        ft.Text(title, size=14, weight=ft.FontWeight.W_700,
                                color=ft.Colors.ON_SURFACE),
                        ft.Text(subtitle, size=11, color=ft.Colors.GREY_500,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text("Start →", size=12, color=accent,
                                weight=ft.FontWeight.W_600),
                    ],
                ),
            )
        sel_count = len(state["selected_mat_ids"])
        context_hint = ft.Container(
            visible=sel_count > 0,
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.PRIMARY),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY)),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.FILTER_LIST_ROUNDED,
                            color=ft.Colors.PRIMARY, size=16),
                    ft.Text(
                        f"Studying from {sel_count} selected material(s). "
                        "Deselect in sidebar to use all.",
                        size=11, color=ft.Colors.PRIMARY, expand=True,
                    ),
                ],
            ),
        )

        # NOTE: material_ids are resolved live at click-time inside each
        # mode_card's on_tap (see below) rather than snapshotted here, so
        # toggling a material chip in the sidebar after the hub has
        # rendered is respected instead of silently ignored.

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=16),
                    content=ft.Column(
                        spacing=16,
                        controls=[
                            mastery_banner,
                            context_hint,
                            _section_label("STUDY MODES"),
                            ft.ResponsiveRow(
                                spacing=12, run_spacing=12,
                                controls=[
                                    mode_card(
                                        ft.Icons.STYLE_ROUNDED,
                                        "Flashcards",
                                        "Spaced repetition — review cards due today.",
                                        f"{due_count} due" if due_count else "All done",
                                        ft.Colors.PURPLE_50, ft.Colors.PURPLE_700,
                                        lambda: page.run_task(
                                            _start_flashcards, _current_selected_ids()
                                        ),
                                        ft.Colors.PURPLE_400,
                                    ),
                                    mode_card(
                                        ft.Icons.QUIZ_ROUNDED,
                                        "Quick Quiz",
                                        "One question at a time with immediate feedback.",
                                        "Low Stakes",
                                        ft.Colors.TEAL_50, ft.Colors.TEAL_700,
                                        lambda: page.run_task(
                                            _start_quiz, _current_selected_ids()
                                        ),
                                        ft.Colors.TEAL_500,
                                    ),
                                    mode_card(
                                        ft.Icons.HISTORY_EDU_ROUNDED,
                                        "Exam Simulator",
                                        "Timed full-length exam with result breakdown.",
                                        "Timed",
                                        ft.Colors.ORANGE_50, ft.Colors.ORANGE_700,
                                        lambda: page.run_task(
                                            _start_exam, _current_selected_ids()
                                        ),
                                        ft.Colors.ORANGE_500,
                                    ),
                                ],
                            ),
                            ft.Container(height=20),
                        ],
                    ),
                )
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # UPLOAD MODAL
    # ─────────────────────────────────────────────────────────────────────────
    def _open_upload_modal():
        title_field = ft.TextField(
            label="Title / Topic *",
            border_radius=10, border_color=ft.Colors.GREY_300,
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        )
        text_field = ft.TextField(
            label="Paste your notes here",
            multiline=True, min_lines=4, max_lines=8,
            border_radius=10, border_color=ft.Colors.GREY_300,
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        )
        error_text  = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False)
        status_text = ft.Text("", color=ft.Colors.TEAL_600, size=12, visible=False)
        file_label  = ft.Text("No file selected", size=12, color=ft.Colors.GREY_400)

        selected_file_bytes = None
        selected_file_name  = None

        at_limit = state["mat_lim"] is not None and state["mat_used"] >= state["mat_lim"]
        limit_warning = ft.Container(
            visible=at_limit,
            border_radius=8,
            bgcolor=ft.Colors.RED_50,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Text(
                "Limit Reached! Upgrade your plan to add more materials.", # <-- Change this text to whatever you want!
                size=12, color=ft.Colors.RED_700,
                weight=ft.FontWeight.W_600, # Added some weight to make it pop
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
                    file_label.value    = f"Selected: {selected_file_name}"
                    file_label.color    = ft.Colors.TEAL_600
                    page.update()
            except Exception:
                file_label.value = "File picker failed — paste text instead."
                file_label.color = ft.Colors.RED_700
                page.update()

        async def submit_upload(e):
            nonlocal selected_file_bytes, selected_file_name
            if at_limit:
                return
            if not (title_field.value or "").strip():
                error_text.value   = "Please give this material a title."
                error_text.visible = True
                page.update()
                return
            if not (text_field.value or "").strip() and not selected_file_bytes:
                error_text.value   = "Please paste notes or upload a file."
                error_text.visible = True
                page.update()
                return

            error_text.visible  = False
            submit_btn.disabled = True
            submit_btn.content  = ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=14, height=14,
                                    color=ft.Colors.ON_PRIMARY, stroke_width=2),
                    ft.Text("Uploading...",
                            color=ft.Colors.ON_PRIMARY, size=12),
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
                status_text.value   = (
                    f"✓ Uploaded! Go ahead and start studying!"
                )
                status_text.visible = True
                submit_btn.disabled = False
                submit_btn.content  = ft.Text("Upload Another",
                                               color=ft.Colors.ON_PRIMARY,
                                               size=13, weight=ft.FontWeight.W_600)

                new_mat = {
                    "id": result.get("material_id", f"mat_{len(state['materials'])+1}"),
                    "title": title_field.value.strip(),
                    "source_type": "pdf" if selected_file_bytes else "text",
                    "created_at": "2025-08-27",
                }
                state["materials"].append(new_mat)
                state["mat_used"] += 1
                
                _refresh_sidebar_materials()
                _refresh_plan_ui()

                title_field.value       = ""
                text_field.value        = ""
                selected_file_bytes     = None
                selected_file_name      = None
                file_label.value        = "No file selected"
                file_label.color        = ft.Colors.GREY_400
                page.update()

            except asyncio.TimeoutError:
                error_text.value   = "Upload timed out. Check your connection."
                error_text.visible = True
                submit_btn.disabled = False
                submit_btn.content  = ft.Text("Upload", color=ft.Colors.ON_PRIMARY,
                                               size=13, weight=ft.FontWeight.W_600)
                page.update()
            except Exception as ex:
                error_text.value   = f"Upload failed ({type(ex).__name__})."
                error_text.visible = True
                submit_btn.disabled = False
                submit_btn.content  = ft.Text("Upload", color=ft.Colors.ON_PRIMARY,
                                               size=13, weight=ft.FontWeight.W_600)
                page.update()

        submit_btn = ft.ElevatedButton(
            content=ft.Text("Upload", color=ft.Colors.ON_PRIMARY,
                            size=13, weight=ft.FontWeight.W_600),
            bgcolor=ft.Colors.PRIMARY,
            expand=True, height=44,
            disabled=at_limit,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10), elevation=0
            ),
            on_click=submit_upload,
        )

        # THE FIX: Defining a proper close_modal handler that modifies the overlay state natively
        def close_modal(e):
            modal.open = False
            page.update()

        modal = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                width=float("inf"),
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("Upload Study Material", size=16,
                            weight=ft.FontWeight.W_700),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18,
                                  icon_color=ft.Colors.GREY_400,
                                  on_click=close_modal), # Replaced page.pop_dialog()
                ],
            ),
            content=ft.Container(
                width=float("inf"),
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO, height=440,
                    spacing=14,
                    controls=[
                        limit_warning,
                        _section_label("TOPIC TITLE"),
                        title_field,
                        _section_label("PASTE NOTES"),
                        text_field,
                        _section_label("OR UPLOAD FILE  (PDF / TXT / MD)"),
                        ft.Container(
                            border_radius=10,
                            width=float("inf"),
                            border=ft.Border.all(1, ft.Colors.GREY_300),
                            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                            ink=True,
                            on_click=pick_file,
                            content=ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Icon(ft.Icons.ATTACH_FILE_ROUNDED,
                                            color=ft.Colors.PRIMARY, size=18),
                                    file_label,
                                ],
                            ),
                        ),
                        error_text,
                        status_text,
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

        cb_flashcards = ft.Checkbox(label="Flashcards (SRS cards)",
                                    value=True, active_color=ft.Colors.PURPLE_400)
        cb_quiz       = ft.Checkbox(label="Quick Quiz questions",
                                    value=False, active_color=ft.Colors.TEAL_500)
        cb_exam       = ft.Checkbox(label="Exam questions",
                                    value=False, active_color=ft.Colors.ORANGE_500)

        gen_error  = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False)
        gen_status = ft.Text("", color=ft.Colors.TEAL_600, size=12, visible=False)

        mats = state["materials"]
        panel_selected: set = set(state["selected_mat_ids"]) 

        panel_mat_checks: list[ft.Checkbox] = []
        for mat in mats:
            cb = ft.Checkbox(
                label=mat.get("title", "Untitled"),
                value=mat["id"] in panel_selected,
                data=mat["id"],
                active_color=ft.Colors.PRIMARY,
            )
            def _on_mat_cb(e, mid=mat["id"]):
                if e.control.value:
                    panel_selected.add(mid)
                else:
                    panel_selected.discard(mid)
            cb.on_change = _on_mat_cb
            panel_mat_checks.append(cb)

        gen_btn = ft.ElevatedButton(
            content=ft.Text("Generate", color=ft.Colors.ON_PRIMARY,
                            size=13, weight=ft.FontWeight.W_600),
            bgcolor=ft.Colors.PURPLE_400,
            expand=True, height=44,
            disabled=at_gen_limit,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10), elevation=0
            ),
        )

        async def do_generate(e):
            selected_types = []
            if cb_flashcards.value: selected_types.append("flashcards")
            if cb_quiz.value:       selected_types.append("quiz")
            if cb_exam.value:       selected_types.append("exam")

            if not selected_types:
                gen_error.value   = "Select at least one output type."
                gen_error.visible = True
                page.update()
                return

            # Keep your original fallback logic!
            mat_ids = list(panel_selected) or [m["id"] for m in mats]
            if not mat_ids:
                gen_error.value   = "Upload at least one material first."
                gen_error.visible = True
                page.update()
                return

            gen_error.visible  = False
            gen_btn.disabled   = True
            gen_btn.content    = ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=14, height=14, color=ft.Colors.ON_PRIMARY, stroke_width=2),
                    ft.Text("Queuing AI Tasks…", color=ft.Colors.ON_PRIMARY, size=12),
                ],
            )
            page.update()

            # --- CRITICAL FIX 1: ADD TO TRACKER IMMEDIATELY ---
            for m_id in mat_ids:
                state["generating_mats"].add(m_id)
                state["poll_strikes"][m_id] = 0

            try:
                # This will return almost instantly because of BackgroundTasks
                result = await asyncio.wait_for(
                    generate_from_materials(token, mat_ids, selected_types),
                    timeout=30,
                )
                
                # --- CRITICAL FIX 2: DO NOT DELETE FROM TRACKER HERE ---
                # We leave them in the list so the Poller can aggressively track them!
                
                state["gen_used"] += 1
                _refresh_plan_ui()
                
                gen_status.value   = f" ✓ Tasks queued! AI is generating in the background."
                gen_status.visible = True
                gen_btn.disabled   = False
                gen_btn.content    = ft.Text("Generate", color=ft.Colors.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600)
                page.update()

            except asyncio.TimeoutError:
                gen_error.value   = "Server request timed out. Try again."
                gen_error.visible = True
                gen_btn.disabled  = False
                gen_btn.content   = ft.Text("Generate", color=ft.Colors.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600)
                
                # Only clean up if it outright failed to queue
                for m_id in mat_ids: state["generating_mats"].discard(m_id)
                page.update()
                
            except Exception as ex:
                gen_error.value   = f"Failed to queue tasks, please try again."
                gen_error.visible = True
                gen_btn.disabled  = False
                gen_btn.content   = ft.Text("Generate", color=ft.Colors.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600)
                
                # Only clean up if it outright failed to queue
                for m_id in mat_ids: state["generating_mats"].discard(m_id)
                page.update()

        gen_btn.on_click = do_generate

        gen_bar_panel = _limit_bar(
            "Generations this period",
            state["gen_used"],
            state["gen_lim"],
            ft.Colors.PURPLE_400,
        )

        limit_row = ft.Container(
            visible=at_gen_limit,
            border_radius=8,
            bgcolor=ft.Colors.RED_50,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Text(
                "Limit Reached! Upgrade your plan to generate more.", # <-- Change this text to whatever you want!
                size=12, color=ft.Colors.RED_700,
                weight=ft.FontWeight.W_600,
            ),
        )

        remaining_chip = ft.Container(
            visible=state["gen_lim"] is not None and not at_gen_limit,
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PURPLE_400),
            border_radius=8,
            content=ft.Text(
                f"{gen_remaining} generation(s) remaining" if gen_remaining else "",
                size=10, color=ft.Colors.PURPLE_700,
            ),
        )

        # THE FIX: Defined proper local modal closer
        def close_generate_modal(e):
            modal.open = False
            page.update()

        modal = ft.AlertDialog(
            modal=False, 
            on_dismiss=close_generate_modal,
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED,
                                    color=ft.Colors.PURPLE_400, size=18),
                            ft.Text("Generate Study Content", size=16,
                                    weight=ft.FontWeight.W_700),
                        ],
                    ),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18,
                                  icon_color=ft.Colors.GREY_400,
                                  on_click=close_generate_modal), # Replaced page.pop_dialog()
                ],
            ),
            content=ft.Container(
                width=500,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO, height=480,
                    spacing=16,
                    controls=[
                        limit_row,
                        gen_bar_panel,
                        remaining_chip,
                        ft.Divider(height=1, color=ft.Colors.GREY_100),
                        _section_label("SELECT MATERIALS"),
                        ft.Column(
                            spacing=4,
                            controls=panel_mat_checks if panel_mat_checks
                            else [ft.Text("No materials uploaded yet.",
                                          size=12, color=ft.Colors.GREY_400)],
                        ),
                        ft.Divider(height=1, color=ft.Colors.GREY_100),
                        _section_label("GENERATE"),
                        ft.Column(
                            spacing=4,
                            controls=[cb_flashcards, cb_quiz, cb_exam],
                        ),
                        gen_error,
                        gen_status,
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
        )


    # ─────────────────────────────────────────────────────────────────────────
    # BOOT
    # ─────────────────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────
    # BOOT & MOBILE LAYOUT FIX
    # ─────────────────────────────────────────────────────────────────────────
    # Pin the sidebar securely
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
            mobile_overlay.visible = False
            sidebar_container.shadow = None
            sidebar_container.visible = state["sidebar_open"]
            
            # Push content right (300px) to make room for the sidebar
            main_content_wrapper.padding = ft.Padding.only(left=300 if state["sidebar_open"] else 0)
        else:
            sidebar_container.shadow = ft.BoxShadow(blur_radius=20, color=ft.Colors.BLACK26)
            sidebar_container.visible = state["sidebar_open"]
            mobile_overlay.visible = state["sidebar_open"]
            
            # Content takes full screen; sidebar overlays it
            main_content_wrapper.padding = 0

        page.update()

    def _toggle_sidebar(e):
        state["sidebar_open"] = not state["sidebar_open"]
        update_layout()

    sidebar_toggle.on_click = _toggle_sidebar
    page.on_resize = update_layout
    
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

