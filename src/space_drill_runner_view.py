"""
Space CBT Drill Runner View for Nu-Age Course Spaces.

Provides a dedicated, distraction-free assessment environment:
- Full-screen view replacing small modal dialogs.
- Interactive question-by-question layout with quick palette jump strip.
- Selectable option cards with automatic multiline text wrapping (zero text bleeding).
- Built-in draggable In-Exam Calculator integration via src.components.exam_calculator.
- Self-paced or timed modes with automatic countdown and sticky header.
- Question flagging (review later), unanswered warnings, and instant step-by-step review with AI/tutor explanations.
"""

import asyncio
from datetime import datetime, timezone
import math
from typing import Optional, Dict, Any, List
import flet as ft

from src.utils.file_opener import show_page_snackbar
from src.components.exam_calculator import build_exam_calculator
from src.requests.course_spaces import get_quiz_for_taking, submit_quiz_attempt

_LETTERS = ["A", "B", "C", "D", "E", "F"]


async def space_drill_runner_view(
    page: ft.Page,
    space_id: str,
    quiz_id: str,
    target_back: Optional[str] = None,
) -> ft.View:
    clean_space_id = str(space_id).split("?")[0].replace("/manage", "").strip()
    clean_quiz_id = str(quiz_id).split("?")[0].strip()
    back_route = target_back or f"/spaces/{clean_space_id}?tab=drills"

    def _screen_w() -> int:
        return int(page.width or 1200)

    # 1. Resolve Auth Token
    token = None
    try:
        if hasattr(page, "shared_preferences"):
            token = await page.shared_preferences.get("auth_token")
    except Exception:
        pass
    if not token and hasattr(page, "session") and hasattr(page.session, "store"):
        token = page.session.store.get("session_auth_token")

    state: Dict[str, Any] = {
        "loading": True,
        "quiz": {},
        "questions": [],
        "current_idx": 0,
        "selected_answers": {},  # str(question_id) -> int(chosen_opt_index)
        "flags": set(),          # set of int question indices flagged
        "submitted": False,
        "results": None,
        "in_review": False,
        "show_calculator": False,
        "calc_type": "basic",
        "remaining_seconds": 0,
        "total_seconds": 0,
        "start_time": datetime.now(timezone.utc),
    }

    main_slot = ft.Container(expand=True)
    calc_container = ft.Container(visible=False)
    root_stack = ft.Stack([main_slot, calc_container], expand=True)

    # ── Timer & Clock Logic ──────────────────────────────────────────────────
    timer_txt = ft.Text("Self-Paced", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)

    def _update_timer_display():
        rem = state["remaining_seconds"]
        if state["total_seconds"] <= 0:
            timer_txt.value = "Self-Paced"
            timer_txt.color = ft.Colors.PRIMARY
            return
        mins = rem // 60
        secs = rem % 60
        timer_txt.value = f"⏱ {mins:02d}:{secs:02d}"
        if rem <= 60:
            timer_txt.color = ft.Colors.RED_400
        elif rem <= 300:
            timer_txt.color = ft.Colors.AMBER_400
        else:
            timer_txt.color = ft.Colors.PRIMARY

    # ── Calculator Mount/Toggle ──────────────────────────────────────────────
    def _close_calc(ev=None):
        state["show_calculator"] = False
        calc_container.visible = False
        page.update()

    def _toggle_calc_mode(ev=None):
        state["calc_type"] = "scientific" if state["calc_type"] == "basic" else "basic"
        _render_calculator()
        page.update()

    def _render_calculator():
        calc_widget = build_exam_calculator(
            page=page,
            calculator_type=state["calc_type"],
            on_close=_close_calc,
            on_toggle_mode=_toggle_calc_mode,
            target_container=calc_container,
        )
        calc_container.content = calc_widget

    def _toggle_calc(ev=None):
        state["show_calculator"] = not state["show_calculator"]
        calc_container.visible = state["show_calculator"]
        if state["show_calculator"]:
            if calc_container.top is None:
                calc_container.top = 60.0
            if calc_container.left is None:
                calc_container.left = max(16.0, _screen_w() - 320.0)
            _render_calculator()
        page.update()

    # ── Exit Dialog ──────────────────────────────────────────────────────────
    def _confirm_exit(ev=None):
        if state["submitted"]:
            page.navigate(back_route)
            return

        def _do_exit(e=None):
            dlg.open = False
            page.update()
            page.navigate(back_route)

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=14),
            title=ft.Row([
                ft.Icon(ft.Icons.WARNING_ROUNDED, color=ft.Colors.AMBER_400),
                ft.Text("Exit Practice Drill?", weight=ft.FontWeight.BOLD, size=16),
            ], spacing=8),
            content=ft.Text(
                "Your current progress will not be saved. Are you sure you want to exit back to the Course Space?",
                size=13,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            actions=[
                ft.TextButton("Stay in Drill", on_click=lambda _: (setattr(dlg, "open", False), page.update())),
                ft.Button("Exit Drill", style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE), on_click=_do_exit),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ── Submit Drill Logic ───────────────────────────────────────────────────
    async def _submit_drill(ev=None, force: bool = False):
        if state["submitted"]:
            return

        questions = state["questions"]
        answered_count = len(state["selected_answers"])
        unanswered_count = len(questions) - answered_count

        if not force and unanswered_count > 0:
            def _proceed_sub(e=None):
                conf_dlg.open = False
                page.update()
                page.run_task(_submit_drill, None, True)

            conf_dlg = ft.AlertDialog(
                shape=ft.RoundedRectangleBorder(radius=14),
                title=ft.Row([
                    ft.Icon(ft.Icons.HELP_OUTLINE_ROUNDED, color=ft.Colors.PRIMARY),
                    ft.Text("Unanswered Questions", weight=ft.FontWeight.BOLD, size=16),
                ], spacing=8),
                content=ft.Text(
                    f"You have answered {answered_count} of {len(questions)} questions.\n"
                    f"{unanswered_count} question{'s remain' if unanswered_count != 1 else ' remains'} unanswered.\n\n"
                    "Do you want to submit your attempt anyway?",
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                actions=[
                    ft.TextButton("Review Questions", on_click=lambda _: (setattr(conf_dlg, "open", False), page.update())),
                    ft.Button("Submit Now", style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY), on_click=_proceed_sub),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.overlay.append(conf_dlg)
            conf_dlg.open = True
            page.update()
            return

        state["submitted"] = True
        state["loading"] = True
        _render_main()
        page.update()

        elapsed = int((datetime.now(timezone.utc) - state["start_time"]).total_seconds())
        answers_payload = [
            {"question_id": str(qid), "chosen_index": int(c_idx)}
            for qid, c_idx in state["selected_answers"].items()
        ]

        res = await submit_quiz_attempt(
            token=token,
            space_id=clean_space_id,
            quiz_id=clean_quiz_id,
            answers=answers_payload,
            duration_seconds=max(1, elapsed),
        )

        state["loading"] = False
        if res.get("status") == "success":
            state["results"] = res
            _render_main()
            page.update()
        else:
            state["submitted"] = False
            show_page_snackbar(page, res.get("message", "Failed to submit drill attempt."))
            _render_main()
            page.update()

    # ── Answer Selection & Navigation ────────────────────────────────────────
    def _select_answer(q_id: str, opt_idx: int):
        if state["submitted"]:
            return
        state["selected_answers"][q_id] = opt_idx
        _render_main()
        page.update()

    def _toggle_flag(idx: int):
        if idx in state["flags"]:
            state["flags"].remove(idx)
        else:
            state["flags"].add(idx)
        _render_main()
        page.update()

    def _jump_to_question(idx: int):
        if 0 <= idx < len(state["questions"]):
            state["current_idx"] = idx
            _render_main()
            page.update()

    # ── Render View ──────────────────────────────────────────────────────────
    def _render_main():
        main_slot.content = None
        sw = _screen_w()
        is_mob = sw < 768

        # If loading skeleton
        if state["loading"]:
            from src.components.shimmer_skeletons import build_cohort_exam_skeleton
            main_slot.content = build_cohort_exam_skeleton(page)
            return

        # If drill submitted and results ready, show Results Screen
        if state["submitted"] and state["results"]:
            main_slot.content = _build_results_view(is_mob)
            return

        questions = state["questions"]
        if not questions:
            main_slot.content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=40,
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.QUIZ_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("No questions found in this practice drill.", size=16, weight=ft.FontWeight.BOLD),
                        ft.Button("Return to Space", on_click=lambda _: page.navigate(back_route)),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
            )
            return

        cur_idx = state["current_idx"]
        cur_q = questions[cur_idx]
        cur_qid = str(cur_q.get("id"))
        is_flagged = cur_idx in state["flags"]
        chosen_opt = state["selected_answers"].get(cur_qid)
        q_topic = cur_q.get("topic") or ""
        q_scenario = cur_q.get("scenario_text") or ""
        q_text = cur_q.get("question_text") or ""
        q_img = cur_q.get("image_url") or ""
        options = cur_q.get("options") or []

        # ── 1. Top Control Bar ───────────────────────────────────────────────
        left_header = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    tooltip="Exit Drill",
                    on_click=_confirm_exit,
                ),
                ft.Column(
                    [
                        ft.Text(
                            state["quiz"].get("title", "Topic CBT Drill"),
                            weight=ft.FontWeight.BOLD,
                            size=14 if is_mob else 16,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            f"Question {cur_idx + 1} of {len(questions)}",
                            size=11,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=1,
                    tight=True,
                    expand=True,
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

        right_header = ft.Row(
            [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                    content=timer_txt,
                ),
                ft.IconButton(
                    icon=ft.Icons.CALCULATE_ROUNDED,
                    tooltip="In-Exam Calculator",
                    icon_color=ft.Colors.PRIMARY if state["show_calculator"] else ft.Colors.ON_SURFACE_VARIANT,
                    on_click=_toggle_calc,
                ),
                ft.IconButton(
                    icon=ft.Icons.FLAG_ROUNDED if is_flagged else ft.Icons.FLAG_OUTLINED,
                    icon_color=ft.Colors.AMBER_400 if is_flagged else ft.Colors.ON_SURFACE_VARIANT,
                    tooltip="Flag for Review" if not is_flagged else "Remove Flag",
                    on_click=lambda _: _toggle_flag(cur_idx),
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

        top_bar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
            content=ft.Row(
                [left_header, right_header],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        # ── 2. Question Content Body ─────────────────────────────────────────
        q_elements = []

        # Topic & Points Pill
        topic_row_items = [
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=6,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                content=ft.Text(f"⚡ Question {cur_idx + 1}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
            ),
        ]
        if q_topic:
            topic_row_items.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    content=ft.Text(q_topic, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT),
                )
            )
        if is_flagged:
            topic_row_items.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER_500),
                    content=ft.Text("🚩 Flagged for Review", size=10.5, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_500),
                )
            )
        q_elements.append(ft.Row(topic_row_items, spacing=6, wrap=True))

        # Scenario text (if present)
        if q_scenario:
            q_elements.append(
                ft.Container(
                    padding=14,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Text(q_scenario, italic=True, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                )
            )

        # Question text
        q_elements.append(
            ft.Text(
                q_text,
                size=15 if is_mob else 16.5,
                weight=ft.FontWeight.W_600,
                color=ft.Colors.ON_SURFACE,
            )
        )

        # Attached image (if present)
        if q_img:
            q_elements.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=10,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    content=ft.Image(src=q_img, fit=ft.BoxFit.CONTAIN, height=220, border_radius=8),
                )
            )

        # ── 3. High-Quality Wrapping Option Cards (Zero Bleed!) ─────────────
        option_cards = []
        for opt_idx, opt_text in enumerate(options):
            is_sel = chosen_opt == opt_idx
            letter = _LETTERS[opt_idx] if opt_idx < len(_LETTERS) else str(opt_idx + 1)

            opt_card = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_sel else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                border=ft.Border.all(
                    1.6 if is_sel else 1,
                    ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                ),
                ink=True,
                on_click=lambda ev, o_idx=opt_idx: _select_answer(cur_qid, o_idx),
                content=ft.Row(
                    [
                        ft.Container(
                            width=32,
                            height=32,
                            border_radius=8,
                            bgcolor=ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text(
                                letter,
                                weight=ft.FontWeight.BOLD,
                                size=13,
                                color=ft.Colors.ON_PRIMARY if is_sel else ft.Colors.ON_SURFACE,
                            ),
                        ),
                        # Crucial: expand=True guarantees multiline text wrapping without horizontal overflow!
                        ft.Text(
                            opt_text,
                            size=13.5,
                            weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.NORMAL,
                            color=ft.Colors.ON_SURFACE,
                            expand=True,
                        ),
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if is_sel else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                            size=20,
                            color=ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.25, ft.Colors.ON_SURFACE),
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            option_cards.append(opt_card)

        q_elements.append(ft.Column(option_cards, spacing=10))

        question_card = ft.Container(
            padding=18 if is_mob else 24,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Column(q_elements, spacing=14),
        )

        # ── 4. Question Palette Jump Strip ──────────────────────────────────
        palette_chips = []
        for p_idx, q_item in enumerate(questions):
            p_qid = str(q_item.get("id"))
            p_ans = p_qid in state["selected_answers"]
            p_flag = p_idx in state["flags"]
            p_active = p_idx == cur_idx

            bg = ft.Colors.PRIMARY if p_active else (ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY) if p_ans else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))
            fg = ft.Colors.ON_PRIMARY if p_active else (ft.Colors.PRIMARY if p_ans else ft.Colors.ON_SURFACE_VARIANT)
            border_c = ft.Colors.AMBER_400 if p_flag else (ft.Colors.PRIMARY if p_active else ft.Colors.TRANSPARENT)

            palette_chips.append(
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=10,
                    bgcolor=bg,
                    border=ft.Border.all(1.8 if p_flag else (1 if p_active else 0), border_c),
                    alignment=ft.Alignment.CENTER,
                    ink=True,
                    tooltip=f"Question {p_idx + 1}" + (" (Flagged)" if p_flag else (" (Answered)" if p_ans else "")),
                    on_click=lambda ev, idx_val=p_idx: _jump_to_question(idx_val),
                    content=ft.Text(str(p_idx + 1), size=12, weight=ft.FontWeight.BOLD, color=fg),
                )
            )

        palette_row = ft.Container(
            padding=ft.Padding.symmetric(vertical=8),
            content=ft.Row(palette_chips, scroll=ft.ScrollMode.AUTO, spacing=8),
        )

        # ── 5. Bottom Navigation & Action Bar ────────────────────────────────
        is_last = cur_idx == len(questions) - 1

        if is_mob:
            btn_prev = ft.OutlinedButton(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=15),
                        ft.Text("Prev", size=12, weight=ft.FontWeight.BOLD),
                    ],
                    tight=True,
                    spacing=4,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                disabled=cur_idx == 0,
                on_click=lambda _: _jump_to_question(cur_idx - 1),
                height=40,
                style=ft.ButtonStyle(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=0),
                    shape=ft.RoundedRectangleBorder(radius=10),
                ),
            )
            btn_next = ft.Button(
                content=ft.Row(
                    [
                        ft.Text("Submit" if is_last else "Next", size=12, weight=ft.FontWeight.BOLD),
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED if is_last else ft.Icons.ARROW_FORWARD_ROUNDED, size=15),
                    ],
                    tight=True,
                    spacing=4,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.ON_PRIMARY,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=0),
                    shape=ft.RoundedRectangleBorder(radius=10),
                ),
                on_click=lambda _: page.run_task(_submit_drill) if is_last else _jump_to_question(cur_idx + 1),
                height=40,
            )
            answered_badge = ft.Container(
                content=ft.Text(
                    f"{len(state['selected_answers'])}/{len(questions)}",
                    size=11.5,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.PRIMARY,
                    text_align=ft.TextAlign.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
            )
            bottom_bar_content = ft.Row(
                [
                    ft.Container(content=btn_prev, expand=1),
                    answered_badge,
                    ft.Container(content=btn_next, expand=1),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        else:
            btn_prev = ft.OutlinedButton(
                "Previous",
                icon=ft.Icons.ARROW_BACK_ROUNDED,
                disabled=cur_idx == 0,
                on_click=lambda _: _jump_to_question(cur_idx - 1),
                height=42,
            )
            btn_next = ft.Button(
                "Review & Submit" if is_last else "Next Question",
                icon=ft.Icons.CHECK_CIRCLE_ROUNDED if is_last else ft.Icons.ARROW_FORWARD_ROUNDED,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.ON_PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=10),
                ),
                on_click=lambda _: page.run_task(_submit_drill) if is_last else _jump_to_question(cur_idx + 1),
                height=42,
            )
            answered_badge = ft.Text(
                f"{len(state['selected_answers'])} of {len(questions)} Answered",
                size=12,
                weight=ft.FontWeight.W_600,
                color=ft.Colors.PRIMARY,
            )
            bottom_bar_content = ft.Row(
                [
                    btn_prev,
                    answered_badge,
                    btn_next,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        bottom_bar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12 if is_mob else 16, vertical=10 if is_mob else 12),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
            content=bottom_bar_content,
        )

        # Assemble Main Layout with Floating Calculator Dock
        center_scroll_col = ft.Column(
            [
                palette_row,
                question_card,
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        main_layout = ft.Column(
            [
                top_bar,
                ft.Container(content=center_scroll_col, padding=ft.Padding.symmetric(horizontal=16, vertical=8), expand=True),
                bottom_bar,
            ],
            spacing=0,
            expand=True,
        )

        main_slot.content = main_layout

    # ── 6. Results & Review View ─────────────────────────────────────────────
    def _build_results_view(is_mob: bool) -> ft.Control:
        res = state["results"] or {}
        score = int(res.get("score") or 0)
        max_score = int(res.get("max_score") or len(state["questions"]))
        pct = int(res.get("percentage") or round((score / max(1, max_score)) * 100))
        passed = bool(res.get("passed", pct >= 70))
        breakdown = res.get("answers_breakdown") or []

        correct_count = sum(1 for b in breakdown if b.get("is_correct"))
        incorrect_count = len(breakdown) - correct_count

        active_filter = state.get("results_filter", "incorrect" if incorrect_count > 0 else "all")

        top_bar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
            content=ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        tooltip="Back to Space",
                        on_click=lambda _: page.navigate(back_route),
                    ),
                    ft.Text("Drill Performance", weight=ft.FontWeight.BOLD, size=16),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        hero_color = ft.Colors.PRIMARY if passed else ft.Colors.AMBER_700
        hero_card = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14 if is_mob else 18, vertical=14),
            border_radius=16,
            bgcolor=ft.Colors.with_opacity(0.08, hero_color),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.24, hero_color)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=46,
                                height=46,
                                border_radius=23,
                                bgcolor=hero_color,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(f"{pct}%", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        "Topic Mastered!" if passed else "Practice Complete!",
                                        size=15,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.Text(
                                        f"Score: {score} / {max_score} points"
                                        + (" · Pass mark: 70%" if not passed else " · Great work!"),
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                content=ft.Text(f"✓ {correct_count} Correct", size=11.5, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED_600),
                                content=ft.Text(f"✕ {incorrect_count} Mistakes", size=11.5, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_600),
                            ),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=10,
            ),
        )

        def _set_filter(f_val):
            state["results_filter"] = f_val
            _render_main()
            page.update()

        filter_row = ft.Row(
            [
                ft.Chip(
                    label=ft.Text(f"All ({len(breakdown)})", size=11.5),
                    selected=active_filter == "all",
                    on_select=lambda _: _set_filter("all"),
                ),
                ft.Chip(
                    label=ft.Text(f"Mistakes ({incorrect_count})", size=11.5),
                    selected=active_filter == "incorrect",
                    on_select=lambda _: _set_filter("incorrect"),
                ),
                ft.Chip(
                    label=ft.Text(f"Correct ({correct_count})", size=11.5),
                    selected=active_filter == "correct",
                    on_select=lambda _: _set_filter("correct"),
                ),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        )

        review_cards = []
        for idx, b in enumerate(breakdown):
            is_c = bool(b.get("is_correct"))
            if active_filter == "incorrect" and is_c:
                continue
            if active_filter == "correct" and not is_c:
                continue

            q_title = b.get("question_text", f"Question {idx + 1}")
            opts = b.get("options") or []
            chosen_i = b.get("chosen_index")
            corr_i = b.get("correct_index", 0)
            expl = b.get("explanation")

            chosen_str = (
                f"{_LETTERS[chosen_i]}. {opts[chosen_i]}"
                if (chosen_i is not None and 0 <= chosen_i < len(opts) and chosen_i < len(_LETTERS))
                else "No answer selected"
            )
            corr_str = (
                f"{_LETTERS[corr_i]}. {opts[corr_i]}"
                if (0 <= corr_i < len(opts) and corr_i < len(_LETTERS))
                else f"Option {corr_i + 1}"
            )

            card_lines = [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if is_c else ft.Icons.CANCEL_ROUNDED,
                            size=18,
                            color=ft.Colors.PRIMARY if is_c else ft.Colors.RED_400,
                        ),
                        ft.Text(f"Q{idx + 1}: {q_title}", weight=ft.FontWeight.BOLD, size=13, expand=True),
                    ],
                    spacing=8,
                ),
                ft.Container(
                    padding=ft.Padding.only(left=26),
                    content=ft.Column(
                        [
                            ft.Text(
                                f"Your Answer: {chosen_str}",
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.PRIMARY if is_c else ft.Colors.RED_400,
                            ),
                            *([ft.Text(f"Correct Answer: {corr_str}", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY)] if not is_c else []),
                            *(
                                [
                                    ft.Container(
                                        padding=10,
                                        border_radius=8,
                                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                                        content=ft.Text(f"💡 Explanation: {expl}", size=11.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                    )
                                ]
                                if expl
                                else []
                            ),
                        ],
                        spacing=4,
                    ),
                ),
            ]

            review_cards.append(
                ft.Container(
                    padding=12,
                    border_radius=12,
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.only(left=ft.BorderSide(3.5, ft.Colors.PRIMARY if is_c else ft.Colors.RED_400)),
                    content=ft.Column(card_lines, spacing=6),
                )
            )

        if not review_cards:
            review_cards.append(
                ft.Container(
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(
                        "No questions match this filter." if active_filter != "incorrect" else "🎉 Perfect score! Zero mistakes.",
                        size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                )
            )

        scroll_content = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14 if is_mob else 18, vertical=10),
            expand=True,
            content=ft.Column(
                [
                    hero_card,
                    filter_row,
                    ft.Text("Question Breakdown & Solutions", weight=ft.FontWeight.BOLD, size=14),
                    ft.Column(review_cards, spacing=8),
                ],
                scroll=ft.ScrollMode.AUTO,
                spacing=12,
                expand=True,
            ),
        )

        bottom_actions = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14 if is_mob else 18, vertical=10),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.OutlinedButton(
                            "Back to Space",
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            height=40,
                            on_click=lambda _: page.navigate(back_route),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=ft.Padding.symmetric(horizontal=8, vertical=0),
                            ),
                        ),
                        expand=1,
                    ),
                    ft.Container(
                        content=ft.Button(
                            "Retake Drill",
                            icon=ft.Icons.REPLAY_ROUNDED,
                            height=40,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.PRIMARY,
                                color=ft.Colors.ON_PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=ft.Padding.symmetric(horizontal=8, vertical=0),
                            ),
                            on_click=lambda _: page.run_task(_reload_and_restart),
                        ),
                        expand=1,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        return ft.Column(
            [
                top_bar,
                scroll_content,
                bottom_actions,
            ],
            spacing=0,
            expand=True,
        )

    async def _reload_and_restart(ev=None):
        state["submitted"] = False
        state["results"] = None
        state["selected_answers"].clear()
        state["flags"].clear()
        state["current_idx"] = 0
        state["start_time"] = datetime.now(timezone.utc)
        state["remaining_seconds"] = state["total_seconds"]
        _render_main()
        page.update()

    # ── Initial Fetch ────────────────────────────────────────────────────────
    async def _init_load():
        q_res = await get_quiz_for_taking(token=token, space_id=clean_space_id, quiz_id=clean_quiz_id)
        if q_res.get("status") == "success":
            state["quiz"] = q_res.get("quiz", {})
            state["questions"] = state["quiz"].get("questions", [])
            t_limit = int(state["quiz"].get("time_limit_minutes") or 0)
            state["total_seconds"] = t_limit * 60
            state["remaining_seconds"] = t_limit * 60
        else:
            show_page_snackbar(page, q_res.get("message", "Could not load quiz questions."))

        state["loading"] = False
        _render_main()
        page.update()

        # Start timer countdown loop if timed
        if state["total_seconds"] > 0:
            while not state["submitted"] and state["remaining_seconds"] > 0:
                await asyncio.sleep(1)
                if state["submitted"]:
                    break
                state["remaining_seconds"] -= 1
                _update_timer_display()
                page.update()
                if state["remaining_seconds"] <= 0 and not state["submitted"]:
                    await _submit_drill(None, force=True)

    page.run_task(_init_load)

    return ft.View(
        route=f"/spaces/{clean_space_id}/drills/{clean_quiz_id}",
        bgcolor=ft.Colors.SURFACE,
        padding=0,
        controls=[ft.SafeArea(content=root_stack, expand=True)],
    )

