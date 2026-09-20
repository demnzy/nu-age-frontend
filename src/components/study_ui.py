"""
Shared design system for the Self-Study Hub (flashcards, quiz, exam).

Everything here is Flet 0.86.5-safe and deliberately theme-token driven
(ft.Colors.PRIMARY / SURFACE / ON_SURFACE) so it tracks the app's light and
dark themes from main.py instead of hardcoding a palette.

Design references — this module implements patterns that are standard across
modern LMS / assessment engines:
  * Segmented progress bars (Quizlet, Duolingo) instead of a single fill bar,
    so learners can see discrete item progress at a glance.
  * Immediate formative feedback for practice, deferred summative feedback
    for exams (Bloom's mastery-learning distinction).
  * Question palettes with a status legend + review-before-submit,
    which is the Prometric / Pearson VUE exam convention.
  * 4-tier recall grading (Again / Hard / Good / Easy) per SM-2 / Anki,
    rather than a coarse 3-button scale.
"""

import asyncio
import inspect

import flet as ft

# ─────────────────────────────────────────────────────────────────────────────
# TOKENS
# ─────────────────────────────────────────────────────────────────────────────
RADIUS_SM = 10
RADIUS_MD = 14
RADIUS_LG = 20
RADIUS_XL = 28

DUR_FAST = 140
DUR_BASE = 240
DUR_SLOW = 420

CURVE_OUT = ft.AnimationCurve.EASE_OUT
CURVE_EMPHASIS = ft.AnimationCurve.EASE_IN_OUT_CUBIC
CURVE_SPRING = ft.AnimationCurve.EASE_OUT_BACK

# Mobile breakpoint. Below this we go single-column, bigger tap targets.
COMPACT_W = 760

# Semantic colours. Kept as explicit Material tones so correctness/error
# states stay legible in both themes (theme PRIMARY is a dark green, which
# would read as "correct" and muddy the feedback signal).
C_CORRECT = ft.Colors.GREEN_600
C_CORRECT_SOFT = ft.Colors.GREEN_400
C_WRONG = ft.Colors.RED_500
C_WRONG_SOFT = ft.Colors.RED_300
C_WARN = ft.Colors.ORANGE_500
C_FLAG = ft.Colors.AMBER_600
C_INFO = ft.Colors.BLUE_500
C_SKIP = ft.Colors.BLUE_GREY_300

# Recall grades → SM-2 quality values the backend expects (0..5).
GRADE_AGAIN = 0
GRADE_HARD = 3
GRADE_GOOD = 4
GRADE_EASY = 5

PASS_THRESHOLD = 70  # % — mirrors the 70/40 banding already used in the hub


def is_compact(page: ft.Page) -> bool:
    """True when we should lay out for a phone-sized viewport."""
    return (page.width or COMPACT_W) < COMPACT_W


def tint(color, opacity: float = 0.10):
    return ft.Colors.with_opacity(opacity, color)


def hairline(opacity: float = 0.12):
    return ft.Colors.with_opacity(opacity, ft.Colors.ON_SURFACE)


def muted(opacity: float = 0.60):
    return ft.Colors.with_opacity(opacity, ft.Colors.ON_SURFACE)


# ─────────────────────────────────────────────────────────────────────────────
# HAPTICS (safe no-op on desktop/web)
# ─────────────────────────────────────────────────────────────────────────────
class Haptics:
    """Thin wrapper so callers never have to care whether haptics exist."""

    def __init__(self, page: ft.Page):
        self._page = page
        self._ctrl = None
        try:
            self._ctrl = ft.HapticFeedback()
            page.overlay.append(self._ctrl)
        except Exception:
            self._ctrl = None

    def _fire(self, name: str):
        # In Flet 0.86 these are coroutines, so calling them synchronously
        # would never actually fire (and leaks "never awaited" warnings).
        # Schedule them on the page's loop instead.
        if not self._ctrl:
            return
        try:
            result = getattr(self._ctrl, name)()
        except Exception:
            return
        if not inspect.iscoroutine(result):
            return
        try:
            async def _run(coro=result):
                try:
                    await coro
                except Exception:
                    pass

            self._page.run_task(_run)
        except Exception:
            # No running loop (e.g. under test) — close the coroutine so it
            # doesn't emit a "never awaited" warning.
            try:
                result.close()
            except Exception:
                pass

    def light(self):
        self._fire("light_impact")

    def medium(self):
        self._fire("medium_impact")

    def select(self):
        self._fire("selection_click")

    def dispose(self):
        try:
            if self._ctrl in self._page.overlay:
                self._page.overlay.remove(self._ctrl)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# PRIMITIVES
# ─────────────────────────────────────────────────────────────────────────────
def surface_card(content, padding=16, radius=RADIUS_MD, accent=None, expand=False):
    """The standard elevated panel used across all three study modes."""
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=radius,
        expand=expand,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, hairline(0.10)),
        shadow=ft.BoxShadow(
            blur_radius=14,
            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
        animate=ft.Animation(DUR_BASE, CURVE_OUT),
    ) if accent is None else ft.Container(
        content=content,
        padding=padding,
        border_radius=radius,
        expand=expand,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, tint(accent, 0.35)),
        shadow=ft.BoxShadow(
            blur_radius=16,
            color=tint(accent, 0.16),
            offset=ft.Offset(0, 5),
        ),
        animate=ft.Animation(DUR_BASE, CURVE_OUT),
    )


def pill(label: str, color, *, icon=None, solid: bool = False, size: int = 10):
    controls = []
    if icon is not None:
        controls.append(
            ft.Icon(icon, size=size + 3, color=ft.Colors.ON_PRIMARY if solid else color)
        )
    controls.append(
        ft.Text(
            label,
            size=size,
            weight=ft.FontWeight.W_700,
            color=ft.Colors.ON_PRIMARY if solid else color,
        )
    )
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=999,
        bgcolor=color if solid else tint(color, 0.12),
        border=None if solid else ft.Border.all(1, tint(color, 0.30)),
        content=ft.Row(spacing=5, tight=True, controls=controls),
    )


def section_label(text: str, *, trailing=None):
    row = [
        ft.Text(
            text.upper(),
            size=10,
            weight=ft.FontWeight.W_800,
            color=muted(0.45),
        )
    ]
    if trailing is not None:
        row.append(ft.Container(expand=True))
        row.append(trailing)
    return ft.Row(spacing=8, controls=row)


def stat_tile(value: str, label: str, color, icon=None):
    """Compact metric tile used in session summaries."""
    return ft.Container(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=10, vertical=12),
        border_radius=RADIUS_SM,
        bgcolor=tint(color, 0.08),
        border=ft.Border.all(1, tint(color, 0.20)),
        content=ft.Column(
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=15, color=color) if icon else ft.Container(height=0),
                ft.Text(value, size=17, weight=ft.FontWeight.W_800, color=color),
                ft.Text(
                    label,
                    size=9,
                    weight=ft.FontWeight.W_600,
                    color=muted(0.55),
                    text_align=ft.TextAlign.CENTER,
                    max_lines=2,
                ),
            ],
        ),
    )


def primary_button(text: str, on_click, *, color=None, icon=None, height=46, expand=False):
    color = color or ft.Colors.PRIMARY
    return ft.Container(
        expand=expand,
        height=height,
        border_radius=RADIUS_SM,
        bgcolor=color,
        ink=True,
        on_click=on_click,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=20),
        scale=1.0,
        animate_scale=ft.Animation(DUR_FAST, CURVE_OUT),
        shadow=ft.BoxShadow(
            blur_radius=12, color=tint(color, 0.35), offset=ft.Offset(0, 4)
        ),
        content=ft.Row(
            tight=True,
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=(
                ([ft.Icon(icon, size=17, color=ft.Colors.ON_PRIMARY)] if icon else [])
                + [
                    ft.Text(
                        text,
                        size=14,
                        weight=ft.FontWeight.W_700,
                        color=ft.Colors.ON_PRIMARY,
                    )
                ]
            ),
        ),
    )


def ghost_button(text: str, on_click, *, color=None, icon=None, height=46, expand=False):
    color = color or ft.Colors.PRIMARY
    return ft.Container(
        expand=expand,
        height=height,
        border_radius=RADIUS_SM,
        bgcolor=ft.Colors.TRANSPARENT,
        border=ft.Border.all(1.5, tint(color, 0.45)),
        ink=True,
        on_click=on_click,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=20),
        content=ft.Row(
            tight=True,
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=(
                ([ft.Icon(icon, size=17, color=color)] if icon else [])
                + [ft.Text(text, size=14, weight=ft.FontWeight.W_700, color=color)]
            ),
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SEGMENTED PROGRESS
# ─────────────────────────────────────────────────────────────────────────────
class SegmentedProgress:
    """
    Discrete per-item progress track.

    Above ~28 items segments get too thin to read, so we transparently fall
    back to a single animated fill bar. Same public API either way.
    """

    MAX_SEGMENTS = 28

    def __init__(self, total: int, *, active_color=None, height: int = 6):
        self.total = max(total, 1)
        self.active_color = active_color or ft.Colors.PRIMARY
        self._segmented = self.total <= self.MAX_SEGMENTS
        self._height = height

        if self._segmented:
            self._segs = [
                ft.Container(
                    expand=True,
                    height=height,
                    border_radius=999,
                    bgcolor=hairline(0.10),
                    animate=ft.Animation(DUR_BASE, CURVE_OUT),
                )
                for _ in range(self.total)
            ]
            self.control = ft.Row(spacing=3, controls=self._segs)
        else:
            self._segs = []
            self._bar = ft.ProgressBar(
                value=0,
                bar_height=height,
                border_radius=999,
                color=self.active_color,
                bgcolor=hairline(0.10),
                expand=True,
            )
            self.control = ft.Row(controls=[self._bar])

    def mark(self, index: int, color):
        """Colour a single completed segment (e.g. green=right, red=wrong)."""
        if self._segmented and 0 <= index < self.total:
            self._segs[index].bgcolor = color

    def set_current(self, index: int):
        """Advance the tracker to `index` (0-based)."""
        if self._segmented:
            for i, seg in enumerate(self._segs):
                if i == index:
                    seg.bgcolor = self.active_color
                elif i > index:
                    seg.bgcolor = hairline(0.10)
        else:
            self._bar.value = (index + 1) / self.total

    def fill_all(self, color=None):
        if self._segmented:
            for seg in self._segs:
                seg.bgcolor = color or self.active_color
        else:
            self._bar.value = 1.0


def progress_header(
    left_label: ft.Text,
    progress: "SegmentedProgress",
    *,
    right: list | None = None,
):
    """Sticky top strip: counter on the left, live chips on the right."""
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.only(bottom=ft.BorderSide(1, hairline(0.08))),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[left_label, ft.Row(spacing=8, controls=right or [])],
                ),
                progress.control,
            ],
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# ANIMATED SCORE RING
# ─────────────────────────────────────────────────────────────────────────────
def score_ring(pct: int, color, *, size: int = 132):
    """Determinate ring + big percentage. Returns (control, animate_coro)."""
    ring = ft.ProgressRing(
        value=0.0,
        width=size,
        height=size,
        stroke_width=10,
        color=color,
        bgcolor=hairline(0.09),
    )
    pct_text = ft.Text("0%", size=30, weight=ft.FontWeight.W_800, color=color)

    stack = ft.Stack(
        width=size,
        height=size,
        controls=[
            ring,
            ft.Container(
                width=size,
                height=size,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    spacing=0,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        pct_text,
                        ft.Text(
                            "SCORE",
                            size=9,
                            weight=ft.FontWeight.W_700,
                            color=muted(0.45),
                        ),
                    ],
                ),
            ),
        ],
    )

    async def animate(page: ft.Page):
        """Count the ring up so the score lands with some weight."""
        steps = 26
        for i in range(steps + 1):
            eased = 1 - (1 - i / steps) ** 3  # ease-out cubic
            ring.value = (pct / 100) * eased
            pct_text.value = f"{round(pct * eased)}%"
            try:
                page.update()
            except Exception:
                return
            await asyncio.sleep(0.018)

    return stack, animate


def verdict_for(pct: int):
    """(label, color, icon, blurb) banding used by every results screen."""
    if pct >= 90:
        return (
            "Mastered",
            C_CORRECT,
            ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
            "Outstanding recall — this material is locked in.",
        )
    if pct >= PASS_THRESHOLD:
        return (
            "On track",
            C_CORRECT_SOFT,
            ft.Icons.TRENDING_UP_ROUNDED,
            "Solid pass. Review the misses below to tighten it up.",
        )
    if pct >= 40:
        return (
            "Needs review",
            C_WARN,
            ft.Icons.REFRESH_ROUNDED,
            "You're getting there — focus on the incorrect items.",
        )
    return (
        "Keep studying",
        C_WRONG,
        ft.Icons.SCHOOL_ROUNDED,
        "Work back through the material, then retry this set.",
    )


def fmt_duration(seconds: int) -> str:
    seconds = max(int(seconds), 0)
    m, s = divmod(seconds, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}h {m:02d}m"
    return f"{m}:{s:02d}"


# ─────────────────────────────────────────────────────────────────────────────
# SHARED RESULTS VIEW
# ─────────────────────────────────────────────────────────────────────────────
def build_results_view(
    page: ft.Page,
    *,
    title: str,
    accent,
    records: list,
    elapsed_seconds: int,
    on_retry,
    on_exit,
    show_pass_band: bool = True,
):
    """
    Full-screen results screen shared by the quiz and the exam.

    `records` is a list of dicts:
        {question, options, correct_index, chosen_index (None = skipped),
         explanation, flagged, seconds}

    This replaces the old fixed-size AlertDialog, which clipped its own
    breakdown on small screens. LMS convention is a reviewable report:
    score, verdict, metrics, then per-item review with filters.
    """
    total = max(len(records), 1)
    correct = sum(1 for r in records if r.get("chosen_index") == r.get("correct_index"))
    skipped = sum(1 for r in records if r.get("chosen_index") is None)
    wrong = total - correct - skipped
    pct = round(correct / total * 100)

    # Longest correct streak — cheap motivation metric, standard in
    # gamified LMS reporting.
    best_streak = cur = 0
    for r in records:
        if r.get("chosen_index") == r.get("correct_index"):
            cur += 1
            best_streak = max(best_streak, cur)
        else:
            cur = 0

    verdict, v_color, v_icon, v_blurb = verdict_for(pct)
    ring, ring_anim = score_ring(pct, v_color)

    avg_secs = round(elapsed_seconds / total) if elapsed_seconds else 0

    # ── per-question review, with filtering ──────────────────────────────
    review_col = ft.Column(spacing=10)
    active_filter = {"mode": "all"}

    def _row(record, index: int):
        chosen = record.get("chosen_index")
        correct_i = record.get("correct_index")
        options = record.get("options") or []
        is_right = chosen == correct_i
        is_skipped = chosen is None

        if is_right:
            state_color, state_icon, state_label = C_CORRECT, ft.Icons.CHECK_ROUNDED, "Correct"
        elif is_skipped:
            state_color, state_icon, state_label = C_SKIP, ft.Icons.REMOVE_ROUNDED, "Skipped"
        else:
            state_color, state_icon, state_label = C_WRONG, ft.Icons.CLOSE_ROUNDED, "Incorrect"

        body = ft.Column(spacing=8, visible=False)

        def _answer_line(label: str, text: str, color, strong=False):
            return ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Container(width=64, content=ft.Text(label, size=10, color=muted(0.50))),
                    ft.Text(
                        text,
                        size=12,
                        color=color,
                        weight=ft.FontWeight.W_700 if strong else ft.FontWeight.W_400,
                        expand=True,
                    ),
                ],
            )

        if not is_right:
            body.controls.append(
                _answer_line(
                    "Your answer",
                    options[chosen] if chosen is not None and chosen < len(options) else "Not answered",
                    C_WRONG if not is_skipped else muted(0.55),
                )
            )
        body.controls.append(
            _answer_line(
                "Correct",
                options[correct_i] if correct_i is not None and correct_i < len(options) else "—",
                C_CORRECT,
                strong=True,
            )
        )
        if record.get("explanation"):
            body.controls.append(
                ft.Container(
                    padding=10,
                    border_radius=RADIUS_SM,
                    bgcolor=tint(C_INFO, 0.06),
                    border=ft.Border.all(1, tint(C_INFO, 0.18)),
                    content=ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=15, color=C_INFO),
                            ft.Text(
                                record["explanation"],
                                size=12,
                                color=muted(0.80),
                                expand=True,
                                selectable=True,
                            ),
                        ],
                    ),
                )
            )

        chevron = ft.Icon(ft.Icons.EXPAND_MORE_ROUNDED, size=18, color=muted(0.45))

        def toggle(_):
            body.visible = not body.visible
            chevron.name = (
                ft.Icons.EXPAND_LESS_ROUNDED if body.visible else ft.Icons.EXPAND_MORE_ROUNDED
            )
            page.update()

        header = ft.Container(
            ink=True,
            on_click=toggle,
            border_radius=RADIUS_SM,
            padding=ft.Padding.symmetric(horizontal=2, vertical=2),
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=26,
                        height=26,
                        border_radius=8,
                        bgcolor=tint(state_color, 0.14),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(state_icon, size=15, color=state_color),
                    ),
                    ft.Column(
                        spacing=1,
                        expand=True,
                        controls=[
                            ft.Text(
                                f"Q{index + 1}. {record.get('question', '')}",
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.ON_SURFACE,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(state_label, size=10, color=state_color,
                                    weight=ft.FontWeight.W_700),
                        ],
                    ),
                    ft.Icon(ft.Icons.FLAG_ROUNDED, size=14, color=C_FLAG)
                    if record.get("flagged")
                    else ft.Container(width=0),
                    chevron,
                ],
            ),
        )

        return ft.Container(
            padding=12,
            border_radius=RADIUS_MD,
            bgcolor=tint(state_color, 0.04),
            border=ft.Border.all(1, tint(state_color, 0.20)),
            content=ft.Column(spacing=8, controls=[header, body]),
        )

    def _render_review():
        review_col.controls.clear()
        mode = active_filter["mode"]
        shown = 0
        for i, rec in enumerate(records):
            right = rec.get("chosen_index") == rec.get("correct_index")
            if mode == "incorrect" and right:
                continue
            if mode == "flagged" and not rec.get("flagged"):
                continue
            review_col.controls.append(_row(rec, i))
            shown += 1
        if shown == 0:
            review_col.controls.append(
                ft.Container(
                    padding=24,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=32,
                                    color=C_CORRECT_SOFT),
                            ft.Text("Nothing here — nice work.", size=12, color=muted(0.55)),
                        ],
                    ),
                )
            )

    filter_defs = [
        ("all", f"All {total}"),
        ("incorrect", f"Needs work {wrong + skipped}"),
        ("flagged", f"Flagged {sum(1 for r in records if r.get('flagged'))}"),
    ]
    filter_chips: list[ft.Container] = []

    def _make_filter(mode: str, label: str):
        chip = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=7),
            border_radius=999,
            ink=True,
            animate=ft.Animation(DUR_FAST, CURVE_OUT),
            content=ft.Text(label, size=11, weight=ft.FontWeight.W_700),
        )

        def pick(_):
            active_filter["mode"] = mode
            for c, (m, _lbl) in zip(filter_chips, filter_defs):
                on = m == mode
                c.bgcolor = ft.Colors.PRIMARY if on else tint(ft.Colors.ON_SURFACE, 0.05)
                c.border = None if on else ft.Border.all(1, hairline(0.12))
                c.content.color = ft.Colors.ON_PRIMARY if on else muted(0.65)
            _render_review()
            page.update()

        chip.on_click = pick
        return chip

    for mode, label in filter_defs:
        filter_chips.append(_make_filter(mode, label))
    # seed default selection styling
    for c, (m, _lbl) in zip(filter_chips, filter_defs):
        on = m == "all"
        c.bgcolor = ft.Colors.PRIMARY if on else tint(ft.Colors.ON_SURFACE, 0.05)
        c.border = None if on else ft.Border.all(1, hairline(0.12))
        c.content.color = ft.Colors.ON_PRIMARY if on else muted(0.65)
    _render_review()

    compact = is_compact(page)

    hero = ft.Container(
        padding=ft.Padding.symmetric(horizontal=20, vertical=24),
        border_radius=RADIUS_LG,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[tint(accent, 0.13), tint(v_color, 0.06)],
        ),
        border=ft.Border.all(1, tint(v_color, 0.22)),
        content=ft.Column(
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                pill(title, accent, icon=ft.Icons.ASSESSMENT_ROUNDED),
                ring,
                ft.Row(
                    spacing=8,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(v_icon, size=18, color=v_color),
                        ft.Text(verdict, size=19, weight=ft.FontWeight.W_800, color=v_color),
                    ],
                ),
                ft.Text(
                    v_blurb,
                    size=12,
                    color=muted(0.65),
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    f"{correct} of {total} correct",
                    size=13,
                    weight=ft.FontWeight.W_700,
                    color=ft.Colors.ON_SURFACE,
                ),
                (
                    pill(
                        f"Pass mark {PASS_THRESHOLD}%",
                        C_CORRECT if pct >= PASS_THRESHOLD else C_WARN,
                        icon=ft.Icons.VERIFIED_ROUNDED
                        if pct >= PASS_THRESHOLD
                        else ft.Icons.INFO_OUTLINE_ROUNDED,
                    )
                    if show_pass_band
                    else ft.Container(height=0)
                ),
            ],
        ),
    )

    stats_row_1 = ft.Row(
        spacing=8,
        controls=[
            stat_tile(str(correct), "Correct", C_CORRECT, ft.Icons.CHECK_CIRCLE_ROUNDED),
            stat_tile(str(wrong), "Incorrect", C_WRONG, ft.Icons.CANCEL_ROUNDED),
            stat_tile(str(skipped), "Skipped", C_SKIP, ft.Icons.REMOVE_CIRCLE_OUTLINE_ROUNDED),
        ],
    )
    stats_row_2 = ft.Row(
        spacing=8,
        controls=[
            stat_tile(f"{pct}%", "Accuracy", ft.Colors.PRIMARY, ft.Icons.PERCENT_ROUNDED),
            stat_tile(str(best_streak), "Best streak", C_WARN, ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED),
            stat_tile(
                fmt_duration(elapsed_seconds) if elapsed_seconds else "—",
                f"Total · ~{avg_secs}s/q" if avg_secs else "Total time",
                C_INFO,
                ft.Icons.TIMER_OUTLINED,
            ),
        ],
    )

    actions = ft.Row(
        spacing=10,
        controls=[
            ghost_button("Back to Hub", lambda _: on_exit(), icon=ft.Icons.HOME_ROUNDED, expand=True),
            primary_button(
                "Try again",
                lambda _: on_retry(),
                color=accent,
                icon=ft.Icons.REPLAY_ROUNDED,
                expand=True,
            ),
        ],
    )

    body = ft.Column(
        spacing=18,
        controls=[
            hero,
            ft.Column(spacing=8, controls=[stats_row_1, stats_row_2]),
            actions,
            ft.Divider(height=1, color=hairline(0.08)),
            section_label("Question review"),
            ft.Row(spacing=8, wrap=True, controls=filter_chips),
            review_col,
            ft.Container(height=28),
        ],
    )

    page.run_task(ring_anim, page)

    return ft.Container(
        expand=True,
        content=ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(
                        horizontal=14 if compact else 28, vertical=18
                    ),
                    content=ft.Container(
                        content=body,
                        width=None if compact else 720,
                    ),
                    alignment=ft.Alignment.TOP_CENTER,
                )
            ],
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# EMPTY STATE
# ─────────────────────────────────────────────────────────────────────────────
def empty_state(icon, title: str, message: str, action_label: str, on_action):
    def _do_action(e=None):
        if on_action and callable(on_action):
            try:
                on_action(e)
            except TypeError:
                try:
                    on_action()
                except Exception:
                    pass

    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        padding=32,
        content=ft.Column(
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Container(
                    width=76,
                    height=76,
                    border_radius=999,
                    bgcolor=tint(ft.Colors.PRIMARY, 0.08),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=36, color=tint(ft.Colors.PRIMARY, 0.55)),
                ),
                ft.Text(title, size=17, weight=ft.FontWeight.W_800,
                        color=ft.Colors.ON_SURFACE, text_align=ft.TextAlign.CENTER),
                ft.Text(message, size=12, color=muted(0.55),
                        text_align=ft.TextAlign.CENTER),
                ft.Container(height=4),
                primary_button(action_label, _do_action,
                               icon=ft.Icons.ARROW_BACK_ROUNDED),
            ],
        ),
    )
