import flet as ft
from datetime import datetime, timezone

from src.components.bottom_appbar import get_bottom_appbar
from src.requests.enrollments import get_enrollment_stats


async def course_stats_view(page: ft.Page, course_id: str) -> ft.View:

    # ── constants ────────────────────────────────────────────────────────────
    SURFACE       = ft.Colors.SURFACE
    ON_SURFACE    = ft.Colors.ON_SURFACE
    PRIMARY       = ft.Colors.PRIMARY
    GREY_100      = ft.Colors.GREY_100
    GREY_200      = ft.Colors.GREY_200
    GREY_400      = ft.Colors.GREY_400
    GREY_500      = ft.Colors.GREY_500
    GOLD          = "#F59E0B"
    GOLD_BG       = "#FFFBEB"
    GREEN         = "#10B981"
    GREEN_BG      = "#ECFDF5"
    BLUE          = "#3B82F6"
    BLUE_BG       = "#EFF6FF"
    PURPLE        = "#8B5CF6"
    PURPLE_BG     = "#F5F3FF"

    token = await page.shared_preferences.get("auth_token") or ""

    # ── loading / error states ────────────────────────────────────────────────
    body = ft.Ref[ft.Column]()
    loading = ft.Container(
        expand=True,
        alignment=ft.Alignment(0, 0),
        content=ft.ProgressRing(color=PRIMARY),
        padding=35
    )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _fmt_date(iso_str):
        if not iso_str:
            return "—"
        try:
            dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y")
        except Exception:
            return str(iso_str)

    def _stat_card(icon, icon_color, bg_color, label, value, sub=None):
        return ft.Container(
            bgcolor=SURFACE,
            border_radius=14,
            border=ft.border.all(1, GREY_200),
            padding=ft.padding.all(16),
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Container(
                        width=38, height=38,
                        border_radius=10,
                        bgcolor=bg_color,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Icon(icon, color=icon_color, size=20),
                    ),
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text(value, size=20, weight=ft.FontWeight.W_700,
                                    color=ON_SURFACE),
                            ft.Text(label, size=11, color=GREY_500,
                                    weight=ft.FontWeight.W_500),
                            *([ ft.Text(sub, size=10, color=GREY_400) ] if sub else []),
                        ],
                    ),
                ],
            ),
        )

    def _section_label(text):
        return ft.Text(text, size=12, weight=ft.FontWeight.W_600,
                       color=GREY_400)

    def _rank_badge(rank, total):
        """Podium-style rank badge for top 3, plain for rest."""
        colours = {1: (GOLD, GOLD_BG), 2: ("#9CA3AF", "#F9FAFB"), 3: ("#CD7C2F", "#FEF3E2")}
        fg, bg = colours.get(rank, (PURPLE, PURPLE_BG))
        label = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
        return ft.Container(
            bgcolor=bg,
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            content=ft.Row(
                tight=True, spacing=8,
                controls=[
                    ft.Text(label, size=22),
                    ft.Column(
                        spacing=0,
                        controls=[
                            ft.Text(f"Rank {rank} of {total}",
                                    size=14, weight=ft.FontWeight.W_700, color=fg),
                            ft.Text("Leaderboard position",
                                    size=11, color=ft.Colors.with_opacity(0.7, fg)),
                        ],
                    ),
                ],
            ),
        )

    def _progress_bar(value_pct, color):
        """value_pct: 0–100"""
        return ft.Stack(
            controls=[
                ft.Container(height=8, border_radius=99, bgcolor=GREY_100, expand=True),
                ft.Container(
                    height=8,
                    border_radius=99,
                    bgcolor=color,
                    width=None,
                    expand=False,
                    # Flet doesn't have a ProgressBar percentage width natively,
                    # so we use a Row trick:
                    content=None,
                ),
            ]
        )

    # ── build page from stats dict ────────────────────────────────────────────
    def build_content(s: dict):
        faster = s.get("faster_than_percentile", 0)
        rank   = s.get("leaderboard_rank")
        total  = s.get("total_completers", 0)
        cert   = s.get("certificate_download_url")

        # ── header banner ────────────────────────────────────────────────────
        header = ft.Container(
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=["#6B5EE4", "#818CF8", "#A78BFA"],
            ),
             border_radius=ft.border_radius.only(
                bottom_left=30, 
                bottom_right=30
            ),
            padding=ft.padding.only(left=20, right=20, top=24, bottom=28),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Text("Course Completed", size=12, color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE),
                            weight=ft.FontWeight.W_500),
                    ft.Text(
                        s.get("course_title", "Course"),
                        size=20, weight=ft.FontWeight.W_700,
                        color=ft.Colors.WHITE,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Container(height=4),
                    ft.Row(
                        spacing=12,
                        controls=[
                            ft.Row(tight=True, spacing=5, controls=[
                                ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED,
                                        size=12, color=ft.Colors.with_opacity(0.7, ft.Colors.WHITE)),
                                ft.Text(f"Enrolled {_fmt_date(s.get('enrolled_at'))}",
                                        size=11, color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE)),
                            ]),
                            ft.Row(tight=True, spacing=5, controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                                        size=12, color=ft.Colors.with_opacity(0.7, ft.Colors.WHITE)),
                                ft.Text(f"Finished {_fmt_date(s.get('completed_at'))}",
                                        size=11, color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE)),
                            ]),
                        ],
                    ),
                ],
            ),
        )

        # ── stat cards grid ──────────────────────────────────────────────────
        stats_grid = ft.ResponsiveRow(
            columns=12,
            spacing=12,
            run_spacing=12,
            controls=[
                ft.Container(
                    col={"xs": 6},
                    content=_stat_card(
                        ft.Icons.TIMER_OUTLINED, BLUE, BLUE_BG,
                        "Time Spent",
                        s.get("time_spent_formatted", "—"),
                    ),
                ),
                ft.Container(
                    col={"xs": 6},
                    content=_stat_card(
                        ft.Icons.EMOJI_EVENTS_ROUNDED, GOLD, GOLD_BG,
                        "Leaderboard Rank",
                        f"#{rank}" if rank else "—",
                        f"of {total} completers" if total else None,
                    ),
                ),
                ft.Container(
                    col={"xs": 6},
                    content=_stat_card(
                        ft.Icons.SPEED_ROUNDED, GREEN, GREEN_BG,
                        "Faster Than",
                        f"{faster}%",
                        "of all completers",
                    ),
                ),
                ft.Container(
                    col={"xs": 6},
                    content=_stat_card(
                        ft.Icons.GROUP_OUTLINED, PURPLE, PURPLE_BG,
                        "Total Completers",
                        str(total) if total else "—",
                    ),
                ),
            ],
        )

        # ── speed percentile bar ─────────────────────────────────────────────
        pct_section = ft.Container(
            bgcolor=SURFACE,
            border_radius=14,
            border=ft.border.all(1, GREY_200),
            padding=ft.padding.all(16),
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Completion Speed", size=13,
                                    weight=ft.FontWeight.W_600, color=ON_SURFACE),
                            ft.Text(f"Top {100 - int(faster)}%",
                                    size=13, weight=ft.FontWeight.W_700, color=GREEN),
                        ],
                    ),
                    ft.Text(
                        f"You completed this course faster than {faster}% of all learners.",
                        size=11, color=GREY_500,
                    ),
                    ft.Container(height=4),
                    ft.Stack(
                        controls=[
                            ft.Container(
                                height=10, border_radius=99,
                                bgcolor=GREY_100, expand=True,
                            ),
                            ft.Container(
                                height=10, border_radius=99,
                                gradient=ft.LinearGradient(
                                    colors=[GREEN, "#6EE7B7"],
                                    begin=ft.Alignment(-1, 0),
                                    end=ft.Alignment(1, 0),
                                ),
                                width=max(10, (faster / 100) * (page.width - 80)),
                            ),
                        ],
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Slowest", size=10, color=GREY_400),
                            ft.Text("Fastest", size=10, color=GREY_400),
                        ],
                    ),
                ],
            ),
        )

        # ── rank badge ───────────────────────────────────────────────────────
        rank_section = _rank_badge(rank, total) if rank else ft.Container()

        # ── certificate ──────────────────────────────────────────────────────
        cert_section = ft.Container()
        if cert:
            # THE FIX: An explicit async wrapper that makes Flet's type-checker happy
            async def do_download(e):
                await page.launch_url(cert)

            cert_section = ft.Container(
                bgcolor=GOLD_BG,
                border_radius=14,
                border=ft.border.all(1, ft.Colors.with_opacity(0.2, GOLD)),
                padding=ft.padding.all(16),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=12, tight=True,
                            controls=[
                                ft.Container(
                                    width=42, height=42, border_radius=10,
                                    bgcolor=ft.Colors.with_opacity(0.15, GOLD),
                                    alignment=ft.Alignment(0, 0),
                                    content=ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                                                    color=GOLD, size=22),
                                ),
                                ft.Column(
                                    spacing=2,
                                    controls=[
                                        ft.Text("Certificate Ready",
                                                size=13, weight=ft.FontWeight.W_700,
                                                color="#92400E"),
                                        ft.Text("Tap to download your certificate",
                                                size=11, color=ft.Colors.with_opacity(0.7, "#92400E")),
                                    ],
                                ),
                            ],
                        ),
                        ft.IconButton(
                            ft.Icons.DOWNLOAD_ROUNDED,
                            icon_color=GOLD,
                            icon_size=22,
                            tooltip="Download Certificate",
                            # THE FIX: Call the explicitly defined async wrapper
                            on_click=lambda e: page.run_task(do_download, e),
                        ),
                    ],
                ),
            )

        return ft.Column(
            spacing=0,
            controls=[
                header,
                ft.Container(
                    padding=ft.padding.only(left=16, right=16, top=20, bottom=32),
                    content=ft.Column(
                        spacing=16,
                        controls=[
                            cert_section,
                            rank_section,
                            _section_label("YOUR STATS"),
                            stats_grid,
                            pct_section,
                        ],
                    ),
                ),
            ],
        )

    # ── fetch ─────────────────────────────────────────────────────────────────
    scroll_col = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
        expand=True,
        controls=[loading],
    )

    async def fetch():
        try:
            stats = await get_enrollment_stats(token, course_id)
            scroll_col.controls = [build_content(stats)]
        except Exception as ex:
            scroll_col.controls = [
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED,
                                    size=36, color=GREY_400),
                            ft.Text("Could not load stats",
                                    size=14, color=GREY_500),
                            ft.Text(str(ex), size=11, color=GREY_400),
                        ],
                    ),
                )
            ]
        page.update()

    page.run_task(fetch)

    # ── view ──────────────────────────────────────────────────────────────────
    return ft.View(
        route=f"/courses/{course_id}/stats",
        padding=0,
        bgcolor="#F8F7FC",
        appbar=ft.AppBar(
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                icon_color=ft.Colors.WHITE,
                icon_size=18,
                on_click=lambda _: page.go(f'/courses'),
            ),
            title=ft.Text("My Results", size=16,
                          weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.PRIMARY,
            elevation=0,
            center_title=False,
        ),
        bottom_appbar=get_bottom_appbar(page),
        controls=[
            ft.SafeArea(
                expand=True,
                content=scroll_col,
            )
        ],
    )