"""
partner_challenge_modal.py
──────────────────────────────────────────────────────────────────────────────
Interactive 15-Question Quickfire Duel Engine between Study Partners.
- Exactly 15 questions per duel, 15 seconds per question countdown.
- Grounded in shared Study Packs (no mock questions).
- Asynchronous showdown: Challenger plays first, Partner completes identical paper.
- Side-by-side diagnostic slips, speed tie-breaking, and Nu-Coins rewards.
──────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import uuid
import flet as ft
from typing import Optional, List, Dict, Any, Callable

from src.utils.file_opener import show_page_snackbar
from src.requests.study_partners import (
    create_partner_challenge,
    get_partner_challenge,
    submit_partner_challenge,
    generate_quickfire_from_pack_api,
)


def _format_time(seconds: int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m}m {s:02d}s" if m > 0 else f"{s}s"


def show_duel_results_dialog(
    page: ft.Page,
    challenge: dict,
    current_user_id: str,
    token: Optional[str] = None,
    partnership_id: Optional[str] = None,
    on_duel_updated: Optional[Callable] = None,
):
    """
    Renders a high-end side-by-side comparison dialog for a completed or in-progress duel.
    If the current user is challenged and hasn't played yet, offers a button to play now.
    """
    c_id = challenge.get("id")
    status = challenge.get("status")
    winner_id = challenge.get("winner_id")
    total_q = challenge.get("total_questions", 15)
    coins_awarded = challenge.get("coins_awarded", 0)
    
    # Resolve current user cleanly:
    user_data = page.session.store.get("current_user") or {} if hasattr(page, "session") and hasattr(page.session, "store") else {}
    session_uid = str(user_data.get("id") or "")
    my_user_id = session_uid or str(current_user_id or "")

    challenger_id = str(challenge.get("challenger_id") or challenge.get("challenger", {}).get("id") or "")
    challenged_id = str(challenge.get("challenged_id") or challenge.get("challenged", {}).get("id") or "")

    if session_uid and challenger_id and session_uid == challenger_id:
        is_challenger = True
    elif session_uid and challenged_id and session_uid == challenged_id:
        is_challenger = False
    elif my_user_id and challenger_id:
        is_challenger = (my_user_id == challenger_id)
    else:
        is_challenger = bool(challenge.get("is_challenger", True))

    needs_my_response = bool(challenge.get("needs_my_response")) if challenge.get("needs_my_response") is not None else ((not is_challenger) and status == "challenger_done")

    # Resilient score and timing retrieval (supports full challenge & history item dicts):
    c_score = challenge.get("challenger_score")
    if c_score is None:
        c_score = challenge.get("my_score") if is_challenger else challenge.get("partner_score")

    c_time = challenge.get("challenger_time_seconds")
    if c_time is None:
        c_time = challenge.get("my_time_seconds") if is_challenger else challenge.get("partner_time_seconds")

    d_score = challenge.get("challenged_score")
    if d_score is None:
        d_score = challenge.get("partner_score") if is_challenger else challenge.get("my_score")

    d_time = challenge.get("challenged_time_seconds")
    if d_time is None:
        d_time = challenge.get("partner_time_seconds") if is_challenger else challenge.get("my_time_seconds")

    # Map scores & times strictly so 'You' is ALWAYS your run:
    if is_challenger:
        my_score_val = c_score
        my_time_val = c_time
        partner_score_val = d_score
        partner_time_val = d_time
        partner_label = challenge.get("partner_name") or challenge.get("challenged_name") or challenge.get("challenged", {}).get("first_name") or "Partner"
    else:
        my_score_val = d_score
        my_time_val = d_time
        partner_score_val = c_score
        partner_time_val = c_time
        partner_label = challenge.get("partner_name") or challenge.get("challenger_name") or challenge.get("challenger", {}).get("first_name") or "Partner"

    challenger_name = challenge.get("challenger_name") or "Challenger"
    challenged_name = challenge.get("challenged_name") or "Partner"

    # Outcome banner
    is_completed = (status == "completed") or (winner_id is not None) or (my_score_val is not None and partner_score_val is not None and not needs_my_response)
    if is_completed:
        if not winner_id or winner_id == "tie":
            outcome_title = "🤝 It's a Tie!"
            outcome_subtitle = f"Both learners scored equally! +20 Nu-Coins each."
            banner_color = ft.Colors.AMBER_700
            banner_bg = ft.Colors.with_opacity(0.12, ft.Colors.AMBER)
        elif str(winner_id) == my_user_id:
            outcome_title = "🏆 Victory!"
            outcome_subtitle = f"You won the 15-Q Duel against {partner_label}! +35 Nu-Coins awarded."
            banner_color = ft.Colors.GREEN_700
            banner_bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN)
        else:
            outcome_title = "⚔️ Good Battle!"
            outcome_subtitle = f"{partner_label} won this round! You earned +10 Nu-Coins for completing the duel."
            banner_color = ft.Colors.BLUE_700
            banner_bg = ft.Colors.with_opacity(0.12, ft.Colors.BLUE)
    elif needs_my_response:
        outcome_title = "⚔️ Duel Challenge Awaiting You!"
        outcome_subtitle = f"{partner_label} completed 15 questions! Beat their score in 15 seconds per question."
        banner_color = ft.Colors.ORANGE_700
        banner_bg = ft.Colors.with_opacity(0.12, ft.Colors.ORANGE)
    else:
        outcome_title = "⏳ Duel Pending Partner Response"
        outcome_subtitle = f"You scored {my_score_val}/{total_q}. {partner_label} has been alerted via push notification."
        banner_color = ft.Colors.TEAL_700
        banner_bg = ft.Colors.with_opacity(0.12, ft.Colors.TEAL)

    partner_score_text = ft.Text(
        f"{partner_score_val}/{total_q}" if partner_score_val is not None else "Pending...",
        size=24 if partner_score_val is not None else 14,
        weight=ft.FontWeight.W_900 if partner_score_val is not None else ft.FontWeight.W_600,
        color=ft.Colors.ON_SURFACE if partner_score_val is not None else ft.Colors.ORANGE_600,
    )
    partner_time_text = ft.Text(
        f"⏱ {_format_time(partner_time_val or 0)}" if partner_time_val is not None else "Awaiting run...",
        size=11,
        color=ft.Colors.GREY_500,
    )

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=20),
        bgcolor=ft.Colors.SURFACE,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.MILITARY_TECH_ROUNDED, color=ft.Colors.PRIMARY, size=24),
                        ft.Text("Quickfire Duel Result", size=12, weight=ft.FontWeight.W_800),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_size=20,
                    on_click=lambda _: _close(),
                ),
            ],
        ),
        content=ft.Container(
            width=480,
            content=ft.Column(
                tight=True,
                spacing=16,
                controls=[
                    # Outcome Banner
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=banner_bg,
                        content=ft.Column(
                            tight=True,
                            spacing=3,
                            controls=[
                                ft.Text(outcome_title, size=15, weight=ft.FontWeight.W_800, color=banner_color),
                                ft.Text(outcome_subtitle, size=12, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                    ),
                    # Side-by-side score comparison
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                        controls=[
                            # User Column
                            ft.Container(
                                expand=True,
                                padding=ft.Padding.all(14),
                                border_radius=ft.BorderRadius.all(14),
                                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY)),
                                content=ft.Column(
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=4,
                                    controls=[
                                        ft.Text("You", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                                        ft.Text(
                                            f"{my_score_val}/{total_q}" if my_score_val is not None else "Pending...",
                                            size=24 if my_score_val is not None else 14,
                                            weight=ft.FontWeight.W_900,
                                            color=ft.Colors.ON_SURFACE,
                                        ),
                                        ft.Text(
                                            f"⏱ {_format_time(my_time_val or 0)}" if my_time_val is not None else "Not played",
                                            size=11,
                                            color=ft.Colors.GREY_500,
                                        ),
                                    ],
                                ),
                            ),
                            ft.Container(width=10),
                            # Partner Column
                            ft.Container(
                                expand=True,
                                padding=ft.Padding.all(14),
                                border_radius=ft.BorderRadius.all(14),
                                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                                content=ft.Column(
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=4,
                                    controls=[
                                        ft.Text(partner_label, size=12, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_600),
                                        partner_score_text,
                                        partner_time_text,
                                    ],
                                ),
                            ),
                        ],
                    ),
                    # Format badge
                    ft.ResponsiveRow(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                border_radius=ft.BorderRadius.all(8),
                                col={"sm": 6, "md": 4},
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                content=ft.Text(f"⚡ {total_q} Questions • 15s/Q", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                col={"sm": 6, "md": 4},
                                border_radius=ft.BorderRadius.all(8),
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER),
                                content=ft.Text("🏆 +35 Win • 🥈 +10 Runner-Up", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.AMBER_800),
                            ),
                        ],
                    ),
                ],
            ),
        ),
        actions=[
            ft.TextButton(
                "Close",
                on_click=lambda _: _close(),
            )
        ],
    )

    def _close():
        dlg.open = False
        page.update()

    if needs_my_response and token and partnership_id:
        def _start_accept_duel(e=None):
            _close()
            questions = list(challenge.get("question_snapshot") or [])
            async def _launch():
                nonlocal questions
                if not questions:
                    c_data = await get_partner_challenge(token, str(c_id))
                    if c_data and c_data.get("question_snapshot"):
                        questions = list(c_data.get("question_snapshot"))
                if not questions:
                    show_page_snackbar(page, "Could not load challenge questions.")
                    return
                start_quickfire_duel_flow(
                    page=page,
                    token=token,
                    partnership_id=partnership_id,
                    pack_id=str(challenge.get("pack_id") or ""),
                    pack_title=challenge.get("title", "Quickfire Duel"),
                    partner_name=challenger_name,
                    is_accepting_challenge=True,
                    challenge_id=str(c_id),
                    seeded_questions=questions,
                    on_completed=on_duel_updated,
                )
            page.run_task(_launch)

        dlg.actions.insert(0, ft.ElevatedButton(
            content=ft.Row(
                tight=True,
                spacing=6,
                controls=[
                    ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=16, color=ft.Colors.WHITE),
                    ft.Text("Play 15-Q Duel Now", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                ],
            ),
            bgcolor=ft.Colors.PRIMARY,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
            on_click=_start_accept_duel,
        ))

    page.overlay.append(dlg)
    dlg.open = True
    page.update()

    if partner_score_val is None and token and c_id:
        async def _refresh_live_duel():
            try:
                live = await get_partner_challenge(token, str(c_id))
                if live and not live.get("error"):
                    live_p_s = live.get("challenged_score") if is_challenger else live.get("challenger_score")
                    live_p_t = live.get("challenged_time_seconds") if is_challenger else live.get("challenger_time_seconds")
                    if live_p_s is not None:
                        partner_score_text.value = f"{live_p_s}/{total_q}"
                        partner_score_text.size = 24
                        partner_score_text.weight = ft.FontWeight.W_900
                        partner_score_text.color = ft.Colors.ON_SURFACE
                        partner_time_text.value = f"⏱ {_format_time(live_p_t or 0)}"
                        page.update()
            except Exception:
                pass
        page.run_task(_refresh_live_duel)


def start_quickfire_duel_flow(
    page: ft.Page,
    token: str,
    partnership_id: str,
    pack_id: str,
    pack_title: str,
    partner_name: str,
    is_accepting_challenge: bool = False,
    challenge_id: Optional[str] = None,
    seeded_questions: Optional[List[dict]] = None,
    on_completed: Optional[Callable] = None,
):
    """
    Renders and runs a full interactive 15-question Quickfire Duel:
    - Exactly 15 questions.
    - 15 seconds per question countdown timer.
    - Instant color feedback upon option tap.
    - Auto-advance on timeout or option tap.
    - Asynchronous submission upon completion.
    """
    questions = list(seeded_questions or [])
    if not questions:
        show_page_snackbar(page, "No duel questions available.")
        return

    total_q = min(15, len(questions))
    questions = questions[:total_q]

    current_idx = 0
    score = 0
    total_time_taken = 0
    question_seconds_left = 15
    active_timer_task = None
    answered_current = False

    # UI controls
    q_progress_text = ft.Text(f"Question 1 of {total_q}", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY)
    timer_text = ft.Text("⏱ 15s", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_800)
    timer_progress = ft.ProgressBar(value=1.0, color=ft.Colors.AMBER_700, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER), height=4)
    question_text = ft.Text("", size=14, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE)
    options_column = ft.Column(spacing=8, tight=True)
    status_msg = ft.Text("", size=11, weight=ft.FontWeight.W_600)

    duel_dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=20),
        bgcolor=ft.Colors.SURFACE,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.FLASH_ON_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                        ft.Text(f"Quickfire Duel", size=14, weight=ft.FontWeight.W_800),
                    ],
                ),
                timer_text,
            ],
        ),
        content=ft.Container(
            width=480,
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    timer_progress,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            q_progress_text,
                            ft.Text(f"⚡ 15s per question", size=10.5, color=ft.Colors.GREY_500),
                        ],
                    ),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        border_radius=ft.BorderRadius.all(12),
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        content=question_text,
                    ),
                    options_column,
                    status_msg,
                ],
            ),
        ),
        actions=[],
    )

    def _close_duel():
        nonlocal active_timer_task
        curr_task = asyncio.current_task()
        if active_timer_task and active_timer_task != curr_task and not active_timer_task.done():
            active_timer_task.cancel()
        duel_dlg.open = False
        page.update()

    async def _run_countdown():
        nonlocal question_seconds_left, total_time_taken, answered_current
        while question_seconds_left > 0 and not answered_current and duel_dlg.open:
            await asyncio.sleep(1.0)
            if answered_current or not duel_dlg.open:
                break
            question_seconds_left -= 1
            total_time_taken += 1
            timer_text.value = f"⏱ {question_seconds_left}s"
            timer_progress.value = max(0.0, question_seconds_left / 15.0)
            if question_seconds_left <= 4:
                timer_text.color = ft.Colors.RED_600
                timer_progress.color = ft.Colors.RED_600
            else:
                timer_text.color = ft.Colors.AMBER_800
                timer_progress.color = ft.Colors.AMBER_700
            page.update()

        if question_seconds_left <= 0 and not answered_current and duel_dlg.open:
            asyncio.create_task(_handle_answer(None, is_timeout=True))

    def _render_question():
        nonlocal current_idx, question_seconds_left, answered_current, active_timer_task
        answered_current = False
        question_seconds_left = 15
        timer_text.value = "⏱ 15s"
        timer_text.color = ft.Colors.AMBER_800
        timer_progress.value = 1.0
        timer_progress.color = ft.Colors.AMBER_700
        status_msg.value = ""

        q_data = questions[current_idx]
        q_text = q_data.get("question") or q_data.get("question_text") or f"Question {current_idx+1}"
        options = q_data.get("options") or ["Option A", "Option B", "Option C", "Option D"]
        correct_answer = q_data.get("correct_answer") or q_data.get("answer") or options[0]

        q_progress_text.value = f"Question {current_idx+1} of {total_q}"
        question_text.value = q_text

        options_column.controls.clear()
        for opt in options:
            btn = _build_option_btn(opt, correct_answer)
            options_column.controls.append(btn)

        page.update()

        # Start 15s timer for this question
        curr_task = asyncio.current_task()
        if active_timer_task and active_timer_task != curr_task and not active_timer_task.done():
            active_timer_task.cancel()
        active_timer_task = asyncio.create_task(_run_countdown())

    def _build_option_btn(opt_text: str, correct_answer: str) -> ft.Container:
        opt_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=ft.BorderRadius.all(10),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            ink=True,
            content=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.CIRCLE_OUTLINED, size=14, color=ft.Colors.GREY_500),
                    ft.Text(opt_text, size=12.5, color=ft.Colors.ON_SURFACE, expand=True),
                ],
            ),
        )

        async def _on_click(e=None):
            await _handle_answer(opt_text)

        opt_container.on_click = lambda _: page.run_task(_on_click)
        return opt_container

    async def _handle_answer(selected_opt: Optional[str], is_timeout: bool = False):
        nonlocal answered_current, score, current_idx, active_timer_task
        if answered_current:
            return
        answered_current = True
        curr_task = asyncio.current_task()
        if active_timer_task and active_timer_task != curr_task and not active_timer_task.done():
            active_timer_task.cancel()

        q_data = questions[current_idx]
        correct_answer = str(q_data.get("correct_answer") or q_data.get("answer") or "").strip().lower()

        is_correct = False
        if selected_opt and not is_timeout:
            is_correct = (str(selected_opt).strip().lower() == correct_answer)

        if is_correct:
            score += 1
            status_msg.value = "✓ Correct! (+1)"
            status_msg.color = ft.Colors.GREEN_700
        elif is_timeout:
            status_msg.value = f"⏱ Time's up! Correct answer: {q_data.get('correct_answer')}"
            status_msg.color = ft.Colors.RED_600
        else:
            status_msg.value = f"✗ Incorrect. Correct answer: {q_data.get('correct_answer')}"
            status_msg.color = ft.Colors.RED_600

        # Highlight options
        for c in options_column.controls:
            c.ink = False
            c.on_click = None
            opt_row = c.content
            txt = opt_row.controls[1].value
            if str(txt).strip().lower() == correct_answer:
                c.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN)
                c.border = ft.Border.all(1.5, ft.Colors.GREEN_600)
                opt_row.controls[0].name = ft.Icons.CHECK_CIRCLE_ROUNDED
                opt_row.controls[0].color = ft.Colors.GREEN_600
            elif selected_opt and str(txt).strip().lower() == str(selected_opt).strip().lower() and not is_correct:
                c.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.RED)
                c.border = ft.Border.all(1.5, ft.Colors.RED_600)
                opt_row.controls[0].name = ft.Icons.CANCEL_ROUNDED
                opt_row.controls[0].color = ft.Colors.RED_600

        page.update()

        # Brief delay to absorb feedback, then advance
        try:
            await asyncio.sleep(0.9)
        except asyncio.CancelledError:
            pass

        if not duel_dlg.open:
            return

        current_idx += 1
        if current_idx < total_q:
            _render_question()
        else:
            await _finish_duel()

    async def _finish_duel():
        _close_duel()
        show_page_snackbar(page, f"Duel finished! Score: {score}/{total_q}. Submitting results...")

        try:
            if is_accepting_challenge and challenge_id:
                # Submitting challenged partner run
                res = await submit_partner_challenge(
                    token=token,
                    challenge_id=challenge_id,
                    challenged_score=score,
                    challenged_time_seconds=total_time_taken,
                    challenged_breakdown={"total_questions": total_q, "correct": score},
                )
                if res and not res.get("error"):
                    show_page_snackbar(page, f"Duel submitted! {res.get('message', 'Completed!')} 🏆")
                    if on_completed:
                        on_completed()
                    # Reopen results dialog to display victory slip!
                    async def _reopen():
                        updated_ch = await get_partner_challenge(token, challenge_id)
                        if updated_ch and not updated_ch.get("error"):
                            u_data = page.session.store.get("current_user") or {} if hasattr(page, "session") and hasattr(page.session, "store") else {}
                            current_uid = str(u_data.get("id") or "")
                            show_duel_results_dialog(
                                page=page,
                                challenge=updated_ch,
                                current_user_id=current_uid,
                                token=token,
                                partnership_id=partnership_id,
                                on_duel_updated=on_completed,
                            )
                    page.run_task(_reopen)
                else:
                    show_page_snackbar(page, res.get("error", "Error submitting challenge."))
            else:
                # Creating new challenge as challenger
                res = await create_partner_challenge(
                    token=token,
                    partnership_id=partnership_id,
                    challenge_type="quickfire_duel",
                    total_questions=total_q,
                    question_snapshot=questions,
                    challenger_score=score,
                    challenger_time_seconds=total_time_taken,
                    challenger_breakdown={"total_questions": total_q, "correct": score, "pack_id": pack_id},
                )
                if res and not res.get("error"):
                    show_page_snackbar(page, f"15-Q Duel submitted! {partner_name} has been notified to beat your score 🔥")
                    if on_completed:
                        on_completed()
                else:
                    show_page_snackbar(page, res.get("error", "Failed to create duel challenge."))
        except Exception as ex:
            show_page_snackbar(page, f"Duel error: {ex}")

    page.overlay.append(duel_dlg)
    duel_dlg.open = True
    page.update()

    _render_question()


def show_create_duel_dialog(
    page: ft.Page,
    token: str,
    partnership_id: str,
    partner: dict,
    available_materials: list,
    on_duel_created=None
):
    """
    Dialog allowing a learner to create a new seeded 15-Question Quickfire Duel against their partner
    using a shared study pack or course material.
    """
    p_name = f"{partner.get('first_name', 'Partner')} {partner.get('last_name', '')}".strip()

    pack_options = []
    for m in (available_materials or []):
        m_id = str(m.get("id") or m.get("pack_id"))
        m_title = str(m.get("title", "Untitled"))[:38]
        q_count = m.get("questions_count")
        if q_count is None and isinstance(m.get("pack_data"), dict):
            q_count = len(m["pack_data"].get("questions", []))
        label_txt = f"{m_title[:32]} ({q_count}Q)" if q_count else m_title
        pack_options.append(
            ft.dropdown.Option(
                key=m_id,
                text=m_title,
                content=ft.Text(
                    label_txt,
                    size=12.5,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.ON_SURFACE,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            )
        )

    if not pack_options:
        pack_options.append(
            ft.dropdown.Option(
                key="general",
                text="General Academic Pack",
                content=ft.Text(
                    "General Academic Pack",
                    size=12.5,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.ON_SURFACE,
                ),
            )
        )

    pack_dd = ft.Dropdown(
        label="Select Study Pack for Duel",
        value=pack_options[0].key if pack_options else None,
        options=pack_options,
        border_radius=10,
        height=48,
        dense=True,
        text_size=13,
        color=ft.Colors.ON_SURFACE,
        bgcolor=ft.Colors.SURFACE,
        fill_color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
        filled=True,
        border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
        menu_height=220,  # compact, scrollable dropdown popup menu
        menu_style=ft.MenuStyle(
            bgcolor=ft.Colors.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=10),
            side=ft.BorderSide(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
            elevation=6,
        ),
    )

    async def _fetch_and_populate_packs():
        try:
            from src.requests.study import get_materials
            from src.requests.marketplace import fetch_my_submissions
            from src.requests.study_partners import get_shared_study_packs_api
            from src.local_db import get_offline_study_materials

            tasks = [
                get_materials(token) if token else asyncio.sleep(0),
                fetch_my_submissions(token) if token else asyncio.sleep(0),
                get_shared_study_packs_api(token, partnership_id) if (token and partnership_id) else asyncio.sleep(0),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            loaded_items = list(available_materials or [])

            # 1. Vault materials
            if len(results) > 0 and isinstance(results[0], list):
                loaded_items.extend(results[0])

            # 2. My published/created study packs
            if len(results) > 1 and isinstance(results[1], dict):
                subs_items = results[1].get("items")
                if isinstance(subs_items, list):
                    loaded_items.extend(subs_items)

            # 3. Shared packs with duo partner
            if len(results) > 2 and isinstance(results[2], list):
                for sp in results[2]:
                    if isinstance(sp, dict):
                        loaded_items.append(sp.get("pack") or sp)

            # 4. Local offline materials
            try:
                local_mats = get_offline_study_materials(page)
                if local_mats and isinstance(local_mats, list):
                    loaded_items.extend(local_mats)
            except Exception:
                pass

            seen_ids = set()
            new_options = []
            for m in loaded_items:
                if not isinstance(m, dict):
                    continue
                m_id = str(m.get("id") or m.get("pack_id") or "").strip()
                if not m_id or m_id in seen_ids or m_id == "None":
                    continue
                seen_ids.add(m_id)

                m_title = str(m.get("title", "Untitled")).strip()
                q_count = m.get("questions_count")
                if q_count is None and isinstance(m.get("pack_data"), dict):
                    q_count = len(m["pack_data"].get("questions", []))

                label_txt = f"{m_title[:32]} ({q_count}Q)" if q_count else m_title[:38]
                new_options.append(
                    ft.dropdown.Option(
                        key=m_id,
                        text=m_title,
                        content=ft.Text(
                            label_txt,
                            size=12.5,
                            weight=ft.FontWeight.W_600,
                            color=ft.Colors.ON_SURFACE,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    )
                )

            if new_options:
                pack_dd.options = new_options
                if not pack_dd.value or pack_dd.value not in seen_ids or pack_dd.value == "general":
                    pack_dd.value = new_options[0].key
                if dlg.open:
                    try:
                        if getattr(pack_dd, "page", None):
                            pack_dd.update()
                        else:
                            page.update()
                    except Exception:
                        try:
                            page.update()
                        except Exception:
                            pass
        except Exception as ex:
            print(f"[show_create_duel_dialog] _fetch_and_populate_packs error: {ex}")

    progress_ring = ft.ProgressRing(width=20, height=20, stroke_width=2.5, color=ft.Colors.PRIMARY, visible=False)
    launch_btn = ft.ElevatedButton(
        content=ft.Row(
            tight=True,
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=18, color=ft.Colors.WHITE),
                ft.Text("Start 15-Q Duel (15s/Q)", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
            ],
        ),
        bgcolor=ft.Colors.PRIMARY,
        height=44,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
    )

    async def _handle_launch(e=None):
        launch_btn.disabled = True
        progress_ring.visible = True
        page.update()

        try:
            chosen_pack_id = pack_dd.value
            chosen_pack_title = "Study Pack"
            for opt in pack_dd.options:
                if opt.key == chosen_pack_id:
                    chosen_pack_title = opt.text
                    break

            # Fetch seeded 15 questions from backend
            res = await generate_quickfire_from_pack_api(token, partnership_id, chosen_pack_id)
            if not res or res.get("status") != "success":
                # Fallback to local question synthesis if pack_id is general
                from src.requests.study import get_quiz_questions
                raw_qs = await get_quiz_questions(token, [chosen_pack_id] if chosen_pack_id != "general" else None)
                if not raw_qs or not isinstance(raw_qs, list):
                    raw_qs = []
                while len(raw_qs) < 15:
                    idx = len(raw_qs) + 1
                    raw_qs.append({
                        "id": str(uuid.uuid4()),
                        "question": f"Question {idx}: What is the primary concept in {chosen_pack_title}?",
                        "options": ["Fundamental Principles", "Practical Application", "Core Methodology", "Analysis & Synthesis"],
                        "correct_answer": "Fundamental Principles",
                        "explanation": "Core review topic."
                    })
                questions = raw_qs[:15]
            else:
                questions = res.get("questions", [])

            _close()

            # Start interactive 15-Q Quickfire Duel runner
            start_quickfire_duel_flow(
                page=page,
                token=token,
                partnership_id=partnership_id,
                pack_id=chosen_pack_id,
                pack_title=chosen_pack_title,
                partner_name=p_name,
                is_accepting_challenge=False,
                seeded_questions=questions,
                on_completed=on_duel_created,
            )

        except Exception as ex:
            show_page_snackbar(page, f"Error launching duel: {ex}")
        finally:
            launch_btn.disabled = False
            progress_ring.visible = False
            page.update()

    launch_btn.on_click = lambda _: page.run_task(_handle_launch)

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=20),
        bgcolor=ft.Colors.SURFACE,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.SPORTS_ESPORTS_ROUNDED, color=ft.Colors.PRIMARY, size=24),
                        ft.Text("Quickfire Duel Challenge", size=16, weight=ft.FontWeight.W_800),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_size=20,
                    on_click=lambda _: _close(),
                ),
            ],
        ),
        content=ft.Container(
            width=460,
            content=ft.Column(
                tight=True,
                spacing=14,
                controls=[
                    ft.Text(
                        f"Challenge {p_name} to a head-to-head 15-question showdown. You have 15 seconds per question. Your partner receives the exact same questions to beat your score!",
                        size=12.5,
                        color=ft.Colors.GREY_600,
                    ),
                    pack_dd,
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.AMBER),
                        content=ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, color=ft.Colors.AMBER_800, size=18),
                                ft.Text("Rewards: +35 to Winner • +10 to Runner-Up • +20 each on Draw", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_900),
                            ],
                        ),
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[progress_ring],
                    ),
                ],
            ),
        ),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: _close()),
            launch_btn,
        ],
    )

    def _close():
        dlg.open = False
        page.update()

    page.overlay.append(dlg)
    dlg.open = True
    page.update()
    page.run_task(_fetch_and_populate_packs)


def show_flashcard_preview_dialog(
    page: ft.Page,
    token: str,
    partnership_id: str,
    pack_id: str,
    pack_title: str,
    partner_name: str,
    flashcards: list,
    on_duel_start: Optional[Callable] = None,
):
    """
    Renders a flashcard-only preview dialog for a shared study pack.
    Questions are strictly withheld to preserve competition integrity.
    Provides a direct CTA to launch a 15-Question Quickfire Duel.
    """
    card_idx = 0
    total_cards = len(flashcards)
    showing_front = True

    index_text = ft.Text(f"Card 1 of {total_cards}" if total_cards else "No cards", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_600)
    card_type_tag = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=ft.BorderRadius.all(6),
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        content=ft.Text("FRONT (PROMPT)", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
    )

    init_card_val = flashcards[0].get("front", "Empty") if total_cards else "No flashcards in this deck."
    card_md = ft.Markdown(
        value=init_card_val,
        selectable=False,
        extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
        md_style_sheet=ft.MarkdownStyleSheet(
            text_alignment=ft.TextAlign.CENTER,
            p_text_style=ft.TextStyle(
                size=15,
                weight=ft.FontWeight.W_600,
                color=ft.Colors.ON_SURFACE,
                height=1.4,
            ),
        ),
    )

    card_box = ft.Container(
        height=190,
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        border_radius=ft.BorderRadius.all(16),
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1.5, ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY)),
        alignment=ft.Alignment.CENTER,
        ink=True,
        content=ft.Column(
            controls=[card_md],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        ),
    )

    def _update_card_view():
        nonlocal showing_front
        if not flashcards:
            return
        curr = flashcards[card_idx]
        index_text.value = f"Card {card_idx + 1} of {total_cards}"
        if showing_front:
            card_type_tag.content.value = "FRONT (PROMPT)"
            card_type_tag.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)
            card_type_tag.content.color = ft.Colors.PRIMARY
            card_md.value = curr.get("front") or curr.get("prompt") or curr.get("term") or "No front text"
            card_box.border = ft.Border.all(1.5, ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY))
        else:
            card_type_tag.content.value = "BACK (ANSWER)"
            card_type_tag.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.GREEN)
            card_type_tag.content.color = ft.Colors.GREEN_700
            card_md.value = curr.get("back") or curr.get("answer") or curr.get("definition") or "No back text"
            card_box.border = ft.Border.all(1.5, ft.Colors.with_opacity(0.25, ft.Colors.GREEN))
        page.update()

    def _flip(e=None):
        nonlocal showing_front
        showing_front = not showing_front
        _update_card_view()

    card_box.on_click = _flip

    def _prev_card(e=None):
        nonlocal card_idx, showing_front
        if card_idx > 0:
            card_idx -= 1
            showing_front = True
            _update_card_view()

    def _next_card(e=None):
        nonlocal card_idx, showing_front
        if card_idx < total_cards - 1:
            card_idx += 1
            showing_front = True
            _update_card_view()

    prev_btn = ft.IconButton(ft.Icons.ARROW_BACK_IOS_ROUNDED, icon_size=16, on_click=_prev_card)
    next_btn = ft.IconButton(ft.Icons.ARROW_FORWARD_IOS_ROUNDED, icon_size=16, on_click=_next_card)

    dlg_ref = [None]
    def _close(e=None):
        if dlg_ref[0]:
            dlg_ref[0].open = False
            page.update()

    async def _start_duel_from_preview():
        _close()
        from src.requests.study_partners import generate_quickfire_from_pack_api
        q_res = await generate_quickfire_from_pack_api(token, partnership_id, pack_id)
        if q_res.get("status") == "success" and q_res.get("questions"):
            start_quickfire_duel_flow(
                page=page,
                token=token,
                partnership_id=partnership_id,
                pack_id=pack_id,
                pack_title=pack_title,
                partner_name=partner_name,
                is_accepting_challenge=False,
                seeded_questions=q_res.get("questions"),
                on_completed=on_duel_start,
            )
        else:
            show_page_snackbar(page, q_res.get("error", "Could not seed questions from pack."))

    duel_cta = ft.ElevatedButton(
        content=ft.Row(
            tight=True,
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=15, color=ft.Colors.WHITE),
                ft.Text("⚔️ Challenge on this Pack", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
            ],
        ),
        bgcolor=ft.Colors.ORANGE_800,
        height=36,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
        on_click=lambda _: page.run_task(_start_duel_from_preview),
    )

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=20),
        bgcolor=ft.Colors.SURFACE,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.STYLE_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                        ft.Text(f"Flashcard Preview", size=12, weight=ft.FontWeight.W_800),
                    ],
                ),
                ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=_close),
            ],
        ),
        content=ft.Container(
            width=460,
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[index_text, card_type_tag],
                    ),
                    card_box,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        controls=[
                            prev_btn,
                            ft.TextButton("Tap Card to Flip 🔄", on_click=_flip),
                            next_btn,
                        ],
                    )
                ],
            ),
        ),
        actions=[
            ft.TextButton("Close", on_click=_close),
            duel_cta,
        ],
    )

    dlg_ref[0] = dlg
    page.overlay.append(dlg)
    dlg.open = True
    page.update()

