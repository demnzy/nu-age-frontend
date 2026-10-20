import asyncio
import re
from typing import Any, Callable, Dict, List, Optional, Set
import flet as ft

from src.components import study_ui as ui
from src.local_db import get_offline_exam_categories
from src.requests.study import get_exam_categories


def _get_pacing_seconds(exam_type_str: str, title_str: str = "") -> tuple[int, str]:
    """Returns (seconds_per_question, board_name) based on official Nigerian/international testing boards."""
    combined = f"{exam_type_str or ''} {title_str or ''}".upper()
    if "POST-UTME" in combined or "PUTME" in combined:
        return 42, "Post-UTME (42s/q)"
    elif "JAMB" in combined or "UTME" in combined:
        return 48, "JAMB UTME (48s/q)"
    elif "WAEC" in combined or "WASSCE" in combined:
        return 72, "WAEC / WASSCE (72s/q)"
    elif "NECO" in combined:
        return 60, "NECO SSCE (60s/q)"
    elif "SAT" in combined:
        return 75, "SAT Digital (75s/q)"
    elif any(x in combined for x in ("NCLEX", "MCAT", "USMLE")):
        return 84, "Clinical Standard (84s/q)"
    return 60, "Standard CBT (60s/q)"


def _format_duration_display(mins: int) -> str:
    """Formats minutes into concise human-readable duration."""
    if mins < 60:
        return f"{mins} Mins"
    hours = mins // 60
    rem = mins % 60
    return f"{hours}h {rem}m" if rem else f"{hours} Hours"


def open_cbt_setup_modal(
    page: ft.Page,
    material_ids: Optional[List[str]] = None,
    exam_title: str = "CBT Examination",
    token: Optional[str] = None,
    is_offline: bool = False,
    on_start: Optional[Callable[[List[str], int, List[str], int], Any]] = None,
):
    """
    Renders an interactive CBT pre-flight customization dialog where the learner:
      1. Chooses the exact number of questions to attempt (presets + continuous slider).
      2. Multi-selects topics/categories to focus on: selecting/deselecting categories dynamically
         updates BOTH the active selected question count and the total pool.
      3. Sees official board-standard duration and pacing recalculate live in real-time.
      4. Operates in a compact, viewport-bounded modal with refined typography, sticky header/footer,
         and mobile-responsive layout.
    """
    clean_ids = [str(mid) for mid in (material_ids or []) if mid]

    screen_w = getattr(page, "width", None) or 420
    screen_h = getattr(page, "height", None) or 750
    is_mobile = screen_w < 768

    dlg_width = min(screen_w - 24, 480) if is_mobile else min(screen_w - 48, 520)
    dlg_height = min(screen_h - (24 if is_mobile else 60), 650)

    # Modal container elements
    loading_view = ft.Container(
        padding=ft.Padding.symmetric(vertical=48),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(width=26, height=26, stroke_width=2.4, color=ft.Colors.PRIMARY),
                ft.Text("Scanning exam categories & questions…", size=12, weight=ft.FontWeight.W_600, color=ui.muted(0.7)),
            ],
        ),
    )

    modal_root_container = ft.Container(
        width=dlg_width,
        height=dlg_height,
        padding=0,
        content=loading_view,
    )

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=18),
        bgcolor=ft.Colors.SURFACE,
        content_padding=ft.Padding.all(0),
        content=modal_root_container,
    )

    def _close_dlg(e=None):
        dlg.open = False
        try:
            page.update()
        except Exception:
            pass

    async def _fetch_and_build():
        cat_data = None
        if not is_offline and token:
            try:
                cat_data = await asyncio.wait_for(get_exam_categories(token, clean_ids), timeout=8)
            except Exception as ex:
                print(f"[CBT Setup Modal] Online fetch failed: {ex}")
                cat_data = None

        if not cat_data or not cat_data.get("categories"):
            cat_data = get_offline_exam_categories(clean_ids, page=page)

        categories: List[Dict[str, Any]] = cat_data.get("categories") or []
        detected_exam_type = cat_data.get("exam_type") or "General CBT"
        total_q_found = int(cat_data.get("total_questions") or sum(c.get("count", 0) for c in categories))

        if total_q_found == 0:
            modal_root_container.content = ft.Container(
                padding=ft.Padding.all(24),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.HELP_OUTLINE_ROUNDED, size=44, color=ft.Colors.AMBER_600),
                        ft.Text("No Exam Questions Found", size=15, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                        ft.Text(
                            "There are currently no practice questions in this study material to simulate an exam.",
                            size=12,
                            color=ui.muted(0.7),
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.ElevatedButton(
                            "Close",
                            on_click=_close_dlg,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.PRIMARY,
                                color=ft.Colors.ON_PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                            ),
                        ),
                    ],
                ),
            )
            page.update()
            return

        # State within the modal
        sec_per_q, board_name = _get_pacing_seconds(detected_exam_type, exam_title)
        all_topic_names = [c["name"] for c in categories]
        selected_topics: Set[str] = set(all_topic_names)
        topic_filter_text = [""]

        def _calc_max_for_selected() -> int:
            if not selected_topics:
                return 0
            return sum(c["count"] for c in categories if c["name"] in selected_topics)

        # Default questions count: min(50, total_q_found)
        current_question_count = [min(50, max(5, total_q_found))]
        if total_q_found < 5:
            current_question_count[0] = total_q_found

        was_on_all_available = [current_question_count[0] == total_q_found]

        # UI Control References
        duration_badge_text = ft.Text("", size=15, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY)
        pacing_detail_text = ft.Text("", size=10.5, weight=ft.FontWeight.W_500, color=ui.muted(0.75))
        slider_ref = ft.Slider(
            min=min(5, _calc_max_for_selected()),
            max=max(5, _calc_max_for_selected()),
            divisions=max(1, _calc_max_for_selected() - min(5, _calc_max_for_selected())),
            value=current_question_count[0],
            active_color=ft.Colors.PRIMARY,
            inactive_color=ui.tint(ft.Colors.PRIMARY, 0.18),
        )
        count_display_text = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ui.tint(ft.Colors.PRIMARY, 0.12),
            content=ft.Text(f"{current_question_count[0]} Questions", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
        )
        preset_chips_row = ft.Row(spacing=6, wrap=True)
        topic_chips_wrap = ft.Row(spacing=6, wrap=True)

        start_btn = ft.FilledButton(
            content=ft.Row(
                spacing=6,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=18, color=ft.Colors.ON_PRIMARY),
                    ft.Text("Start Examination", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_PRIMARY),
                ],
            ),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding.symmetric(horizontal=20, vertical=12),
            ),
        )

        active_topics_badge = ft.Text(
            f"{len(selected_topics)}/{len(all_topic_names)} active",
            size=10.5,
            color=ui.muted(0.7),
            text_align=ft.TextAlign.RIGHT,
            no_wrap=False,
        )

        def _update_telemetry():
            max_avail = _calc_max_for_selected()
            if max_avail <= 0:
                current_question_count[0] = 0
                duration_badge_text.value = "0 Mins"
                pacing_detail_text.value = "Please select at least one topic to take the exam."
                count_display_text.content.value = "0 Selected"
                count_display_text.content.color = ft.Colors.RED_400
                start_btn.disabled = True
                slider_ref.disabled = True
                active_topics_badge.value = "0 active (0 pool)"
            else:
                slider_ref.disabled = False
                start_btn.disabled = False
                min_val = min(5, max_avail)

                # Clamp current_question_count
                current_question_count[0] = max(min_val, min(current_question_count[0], max_avail))

                slider_ref.min = min_val
                slider_ref.max = max_avail
                slider_ref.divisions = max(1, max_avail - min_val)
                slider_ref.value = current_question_count[0]

                total_secs = current_question_count[0] * sec_per_q
                mins = max(5, round(total_secs / 60))
                duration_badge_text.value = _format_duration_display(mins)
                pacing_detail_text.value = f"⏱ ~{round(mins*60/max(1, current_question_count[0]))}s/q • {board_name}"
                count_display_text.content.value = f"{current_question_count[0]} of {max_avail} questions"
                count_display_text.content.color = ft.Colors.PRIMARY
                active_topics_badge.value = f"{len(selected_topics)}/{len(all_topic_names)} active ({max_avail} Qs)"

            # Re-highlight preset chips
            _build_preset_chips()
            try:
                page.update()
            except Exception:
                pass

        def _on_slider_change(e):
            current_question_count[0] = int(round(e.control.value))
            max_avail = _calc_max_for_selected()
            was_on_all_available[0] = (current_question_count[0] == max_avail)
            _update_telemetry()

        slider_ref.on_change = _on_slider_change

        def _set_question_count(count: int):
            max_avail = _calc_max_for_selected()
            current_question_count[0] = max(1, min(count, max_avail))
            was_on_all_available[0] = (current_question_count[0] == max_avail)
            _update_telemetry()

        def _build_preset_chips():
            max_avail = _calc_max_for_selected()
            if max_avail >= 100:
                presets = [10, 20, 40, 60, 100]
            else:
                presets = [10, 20, 30, 50]

            chips = []
            for p in presets:
                if p <= max_avail:
                    is_active = (current_question_count[0] == p and not was_on_all_available[0])
                    chips.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                            border_radius=ft.BorderRadius.all(8),
                            bgcolor=ft.Colors.PRIMARY if is_active else ui.tint(ft.Colors.ON_SURFACE, 0.05),
                            border=ft.Border.all(1, ft.Colors.PRIMARY if is_active else ui.hairline(0.12)),
                            ink=True,
                            on_click=lambda _, val=p: _set_question_count(val),
                            content=ft.Text(
                                str(p),
                                size=11.5,
                                weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500,
                                color=ft.Colors.ON_PRIMARY if is_active else ft.Colors.ON_SURFACE,
                            ),
                        )
                    )

            # "All Available" chip
            if max_avail > 0:
                is_all_active = (current_question_count[0] == max_avail or was_on_all_available[0])
                chips.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        border_radius=ft.BorderRadius.all(8),
                        bgcolor=ft.Colors.PRIMARY if is_all_active else ui.tint(ft.Colors.ON_SURFACE, 0.05),
                        border=ft.Border.all(1, ft.Colors.PRIMARY if is_all_active else ui.hairline(0.12)),
                        ink=True,
                        on_click=lambda _: _set_question_count(max_avail),
                        content=ft.Text(
                            f"All ({max_avail})",
                            size=11.5,
                            weight=ft.FontWeight.W_700 if is_all_active else ft.FontWeight.W_500,
                            color=ft.Colors.ON_PRIMARY if is_all_active else ft.Colors.ON_SURFACE,
                        ),
                    )
                )

            preset_chips_row.controls = chips

        def _toggle_topic(name: str):
            cat_count = next((c["count"] for c in categories if c["name"] == name), 0)
            if name in selected_topics:
                # Do not allow deselecting last remaining topic
                if len(selected_topics) > 1:
                    selected_topics.remove(name)
                    new_max = _calc_max_for_selected()
                    if was_on_all_available[0]:
                        current_question_count[0] = new_max
                    else:
                        # Subtract category question count from selected count down to new max
                        current_question_count[0] = max(min(5, new_max), min(new_max, current_question_count[0] - cat_count))
            else:
                selected_topics.add(name)
                new_max = _calc_max_for_selected()
                if was_on_all_available[0]:
                    current_question_count[0] = new_max
                else:
                    # Add category question count to selected count
                    current_question_count[0] = min(new_max, current_question_count[0] + cat_count)

            _render_topic_chips()
            _update_telemetry()

        def _toggle_all_topics():
            if len(selected_topics) == len(all_topic_names):
                # Deselect all except first
                selected_topics.clear()
                if all_topic_names:
                    selected_topics.add(all_topic_names[0])
                    new_max = _calc_max_for_selected()
                    was_on_all_available[0] = False
                    current_question_count[0] = min(50, new_max)
            else:
                selected_topics.clear()
                selected_topics.update(all_topic_names)
                was_on_all_available[0] = True
                current_question_count[0] = total_q_found

            _render_topic_chips()
            _update_telemetry()

        def _render_topic_chips():
            is_all_selected = (len(selected_topics) == len(all_topic_names))
            max_avail = _calc_max_for_selected()

            controls = [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ui.tint(ft.Colors.PRIMARY, 0.16) if is_all_selected else ui.tint(ft.Colors.ON_SURFACE, 0.05),
                    border=ft.Border.all(1.2 if is_all_selected else 1, ft.Colors.PRIMARY if is_all_selected else ui.hairline(0.12)),
                    ink=True,
                    animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                    on_click=lambda _: _toggle_all_topics(),
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        controls=[
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_ROUNDED if is_all_selected else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                                size=13,
                                color=ft.Colors.PRIMARY if is_all_selected else ui.muted(0.5),
                            ),
                            ft.Text(
                                "All Topics",
                                size=11,
                                weight=ft.FontWeight.W_700 if is_all_selected else ft.FontWeight.W_500,
                                color=ft.Colors.PRIMARY if is_all_selected else ft.Colors.ON_SURFACE,
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                                border_radius=ft.BorderRadius.all(5),
                                bgcolor=ui.tint(ft.Colors.PRIMARY, 0.25) if is_all_selected else ui.tint(ft.Colors.ON_SURFACE, 0.08),
                                content=ft.Text(
                                    f"{max_avail}/{total_q_found}" if not is_all_selected else str(total_q_found),
                                    size=9,
                                    weight=ft.FontWeight.W_800,
                                    color=ft.Colors.PRIMARY if is_all_selected else ui.muted(0.8),
                                ),
                            ),
                        ],
                    ),
                )
            ]

            filter_kw = topic_filter_text[0].strip().lower()

            for cat in categories:
                cname = cat["name"]
                ccount = cat["count"]
                if filter_kw and filter_kw not in cname.lower():
                    continue

                is_sel = cname in selected_topics
                controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=9, vertical=5),
                        border_radius=ft.BorderRadius.all(8),
                        bgcolor=ui.tint(ft.Colors.PRIMARY, 0.14) if is_sel else ui.tint(ft.Colors.ON_SURFACE, 0.03),
                        border=ft.Border.all(1.2 if is_sel else 1, ft.Colors.PRIMARY if is_sel else ui.hairline(0.10)),
                        ink=True,
                        animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                        on_click=lambda _, name=cname: _toggle_topic(name),
                        content=ft.Row(
                            spacing=5,
                            tight=True,
                            controls=[
                                ft.Icon(
                                    ft.Icons.CHECK_ROUNDED if is_sel else ft.Icons.ADD_ROUNDED,
                                    size=12,
                                    color=ft.Colors.PRIMARY if is_sel else ui.muted(0.4),
                                ),
                                ft.Text(
                                    cname,
                                    size=11,
                                    weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.W_400,
                                    color=ft.Colors.PRIMARY if is_sel else ft.Colors.ON_SURFACE,
                                ),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=4.5, vertical=1),
                                    border_radius=ft.BorderRadius.all(4),
                                    bgcolor=ui.tint(ft.Colors.PRIMARY, 0.20) if is_sel else ui.tint(ft.Colors.ON_SURFACE, 0.06),
                                    content=ft.Text(
                                        str(ccount),
                                        size=9,
                                        weight=ft.FontWeight.W_800,
                                        color=ft.Colors.PRIMARY if is_sel else ui.muted(0.7),
                                    ),
                                ),
                            ],
                        ),
                    )
                )

            topic_chips_wrap.controls = controls
            try:
                page.update()
            except Exception:
                pass

        def _on_filter_changed(e):
            topic_filter_text[0] = str(e.control.value or "")
            _render_topic_chips()

        topic_search_field = ft.TextField(
            hint_text="Search syllabus topics…",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            dense=True,
            text_size=11.5,
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=ft.BorderRadius.all(8),
            bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.03),
            border_color=ui.hairline(0.12),
            on_change=_on_filter_changed,
        )

        _render_topic_chips()
        _update_telemetry()

        def _on_start_clicked(e):
            chosen_limit = current_question_count[0]
            chosen_topics = list(selected_topics) if len(selected_topics) < len(all_topic_names) else ["all"]
            total_secs = chosen_limit * sec_per_q
            calculated_duration = max(300, round(total_secs / 60) * 60)

            # Button async loading feedback
            start_btn.disabled = True
            start_btn.content = ft.Row(
                spacing=6,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.ON_PRIMARY),
                    ft.Text("Preparing Exam…", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_PRIMARY),
                ],
            )
            page.update()

            _close_dlg()

            if on_start:
                on_start(clean_ids, chosen_limit, chosen_topics, calculated_duration)

        start_btn.on_click = _on_start_clicked

        # ── FIXED HEADER ───────────────────────────────────────────────────
        header_widget = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=ft.BorderRadius.all(10),
                                bgcolor=ui.tint(ft.Colors.PRIMARY, 0.15),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.TUNE_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                controls=[
                                    ft.Text("Exam Customization", size=15, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                    ft.Text(f"{board_name} standard", size=10.5, color=ui.muted(0.65)),
                                ],
                            ),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        tooltip="Close",
                        on_click=_close_dlg,
                    ),
                ],
            ),
        )

        # ── SCROLLABLE BODY ────────────────────────────────────────────────
        body_scroll_content = ft.Column(
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                # 1. Topic Multi-Select Section
                ft.Column(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=5,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.CATEGORY_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                                        ft.Text("Topics & Syllabus", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                    ],
                                ),
                                ft.Container(
                                    content=active_topics_badge,
                                    expand=True,
                                    alignment=ft.Alignment.CENTER_RIGHT,
                                ),
                            ],
                        ),
                        *( [topic_search_field] if len(categories) > 6 else [] ),
                        topic_chips_wrap,
                    ],
                ),
                ft.Divider(height=1, color=ui.hairline(0.08)),

                # 2. Question Count Selector
                ft.Column(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=5,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.FORMAT_LIST_NUMBERED_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                                        ft.Text("Number of Questions", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                    ],
                                ),
                                count_display_text,
                            ],
                        ),
                        preset_chips_row,
                        slider_ref,
                    ],
                ),

                # 3. Dynamic Auto-Pacing Telemetry Card
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=ft.BorderRadius.all(12),
                    bgcolor=ui.tint(ft.Colors.PRIMARY, 0.08),
                    border=ft.Border.all(1, ui.tint(ft.Colors.PRIMARY, 0.22)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                spacing=2,
                                tight=True,
                                controls=[
                                    ft.Row(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.TIMER_OUTLINED, size=11, color=ft.Colors.PRIMARY),
                                            ft.Text("ALLOCATED TIME", size=9, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                                        ],
                                    ),
                                    pacing_detail_text,
                                ],
                            ),
                            duration_badge_text,
                        ],
                    ),
                ),
            ],
        )

        body_widget = ft.Container(
            expand=True,
            padding=ft.Padding.only(left=16, right=16, top=4, bottom=10),
            content=body_scroll_content,
        )

        # ── FIXED FOOTER ───────────────────────────────────────────────────
        cancel_btn = ft.TextButton(
            "Cancel",
            on_click=_close_dlg,
            style=ft.ButtonStyle(
                color=ui.muted(0.8),
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            ),
        )

        if is_mobile:
            footer_content = ft.Row(
                spacing=8,
                controls=[
                    cancel_btn,
                    ft.Container(expand=True, content=start_btn),
                ],
            )
        else:
            footer_content = ft.Row(
                alignment=ft.MainAxisAlignment.END,
                spacing=10,
                controls=[
                    cancel_btn,
                    start_btn,
                ],
            )

        footer_widget = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            border=ft.Border(top=ft.BorderSide(1, ui.hairline(0.10))),
            content=footer_content,
        )

        modal_root_container.content = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                header_widget,
                ft.Divider(height=1, color=ui.hairline(0.10)),
                body_widget,
                footer_widget,
            ],
        )
        page.update()

    page.overlay.append(dlg)
    dlg.open = True
    page.update()
    page.run_task(_fetch_and_build)
