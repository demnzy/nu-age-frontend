"""
Modern Sleek Course Completion Stats & Results View for Nu-Age LMS.
Features a celebratory achievement hero, verified certificate showcase,
bento performance metrics grid, pace percentile radial ring,
and interactive learning momentum line chart with full dark/light theme adaptability.
"""

import asyncio
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional
import flet as ft
import flet_charts as fch

from src.components.bottom_appbar import get_bottom_appbar
from src.requests.enrollments import get_enrollment_stats, get_weekly_activity


def format_time_ascension(seconds: int) -> str:
    """Formats raw seconds into clean, human-readable duration."""
    if not seconds or seconds <= 0:
        return "—"
    try:
        seconds = int(seconds)
    except Exception:
        return "—"

    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    w, d = divmod(d, 7)
    mo, w = divmod(w, 4)
    yr, mo = divmod(mo, 12)

    parts = []
    if yr > 0:
        parts.append(f"{yr}y")
        if mo > 0:
            parts.append(f"{mo}mo")
    elif mo > 0:
        parts.append(f"{mo}mo")
        if w > 0:
            parts.append(f"{w}w")
    elif w > 0:
        parts.append(f"{w}w")
        if d > 0:
            parts.append(f"{d}d")
    elif d > 0:
        parts.append(f"{d}d")
        if h > 0:
            parts.append(f"{h}h")
    elif h > 0:
        parts.append(f"{h}h")
        if m > 0:
            parts.append(f"{m}m")
    elif m > 0:
        parts.append(f"{m}m")
    else:
        parts.append(f"{s}s")

    return " ".join(parts) or "—"


async def course_stats_view(page: ft.Page, course_id: str) -> ft.View:
    """
    Renders the modern, comprehensive Completed Course Results & Stats view.
    """
    token = await page.shared_preferences.get("auth_token") or ""
    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK if page else False

    # Accent and semantic colors
    PRIMARY = ft.Colors.PRIMARY
    SURFACE = ft.Colors.SURFACE
    ON_SURFACE = ft.Colors.ON_SURFACE
    ON_SURFACE_VARIANT = ft.Colors.ON_SURFACE_VARIANT
    BORDER_COLOR = ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)

    GOLD = "#F59E0B"
    GOLD_BG = ft.Colors.with_opacity(0.12, GOLD)
    GREEN = "#10B981"
    GREEN_BG = ft.Colors.with_opacity(0.12, GREEN)
    BLUE = "#0EA5E9"
    BLUE_BG = ft.Colors.with_opacity(0.12, BLUE)
    PURPLE = "#8B5CF6"
    PURPLE_BG = ft.Colors.with_opacity(0.12, PURPLE)

    # Content Socket
    content_socket = ft.Ref[ft.Container]()

    def _fmt_date(iso_str: Optional[str]) -> str:
        if not iso_str:
            return "—"
        try:
            dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y")
        except Exception:
            return str(iso_str)

    # ── WhatsApp Social Share Handler ─────────────────────────────────────────
    async def open_whatsapp_share(title: str, rank: Optional[int], faster: float):
        rank_text = f" (Ranked #{rank}) " if rank else " "
        speed_text = f" Completed faster than {int(faster)}% of learners! ⚡\n\n" if faster > 0 else "\n\n"
        message = (
            f'🎓 I just completed "{title}"{rank_text}on Nu-Age!\n'
            f"{speed_text}"
            f"Finished the complete curriculum with verified modules, flashcards, and exam mastery!\n\n"
            f"Check it out 👉 : nu-age.com.ng"
        )
        encoded = urllib.parse.quote(message)
        await page.launch_url(f"https://wa.me/?text={encoded}")

    # ── Main Content Builder ──────────────────────────────────────────────────
    def build_main_content(s: Dict[str, Any], activity: List[Dict[str, Any]]) -> ft.Control:
        course_title = s.get("course_title") or "Course Completion"
        faster = float(s.get("faster_than_percentile", 0) or 0)
        rank = s.get("leaderboard_rank")
        total = s.get("total_completers", 0)
        cert = s.get("certificate_download_url")
        auto_cert = s.get("auto_certificate", True)
        time_spent_sec = s.get("time_spent_seconds", 0)

        page_w = getattr(page, "width", None) or 1080
        is_mobile = page_w < 650
        is_xs = page_w < 450

        # ── Stat Card Component (Adaptive Mobile Layout) ──────────────────────
        def build_kpi_card(icon, icon_color, bg_color, label: str, value: str, sub: Optional[str] = None) -> ft.Control:
            return ft.Container(
                bgcolor=SURFACE,
                border_radius=ft.BorderRadius.all(14 if is_mobile else 18),
                border=ft.Border.all(1, BORDER_COLOR),
                padding=ft.Padding.all(12 if is_xs else (14 if is_mobile else 18)),
                shadow=ft.BoxShadow(
                    blur_radius=8 if is_mobile else 10,
                    color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2 if is_mobile else 3),
                ),
                content=ft.Column(
                    spacing=8 if is_mobile else 12,
                    controls=[
                        ft.Container(
                            width=34 if is_mobile else 42,
                            height=34 if is_mobile else 42,
                            border_radius=ft.BorderRadius.all(10 if is_mobile else 12),
                            bgcolor=bg_color,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, color=icon_color, size=18 if is_mobile else 22),
                        ),
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text(
                                    value,
                                    size=16 if is_xs else (18 if is_mobile else 20),
                                    weight=ft.FontWeight.W_800,
                                    color=ON_SURFACE,
                                    no_wrap=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    label,
                                    size=10.5 if is_mobile else 12,
                                    color=ON_SURFACE_VARIANT,
                                    weight=ft.FontWeight.W_600,
                                    no_wrap=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                *([ft.Text(
                                    sub,
                                    size=9.5 if is_mobile else 11,
                                    color=ON_SURFACE_VARIANT,
                                    no_wrap=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                )] if sub else []),
                            ],
                        ),
                    ],
                ),
            )

        # ── 1. Celebratory Hero Banner ────────────────────────────────────────
        badge_text = "COMPLETED" if is_xs else ("COURSE COMPLETED" if is_mobile else "COURSE COMPLETED • MILESTONE ACHIEVED")
        hero_banner = ft.Container(
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    PRIMARY,
                    ft.Colors.with_opacity(0.85, ft.Colors.SECONDARY or PRIMARY),
                ],
            ),
            border_radius=ft.BorderRadius.all(16 if is_mobile else 22),
            padding=ft.Padding.all(14 if is_xs else (18 if is_mobile else 24)),
            shadow=ft.BoxShadow(
                blur_radius=16 if is_mobile else 20,
                color=ft.Colors.with_opacity(0.15, PRIMARY),
                offset=ft.Offset(0, 6 if is_mobile else 8),
            ),
            content=ft.Column(
                spacing=10 if is_mobile else 14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8 if is_mobile else 10, vertical=4 if is_mobile else 5),
                                border_radius=ft.BorderRadius.all(10 if is_mobile else 12),
                                bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                                content=ft.Row(
                                    spacing=5,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=ft.Colors.AMBER_300, size=15 if is_mobile else 16),
                                        ft.Text(
                                            badge_text,
                                            size=10,
                                            weight=ft.FontWeight.W_800,
                                            color=ft.Colors.WHITE,
                                        ),
                                    ],
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.SHARE_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=18 if is_mobile else 20,
                                tooltip="Share Achievement on WhatsApp",
                                bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
                                width=36 if is_mobile else 40,
                                height=36 if is_mobile else 40,
                                on_click=lambda _: asyncio.create_task(
                                    open_whatsapp_share(course_title, rank, faster)
                                ),
                            ),
                        ],
                    ),
                    ft.Text(
                        course_title,
                        size=19 if is_xs else (22 if is_mobile else 28),
                        weight=ft.FontWeight.W_900,
                        color=ft.Colors.WHITE,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Row(
                        wrap=True,
                        spacing=10 if is_mobile else 16,
                        run_spacing=6 if is_mobile else 8,
                        controls=[
                            ft.Row(
                                tight=True,
                                spacing=5,
                                controls=[
                                    ft.Icon(ft.Icons.LOGIN_ROUNDED, size=13, color=ft.Colors.WHITE70),
                                    ft.Text(f"Started: {_fmt_date(s.get('enrolled_at'))}", size=11 if is_mobile else 12, color=ft.Colors.WHITE),
                                ],
                            ),
                            ft.Row(
                                tight=True,
                                spacing=5,
                                controls=[
                                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=13, color=ft.Colors.GREEN_300),
                                    ft.Text(f"Completed: {_fmt_date(s.get('completed_at'))}", size=11 if is_mobile else 12, color=ft.Colors.WHITE),
                                ],
                            ),
                            *([ft.Row(
                                tight=True,
                                spacing=5,
                                controls=[
                                    ft.Icon(ft.Icons.MILITARY_TECH_ROUNDED, size=13, color=ft.Colors.AMBER_300),
                                    ft.Text(f"Rank: #{rank}/{total}" if is_mobile else f"Cohort Rank: #{rank} of {total}", size=11 if is_mobile else 12, color=ft.Colors.WHITE),
                                ],
                            )] if rank else []),
                        ],
                    ),
                ],
            ),
        )

        # ── 2. Certificate Showcase Card ──────────────────────────────────────
        cert_card = None
        if cert or auto_cert:
            cert_download_url = cert or f"https://nu-age.name.ng/certificates/{course_id}"
            cert_card = ft.Container(
                bgcolor=SURFACE,
                border_radius=ft.BorderRadius.all(16 if is_mobile else 18),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.25, GOLD)),
                padding=ft.Padding.all(14 if is_xs else (16 if is_mobile else 20)),
                shadow=ft.BoxShadow(
                    blur_radius=12 if is_mobile else 14,
                    color=ft.Colors.with_opacity(0.08, GOLD),
                    offset=ft.Offset(0, 3 if is_mobile else 4),
                ),
                content=ft.ResponsiveRow(
                    columns=12,
                    spacing=12 if is_mobile else 16,
                    run_spacing=12 if is_mobile else 14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            col={"xs": 12, "md": 8},
                            content=ft.Row(
                                spacing=12 if is_mobile else 16,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        width=42 if is_mobile else 52,
                                        height=42 if is_mobile else 52,
                                        border_radius=ft.BorderRadius.all(12 if is_mobile else 14),
                                        bgcolor=GOLD_BG,
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, color=GOLD, size=22 if is_mobile else 28),
                                    ),
                                    ft.Column(
                                        spacing=3,
                                        expand=True,
                                        controls=[
                                            ft.Row(
                                                spacing=6,
                                                tight=True,
                                                controls=[
                                                    ft.Text(
                                                        "Certificate of Completion",
                                                        size=14.5 if is_mobile else 16,
                                                        weight=ft.FontWeight.W_800,
                                                        color=ON_SURFACE,
                                                    ),
                                                    ft.Container(
                                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                        border_radius=ft.BorderRadius.all(6),
                                                        bgcolor=GOLD_BG,
                                                        content=ft.Text(
                                                            "VERIFIED",
                                                            size=9,
                                                            weight=ft.FontWeight.BOLD,
                                                            color=GOLD,
                                                        ),
                                                    ),
                                                ],
                                            ),
                                            ft.Text(
                                                "Your official credential is authenticated and verifiable across the Nu-Age network.",
                                                size=11 if is_mobile else 12,
                                                color=ON_SURFACE_VARIANT,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "md": 4},
                            alignment=ft.Alignment.CENTER_RIGHT if not is_mobile else ft.Alignment.CENTER,
                            content=ft.ElevatedButton(
                                content=ft.Row(
                                    spacing=8,
                                    tight=True,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    controls=[
                                        ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=16 if is_mobile else 18, color=ft.Colors.WHITE),
                                        ft.Text("Download Certificate", size=12 if is_mobile else 13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    ],
                                ),
                                bgcolor=GOLD,
                                height=40 if is_mobile else 44,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    elevation=2,
                                ),
                                on_click=lambda _: asyncio.create_task(page.launch_url(cert_download_url)),
                            ),
                        ),
                    ],
                ),
            )

        # ── 3. Bento KPI Cards Grid ───────────────────────────────────────────
        kpi_grid = ft.ResponsiveRow(
            columns=12,
            spacing=10 if is_mobile else 16,
            run_spacing=10 if is_mobile else 16,
            controls=[
                ft.Container(
                    col={"xs": 6, "md": 3},
                    content=build_kpi_card(
                        ft.Icons.TIMER_OUTLINED,
                        BLUE,
                        BLUE_BG,
                        "Time Invested",
                        format_time_ascension(time_spent_sec),
                        "Total learning time",
                    ),
                ),
                ft.Container(
                    col={"xs": 6, "md": 3},
                    content=build_kpi_card(
                        ft.Icons.LEADERBOARD_ROUNDED,
                        GOLD,
                        GOLD_BG,
                        "Cohort Rank",
                        f"#{rank}" if rank else "Top Tier",
                        f"of {total} completers" if total else "Pioneering graduate",
                    ),
                ),
                ft.Container(
                    col={"xs": 6, "md": 3},
                    content=build_kpi_card(
                        ft.Icons.SPEED_ROUNDED,
                        GREEN,
                        GREEN_BG,
                        "Completion Pace",
                        f"Top {max(1, 100 - int(faster))}%",
                        f"Ahead of {int(faster)}% of peers",
                    ),
                ),
                ft.Container(
                    col={"xs": 6, "md": 3},
                    content=build_kpi_card(
                        ft.Icons.GROUP_ROUNDED,
                        PURPLE,
                        PURPLE_BG,
                        "Total Graduates",
                        str(total) if total else "Active",
                        "Alumni network",
                    ),
                ),
            ],
        )

        # ── 4. Pace Percentile & Cohort Benchmark Comparison Card ────────────
        pace_fraction = min(1.0, max(0.05, faster / 100.0))

        # Modern Comparison Bar Chart (Average vs You vs Top 10%)
        bar_chart = fch.BarChart(
            groups=[
                fch.BarChartGroup(
                    x=0,
                    rods=[
                        fch.BarChartRod(
                            from_y=0,
                            to_y=50,
                            width=16 if is_mobile else 18,
                            color=ft.Colors.with_opacity(0.35, ON_SURFACE_VARIANT),
                            border_radius=ft.BorderRadius.all(5 if is_mobile else 6),
                            tooltip="Cohort Average Time",
                        )
                    ],
                ),
                fch.BarChartGroup(
                    x=1,
                    rods=[
                        fch.BarChartRod(
                            from_y=0,
                            to_y=max(12, 100 - int(faster)),
                            width=16 if is_mobile else 18,
                            color=GREEN,
                            border_radius=ft.BorderRadius.all(5 if is_mobile else 6),
                            tooltip=f"Your Time ({format_time_ascension(time_spent_sec)})",
                        )
                    ],
                ),
                fch.BarChartGroup(
                    x=2,
                    rods=[
                        fch.BarChartRod(
                            from_y=0,
                            to_y=20,
                            width=16 if is_mobile else 18,
                            color=GOLD,
                            border_radius=ft.BorderRadius.all(5 if is_mobile else 6),
                            tooltip="Top 10% Fastest Benchmark",
                        )
                    ],
                ),
            ],
            bottom_axis=fch.ChartAxis(
                labels=[
                    fch.ChartAxisLabel(value=0, label=ft.Text("Avg", size=10, color=ON_SURFACE_VARIANT, weight=ft.FontWeight.W_600)),
                    fch.ChartAxisLabel(value=1, label=ft.Text("You", size=10, color=GREEN, weight=ft.FontWeight.W_800)),
                    fch.ChartAxisLabel(value=2, label=ft.Text("Top 10%", size=10, color=GOLD, weight=ft.FontWeight.W_600)),
                ],
                label_size=22,
            ),
            left_axis=fch.ChartAxis(show_labels=False),
            horizontal_grid_lines=fch.ChartGridLines(
                color=BORDER_COLOR,
                dash_pattern=[3, 3],
                width=1,
            ),
            tooltip=fch.BarChartTooltip(bgcolor=ft.Colors.with_opacity(0.88, ft.Colors.BLACK)),
            interactive=True,
            expand=True,
            min_y=0,
            max_y=110,
        )

        pace_card = ft.Container(
            bgcolor=SURFACE,
            border_radius=ft.BorderRadius.all(16 if is_mobile else 18),
            border=ft.Border.all(1, BORDER_COLOR),
            padding=ft.Padding.all(14 if is_xs else (16 if is_mobile else 22)),
            shadow=ft.BoxShadow(
                blur_radius=8 if is_mobile else 10,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 2 if is_mobile else 3),
            ),
            content=ft.Column(
                spacing=14 if is_mobile else 18,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=6 if is_mobile else 8,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.INSIGHTS_ROUNDED, color=GREEN, size=18 if is_mobile else 20),
                                    ft.Text("Performance Comparison", size=13.5 if is_mobile else 15, weight=ft.FontWeight.W_800, color=ON_SURFACE),
                                ],
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=GREEN_BG,
                                content=ft.Text(
                                    "Accelerated" if faster >= 50 else "Steady & Thorough",
                                    size=10,
                                    weight=ft.FontWeight.BOLD,
                                    color=GREEN,
                                ),
                            ),
                        ],
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16 if is_mobile else 20,
                        run_spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                        controls=[
                            # Radial Speed Ring
                            ft.Container(
                                width=104 if is_mobile else 120,
                                height=104 if is_mobile else 120,
                                content=ft.Stack(
                                    controls=[
                                        ft.ProgressRing(
                                            value=1.0,
                                            color=ft.Colors.with_opacity(0.1, ON_SURFACE),
                                            stroke_width=8 if is_mobile else 9,
                                            width=96 if is_mobile else 110,
                                            height=96 if is_mobile else 110,
                                        ),
                                        ft.ProgressRing(
                                            value=pace_fraction,
                                            color=GREEN,
                                            stroke_width=8 if is_mobile else 9,
                                            width=96 if is_mobile else 110,
                                            height=96 if is_mobile else 110,
                                        ),
                                        ft.Container(
                                            alignment=ft.Alignment.CENTER,
                                            content=ft.Column(
                                                alignment=ft.MainAxisAlignment.CENTER,
                                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                spacing=0,
                                                controls=[
                                                    ft.Text("Top", size=9, color=ON_SURFACE_VARIANT, weight=ft.FontWeight.W_600),
                                                    ft.Text(
                                                        f"{max(1, 100 - int(faster))}%",
                                                        size=19 if is_mobile else 22,
                                                        weight=ft.FontWeight.W_900,
                                                        color=ON_SURFACE,
                                                    ),
                                                    ft.Text("Pace", size=9, color=ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                                                ],
                                            ),
                                        ),
                                    ]
                                ),
                            ),
                            # Comparative Bar Chart
                            ft.Container(
                                width=160 if not is_mobile else min(220, max(140, page_w - 70)),
                                height=125 if is_mobile else 130,
                                content=bar_chart,
                            ),
                        ],
                    ),
                    ft.Text(
                        f"You completed this course faster than {int(faster)}% of all enrolled learners.",
                        size=11.5 if is_mobile else 12.5,
                        weight=ft.FontWeight.W_600,
                        color=ON_SURFACE,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            ),
        )

        # ── 5. Weekly Learning Momentum Chart Card ────────────────────────────
        chart_points = []
        axis_labels = []

        if activity and isinstance(activity, list) and len(activity) > 0:
            max_p = max([int(item.get("participations", 1)) for item in activity] or [5])
            top_val = max(10, int(max_p * 1.3))
            for idx, item in enumerate(activity):
                w_lbl = str(item.get("week") or f"W{idx+1}")
                val = int(item.get("participations", 0))
                chart_points.append(
                    fch.LineChartDataPoint(
                        x=idx,
                        y=val,
                        tooltip=f"{w_lbl}: {val} lessons completed",
                    )
                )
                axis_labels.append(
                    fch.ChartAxisLabel(
                        value=idx,
                        label=ft.Text(w_lbl, size=9.5 if is_mobile else 10, color=ON_SURFACE_VARIANT, weight=ft.FontWeight.W_600),
                    )
                )
        else:
            # Benchmark trajectory if single-session or no historical weekly log
            top_val = 20
            demo_data = [
                ("Start", 3),
                ("Phase 1", 7),
                ("Phase 2", 12),
                ("Finish", 18),
            ]
            for idx, (lbl, val) in enumerate(demo_data):
                chart_points.append(
                    fch.LineChartDataPoint(
                        x=idx,
                        y=val,
                        tooltip=f"{lbl}: Milestone Progress",
                    )
                )
                axis_labels.append(
                    fch.ChartAxisLabel(
                        value=idx,
                        label=ft.Text(lbl, size=9.5 if is_mobile else 10, color=ON_SURFACE_VARIANT, weight=ft.FontWeight.W_600),
                    )
                )

        if len(chart_points) == 1:
            # Anchor single-session activity from origin so a visible trajectory is drawn
            p0 = chart_points[0]
            chart_points = [
                fch.LineChartDataPoint(x=0, y=0, tooltip="Course Start"),
                fch.LineChartDataPoint(x=1, y=p0.y, tooltip=p0.tooltip),
            ]
            axis_labels = [
                fch.ChartAxisLabel(value=0, label=ft.Text("Start", size=9.5 if is_mobile else 10, color=ON_SURFACE_VARIANT, weight=ft.FontWeight.W_600)),
                fch.ChartAxisLabel(value=1, label=axis_labels[0].label if axis_labels else ft.Text("Completed", size=9.5 if is_mobile else 10, color=ON_SURFACE_VARIANT, weight=ft.FontWeight.W_600)),
            ]

        activity_series = fch.LineChartData(
            points=chart_points,
            curved=True,
            curve_smoothness=0.35,
            stroke_width=2.5 if is_mobile else 3,
            color=PRIMARY,
            point=fch.ChartCirclePoint(
                radius=3.5 if is_mobile else 4,
                color=PRIMARY,
            ),
            below_line_bgcolor=ft.Colors.with_opacity(0.12, PRIMARY),
            prevent_curve_over_shooting=True,
        )

        momentum_chart = fch.LineChart(
            data_series=[activity_series],
            min_y=0,
            max_y=max(10, top_val),
            min_x=0,
            max_x=max(1, len(chart_points) - 1),
            bottom_axis=fch.ChartAxis(labels=axis_labels),
            horizontal_grid_lines=fch.ChartGridLines(
                color=BORDER_COLOR,
                dash_pattern=[4, 4],
                width=1,
            ),
            tooltip=fch.LineChartTooltip(bgcolor=ft.Colors.with_opacity(0.9, ft.Colors.BLACK)),
            interactive=True,
            expand=True,
        )

        momentum_card = ft.Container(
            bgcolor=SURFACE,
            border_radius=ft.BorderRadius.all(16 if is_mobile else 18),
            border=ft.Border.all(1, BORDER_COLOR),
            padding=ft.Padding.all(14 if is_xs else (16 if is_mobile else 22)),
            shadow=ft.BoxShadow(
                blur_radius=8 if is_mobile else 10,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 2 if is_mobile else 3),
            ),
            content=ft.Column(
                spacing=12 if is_mobile else 16,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=6 if is_mobile else 8,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.TIMELINE_ROUNDED, color=PRIMARY, size=18 if is_mobile else 20),
                                    ft.Text("Learning Momentum", size=13.5 if is_mobile else 15, weight=ft.FontWeight.W_800, color=ON_SURFACE),
                                ],
                            ),
                            ft.Text(
                                "Activity Trend" if is_mobile else "Active Progress Progression",
                                size=10 if is_mobile else 11,
                                color=ON_SURFACE_VARIANT,
                                weight=ft.FontWeight.W_500,
                            ),
                        ],
                    ),
                    ft.Container(
                        height=125 if is_mobile else 135,
                        content=momentum_chart,
                    ),
                ],
            ),
        )

        # ── Two-Column Charts Row ─────────────────────────────────────────────
        analytics_row = ft.ResponsiveRow(
            columns=12,
            spacing=12 if is_mobile else 16,
            run_spacing=12 if is_mobile else 16,
            controls=[
                ft.Container(col={"xs": 12, "lg": 6}, content=pace_card),
                ft.Container(col={"xs": 12, "lg": 6}, content=momentum_card),
            ],
        )

        # ── Assemble Overall Layout ───────────────────────────────────────────
        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=14 if is_mobile else 18,
            controls=[
                hero_banner,
                *( [cert_card] if cert_card else [] ),
                kpi_grid,
                analytics_row,
                ft.Container(height=24 if is_mobile else 36),
            ],
        )

    # ── Data Fetcher Task ─────────────────────────────────────────────────────
    async def load_data():
        try:
            stats_task = asyncio.create_task(get_enrollment_stats(token, course_id))
            activity_task = asyncio.create_task(get_weekly_activity(token, course_id))

            stats_res, activity_res = await asyncio.gather(stats_task, activity_task, return_exceptions=True)

            if isinstance(stats_res, Exception) or not isinstance(stats_res, dict) or "error" in stats_res:
                err_text = stats_res.get("error") if isinstance(stats_res, dict) else str(stats_res)
                if content_socket.current:
                    content_socket.current.alignment = ft.Alignment.CENTER
                    content_socket.current.content = ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=14,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=48, color=ft.Colors.RED_400),
                            ft.Text("Could not load course completion stats", size=16, weight=ft.FontWeight.W_700, color=ON_SURFACE),
                            ft.Text(str(err_text), size=12, color=ON_SURFACE_VARIANT),
                            ft.ElevatedButton("Return to Catalog", on_click=lambda _: page.go("/courses")),
                        ],
                    )
                    page.update()
                return

            activity_list = activity_res if isinstance(activity_res, list) else []

            if content_socket.current:
                content_socket.current.alignment = ft.Alignment.TOP_CENTER
                content_socket.current.content = build_main_content(stats_res, activity_list)
                page.update()

        except Exception as ex:
            if content_socket.current:
                content_socket.current.alignment = ft.Alignment.CENTER
                content_socket.current.content = ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=48, color=ft.Colors.AMBER_500),
                        ft.Text("Failed to load statistics", size=16, weight=ft.FontWeight.W_600, color=ON_SURFACE),
                        ft.Text(str(ex), size=12, color=ON_SURFACE_VARIANT),
                        ft.ElevatedButton("Return to Catalog", on_click=lambda _: page.go("/courses")),
                    ],
                )
                page.update()

    # Content Socket (Centralized Loading State)
    content = ft.Container(
        ref=content_socket,
        expand=True,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(
            horizontal=12 if (getattr(page, "width", None) or 1080) < 450 else (16 if (getattr(page, "width", None) or 1080) < 650 else 24),
            vertical=12 if (getattr(page, "width", None) or 1080) < 650 else 18,
        ),
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
            tight=True,
            controls=[
                ft.ProgressRing(color=PRIMARY, width=42, height=42, stroke_width=3.5),
                ft.Text(
                    "Loading Course Results & Analytics…",
                    size=13.5,
                    color=ON_SURFACE_VARIANT,
                    weight=ft.FontWeight.W_500,
                ),
            ],
        ),
    )

    # Initial async load task
    asyncio.create_task(load_data())

    return ft.View(
        route=f"/courses/{course_id}/stats",
        padding=0,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        appbar=ft.AppBar(
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                icon_color=ON_SURFACE,
                icon_size=18,
                on_click=lambda _: page.go("/courses"),
            ),
            title=ft.Text("Course Results & Stats", size=16, weight=ft.FontWeight.W_700, color=ON_SURFACE),
            bgcolor=SURFACE,
            elevation=0,
            center_title=False,
        ),
        bottom_appbar=get_bottom_appbar(page),
        controls=[ft.SafeArea(expand=True, content=content)],
    )