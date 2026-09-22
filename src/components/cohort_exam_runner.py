"""
Candidate Exam Runner for Cohort Assessments with Enterprise Anti-Cheat Security:
  * Pre-Exam Briefing & Rules screen before the timer begins.
  * Server-synced sticky countdown timer with auto-submit on expiry.
  * Anti-Cheat Focus & Lifecycle Watcher:
    - Android/iOS app lifecycle change detection (inactive, paused, hidden) with strike cooldown debouncing.
    - Desktop/Web window blur and focus loss detection.
    - Security policy: Strict (auto-submit on first breach), Monitored (warning strikes), Relaxed (practice).
  * Kiosk / Fullscreen enforcement with clean release.
  * Hardware & Software back navigation trapping.
  * DevTools and copy-paste suppression.
  * Session token binding and server-authoritative submission.
  * Fast question palette jump strip, dynamic button states, and support for delayed result notes.
"""

import asyncio
from datetime import datetime, timezone
import time
from typing import Optional
import flet as ft
from src.components import study_ui as ui
from src.components.exam_calculator import build_exam_calculator
from src.requests.Cohorts import submit_cohort_exam

_LETTERS = ["A", "B", "C", "D", "E", "F"]


def build_cohort_exam_view(
    page: ft.Page,
    exam_payload: dict,
    org_id: str,
    cohort_id: str,
    exam_id: str,
    token: str,
    on_exit,
):
    questions = exam_payload.get("questions", [])
    total = len(questions)
    title = exam_payload.get("exam_title", "Cohort Assessment")
    duration_remaining = exam_payload.get("remaining_seconds", 3600)
    total_duration_sec = exam_payload.get("total_duration_seconds") or duration_remaining
    instructions = exam_payload.get("instructions")
    security_mode = exam_payload.get("security_mode", "monitored")  # strict, monitored, relaxed
    max_violations = int(exam_payload.get("max_violations", 2))
    session_token = exam_payload.get("session_token")
    pass_mark = exam_payload.get("pass_percentage", 70.0)
    calculator_type = exam_payload.get("calculator_type", "none")  # none, basic, scientific
    show_immediate_results = exam_payload.get("show_immediate_results", False)

    if total == 0:
        return ui.empty_state(
            ft.Icons.ASSIGNMENT_OUTLINED,
            "No exam questions found",
            "This assessment does not have any questions configured yet.",
            "Return to Hub",
            on_exit,
        )

    state = {
        "index": 0,
        "answers": {},       # index -> chosen option index
        "flags": set(),      # set of question indices flagged
        "running": False,
        "started_assessment": False,
        "submitted": False,
        "started": time.time(),
        "remaining": max(10, int(duration_remaining)),
        "violations_count": 0,
        "violation_log": [],
        "violation_dialog_open": False,
        "in_review": False,
    }

    last_violation_ts = [0.0]
    root = ft.Container(expand=True)

    # ── Fullscreen & Kiosk Activation ────────────────────────────────────
    win = getattr(page, "window", None)
    prev_prevent_close = getattr(win, "prevent_close", False) if win else False

    def apply_security_locks():
        try:
            w = getattr(page, "window", None)
            if w:
                w.prevent_close = True
                w.full_screen = True
                w.on_event = on_window_event
            page.on_keyboard_event = on_key_event
            page.on_app_lifecycle_state_change = on_lifecycle_change
            page.update()
        except Exception:
            pass

    def release_security_locks():
        try:
            w = getattr(page, "window", None)
            if w:
                w.prevent_close = prev_prevent_close
                w.full_screen = False
                w.on_event = None
            page.on_keyboard_event = None
            page.on_app_lifecycle_state_change = None
            page.update()
        except Exception:
            pass

    def safe_exit(e=None):
        release_security_locks()
        if on_exit and callable(on_exit):
            try:
                on_exit(e)
            except TypeError:
                on_exit()

    # ── Strike Badges & Telemetry ────────────────────────────────────────
    sidebar_strike_icon = ft.Icon(ft.Icons.SECURITY_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT)
    sidebar_strike_text = ft.Text(
        f"Proctored · 0/{max_violations} Strikes" if security_mode == "monitored" else "Strict Security Active",
        size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT,
    )
    sidebar_strike_box = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
        content=ft.Row([sidebar_strike_icon, sidebar_strike_text], spacing=6, tight=True),
    )

    topbar_strike_icon = ft.Icon(ft.Icons.SECURITY_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    topbar_strike_text = ft.Text(
        f"0/{max_violations}" if security_mode == "monitored" else "Strict",
        size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT,
    )
    topbar_strike_box = ft.Container(
        padding=ft.Padding.symmetric(horizontal=6, vertical=3),
        border_radius=6,
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
        content=ft.Row([topbar_strike_icon, topbar_strike_text], spacing=3, tight=True),
    )

    def update_strike_badges_ui():
        cnt = state["violations_count"]
        strike_c = ft.Colors.RED_600 if cnt > 0 else ft.Colors.ON_SURFACE_VARIANT
        bg_c = ft.Colors.with_opacity(0.12 if cnt > 0 else 0.06, ft.Colors.RED_700 if cnt > 0 else ft.Colors.ON_SURFACE)
        border_c = ft.Colors.with_opacity(0.3 if cnt > 0 else 0.15, ft.Colors.RED_700 if cnt > 0 else ft.Colors.ON_SURFACE)

        sidebar_strike_icon.color = strike_c
        sidebar_strike_text.color = strike_c
        sidebar_strike_text.value = (
            f"Proctored · {cnt}/{max_violations} Strikes"
            if security_mode == "monitored"
            else ("Strict · 1 Incident Logged" if cnt > 0 else "Strict Security Active")
        )
        sidebar_strike_box.bgcolor = bg_c
        sidebar_strike_box.border = ft.Border.all(1, border_c)

        topbar_strike_icon.color = strike_c
        topbar_strike_text.color = strike_c
        topbar_strike_text.value = f"{cnt}/{max_violations}" if security_mode == "monitored" else ("1 Alert" if cnt > 0 else "Strict")
        topbar_strike_box.bgcolor = bg_c

    # ── Anti-Cheat Focus & Lifecycle Watcher ──────────────────────────────
    async def _submit_on_violation(reason: str):
        await execute_final_submit(is_violation=True, violation_reason=reason)

    def record_violation(v_type: str, details: str):
        if state["submitted"] or not state["running"] or security_mode == "relaxed":
            return
        if state["violation_dialog_open"]:
            return

        # Cooldown debounce: Ignore rapid cascading OS events within 3 seconds
        now_ts = time.time()
        if now_ts - last_violation_ts[0] < 3.0:
            return
        last_violation_ts[0] = now_ts

        now_str = datetime.now(timezone.utc).isoformat()
        state["violations_count"] += 1
        state["violation_log"].append({
            "timestamp": now_str,
            "type": v_type,
            "details": details,
            "strike": state["violations_count"],
        })

        update_strike_badges_ui()

        if security_mode == "strict":
            page.run_task(_submit_on_violation, f"Strict anti-cheat violation: {details}")
        else:
            if state["violations_count"] > max_violations:
                page.run_task(_submit_on_violation, f"Violation limit exceeded ({state['violations_count']}/{max_violations}): {details}")
            else:
                show_violation_warning(v_type, details)

    def show_violation_warning(v_type: str, details: str):
        if state["submitted"] or state["violation_dialog_open"]:
            return
        state["violation_dialog_open"] = True

        strikes_left = max(0, max_violations - state["violations_count"])
        subtext = (
            "This is your final warning. Any further focus loss, window switch, or restricted shortcut will immediately and permanently submit your assessment."
            if strikes_left == 0
            else f"You have {strikes_left} warning strike(s) remaining before your exam is automatically terminated and submitted."
        )

        warn_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.SECURITY_ROUNDED, color=ft.Colors.RED_600, size=24),
                ft.Text("SECURITY WARNING", color=ft.Colors.RED_700, weight=ft.FontWeight.BOLD, size=16),
            ], spacing=8),
            content=ft.Container(
                width=380,
                content=ft.Column([
                    ft.Text(f"Violation Incident {state['violations_count']} of {max_violations}",
                            weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.RED_700),
                    ft.Text(f"Event: {details}", size=12, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    ft.Text(
                        f"Navigating away, switching windows/apps, splitting screens, or exiting fullscreen is strictly prohibited. {subtext}",
                        size=12, color=ft.Colors.ON_SURFACE_VARIANT
                    ),
                ], tight=True, spacing=6),
            ),
            actions=[
                ft.FilledButton(
                    "I Understand & Resume Exam",
                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700),
                    on_click=lambda _: close_warn_dlg(warn_dlg),
                )
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        page.show_dialog(warn_dlg)

    def close_warn_dlg(dlg):
        state["violation_dialog_open"] = False
        last_violation_ts[0] = time.time()  # Grace period on resuming to prevent immediate bounce
        try:
            page.pop_dialog()
            w = getattr(page, "window", None)
            if w:
                w.full_screen = True
            page.update()
        except Exception:
            pass

    # 1. Mobile app lifecycle change listener
    def on_lifecycle_change(e):
        lifecycle_state = str(e.data).lower()
        if lifecycle_state in ("inactive", "paused", "hidden", "detached"):
            record_violation("app_lifecycle_unfocused", f"App transitioned to {lifecycle_state} (switched apps/split screen)")

    # 2. Desktop/web window blur & unmaximize listener
    def on_window_event(e):
        ev_name = str(e.data).lower()
        if any(term in ev_name for term in ("blur", "minimize", "unmaximize", "leavefullscreen", "hidden")):
            record_violation("window_blur", f"Window lost focus or exited fullscreen ({ev_name})")

    # 3. Keyboard devtools & copy-paste suppression
    def on_key_event(e: ft.KeyboardEvent):
        key = (e.key or "").lower()
        ctrl_or_cmd = bool(e.ctrl or e.meta)
        alt = bool(e.alt)

        if (
            (ctrl_or_cmd and key in ("c", "v", "x", "u", "p", "a", "s", "w", "t", "r", "n", "j", "i"))
            or (alt and key in ("tab", "f4", "left", "right"))
            or key in ("f12", "f11", "printscreen", "f5")
        ):
            prefix = "Ctrl+" if ctrl_or_cmd else ("Alt+" if alt else "")
            record_violation("prohibited_shortcut", f"Prohibited keyboard shortcut attempted: {prefix}{key.upper()}")

    # ── Exit Confirmation Dialog (Back Trap) ─────────────────────────────
    def confirm_leave_exam(e=None):
        leave_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.WARNING_ROUNDED, color=ft.Colors.AMBER_700, size=24),
                ft.Text("Exit Assessment?", weight=ft.FontWeight.BOLD, size=16),
            ], spacing=8),
            content=ft.Container(
                width=380,
                content=ft.Column([
                    ft.Text("Leaving now will automatically finalize and submit your assessment.", size=13, weight=ft.FontWeight.W_600),
                    ft.Text("All questions you have answered so far will be graded. This attempt cannot be resumed once exited.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], tight=True, spacing=6),
            ),
            actions=[
                ft.TextButton("Stay & Continue Exam", on_click=lambda _: page.pop_dialog()),
                ft.FilledButton(
                    "Submit & Exit Now",
                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700),
                    on_click=lambda _: page.run_task(do_submit_and_leave, leave_dlg),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        page.show_dialog(leave_dlg)

    async def do_submit_and_leave(leave_dlg):
        page.pop_dialog()
        await execute_final_submit(is_violation=False, violation_reason="Candidate voluntarily chose to submit and leave.")

    # ── Progress Bar & Timer ─────────────────────────────────────────────
    timer_text = ft.Text("00:00", size=15, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY)
    timer_icon = ft.Icon(ft.Icons.TIMER_ROUNDED, size=18, color=ft.Colors.PRIMARY)
    timer_bar = ft.ProgressBar(value=1.0, height=4, color=ft.Colors.PRIMARY, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY))
    q_counter = ft.Text(f"1 of {total}", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE)
    flag_btn = ft.OutlinedButton(
        content=ft.Row([ft.Icon(ft.Icons.FLAG_OUTLINED, size=15, color=ft.Colors.AMBER_700), ft.Text("Flag", size=12, weight=ft.FontWeight.W_600)], tight=True, spacing=4),
        style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=10, vertical=4)),
    )

    def _build_palette_legend():
        return ft.Row([
            ft.Row([
                ft.Container(width=8, height=8, border_radius=4, bgcolor=ft.Colors.GREEN_600),
                ft.Text("Answered", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=4, tight=True),
            ft.Row([
                ft.Container(width=8, height=8, border_radius=4, bgcolor=ft.Colors.AMBER_700),
                ft.Text("Flagged", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=4, tight=True),
            ft.Row([
                ft.Container(width=8, height=8, border_radius=4, border=ft.Border.all(1, ft.Colors.ON_SURFACE_VARIANT)),
                ft.Text("Unanswered", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=4, tight=True),
        ], spacing=10, wrap=True)

    # Question jumper row (for mobile horizontal scroll) and grid (for desktop sidebar)
    jump_strip_row = ft.Row(spacing=6, scroll=ft.ScrollMode.AUTO)
    jump_grid_sidebar = ft.Row(spacing=6, wrap=True, scroll=ft.ScrollMode.AUTO)

    def refresh_jump_strip():
        chips = []
        for i in range(total):
            is_curr = (i == state["index"])
            is_ans = (i in state["answers"])
            is_flg = (i in state["flags"])

            if is_curr:
                bg = ft.Colors.PRIMARY
                fg = ft.Colors.WHITE
                border_c = ft.Colors.PRIMARY
            elif is_flg:
                bg = ft.Colors.with_opacity(0.15, ft.Colors.AMBER_700)
                fg = ft.Colors.AMBER_800
                border_c = ft.Colors.AMBER_700
            elif is_ans:
                bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)
                fg = ft.Colors.GREEN_800
                border_c = ft.Colors.GREEN_600
            else:
                bg = ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE)
                fg = ft.Colors.ON_SURFACE_VARIANT
                border_c = ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)

            def make_jump(target_i):
                return lambda _: jump_to_q(target_i)

            chips.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=8,
                    bgcolor=bg,
                    border=ft.Border.all(1.5 if is_curr else 1, border_c),
                    ink=True,
                    on_click=make_jump(i),
                    content=ft.Text(f"{i + 1}", size=11, weight=ft.FontWeight.BOLD if (is_curr or is_ans) else ft.FontWeight.NORMAL, color=fg),
                )
            )
        jump_strip_row.controls = list(chips)
        jump_grid_sidebar.controls = list(chips)

    def jump_to_q(target_i: int):
        state["in_review"] = False
        state["index"] = target_i
        render_current_question()
        page.update()

    def format_time(seconds: int) -> str:
        mins, secs = divmod(max(0, seconds), 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            return f"{hrs:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    # ── Question Rendering ───────────────────────────────────────────────
    question_content_area = ft.Container(expand=True)
    prev_btn_ref = [None]
    next_btn_ref = [None]

    def render_current_question():
        idx = state["index"]
        q = questions[idx]
        q_counter.value = f"{idx + 1} of {total}"

        is_flagged = idx in state["flags"]
        flag_btn.content = ft.Row([
            ft.Icon(ft.Icons.FLAG_ROUNDED if is_flagged else ft.Icons.FLAG_OUTLINED,
                    size=15, color=ft.Colors.AMBER_700 if is_flagged else ft.Colors.ON_SURFACE_VARIANT),
            ft.Text("Flagged" if is_flagged else "Flag for review", size=12,
                    weight=ft.FontWeight.BOLD if is_flagged else ft.FontWeight.W_500,
                    color=ft.Colors.AMBER_700 if is_flagged else ft.Colors.ON_SURFACE),
        ], tight=True, spacing=4)

        # Options
        options = q.get("options", [])
        chosen = state["answers"].get(idx)

        option_tiles = []
        for opt_idx, opt_text in enumerate(options):
            is_chosen = (chosen == opt_idx)
            letter = _LETTERS[opt_idx] if opt_idx < len(_LETTERS) else str(opt_idx + 1)

            def make_select_handler(selected_index):
                def select_opt(_):
                    if state["submitted"]: return
                    state["answers"][idx] = selected_index
                    render_current_question()
                    page.update()
                return select_opt

            badge = ft.Container(
                width=30, height=30, border_radius=15,
                bgcolor=ft.Colors.PRIMARY if is_chosen else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                alignment=ft.Alignment.CENTER,
                content=ft.Text(letter, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE if is_chosen else ft.Colors.ON_SURFACE),
            )

            tile = ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_chosen else ft.Colors.SURFACE,
                border=ft.Border.all(1.5 if is_chosen else 1, ft.Colors.PRIMARY if is_chosen else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                ink=True,
                on_click=make_select_handler(opt_idx),
                content=ft.Row([
                    badge,
                    ft.Text(opt_text, size=14, weight=ft.FontWeight.W_600 if is_chosen else ft.FontWeight.NORMAL,
                            color=ft.Colors.ON_SURFACE, expand=True, selectable=False),
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=20, color=ft.Colors.PRIMARY) if is_chosen else ft.Container(),
                ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
            option_tiles.append(tile)

        pts = q.get("points", 1.0)
        pts_label = f"{pts:g} pt" if pts == 1.0 else f"{pts:g} pts"

        refresh_jump_strip()

        # Update Navigation Button States
        if prev_btn_ref[0]:
            prev_btn_ref[0].disabled = (idx == 0)

        if next_btn_ref[0]:
            is_last = (idx == total - 1)
            next_btn_ref[0].content = ft.Row([
                ft.Text("Review & Submit" if is_last else "Next", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Icon(ft.Icons.FACT_CHECK_ROUNDED if is_last else ft.Icons.ARROW_FORWARD_ROUNDED, size=16, color=ft.Colors.WHITE),
            ], tight=True, spacing=6)
            next_btn_ref[0].style = ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_700 if is_last else ft.Colors.PRIMARY,
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            )

        is_desktop = (getattr(page, "width", 0) or 0) >= 850
        body_elements = [
            ft.Row([
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                    border_radius=6,
                    content=ft.Text(f"Question {idx + 1} · {pts_label}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                ),
                flag_btn,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ]
        if not is_desktop:
            body_elements.append(jump_strip_row)
            body_elements.append(_build_palette_legend())

        scenario = (q.get("scenario_text") or "").strip()
        if scenario:
            body_elements.extend([
                ft.Container(
                    padding=ft.Padding.all(14),
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
                    border=ft.Border(left=ft.BorderSide(3.5, ft.Colors.PRIMARY)),
                    border_radius=ft.BorderRadius.only(top_right=8, bottom_right=8),
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                            ft.Text("SCENARIO / CASE STUDY CONTEXT", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                        ], spacing=6),
                        ft.Text(scenario, size=14, color=ft.Colors.ON_SURFACE, selectable=True),
                    ], spacing=8),
                ),
                ft.Container(height=4),
            ])

        body_elements.extend([
            ft.Text(q.get("question_text", ""), size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, selectable=False),
            ft.Container(height=8),
            ft.Column(option_tiles, spacing=10),
        ])

        body = ft.Column(body_elements, spacing=12, scroll=ft.ScrollMode.AUTO)

        question_content_area.content = body

    def toggle_flag(_):
        idx = state["index"]
        if idx in state["flags"]:
            state["flags"].remove(idx)
        else:
            state["flags"].add(idx)
        render_current_question()
        page.update()

    flag_btn.on_click = toggle_flag

    def goto_prev(_):
        if state["index"] > 0:
            state["index"] -= 1
            render_current_question()
            page.update()

    def goto_next(_):
        if state["index"] < total - 1:
            state["index"] += 1
            render_current_question()
            page.update()
        else:
            show_review_screen()

    # ── Review Before Submit Screen ───────────────────────────────────────
    def show_review_screen():
        state["in_review"] = True
        answered_indices = set(state["answers"].keys())
        unanswered_indices = [i for i in range(total) if i not in answered_indices]
        flagged_indices = sorted(list(state["flags"]))

        def jump_to_question(target_idx):
            state["in_review"] = False
            state["index"] = target_idx
            build_runner_screen()
            render_current_question()
            page.update()

        pct_answered = round((len(answered_indices) / total) * 100) if total else 0

        # Stat Capsule Component
        def _review_capsule(icon, count_val, label, color):
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.06, color),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, color)),
                expand=True,
                content=ft.Row([
                    ft.Container(
                        width=32, height=32, border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.12, color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=17, color=color),
                    ),
                    ft.Column([
                        ft.Text(f"{count_val}", size=16, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                        ft.Text(label, size=10, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                    ], spacing=1, expand=True),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )

        metric_ribbon = ft.Row([
            _review_capsule(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, len(answered_indices), "Answered", ft.Colors.GREEN_600),
            _review_capsule(ft.Icons.WARNING_AMBER_ROUNDED, len(unanswered_indices), "Unanswered", ft.Colors.RED_600 if unanswered_indices else ft.Colors.GREY_500),
            _review_capsule(ft.Icons.FLAG_OUTLINED, len(flagged_indices), "Flagged", ft.Colors.AMBER_700 if flagged_indices else ft.Colors.GREY_500),
        ], spacing=10)

        # Full Interactive Question Matrix
        matrix_chips = []
        for i in range(total):
            is_ans = (i in answered_indices)
            is_flg = (i in state["flags"])

            if is_flg:
                c_bg = ft.Colors.with_opacity(0.08, ft.Colors.AMBER_700)
                c_border = ft.Colors.with_opacity(0.35, ft.Colors.AMBER_700)
                c_icon = ft.Icon(ft.Icons.FLAG_ROUNDED, size=12, color=ft.Colors.AMBER_800)
                c_text_color = ft.Colors.AMBER_900
                badge_lbl = "Flagged"
            elif is_ans:
                c_bg = ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600)
                c_border = ft.Colors.with_opacity(0.35, ft.Colors.GREEN_600)
                c_icon = ft.Icon(ft.Icons.CHECK_ROUNDED, size=12, color=ft.Colors.GREEN_700)
                c_text_color = ft.Colors.GREEN_800
                badge_lbl = "Answered"
            else:
                c_bg = ft.Colors.with_opacity(0.04, ft.Colors.RED_600)
                c_border = ft.Colors.with_opacity(0.25, ft.Colors.RED_600)
                c_icon = ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED, size=11, color=ft.Colors.RED_600)
                c_text_color = ft.Colors.RED_700
                badge_lbl = "Skipped"

            def make_q_click(idx):
                return lambda _: jump_to_question(idx)

            matrix_chips.append(
                ft.Container(
                    width=72,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    border_radius=8,
                    bgcolor=c_bg,
                    border=ft.Border.all(1, c_border),
                    ink=True,
                    on_click=make_q_click(i),
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"Q{i + 1}", size=11, weight=ft.FontWeight.BOLD, color=c_text_color),
                            c_icon,
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(badge_lbl, size=9, color=c_text_color),
                    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.START),
                )
            )

        matrix_card = ft.Container(
            padding=16, border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            content=ft.Column([
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.GRID_VIEW_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                        ft.Text("Interactive Question Matrix", size=13, weight=ft.FontWeight.BOLD),
                    ], spacing=6, tight=True),
                    ft.Text("Click any question to jump directly and edit", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                ft.Row(matrix_chips, wrap=True, spacing=8),
            ], spacing=10),
        )

        # Pre-Submission Advisory Banner
        if unanswered_indices:
            advisory_banner = ft.Container(
                padding=12, border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.AMBER_700),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.AMBER_700)),
                content=ft.Row([
                    ft.Icon(ft.Icons.WARNING_ROUNDED, size=18, color=ft.Colors.AMBER_800),
                    ft.Column([
                        ft.Text(f"Notice: You have {len(unanswered_indices)} unanswered question(s).", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_900),
                        ft.Text("Unanswered questions receive 0 points. You may return to complete them before submitting.", size=11, color=ft.Colors.AMBER_900),
                    ], spacing=1, expand=True),
                ], spacing=10),
            )
        else:
            advisory_banner = ft.Container(
                padding=12, border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.GREEN_600),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.GREEN_600)),
                content=ft.Row([
                    ft.Icon(ft.Icons.TASK_ALT_ROUNDED, size=18, color=ft.Colors.GREEN_700),
                    ft.Column([
                        ft.Text("All questions have been answered.", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
                        ft.Text("Review your flagged questions above or confirm final submission below.", size=11, color=ft.Colors.GREEN_800),
                    ], spacing=1, expand=True),
                ], spacing=10),
            )

        submit_btn = ft.FilledButton(
            content=ft.Row([
                ft.Text("Finalize & Submit Assessment", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=16, color=ft.Colors.WHITE),
            ], tight=True, spacing=6),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_700,
                padding=ft.Padding.symmetric(horizontal=24, vertical=12),
            ),
            on_click=lambda _: page.run_task(execute_final_submit),
        )

        action_card = ft.Container(
            padding=14, border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
            content=ft.Row([
                ft.TextButton(
                    content=ft.Row([ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=15), ft.Text(f"Back to Question {state['index'] + 1}", size=12)], spacing=4, tight=True),
                    on_click=lambda _: jump_to_question(state["index"]),
                ),
                submit_btn,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        )

        review_layout = ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(horizontal=24, vertical=20),
            alignment=ft.Alignment.TOP_CENTER,
            content=ft.Container(
                width=min(getattr(page, "width", 840) or 840, 800),
                content=ft.Column([
                    # Header Tag
                    ft.Row([
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                            content=ft.Row([
                                ft.Icon(ft.Icons.FACT_CHECK_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                                ft.Text("PRE-SUBMISSION AUDIT & REVIEW", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                            ], tight=True, spacing=5),
                        ),
                    ]),
                    ft.Text("Review Your Assessment", size=22, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                    ft.Row([
                        ft.Icon(ft.Icons.TIMER_OUTLINED, size=14, color=ft.Colors.PRIMARY),
                        ft.Text(f"Timer running · {timer_text.value} remaining to audit your responses", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                    ], spacing=6),
                    ft.Container(height=4),
                    # Overall completion bar
                    ft.Column([
                        ft.Row([
                            ft.Text(f"Overall Progress: {len(answered_indices)} of {total} Questions Answered", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ft.Text(f"{pct_answered}%", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.ProgressBar(value=(len(answered_indices) / total) if total else 0, color=ft.Colors.GREEN_600, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600), height=5, border_radius=3),
                    ], spacing=4),
                    metric_ribbon,
                    advisory_banner,
                    matrix_card,
                    action_card,
                ], spacing=12, scroll=ft.ScrollMode.AUTO),
            ),
        )

        root.content = review_layout
        page.update()

    # ── Final Submission Handler ─────────────────────────────────────────
    submitting_overlay = ft.Container(
        expand=True, alignment=ft.Alignment.CENTER,
        content=ft.Column([
            ft.ProgressRing(color=ft.Colors.PRIMARY, width=36, height=36),
            ft.Text("Submitting and grading your exam securely...", size=14, weight=ft.FontWeight.BOLD),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=14),
    )

    async def execute_final_submit(e=None, *, is_violation: bool = False, violation_reason: Optional[str] = None):
        if state["submitted"]: return
        state["submitted"] = True
        state["running"] = False
        release_security_locks()

        root.content = submitting_overlay
        page.update()

        elapsed = int(time.time() - state["started"])
        answers_payload = []
        for i, q in enumerate(questions):
            q_id = str(q.get("id"))
            chosen_opt = state["answers"].get(i)
            answers_payload.append({
                "question_id": q_id,
                "chosen_index": chosen_opt,
            })

        submit_data = {
            "answers": answers_payload,
            "duration_seconds": elapsed,
            "violations_count": state["violations_count"],
            "violation_log": state["violation_log"],
            "session_token": session_token,
        }

        res = await submit_cohort_exam(
            token=token,
            org_id=org_id,
            cohort_id=cohort_id,
            exam_id=exam_id,
            payload=submit_data,
        )

        display_result_view(res, is_violation=is_violation, violation_reason=violation_reason)

    def display_result_view(res: dict, is_violation: bool = False, violation_reason: Optional[str] = None):
        if "error" in res:
            root.content = ft.Container(
                padding=24, alignment=ft.Alignment.CENTER,
                content=ft.Column([
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=48, color=ft.Colors.RED_500),
                    ft.Text("Submission Error", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(res.get("error", "An error occurred during submission."), color=ft.Colors.RED_700),
                    ft.FilledButton("Return to Hub", on_click=safe_exit),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14),
            )
            page.update()
            return

        duration_sec = res.get("duration_seconds", 0)
        mins, secs = divmod(duration_sec, 60)

        # Violation banner if flagged
        violation_banner = ft.Container()
        if is_violation or res.get("status") == "flagged_violation" or state["violations_count"] > 0:
            violation_banner = ft.Container(
                padding=14, border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED_700),
                border=ft.Border.all(1, ft.Colors.RED_700),
                content=ft.Row([
                    ft.Icon(ft.Icons.SECURITY_ROUNDED, color=ft.Colors.RED_700, size=20),
                    ft.Column([
                        ft.Text("Security Audit Notice", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.RED_700),
                        ft.Text(violation_reason or f"{state['violations_count']} focus/app-switch incident(s) recorded during this attempt.", size=11, color=ft.Colors.RED_800),
                    ], spacing=2, expand=True),
                ], spacing=10),
            )

        show_immed = res.get("show_immediate_results", show_immediate_results)
        has_score = ("score" in res and res.get("score") is not None)

        if not show_immed or not has_score:
            # ── Modern Submission Receipt: Confidential / Post-Review Scoring ──
            receipt_date = datetime.now().strftime("%b %d, %Y · %I:%M %p")
            q_recorded = res.get("questions_answered", len(state["answers"]))

            root.content = ft.Container(
                padding=24, alignment=ft.Alignment.CENTER,
                content=ft.Column([
                    ft.Container(
                        width=540 if getattr(page, "width", 0) and page.width > 600 else None,
                        padding=32,
                        border_radius=18,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                        content=ft.Column([
                            violation_banner,
                            ft.Container(
                                width=64, height=64, border_radius=32,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.TASK_ALT_ROUNDED, size=34, color=ft.Colors.GREEN_600),
                            ),
                            ft.Text("Assessment Submitted", size=22, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Your answers have been securely recorded and sealed for institutional evaluation.",
                                size=13, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=8),
                            # Receipt Details Card
                            ft.Container(
                                padding=18, border_radius=14,
                                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                                content=ft.Column([
                                    ft.Row([
                                        ft.Text("Evaluation Status", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                            border_radius=6,
                                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLUE_600),
                                            content=ft.Text("Under Academic Review", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
                                        ),
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                                    ft.Row([
                                        ft.Text("Questions Recorded", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ft.Text(f"{q_recorded} of {total}", size=12, weight=ft.FontWeight.BOLD),
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Row([
                                        ft.Text("Duration Elapsed", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ft.Text(f"{mins}m {secs}s", size=12, weight=ft.FontWeight.BOLD),
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Row([
                                        ft.Text("Timestamp", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ft.Text(receipt_date, size=11, color=ft.Colors.ON_SURFACE),
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ], spacing=10),
                            ),
                            ft.Container(height=6),
                            # Academic Review Notice
                            ft.Container(
                                padding=14, border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY)),
                                content=ft.Row([
                                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=20, color=ft.Colors.PRIMARY),
                                    ft.Text(
                                        res.get("note") or "Official results and detailed feedback will be published by your instructor once grading moderation is concluded.",
                                        size=12, color=ft.Colors.ON_SURFACE, expand=True,
                                    ),
                                ], spacing=10),
                            ),
                            ft.Container(height=14),
                            ft.FilledButton(
                                "Return to Learning Hub",
                                icon=ft.Icons.ARROW_BACK_ROUNDED,
                                on_click=safe_exit,
                                style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=28, vertical=14)),
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )
            page.update()
            return

        percentage = res.get("percentage", 0.0)
        passed = res.get("passed", False)
        score = res.get("score", 0.0)
        max_score = res.get("max_score", 0.0)

        badge_color = ft.Colors.GREEN_600 if passed else ft.Colors.RED_500
        badge_icon = ft.Icons.VERIFIED_ROUNDED if passed else ft.Icons.CANCEL_ROUNDED
        status_label = "PASSED" if passed else "DID NOT PASS"

        breakdown = res.get("breakdown", [])
        breakdown_controls = []
        for b_idx, b in enumerate(breakdown):
            b_correct = b.get("is_correct", False)
            b_color = ft.Colors.GREEN_600 if b_correct else ft.Colors.RED_500
            b_scen = (b.get("scenario_text") or "").strip()

            b_elements = [
                ft.Row([
                    ft.Row([
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=6, bgcolor=ft.Colors.with_opacity(0.1, b_color),
                            content=ft.Text(f"Q{b_idx + 1} · {'Correct' if b_correct else 'Incorrect'}",
                                            size=11, weight=ft.FontWeight.BOLD, color=b_color),
                        ),
                        ft.Container(
                            visible=bool(b_scen),
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            border_radius=4,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                            content=ft.Row([
                                ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=10, color=ft.Colors.PRIMARY),
                                ft.Text("Scenario", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                            ], spacing=3, tight=True),
                        ),
                    ], spacing=6, tight=True),
                    ft.Text(f"{b.get('points_earned', 0):g}/{b.get('max_points', 1):g} pts", size=11, weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ]
            if b_scen:
                b_elements.append(
                    ft.Container(
                        padding=ft.Padding.all(8),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
                        border=ft.Border(left=ft.BorderSide(2.5, ft.Colors.PRIMARY)),
                        content=ft.Text(b_scen, size=11, color=ft.Colors.ON_SURFACE_VARIANT, italic=True),
                    )
                )
            b_elements.append(ft.Text(b.get("question_text", ""), size=13, weight=ft.FontWeight.W_600))
            if b.get("explanation"):
                b_elements.append(ft.Text(f"Explanation: {b.get('explanation')}", size=11, color=ft.Colors.ON_SURFACE_VARIANT, italic=True))

            breakdown_controls.append(
                ft.Container(
                    padding=14, border_radius=10,
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    content=ft.Column(b_elements, spacing=6),
                )
            )

        # Delayed-results note banner if breakdown is omitted
        note_text = res.get("note")
        delayed_note_widget = ft.Container()
        if not breakdown and note_text:
            delayed_note_widget = ft.Container(
                padding=14, border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_600),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.BLUE_600)),
                content=ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=20, color=ft.Colors.BLUE_700),
                    ft.Text(note_text, size=12, color=ft.Colors.BLUE_800, expand=True),
                ], spacing=10),
            )

        root.content = ft.Container(
            padding=24, alignment=ft.Alignment.CENTER,
            content=ft.Column([
                ft.Container(
                    width=600 if page.width and page.width > 700 else None,
                    content=ft.Column([
                        violation_banner,
                        ft.Container(
                            padding=24, border_radius=16, alignment=ft.Alignment.CENTER,
                            bgcolor=ft.Colors.with_opacity(0.08, badge_color),
                            border=ft.Border.all(1.5, badge_color),
                            content=ft.Column([
                                ft.Icon(badge_icon, size=48, color=badge_color),
                                ft.Text(status_label, size=22, weight=ft.FontWeight.BOLD, color=badge_color),
                                ft.Text(f"Final Score: {score:g} / {max_score:g} ({percentage}%)", size=16, weight=ft.FontWeight.W_700),
                                ft.Text(f"Completed in {mins}m {secs}s", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                        ),
                        ft.Container(height=16),
                        ft.FilledButton(
                            "Return to Hub",
                            icon=ft.Icons.CHECK_ROUNDED,
                            on_click=safe_exit,
                            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=24, vertical=14)),
                        ),
                        delayed_note_widget,
                        ft.Container(height=16) if breakdown_controls else ft.Container(),
                        ft.Text("Detailed Question Breakdown", size=15, weight=ft.FontWeight.BOLD) if breakdown_controls else ft.Container(),
                        ft.Column(breakdown_controls, spacing=10) if breakdown_controls else ft.Container(),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO, spacing=10),
                ),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )
        page.update()

    # ── Ticking Timer Loop ───────────────────────────────────────────────
    async def timer_loop():
        total_duration = total_duration_sec
        while state["running"] and state["remaining"] > 0:
            await asyncio.sleep(1)
            state["remaining"] -= 1
            timer_text.value = format_time(state["remaining"])
            progress_ratio = max(0.0, state["remaining"] / max(total_duration, 1))
            timer_bar.value = progress_ratio

            if progress_ratio < 0.10:
                timer_text.color = ft.Colors.RED_600
                timer_icon.color = ft.Colors.RED_600
                timer_bar.color = ft.Colors.RED_600
            elif progress_ratio < 0.25:
                timer_text.color = ft.Colors.AMBER_600
                timer_icon.color = ft.Colors.AMBER_600
                timer_bar.color = ft.Colors.AMBER_600

            # Time-critical non-blocking alerts at 5 mins and 1 min
            if state["remaining"] == 300:
                try:
                    snack = ft.SnackBar(
                        content=ft.Row([
                            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.WHITE, size=20),
                            ft.Text("5 minutes remaining — review your questions.", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ], spacing=8),
                        bgcolor=ft.Colors.AMBER_900,
                        duration=4000,
                    )
                    page.overlay.append(snack)
                    snack.open = True
                except Exception:
                    pass
            elif state["remaining"] == 60:
                try:
                    snack = ft.SnackBar(
                        content=ft.Row([
                            ft.Icon(ft.Icons.TIMER_ROUNDED, color=ft.Colors.WHITE, size=20),
                            ft.Text("1 minute remaining — exam will auto-submit on countdown expiry.", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ], spacing=8),
                        bgcolor=ft.Colors.RED_900,
                        duration=4000,
                    )
                    page.overlay.append(snack)
                    snack.open = True
                except Exception:
                    pass

            page.update()

        if state["running"] and not state["submitted"]:
            # Auto-submit on timeout
            await execute_final_submit(is_violation=False, violation_reason="Time limit expired.")

    # ── Build Screen Layout ──────────────────────────────────────────────
    def build_runner_screen():
        prev_btn = ft.OutlinedButton("Previous", icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=goto_prev, disabled=True)
        next_btn = ft.FilledButton(
            content=ft.Row([
                ft.Text("Next", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16, color=ft.Colors.WHITE),
            ], tight=True, spacing=6),
            on_click=goto_next,
        )
        prev_btn_ref[0] = prev_btn
        next_btn_ref[0] = next_btn

        # Floating Calculator overlay
        calc_overlay = ft.Container(
            visible=False,
            alignment=ft.Alignment.TOP_RIGHT,
            padding=ft.Padding.only(top=14, right=14),
        )

        def toggle_calc(_=None):
            calc_overlay.visible = not calc_overlay.visible
            if calc_overlay.visible and calc_overlay.content is None:
                calc_overlay.content = build_exam_calculator(
                    page=page,
                    calculator_type=calculator_type,
                    on_close=toggle_calc,
                )
            page.update()

        is_desktop = (getattr(page, "width", 0) or 0) >= 850

        if is_desktop:
            # Desktop Split-Pane Layout
            sidebar_items = [
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        tooltip="Exit Assessment",
                        on_click=confirm_leave_exam,
                    ),
                    ft.Column([
                        ft.Text(title, size=13, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"{total} Questions", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=1, expand=True),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.08, timer_text.color),
                    content=ft.Column([
                        ft.Row([timer_icon, timer_text], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                        timer_bar,
                    ], spacing=6),
                ),
            ]

            if calculator_type in ("basic", "scientific"):
                sidebar_items.append(
                    ft.OutlinedButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CALCULATE_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                            ft.Text("Calculator", size=12, weight=ft.FontWeight.W_600),
                        ], tight=True, spacing=6),
                        style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=12, vertical=8)),
                        tooltip="Open Calculator",
                        on_click=toggle_calc,
                    )
                )

            if security_mode in ("strict", "monitored"):
                update_strike_badges_ui()
                sidebar_items.append(sidebar_strike_box)

            sidebar_items.extend([
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                ft.Row([
                    ft.Text("Question Palette", size=12, weight=ft.FontWeight.BOLD),
                    q_counter,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                _build_palette_legend(),
                ft.Container(
                    content=jump_grid_sidebar,
                    expand=True,
                ),
                ft.FilledButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.FACT_CHECK_ROUNDED, size=16, color=ft.Colors.WHITE),
                        ft.Text("Review & Submit", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700),
                    on_click=lambda _: show_review_screen(),
                ),
            ])

            desktop_sidebar = ft.Container(
                width=280,
                bgcolor=ft.Colors.SURFACE,
                padding=16,
                border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
                content=ft.Column(sidebar_items, spacing=10, expand=True),
            )

            nav_footer = ft.Container(
                padding=ft.Padding.symmetric(horizontal=24, vertical=12),
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
                content=ft.Row([
                    prev_btn,
                    next_btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            )

            right_pane = ft.Column([
                ft.Container(
                    content=question_content_area,
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=32, vertical=20),
                    alignment=ft.Alignment.TOP_CENTER,
                ),
                nav_footer,
            ], expand=True, spacing=0)

            main_layout = ft.Row([desktop_sidebar, right_pane], expand=True, spacing=0)
            root.content = ft.Stack([main_layout, calc_overlay], expand=True)
        else:
            # Mobile Layout
            top_bar_actions = []
            if calculator_type in ("basic", "scientific"):
                top_bar_actions.append(
                    ft.IconButton(
                        icon=ft.Icons.CALCULATE_ROUNDED,
                        tooltip="Open Calculator",
                        on_click=toggle_calc,
                    )
                )
            if security_mode in ("strict", "monitored"):
                update_strike_badges_ui()
                top_bar_actions.append(topbar_strike_box)
            top_bar_actions.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.08, timer_text.color),
                    content=ft.Row([timer_icon, timer_text], spacing=6, tight=True),
                )
            )

            top_bar = ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
                content=ft.Column([
                    ft.Row([
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            tooltip="Exit Assessment",
                            on_click=confirm_leave_exam,
                        ),
                        ft.Column([
                            ft.Text(title, size=14, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            q_counter,
                        ], spacing=1, expand=True),
                        ft.Row(top_bar_actions, spacing=4, tight=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    timer_bar,
                ], spacing=8),
            )

            nav_footer = ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
                content=ft.Row([
                    prev_btn,
                    ft.TextButton("Review Palette", icon=ft.Icons.GRID_VIEW_ROUNDED, on_click=lambda _: show_review_screen()),
                    next_btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            )

            main_layout = ft.Column([
                top_bar,
                ft.Container(
                    content=question_content_area,
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=16),
                    alignment=ft.Alignment.TOP_CENTER,
                ),
                nav_footer,
            ], expand=True, spacing=0)

            root.content = ft.Stack([main_layout, calc_overlay], expand=True)

    # ── Pre-Exam Briefing Screen ──────────────────────────────────────────
    def start_exam_from_briefing(_):
        state["started_assessment"] = True
        state["started"] = time.time()
        state["running"] = True
        apply_security_locks()
        build_runner_screen()
        render_current_question()
        page.run_task(timer_loop)
        page.update()

    def show_pre_exam_briefing():
        dur_mins = duration_remaining // 60
        max_att = exam_payload.get("max_attempts") or exam_payload.get("allowed_attempts") or 1
        security_label = "Strict (Zero Tolerance)" if security_mode == "strict" else ("Monitored (Warning Strikes)" if security_mode == "monitored" else "Practice (Relaxed)")

        # Metric Ribbon Capsules
        def _metric_capsule(icon, label, value, color=ft.Colors.PRIMARY):
            return ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Row([
                    ft.Container(
                        width=32, height=32, border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.1, color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=17, color=color),
                    ),
                    ft.Column([
                        ft.Text(label, size=10, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                        ft.Text(value, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ], spacing=1, expand=True),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )

        spec_ribbon = ft.Row([
            _metric_capsule(ft.Icons.TIMER_OUTLINED, "Duration", f"{dur_mins} Minutes", ft.Colors.BLUE_600),
            _metric_capsule(ft.Icons.FORMAT_LIST_NUMBERED_ROUNDED, "Total Items", f"{total} Questions", ft.Colors.TEAL_600),
            _metric_capsule(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, "Pass Mark", f"{pass_mark}%", ft.Colors.GREEN_600),
            _metric_capsule(ft.Icons.REPEAT_ROUNDED, "Attempts Allowed", f"{max_att} Max", ft.Colors.AMBER_700),
        ], spacing=10)

        # Permitted Calculator Pill
        if calculator_type != "none":
            calc_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.GREEN_600),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.GREEN_600)),
                content=ft.Row([
                    ft.Icon(ft.Icons.CALCULATE_ROUNDED, size=16, color=ft.Colors.GREEN_700),
                    ft.Column([
                        ft.Text(f"Embedded {calculator_type.capitalize()} Calculator Permitted", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800),
                        ft.Text("Interactive digital calculator overlay is available in the examination top bar.", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=1, expand=True),
                ], spacing=8),
            )
        else:
            calc_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                content=ft.Row([
                    ft.Icon(ft.Icons.BLOCK_ROUNDED, size=16, color=ft.Colors.RED_700),
                    ft.Column([
                        ft.Text("Closed Book: No Calculator Permitted", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_800),
                        ft.Text("External or digital calculators are strictly prohibited during this exam.", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=1, expand=True),
                ], spacing=8),
            )

        # Section 1: Security & Anti-Cheat Regulations
        security_card = ft.Container(
            padding=16, border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            content=ft.Column([
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.SHIELD_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                        ft.Text("Proctoring & Anti-Cheat Protocols", size=13, weight=ft.FontWeight.BOLD),
                    ], spacing=6, tight=True),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                        content=ft.Text(security_label, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.FULLSCREEN_ROUNDED, size=15, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Column([
                            ft.Text("Fullscreen Kiosk Enforced", size=11, weight=ft.FontWeight.BOLD),
                            ft.Text("Assessment runs in locked fullscreen. Minimizing, unmaximizing, or exiting is recorded as a strike.", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=1, expand=True),
                    ], spacing=8),
                    ft.Row([
                        ft.Icon(ft.Icons.VISIBILITY_OUTLINED, size=15, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Column([
                            ft.Text("Active Focus & App-Switch Tracking", size=11, weight=ft.FontWeight.BOLD),
                            ft.Text("Switching apps, splitting screens, or losing window focus logs an automated security violation.", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=1, expand=True),
                    ], spacing=8),
                    ft.Row([
                        ft.Icon(ft.Icons.KEYBOARD_ROUNDED, size=15, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Column([
                            ft.Text("Restricted Keyboard Shortcuts & DevTools", size=11, weight=ft.FontWeight.BOLD),
                            ft.Text("Copy (Ctrl+C), paste (Ctrl+V), DevTools (F12), and screenshot keys are intercepted and suppressed.", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=1, expand=True),
                    ], spacing=8),
                ], spacing=10),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.AMBER_700),
                    content=ft.Row([
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=13, color=ft.Colors.AMBER_800),
                        ft.Text(
                            f"Violation policy: {'1 breach causes immediate permanent auto-submission.' if security_mode == 'strict' else str(max_violations) + ' strikes allowed before automatic submission.'}",
                            size=10, color=ft.Colors.AMBER_900, weight=ft.FontWeight.W_500,
                        ),
                    ], spacing=6),
                ),
            ], spacing=10),
        )

        # Section 2: Instructions & Tools
        instr_text = instructions if instructions else "Read each question carefully before choosing your response. You may navigate freely between questions, flag items for review, and utilize the question palette to jump between sections."
        tools_instructions_card = ft.Container(
            padding=16, border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.FACT_CHECK_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                    ft.Text("Tools & Examination Guidelines", size=13, weight=ft.FontWeight.BOLD),
                ], spacing=6),
                calc_badge,
                ft.Container(
                    padding=10, border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                    content=ft.Column([
                        ft.Text("Instructor Instructions", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(instr_text, size=11, color=ft.Colors.ON_SURFACE),
                    ], spacing=4),
                ),
                ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                    ft.Text("Answers are saved in real-time. Timer runs continuously without pause.", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=6),
            ], spacing=10),
        )

        # Section 3: Honor Code Pledge Card & Action Bar
        start_btn = ft.FilledButton(
            content=ft.Row([
                ft.Text("Begin Assessment", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16, color=ft.Colors.WHITE),
            ], tight=True, spacing=6),
            style=ft.ButtonStyle(
                bgcolor={ft.ControlState.DEFAULT: ft.Colors.GREEN_700, ft.ControlState.DISABLED: ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)},
                padding=ft.Padding.symmetric(horizontal=24, vertical=12),
            ),
            disabled=True,
            on_click=start_exam_from_briefing,
        )

        pledge_card = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=10,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE)),
            ink=True,
        )

        def toggle_ack(e=None):
            ack_chk.value = not ack_chk.value
            on_ack_change(None)

        def on_ack_change(e=None):
            is_checked = bool(ack_chk.value)
            start_btn.disabled = not is_checked
            pledge_card.border = ft.Border.all(1.5, ft.Colors.PRIMARY if is_checked else ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE))
            pledge_card.bgcolor = ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY) if is_checked else ft.Colors.SURFACE
            page.update()

        ack_chk = ft.Checkbox(
            value=False,
            scale=0.9,
            on_change=on_ack_change,
        )

        pledge_card.content = ft.Row([
            ack_chk,
            ft.Column([
                ft.Text("Academic Integrity & Honor Code Pledge", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Text(
                    "I confirm that I will complete this assessment independently under enforced fullscreen rules without unauthorized aids, external browser tabs, or secondary devices.",
                    size=10, color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ], spacing=2, expand=True),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        pledge_card.on_click = toggle_ack

        action_card = ft.Container(
            padding=14, border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
            content=ft.Column([
                pledge_card,
                ft.Container(height=4),
                ft.Row([
                    ft.TextButton(
                        content=ft.Row([ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=15), ft.Text("Exit / Not Ready", size=12)], spacing=4, tight=True),
                        on_click=safe_exit,
                    ),
                    start_btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=8),
        )

        briefing_layout = ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(horizontal=24, vertical=20),
            alignment=ft.Alignment.TOP_CENTER,
            content=ft.Container(
                width=min(getattr(page, "width", 840) or 840, 800),
                content=ft.Column([
                    # Header
                    ft.Row([
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                            content=ft.Row([
                                ft.Icon(ft.Icons.VERIFIED_USER_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                                ft.Text("SECURE CANDIDATE PORTAL", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                            ], tight=True, spacing=5),
                        ),
                    ]),
                    ft.Text(title, size=22, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                    ft.Row([
                        ft.Container(width=7, height=7, border_radius=3.5, bgcolor=ft.Colors.GREEN_600),
                        ft.Text("Assessment Window Active · Secure Proctoring Monitored", size=11, color=ft.Colors.GREEN_700, weight=ft.FontWeight.W_600),
                    ], spacing=6),
                    ft.Container(height=4),
                    spec_ribbon,
                    security_card,
                    tools_instructions_card,
                    action_card,
                ], spacing=12, scroll=ft.ScrollMode.AUTO),
            ),
        )
        root.content = briefing_layout

    show_pre_exam_briefing()
    return root
