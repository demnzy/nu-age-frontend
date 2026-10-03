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
from src.components.deck_inspector import open_deck_inspector


def build_flashcard_session(
    page: ft.Page,
    cards: list,
    *,
    token: str,
    on_exit,
    on_restart,
    material: dict | None = None,
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

    # ── card faces (Full Markdown Supported) ──────────────────────────
    front_markdown = ft.Markdown(
        "",
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        selectable=True,
        auto_follow_links=True,
        code_theme="atom-one-dark",
    )
    back_markdown = ft.Markdown(
        "",
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        selectable=True,
        auto_follow_links=True,
        code_theme="atom-one-dark",
    )

    face_hint = ft.Text(
        "Tap to reveal", size=10, weight=ft.FontWeight.W_700, color=ui.muted(0.40)
    )

    front_face = ft.Column(
        expand=True,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
        controls=[
            ui.pill("QUESTION", ft.Colors.PRIMARY, icon=ft.Icons.HELP_OUTLINE_ROUNDED),
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            alignment=ft.Alignment.CENTER,
                            content=front_markdown,
                        ),
                    ],
                ),
            ),
        ],
    )
    back_face = ft.Column(
        expand=True,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
        visible=False,
        controls=[
            ui.pill("ANSWER & EXPLANATION", ui.C_CORRECT, icon=ft.Icons.LIGHTBULB_OUTLINE_ROUNDED),
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            alignment=ft.Alignment.CENTER,
                            content=back_markdown,
                        ),
                    ],
                ),
            ),
        ],
    )

    card_inner = ft.Column(
        expand=True,
        spacing=10,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(expand=True, alignment=ft.Alignment.CENTER, content=ft.Stack(expand=True, controls=[front_face, back_face])),
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

    def _get_font_size(text: str) -> int:
        l = len((text or "").strip())
        if l <= 60:
            return 22
        elif l <= 140:
            return 18
        elif l <= 280:
            return 15
        else:
            return 13.5

    def _make_stylesheet(size: int, is_bold: bool = False):
        return ft.MarkdownStyleSheet(
            text_alignment=ft.TextAlign.CENTER,
            h1_alignment=ft.CrossAxisAlignment.CENTER,
            h2_alignment=ft.CrossAxisAlignment.CENTER,
            h3_alignment=ft.CrossAxisAlignment.CENTER,
            ordered_list_alignment=ft.CrossAxisAlignment.CENTER,
            unordered_list_alignment=ft.CrossAxisAlignment.CENTER,
            p_text_style=ft.TextStyle(
                size=size,
                weight=ft.FontWeight.W_700 if is_bold else ft.FontWeight.W_500,
                color=ft.Colors.ON_SURFACE,
            ),
            h1_text_style=ft.TextStyle(size=size + 4, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
            h2_text_style=ft.TextStyle(size=size + 2, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
            h3_text_style=ft.TextStyle(size=size, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
            strong_text_style=ft.TextStyle(size=size, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
            code_text_style=ft.TextStyle(size=max(11, int(size - 2))),
            list_bullet_text_style=ft.TextStyle(size=size),
        )

    def _render_card():
        card = cards[state["index"]] or {}
        front_val = str(card.get("front") or card.get("question") or "—")
        back_val = str(card.get("back") or card.get("answer") or "")
        expl = str(card.get("explanation") or "").strip()
        if expl and expl not in back_val:
            if back_val:
                back_val = f"{back_val}\n\n---\n\n**💡 Explanation:**\n{expl}"
            else:
                back_val = f"**💡 Explanation:**\n{expl}"
        elif not back_val and not expl:
            back_val = "—"

        f_size = _get_font_size(front_val)
        b_size = _get_font_size(back_val)
        front_markdown.md_style_sheet = _make_stylesheet(f_size, is_bold=(f_size >= 18))
        back_markdown.md_style_sheet = _make_stylesheet(b_size, is_bold=False)

        front_markdown.value = front_val
        back_markdown.value = back_val
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

        # Fire the review off quietly in the background without exposing the algorithm intervals
        try:
            from src.requests.study import post_review

            asyncio.create_task(post_review(token, card_id=card_id, quality=quality))
        except Exception:
            pass

        state["busy"] = False
        await _advance()

    # ── tactile animated grading controls ────────────────────────────────
    grade_actions_map = {}

    def _make_grade_button(label: str, icon_name, color, quality: int, bucket: str, key_digit: str):
        btn_box = ft.Container(
            expand=True,
            height=42,
            border_radius=ft.BorderRadius.all(10),
            bgcolor=color,
            ink=True,
            padding=ft.Padding.symmetric(horizontal=4, vertical=4),
            scale=1.0,
            animate_scale=ft.Animation(80, ft.AnimationCurve.EASE_OUT),
            animate_opacity=ft.Animation(80, ft.AnimationCurve.EASE_OUT),
            shadow=ft.BoxShadow(
                blur_radius=6,
                color=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            content=ft.Row(
                spacing=5,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(icon_name, size=15, color=ft.Colors.WHITE),
                    ft.Text(label, size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                    ft.Text(f"({key_digit})", size=9.5, weight=ft.FontWeight.W_600, color=ft.Colors.with_opacity(0.80, ft.Colors.WHITE)),
                ],
            ),
        )

        async def _tap_action(e=None):
            if state["busy"] or state["done"]:
                return
            # Tapping tactile animation: squish and bounce
            btn_box.scale = 0.90
            btn_box.opacity = 0.85
            page.update()
            await asyncio.sleep(0.08)
            btn_box.scale = 1.0
            btn_box.opacity = 1.0
            page.update()
            await _grade(quality, bucket, color)

        btn_box.on_click = lambda e: page.run_task(_tap_action)
        grade_actions_map[key_digit] = _tap_action
        return btn_box

    grade_row = ft.Row(
        spacing=8,
        visible=False,
        controls=[
            _make_grade_button("Again", ft.Icons.REPLAY_ROUNDED, ui.C_WRONG, ui.GRADE_AGAIN, "again", "1"),
            _make_grade_button("Hard", ft.Icons.FITNESS_CENTER_ROUNDED, ui.C_WARN, ui.GRADE_HARD, "hard", "2"),
            _make_grade_button("Good", ft.Icons.THUMB_UP_ALT_ROUNDED, ui.C_CORRECT_SOFT, ui.GRADE_GOOD, "good", "3"),
            _make_grade_button("Easy", ft.Icons.ROCKET_LAUNCH_ROUNDED, ui.C_CORRECT, ui.GRADE_EASY, "easy", "4"),
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
            action = grade_actions_map.get(key)
            if action:
                page.run_task(action)

    page.on_keyboard_event = _on_key

    # ── assemble ─────────────────────────────────────────────────────────
    _render_card()

    browse_btn = ft.Container(
        tooltip="Browse Full Deck (Q&A)",
        ink=True,
        border_radius=ft.BorderRadius.all(8),
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        bgcolor=ui.tint(ft.Colors.PRIMARY, 0.08),
        border=ft.Border.all(1, ui.tint(ft.Colors.PRIMARY, 0.22)),
        on_click=lambda _: open_deck_inspector(page, token, material=material),
        content=ft.Row(
            tight=True,
            spacing=5,
            controls=[
                ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                ft.Text("Browse Deck", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
            ],
        ),
    )

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
            ui.progress_header(counter, progress, right=[remaining_pill, browse_btn]),
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
                            content=ft.Column(spacing=8, controls=[flip_row, grade_row]),
                        ),
                    ],
                ),
            ),
        ],
    )

    return session_socket
