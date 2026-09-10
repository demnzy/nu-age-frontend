"""
Redesigned flashcard review session.

Key UX changes vs. the previous implementation:
  * A real flip animation (two stacked faces, rotate + fade) instead of
    swapping text in place, so the card feels physical.
  * 4-tier SM-2 recall grading (Again / Hard / Good / Easy) instead of a
    coarse 3-button scale. Maps to the quality values the backend expects.
  * The scheduling result from POST /study/review is surfaced back to the
    learner ("Next review in 4 days") — previously it was discarded.
  * Keyboard shortcuts: Space/Enter flips, 1-4 grades, Esc exits.
  * Session summary at the end instead of dumping the user back to the hub.
"""

import asyncio
import time

import flet as ft

from src.components import study_ui as ui


def build_flashcard_session(
    page: ft.Page,
    cards: list,
    *,
    token: str,
    on_exit,
    on_restart,
    haptics: "ui.Haptics | None" = None,
):
    """Returns a Control for the full flashcard session."""
    total = len(cards)
    state = {
        "index": 0,
        "flipped": False,
        "busy": False,
        "started": time.time(),
        "grades": {"again": 0, "hard": 0, "good": 0, "easy": 0},
        "done": False,
    }

    progress = ui.SegmentedProgress(total, active_color=ft.Colors.PRIMARY)
    counter = ft.Text(
        f"Card 1 of {total}", size=12, weight=ft.FontWeight.W_700, color=ui.muted(0.70)
    )
    remaining_pill = ui.pill(f"{total} left", ui.C_INFO, icon=ft.Icons.LAYERS_ROUNDED)

    # ── card faces ───────────────────────────────────────────────────────
    front_text = ft.Text(
        "",
        size=20,
        weight=ft.FontWeight.W_700,
        color=ft.Colors.ON_SURFACE,
        text_align=ft.TextAlign.CENTER,
        selectable=True,
    )
    back_text = ft.Text(
        "",
        size=16,
        color=ui.muted(0.85),
        text_align=ft.TextAlign.CENTER,
        selectable=True,
    )

    face_hint = ft.Text(
        "Tap to reveal", size=10, weight=ft.FontWeight.W_700, color=ui.muted(0.40)
    )

    front_face = ft.Column(
        expand=True,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=14,
        controls=[
            ui.pill("QUESTION", ft.Colors.PRIMARY, icon=ft.Icons.HELP_OUTLINE_ROUNDED),
            front_text,
        ],
    )
    back_face = ft.Column(
        expand=True,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=14,
        visible=False,
        controls=[
            ui.pill("ANSWER", ui.C_CORRECT, icon=ft.Icons.LIGHTBULB_OUTLINE_ROUNDED),
            back_text,
        ],
    )

    card_inner = ft.Column(
        expand=True,
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(expand=True, content=ft.Stack(expand=True, controls=[front_face, back_face])),
            face_hint,
        ],
    )

    card_surface = ft.Container(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=22, vertical=26),
        border_radius=ui.RADIUS_LG,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ui.hairline(0.12)),
        shadow=ft.BoxShadow(
            blur_radius=22,
            color=ft.Colors.with_opacity(0.10, ft.Colors.BLACK),
            offset=ft.Offset(0, 8),
        ),
        alignment=ft.Alignment.CENTER,
        content=card_inner,
        # Animate the flip: a small Y-rotation plus opacity gives a
        # convincing 3D-ish flip without needing a real transform matrix.
        rotate=ft.Rotate(angle=0),
        animate_rotation=ft.Animation(ui.DUR_BASE, ui.CURVE_EMPHASIS),
        opacity=1.0,
        animate_opacity=ft.Animation(ui.DUR_FAST, ui.CURVE_OUT),
        scale=1.0,
        animate_scale=ft.Animation(ui.DUR_BASE, ui.CURVE_SPRING),
        offset=ft.Offset(0, 0),
        animate_offset=ft.Animation(ui.DUR_BASE, ui.CURVE_OUT),
    )

    # ── scheduling feedback ("Next review in N days") ────────────────────
    sched_text = ft.Text("", size=11, weight=ft.FontWeight.W_700, color=ui.C_INFO)
    sched_banner = ft.Container(
        opacity=0.0,
        animate_opacity=ft.Animation(ui.DUR_BASE, ui.CURVE_OUT),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=999,
        bgcolor=ui.tint(ui.C_INFO, 0.10),
        border=ft.Border.all(1, ui.tint(ui.C_INFO, 0.25)),
        content=ft.Row(
            tight=True,
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.EVENT_AVAILABLE_ROUNDED, size=13, color=ui.C_INFO),
                sched_text,
            ],
        ),
    )

    def _render_card():
        card = cards[state["index"]] or {}
        front_text.value = str(card.get("front") or "—")
        back_text.value = str(card.get("back") or "—")
        state["flipped"] = False
        front_face.visible = True
        back_face.visible = False
        face_hint.value = "Tap to reveal  ·  Space"
        counter.value = f"Card {state['index'] + 1} of {total}"
        left = total - state["index"]
        remaining_pill.content.controls[-1].value = f"{left} left"
        progress.set_current(state["index"])
        grade_row.visible = False
        flip_row.visible = True
        sched_banner.opacity = 0.0

    def _flip(_=None):
        if state["busy"] or state["done"]:
            return
        state["flipped"] = not state["flipped"]
        if haptics:
            haptics.select()

        async def _run():
            # Half-turn out, swap faces at the midpoint, half-turn back.
            card_surface.rotate = ft.Rotate(angle=0.06 if state["flipped"] else -0.06)
            card_surface.opacity = 0.55
            page.update()
            await asyncio.sleep(ui.DUR_FAST / 1000)
            front_face.visible = not state["flipped"]
            back_face.visible = state["flipped"]
            face_hint.value = (
                "How well did you recall this?" if state["flipped"] else "Tap to reveal  ·  Space"
            )
            grade_row.visible = state["flipped"]
            flip_row.visible = not state["flipped"]
            card_surface.rotate = ft.Rotate(angle=0)
            card_surface.opacity = 1.0
            page.update()

        page.run_task(_run)

    async def _advance():
        """Slide the current card out, bring the next one in."""
        card_surface.offset = ft.Offset(-0.25, 0)
        card_surface.opacity = 0.0
        page.update()
        await asyncio.sleep(ui.DUR_BASE / 1000)

        state["index"] += 1
        if state["index"] >= total:
            _finish()
            return

        _render_card()
        card_surface.offset = ft.Offset(0.25, 0)
        page.update()
        await asyncio.sleep(0.02)
        card_surface.offset = ft.Offset(0, 0)
        card_surface.opacity = 1.0
        page.update()

    async def _grade(quality: int, bucket: str, seg_color):
        if state["busy"] or state["done"]:
            return
        state["busy"] = True
        state["grades"][bucket] += 1
        progress.mark(state["index"], seg_color)
        if haptics:
            haptics.light()

        card = cards[state["index"]] or {}
        card_id = str(card.get("id") or "")

        # Fire the review off, but surface the returned schedule.
        try:
            from src.requests.study import post_review

            result = await asyncio.wait_for(
                post_review(token, card_id=card_id, quality=quality), timeout=12
            )
            days = (result or {}).get("interval_days")
            if days is not None:
                sched_text.value = (
                    "Next review tomorrow" if int(days) <= 1
                    else f"Next review in {int(days)} days"
                )
                sched_banner.opacity = 1.0
                page.update()
                await asyncio.sleep(0.45)
        except Exception:
            # Offline / failed sync shouldn't block the session.
            pass

        state["busy"] = False
        await _advance()

    def _grade_click(quality: int, bucket: str, color):
        def handler(_):
            page.run_task(_grade, quality, bucket, color)

        return handler

    # ── grading controls ─────────────────────────────────────────────────
    def _grade_button(label: str, sub: str, color, quality: int, bucket: str, key: str):
        return ft.Container(
            expand=True,
            height=62,
            border_radius=ui.RADIUS_SM,
            bgcolor=ui.tint(color, 0.10),
            border=ft.Border.all(1.5, ui.tint(color, 0.35)),
            ink=True,
            on_click=_grade_click(quality, bucket, color),
            padding=ft.Padding.symmetric(horizontal=6, vertical=8),
            animate=ft.Animation(ui.DUR_FAST, ui.CURVE_OUT),
            content=ft.Column(
                spacing=1,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(label, size=11, weight=ft.FontWeight.W_800, color=color),
                    ft.Text(sub, size=9, color=ui.muted(0.50)),
                    ft.Text(key, size=8, weight=ft.FontWeight.W_700, color=ui.muted(0.35)),
                ],
            ),
        )

    grade_row = ft.Row(
        spacing=8,
        visible=False,
        controls=[
            _grade_button("Again", "Forgot", ui.C_WRONG, ui.GRADE_AGAIN, "again", "1"),
            _grade_button("Hard", "Struggled", ui.C_WARN, ui.GRADE_HARD, "hard", "2"),
            _grade_button("Good", "Recalled", ui.C_CORRECT_SOFT, ui.GRADE_GOOD, "good", "3"),
            _grade_button("Easy", "Instant", ui.C_CORRECT, ui.GRADE_EASY, "easy", "4"),
        ],
    )

    flip_row = ft.Row(
        controls=[
            ui.primary_button(
                "Reveal answer", _flip, icon=ft.Icons.VISIBILITY_ROUNDED, expand=True, height=52
            )
        ]
    )

    # ── session summary ──────────────────────────────────────────────────
    session_socket = ft.Container(expand=True)

    def _finish():
        state["done"] = True
        progress.fill_all(ft.Colors.PRIMARY)
        elapsed = int(time.time() - state["started"])
        g = state["grades"]
        recalled = g["good"] + g["easy"]
        pct = round(recalled / max(total, 1) * 100)
        verdict, v_color, v_icon, blurb = ui.verdict_for(pct)
        ring, ring_anim = ui.score_ring(pct, v_color)

        summary = ft.Column(
            spacing=18,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=20, vertical=24),
                    border_radius=ui.RADIUS_LG,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_LEFT,
                        end=ft.Alignment.BOTTOM_RIGHT,
                        colors=[ui.tint(ft.Colors.PRIMARY, 0.12), ui.tint(v_color, 0.06)],
                    ),
                    border=ft.Border.all(1, ui.tint(v_color, 0.22)),
                    content=ft.Column(
                        spacing=12,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ui.pill("Session complete", ft.Colors.PRIMARY,
                                    icon=ft.Icons.CELEBRATION_ROUNDED),
                            ring,
                            ft.Row(
                                spacing=8,
                                alignment=ft.MainAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(v_icon, size=18, color=v_color),
                                    ft.Text(verdict, size=19, weight=ft.FontWeight.W_800,
                                            color=v_color),
                                ],
                            ),
                            ft.Text(blurb, size=12, color=ui.muted(0.65),
                                    text_align=ft.TextAlign.CENTER),
                            ft.Text(f"You recalled {recalled} of {total} cards",
                                    size=13, weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE),
                        ],
                    ),
                ),
                ft.Row(
                    spacing=8,
                    controls=[
                        ui.stat_tile(str(g["again"]), "Again", ui.C_WRONG,
                                     ft.Icons.REPLAY_ROUNDED),
                        ui.stat_tile(str(g["hard"]), "Hard", ui.C_WARN,
                                     ft.Icons.TRENDING_DOWN_ROUNDED),
                        ui.stat_tile(str(g["good"]), "Good", ui.C_CORRECT_SOFT,
                                     ft.Icons.CHECK_ROUNDED),
                        ui.stat_tile(str(g["easy"]), "Easy", ui.C_CORRECT,
                                     ft.Icons.BOLT_ROUNDED),
                    ],
                ),
                ft.Row(
                    spacing=8,
                    controls=[
                        ui.stat_tile(ui.fmt_duration(elapsed), "Time studied", ui.C_INFO,
                                     ft.Icons.TIMER_OUTLINED),
                        ui.stat_tile(
                            f"{round(elapsed / max(total, 1))}s", "Avg / card",
                            ft.Colors.PRIMARY, ft.Icons.SPEED_ROUNDED,
                        ),
                    ],
                ),
                ft.Row(
                    spacing=10,
                    controls=[
                        ui.ghost_button("Back to Hub", lambda _: on_exit(),
                                        icon=ft.Icons.HOME_ROUNDED, expand=True),
                        ui.primary_button("Study again", lambda _: on_restart(),
                                          icon=ft.Icons.REPLAY_ROUNDED, expand=True),
                    ],
                ),
                ft.Container(height=20),
            ],
        )

        compact = ui.is_compact(page)
        session_socket.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Container(
                    alignment=ft.Alignment.TOP_CENTER,
                    padding=ft.Padding.symmetric(
                        horizontal=14 if compact else 28, vertical=18
                    ),
                    content=ft.Container(content=summary, width=None if compact else 640),
                )
            ],
        )
        page.run_task(ring_anim, page)
        page.update()

    # ── keyboard shortcuts ───────────────────────────────────────────────
    def _on_key(e: ft.KeyboardEvent):
        if state["done"]:
            return
        key = (e.key or "").lower()
        if key in (" ", "space", "enter"):
            _flip()
        elif key == "escape":
            on_exit()
        elif state["flipped"] and key in ("1", "2", "3", "4"):
            mapping = {
                "1": (ui.GRADE_AGAIN, "again", ui.C_WRONG),
                "2": (ui.GRADE_HARD, "hard", ui.C_WARN),
                "3": (ui.GRADE_GOOD, "good", ui.C_CORRECT_SOFT),
                "4": (ui.GRADE_EASY, "easy", ui.C_CORRECT),
            }
            q, bucket, color = mapping[key]
            page.run_task(_grade, q, bucket, color)

    page.on_keyboard_event = _on_key

    # ── assemble ─────────────────────────────────────────────────────────
    _render_card()

    tappable_card = ft.GestureDetector(
        expand=True,
        on_tap=_flip,
        # Horizontal drag = "I knew it / I didn't", the Tinder-style gesture
        # learners already expect from Quizlet and Anki mobile.
        on_horizontal_drag_end=lambda e: (
            page.run_task(_grade, ui.GRADE_GOOD, "good", ui.C_CORRECT_SOFT)
            if state["flipped"]
            else _flip()
        ),
        content=card_surface,
    )

    compact = ui.is_compact(page)
    session_socket.content = ft.Column(
        expand=True,
        spacing=0,
        controls=[
            ui.progress_header(counter, progress, right=[remaining_pill]),
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(horizontal=14 if compact else 28, vertical=16),
                content=ft.Column(
                    expand=True,
                    spacing=12,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            expand=True,
                            width=None if compact else 620,
                            content=tappable_card,
                        ),
                        ft.Container(
                            width=None if compact else 620,
                            alignment=ft.Alignment.CENTER,
                            content=sched_banner,
                        ),
                        ft.Container(
                            width=None if compact else 620,
                            content=ft.Column(spacing=8, controls=[flip_row, grade_row]),
                        ),
                    ],
                ),
            ),
        ],
    )

    return session_socket
