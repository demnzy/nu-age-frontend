"""
Dedicated Full-Page Cohort Examination View.
Provides an addressable route (/cohorts/:cohort_id/exams/:exam_id) for candidate exams:
  * Restores cleanly on page refresh or browser reload.
  * Ensures fullscreen / kiosk security is bound specifically to this active route.
  * Resolves organization ID gracefully from query parameters or cohort memberships.
  * Handles errors (e.g. attempt limits, window closed) with clear guidance.
"""

from typing import Optional
import urllib.parse
import flet as ft

from src.requests.Cohorts import get_learner_cohorts, start_cohort_exam
from src.components.cohort_exam_runner import build_cohort_exam_view


async def cohort_exam_page_view(
    page: ft.Page,
    cohort_id: str,
    exam_id: str,
    org_id: Optional[str] = None,
    back_target: Optional[str] = None,
) -> ft.View:
    current_route = f"/cohorts/{cohort_id}/exams/{exam_id}"
    effective_back = back_target or f"/cohorts/{cohort_id}"

    token = None
    try:
        token = await page.shared_preferences.get("auth_token")
    except Exception:
        token = None

    if not token:
        return ft.View(
            route=current_route,
            controls=[
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column([
                        ft.Icon(ft.Icons.LOCK_ROUNDED, size=48, color=ft.Colors.AMBER_700),
                        ft.Text("Authentication Required", size=18, weight=ft.FontWeight.BOLD),
                        ft.Text("Please log in to access this assessment.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.FilledButton("Log In", on_click=lambda _: page.go("/login")),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                )
            ],
            padding=0,
        )

    # 1. Resolve org_id from query params if not provided directly
    if not org_id:
        try:
            parsed = urllib.parse.urlparse(page.route or "")
            qs = urllib.parse.parse_qs(parsed.query)
            if "org_id" in qs and qs["org_id"]:
                org_id = qs["org_id"][0]
        except Exception:
            pass

    # 2. If still missing, look up org_id from learner's enrolled cohorts
    if not org_id:
        try:
            res = await get_learner_cohorts(token)
            for c in res.get("cohorts", []):
                if str(c.get("id")) == str(cohort_id):
                    org_id = str(c.get("organisation_id") or c.get("org_id") or "")
                    break
        except Exception:
            pass

    if not org_id:
        return ft.View(
            route=page.route,
            controls=[
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    padding=24,
                    content=ft.Container(
                        width=460,
                        padding=28,
                        border_radius=16,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                        content=ft.Column([
                            ft.Icon(ft.Icons.HELP_OUTLINE_ROUNDED, size=40, color=ft.Colors.AMBER_700),
                            ft.Text("Cohort Not Found", size=18, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Unable to determine the organization associated with this cohort. Please return to your cohorts list.",
                                size=12, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER,
                            ),
                            ft.FilledButton("Return to Cohorts", icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda _: page.go("/cohorts")),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    ),
                )
            ],
            padding=0,
        )

    # 3. Call start_cohort_exam to begin or resume the attempt
    payload = await start_cohort_exam(token, str(org_id), str(cohort_id), str(exam_id))

    if "error" in payload:
        err_msg = str(payload.get("error", "Unable to start assessment."))
        return ft.View(
            route=current_route,
            controls=[
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    padding=24,
                    content=ft.Container(
                        width=480,
                        padding=32,
                        border_radius=18,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                        content=ft.Column([
                            ft.Container(
                                width=56, height=56, border_radius=28,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_700),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, size=28, color=ft.Colors.AMBER_700),
                            ),
                            ft.Text("Assessment Unavailable", size=18, weight=ft.FontWeight.BOLD),
                            ft.Text(err_msg, size=13, color=ft.Colors.ON_SURFACE, text_align=ft.TextAlign.CENTER),
                            ft.Text(
                                "If you need an additional attempt or have questions about your assessment window, please reach out to your instructor or cohort administrator.",
                                size=11, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=10),
                            ft.FilledButton(
                                "Return to Cohort",
                                icon=ft.Icons.ARROW_BACK_ROUNDED,
                                on_click=lambda _: page.go(effective_back),
                                style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=22, vertical=12)),
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    ),
                )
            ],
            padding=0,
        )

    # 4. Safe exit handler that pops back to cohort
    def on_exit_exam(*_):
        try:
            w = getattr(page, "window", None)
            if w:
                w.full_screen = False
                w.prevent_close = False
        except Exception:
            pass
        page.go(effective_back)

    # 5. Build full exam runner
    exam_runner_content = build_cohort_exam_view(
        page=page,
        exam_payload=payload,
        org_id=str(org_id),
        cohort_id=str(cohort_id),
        exam_id=str(exam_id),
        token=token,
        on_exit=on_exit_exam,
    )

    return ft.View(
        route=current_route,
        controls=[exam_runner_content],
        padding=0,
    )
