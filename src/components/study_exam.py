"""
Redesigned Exam Simulator — summative assessment.

Follows the Prometric / Pearson VUE conventions real candidates expect:
  * Sticky countdown timer that changes colour at the 25% and 10% marks,
    with a visible time-elapsed bar.
  * Free navigation (Previous / Next) plus a question palette showing
    answered / unanswered / flagged state, with a legend.
  * "Flag for review" per question — the single most-requested exam feature
    and completely absent before.
  * A review-before-submit screen listing unanswered and flagged items, so
    nobody submits by accident.
  * NO per-question feedback during the exam. Feedback is deferred to the
    results report — this is what makes it summative rather than practice.
"""

import asyncio
import time

import flet as ft

from src.components import study_ui as ui

_LETTERS = ["A", "B", "C", "D", "E", "F"]


def build_exam(
    page: ft.Page,
    questions: list,
    duration_seconds: int | None = None,
    *,
    on_exit,
    on_restart,
    on_lock=None,
    haptics: "ui.Haptics | None" = None,
    on_register_submit=None,
):
    """
    Returns a Control for the exam.

    `on_lock(bool)` lets the host view disable navigation while the exam is
    in progress (already implemented in self_study.py as _lock_exam_ui).
    """
    total = len(questions)
    if total == 0:
        return ui.empty_state(
            ft.Icons.ASSIGNMENT_OUTLINED,
            "No exam questions yet",
            "Generate questions from your study material first,\nthen sit a full exam.",
            "Back to Hub",
            on_exit,
        )

    # Server-provided duration wins; fall back to 60s/question (min 5 min).
    limit = int(duration_seconds) if duration_seconds else max(total * 60, 300)

    state = {
        "index": 0,
        "answers": {},          # index -> chosen option index
        "flags": set(),
        "remaining": limit,
        "running": True,
        "submitted": False,
        "started": time.time(),
        "reviewing": False,
    }

    root = ft.Container(expand=True)
    if on_lock:
        on_lock(True)

    # ── timer ────────────────────────────────────────────────────────────
    timer_text = ft.Text(
        ui.fmt_duration(limit), size=15, weight=ft.FontWeight.W_800, color=ui.C_INFO
    )
    timer_icon = ft.Icon(ft.Icons.TIMER_ROUNDED, size=16, color=ui.C_INFO)
    timer_chip = ft.Container(
        padding=ft.Padding.symmetric(horizontal=11, vertical=6),
        border_radius=999,
        bgcolor=ui.tint(ui.C_INFO, 0.10),
        border=ft.Border.all(1, ui.tint(ui.C_INFO, 0.28)),
        animate=ft.Animation(ui.DUR_BASE, ui.CURVE_OUT),
        content=ft.Row(tight=True, spacing=6, controls=[timer_icon, timer_text]),
    )
    time_bar = ft.ProgressBar(
        value=0.0, bar_height=4, border_radius=999,
        color=ui.C_INFO, bgcolor=ui.hairline(0.10), expand=True,
    )

    answered_pill = ui.pill(f"0/{total} answered", ft.Colors.PRIMARY,
                            icon=ft.Icons.EDIT_NOTE_ROUNDED)

    async def _tick():
        while state["running"] and not state["submitted"]:
            await asyncio.sleep(1)
            if not state["running"] or state["submitted"]:
                return
            state["remaining"] -= 1
            frac_left = state["remaining"] / max(limit, 1)

            if frac_left <= 0.10:
                col = ui.C_WRONG
            elif frac_left <= 0.25:
                col = ui.C_WARN
            else:
                col = ui.C_INFO

            timer_text.value = ui.fmt_duration(max(state["remaining"], 0))
            timer_text.color = col
            timer_icon.color = col
            timer_chip.bgcolor = ui.tint(col, 0.10)
            timer_chip.border = ft.Border.all(1, ui.tint(col, 0.28))
            time_bar.color = col
            time_bar.value = 1 - frac_left

            if state["remaining"] <= 0:
                _submit(auto=True)
                return
            try:
                page.update()
            except Exception:
                return

    # ── question rendering ───────────────────────────────────────────────
    counter = ft.Text("", size=12, weight=ft.FontWeight.W_700, color=ui.muted(0.70))
    question_text = ft.Text(
        "", size=17, weight=ft.FontWeight.W_700,
        color=ft.Colors.ON_SURFACE, selectable=True,
    )
    options_col = ft.Column(spacing=9)

    flag_btn = ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border_radius=999,
        ink=True,
        animate=ft.Animation(ui.DUR_FAST, ui.CURVE_OUT),
        content=ft.Row(
            tight=True,
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.FLAG_OUTLINED, size=15, color=ui.muted(0.55)),
                ft.Text("Flag", size=11, weight=ft.FontWeight.W_700, color=ui.muted(0.55)),
            ],
        ),
    )

    palette_wrap = ft.Row(spacing=6, wrap=True, run_spacing=6)

    def _sync_flag_btn():
        on = state["index"] in state["flags"]
        flag_btn.bgcolor = ui.tint(ui.C_FLAG, 0.14) if on else ui.tint(ft.Colors.ON_SURFACE, 0.05)
        flag_btn.border = ft.Border.all(1, ui.tint(ui.C_FLAG, 0.40) if on else ui.hairline(0.12))
        flag_btn.content.controls[0].name = (
            ft.Icons.FLAG_ROUNDED if on else ft.Icons.FLAG_OUTLINED
        )
        flag_btn.content.controls[0].color = ui.C_FLAG if on else ui.muted(0.55)
        flag_btn.content.controls[1].value = "Flagged" if on else "Flag"
        flag_btn.content.controls[1].color = ui.C_FLAG if on else ui.muted(0.55)

    def _toggle_flag(_=None):
        if state["index"] in state["flags"]:
            state["flags"].discard(state["index"])
        else:
            state["flags"].add(state["index"])
            if haptics:
                haptics.select()
        _sync_flag_btn()
        _build_palette()
        page.update()

    flag_btn.on_click = _toggle_flag

    def _build_palette():
        """Grid of question numbers with answered / flagged / current state."""
        palette_wrap.controls.clear()
        for i in range(total):
            answered = i in state["answers"]
            flagged = i in state["flags"]
            current = i == state["index"]

            if current:
                bg, fg, bd = ft.Colors.PRIMARY, ft.Colors.ON_PRIMARY, ft.Colors.PRIMARY
            elif flagged:
                bg, fg, bd = ui.tint(ui.C_FLAG, 0.18), ui.C_FLAG, ui.tint(ui.C_FLAG, 0.45)
            elif answered:
                bg, fg, bd = ui.tint(ui.C_CORRECT, 0.14), ui.C_CORRECT, ui.tint(ui.C_CORRECT, 0.35)
            else:
                bg, fg, bd = ft.Colors.TRANSPARENT, ui.muted(0.50), ui.hairline(0.15)

            palette_wrap.controls.append(
                ft.Container(
                    width=31,
                    height=31,
                    border_radius=8,
                    bgcolor=bg,
                    border=ft.Border.all(1.2, bd),
                    alignment=ft.Alignment.CENTER,
                    ink=True,
                    animate=ft.Animation(ui.DUR_FAST, ui.CURVE_OUT),
                    on_click=lambda _, n=i: _goto(n),
                    content=ft.Text(
                        str(i + 1), size=11, weight=ft.FontWeight.W_800, color=fg
                    ),
                )
            )

    def _option_tile(idx: int, label: str, selected: bool):
        letter_box = ft.Container(
            width=27, height=27, border_radius=8,
            bgcolor=ft.Colors.PRIMARY if selected else ui.tint(ft.Colors.ON_SURFACE, 0.06),
            alignment=ft.Alignment.CENTER,
            animate=ft.Animation(ui.DUR_FAST, ui.CURVE_OUT),
            content=ft.Text(
                _LETTERS[idx] if idx < len(_LETTERS) else str(idx + 1),
                size=11, weight=ft.FontWeight.W_800,
                color=ft.Colors.ON_PRIMARY if selected else ui.muted(0.60),
            ),
        )
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=13, vertical=13),
            border_radius=ui.RADIUS_MD,
            bgcolor=ui.tint(ft.Colors.PRIMARY, 0.07) if selected else ft.Colors.SURFACE,
            border=ft.Border.all(
                1.5,
                ui.tint(ft.Colors.PRIMARY, 0.50) if selected else ui.hairline(0.12),
            ),
            ink=True,
            animate=ft.Animation(ui.DUR_BASE, ui.CURVE_OUT),
            on_click=lambda _, i=idx: _choose(i),
            content=ft.Row(
                spacing=11,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    letter_box,
                    ft.Text(label, size=13, color=ft.Colors.ON_SURFACE, expand=True),
                    ft.Icon(
                        ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED if selected
                        else ft.Icons.CIRCLE_OUTLINED,
                        size=17,
                        color=ft.Colors.PRIMARY if selected else ui.hairline(0.18),
                    ),
                ],
            ),
        )

    def _render_question():
        q = questions[state["index"]] or {}
        counter.value = f"Question {state['index'] + 1} of {total}"
        question_text.value = str(q.get("question") or "—")

        chosen = state["answers"].get(state["index"])
        options_col.controls.clear()
        for i, opt in enumerate(q.get("options") or []):
            options_col.controls.append(_option_tile(i, str(opt), chosen == i))

        answered_pill.content.controls[-1].value = f"{len(state['answers'])}/{total} answered"
        prev_btn.disabled = state["index"] == 0
        prev_btn.opacity = 0.4 if state["index"] == 0 else 1.0
        next_label.value = "Review" if state["index"] == total - 1 else "Next"
        _sync_flag_btn()
        _build_palette()

    def _choose(idx: int):
        state["answers"][state["index"]] = idx
        if haptics:
            haptics.select()
        _render_question()
        page.update()

    def _goto(n: int):
        state["index"] = max(0, min(n, total - 1))
        state["reviewing"] = False
        root.content = exam_layout
        _render_question()
        page.update()

    def _next(_=None):
        if state["index"] >= total - 1:
            _show_review()
            return
        _goto(state["index"] + 1)

    def _prev(_=None):
        _goto(state["index"] - 1)

    # ── navigation controls ──────────────────────────────────────────────
    prev_btn = ft.Container(
        height=46,
        expand=True,
        border_radius=ui.RADIUS_SM,
        border=ft.Border.all(1.5, ui.hairline(0.18)),
        ink=True,
        on_click=_prev,
        alignment=ft.Alignment.CENTER,
        animate_opacity=ft.Animation(ui.DUR_FAST, ui.CURVE_OUT),
        content=ft.Row(
            tight=True, spacing=7, alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=16, color=ui.muted(0.65)),
                ft.Text("Previous", size=13, weight=ft.FontWeight.W_700, color=ui.muted(0.65)),
            ],
        ),
    )
    next_label = ft.Text("Next", size=13, weight=ft.FontWeight.W_700,
                         color=ft.Colors.ON_PRIMARY)
    next_btn = ft.Container(
        height=46,
        expand=True,
        border_radius=ui.RADIUS_SM,
        bgcolor=ft.Colors.PRIMARY,
        ink=True,
        on_click=_next,
        alignment=ft.Alignment.CENTER,
        content=ft.Row(
            tight=True, spacing=7, alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                next_label,
                ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16, color=ft.Colors.ON_PRIMARY),
            ],
        ),
    )

    legend = ft.Row(
        spacing=12,
        wrap=True,
        run_spacing=6,
        controls=[
            ft.Row(spacing=5, tight=True, controls=[
                ft.Container(width=10, height=10, border_radius=3, bgcolor=ft.Colors.PRIMARY),
                ft.Text("Current", size=9, color=ui.muted(0.55)),
            ]),
            ft.Row(spacing=5, tight=True, controls=[
                ft.Container(width=10, height=10, border_radius=3,
                             bgcolor=ui.tint(ui.C_CORRECT, 0.35)),
                ft.Text("Answered", size=9, color=ui.muted(0.55)),
            ]),
            ft.Row(spacing=5, tight=True, controls=[
                ft.Container(width=10, height=10, border_radius=3,
                             bgcolor=ui.tint(ui.C_FLAG, 0.40)),
                ft.Text("Flagged", size=9, color=ui.muted(0.55)),
            ]),
            ft.Row(spacing=5, tight=True, controls=[
                ft.Container(width=10, height=10, border_radius=3,
                             bgcolor=ft.Colors.TRANSPARENT,
                             border=ft.Border.all(1, ui.hairline(0.25))),
                ft.Text("Unanswered", size=9, color=ui.muted(0.55)),
            ]),
        ],
    )

    # ── review-before-submit ─────────────────────────────────────────────
    def _show_review():
        state["reviewing"] = True
        unanswered = [i for i in range(total) if i not in state["answers"]]
        flagged = sorted(state["flags"])

        def _jump_chips(indices, color):
            return ft.Row(
                spacing=6, wrap=True, run_spacing=6,
                controls=[
                    ft.Container(
                        width=33, height=33, border_radius=8,
                        bgcolor=ui.tint(color, 0.12),
                        border=ft.Border.all(1.2, ui.tint(color, 0.38)),
                        alignment=ft.Alignment.CENTER, ink=True,
                        on_click=lambda _, n=i: _goto(n),
                        content=ft.Text(str(i + 1), size=11,
                                        weight=ft.FontWeight.W_800, color=color),
                    )
                    for i in indices
                ],
            )

        blocks = [
            ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(horizontal=18, vertical=22),
                border_radius=ui.RADIUS_LG,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment.TOP_LEFT,
                    end=ft.Alignment.BOTTOM_RIGHT,
                    colors=[ui.tint(ft.Colors.PRIMARY, 0.12), ui.tint(ui.C_INFO, 0.05)],
                ),
                border=ft.Border.all(1, ui.tint(ft.Colors.PRIMARY, 0.22)),
                content=ft.Column(
                    spacing=10,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.FACT_CHECK_ROUNDED, size=34,
                                color=ft.Colors.PRIMARY),
                        ft.Text(
                            "Before you submit",
                            size=19,
                            weight=ft.FontWeight.W_800,
                            color=ft.Colors.ON_SURFACE,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "Check anything you left blank or flagged.\n"
                            "You can't change answers after submitting.",
                            size=12,
                            color=ui.muted(0.65),
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Row(
                            spacing=8,
                            wrap=True,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ui.pill(f"{len(state['answers'])} answered", ui.C_CORRECT,
                                        icon=ft.Icons.CHECK_ROUNDED),
                                ui.pill(f"{len(unanswered)} blank",
                                        ui.C_WRONG if unanswered else ui.C_SKIP,
                                        icon=ft.Icons.REMOVE_ROUNDED),
                                ui.pill(f"{len(flagged)} flagged", ui.C_FLAG,
                                        icon=ft.Icons.FLAG_ROUNDED),
                            ],
                        ),
                        ui.pill(f"Time left {ui.fmt_duration(max(state['remaining'], 0))}",
                                ui.C_INFO, icon=ft.Icons.TIMER_ROUNDED),
                    ],
                ),
            )
        ]

        if unanswered:
            blocks.append(
                ui.surface_card(
                    ft.Column(
                        spacing=10,
                        controls=[
                            ui.section_label(f"Unanswered · {len(unanswered)}"),
                            ft.Text("Tap a number to jump straight to it.",
                                    size=11, color=ui.muted(0.55)),
                            _jump_chips(unanswered, ui.C_WRONG),
                        ],
                    )
                )
            )
        if flagged:
            blocks.append(
                ui.surface_card(
                    ft.Column(
                        spacing=10,
                        controls=[
                            ui.section_label(f"Flagged for review · {len(flagged)}"),
                            _jump_chips(flagged, ui.C_FLAG),
                        ],
                    )
                )
            )

        blocks.append(
            ft.Column(
                spacing=10,
                controls=[
                    ui.ghost_button("Keep working", lambda _: _goto(state["index"]),
                                    icon=ft.Icons.EDIT_ROUNDED, expand=True),
                    ui.primary_button("Submit exam", lambda _: _submit(),
                                      icon=ft.Icons.SEND_ROUNDED,
                                      color=ft.Colors.PRIMARY, expand=True, height=50),
                ],
            )
        )
        blocks.append(ft.Container(height=24))

        compact = ui.is_compact(page)
        root.content = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                sticky_bar,
                ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        ft.Container(
                            alignment=ft.Alignment.TOP_CENTER,
                            padding=ft.Padding.symmetric(
                                horizontal=14 if compact else 28, vertical=18
                            ),
                            content=ft.Container(
                                width=None if compact else 640,
                                content=ft.Column(
                                    spacing=16,
                                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                    controls=blocks,
                                ),
                            ),
                        )
                    ],
                ),
            ],
        )
        page.update()

    # ── submit ───────────────────────────────────────────────────────────
    def _submit(auto: bool = False):
        if state["submitted"]:
            return
        state["submitted"] = True
        state["running"] = False
        if on_lock:
            on_lock(False)
        if haptics:
            haptics.medium()

        records = []
        for i, q in enumerate(questions):
            q = q or {}
            try:
                correct_i = int(q.get("answer"))
            except (TypeError, ValueError):
                correct_i = -1
            records.append(
                {
                    "question": q.get("question") or "",
                    "options": list(q.get("options") or []),
                    "correct_index": correct_i,
                    "chosen_index": state["answers"].get(i),
                    "explanation": q.get("explanation"),
                    "flagged": i in state["flags"],
                    "seconds": 0,
                }
            )

        elapsed = int(time.time() - state["started"])
        results = ui.build_results_view(
            page,
            title="Exam Simulator",
            accent=ui.C_INFO,
            records=records,
            elapsed_seconds=elapsed,
            on_retry=on_restart,
            on_exit=on_exit,
            show_pass_band=True,
        )

        if auto:
            banner = ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=11),
                bgcolor=ui.tint(ui.C_WARN, 0.12),
                border=ft.Border.only(bottom=ft.BorderSide(1, ui.tint(ui.C_WARN, 0.30))),
                content=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.ALARM_ROUNDED, size=17, color=ui.C_WARN),
                        ft.Text("Time's up — your exam was submitted automatically.",
                                size=12, weight=ft.FontWeight.W_700, color=ui.C_WARN),
                    ],
                ),
            )
            root.content = ft.Column(expand=True, spacing=0, controls=[banner, results])
        else:
            root.content = results
        page.update()

    if on_register_submit:
        on_register_submit(_submit)

    # ── sticky top bar ───────────────────────────────────────────────────
    sticky_bar = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=11),
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.only(bottom=ft.BorderSide(1, ui.hairline(0.10))),
        content=ft.Column(
            spacing=9,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(spacing=9, controls=[counter, answered_pill]),
                        timer_chip,
                    ],
                ),
                ft.Row(controls=[time_bar]),
            ],
        ),
    )

    # ── keyboard ─────────────────────────────────────────────────────────
    def _on_key(e: ft.KeyboardEvent):
        if state["submitted"]:
            return
        key = (e.key or "").lower()
        if state["reviewing"]:
            return
        if key == "arrow right":
            _next()
        elif key == "arrow left":
            _prev()
        elif key == "f":
            _toggle_flag()
        else:
            opts = len(((questions[state["index"]] or {}).get("options")) or [])
            if key.isdigit() and 1 <= int(key) <= opts:
                _choose(int(key) - 1)
            elif len(key) == 1 and key.upper() in _LETTERS[:opts]:
                _choose(_LETTERS.index(key.upper()))

    page.on_keyboard_event = _on_key

    # ── assemble ─────────────────────────────────────────────────────────
    compact = ui.is_compact(page)
    body = ft.Column(
        spacing=16,
        controls=[
            ui.surface_card(
                ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[ui.section_label("Question"), flag_btn],
                        ),
                        question_text,
                    ],
                ),
                padding=17,
            ),
            options_col,
            ft.Row(spacing=10, controls=[prev_btn, next_btn]),
            ui.surface_card(
                ft.Column(
                    spacing=11,
                    controls=[
                        ui.section_label("Question navigator"),
                        palette_wrap,
                        ft.Divider(height=1, color=ui.hairline(0.08)),
                        legend,
                    ],
                ),
                padding=15,
            ),
            ui.ghost_button("Review & submit", lambda _: _show_review(),
                            icon=ft.Icons.FACT_CHECK_ROUNDED, color=ui.C_INFO, expand=True),
            ft.Container(height=24),
        ],
    )

    exam_layout = ft.Column(
        expand=True,
        spacing=0,
        controls=[
            sticky_bar,
            ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Container(
                        alignment=ft.Alignment.TOP_CENTER,
                        padding=ft.Padding.symmetric(
                            horizontal=14 if compact else 28, vertical=18
                        ),
                        content=ft.Container(
                            content=body, width=None if compact else 680
                        ),
                    )
                ],
            ),
        ],
    )

    _render_question()
    root.content = exam_layout
    page.run_task(_tick)
    return root
