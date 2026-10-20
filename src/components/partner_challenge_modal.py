"""
partner_challenge_modal.py
──────────────────────────────────────────────────────────────────────────────
Interactive 15-Question Quickfire Duel Engine between Study Partners.
- Exactly 15 questions per duel, 15 seconds per question countdown.
- Grounded in shared Study Packs (no mock questions).
- Asynchronous showdown: Challenger plays first, Partner completes identical paper.
- Side-by-side diagnostic slips, speed tie-breaking, and Nu-Coins rewards.

Mobile-first layout notes
- Dialog widths are derived from the live page width (no fixed 480/500/520px).
- Dialogs are scrollable and use tighter insets so nothing bleeds off-screen.
- Greys replaced with theme-aware colours (ON_SURFACE_VARIANT + primary tints).
- Larger tap targets, wrapping chips/badges, roomier spacing.
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
from src.components.nu_coin_icon import nu_coin_icon


# ──────────────────────────────────────────────────────────────────────────────
# Shared design helpers
# ──────────────────────────────────────────────────────────────────────────────

# Theme-aware muted text colour (adapts to light/dark, never a dead grey).
MUTED = ft.Colors.ON_SURFACE_VARIANT

OPTION_LETTERS = "ABCDEFGH"

# Session-wide tracking of completed challenges to prevent duplicate duel runs under network lag
_COMPLETED_CHALLENGE_IDS: set = set()


def mark_challenge_completed(challenge_id: str):
    if challenge_id:
        _COMPLETED_CHALLENGE_IDS.add(str(challenge_id))


def is_challenge_completed(challenge_id: str) -> bool:
    return bool(challenge_id and str(challenge_id) in _COMPLETED_CHALLENGE_IDS)


def _tint(opacity: float, color=ft.Colors.PRIMARY):
    return ft.Colors.with_opacity(opacity, color)


def _format_time(seconds: int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m}m {s:02d}s" if m > 0 else f"{s}s"


def _content_width(page: ft.Page, max_w: int = 520) -> int:
    """Dialog content width that always fits the screen (inset + padding aware)."""
    w = getattr(page, "width", None) or 0
    if not w:
        return max_w
    return max(240, min(max_w, int(w) - 72))


def _dialog_paddings() -> dict:
    """Tighter dialog chrome so content gets the room on small screens."""
    return dict(
        inset_padding=ft.Padding.symmetric(horizontal=16, vertical=24),
        title_padding=ft.Padding.only(left=20, right=12, top=18, bottom=6),
        content_padding=ft.Padding.symmetric(horizontal=20, vertical=8),
        actions_padding=ft.Padding.only(left=16, right=16, top=8, bottom=14),
        actions_alignment=ft.MainAxisAlignment.END,
        scrollable=True,
    )


def _title_row(icon, text: str, trailing: Optional[ft.Control] = None, size: int = 16) -> ft.Row:
    left = ft.Row(
        spacing=10,
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Icon(icon, color=ft.Colors.PRIMARY, size=24),
            ft.Text(
                text,
                size=size,
                weight=ft.FontWeight.W_800,
                expand=True,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ],
    )
    controls = [left] + ([trailing] if trailing is not None else [])
    return ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=controls,
    )


def _pill(content: ft.Control, bgcolor, border_color=None) -> ft.Container:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=7),
        border_radius=ft.BorderRadius.all(20),
        bgcolor=bgcolor,
        border=ft.Border.all(1, border_color) if border_color else None,
        content=content,
    )


def _info_row(icon, text: str, icon_color=ft.Colors.PRIMARY) -> ft.Row:
    """Icon + wrapping text (text never overflows the dialog)."""
    return ft.Row(
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Icon(icon, size=18, color=icon_color),
            ft.Text(text, size=12.5, color=ft.Colors.ON_SURFACE, expand=True),
        ],
    )


def _score_card(
    label: str,
    score_control: ft.Control,
    time_control: ft.Control,
    is_me: bool,
    is_winner: bool,
) -> ft.Container:
    if is_winner:
        bg, bd, label_color = _tint(0.12, ft.Colors.GREEN), _tint(0.55, ft.Colors.GREEN), ft.Colors.GREEN_700
    elif is_me:
        bg, bd, label_color = _tint(0.08), _tint(0.28), ft.Colors.PRIMARY
    else:
        bg, bd, label_color = _tint(0.04, ft.Colors.SECONDARY), _tint(0.20, ft.Colors.SECONDARY), ft.Colors.SECONDARY

    header = [
        ft.Text(
            label,
            size=12.5,
            weight=ft.FontWeight.W_700,
            color=label_color,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            text_align=ft.TextAlign.CENTER,
        )
    ]
    if is_winner:
        header.insert(0, ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, size=16, color=ft.Colors.AMBER_700))

    return ft.Container(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=10, vertical=16),
        border_radius=ft.BorderRadius.all(16),
        bgcolor=bg,
        border=ft.Border.all(1.5 if is_winner else 1, bd),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
            tight=True,
            controls=[
                ft.Row(header, alignment=ft.MainAxisAlignment.CENTER, spacing=4, tight=True),
                score_control,
                time_control,
            ],
        ),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Duel results
# ──────────────────────────────────────────────────────────────────────────────

def show_duel_results_dialog(
    page: ft.Page,
    challenge: dict,
    current_user_id: str,
    token: Optional[str] = None,
    partnership_id: Optional[str] = None,
    on_duel_updated: Optional[Callable] = None,
):
    """
    Renders a side-by-side comparison dialog for a completed or in-progress duel.
    If the current user is challenged and hasn't played yet, offers a button to play now.
    """
    c_id = challenge.get("id")
    status = challenge.get("status")
    winner_id = challenge.get("winner_id")
    total_q = challenge.get("total_questions", 15)
    coins_awarded = challenge.get("coins_awarded", 0)
    wager_val = int(challenge.get("wager_amount") or 0)

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

    if is_challenge_completed(str(c_id)):
        needs_my_response = False
    else:
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
    i_won = False
    partner_won = False
    is_completed = (status == "completed") or (winner_id is not None) or (my_score_val is not None and partner_score_val is not None and not needs_my_response)
    if is_completed:
        if not winner_id or winner_id == "tie":
            outcome_title = "🤝 It's a Tie!"
            if wager_val > 0:
                outcome_subtitle = f"Both learners scored equally! Stake of {wager_val} Nu-Coins refunded to each."
            else:
                outcome_subtitle = "Both learners scored equally! Outstanding academic effort."
            banner_color = ft.Colors.AMBER_800
            banner_tint = ft.Colors.AMBER
        elif str(winner_id) == my_user_id:
            i_won = True
            outcome_title = "🏆 Victory!"
            if wager_val > 0:
                payout = coins_awarded if coins_awarded else int(wager_val * 2 * 0.9)
                outcome_subtitle = f"You won the {wager_val}-Coin Wager Duel against {partner_label}! +{payout} Nu-Coins pot claimed."
            else:
                outcome_subtitle = f"You won the Quickfire Duel against {partner_label}! Excellent mastery."
            banner_color = ft.Colors.GREEN_700
            banner_tint = ft.Colors.GREEN
        else:
            partner_won = True
            outcome_title = "⚔️ Good Battle!"
            if wager_val > 0:
                outcome_subtitle = f"{partner_label} won this round and claimed the pot. Challenge them again to win it back!"
            else:
                outcome_subtitle = f"{partner_label} won this round! Great study practice for upcoming exams."
            banner_color = ft.Colors.BLUE_700
            banner_tint = ft.Colors.BLUE
    elif needs_my_response:
        if wager_val > 0:
            outcome_title = "⚔️ Wager Duel Awaiting You!"
            pot_total = int(wager_val * 2 * 0.9)
            outcome_subtitle = f"{partner_label} staked {wager_val} Nu-Coins! Matching stake of {wager_val} coins required. Winner takes {pot_total} Nu-Coins!"
        else:
            outcome_title = "⚔️ Duel Challenge Awaiting You!"
            outcome_subtitle = f"{partner_label} completed 15 questions! Beat their score in 15 seconds per question."
        banner_color = ft.Colors.ORANGE_800
        banner_tint = ft.Colors.ORANGE
    else:
        if wager_val > 0:
            outcome_title = "⏳ Wager Duel Pending Partner"
            outcome_subtitle = f"You scored {my_score_val}/{total_q} with {wager_val} coins staked. {partner_label} has been alerted to match your wager."
        else:
            outcome_title = "⏳ Duel Pending Partner Response"
            outcome_subtitle = f"You scored {my_score_val}/{total_q}. {partner_label} has been alerted via push notification."
        banner_color = ft.Colors.TEAL_700
        banner_tint = ft.Colors.TEAL

    my_score_text = ft.Text(
        f"{my_score_val}/{total_q}" if my_score_val is not None else "Pending",
        size=30 if my_score_val is not None else 15,
        weight=ft.FontWeight.W_900 if my_score_val is not None else ft.FontWeight.W_600,
        color=ft.Colors.ON_SURFACE if my_score_val is not None else ft.Colors.ORANGE_700,
    )
    my_time_text = ft.Text(
        f"⏱ {_format_time(my_time_val or 0)}" if my_time_val is not None else "Not played",
        size=12,
        color=MUTED,
    )
    partner_score_text = ft.Text(
        f"{partner_score_val}/{total_q}" if partner_score_val is not None else "Pending",
        size=30 if partner_score_val is not None else 15,
        weight=ft.FontWeight.W_900 if partner_score_val is not None else ft.FontWeight.W_600,
        color=ft.Colors.ON_SURFACE if partner_score_val is not None else ft.Colors.ORANGE_700,
    )
    partner_time_text = ft.Text(
        f"⏱ {_format_time(partner_time_val or 0)}" if partner_time_val is not None else "Awaiting run…",
        size=12,
        color=MUTED,
    )

    pot_display = coins_awarded if coins_awarded else int(wager_val * 2 * 0.9)

    # Format badges (wrap instead of squeezing into a ResponsiveRow)
    format_badge = _pill(
        ft.Text(f"⚡ {total_q} Questions • 15s each", size=11.5, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
        bgcolor=_tint(0.08),
    )
    if wager_val > 0:
        stake_badge = _pill(
            ft.Row(
                tight=True,
                spacing=6,
                controls=[
                    nu_coin_icon(size=14),
                    ft.Text(f"Stake {wager_val} • Pot {pot_display}", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_900),
                ],
            ),
            bgcolor=_tint(0.12, ft.Colors.AMBER),
            border_color=_tint(0.35, ft.Colors.AMBER_700),
        )
    else:
        stake_badge = _pill(
            ft.Text("Casual • 0 Coins", size=11.5, weight=ft.FontWeight.W_600, color=MUTED),
            bgcolor=_tint(0.06, ft.Colors.SECONDARY),
        )

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=24),
        bgcolor=ft.Colors.SURFACE,
        title=_title_row(
            ft.Icons.MILITARY_TECH_ROUNDED,
            "Duel Result",
            trailing=ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=20, on_click=lambda _: _close()),
        ),
        content=ft.Container(
            width=_content_width(page, 480),
            content=ft.Column(
                tight=True,
                spacing=18,
                controls=[
                    # Outcome banner
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                        border_radius=ft.BorderRadius.all(14),
                        bgcolor=_tint(0.10, banner_tint),
                        border=ft.Border.all(1, _tint(0.30, banner_tint)),
                        content=ft.Column(
                            tight=True,
                            spacing=5,
                            controls=[
                                ft.Text(outcome_title, size=16, weight=ft.FontWeight.W_800, color=banner_color),
                                ft.Text(outcome_subtitle, size=12.5, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                    ),
                    # Side-by-side score comparison
                    ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            _score_card("You", my_score_text, my_time_text, is_me=True, is_winner=i_won),
                            _score_card(partner_label, partner_score_text, partner_time_text, is_me=False, is_winner=partner_won),
                        ],
                    ),
                    # Format badges
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        wrap=True,
                        spacing=8,
                        run_spacing=8,
                        controls=[format_badge, stake_badge],
                    ),
                ],
            ),
        ),
        actions=[
            ft.TextButton("Close", on_click=lambda _: _close()),
        ],
        **_dialog_paddings(),
    )

    def _close():
        dlg.open = False
        page.update()

    if needs_my_response and token and partnership_id:
        is_accepting = False
        def _start_accept_duel(e=None):
            nonlocal is_accepting
            if is_accepting or is_challenge_completed(str(c_id)):
                return
            is_accepting = True
            mark_challenge_completed(str(c_id))
            if wager_val > 0:
                user_coins = int(user_data.get("coins_balance") or 0)
                if user_coins < wager_val:
                    is_accepting = False
                    _COMPLETED_CHALLENGE_IDS.discard(str(c_id))
                    show_page_snackbar(page, f"Insufficient Nu-Coins to match {wager_val}-coin wager. You have {user_coins} coins. Top up in the Store.")
                    return
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
                    wager_amount=wager_val,
                )
            page.run_task(_launch)

        play_label = f"Match {wager_val} & Play" if wager_val > 0 else "Play Duel Now"
        dlg.actions.insert(0, ft.ElevatedButton(
            content=ft.Row(
                tight=True,
                spacing=6,
                controls=[
                    nu_coin_icon(size=15) if wager_val > 0 else ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=17, color=ft.Colors.WHITE),
                    ft.Text(play_label, size=13, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                ],
            ),
            bgcolor=ft.Colors.AMBER_800 if wager_val > 0 else ft.Colors.PRIMARY,
            height=42,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), elevation=0),
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
                        partner_score_text.size = 30
                        partner_score_text.weight = ft.FontWeight.W_900
                        partner_score_text.color = ft.Colors.ON_SURFACE
                        partner_time_text.value = f"⏱ {_format_time(live_p_t or 0)}"
                        page.update()
            except Exception:
                pass
        page.run_task(_refresh_live_duel)


# ──────────────────────────────────────────────────────────────────────────────
# Live duel runner
# ──────────────────────────────────────────────────────────────────────────────

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
    wager_amount: int = 0,
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
    q_progress_text = ft.Text(f"Question 1 of {total_q}", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY)
    timer_text = ft.Text("⏱ 15s", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_900)
    timer_pill = _pill(timer_text, bgcolor=_tint(0.14, ft.Colors.AMBER))
    timer_progress = ft.ProgressBar(
        value=1.0,
        color=ft.Colors.AMBER_700,
        bgcolor=_tint(0.15, ft.Colors.AMBER),
        height=6,
        border_radius=ft.BorderRadius.all(4),
    )
    question_md = ft.Markdown(
        "",
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        md_style_sheet=ft.MarkdownStyleSheet(
            p_text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE, height=1.4),
            code_text_style=ft.TextStyle(size=13.5, bgcolor=_tint(0.10)),
        ),
    )
    options_column = ft.Column(spacing=10, tight=True)
    status_msg = ft.Text("", size=12.5, weight=ft.FontWeight.W_700, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS)

    sub_label = f"Stake: {wager_amount} coins" if wager_amount > 0 else "⚡ 15s per question"

    duel_dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=24),
        bgcolor=ft.Colors.SURFACE,
        title=_title_row(
            ft.Icons.FLASH_ON_ROUNDED,
            "Quickfire Duel",
            trailing=timer_pill,
        ),
        content=ft.Container(
            width=_content_width(page, 500),
            content=ft.Column(
                tight=True,
                spacing=14,
                controls=[
                    timer_progress,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            q_progress_text,
                            ft.Text(sub_label, size=11.5, weight=ft.FontWeight.W_600, color=MUTED),
                        ],
                    ),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=16, vertical=16),
                        border_radius=ft.BorderRadius.all(16),
                        bgcolor=_tint(0.06),
                        border=ft.Border.all(1, _tint(0.16)),
                        content=question_md,
                    ),
                    options_column,
                    ft.Container(height=36, alignment=ft.Alignment.CENTER_LEFT, content=status_msg),
                ],
            ),
        ),
        actions=[],
        **_dialog_paddings(),
    )

    def _safe_current_task():
        try:
            return asyncio.current_task()
        except RuntimeError:
            return None

    def _close_duel():
        nonlocal active_timer_task
        curr_task = _safe_current_task()
        if active_timer_task and active_timer_task != curr_task and not active_timer_task.done():
            active_timer_task.cancel()
        duel_dlg.open = False
        page.update()

    def _style_timer(low: bool):
        if low:
            timer_text.color = ft.Colors.RED_700
            timer_pill.bgcolor = _tint(0.14, ft.Colors.RED)
            timer_progress.color = ft.Colors.RED_600
            timer_progress.bgcolor = _tint(0.15, ft.Colors.RED)
        else:
            timer_text.color = ft.Colors.AMBER_900
            timer_pill.bgcolor = _tint(0.14, ft.Colors.AMBER)
            timer_progress.color = ft.Colors.AMBER_700
            timer_progress.bgcolor = _tint(0.15, ft.Colors.AMBER)

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
            _style_timer(question_seconds_left <= 4)
            page.update()

        if question_seconds_left <= 0 and not answered_current and duel_dlg.open:
            asyncio.create_task(_handle_answer(None, is_timeout=True))

    def _render_question():
        nonlocal current_idx, question_seconds_left, answered_current, active_timer_task
        answered_current = False
        question_seconds_left = 15
        timer_text.value = "⏱ 15s"
        timer_progress.value = 1.0
        _style_timer(False)
        status_msg.value = ""

        q_data = questions[current_idx]
        q_text = q_data.get("question") or q_data.get("question_text") or f"Question {current_idx+1}"
        options = q_data.get("options") or ["Option A", "Option B", "Option C", "Option D"]
        correct_answer = q_data.get("correct_answer") or q_data.get("answer") or options[0]

        q_progress_text.value = f"Question {current_idx+1} of {total_q}"
        question_md.value = q_text

        options_column.controls.clear()
        for i, opt in enumerate(options):
            btn = _build_option_btn(opt, correct_answer, OPTION_LETTERS[i % len(OPTION_LETTERS)])
            options_column.controls.append(btn)

        page.update()

        # Start 15s timer for this question
        curr_task = _safe_current_task()
        if active_timer_task and active_timer_task != curr_task and not active_timer_task.done():
            active_timer_task.cancel()
        try:
            loop = asyncio.get_running_loop()
            active_timer_task = loop.create_task(_run_countdown())
        except RuntimeError:
            active_timer_task = None

    def _build_option_btn(opt_text: str, correct_answer: str, letter: str) -> ft.Container:
        badge = ft.Container(
            width=28,
            height=28,
            border_radius=ft.BorderRadius.all(14),
            bgcolor=_tint(0.12),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(letter, size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
        )
        opt_container = ft.Container(
            data=opt_text,
            padding=ft.Padding.symmetric(horizontal=14, vertical=14),
            border_radius=ft.BorderRadius.all(14),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1.5, _tint(0.22)),
            ink=True,
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    badge,
                    ft.Container(
                        expand=True,
                        content=ft.Markdown(
                            opt_text,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                            md_style_sheet=ft.MarkdownStyleSheet(
                                p_text_style=ft.TextStyle(size=14, color=ft.Colors.ON_SURFACE, height=1.3),
                                code_text_style=ft.TextStyle(size=12.5, bgcolor=_tint(0.10)),
                            ),
                        ),
                    ),
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
        curr_task = _safe_current_task()
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
            status_msg.color = ft.Colors.RED_700
        else:
            status_msg.value = f"✗ Incorrect. Correct answer: {q_data.get('correct_answer')}"
            status_msg.color = ft.Colors.RED_700

        # Highlight options
        for c in options_column.controls:
            c.ink = False
            c.on_click = None
            opt_row = c.content
            badge = opt_row.controls[0]
            txt = getattr(c, "data", None) or ""
            if str(txt).strip().lower() == correct_answer:
                c.bgcolor = _tint(0.14, ft.Colors.GREEN)
                c.border = ft.Border.all(2, ft.Colors.GREEN_600)
                badge.bgcolor = ft.Colors.GREEN_600
                badge.content = ft.Icon(ft.Icons.CHECK_ROUNDED, size=17, color=ft.Colors.WHITE)
            elif selected_opt and str(txt).strip().lower() == str(selected_opt).strip().lower() and not is_correct:
                c.bgcolor = _tint(0.14, ft.Colors.RED)
                c.border = ft.Border.all(2, ft.Colors.RED_600)
                badge.bgcolor = ft.Colors.RED_600
                badge.content = ft.Icon(ft.Icons.CLOSE_ROUNDED, size=17, color=ft.Colors.WHITE)
            else:
                c.opacity = 0.55

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

        _is_finishing = False
        async def _finish_duel():
            nonlocal _is_finishing, active_timer_task
            if _is_finishing:
                return
            _is_finishing = True

            curr_task = _safe_current_task()
            if active_timer_task and active_timer_task != curr_task and not active_timer_task.done():
                active_timer_task.cancel()

            if is_accepting_challenge and challenge_id:
                mark_challenge_completed(str(challenge_id))

            # Immediately trigger on_completed to hide the duel banner from dashboard behind the modal!
            if on_completed:
                try:
                    on_completed()
                except Exception:
                    pass

            # Transition duel dialog to a Submitting state (locks UI and prevents spam tapping dashboard)
            duel_dlg.title = _title_row(ft.Icons.SPORTS_ESPORTS_ROUNDED, "Submitting Duel...", size=16)
            duel_dlg.content = ft.Container(
                width=_content_width(page, 440),
                padding=ft.Padding.symmetric(vertical=24, horizontal=16),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.ProgressRing(width=36, height=36, stroke_width=3, color=ft.Colors.PRIMARY),
                        ft.Text(f"Completed {score} of {total_q} questions!", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                        ft.Text("Resolving winner & synchronizing study scores...", size=12.5, color=MUTED, text_align=ft.TextAlign.CENTER),
                    ],
                ),
            )
            duel_dlg.actions = []
            page.update()

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
                    _close_duel()
                    if res and not res.get("error"):
                        show_page_snackbar(page, f"Duel submitted! {res.get('message', 'Completed!')} 🏆")
                        if on_completed:
                            try:
                                on_completed()
                            except Exception:
                                pass

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
                        wager_amount=wager_amount,
                    )
                    _close_duel()
                    if res and not res.get("error"):
                        show_page_snackbar(page, f"15-Q Duel submitted! {partner_name} has been notified to match and beat your score 🔥")
                        if on_completed:
                            try:
                                on_completed()
                            except Exception:
                                pass
                    else:
                        show_page_snackbar(page, res.get("error", "Failed to create duel challenge."))
            except Exception as ex:
                _close_duel()
                show_page_snackbar(page, f"Duel error: {ex}")

    page.overlay.append(duel_dlg)
    duel_dlg.open = True
    page.update()

    _render_question()


# ──────────────────────────────────────────────────────────────────────────────
# Create duel
# ──────────────────────────────────────────────────────────────────────────────

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

    def _make_option(m_id: str, m_title: str, label_txt: str) -> ft.dropdown.Option:
        return ft.dropdown.Option(
            key=m_id,
            text=m_title,
            content=ft.Text(
                label_txt,
                size=13.5,
                weight=ft.FontWeight.W_600,
                color=ft.Colors.ON_SURFACE,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        )

    pack_options = []
    for m in (available_materials or []):
        m_id = str(m.get("id") or m.get("pack_id"))
        m_title = str(m.get("title", "Untitled"))[:38]
        q_count = m.get("questions_count")
        if q_count is None and isinstance(m.get("pack_data"), dict):
            q_count = len(m["pack_data"].get("questions", []))
        label_txt = f"{m_title[:32]} ({q_count}Q)" if q_count else m_title
        pack_options.append(_make_option(m_id, m_title, label_txt))

    if not pack_options:
        pack_options.append(_make_option("general", "General Academic Pack", "General Academic Pack"))

    pack_dd = ft.Dropdown(
        label="Study pack",
        value=pack_options[0].key if pack_options else None,
        options=pack_options,
        border_radius=12,
        dense=True,
        text_size=14,
        color=ft.Colors.ON_SURFACE,
        bgcolor=ft.Colors.SURFACE,
        fill_color=_tint(0.05),
        filled=True,
        border_color=_tint(0.25),
        focused_border_color=ft.Colors.PRIMARY,
        menu_height=240,  # compact, scrollable dropdown popup menu
        menu_style=ft.MenuStyle(
            bgcolor=ft.Colors.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=12),
            side=ft.BorderSide(1, _tint(0.25)),
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
                new_options.append(_make_option(m_id, m_title, label_txt))

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
                ft.Text("Start Duel", size=14, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
            ],
        ),
        bgcolor=ft.Colors.PRIMARY,
        height=46,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), elevation=0),
    )

    # ── Wager / Stake State ──
    selected_wager = [0]
    user_coins_box = [0]
    u_data = page.session.store.get("current_user") or {} if hasattr(page, "session") and hasattr(page.session, "store") else {}
    user_coins_box[0] = int(u_data.get("coins_balance") or 0)

    wager_chips_row = ft.Row(spacing=8, run_spacing=8, wrap=True)
    pot_summary_text = ft.Text(
        "Casual showdown: no stakes, just practice.",
        size=12,
        weight=ft.FontWeight.W_600,
        color=MUTED,
    )
    wallet_info_text = ft.Text(f"{user_coins_box[0]}", size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE)

    WAGER_OPTIONS = [
        (0, "Casual"),
        (10, "10"),
        (25, "25"),
        (50, "50"),
        (100, "100"),
    ]

    def _select_wager(val: int):
        selected_wager[0] = val
        if val == 0:
            pot_summary_text.value = "Casual showdown: no stakes, just practice."
            pot_summary_text.color = MUTED
            launch_btn.disabled = False
        else:
            pot = val * 2
            burn = int(pot * 0.10)
            payout = pot - burn
            if user_coins_box[0] < val:
                pot_summary_text.value = f"⚠️ Insufficient Nu-Coins. You need {val} coins to stake. Top up in the Store or choose Casual."
                pot_summary_text.color = ft.Colors.RED_700
                launch_btn.disabled = True
            else:
                pot_summary_text.value = f"⚔️ Pot: {pot} Nu-Coins • Winner takes {payout} (10% platform burn). Draws refund both."
                pot_summary_text.color = ft.Colors.AMBER_900
                launch_btn.disabled = False
        _render_wager_chips()
        page.update()

    def _render_wager_chips():
        wager_chips_row.controls.clear()
        for w_val, w_lbl in WAGER_OPTIONS:
            is_selected = (selected_wager[0] == w_val)
            chip = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.PRIMARY if is_selected else ft.Colors.SURFACE,
                border=ft.Border.all(1.5, ft.Colors.PRIMARY if is_selected else _tint(0.25)),
                ink=True,
                on_click=(lambda v=w_val: lambda _: _select_wager(v))(),
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        nu_coin_icon(size=15) if w_val > 0 else ft.Icon(ft.Icons.SPORTS_ESPORTS_ROUNDED, size=15, color=ft.Colors.WHITE if is_selected else ft.Colors.PRIMARY),
                        ft.Text(
                            w_lbl,
                            size=13,
                            weight=ft.FontWeight.W_800 if is_selected else ft.FontWeight.W_600,
                            color=ft.Colors.WHITE if is_selected else ft.Colors.ON_SURFACE,
                        ),
                    ],
                ),
            )
            wager_chips_row.controls.append(chip)

    _render_wager_chips()

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

            wager_val = selected_wager[0]
            if wager_val > 0 and user_coins_box[0] < wager_val:
                show_page_snackbar(page, f"Insufficient Nu-Coins for {wager_val}-coin stake. Top up in Store.")
                return

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
                wager_amount=wager_val,
            )

        except Exception as ex:
            show_page_snackbar(page, f"Error launching duel: {ex}")
        finally:
            launch_btn.disabled = bool(selected_wager[0] > 0 and user_coins_box[0] < selected_wager[0])
            progress_ring.visible = False
            page.update()

    launch_btn.on_click = lambda _: page.run_task(_handle_launch)

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=24),
        bgcolor=ft.Colors.SURFACE,
        title=_title_row(
            ft.Icons.SPORTS_ESPORTS_ROUNDED,
            "Quickfire Duel",
            trailing=ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=20, on_click=lambda _: _close()),
        ),
        content=ft.Container(
            width=_content_width(page, 520),
            content=ft.Column(
                tight=True,
                spacing=16,
                controls=[
                    # How it works
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                        border_radius=ft.BorderRadius.all(14),
                        bgcolor=_tint(0.06),
                        border=ft.Border.all(1, _tint(0.16)),
                        content=ft.Column(
                            spacing=10,
                            tight=True,
                            controls=[
                                _info_row(ft.Icons.BOLT_ROUNDED, "15 questions • 15 seconds each"),
                                _info_row(ft.Icons.SYNC_ALT_ROUNDED, f"{p_name} gets the exact same questions"),
                                _info_row(ft.Icons.EMOJI_EVENTS_ROUNDED, "Winner claims the pot (draws refund both)", icon_color=ft.Colors.AMBER_700),
                            ],
                        ),
                    ),
                    pack_dd,
                    # Wager / Stake Selection Box
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=14, vertical=14),
                        border_radius=ft.BorderRadius.all(14),
                        bgcolor=_tint(0.07, ft.Colors.AMBER),
                        border=ft.Border.all(1, _tint(0.30, ft.Colors.AMBER_700)),
                        content=ft.Column(
                            spacing=12,
                            tight=True,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Text("Stake", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.AMBER_900),
                                        _pill(
                                            ft.Row(
                                                [nu_coin_icon(size=14), wallet_info_text],
                                                spacing=5,
                                                tight=True,
                                            ),
                                            bgcolor=_tint(0.12, ft.Colors.AMBER),
                                        ),
                                    ],
                                ),
                                wager_chips_row,
                                pot_summary_text,
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
        **_dialog_paddings(),
    )

    def _close():
        dlg.open = False
        page.update()

    page.overlay.append(dlg)
    dlg.open = True
    page.update()
    page.run_task(_fetch_and_populate_packs)


# ──────────────────────────────────────────────────────────────────────────────
# Flashcard preview
# ──────────────────────────────────────────────────────────────────────────────

def show_flashcard_preview_dialog(
    page: ft.Page,
    token: str,
    partnership_id: str,
    pack_id: str,
    pack_title: str,
    partner_name: str,
    flashcards: list,
    on_duel_start: Optional[Callable] = None,
    duel_action_label: Optional[str] = None,
    on_action_click: Optional[Callable] = None,
):
    """
    Renders a flashcard-only preview dialog for a shared study pack.
    Questions are strictly withheld to preserve competition integrity.
    Provides a direct CTA to launch a 15-Question Quickfire Duel or perform custom duel action.
    """
    card_idx = 0
    total_cards = len(flashcards)
    showing_front = True

    index_text = ft.Text(
        f"Card 1 of {total_cards}" if total_cards else "No cards",
        size=13,
        weight=ft.FontWeight.W_700,
        color=MUTED,
    )
    deck_progress = ft.ProgressBar(
        value=(card_idx + 1) / total_cards if total_cards else 1.0,
        color=ft.Colors.PRIMARY,
        bgcolor=_tint(0.12),
        height=6,
        border_radius=ft.BorderRadius.all(4),
    )
    card_type_label = ft.Text("FRONT", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY)
    card_type_tag = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=ft.BorderRadius.all(8),
        bgcolor=_tint(0.12),
        content=card_type_label,
    )

    init_card_val = flashcards[0].get("front", "Empty") if total_cards else "No flashcards in this deck."
    card_md = ft.Markdown(
        value=init_card_val,
        selectable=False,
        extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
        md_style_sheet=ft.MarkdownStyleSheet(
            text_alignment=ft.TextAlign.CENTER,
            p_text_style=ft.TextStyle(
                size=16,
                weight=ft.FontWeight.W_600,
                color=ft.Colors.ON_SURFACE,
                height=1.45,
            ),
        ),
    )

    card_box = ft.Container(
        height=230,
        padding=ft.Padding.symmetric(horizontal=18, vertical=16),
        border_radius=ft.BorderRadius.all(20),
        bgcolor=_tint(0.06),
        border=ft.Border.all(1.5, _tint(0.25)),
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
        deck_progress.value = (card_idx + 1) / total_cards if total_cards else 1.0
        if showing_front:
            card_type_label.value = "FRONT"
            card_type_label.color = ft.Colors.PRIMARY
            card_type_tag.bgcolor = _tint(0.12)
            card_md.value = curr.get("front") or curr.get("prompt") or curr.get("term") or "No front text"
            card_box.bgcolor = _tint(0.06)
            card_box.border = ft.Border.all(1.5, _tint(0.25))
        else:
            card_type_label.value = "ANSWER"
            card_type_label.color = ft.Colors.GREEN_700
            card_type_tag.bgcolor = _tint(0.14, ft.Colors.GREEN)
            card_md.value = curr.get("back") or curr.get("answer") or curr.get("definition") or "No back text"
            card_box.bgcolor = _tint(0.07, ft.Colors.GREEN)
            card_box.border = ft.Border.all(1.5, _tint(0.40, ft.Colors.GREEN))
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

    nav_style = ft.ButtonStyle(bgcolor=_tint(0.10), shape=ft.CircleBorder())
    prev_btn = ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED, icon_size=18, icon_color=ft.Colors.PRIMARY, style=nav_style, on_click=_prev_card)
    next_btn = ft.IconButton(ft.Icons.ARROW_FORWARD_IOS_ROUNDED, icon_size=18, icon_color=ft.Colors.PRIMARY, style=nav_style, on_click=_next_card)

    dlg_ref = [None]

    def _close(e=None):
        if dlg_ref[0]:
            dlg_ref[0].open = False
            page.update()

    async def _start_duel_from_preview():
        _close()
        if on_action_click:
            res = on_action_click()
            if asyncio.iscoroutine(res):
                await res
            return
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

    action_label = duel_action_label or "Challenge on this pack"
    action_icon = ft.Icons.PLAY_ARROW_ROUNDED if on_action_click else ft.Icons.FLASH_ON_ROUNDED

    duel_cta = ft.ElevatedButton(
        content=ft.Row(
            tight=True,
            spacing=6,
            controls=[
                ft.Icon(action_icon, size=17, color=ft.Colors.WHITE),
                ft.Text(action_label, size=13, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
            ],
        ),
        bgcolor=ft.Colors.ORANGE_800,
        height=42,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), elevation=0),
        on_click=lambda _: page.run_task(_start_duel_from_preview),
    )

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=24),
        bgcolor=ft.Colors.SURFACE,
        title=_title_row(
            ft.Icons.STYLE_ROUNDED,
            "Flashcard Preview",
            trailing=ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=20, on_click=_close),
        ),
        content=ft.Container(
            width=_content_width(page, 500),
            content=ft.Column(
                tight=True,
                spacing=14,
                controls=[
                    deck_progress,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[index_text, card_type_tag],
                    ),
                    card_box,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=18,
                        controls=[
                            prev_btn,
                            ft.TextButton("Tap card to flip", icon=ft.Icons.FLIP_ROUNDED, on_click=_flip),
                            next_btn,
                        ],
                    ),
                ],
            ),
        ),
        actions=[
            ft.TextButton("Close", on_click=_close),
            duel_cta,
        ],
        **_dialog_paddings(),
    )

    dlg_ref[0] = dlg
    page.overlay.append(dlg)
    dlg.open = True
    page.update()