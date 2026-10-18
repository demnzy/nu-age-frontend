"""
Enterprise-Grade CBT Examination Engine
Provides a summative Computer-Based Test (CBT) simulator modeled after
JAMB UTME, WAEC WASSCE, and NECO conventions.

Key Architecture:
- Single outer scroll container with sticky top HUD (zero nested ListViews or unbounded flex rows).
- Centered bounded layout (width=780 on desktop, fluid on mobile) preventing Flutter RenderFlex crashes.
- Floating dockable calculator integrated with the app's standard exam_calculator component.
- Strictly theme-driven via Flet theme tokens (ft.Colors.PRIMARY / SURFACE / ON_SURFACE)
  matching NU-Age's brand identity across Light and Dark modes.
- High-contrast options (A-E), keyboard hotkeys, and dynamic diagram zoom lightbox.
- Resilient image extraction supporting image_url, diagram_url, image, diagram, figure,
  and embedded markdown ![...](url) illustrations.
- Clean candidate terminal header (no fake seat badges).
- Multi-Subject architecture:
  - JAMB UTME: Simultaneous multi-subject sections (English, Maths, Physics, Chemistry)
    under a unified countdown timer, yielding an official aggregate score out of 400.
  - WAEC WASSCE / NECO: Multi-subject paper tracking culminating in an official
    WAEC 9-point Result Slip (A1-F9) and credit pass qualification count.
  - Strict grading parity: Zero WAEC grades on JAMB reports, zero JAMB aggregates on WAEC reports.
- Longitudinal Attempt Tracking & Score Trajectory Charts persisted via local SQLite.
"""

import json
import math
import re
import time
from typing import List, Dict, Any, Callable, Optional
import flet as ft
from src.components import study_ui as ui
from src.components.exam_calculator import build_exam_calculator
from src.local_db import record_exam_attempt, get_exam_attempts

_LETTERS = ["A", "B", "C", "D", "E"]
_DEFAULT_API_BASE = "https://api.nu-age.name.ng"


def _normalize_image_url(url: Optional[str]) -> Optional[str]:
    """Ensures diagram image URLs have a valid absolute scheme and host."""
    if not url:
        return None
    cleaned = str(url).strip()
    if not cleaned:
        return None
    if cleaned.startswith("http://") or cleaned.startswith("https://") or cleaned.startswith("data:"):
        return cleaned
    if cleaned.startswith("/"):
        return f"{_DEFAULT_API_BASE}{cleaned}"
    return f"{_DEFAULT_API_BASE}/{cleaned}"


def _extract_image_url(q: Dict[str, Any]) -> Optional[str]:
    """Resiliently resolves illustration image URL from any known property or markdown."""
    url = (
        q.get("image_url")
        or q.get("diagram_url")
        or q.get("image")
        or q.get("diagram")
        or q.get("figure")
    )
    if not url:
        txt = str(q.get("question_text") or q.get("question") or "")
        m = re.search(r'!\[.*?\]\((https?://[^\s\)]+|/[^\s\)]+)\)', txt)
        if m:
            url = m.group(1)
    return _normalize_image_url(url)


def _clean_question_text(q: Dict[str, Any]) -> str:
    """Removes embedded markdown image tags and difficulty tag prefixes from question text to prevent double-rendering."""
    txt = str(q.get("question_text") or q.get("question") or "")
    clean = re.sub(r'!\[.*?\]\((https?://[^\s\)]+|/[^\s\)]+)\)', '', txt).strip()
    clean = re.sub(
        r'^\s*[\(\[]?\s*(?:exam[\s\-_]?level|tricky|straightforward|easy|medium|hard)\s*[\)\]]?[\s:\-–—]*',
        '',
        clean,
        flags=re.IGNORECASE
    ).strip()
    return clean or "*(No question text provided)*"


def _get_jamb_tier(aggregate: int) -> tuple[str, str, str]:
    """Returns JAMB UTME performance tier, description, and hex color based on aggregate / 400."""
    if aggregate >= 300:
        return (
            "Top Merit Distinction (300+ / 400)",
            "Exceptionally competitive for Medicine, Law, and Engineering at Premier Universities.",
            "#059669",
        )
    elif aggregate >= 240:
        return (
            "Competitive Tier (240 - 299 / 400)",
            "Strong competitive benchmark meeting high-demand faculty entry requirements.",
            "#2563EB",
        )
    elif aggregate >= 180:
        return (
            "Acceptable Cut-off Tier (180 - 239 / 400)",
            "Meets standard Federal and State tertiary institution cut-off benchmarks.",
            "#D97706",
        )
    else:
        return (
            "Below Cut-off Tier (< 180 / 400)",
            "Below competitive threshold. Intensive revision recommended.",
            "#DC2626",
        )


def _get_waec_grade(percentage: float) -> tuple[str, str, bool, str]:
    """Returns WAEC / NECO 9-Point Scale: (Grade, Label, IsCreditPass, HexColor)."""
    if percentage >= 75:
        return ("A1", "Excellent", True, "#059669")
    elif percentage >= 70:
        return ("B2", "Very Good", True, "#047857")
    elif percentage >= 65:
        return ("B3", "Good", True, "#0D9488")
    elif percentage >= 60:
        return ("C4", "Credit", True, "#2563EB")
    elif percentage >= 55:
        return ("C5", "Credit", True, "#3B82F6")
    elif percentage >= 50:
        return ("C6", "Credit", True, "#60A5FA")
    elif percentage >= 45:
        return ("D7", "Pass", False, "#D97706")
    elif percentage >= 40:
        return ("E8", "Pass", False, "#F59E0B")
    else:
        return ("F9", "Fail", False, "#DC2626")


class CBTExamEngine:
    """
    Enterprise Summative CBT Exam Engine.
    Uses a robust single-scroll architecture with bounded layout to prevent Flutter layout crashes.
    Strictly follows application theme tokens (PRIMARY, SURFACE, ON_SURFACE).
    """
    def __init__(
        self,
        page: ft.Page,
        questions: List[Dict[str, Any]],
        duration_seconds: Optional[int] = None,
        exam_title: str = "CBT Past Questions Examination",
        exam_type: str = "General CBT",
        exam_year: Optional[int] = None,
        candidate_name: str = "Student Candidate",
        material_id: Optional[str] = None,
        bundle_id: Optional[str] = None,
        on_exit: Optional[Callable[[], None]] = None,
        on_restart: Optional[Callable[[], None]] = None,
    ):
        self.page = page
        self.raw_questions = questions or []
        self.total = len(self.raw_questions)
        self.exam_title = exam_title
        self.exam_type = exam_type
        self.exam_year = exam_year
        self.candidate_name = candidate_name or "Student Candidate"
        self.material_id = material_id
        self.bundle_id = bundle_id
        self.on_exit = on_exit
        self.on_restart = on_restart

        # Organize questions and detect subjects
        self.subjects: List[str] = []
        for q in self.raw_questions:
            s_name = q.get("subject") or q.get("material_title") or "General Syllabus"
            if s_name not in self.subjects:
                self.subjects.append(s_name)

        # Duration setup
        if duration_seconds and duration_seconds > 0:
            self.total_seconds = int(duration_seconds)
        else:
            self.total_seconds = max(self.total * 60, 300)

        self.remaining_seconds = self.total_seconds
        self.time_started = time.time()
        self.is_running = True
        self.active_index = 0

        # State dictionaries
        self.answers: Dict[int, int] = {}
        self.flags: set[int] = set()
        self.question_times: Dict[int, int] = {}
        self.current_q_enter_time = time.time()

        # Calculator state
        self.calc_mode = "scientific"

        screen_width = getattr(self.page, "width", None) or 800
        self.is_mobile = screen_width < 768

        # Build root layout - inherits page background cleanly
        self.root = ft.Container(expand=True)
        self._init_ui()

    def _init_ui(self):
        if self.total == 0:
            self.root.content = ui.empty_state(
                ft.Icons.ASSIGNMENT_OUTLINED,
                "No CBT exam questions found",
                "This study material has no practice questions available.",
                "Back to Study Hub",
                self.on_exit or (lambda: None),
            )
            return

        screen_width = self.page.width or 800
        self.is_mobile = screen_width < 768

        # ── 1. Top HUD Sticky Controls ──
        self.timer_text = ft.Text(
            self._format_time(self.remaining_seconds),
            size=16 if not self.is_mobile else 14,
            weight=ft.FontWeight.W_900,
            color=ft.Colors.PRIMARY,
            font_family="monospace",
        )
        self.timer_icon = ft.Icon(ft.Icons.TIMER_ROUNDED, size=16, color=ft.Colors.PRIMARY)
        self.timer_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=ft.BorderRadius.all(10),
            bgcolor=ui.tint(ft.Colors.PRIMARY, 0.12),
            border=ft.Border.all(1.2, ft.Colors.PRIMARY),
            content=ft.Row([
                self.timer_icon,
                self.timer_text,
            ], spacing=6, tight=True),
        )

        self.progress_pill_text = ft.Text(
            f"0/{self.total} Answered",
            size=11,
            weight=ft.FontWeight.W_700,
            color=ui.muted(),
        )

        self.calc_btn = ft.IconButton(
            icon=ft.Icons.CALCULATE_ROUNDED,
            icon_size=20,
            icon_color=ft.Colors.PRIMARY,
            tooltip="Open In-Exam Calculator",
            bgcolor=ui.tint(ft.Colors.PRIMARY, 0.10),
            on_click=self._toggle_calculator,
        )

        # ── 2. Multi-Subject Sticky Navigation Bar ──
        self.subject_tabs_bar = ft.Container()
        self._render_subject_tabs()

        # ── 3. Active Question Controls ──
        self.q_counter_badge = ft.Text("Question 1", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY)
        self.q_subject_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ui.tint(ft.Colors.PRIMARY, 0.12),
            border=ft.Border.all(1, ui.tint(ft.Colors.PRIMARY, 0.30)),
            content=ft.Text("", size=10.5, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
            visible=False,
        )
        self.q_topic_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.06),
            border=ft.Border.all(1, ui.hairline()),
            content=ft.Text("", size=10, weight=ft.FontWeight.W_700, color=ui.muted()),
            visible=False,
        )

        self.flag_action_btn = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=ft.BorderRadius.all(8),
            bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.06),
            border=ft.Border.all(1, ui.hairline()),
            ink=True,
            on_click=self._toggle_flag,
            content=ft.Row([
                ft.Icon(ft.Icons.OUTLINED_FLAG_ROUNDED, size=15, color=ui.muted()),
                ft.Text("Flag for Review", size=11, weight=ft.FontWeight.W_700, color=ui.muted()),
            ], spacing=5, tight=True),
        )

        self.question_markdown = ft.Markdown(
            "",
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            selectable=True,
        )

        self.diagram_container = ft.Container(visible=False)
        self.options_column = ft.Column(spacing=10)

        # Navigation controls
        self.prev_btn = ft.OutlinedButton(
            content=ft.Row([
                ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=15),
                ft.Text("Previous (P)", size=12, weight=ft.FontWeight.W_700),
            ], spacing=5, tight=True),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, ui.hairline()),
                color=ft.Colors.ON_SURFACE,
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            ),
            on_click=lambda _: self._goto_prev(),
        )

        self.next_btn = ft.FilledButton(
            content=ft.Row([
                ft.Text("Next (N)", size=12, weight=ft.FontWeight.W_700),
                ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=15),
            ], spacing=5, tight=True),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
                color=ft.Colors.ON_PRIMARY,
                padding=ft.Padding.symmetric(horizontal=18, vertical=12),
            ),
            on_click=lambda _: self._goto_next(),
        )

        self.review_btn = ft.OutlinedButton(
            content=ft.Row([
                ft.Icon(ft.Icons.FACT_CHECK_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                ft.Text("Review & Submit", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
            ], spacing=5, tight=True),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1.2, ft.Colors.PRIMARY),
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            ),
            on_click=lambda _: self._show_pre_submission_dialog(),
        )

        # Matrix Palette controls
        self.matrix_grid = ft.Row(wrap=True, spacing=6, run_spacing=6)
        self.matrix_filter = ["all"]

        # Calculator overlay container (integrated from src.components.exam_calculator)
        self.calc_overlay = ft.Container(
            visible=False,
            top=60,
            right=20 if not self.is_mobile else None,
            left=20 if self.is_mobile else None,
        )

        self._assemble_view()
        self._render_active_question()
        self._render_matrix_palette()

        # Wire keyboard shortcuts (N=Next, P=Prev, A-E=Options, F/R=Flag, S=Submit)
        self._prev_key_handler = getattr(self.page, "on_keyboard_event", None)
        self.page.on_keyboard_event = self._on_key_event

        # Launch countdown timer
        self.page.run_task(self._countdown_loop)

    def _assemble_view(self):
        screen_width = self.page.width or 800
        self.is_mobile = screen_width < 768

        # ── 1. Top HUD Sticky Header (Clean Candidate Header) ──
        exam_badge = f"{self.exam_type} {self.exam_year or ''}".strip()
        self.top_header = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.only(bottom=ft.BorderSide(1, ui.hairline())),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row([
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            icon_size=18,
                            icon_color=ft.Colors.ON_SURFACE,
                            tooltip="Exit CBT Simulation",
                            on_click=lambda _: self._confirm_exit_exam(),
                        ),
                        ft.Container(
                            width=36,
                            height=36,
                            border_radius=ft.BorderRadius.all(10),
                            gradient=ft.LinearGradient(
                                colors=[ft.Colors.PRIMARY, ft.Colors.SECONDARY],
                                begin=ft.Alignment.TOP_LEFT,
                                end=ft.Alignment.BOTTOM_RIGHT,
                            ),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.SCHOOL_ROUNDED, color=ft.Colors.ON_PRIMARY, size=18),
                        ),
                        ft.Column([
                            ft.Text(self.exam_title, size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(f"{exam_badge} • Candidate: {self.candidate_name}", size=10.5, color=ui.muted()),
                        ], spacing=1, tight=True, expand=True if self.is_mobile else False),
                    ], spacing=6, tight=True, expand=True if self.is_mobile else False),
                    ft.Row([
                        self.calc_btn,
                        self.timer_container,
                    ], spacing=8, tight=True),
                ],
            ),
        )

        # ── 2. Question Surface Card ──
        q_header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row([
                    self.q_counter_badge,
                    self.q_subject_badge,
                    self.q_topic_badge,
                ], spacing=6, tight=True, wrap=True),
                self.flag_action_btn,
            ],
        )

        question_card = ft.Container(
            padding=ft.Padding.all(18),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ui.hairline()),
            content=ft.Column([
                q_header,
                ft.Container(height=4),
                self.question_markdown,
                self.diagram_container,
                ft.Container(height=8),
                self.options_column,
            ], spacing=12, tight=True),
        )

        # Question Action Bar
        action_bar = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self.prev_btn,
                ft.Row([
                    self.review_btn,
                    self.next_btn,
                ], spacing=8, tight=True),
            ],
        )

        # ── 3. Matrix Palette Card ──
        palette_card = ft.Container(
            padding=ft.Padding.all(16),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ui.hairline()),
            content=ft.Column([
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Question Matrix", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                        self.progress_pill_text,
                    ],
                ),
                self._build_matrix_filter_chips(),
                self.matrix_grid,
                ft.Divider(height=1, color=ui.hairline()),
                self._build_palette_legend(),
            ], spacing=10, tight=True),
        )

        # ── 4. Main Scroll Column (Single-Tree, Bounded Width) ──
        content_column = ft.Column(
            spacing=16,
            controls=[
                question_card,
                action_bar,
                palette_card,
                ui.ghost_button(
                    "Review All Answers & Submit",
                    lambda _: self._show_pre_submission_dialog(),
                    icon=ft.Icons.FACT_CHECK_ROUNDED,
                    color=ft.Colors.PRIMARY,
                    expand=True,
                ),
                ft.Container(height=30),
            ],
        )

        bounded_canvas = ft.Container(
            alignment=ft.Alignment.TOP_CENTER,
            padding=ft.Padding.symmetric(
                horizontal=12 if self.is_mobile else 24,
                vertical=16,
            ),
            content=ft.Container(
                width=None if self.is_mobile else 780,
                content=content_column,
            ),
        )

        self.main_scroll_area = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[bounded_canvas],
        )

        self.main_view = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                self.top_header,
                self.subject_tabs_bar,
                self.main_scroll_area,
            ],
        )

        self.main_container = ft.Container(
            expand=True,
            content=self.main_view,
        )

        self.root.content = ft.Stack(
            expand=True,
            controls=[
                self.main_container,
                self.calc_overlay,
            ],
        )

    # ── MULTI-SUBJECT NAVIGATION TABS ──
    def _render_subject_tabs(self):
        """Renders sticky horizontal subject tabs when multiple subjects are present."""
        if len(self.subjects) <= 1:
            self.subject_tabs_bar.content = None
            self.subject_tabs_bar.visible = False
            return

        current_q = self.raw_questions[self.active_index] if self.active_index < self.total else {}
        current_subj = current_q.get("subject") or current_q.get("material_title") or "General Syllabus"

        pills = []
        for s_name in self.subjects:
            is_active = (s_name == current_subj)
            s_total = sum(1 for q in self.raw_questions if (q.get("subject") or q.get("material_title") or "General Syllabus") == s_name)
            s_ans = sum(1 for idx, q in enumerate(self.raw_questions) if (q.get("subject") or q.get("material_title") or "General Syllabus") == s_name and idx in self.answers)

            pills.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ui.tint(ft.Colors.PRIMARY, 0.16) if is_active else ui.tint(ft.Colors.ON_SURFACE, 0.04),
                    border=ft.Border.all(1.4 if is_active else 1.0, ft.Colors.PRIMARY if is_active else ui.hairline()),
                    ink=True,
                    on_click=lambda _, s=s_name: self._switch_to_subject(s),
                    content=ft.Row([
                        ft.Text(
                            s_name,
                            size=11.5,
                            weight=ft.FontWeight.W_800 if is_active else ft.FontWeight.W_600,
                            color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE,
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            border_radius=ft.BorderRadius.all(6),
                            bgcolor=ft.Colors.PRIMARY if is_active else ui.tint(ft.Colors.ON_SURFACE, 0.08),
                            content=ft.Text(
                                f"{s_ans}/{s_total}",
                                size=10,
                                weight=ft.FontWeight.W_700,
                                color=ft.Colors.ON_PRIMARY if is_active else ui.muted(),
                            ),
                        ),
                    ], spacing=6, tight=True),
                )
            )

        self.subject_tabs_bar.content = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            bgcolor=ui.tint(ft.Colors.SURFACE, 0.96),
            border=ft.Border.only(bottom=ft.BorderSide(1, ui.hairline())),
            content=ft.Row(
                scroll=ft.ScrollMode.ADAPTIVE,
                controls=pills,
                spacing=8,
            ),
        )
        self.subject_tabs_bar.visible = True

    def _switch_to_subject(self, subject_name: str):
        """Jumps directly to the first question in the designated subject section."""
        for idx, q in enumerate(self.raw_questions):
            s = q.get("subject") or q.get("material_title") or "General Syllabus"
            if s == subject_name:
                self.active_index = idx
                self._render_active_question()
                self._render_matrix_palette()
                self._render_subject_tabs()
                self.page.update()
                break

    def _render_active_question(self):
        """Renders the question at active_index with resilient illustration handling."""
        if not self.raw_questions or self.active_index >= self.total:
            return

        q = self.raw_questions[self.active_index]
        self.q_counter_badge.value = f"Question {self.active_index + 1} of {self.total}"

        # Subject badge (if multi-subject)
        subject = q.get("subject") or q.get("material_title")
        if len(self.subjects) > 1 and subject:
            self.q_subject_badge.content.value = str(subject).strip()
            self.q_subject_badge.visible = True
        else:
            self.q_subject_badge.visible = False

        # Topic badge
        topic = q.get("topic")
        if topic and str(topic).strip() and str(topic).strip() != str(subject).strip():
            self.q_topic_badge.content.value = str(topic).strip()
            self.q_topic_badge.visible = True
        else:
            self.q_topic_badge.visible = False

        # Flag button state
        is_flagged = self.active_index in self.flags
        self.flag_action_btn.bgcolor = ui.tint(ui.C_FLAG, 0.14) if is_flagged else ui.tint(ft.Colors.ON_SURFACE, 0.06)
        self.flag_action_btn.border = ft.Border.all(1, ui.C_FLAG if is_flagged else ui.hairline())
        self.flag_action_btn.content.controls[0].name = ft.Icons.FLAG_ROUNDED if is_flagged else ft.Icons.OUTLINED_FLAG_ROUNDED
        self.flag_action_btn.content.controls[0].color = ui.C_FLAG if is_flagged else ui.muted()
        self.flag_action_btn.content.controls[1].color = ui.C_FLAG if is_flagged else ui.muted()

        # Clean Question Markdown text (strips duplicate markdown images)
        clean_text = _clean_question_text(q)
        self.question_markdown.value = clean_text

        # Resilient Inline Diagram Extraction
        norm_img_url = _extract_image_url(q)
        if norm_img_url:
            self.diagram_container.content = ft.Container(
                padding=ft.Padding.all(10),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.04),
                border=ft.Border.all(1, ui.hairline()),
                ink=True,
                on_click=lambda _, u=norm_img_url: self._show_image_lightbox(u),
                tooltip="Tap to zoom illustration figure",
                content=ft.Column([
                    ft.Image(
                        src=norm_img_url,
                        fit=ft.BoxFit.CONTAIN,
                        height=200 if not self.is_mobile else 150,
                        border_radius=ft.BorderRadius.all(8),
                    ),
                    ft.Row([
                        ft.Icon(ft.Icons.ZOOM_IN_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                        ft.Text("Tap illustration to enlarge", size=10.5, color=ft.Colors.PRIMARY, weight=ft.FontWeight.W_600),
                    ], spacing=4, tight=True, alignment=ft.MainAxisAlignment.CENTER),
                ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )
            self.diagram_container.visible = True
        else:
            self.diagram_container.content = None
            self.diagram_container.visible = False

        # Options tiles
        self.options_column.controls.clear()
        raw_opts = q.get("options") or []
        if isinstance(raw_opts, str):
            try:
                raw_opts = json.loads(raw_opts)
            except Exception:
                raw_opts = [raw_opts]
        opts = list(raw_opts) if isinstance(raw_opts, (list, tuple)) else [str(raw_opts)]
        chosen_opt = self.answers.get(self.active_index)

        for i, opt_text in enumerate(opts):
            is_selected = (chosen_opt == i)
            self.options_column.controls.append(
                self._build_option_tile(i, str(opt_text), is_selected)
            )

        # Nav button states
        self.prev_btn.disabled = (self.active_index == 0)
        if self.active_index == self.total - 1:
            self.next_btn.content.controls[0].value = "Review & Submit"
            self.next_btn.content.controls[1].name = ft.Icons.FACT_CHECK_ROUNDED
        else:
            self.next_btn.content.controls[0].value = "Next (N)"
            self.next_btn.content.controls[1].name = ft.Icons.ARROW_FORWARD_ROUNDED

        self.progress_pill_text.value = f"{len(self.answers)}/{self.total} Answered"

    def _show_image_lightbox(self, url: str):
        """Displays modal high-resolution image zoom lightbox strictly bounded to the viewport."""
        screen_w = getattr(self.page, "width", None) or 800
        screen_h = getattr(self.page, "height", None) or 600
        dialog_w = min(screen_w - 32, 680)
        img_max_h = max(200, min(screen_h - 180, 480))

        lightbox_dlg = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE,
            content_padding=ft.Padding.all(16),
            shape=ft.RoundedRectangleBorder(radius=16),
        )

        header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.IMAGE_SEARCH_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                    ft.Text("Question Diagram Lightbox", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ], spacing=8, tight=True),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_color=ui.muted(),
                    icon_size=18,
                    tooltip="Close diagram view",
                    on_click=lambda _: self._close_dialog(lightbox_dlg),
                ),
            ],
        )

        lightbox_dlg.content = ft.Container(
            width=dialog_w,
            content=ft.Column([
                header,
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    content=ft.Image(
                        src=url,
                        fit=ft.BoxFit.CONTAIN,
                        height=img_max_h,
                        border_radius=ft.BorderRadius.all(10),
                    ),
                ),
            ], spacing=12, tight=True),
        )

        lightbox_dlg.open = True
        self.page.overlay.append(lightbox_dlg)
        self.page.update()

    def _build_option_tile(self, idx: int, text: str, is_selected: bool) -> ft.Container:
        """Tactile option tile (A-E) with high-contrast radio letter squircle and Markdown formatting support."""
        letter = _LETTERS[idx] if idx < len(_LETTERS) else str(idx + 1)
        bg = ui.tint(ft.Colors.PRIMARY, 0.12) if is_selected else ui.tint(ft.Colors.ON_SURFACE, 0.03)
        border_col = ft.Colors.PRIMARY if is_selected else ui.hairline()

        letter_squircle = ft.Container(
            width=32,
            height=32,
            border_radius=ft.BorderRadius.all(8),
            bgcolor=ft.Colors.PRIMARY if is_selected else ui.tint(ft.Colors.ON_SURFACE, 0.08),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                letter,
                size=12.5,
                weight=ft.FontWeight.W_900,
                color=ft.Colors.ON_PRIMARY if is_selected else ft.Colors.ON_SURFACE,
            ),
        )

        # Markdown option rendering to support formulas, superscripts, bold text, etc.
        option_markdown = ft.Markdown(
            str(text or ""),
            selectable=False,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            auto_follow_links=False,
            code_theme="atom-one-dark",
        )

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            border_radius=ft.BorderRadius.all(12),
            bgcolor=bg,
            border=ft.Border.all(1.4 if is_selected else 1.0, border_col),
            ink=True,
            on_click=lambda _, i=idx: self._select_option(i),
            content=ft.Row([
                letter_squircle,
                ft.Container(
                    content=option_markdown,
                    expand=True,
                ),
                *(
                    [ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18, color=ft.Colors.PRIMARY)]
                    if is_selected else []
                ),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _on_key_event(self, e: ft.KeyboardEvent):
        """Authentic CBT keyboard shortcuts: N=Next, P=Prev, A-E=Option, F/R=Flag, S=Submit, C=Calc."""
        if not self.is_running or not hasattr(e, "key"):
            return
        key_raw = (e.key or "").strip().lower()

        # Navigation
        if key_raw in ("n", "arrowright", "arrow_right", "right"):
            self._goto_next()
        elif key_raw in ("p", "arrowleft", "arrow_left", "left"):
            self._goto_prev()
        elif key_raw in ("f", "r"):
            self._toggle_flag()
        elif key_raw in ("s",):
            self._show_pre_submission_dialog()
        elif key_raw in ("c",):
            self._toggle_calculator()
        else:
            # Option selection A-E or numeric 1-5
            q = self.raw_questions[self.active_index] if self.active_index < self.total else {}
            opts_count = len(q.get("options") or [])
            if key_raw.isdigit() and 1 <= int(key_raw) <= opts_count:
                self._select_option(int(key_raw) - 1)
            elif len(key_raw) == 1 and key_raw.upper() in _LETTERS[:opts_count]:
                self._select_option(_LETTERS.index(key_raw.upper()))

    def _restore_keyboard_handler(self):
        """Safely detaches or restores previous keyboard event handler on simulation completion or exit."""
        try:
            if getattr(self.page, "on_keyboard_event", None) == self._on_key_event:
                self.page.on_keyboard_event = getattr(self, "_prev_key_handler", None)
        except Exception:
            pass

    def _confirm_exit_exam(self):
        """Displays modal confirmation before exiting an in-progress exam."""
        exit_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row([
                ft.Icon(ft.Icons.WARNING_ROUNDED, color=ui.C_WARN, size=20),
                ft.Text("Exit CBT Simulation?", size=15, weight=ft.FontWeight.W_800),
            ], spacing=8),
            content=ft.Text(
                "Are you sure you want to exit? Your exam timer and in-progress answers will not be saved.",
                size=12.5,
                color=ui.muted(),
            ),
            actions=[
                ft.TextButton("Continue Exam", on_click=lambda _: self._close_dialog(exit_dlg)),
                ft.FilledButton(
                    "Exit to Hub",
                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE),
                    on_click=lambda _: (self._close_dialog(exit_dlg), self._handle_direct_exit()),
                ),
            ],
        )
        exit_dlg.open = True
        self.page.overlay.append(exit_dlg)
        self.page.update()

    def _handle_direct_exit(self):
        self.is_running = False
        self._restore_keyboard_handler()
        if self.on_exit:
            self.on_exit()

    def _select_option(self, opt_idx: int):
        self.answers[self.active_index] = opt_idx
        self._render_active_question()
        self._render_matrix_palette()
        self._render_subject_tabs()
        self.page.update()

    def _toggle_flag(self, _=None):
        if self.active_index in self.flags:
            self.flags.discard(self.active_index)
        else:
            self.flags.add(self.active_index)
        self._render_active_question()
        self._render_matrix_palette()
        self.page.update()

    def _goto_prev(self):
        if self.active_index > 0:
            self.active_index -= 1
            self._render_active_question()
            self._render_matrix_palette()
            self._render_subject_tabs()
            self.page.update()

    def _goto_next(self):
        if self.active_index < self.total - 1:
            self.active_index += 1
            self._render_active_question()
            self._render_matrix_palette()
            self._render_subject_tabs()
            self.page.update()
        else:
            self._show_pre_submission_dialog()

    def _goto_question(self, index: int):
        if 0 <= index < self.total:
            self.active_index = index
            self._render_active_question()
            self._render_matrix_palette()
            self._render_subject_tabs()
            self.page.update()

    # ── MATRIX PALETTE ──
    def _build_matrix_filter_chips(self) -> ft.Row:
        def _chip(mode: str, label: str):
            is_active = (self.matrix_filter[0] == mode)
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=ui.tint(ft.Colors.PRIMARY, 0.18) if is_active else ui.tint(ft.Colors.ON_SURFACE, 0.05),
                border=ft.Border.all(1, ft.Colors.PRIMARY if is_active else ui.hairline()),
                ink=True,
                on_click=lambda _, m=mode: self._set_palette_filter(m),
                content=ft.Text(label, size=10, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY if is_active else ui.muted()),
            )

        return ft.Row([
            _chip("all", f"All ({self.total})"),
            _chip("answered", f"Ans ({len(self.answers)})"),
            _chip("unanswered", f"Blank ({self.total - len(self.answers)})"),
            _chip("flagged", f"Flagged ({len(self.flags)})"),
        ], spacing=6, wrap=True)

    def _set_palette_filter(self, mode: str):
        self.matrix_filter[0] = mode
        self._render_matrix_palette()
        self.page.update()

    def _render_matrix_palette(self):
        self.matrix_grid.controls.clear()
        mode = self.matrix_filter[0]

        for i in range(self.total):
            is_cur = (i == self.active_index)
            is_ans = (i in self.answers)
            is_flg = (i in self.flags)

            if mode == "answered" and not is_ans:
                continue
            if mode == "unanswered" and is_ans:
                continue
            if mode == "flagged" and not is_flg:
                continue

            if is_cur:
                bg = ft.Colors.PRIMARY
                border = ft.Colors.PRIMARY
                text_col = ft.Colors.ON_PRIMARY
            elif is_flg:
                bg = ui.tint(ui.C_FLAG, 0.20)
                border = ui.C_FLAG
                text_col = ui.C_FLAG
            elif is_ans:
                bg = ui.tint(ui.C_CORRECT, 0.18)
                border = ui.C_CORRECT
                text_col = ui.C_CORRECT
            else:
                bg = ui.tint(ft.Colors.ON_SURFACE, 0.04)
                border = ui.hairline()
                text_col = ui.muted()

            self.matrix_grid.controls.append(
                ft.Container(
                    width=32,
                    height=32,
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=bg,
                    border=ft.Border.all(1.4 if is_cur else 1.0, border),
                    alignment=ft.Alignment.CENTER,
                    ink=True,
                    on_click=lambda _, idx=i: self._goto_question(idx),
                    content=ft.Text(
                        str(i + 1),
                        size=11,
                        weight=ft.FontWeight.W_800 if is_cur else ft.FontWeight.W_600,
                        color=text_col,
                    ),
                )
            )
        self.progress_pill_text.value = f"{len(self.answers)}/{self.total} Answered"

    def _build_palette_legend(self) -> ft.Row:
        def _item(color: str, label: str):
            return ft.Row([
                ft.Container(width=10, height=10, border_radius=ft.BorderRadius.all(3), bgcolor=color),
                ft.Text(label, size=10, color=ui.muted()),
            ], spacing=4, tight=True)

        return ft.Row([
            _item(ft.Colors.PRIMARY, "Active"),
            _item(ui.C_CORRECT, "Answered"),
            _item(ui.C_FLAG, "Flagged"),
            _item(ui.hairline(), "Unanswered"),
        ], spacing=10, wrap=True)

    # ── CALCULATOR OVERLAY (INTEGRATED FROM exam_calculator.py) ──
    def _toggle_calculator(self, _=None):
        self.calc_overlay.visible = not self.calc_overlay.visible
        if self.calc_overlay.visible:
            self._render_calculator()
        self.page.update()

    def _toggle_calc_mode(self, _=None):
        self.calc_mode = "basic" if self.calc_mode == "scientific" else "scientific"
        self._render_calculator()
        self.page.update()

    def _render_calculator(self):
        self.calc_overlay.content = build_exam_calculator(
            page=self.page,
            calculator_type=self.calc_mode,
            on_close=self._toggle_calculator,
            on_toggle_mode=self._toggle_calc_mode,
        )

    # ── TIMER LOOP ──
    async def _countdown_loop(self):
        import asyncio
        while self.is_running and self.remaining_seconds > 0:
            await asyncio.sleep(1)
            if not self.is_running:
                break
            self.remaining_seconds -= 1

            # Update timer text
            self.timer_text.value = self._format_time(self.remaining_seconds)

            # Progressive ambient color triggers
            if self.remaining_seconds <= 120:
                self.timer_text.color = ui.C_WRONG
                self.timer_icon.color = ui.C_WRONG
                self.timer_container.bgcolor = ui.tint(ui.C_WRONG, 0.18)
                self.timer_container.border = ft.Border.all(1.2, ui.C_WRONG)
            elif self.remaining_seconds <= 300:
                self.timer_text.color = ui.C_WARN
                self.timer_icon.color = ui.C_WARN
                self.timer_container.bgcolor = ui.tint(ui.C_WARN, 0.14)
                self.timer_container.border = ft.Border.all(1.2, ui.C_WARN)

            self.page.update()

        # Handle auto-submission on timeout
        if self.is_running and self.remaining_seconds <= 0:
            self.is_running = False
            self._submit_exam(is_auto_timeout=True)

    def _format_time(self, seconds: int) -> str:
        mins, secs = divmod(max(0, seconds), 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            return f"{hrs:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    # ── PRE-SUBMISSION AUDIT DIALOG ──
    def _show_pre_submission_dialog(self):
        """Displays review dialog summarizing answered, unanswered, and flagged questions."""
        answered_count = len(self.answers)
        unanswered_count = self.total - answered_count
        flagged_count = len(self.flags)

        screen_w = self.page.width or 800
        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE,
            content_padding=ft.Padding.all(20),
            shape=ft.RoundedRectangleBorder(radius=16),
        )

        header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.FACT_CHECK_ROUNDED, size=20, color=ft.Colors.PRIMARY),
                    ft.Text("Exam Audit & Confirmation", size=15, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                ], spacing=8, tight=True),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_color=ui.muted(),
                    icon_size=18,
                    on_click=lambda _: self._close_dialog(dlg),
                ),
            ],
        )

        body = ft.Container(
            padding=ft.Padding.only(top=14),
            content=ft.Column([
                ft.Text(
                    f"You have answered {answered_count} of {self.total} questions across {len(self.subjects)} subject section(s). Please review your summary before finalizing your submission.",
                    size=12.5,
                    color=ui.muted(),
                ),
                ft.Row([
                    self._audit_stat_tile("Total", str(self.total), ui.C_INFO),
                    self._audit_stat_tile("Answered", str(answered_count), ui.C_CORRECT),
                    self._audit_stat_tile("Blank", str(unanswered_count), ui.C_WRONG if unanswered_count > 0 else ui.muted()),
                    self._audit_stat_tile("Flagged", str(flagged_count), ui.C_FLAG),
                ], spacing=8),
                *(
                    [
                        ft.Container(
                            padding=ft.Padding.all(10),
                            border_radius=ft.BorderRadius.all(8),
                            bgcolor=ui.tint(ui.C_WARN, 0.12),
                            border=ft.Border.all(1, ui.tint(ui.C_WARN, 0.30)),
                            content=ft.Row([
                                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=16, color=ui.C_WARN),
                                ft.Text(
                                    f"Attention: {unanswered_count} questions are left unanswered!",
                                    size=11.5,
                                    weight=ft.FontWeight.W_700,
                                    color=ui.C_WARN,
                                ),
                            ], spacing=6),
                        )
                    ] if unanswered_count > 0 else []
                ),
                ft.Row([
                    ft.OutlinedButton(
                        "Return to Test",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side=ft.BorderSide(1, ui.hairline()),
                            color=ft.Colors.ON_SURFACE,
                        ),
                        on_click=lambda _: self._close_dialog(dlg),
                        expand=True,
                    ),
                    ft.FilledButton(
                        "Confirm & Submit",
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PRIMARY,
                            shape=ft.RoundedRectangleBorder(radius=10),
                            color=ft.Colors.ON_PRIMARY,
                        ),
                        on_click=lambda _: self._confirm_and_submit_exam(dlg),
                        expand=True,
                    ),
                ], spacing=10),
            ], spacing=14, tight=True),
        )

        dlg.content = ft.Container(
            width=min(screen_w - 32, 460),
            content=ft.Column([header, body], spacing=0, tight=True),
        )

        dlg.open = True
        self.page.overlay.append(dlg)
        self.page.update()

    def _audit_stat_tile(self, label: str, value: str, color: str) -> ft.Container:
        return ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(vertical=10),
            border_radius=ft.BorderRadius.all(10),
            bgcolor=ui.tint(color, 0.12),
            border=ft.Border.all(1, ui.tint(color, 0.25)),
            content=ft.Column([
                ft.Text(value, size=18, weight=ft.FontWeight.W_900, color=color),
                ft.Text(label, size=10, weight=ft.FontWeight.W_700, color=color),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
        )

    def _confirm_and_submit_exam(self, dlg: ft.AlertDialog):
        """Atomically closes audit dialog and initiates exam submission."""
        dlg.open = False
        self._submit_exam(is_auto_timeout=False)

    def _close_dialog(self, dlg: ft.AlertDialog):
        dlg.open = False
        self.page.update()

    # ── SUBMISSION & DIAGNOSTIC REPORT ENGINE ──
    def _submit_exam(self, is_auto_timeout: bool = False):
        self.is_running = False
        self._restore_keyboard_handler()
        elapsed_seconds = int(time.time() - self.time_started)

        # 1. Calculate Results, Subject breakdowns & Topic Mastery
        score = 0
        subject_stats: Dict[str, Dict[str, int]] = {}
        topic_stats: Dict[str, Dict[str, int]] = {}
        question_review_records = []

        for i, q in enumerate(self.raw_questions):
            try:
                correct_idx = int(q.get("answer_index", q.get("answer", 0)))
            except (ValueError, TypeError):
                correct_idx = 0

            chosen_idx = self.answers.get(i)
            is_correct = (chosen_idx == correct_idx)
            if is_correct:
                score += 1

            s_key = q.get("subject") or q.get("material_title") or "General Syllabus"
            if s_key not in subject_stats:
                subject_stats[s_key] = {"correct": 0, "total": 0}
            subject_stats[s_key]["total"] += 1
            if is_correct:
                subject_stats[s_key]["correct"] += 1

            topic_key = q.get("topic") or "General Syllabus"
            if topic_key not in topic_stats:
                topic_stats[topic_key] = {"correct": 0, "total": 0}
            topic_stats[topic_key]["total"] += 1
            if is_correct:
                topic_stats[topic_key]["correct"] += 1

            # Resiliently normalize options list
            raw_opts = q.get("options") or []
            if isinstance(raw_opts, str):
                try:
                    raw_opts = json.loads(raw_opts)
                except Exception:
                    raw_opts = [raw_opts]
            opts_list = list(raw_opts) if isinstance(raw_opts, (list, tuple)) else [str(raw_opts)]

            question_review_records.append({
                "index": i + 1,
                "question": _clean_question_text(q),
                "question_text": _clean_question_text(q),
                "options": opts_list,
                "correct_index": correct_idx,
                "chosen_index": chosen_idx,
                "is_correct": is_correct,
                "explanation": q.get("explanation", ""),
                "subject": s_key,
                "topic": topic_key,
                "image_url": _extract_image_url(q),
                "flagged": i in self.flags,
                "seconds": self.question_times.get(i, 0),
            })

        percentage = (score / self.total * 100.0) if self.total > 0 else 0.0

        # Exam Category Determination
        norm_type = (self.exam_type or "").upper()
        is_jamb = "JAMB" in norm_type or "UTME" in norm_type
        is_waec = any(k in norm_type for k in ["WAEC", "WASSCE", "NECO", "GCE", "SSCE"])

        # Compute Subject-level Scores
        subject_results = []
        jamb_aggregate_calc = 0
        waec_credit_passes = 0

        for s_name, s_info in subject_stats.items():
            s_cor = s_info["correct"]
            s_tot = s_info["total"]
            s_pct = (s_cor / s_tot * 100.0) if s_tot > 0 else 0.0
            s_scaled = round(s_pct)

            w_grade, w_label, w_is_credit, w_col = _get_waec_grade(s_pct)
            if w_is_credit:
                waec_credit_passes += 1

            subject_results.append({
                "subject": s_name,
                "correct": s_cor,
                "total": s_tot,
                "percentage": s_pct,
                "scaled_100": s_scaled,
                "waec_grade": w_grade,
                "waec_label": w_label,
                "waec_is_credit": w_is_credit,
                "waec_color": w_col,
            })
            jamb_aggregate_calc += s_scaled

        # Normalize JAMB aggregate based on number of subjects
        if is_jamb:
            num_subjs = len(subject_stats)
            if num_subjs == 4:
                final_jamb_aggregate = min(400, jamb_aggregate_calc)
            elif num_subjs > 0:
                final_jamb_aggregate = round((score / self.total) * 400.0)
            else:
                final_jamb_aggregate = 0
        else:
            final_jamb_aggregate = round((score / self.total) * 400.0)

        jamb_tier_title, jamb_tier_desc, jamb_tier_col = _get_jamb_tier(final_jamb_aggregate)

        overall_waec_grade, overall_waec_label, overall_waec_credit, overall_waec_col = _get_waec_grade(percentage)

        avg_seconds_per_q = round(elapsed_seconds / self.total) if self.total > 0 else 0

        # 2. Record Attempt to Local SQLite Database for Longitudinal Tracking
        past_attempts = []
        try:
            scaled_for_record = final_jamb_aggregate if is_jamb else round(percentage)
            grade_for_record = f"{waec_credit_passes} Credits" if is_waec else (f"{final_jamb_aggregate}/400" if is_jamb else f"{round(percentage)}%")
            record_exam_attempt(
                material_id=self.material_id,
                exam_title=self.exam_title,
                exam_type=self.exam_type,
                score=score,
                total=self.total,
                percentage=percentage,
                scaled_score=scaled_for_record,
                grade=grade_for_record,
                time_spent_seconds=elapsed_seconds,
                breakdown_json=json.dumps(subject_results),
                bundle_id=self.bundle_id,
                page=self.page,
            )
            past_attempts = get_exam_attempts(
                material_id=self.material_id,
                limit=10,
                page=self.page,
            )
        except Exception as e:
            print(f"[CBT] Error persisting attempt trajectory: {e}")

        # Asynchronously sync active partnership study progress and advance duo streak
        async def _sync_partnership_study():
            try:
                curr_tok = await self.page.shared_preferences.get("auth_token")
                if curr_tok:
                    from src.requests.study_partners import get_active_partnership, log_partnership_activity
                    p_res = await get_active_partnership(curr_tok)
                    if p_res and p_res.get("has_partnership"):
                        p_list = p_res.get("partnerships") or ([p_res.get("partnership")] if p_res.get("partnership") else [])
                        study_mins = max(1, elapsed_seconds // 60)
                        for p in p_list:
                            if p and p.get("id"):
                                await log_partnership_activity(curr_tok, p["id"], minutes_studied=study_mins, questions_solved=self.total)
            except Exception as p_err:
                print(f"[CBT] Error logging partnership activity: {p_err}")

        self.page.run_task(_sync_partnership_study)

        # 3. Build Proven Results UI using ui.build_results_view
        results_title = self.exam_title or f"{self.exam_type} Simulation"
        results = ui.build_results_view(
            self.page,
            title=results_title,
            accent=ft.Colors.PRIMARY,
            records=question_review_records,
            elapsed_seconds=elapsed_seconds,
            on_retry=self.on_restart or (lambda: None),
            on_exit=self.on_exit or (lambda: None),
            show_pass_band=True,
        )

        # Augment with CBT Summary Card (JAMB 400 aggregate / WAEC credit slips / subject breakdown)
        try:
            cbt_card = self._build_cbt_summary_card(
                score=score,
                percentage=percentage,
                is_jamb=is_jamb,
                is_waec=is_waec,
                jamb_aggregate=final_jamb_aggregate,
                jamb_tier_title=jamb_tier_title,
                jamb_tier_desc=jamb_tier_desc,
                jamb_tier_col=jamb_tier_col,
                waec_credit_passes=waec_credit_passes,
                overall_waec_grade=overall_waec_grade,
                overall_waec_label=overall_waec_label,
                overall_waec_credit=overall_waec_credit,
                overall_waec_col=overall_waec_col,
                subject_results=subject_results,
                past_attempts=past_attempts,
                topic_stats=topic_stats,
            )
            body = results.content.controls[0].content.content
            body.controls.insert(1, cbt_card)
        except Exception as ex:
            print(f"[CBT] Error augmenting results with cbt_card: {ex}")

        # Timeout banner if exam auto-submitted
        if is_auto_timeout:
            try:
                banner = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=11),
                    bgcolor=ui.tint(ui.C_WARN, 0.12),
                    border=ft.Border.only(bottom=ft.BorderSide(1, ui.tint(ui.C_WARN, 0.30))),
                    content=ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.ALARM_ROUNDED, size=17, color=ui.C_WARN),
                            ft.Text("Time's up — your CBT exam was submitted automatically.",
                                    size=12, weight=ft.FontWeight.W_700, color=ui.C_WARN),
                        ],
                    ),
                )
                body = results.content.controls[0].content.content
                body.controls.insert(0, banner)
            except Exception:
                pass

        # 4. Clean Direct Root Mount (guaranteed zero blank screens)
        self.calc_overlay.visible = False
        self.root.content = results
        self.page.update()

    def _build_cbt_summary_card(
        self,
        score: int,
        percentage: float,
        is_jamb: bool,
        is_waec: bool,
        jamb_aggregate: int,
        jamb_tier_title: str,
        jamb_tier_desc: str,
        jamb_tier_col: str,
        waec_credit_passes: int,
        overall_waec_grade: str,
        overall_waec_label: str,
        overall_waec_credit: bool,
        overall_waec_col: str,
        subject_results: List[Dict[str, Any]],
        past_attempts: List[Dict[str, Any]],
        topic_stats: Dict[str, Dict[str, int]],
    ) -> ft.Control:
        """Compact summary card displaying JAMB UTME / WAEC WASSCE scores and subject breakdown."""
        card_content = []

        if is_jamb:
            tier_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ui.tint(jamb_tier_col, 0.12),
                border=ft.Border.all(1, jamb_tier_col),
                content=ft.Column([
                    ft.Text(jamb_tier_title, size=12, weight=ft.FontWeight.W_800, color=jamb_tier_col),
                    ft.Text(jamb_tier_desc, size=10, color=ft.Colors.ON_SURFACE),
                ], spacing=2, tight=True),
            )

            score_block = ft.Column([
                ft.Row([
                    ft.Text(f"{jamb_aggregate}", size=36, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                    ft.Text("/ 400", size=18, weight=ft.FontWeight.W_800, color=ui.muted()),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                ft.Text("Official JAMB UTME Aggregate", size=11, weight=ft.FontWeight.W_700, color=ui.muted()),
            ], spacing=1, tight=True)

            card_content.append(
                ft.Row(
                    [score_block, tier_badge],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        elif is_waec:
            num_subjs = len(subject_results)
            qualifies = waec_credit_passes >= min(5, num_subjs)
            qual_col = ui.C_CORRECT if qualifies else ui.C_WARN
            qual_text = "Meets University Matriculation Standard (5+ Credits)" if qualifies else f"{waec_credit_passes} Credit(s) Passed • Deficiencies in {max(0, 5 - waec_credit_passes)} subject(s)"

            tier_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ui.tint(qual_col, 0.12),
                border=ft.Border.all(1, qual_col),
                content=ft.Column([
                    ft.Text(f"Overall Grade: {overall_waec_grade} ({overall_waec_label})", size=12, weight=ft.FontWeight.W_800, color=qual_col),
                    ft.Text(qual_text, size=10, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                ], spacing=2, tight=True),
            )

            score_block = ft.Column([
                ft.Row([
                    ft.Text(f"{waec_credit_passes}", size=36, weight=ft.FontWeight.W_900, color=qual_col),
                    ft.Text(f"/ {num_subjs} Credits", size=18, weight=ft.FontWeight.W_800, color=ui.muted()),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                ft.Text("WAEC / WASSCE Credit Passes (A1 - C6)", size=11, weight=ft.FontWeight.W_700, color=ui.muted()),
            ], spacing=1, tight=True)

            card_content.append(
                ft.Row(
                    [score_block, tier_badge],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        else:
            # General / Academic Simulation summary score block
            score_block = ft.Column([
                ft.Row([
                    ft.Text(f"{score}", size=36, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                    ft.Text(f"/ {self.total}", size=18, weight=ft.FontWeight.W_800, color=ui.muted()),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                ft.Text(f"{percentage:.1f}% Raw Accuracy", size=11, weight=ft.FontWeight.W_700, color=ui.muted()),
            ], spacing=1, tight=True)

            tier_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ui.tint(ft.Colors.PRIMARY, 0.12),
                border=ft.Border.all(1, ft.Colors.PRIMARY),
                content=ft.Column([
                    ft.Text("Exam Completed", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                    ft.Text(f"{score} of {self.total} correct", size=10, color=ft.Colors.ON_SURFACE),
                ], spacing=2, tight=True),
            )

            card_content.append(
                ft.Row(
                    [score_block, tier_badge],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        # Subject breakdown rows
        if subject_results and len(subject_results) > 1:
            card_content.append(ft.Divider(height=1, color=ui.hairline(0.12)))
            card_content.append(
                ft.Row([
                    ft.Icon(ft.Icons.SUBJECT_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                    ft.Text("Subject Breakdown", size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                ], spacing=6, tight=True)
            )

            subj_rows = []
            for s in subject_results:
                s_name = s.get("subject", "General")
                s_pct = s.get("percentage", 0.0)
                s_cor = s.get("correct", 0)
                s_tot = s.get("total", 0)

                if is_jamb:
                    badge_str = f"{s.get('scaled_100', round(s_pct))}/100"
                    badge_col = ft.Colors.PRIMARY
                elif is_waec:
                    badge_str = f"{s.get('waec_grade', '—')} ({s.get('waec_label', '')})"
                    badge_col = s.get("waec_color", ft.Colors.PRIMARY)
                else:
                    badge_str = f"{round(s_pct)}%"
                    badge_col = ui.C_CORRECT if s_pct >= 50 else ui.C_WRONG

                bar_col = ui.C_CORRECT if s_pct >= 70 else (ui.C_WARN if s_pct >= 50 else ui.C_WRONG)

                subj_rows.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.03),
                        border=ft.Border.all(1, ui.hairline(0.10)),
                        content=ft.Column([
                            ft.Row([
                                ft.Text(s_name, size=12, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE, expand=True),
                                ft.Text(f"{s_cor}/{s_tot} correct", size=11, color=ui.muted()),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                    border_radius=ft.BorderRadius.all(6),
                                    bgcolor=ui.tint(badge_col, 0.12),
                                    border=ft.Border.all(1, ui.tint(badge_col, 0.3)),
                                    content=ft.Text(badge_str, size=11, weight=ft.FontWeight.W_800, color=badge_col),
                                ),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.ProgressBar(
                                value=s_pct / 100.0,
                                color=bar_col,
                                bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.08),
                                height=5,
                                border_radius=ft.BorderRadius.all(3),
                            ),
                        ], spacing=6),
                    )
                )

            card_content.append(ft.Column(subj_rows, spacing=8))

        # Attempt Progression (if available)
        if past_attempts and len(past_attempts) > 1:
            card_content.append(ft.Divider(height=1, color=ui.hairline(0.12)))
            latest = past_attempts[0]
            prev = past_attempts[1]
            diff = (latest.get("percentage") or 0.0) - (prev.get("percentage") or 0.0)
            diff_str = f"+{diff:.1f}%" if diff >= 0 else f"{diff:.1f}%"
            diff_col = ui.C_CORRECT if diff >= 0 else ui.C_WRONG

            card_content.append(
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.TRENDING_UP_ROUNDED if diff >= 0 else ft.Icons.TRENDING_DOWN_ROUNDED, size=16, color=diff_col),
                        ft.Text(f"Attempt #{len(past_attempts)}", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                    ], spacing=6, tight=True),
                    ft.Text(f"vs Previous: {diff_str}", size=11.5, weight=ft.FontWeight.W_800, color=diff_col),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )

        return ft.Container(
            padding=ft.Padding.all(16),
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1.2, ui.tint(ft.Colors.PRIMARY, 0.25)),
            content=ft.Column(card_content, spacing=12),
        )

    def _build_diagnostic_report_canvas(
        self,
        score: int,
        percentage: float,
        is_jamb: bool,
        is_waec: bool,
        jamb_aggregate: int,
        jamb_tier_title: str,
        jamb_tier_desc: str,
        jamb_tier_col: str,
        waec_credit_passes: int,
        overall_waec_grade: str,
        overall_waec_label: str,
        overall_waec_credit: bool,
        overall_waec_col: str,
        subject_results: List[Dict[str, Any]],
        elapsed_seconds: int,
        avg_seconds: int,
        topic_stats: Dict[str, Dict[str, int]],
        records: List[Dict[str, Any]],
        past_attempts: List[Dict[str, Any]],
        is_auto_timeout: bool,
    ) -> ft.Control:
        """Full interactive Diagnostic Performance Report with strict JAMB vs WAEC parity."""

        # ── 1. Hero Score Banner (Exam-Cognizant) ──
        if is_jamb:
            # Strictly JAMB UTME Display (Zero WAEC Grades)
            banner_title = "Official JAMB UTME Performance Diagnostics"
            hero_primary_score = ft.Column([
                ft.Row([
                    ft.Text(f"{jamb_aggregate}", size=42, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                    ft.Text("/ 400", size=20, weight=ft.FontWeight.W_800, color=ui.muted()),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(f"UTME Aggregate • {score}/{self.total} Raw ({percentage:.1f}%)", size=12.5, weight=ft.FontWeight.W_700, color=ui.muted()),
            ], spacing=1)

            tier_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ui.tint(jamb_tier_col, 0.14),
                border=ft.Border.all(1.2, jamb_tier_col),
                content=ft.Column([
                    ft.Text(jamb_tier_title, size=13, weight=ft.FontWeight.W_900, color=jamb_tier_col),
                    ft.Text(jamb_tier_desc, size=11, color=ft.Colors.ON_SURFACE),
                ], spacing=3),
            )
            report_hero_body = ft.Column([
                ft.Row([hero_primary_score, tier_badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
            ], spacing=10)

        elif is_waec:
            # Strictly WAEC WASSCE Display (Zero JAMB Aggregates)
            banner_title = "Official WAEC / WASSCE Examination Result Slip"
            num_subjs = len(subject_results)
            qualifies = waec_credit_passes >= min(5, num_subjs)
            qual_col = ui.C_CORRECT if qualifies else ui.C_WARN
            qual_text = "Meets University Matriculation Standard (5+ Credits)" if qualifies else f"{waec_credit_passes} Credit(s) Passed • Deficiencies in {max(0, 5 - waec_credit_passes)} subject(s)"

            hero_primary_score = ft.Column([
                ft.Row([
                    ft.Text(f"{waec_credit_passes}", size=42, weight=ft.FontWeight.W_900, color=qual_col),
                    ft.Text(f"/ {num_subjs} Credits", size=20, weight=ft.FontWeight.W_800, color=ui.muted()),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(f"Credit Passes (Grades A1 - C6) • {percentage:.1f}% Overall", size=12.5, weight=ft.FontWeight.W_700, color=ui.muted()),
            ], spacing=1)

            tier_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ui.tint(qual_col, 0.14),
                border=ft.Border.all(1.2, qual_col),
                content=ft.Column([
                    ft.Text(f"Overall Grade: {overall_waec_grade} ({overall_waec_label})", size=13, weight=ft.FontWeight.W_900, color=qual_col),
                    ft.Text(qual_text, size=11, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                ], spacing=3),
            )
            report_hero_body = ft.Column([
                ft.Row([hero_primary_score, tier_badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
            ], spacing=10)

        else:
            # General / Academic Simulation
            banner_title = "Official CBT Performance Diagnostic Report"
            report_hero_body = ft.Row([
                ft.Column([
                    ft.Text(f"{score}/{self.total}", size=36, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                    ft.Text(f"{percentage:.1f}% Raw Accuracy", size=13, weight=ft.FontWeight.W_700, color=ui.muted()),
                ], spacing=2),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                    border_radius=ft.BorderRadius.all(12),
                    bgcolor=ui.tint(ft.Colors.PRIMARY, 0.14),
                    border=ft.Border.all(1.2, ft.Colors.PRIMARY),
                    content=ft.Column([
                        ft.Text(f"Score: {round(percentage)}%", size=14, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                        ft.Text("Completed Simulation", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True)

        hero_card = ft.Container(
            padding=ft.Padding.all(22),
            border_radius=ft.BorderRadius.all(18),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1.4, ui.tint(ft.Colors.PRIMARY, 0.40)),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, size=26, color=ui.C_WARN),
                    ft.Text(banner_title, size=15, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                ], spacing=8),
                ft.Text(f"{self.exam_title} • Candidate: {self.candidate_name}", size=11.5, color=ui.muted()),
                ft.Divider(height=1, color=ui.hairline()),
                report_hero_body,
            ], spacing=12),
        )

        # ── 2. Multi-Subject Breakdown (Grade Slip or JAMB Subject Table) ──
        subject_breakdown_section = self._build_subject_results_section(subject_results, is_jamb, is_waec)

        # ── 3. Speed and Time Analytics Card ──
        pace_target = 40 if is_jamb else 60
        pace_status = "Optimal" if avg_seconds <= pace_target else ("Standard" if avg_seconds <= pace_target + 20 else "Slow")
        pace_color = ui.C_CORRECT if pace_status == "Optimal" else (ui.C_WARN if pace_status == "Standard" else ui.C_WRONG)

        analytics_card = ft.Container(
            padding=ft.Padding.all(16),
            border_radius=ft.BorderRadius.all(14),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ui.hairline()),
            content=ft.Row([
                self._stat_block("Time Elapsed", self._format_time(elapsed_seconds), ft.Colors.PRIMARY),
                self._stat_block("Avg Pace", f"{avg_seconds}s / Q", pace_color),
                self._stat_block("Benchmark Pace", f"{pace_target}s / Q", ui.muted()),
                self._stat_block("Pacing Efficiency", pace_status, pace_color),
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND, wrap=True),
        )

        # ── 4. Longitudinal Attempt Trajectory & Progress Chart ──
        trajectory_card = self._build_attempt_trajectory_card(past_attempts, percentage, is_jamb, jamb_aggregate)

        # ── 5. Topic Mastery Breakdown Cards ──
        topic_bars = []
        for t_name, t_stat in topic_stats.items():
            t_total = t_stat["total"]
            t_cor = t_stat["correct"]
            t_pct = (t_cor / t_total * 100.0) if t_total > 0 else 0.0
            t_col = ui.C_CORRECT if t_pct >= 70 else (ui.C_WARN if t_pct >= 50 else ui.C_WRONG)

            topic_bars.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.03),
                    border=ft.Border.all(1, ui.hairline()),
                    content=ft.Column([
                        ft.Row([
                            ft.Text(t_name, size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                            ft.Text(f"{t_cor}/{t_total} ({t_pct:.0f}%)", size=12, weight=ft.FontWeight.W_800, color=t_col),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.ProgressBar(
                            value=t_pct / 100.0,
                            color=t_col,
                            bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.08),
                            height=6,
                            border_radius=ft.BorderRadius.all(3),
                        ),
                    ], spacing=6),
                )
            )

        topics_section = ft.Container(
            padding=ft.Padding.all(16),
            border_radius=ft.BorderRadius.all(14),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ui.hairline()),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.LEADERBOARD_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                    ft.Text("Syllabus & Topic Mastery Diagnostics", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                ], spacing=8),
                ft.Column(topic_bars, spacing=8),
            ], spacing=12),
        )

        # ── 6. Detailed Question Review List ──
        review_cards = []
        for r in records:
            review_cards.append(self._build_review_question_tile(r))

        review_section = ft.Container(
            padding=ft.Padding.all(16),
            border_radius=ft.BorderRadius.all(14),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ui.hairline()),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                    ft.Text(f"Full Step-by-Step Question Review ({len(records)} Questions)", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                ], spacing=8),
                ft.Column(review_cards, spacing=14),
            ], spacing=14),
        )

        # Responsive Action Buttons
        hub_btn = ft.OutlinedButton(
            "Back to Study Hub",
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, ui.hairline()),
                color=ft.Colors.ON_SURFACE,
                padding=ft.Padding.symmetric(horizontal=18, vertical=14),
            ),
            on_click=lambda _: self.on_exit() if self.on_exit else None,
            expand=True if not self.is_mobile else False,
        )
        retake_btn = ft.FilledButton(
            "Retake CBT Simulation",
            icon=ft.Icons.REFRESH_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
                color=ft.Colors.ON_PRIMARY,
                padding=ft.Padding.symmetric(horizontal=20, vertical=14),
            ),
            on_click=lambda _: self.on_restart() if self.on_restart else None,
            expand=True if not self.is_mobile else False,
        )

        action_footer = (
            ft.Column(
                [retake_btn, hub_btn],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                spacing=10,
            )
            if self.is_mobile
            else ft.Row([hub_btn, retake_btn], spacing=12)
        )

        return ft.Container(
            alignment=ft.Alignment.TOP_CENTER,
            padding=ft.Padding.symmetric(
                horizontal=12 if self.is_mobile else 24,
                vertical=18,
            ),
            content=ft.Container(
                width=None if self.is_mobile else 780,
                content=ft.Column([
                    hero_card,
                    subject_breakdown_section,
                    trajectory_card,
                    analytics_card,
                    topics_section,
                    review_section,
                    action_footer,
                    ft.Container(height=36),
                ], spacing=16),
            ),
        )

    def _build_report_top_hud(self) -> ft.Control:
        """Top sticky candidate header displayed on the diagnostic report."""
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        icon_size=18,
                        icon_color=ft.Colors.ON_SURFACE,
                        tooltip="Back to Study Hub",
                        on_click=lambda _: self.on_exit() if self.on_exit else None,
                    ),
                    ft.Container(
                        width=36,
                        height=36,
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ui.tint(ft.Colors.PRIMARY, 0.15),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.ASSESSMENT_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                    ),
                    ft.Column([
                        ft.Text("Performance Diagnostic Report", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                        ft.Text(f"{self.exam_title} • {self.candidate_name}", size=10.5, color=ui.muted()),
                    ], spacing=1, tight=True, expand=True if self.is_mobile else False),
                ], spacing=8, tight=True, expand=True if self.is_mobile else False),
                ft.Row([
                    ft.OutlinedButton(
                        "Study Hub",
                        icon=ft.Icons.HOME_ROUNDED,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            side=ft.BorderSide(1, ui.hairline()),
                            color=ft.Colors.ON_SURFACE,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        ),
                        on_click=lambda _: self.on_exit() if self.on_exit else None,
                    ),
                    ft.FilledButton(
                        "Retake",
                        icon=ft.Icons.REFRESH_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PRIMARY,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            color=ft.Colors.ON_PRIMARY,
                            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        ),
                        on_click=lambda _: self.on_restart() if self.on_restart else None,
                    ),
                ], spacing=8, tight=True),
            ],
        )

    def _build_diagnostic_report_view(self, **kwargs) -> ft.Control:
        """Full interactive Diagnostic Performance Report container wrapper."""
        return ft.Container(
            expand=True,
            bgcolor=ft.Colors.SURFACE,
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    self._build_report_top_hud(),
                    ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[self._build_diagnostic_report_canvas(**kwargs)],
                    ),
                ],
            ),
        )

    def _build_fallback_report_canvas(
        self,
        score: int,
        percentage: float,
        elapsed_seconds: int,
        error: Exception,
    ) -> ft.Container:
        """Resilient fallback diagnostic canvas if rich rendering encounters an unexpected exception."""
        hub_btn = ft.OutlinedButton(
            "Back to Study Hub",
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            on_click=lambda _: self.on_exit() if self.on_exit else None,
            expand=True if not self.is_mobile else False,
        )
        retake_btn = ft.FilledButton(
            "Retake Simulation",
            icon=ft.Icons.REFRESH_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
            on_click=lambda _: self.on_restart() if self.on_restart else None,
            expand=True if not self.is_mobile else False,
        )
        btn_layout = (
            ft.Column([retake_btn, hub_btn], horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=10)
            if self.is_mobile
            else ft.Row([hub_btn, retake_btn], spacing=10)
        )
        return ft.Container(
            alignment=ft.Alignment.TOP_CENTER,
            padding=ft.Padding.all(24),
            content=ft.Container(
                width=None if self.is_mobile else 600,
                padding=ft.Padding.all(24),
                border_radius=ft.BorderRadius.all(16),
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1.2, ft.Colors.PRIMARY),
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=28, color=ft.Colors.PRIMARY),
                        ft.Text("Exam Submitted Successfully", size=16, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                    ], spacing=10),
                    ft.Text(f"Candidate: {self.candidate_name} • {self.exam_title}", size=12, color=ui.muted()),
                    ft.Divider(height=1, color=ui.hairline()),
                    ft.Row([
                        ft.Column([
                            ft.Text(f"{score}/{self.total}", size=36, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                            ft.Text(f"Raw Score ({percentage:.1f}%)", size=12, weight=ft.FontWeight.W_700, color=ui.muted()),
                        ], spacing=2),
                        ft.Column([
                            ft.Text(self._format_time(elapsed_seconds), size=24, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                            ft.Text("Time Elapsed", size=12, color=ui.muted()),
                        ], spacing=2),
                    ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                    ft.Container(height=16),
                    btn_layout,
                ], spacing=14, tight=True),
            ),
        )

    def _build_fallback_report(
        self,
        score: int,
        percentage: float,
        elapsed_seconds: int,
        error: Exception,
    ) -> ft.Control:
        """Fallback report wrapper."""
        return ft.Container(
            expand=True,
            bgcolor=ft.Colors.SURFACE,
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    self._build_report_top_hud(),
                    ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[self._build_fallback_report_canvas(score, percentage, elapsed_seconds, error)],
                    ),
                ],
            ),
        )

    def _build_subject_results_section(
        self,
        subject_results: List[Dict[str, Any]],
        is_jamb: bool,
        is_waec: bool,
    ) -> ft.Container:
        """Renders either a JAMB 400 Subject Aggregate breakdown or an Official WAEC Result Slip."""
        if not subject_results or len(subject_results) == 0:
            return ft.Container(height=0, visible=False)

        if is_waec:
            # Official WAEC Grade Table
            rows = []
            for s in subject_results:
                is_credit = s["waec_is_credit"]
                status_color = ui.C_CORRECT if is_credit else (ui.C_WARN if s["waec_grade"] in ["D7", "E8"] else ui.C_WRONG)
                status_label = "Credit Pass" if is_credit else ("Pass" if s["waec_grade"] in ["D7", "E8"] else "Fail")

                rows.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        border_radius=ft.BorderRadius.all(8),
                        bgcolor=ui.tint(status_color, 0.08) if is_credit else ui.tint(ft.Colors.ON_SURFACE, 0.02),
                        border=ft.Border.all(1, ui.tint(status_color, 0.3) if is_credit else ui.hairline()),
                        content=ft.Row([
                            ft.Text(s["subject"], size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE, expand=True),
                            ft.Text(f"{s['correct']}/{s['total']} ({s['percentage']:.0f}%)", size=12, color=ui.muted()),
                            ft.Container(
                                width=44,
                                height=28,
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ui.tint(s["waec_color"], 0.18),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(s["waec_grade"], size=12, weight=ft.FontWeight.W_900, color=s["waec_color"]),
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ui.tint(status_color, 0.14),
                                content=ft.Text(status_label, size=10, weight=ft.FontWeight.W_800, color=status_color),
                            ),
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    )
                )

            return ft.Container(
                padding=ft.Padding.all(16),
                border_radius=ft.BorderRadius.all(14),
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ui.hairline()),
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.ARTICLE_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                        ft.Text("Official WAEC Subject Grade Slip", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                    ], spacing=8),
                    ft.Column(rows, spacing=6),
                ], spacing=12),
            )

        elif is_jamb:
            # Official JAMB Subject Breakdown Table
            rows = []
            for s in subject_results:
                s_pct = s["percentage"]
                tier_col = ui.C_CORRECT if s_pct >= 75 else (ui.C_INFO if s_pct >= 60 else (ui.C_WARN if s_pct >= 45 else ui.C_WRONG))

                rows.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        border_radius=ft.BorderRadius.all(8),
                        bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.03),
                        border=ft.Border.all(1, ui.hairline()),
                        content=ft.Row([
                            ft.Text(s["subject"], size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE, expand=True),
                            ft.Text(f"{s['correct']}/{s['total']} Raw", size=12, color=ui.muted()),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ui.tint(tier_col, 0.14),
                                border=ft.Border.all(1, tier_col),
                                content=ft.Text(f"{s['scaled_100']} / 100", size=12, weight=ft.FontWeight.W_900, color=tier_col),
                            ),
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    )
                )

            return ft.Container(
                padding=ft.Padding.all(16),
                border_radius=ft.BorderRadius.all(14),
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ui.hairline()),
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.GRID_VIEW_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                        ft.Text(
                            "JAMB UTME Subject Breakdown" if is_jamb
                            else ("WAEC / WASSCE Subject Breakdown" if is_waec
                            else "Subject Performance Breakdown"),
                            size=14,
                            weight=ft.FontWeight.W_800,
                            color=ft.Colors.ON_SURFACE,
                        ),
                    ], spacing=8),
                    ft.Column(rows, spacing=6),
                ], spacing=12),
            )

        return ft.Container(height=0, visible=False)

    def _build_attempt_trajectory_card(
        self,
        past_attempts: List[Dict[str, Any]],
        current_pct: float,
        is_jamb: bool,
        jamb_aggregate: int,
    ) -> ft.Container:
        """Visual progress trajectory & score progression across attempts."""
        if not past_attempts:
            past_attempts = [{
                "percentage": current_pct,
                "scaled_score": jamb_aggregate if is_jamb else round(current_pct),
                "attempted_at": "Now",
            }]

        # Chronological progression from past to latest
        attempts_chronological = list(reversed(past_attempts))
        num_attempts = len(attempts_chronological)
        all_percentages = []
        for a in attempts_chronological:
            try:
                all_percentages.append(float(a.get("percentage") or 0.0))
            except (ValueError, TypeError):
                all_percentages.append(0.0)
        best_pct = max(all_percentages) if all_percentages else current_pct
        prev_pct = all_percentages[-2] if num_attempts >= 2 else None
        delta_str = ""
        delta_color = ui.muted()
        if prev_pct is not None:
            delta = current_pct - prev_pct
            if delta > 0:
                delta_str = f"+{delta:.1f}% vs last attempt"
                delta_color = ui.C_CORRECT
            elif delta < 0:
                delta_str = f"{delta:.1f}% vs last attempt"
                delta_color = ui.C_WRONG
            else:
                delta_str = "Equal to last attempt"

        # Construct visual column bars for attempts
        chart_bars = []
        for i, a in enumerate(attempts_chronological):
            try:
                pct = float(a.get("percentage") or 0.0)
            except (ValueError, TypeError):
                pct = 0.0
            is_latest = (i == num_attempts - 1)
            is_best = (pct == best_pct and num_attempts > 1)
            bar_height = max(16, int(pct * 0.9))

            col_color = ft.Colors.PRIMARY if is_latest else (ui.C_CORRECT if is_best else ui.tint(ft.Colors.ON_SURFACE, 0.35))

            chart_bars.append(
                ft.Column([
                    ft.Text(f"{pct:.0f}%", size=10, weight=ft.FontWeight.W_800, color=col_color),
                    ft.Container(
                        width=24,
                        height=bar_height,
                        border_radius=ft.BorderRadius.all(6),
                        bgcolor=col_color,
                    ),
                    ft.Text(f"#{i+1}", size=9.5, weight=ft.FontWeight.W_700, color=ui.muted()),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=3)
            )

        return ft.Container(
            padding=ft.Padding.all(16),
            border_radius=ft.BorderRadius.all(14),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ui.hairline()),
            content=ft.Column([
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.INSIGHTS_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                        ft.Text("Exam Attempt Trajectory & Progress", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                    ], spacing=8, tight=True),
                    *(
                        [ft.Text(delta_str, size=11, weight=ft.FontWeight.W_800, color=delta_color)]
                        if delta_str else []
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    self._stat_block("Attempts Sat", str(num_attempts), ft.Colors.PRIMARY),
                    self._stat_block("Personal Best", f"{best_pct:.0f}%", ui.C_CORRECT),
                    self._stat_block("Latest Score", f"{current_pct:.0f}%", ft.Colors.ON_SURFACE),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                ft.Container(height=6),
                ft.Container(
                    height=130,
                    padding=ft.Padding.symmetric(vertical=8, horizontal=10),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.03),
                    content=ft.Row(
                        controls=chart_bars,
                        alignment=ft.MainAxisAlignment.SPACE_AROUND,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                ),
            ], spacing=10),
        )

    def _stat_block(self, label: str, val: str, color: str) -> ft.Container:
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Column([
                ft.Text(val, size=15, weight=ft.FontWeight.W_900, color=color),
                ft.Text(label, size=10, color=ui.muted()),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
        )

    def _build_review_question_tile(self, r: Dict[str, Any]) -> ft.Container:
        """Card reviewing an individual question with diagrams and solution working."""
        is_cor = r["is_correct"]
        badge_col = ui.C_CORRECT if is_cor else ui.C_WRONG
        badge_text = "CORRECT" if is_cor else "INCORRECT"

        content_controls = [
            ft.Row([
                ft.Text(f"Q{r['index']} • {r['subject']} ({r['topic']})", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=ft.BorderRadius.all(4),
                    bgcolor=ui.tint(badge_col, 0.18),
                    content=ft.Text(badge_text, size=9.5, weight=ft.FontWeight.W_900, color=badge_col),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Markdown(
                str(r.get("question_text") or r.get("question") or ""),
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                selectable=True,
                code_theme="atom-one-dark",
            ),
        ]

        norm_img = r.get("image_url")
        if norm_img:
            content_controls.append(
                ft.Container(
                    content=ft.Image(src=norm_img, fit=ft.BoxFit.CONTAIN, height=140),
                    alignment=ft.Alignment.CENTER,
                    padding=6,
                )
            )

        # Options comparison
        opt_rows = []
        for opt_idx, opt_str in enumerate(r["options"]):
            letter = _LETTERS[opt_idx] if opt_idx < len(_LETTERS) else str(opt_idx + 1)
            is_the_correct_one = (opt_idx == r["correct_index"])
            is_the_chosen_one = (opt_idx == r["chosen_index"])

            if is_the_correct_one:
                row_bg = ui.tint(ui.C_CORRECT, 0.15)
                row_border = ui.C_CORRECT
                trail_icon = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=16, color=ui.C_CORRECT)
            elif is_the_chosen_one and not is_cor:
                row_bg = ui.tint(ui.C_WRONG, 0.15)
                row_border = ui.C_WRONG
                trail_icon = ft.Icon(ft.Icons.CANCEL_ROUNDED, size=16, color=ui.C_WRONG)
            else:
                row_bg = ft.Colors.TRANSPARENT
                row_border = ui.hairline()
                trail_icon = None

            row_elements = [
                ft.Text(f"{letter}.", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Container(
                    content=ft.Markdown(
                        str(opt_str or ""),
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        selectable=False,
                        code_theme="atom-one-dark",
                    ),
                    expand=True,
                ),
            ]
            if trail_icon:
                row_elements.append(trail_icon)

            opt_rows.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=row_bg,
                    border=ft.Border.all(1, row_border),
                    content=ft.Row(row_elements, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                )
            )

        content_controls.append(ft.Column(opt_rows, spacing=4))

        # Explanation / Working
        if r.get("explanation") and str(r["explanation"]).strip():
            content_controls.append(
                ft.Container(
                    padding=ft.Padding.all(10),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ui.tint(ft.Colors.PRIMARY, 0.08),
                    border=ft.Border.all(1, ui.tint(ft.Colors.PRIMARY, 0.20)),
                    content=ft.Row([
                        ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                        ft.Column([
                            ft.Text("Working & Solution Explanation:", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                            ft.Markdown(
                                str(r["explanation"]),
                                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                                selectable=True,
                                code_theme="atom-one-dark",
                            ),
                        ], spacing=3, expand=True),
                    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
                )
            )

        return ft.Container(
            padding=ft.Padding.all(14),
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.03),
            border=ft.Border.all(1, ui.tint(ui.C_CORRECT if is_cor else ui.C_WRONG, 0.25)),
            content=ft.Column(content_controls, spacing=10),
        )


def build_cbt_exam_view(
    page: ft.Page,
    questions: List[Dict[str, Any]],
    duration_seconds: Optional[int] = None,
    exam_title: str = "CBT Past Questions Examination",
    exam_type: str = "General CBT",
    exam_year: Optional[int] = None,
    candidate_name: str = "Student Candidate",
    material_id: Optional[str] = None,
    bundle_id: Optional[str] = None,
    on_exit: Optional[Callable[[], None]] = None,
    on_restart: Optional[Callable[[], None]] = None,
) -> ft.Control:
    """Convenience factory function returning root Control of the CBT Exam Engine."""
    engine = CBTExamEngine(
        page=page,
        questions=questions,
        duration_seconds=duration_seconds,
        exam_title=exam_title,
        exam_type=exam_type,
        exam_year=exam_year,
        candidate_name=candidate_name,
        material_id=material_id,
        bundle_id=bundle_id,
        on_exit=on_exit,
        on_restart=on_restart,
    )
    return engine.root
