"""
Interactive Question Curator & CBT Editor Studio
Provides administrators and educators with a professional dual-pane studio
to inspect, refine, reorder, and edit questions generated from past exam papers,
configure exam duration & coin pricing, and attach inline diagram figures.
Supports 4 or 5 options (JAMB/WAEC/NECO) and responsive dual-pane/mobile layouts.
"""

import asyncio
import flet as ft
from typing import List, Dict, Any, Callable, Optional
from src.components import study_ui as ui
from src.utils.file_opener import show_page_snackbar
from src.requests.marketplace import upload_cbt_diagram_image_api

_LETTERS = ["A", "B", "C", "D", "E"]
_THEMES = [
    ("emerald_teal", "Emerald Teal"),
    ("purple_indigo", "Purple Indigo"),
    ("oceanic_blue", "Oceanic Blue"),
    ("sunset_orange", "Sunset Orange"),
    ("rose_amber", "Rose Amber"),
    ("midnight_dark", "Midnight Dark"),
]


def show_question_curator_dialog(
    page: ft.Page,
    initial_questions: List[Dict[str, Any]],
    pack_title: str,
    subject: str = "General",
    exam_type: str = "General CBT",
    exam_year: Optional[int] = None,
    initial_price_coins: int = 0,
    initial_theme_gradient: str = "emerald_teal",
    initial_description: str = "",
    initial_duration_minutes: int = 60,
    on_publish: Optional[Callable[[Dict[str, Any]], Any]] = None,
    token: Optional[str] = None,
    save_button_label: str = "Publish Official CBT Pack",
):
    """
    Renders the Question Curator & CBT Editor modal.
    Adapts from a spacious dual-pane desktop studio into a streamlined mobile flow.
    Adheres strictly to Flet 0.86.5 conventions.
    """
    screen_width = page.width or 800
    screen_height = page.height or 800
    is_desktop = screen_width >= 880

    # Deep copy questions to mutate locally
    questions: List[Dict[str, Any]] = []
    for q in (initial_questions or []):
        raw_opts = list(q.get("options") or ["", "", "", ""])
        while len(raw_opts) < 4:
            raw_opts.append("")
        raw_opts = raw_opts[:5]
        questions.append({
            "question_text": q.get("question_text", q.get("question", "")),
            "options": raw_opts,
            "answer_index": int(q.get("answer_index", q.get("answer", 0))),
            "explanation": q.get("explanation", ""),
            "topic": q.get("topic", subject),
            "difficulty": q.get("difficulty", "standard"),
            "image_url": q.get("image_url") or "",
            "has_diagram": bool(q.get("has_diagram") or q.get("image_url")),
            "num_options": len(raw_opts) if len(raw_opts) in (4, 5) else 4,
        })

    if not questions:
        questions.append({
            "question_text": "Sample CBT Question 1",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer_index": 0,
            "explanation": "Explanation of correct option.",
            "topic": subject,
            "difficulty": "standard",
            "image_url": "",
            "has_diagram": False,
            "num_options": 4,
        })

    active_idx = [0]
    filter_mode = ["all"]
    settings_open = [False]

    # --- Header / Metadata Controls ---
    title_field = ft.TextField(
        value=pack_title,
        label="CBT Study Pack Title",
        border_color=ui.hairline(0.18),
        dense=True,
        expand=True,
    )
    category_field = ft.TextField(
        value=subject,
        label="Subject / Category",
        border_color=ui.hairline(0.18),
        dense=True,
        width=160 if is_desktop else None,
    )
    exam_type_field = ft.TextField(
        value=exam_type,
        label="Exam Board",
        border_color=ui.hairline(0.18),
        dense=True,
        width=140 if is_desktop else None,
    )
    year_field = ft.TextField(
        value=str(exam_year) if exam_year else "2025",
        label="Exam Year",
        border_color=ui.hairline(0.18),
        dense=True,
        width=100 if is_desktop else None,
    )
    price_coins_field = ft.TextField(
        value=str(initial_price_coins or 0),
        label="Price (Coins)",
        hint_text="0 for Free",
        border_color=ui.hairline(0.18),
        dense=True,
        width=120 if is_desktop else None,
    )
    duration_field = ft.TextField(
        value=str(initial_duration_minutes or 60),
        label="Duration (Mins)",
        border_color=ui.hairline(0.18),
        dense=True,
        width=130 if is_desktop else None,
    )
    theme_dropdown = ft.Dropdown(
        label="Theme Palette",
        dense=True,
        width=160 if is_desktop else None,
        options=[ft.dropdown.Option(k, v) for k, v in _THEMES],
        value=initial_theme_gradient or "emerald_teal",
    )
    desc_field = ft.TextField(
        value=initial_description or (
            f"Official {exam_type} Past Questions practice pack with comprehensive step-by-step explanations."
            if exam_type and "GENERAL" not in str(exam_type).upper()
            else "Comprehensive CBT practice pack with step-by-step explanations."
        ),
        label="Exam Instructions / Overview",
        multiline=True,
        min_lines=2,
        max_lines=3,
        dense=True,
        border_color=ui.hairline(0.18),
        expand=True,
    )

    # --- Active Question Editor Controls ---
    q_text_input = ft.TextField(
        multiline=True,
        min_lines=3,
        max_lines=6,
        label="Question Body (Markdown supported)",
        border_color=ui.hairline(0.20),
    )

    topic_input = ft.TextField(
        label="Syllabus Topic (e.g. Current Electricity)",
        border_color=ui.hairline(0.18),
        dense=True,
        expand=True,
    )

    difficulty_dropdown = ft.Dropdown(
        label="Difficulty",
        dense=True,
        width=120,
        options=[
            ft.dropdown.Option("easy", "Easy"),
            ft.dropdown.Option("standard", "Standard"),
            ft.dropdown.Option("hard", "Hard"),
        ],
        value="standard",
    )

    num_options_dropdown = ft.Dropdown(
        label="Options Count",
        dense=True,
        width=130,
        options=[
            ft.dropdown.Option("4", "4 (A-D)"),
            ft.dropdown.Option("5", "5 (A-E)"),
        ],
        value="4",
    )

    # Inline Image / Diagram Controls
    image_url_input = ft.TextField(
        label="Inline Diagram Image URL (Web or CDN)",
        border_color=ui.hairline(0.18),
        dense=True,
        expand=True,
        hint_text="https://... (circuit, map, formula, graph)",
    )

    upload_img_btn = ft.FilledButton(
        "Upload Figure",
        icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
        style=ft.ButtonStyle(
            bgcolor=ui.tint(ft.Colors.PRIMARY, 0.15),
            color=ft.Colors.PRIMARY,
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
        tooltip="Upload image from computer directly to Nu-age CDN",
    )

    diagram_input_control = (
        ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                image_url_input,
                upload_img_btn,
            ],
        )
        if is_desktop
        else ft.Column(
            spacing=6,
            controls=[
                image_url_input,
                ft.Row([upload_img_btn], alignment=ft.MainAxisAlignment.END),
            ],
        )
    )

    diagram_preview_container = ft.Container(visible=False)

    diagram_hint_banner = ft.Container(
        visible=False,
        bgcolor=ui.tint(ui.C_WARN, 0.12),
        border=ft.Border.all(1, ui.tint(ui.C_WARN, 0.35)),
        border_radius=ft.BorderRadius.all(8),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        content=ft.Row(
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=16, color=ui.C_WARN),
                ft.Text(
                    "This question references a figure/diagram. Attach an image URL above so learners can see the illustration.",
                    size=11,
                    weight=ft.FontWeight.W_600,
                    color=ui.C_WARN,
                    expand=True,
                ),
            ],
        ),
    )

    # 5 Option inputs (A-E)
    opt_inputs = [
        ft.TextField(dense=True, expand=True, border_color=ui.hairline(0.15))
        for _ in range(5)
    ]
    radio_group = ft.RadioGroup(
        content=ft.Column(spacing=6),
        value="0",
    )

    expl_input = ft.TextField(
        multiline=True,
        min_lines=2,
        max_lines=5,
        label="Step-by-Step Explanation / Working",
        border_color=ui.hairline(0.18),
    )

    # Question list containers
    q_directory_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO)
    filter_bar_container = ft.Row(spacing=6, scroll=ft.ScrollMode.AUTO)
    mobile_chips_row = ft.Row(spacing=6, scroll=ft.ScrollMode.AUTO)

    # Header summary indicator labels
    pack_title_summary = ft.Text(pack_title or "Untitled Pack", size=14, weight=ft.FontWeight.BOLD, no_wrap=True)
    pack_meta_pill = ft.Text(f"{exam_type} • {len(questions)} Qs", size=11, color=ui.muted(0.70))

    def _sync_active_to_state():
        if not (0 <= active_idx[0] < len(questions)):
            return
        curr = questions[active_idx[0]]
        curr["question_text"] = (q_text_input.value or "").strip()

        opt_cnt = int(num_options_dropdown.value or "4")
        curr["num_options"] = opt_cnt
        curr["options"] = [(opt_inputs[i].value or "").strip() for i in range(opt_cnt)]

        try:
            curr["answer_index"] = min(int(radio_group.value or "0"), opt_cnt - 1)
        except ValueError:
            curr["answer_index"] = 0
        curr["explanation"] = (expl_input.value or "").strip()
        curr["topic"] = (topic_input.value or "").strip() or subject
        curr["difficulty"] = difficulty_dropdown.value or "standard"
        curr["image_url"] = (image_url_input.value or "").strip()
        curr["has_diagram"] = bool(curr["image_url"])

    def _update_diagram_preview(url: str):
        if url:
            diagram_preview_container.content = ft.Container(
                bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.04),
                border=ft.Border.all(1, ui.hairline(0.14)),
                border_radius=ft.BorderRadius.all(8),
                padding=8,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Image(
                            src=url,
                            fit=ft.BoxFit.CONTAIN,
                            height=140,
                            border_radius=ft.BorderRadius.all(6),
                        ),
                        ft.Text("Inline Figure / Diagram Preview", size=10, color=ui.muted(0.60)),
                    ],
                ),
            )
            diagram_preview_container.visible = True
        else:
            diagram_preview_container.visible = False
            diagram_preview_container.content = None

    def _rebuild_radio_rows(opt_cnt: int):
        rows = []
        for i in range(opt_cnt):
            rows.append(
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Radio(value=str(i), fill_color=ft.Colors.PRIMARY),
                        ft.Text(f"{_LETTERS[i]}.", size=12, weight=ft.FontWeight.BOLD, color=ui.muted(0.70)),
                        opt_inputs[i],
                    ],
                )
            )
        radio_group.content = ft.Column(spacing=6, controls=rows)

    def _load_state_to_inputs():
        if not (0 <= active_idx[0] < len(questions)):
            return
        curr = questions[active_idx[0]]
        q_text_input.value = curr.get("question_text", "")
        opts = list(curr.get("options") or ["", "", "", ""])
        while len(opts) < 5:
            opts.append("")

        opt_cnt = curr.get("num_options", 4)
        if len(curr.get("options", [])) >= 5:
            opt_cnt = 5
        num_options_dropdown.value = str(opt_cnt)

        for i in range(5):
            opt_inputs[i].value = opts[i]
            opt_inputs[i].visible = (i < opt_cnt)

        radio_group.value = str(min(curr.get("answer_index", 0), opt_cnt - 1))
        expl_input.value = curr.get("explanation", "")
        topic_input.value = curr.get("topic", subject)
        difficulty_dropdown.value = curr.get("difficulty", "standard")
        img_url = curr.get("image_url", "")
        image_url_input.value = img_url

        _update_diagram_preview(img_url)

        text_lower = q_text_input.value.lower()
        mentions_diagram = any(w in text_lower for w in ["diagram", "figure", "illustration", "circuit", "graph", "shown below"])
        diagram_hint_banner.visible = mentions_diagram and not bool(img_url)

        _rebuild_radio_rows(opt_cnt)
        _render_directory()
        _render_filters()

    def _on_options_count_change(e=None):
        opt_cnt = int(num_options_dropdown.value or "4")
        if 0 <= active_idx[0] < len(questions):
            questions[active_idx[0]]["num_options"] = opt_cnt
        _rebuild_radio_rows(opt_cnt)
        page.update()

    num_options_dropdown.on_change = _on_options_count_change

    def _on_img_change(e=None):
        url = (image_url_input.value or "").strip()
        _update_diagram_preview(url)
        if url:
            diagram_hint_banner.visible = False
        else:
            text_lower = q_text_input.value.lower()
            mentions_diagram = any(w in text_lower for w in ["diagram", "figure", "illustration", "circuit", "graph", "shown below"])
            diagram_hint_banner.visible = mentions_diagram
        page.update()

    image_url_input.on_change = _on_img_change

    async def _pick_and_upload_image(e=None):
        if upload_img_btn.disabled:
            return
        upload_img_btn.disabled = True
        upload_img_btn.text = "Selecting file..."
        page.update()

        try:
            files = await ft.FilePicker().pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )

            if not files:
                upload_img_btn.disabled = False
                upload_img_btn.text = "Upload Figure"
                page.update()
                return

            f = files[0]
            upload_img_btn.text = f"Uploading {f.name[:12]}..."
            page.update()

            file_bytes = getattr(f, "bytes", None)
            if not file_bytes and getattr(f, "path", None):
                try:
                    with open(f.path, "rb") as fp:
                        file_bytes = fp.read()
                except Exception:
                    file_bytes = None

            if not file_bytes:
                show_page_snackbar(page, "Failed to read image file data.")
                upload_img_btn.disabled = False
                upload_img_btn.text = "Upload Figure"
                page.update()
                return

            active_token = token or page.session.get("token") or page.client_storage.get("token") or ""

            res = await upload_cbt_diagram_image_api(
                token=active_token,
                file_name=f.name,
                file_bytes=file_bytes,
            )

            cdn_url = res.get("url") or res.get("view_url") or ""
            if res.get("error") or not cdn_url:
                show_page_snackbar(page, f"CDN Upload failed: {res.get('error', 'Unknown error')}")
            else:
                image_url_input.value = cdn_url
                _on_img_change()
                if 0 <= active_idx[0] < len(questions):
                    questions[active_idx[0]]["image_url"] = cdn_url
                    questions[active_idx[0]]["has_diagram"] = True
                show_page_snackbar(page, "Figure uploaded to CDN and linked successfully!")
        except Exception as ex:
            show_page_snackbar(page, f"Error uploading figure: {ex}")
        finally:
            upload_img_btn.disabled = False
            upload_img_btn.text = "Upload Figure"
            page.update()

    upload_img_btn.on_click = lambda e: asyncio.create_task(_pick_and_upload_image(e))

    def _render_filters():
        diag_count = sum(1 for q in questions if q.get("image_url") or q.get("has_diagram"))
        no_expl_count = sum(1 for q in questions if not (q.get("explanation") or "").strip())

        filter_bar_container.controls = [
            ft.Chip(
                label=ft.Text(f"All ({len(questions)})", size=10),
                selected=(filter_mode[0] == "all"),
                on_select=lambda _: _set_filter("all"),
            ),
            ft.Chip(
                label=ft.Text(f"Diagrams ({diag_count})", size=10),
                selected=(filter_mode[0] == "diagram"),
                on_select=lambda _: _set_filter("diagram"),
            ),
            ft.Chip(
                label=ft.Text(f"Missing Expl ({no_expl_count})", size=10),
                selected=(filter_mode[0] == "no_expl"),
                on_select=lambda _: _set_filter("no_expl"),
            ),
        ]

    def _set_filter(f_mode: str):
        filter_mode[0] = f_mode
        _render_directory()
        _render_filters()
        page.update()

    def _select_q(idx: int):
        _sync_active_to_state()
        active_idx[0] = idx
        _load_state_to_inputs()
        page.update()

    def _render_directory():
        q_directory_col.controls.clear()
        mobile_chips_row.controls.clear()
        f = filter_mode[0]

        pack_title_summary.value = (title_field.value or "").strip() or "Untitled Pack"
        pack_meta_pill.value = f"{exam_type_field.value or 'CBT'} • {len(questions)} Qs"

        for idx, q in enumerate(questions):
            has_img = bool(q.get("image_url") or q.get("has_diagram"))
            missing_expl = not bool((q.get("explanation") or "").strip())

            if f == "diagram" and not has_img:
                continue
            if f == "no_expl" and not missing_expl:
                continue

            is_active = (idx == active_idx[0])
            bg = ui.tint(ft.Colors.PRIMARY, 0.12) if is_active else ui.tint(ft.Colors.ON_SURFACE, 0.03)
            border_color = ft.Colors.PRIMARY if is_active else ui.hairline(0.12)

            q_text_snippet = (q.get("question_text") or "Empty question").replace("\n", " ").strip()
            if len(q_text_snippet) > 42:
                q_text_snippet = q_text_snippet[:40] + "…"

            badges = []
            if has_img:
                badges.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.IMAGE_ROUNDED, size=10, color=ui.C_INFO),
                            ft.Text("Fig", size=9, weight=ft.FontWeight.BOLD, color=ui.C_INFO),
                        ], spacing=2, tight=True),
                        bgcolor=ui.tint(ui.C_INFO, 0.12),
                        padding=ft.Padding.symmetric(horizontal=4, vertical=2),
                        border_radius=4,
                    )
                )
            if missing_expl:
                badges.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=10, color=ui.C_WARN),
                            ft.Text("No Sol", size=9, weight=ft.FontWeight.BOLD, color=ui.C_WARN),
                        ], spacing=2, tight=True),
                        bgcolor=ui.tint(ui.C_WARN, 0.12),
                        padding=ft.Padding.symmetric(horizontal=4, vertical=2),
                        border_radius=4,
                    )
                )

            # Left rail card
            q_directory_col.controls.append(
                ft.Container(
                    bgcolor=bg,
                    border=ft.Border.all(1.5 if is_active else 1, border_color),
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    ink=True,
                    on_click=lambda _, i=idx: _select_q(i),
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(f"Question {idx + 1}", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE),
                                    ft.Row(badges, spacing=4, tight=True),
                                ],
                            ),
                            ft.Text(q_text_snippet, size=11, color=ui.muted(0.75), max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                    ),
                )
            )

            # Mobile compact chip
            mobile_chips_row.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    border_radius=8,
                    bgcolor=ft.Colors.PRIMARY if is_active else ui.tint(ft.Colors.ON_SURFACE, 0.05),
                    border=ft.Border.all(1, ft.Colors.PRIMARY if is_active else ui.hairline(0.15)),
                    ink=True,
                    on_click=lambda _, i=idx: _select_q(i),
                    content=ft.Text(
                        f"Q{idx+1}",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ON_PRIMARY if is_active else ui.muted(0.80),
                    ),
                )
            )

    def _add_q(e=None):
        _sync_active_to_state()
        questions.append({
            "question_text": f"New CBT Question {len(questions) + 1}",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer_index": 0,
            "explanation": "",
            "topic": (topic_input.value or "").strip() or subject,
            "difficulty": "standard",
            "image_url": "",
            "has_diagram": False,
            "num_options": 4,
        })
        active_idx[0] = len(questions) - 1
        _load_state_to_inputs()
        page.update()

    def _delete_q(e=None):
        if len(questions) <= 1:
            show_page_snackbar(page, "A CBT pack must contain at least 1 question.")
            return
        del questions[active_idx[0]]
        active_idx[0] = max(0, active_idx[0] - 1)
        _load_state_to_inputs()
        page.update()

    def _move_q_up(e=None):
        if active_idx[0] <= 0:
            return
        _sync_active_to_state()
        curr_i = active_idx[0]
        questions[curr_i - 1], questions[curr_i] = questions[curr_i], questions[curr_i - 1]
        active_idx[0] = curr_i - 1
        _load_state_to_inputs()
        page.update()

    def _move_q_down(e=None):
        if active_idx[0] >= len(questions) - 1:
            return
        _sync_active_to_state()
        curr_i = active_idx[0]
        questions[curr_i + 1], questions[curr_i] = questions[curr_i], questions[curr_i + 1]
        active_idx[0] = curr_i + 1
        _load_state_to_inputs()
        page.update()

    dlg_ref = [None]

    def _close_dlg(e=None):
        if dlg_ref[0]:
            dlg_ref[0].open = False
            page.update()

    def _do_publish(e=None):
        _sync_active_to_state()

        for idx, q in enumerate(questions):
            q_txt = (q.get("question_text") or "").strip()
            if not q_txt:
                show_page_snackbar(page, f"Question {idx + 1} has empty question text. Please provide question content.")
                _select_q(idx)
                return
            opts = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
            if len(opts) < 2:
                show_page_snackbar(page, f"Question {idx + 1} must have at least 2 valid answer choices.")
                _select_q(idx)
                return

        p_coins_str = (price_coins_field.value or "").strip()
        pack_coins = int(p_coins_str) if p_coins_str.isdigit() else 0
        dur_str = (duration_field.value or "").strip()
        dur_mins = int(dur_str) if dur_str.isdigit() else 60
        yr_str = (year_field.value or "").strip()

        final_pack_data = {
            "title": (title_field.value or "").strip() or "CBT Past Questions Pack",
            "category": (category_field.value or "").strip() or subject,
            "exam_type": (exam_type_field.value or "").strip() or exam_type,
            "exam_year": int(yr_str) if yr_str.isdigit() else exam_year,
            "description": (desc_field.value or "").strip(),
            "price_coins": max(0, pack_coins),
            "theme_gradient": theme_dropdown.value or "emerald_teal",
            "duration_minutes": max(5, dur_mins),
            "duration_seconds": max(5, dur_mins) * 60,
            "questions": questions,
            "questions_count": len(questions),
        }
        _close_dlg()
        if on_publish:
            on_publish(final_pack_data)

    # Initial load of controls
    _load_state_to_inputs()

    # --- Collapsible Settings Card ---
    settings_content_card = ui.surface_card(
        ft.Column(
            spacing=10,
            controls=[
                ft.Row([title_field, category_field], spacing=10),
                ft.Row([exam_type_field, year_field, price_coins_field, duration_field, theme_dropdown], spacing=10),
                desc_field,
            ],
        ),
        padding=12,
    )
    settings_container = ft.Container(
        visible=False,
        content=settings_content_card,
        animate_opacity=200,
    )

    settings_toggle_icon = ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, size=18, color=ft.Colors.PRIMARY)
    settings_toggle_label = ft.Text("Pack Settings & Commerce", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY)

    def _toggle_settings(e=None):
        settings_open[0] = not settings_open[0]
        settings_container.visible = settings_open[0]
        settings_toggle_icon.name = ft.Icons.KEYBOARD_ARROW_UP_ROUNDED if settings_open[0] else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
        page.update()

    settings_toggle_bar = ft.Container(
        ink=True,
        on_click=_toggle_settings,
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border_radius=8,
        bgcolor=ui.tint(ft.Colors.PRIMARY, 0.08),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.SETTINGS_OUTLINED, size=16, color=ft.Colors.PRIMARY),
                    settings_toggle_label,
                    pack_meta_pill,
                ], spacing=8, tight=True),
                settings_toggle_icon,
            ],
        ),
    )

    # --- Studio Body Layout ---
    if is_desktop:
        # Dual-Pane layout
        left_rail = ft.Container(
            width=290,
            bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.02),
            border=ft.Border.all(1, ui.hairline(0.12)),
            border_radius=10,
            padding=10,
            content=ft.Column(
                spacing=8,
                expand=True,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Questions", size=13, weight=ft.FontWeight.BOLD),
                            ft.TextButton(
                                "+ Add",
                                icon=ft.Icons.ADD_ROUNDED,
                                on_click=_add_q,
                            ),
                        ],
                    ),
                    filter_bar_container,
                    ft.Divider(height=1, color=ui.hairline(0.10)),
                    ft.Container(
                        content=q_directory_col,
                        expand=True,
                    ),
                ],
            ),
        )

        right_canvas = ft.Container(
            expand=True,
            content=ft.Column(
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ui.surface_card(
                        ft.Column(
                            spacing=10,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Row([
                                            ui.section_label("Question Details"),
                                            ft.IconButton(ft.Icons.ARROW_UPWARD_ROUNDED, tooltip="Move Up", icon_size=16, on_click=_move_q_up),
                                            ft.IconButton(ft.Icons.ARROW_DOWNWARD_ROUNDED, tooltip="Move Down", icon_size=16, on_click=_move_q_down),
                                            ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, tooltip="Delete Question", icon_size=16, icon_color=ui.C_WRONG, on_click=_delete_q),
                                        ], spacing=4, tight=True),
                                        ft.Row([
                                            difficulty_dropdown,
                                            num_options_dropdown,
                                        ], spacing=8, tight=True),
                                    ],
                                ),
                                topic_input,
                                diagram_hint_banner,
                                q_text_input,
                                diagram_input_control,
                                diagram_preview_container,
                                ft.Divider(height=1, color=ui.hairline(0.10)),
                                ft.Row([
                                    ft.Text("Answer Choices (Mark the correct answer):", size=12, weight=ft.FontWeight.BOLD),
                                    ft.Text("A through E supported", size=11, color=ui.muted(0.60)),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                radio_group,
                                ft.Divider(height=1, color=ui.hairline(0.10)),
                                expl_input,
                            ],
                        ),
                        padding=14,
                    ),
                ],
            ),
        )

        body_content = ft.Row(
            spacing=12,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[left_rail, right_canvas],
        )
    else:
        # Mobile stacked layout
        body_content = ft.Column(
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            controls=[
                ft.Row([
                    ft.Text(f"Questions ({len(questions)})", size=12, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.IconButton(ft.Icons.ADD_ROUNDED, tooltip="Add", icon_size=18, on_click=_add_q),
                        ft.IconButton(ft.Icons.ARROW_UPWARD_ROUNDED, tooltip="Move Up", icon_size=16, on_click=_move_q_up),
                        ft.IconButton(ft.Icons.ARROW_DOWNWARD_ROUNDED, tooltip="Move Down", icon_size=16, on_click=_move_q_down),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, tooltip="Delete", icon_size=16, icon_color=ui.C_WRONG, on_click=_delete_q),
                    ], spacing=2, tight=True),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                filter_bar_container,
                mobile_chips_row,
                ft.Divider(height=1, color=ui.hairline(0.10)),
                topic_input,
                ft.Row([difficulty_dropdown, num_options_dropdown], spacing=8),
                diagram_hint_banner,
                q_text_input,
                diagram_input_control,
                diagram_preview_container,
                ft.Divider(height=1, color=ui.hairline(0.10)),
                ft.Text("Answer Choices (Mark the correct answer):", size=12, weight=ft.FontWeight.BOLD),
                radio_group,
                ft.Divider(height=1, color=ui.hairline(0.10)),
                expl_input,
            ],
        )

    modal_width = min(1180, int(screen_width * 0.96))
    modal_height = min(780, int(screen_height * 0.90))

    dlg_content = ft.Container(
        width=modal_width,
        height=modal_height,
        content=ft.Column(
            spacing=8,
            expand=True,
            controls=[
                settings_toggle_bar,
                settings_container,
                body_content,
            ],
        ),
    )

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                        pack_title_summary,
                    ],
                ),
                ft.IconButton(ft.Icons.CLOSE_ROUNDED, tooltip="Close", on_click=_close_dlg),
            ],
        ),
        content=dlg_content,
        actions=[
            ft.TextButton("Cancel", on_click=_close_dlg),
            ft.FilledButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.SAVE_ROUNDED if "save" in save_button_label.lower() else ft.Icons.ROCKET_LAUNCH_ROUNDED, size=16, color=ft.Colors.ON_PRIMARY),
                    ft.Text(save_button_label, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
                ], spacing=6, tight=True),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.Padding.symmetric(horizontal=18, vertical=12),
                ),
                on_click=_do_publish,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref[0] = dlg

    page.overlay.append(dlg)
    dlg.open = True
    page.update()
