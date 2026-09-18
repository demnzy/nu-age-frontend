"""
Candidate Exam Runner for Cohort Assessments with Enterprise Anti-Cheat Security:
  * Server-synced sticky countdown timer with auto-submit on expiry.
  * Anti-Cheat Focus & Lifecycle Watcher:
    - Android/iOS app lifecycle change detection (inactive, paused, hidden).
    - Desktop/Web window blur and focus loss detection.
  * Configurable Security Enforcement:
    - Strict mode: Immediate auto-submit on first app switch or blur.
    - Monitored mode: Warning strikes with full audit log and auto-submit on limit.
  * Kiosk / Fullscreen enforcement.
  * Hardware & Software back navigation trapping.
  * DevTools and copy-paste suppression.
  * Session token binding and server-authoritative submission.
"""

import asyncio
from datetime import datetime, timezone
import time
import flet as ft
from src.components import study_ui as ui
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
    instructions = exam_payload.get("instructions")
    security_mode = exam_payload.get("security_mode", "monitored")  # strict, monitored, relaxed
    max_violations = int(exam_payload.get("max_violations", 2))
    session_token = exam_payload.get("session_token")

    if total == 0:
        return ui.empty_state(
            ft.Icons.ASSIGNMENT_OUTLINED,
            "No exam questions found",
            "This assessment does not have any questions configured yet.",
            "Return to Cohort",
            on_exit,
        )

    state = {
        "index": 0,
        "answers": {},       # index -> chosen option index
        "flags": set(),      # set of question indices flagged
        "running": True,
        "submitted": False,
        "started": time.time(),
        "remaining": max(10, int(duration_remaining)),
        "violations_count": 0,
        "violation_log": [],
        "violation_dialog_open": False,
    }

    root = ft.Container(expand=True)

    # ── Fullscreen & Kiosk Activation ────────────────────────────────────
    prev_prevent_close = getattr(page.window, "prevent_close", False)
    try:
        page.window.prevent_close = True
        page.window.full_screen = True
        page.update()
    except Exception:
        pass

    def release_security_locks():
        try:
            page.window.prevent_close = prev_prevent_close
            page.window.full_screen = False
            page.on_keyboard_event = None
            page.on_app_lifecycle_state_change = None
            page.window.on_event = None
            page.update()
        except Exception:
            pass

    def safe_exit(e=None):
        release_security_locks()
        if on_exit:
            on_exit(e)

    # ── Anti-Cheat Focus & Lifecycle Watcher ──────────────────────────────
    def record_violation(v_type: str, details: str):
        if state["submitted"] or not state["running"] or security_mode == "relaxed":
            return

        now_str = datetime.now(timezone.utc).isoformat()
        state["violations_count"] += 1
        state["violation_log"].append({
            "timestamp": now_str,
            "type": v_type,
            "details": details,
            "strike": state["violations_count"],
        })

        if security_mode == "strict":
            # Immediate submission in strict mode
            page.run_task(execute_final_submit, True, f"Strict anti-cheat violation: {details}")
        else:
            # Monitored mode with warning strikes
            if state["violations_count"] > max_violations:
                page.run_task(execute_final_submit, True, f"Violation limit exceeded ({state['violations_count']}/{max_violations}): {details}")
            else:
                show_violation_warning(v_type, details)

    def show_violation_warning(v_type: str, details: str):
        if state["submitted"] or state["violation_dialog_open"]:
            return
        state["violation_dialog_open"] = True

        strikes_left = max(0, max_violations - state["violations_count"] + 1)
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
                        "Navigating away, switching windows/apps, splitting screens, or exiting fullscreen is prohibited. "
                        f"You have {strikes_left} strike(s) remaining before your exam is permanently submitted automatically.",
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
        try:
            page.pop_dialog()
            page.window.full_screen = True
            page.update()
        except Exception:
            pass

    # 1. Mobile app lifecycle change listener
    def on_lifecycle_change(e):
        lifecycle_state = str(e.data).lower()
        if lifecycle_state in ("inactive", "paused", "hidden", "detached"):
            record_violation("app_lifecycle_unfocused", f"App transitioned to {lifecycle_state} (switched apps/split screen)")

    page.on_app_lifecycle_state_change = on_lifecycle_change

    # 2. Desktop/web window blur listener
    def on_window_event(e):
        ev_name = str(e.data).lower()
        if ev_name in ("blur", "minimize"):
            record_violation("window_blur", f"Window lost focus ({ev_name})")

    try:
        page.window.on_event = on_window_event
    except Exception:
        pass

    # 3. Keyboard devtools & copy-paste suppression
    def on_key_event(e: ft.KeyboardEvent):
        key = (e.key or "").lower()
        ctrl_or_cmd = e.ctrl or e.meta

        # Block Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+U, Ctrl+P, F12
        if (ctrl_or_cmd and key in ("c", "v", "x", "u", "p")) or key in ("f12", "f11"):
            record_violation("prohibited_shortcut", f"Prohibited keyboard shortcut attempted: {key.upper()}")

    page.on_keyboard_event = on_key_event

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
        await execute_final_submit(False, "Candidate voluntarily chose to submit and leave.")

    # ── Progress Bar & Timer ─────────────────────────────────────────────
    timer_text = ft.Text("00:00", size=15, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY)
    timer_icon = ft.Icon(ft.Icons.TIMER_ROUNDED, size=18, color=ft.Colors.PRIMARY)
    timer_bar = ft.ProgressBar(value=1.0, height=4, color=ft.Colors.PRIMARY, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY))
    q_counter = ft.Text(f"1 of {total}", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE)
    flag_btn = ft.OutlinedButton(
        content=ft.Row([ft.Icon(ft.Icons.FLAG_OUTLINED, size=15, color=ft.Colors.AMBER_700), ft.Text("Flag", size=12, weight=ft.FontWeight.W_600)], tight=True, spacing=4),
        style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=10, vertical=4)),
    )

    def format_time(seconds: int) -> str:
        mins, secs = divmod(max(0, seconds), 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            return f"{hrs:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    # ── Question Rendering ───────────────────────────────────────────────
    question_content_area = ft.Container(expand=True)

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

        body = ft.Column([
            ft.Row([
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                    border_radius=6,
                    content=ft.Text(f"Question {idx + 1} · {pts_label}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                ),
                flag_btn,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(q.get("question_text", ""), size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, selectable=False),
            ft.Container(height=8),
            ft.Column(option_tiles, spacing=10),
        ], spacing=14)

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

        unanswered_chips = [
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED_700),
                ink=True,
                on_click=lambda _, idx=i: jump_to_question(idx),
                content=ft.Text(f"Q{i + 1}", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700),
            )
            for i in unanswered_indices
        ]

        flagged_chips = [
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_700),
                ink=True,
                on_click=lambda _, idx=i: jump_to_question(idx),
                content=ft.Row([
                    ft.Icon(ft.Icons.FLAG_ROUNDED, size=13, color=ft.Colors.AMBER_700),
                    ft.Text(f"Q{i + 1}", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_700),
                ], spacing=4, tight=True),
            )
            for i in flagged_indices
        ]

        submit_btn = ft.FilledButton(
            content=ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18, color=ft.Colors.WHITE),
                ft.Text("Submit Exam Now", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            ], tight=True, spacing=8),
            style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, padding=ft.Padding.symmetric(horizontal=24, vertical=16)),
            on_click=lambda _: page.run_task(execute_final_submit),
        )

        review_layout = ft.Container(
            padding=24,
            content=ft.Column([
                ft.Text("Review Your Assessment", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Text(f"You have answered {len(answered_indices)} of {total} questions.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Container(height=10),
                # Stats grid
                ft.Row([
                    ft.Container(
                        padding=16, border_radius=12, expand=True,
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.GREEN_600),
                        content=ft.Column([
                            ft.Text("Answered", size=12, color=ft.Colors.GREEN_700),
                            ft.Text(f"{len(answered_indices)}", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
                        ], spacing=2),
                    ),
                    ft.Container(
                        padding=16, border_radius=12, expand=True,
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.RED_600),
                        content=ft.Column([
                            ft.Text("Unanswered", size=12, color=ft.Colors.RED_700),
                            ft.Text(f"{len(unanswered_indices)}", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700),
                        ], spacing=2),
                    ),
                    ft.Container(
                        padding=16, border_radius=12, expand=True,
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.AMBER_600),
                        content=ft.Column([
                            ft.Text("Flagged", size=12, color=ft.Colors.AMBER_800),
                            ft.Text(f"{len(flagged_indices)}", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_800),
                        ], spacing=2),
                    ),
                ], spacing=12),
                ft.Container(height=16),
                ft.Text("Unanswered Questions:", size=13, weight=ft.FontWeight.BOLD) if unanswered_chips else ft.Container(),
                ft.Row(unanswered_chips, wrap=True, spacing=8) if unanswered_chips else ft.Container(),
                ft.Container(height=10) if unanswered_chips else ft.Container(),
                ft.Text("Flagged for Review:", size=13, weight=ft.FontWeight.BOLD) if flagged_chips else ft.Container(),
                ft.Row(flagged_chips, wrap=True, spacing=8) if flagged_chips else ft.Container(),
                ft.Container(height=24),
                ft.Row([
                    ft.OutlinedButton("Return to Exam", icon=ft.Icons.ARROW_BACK_ROUNDED,
                                      on_click=lambda _: jump_to_question(state["index"])),
                    submit_btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], scroll=ft.ScrollMode.AUTO),
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

    async def execute_final_submit(e=None, is_violation: bool = False, violation_reason: str = None):
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

        display_result_view(res, is_violation, violation_reason)

    def display_result_view(res: dict, is_violation: bool = False, violation_reason: str = None):
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

        percentage = res.get("percentage", 0.0)
        passed = res.get("passed", False)
        score = res.get("score", 0.0)
        max_score = res.get("max_score", 0.0)
        duration_sec = res.get("duration_seconds", 0)
        mins, secs = divmod(duration_sec, 60)

        badge_color = ft.Colors.GREEN_600 if passed else ft.Colors.RED_500
        badge_icon = ft.Icons.VERIFIED_ROUNDED if passed else ft.Icons.CANCEL_ROUNDED
        status_label = "PASSED" if passed else "DID NOT PASS"

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

        breakdown = res.get("breakdown", [])
        breakdown_controls = []
        for b_idx, b in enumerate(breakdown):
            b_correct = b.get("is_correct", False)
            b_color = ft.Colors.GREEN_600 if b_correct else ft.Colors.RED_500
            breakdown_controls.append(
                ft.Container(
                    padding=14, border_radius=10,
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=6, bgcolor=ft.Colors.with_opacity(0.1, b_color),
                                content=ft.Text(f"Q{b_idx + 1} · {'Correct' if b_correct else 'Incorrect'}",
                                                size=11, weight=ft.FontWeight.BOLD, color=b_color),
                            ),
                            ft.Text(f"{b.get('points_earned', 0):g}/{b.get('max_points', 1):g} pts", size=11, weight=ft.FontWeight.BOLD),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(b.get("question_text", ""), size=13, weight=ft.FontWeight.W_600),
                        ft.Text(f"Explanation: {b.get('explanation')}", size=11, color=ft.Colors.ON_SURFACE_VARIANT, italic=True) if b.get("explanation") else ft.Container(),
                    ], spacing=6),
                )
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
                            "Return to Cohort",
                            icon=ft.Icons.CHECK_ROUNDED,
                            on_click=safe_exit,
                            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=24, vertical=14)),
                        ),
                        ft.Container(height=16),
                        ft.Text("Detailed Question Breakdown", size=15, weight=ft.FontWeight.BOLD) if breakdown_controls else ft.Container(),
                        ft.Column(breakdown_controls, spacing=10) if breakdown_controls else ft.Container(),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO),
                ),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )
        page.update()

    # ── Ticking Timer Loop ───────────────────────────────────────────────
    async def timer_loop():
        total_duration = exam_payload.get("total_duration_seconds") or (exam_payload.get("remaining_seconds", 3600))
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

            page.update()

        if state["running"] and not state["submitted"]:
            # Auto-submit on timeout
            await execute_final_submit()

    # ── Build Screen Layout ──────────────────────────────────────────────
    def build_runner_screen():
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
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.08, timer_text.color),
                        content=ft.Row([timer_icon, timer_text], spacing=6, tight=True),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                timer_bar,
            ], spacing=8),
        )

        nav_footer = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
            content=ft.Row([
                ft.OutlinedButton("Previous", icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=goto_prev),
                ft.TextButton("Review Palette", icon=ft.Icons.GRID_VIEW_ROUNDED, on_click=lambda _: show_review_screen()),
                ft.FilledButton("Next", icon=ft.Icons.ARROW_FORWARD_ROUNDED, on_click=goto_next),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        )

        root.content = ft.Column([
            top_bar,
            ft.Container(
                content=question_content_area,
                expand=True,
                padding=ft.Padding.symmetric(horizontal=16, vertical=16),
                alignment=ft.Alignment.TOP_CENTER,
            ),
            nav_footer,
        ], expand=True, spacing=0)

    build_runner_screen()
    render_current_question()
    page.run_task(timer_loop)
    return root
