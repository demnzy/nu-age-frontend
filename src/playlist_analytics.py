import asyncio
import flet as ft
from src.requests.playlists import get_playlist, get_playlist_analytics
from src.requests.organisations import get_my_organisation
from src.requests.chats import start_direct_message
from src.components.bottom_appbar import get_bottom_appbar


# ═══════════════════════════════════════════════════════════════════════════════
# PLAYLIST (LEARNING PATH) ANALYTICS (UNCLUTTERED, SEGMENTED & EXPLANATORY)
# ═══════════════════════════════════════════════════════════════════════════════

def _pill(label: str, bg, fg, icon=None) -> ft.Container:
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=11, color=fg))
    controls.append(ft.Text(label, size=10, color=fg, weight=ft.FontWeight.W_600))
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        bgcolor=bg,
        border_radius=8,
        content=ft.Row(controls, spacing=4, tight=True),
    )


def _section_header(title: str, subtitle: str = None) -> ft.Column:
    controls = [
        ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
    ]
    if subtitle:
        controls.append(ft.Text(subtitle, size=11, color=ft.Colors.ON_SURFACE_VARIANT))
    return ft.Column(controls, spacing=2)


def _progress_color(pct: float):
    if pct >= 0.75:
        return ft.Colors.GREEN_600
    if pct >= 0.4:
        return ft.Colors.AMBER_700
    return ft.Colors.BLUE_600


async def playlist_analytics_view(page: ft.Page, org_id: str, playlist_id: str):
    app_bar = get_bottom_appbar(page)
    # Hide bottom app bar during loading so user sees only the centered loading spinner
    app_bar.visible = False
    token = await page.shared_preferences.get("auth_token")

    def _go_back(e=None):
        if len(page.views) > 1:
            page.views.pop()
        else:
            page.go("/organisations")
        page.update()

    theme_color = ft.Colors.INDIGO_600
    playlist_data: dict = {}
    analytics_data: list = []

    # Active tab state: "performance", "milestones", "learners"
    active_tab = "performance"

    # Search and filter state
    learner_search_query = ""
    learner_filter_status = "all"  # "all", "completed", "in_progress", "not_started"

    # Centered loading container (dead-center of the screen, no appbar peeking)
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=44, height=44, stroke_width=3.5),
                ft.Container(height=16),
                ft.Text("Aggregating Learning Path Telemetry…", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
        ),
    )

    def _show_load_error(msg: str):
        app_bar.visible = True
        content_socket.alignment = ft.Alignment.CENTER
        content_socket.content = ft.Container(
            padding=32,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=48, color=ft.Colors.RED_400),
                    ft.Text("Pathway Analytics Unavailable", size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(msg, size=12, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=8),
                    ft.FilledButton(
                        "Retry Telemetry",
                        icon=ft.Icons.REFRESH_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=theme_color,
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                        ),
                        on_click=lambda _: page.run_task(fetch_analytics_data),
                    ),
                ],
            ),
        )
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # BENTO STAT CARD
    # ─────────────────────────────────────────────────────────────────────────
    def bento_stat(icon, title: str, value: str, subtext: str, accent_color, col_spec=None):
        return ft.Container(
            col=col_spec or {"xs": 12, "sm": 6, "md": 3},
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        width=36,
                        height=36,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, accent_color),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=18, color=accent_color),
                    ),
                    ft.Text(title, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=4),
                ft.Text(str(value), size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Text(subtext, size=11, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=2),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # EXPLANATORY CHART 1: PATHWAY PROGRESSION TIER DISTRIBUTION
    # ─────────────────────────────────────────────────────────────────────────
    def build_pathway_tier_distribution(learners: list):
        total = max(len(learners), 1)

        tier_mastery = [l for l in learners if float(l.get("progress", 0) or 0) >= 90.0]
        tier_proficient = [l for l in learners if 60.0 <= float(l.get("progress", 0) or 0) < 90.0]
        tier_developing = [l for l in learners if 30.0 <= float(l.get("progress", 0) or 0) < 60.0]
        tier_initiating = [l for l in learners if 0.1 <= float(l.get("progress", 0) or 0) < 30.0]
        tier_unstarted = [l for l in learners if float(l.get("progress", 0) or 0) < 0.1]

        tiers = [
            {"label": "Pathway Graduates (90% – 100%)", "count": len(tier_mastery), "color": ft.Colors.GREEN_600, "insight": "Full track mastery achieved"},
            {"label": "Advanced Milestones (60% – 89%)", "count": len(tier_proficient), "color": ft.Colors.TEAL_600, "insight": "Completing final courses"},
            {"label": "Mid-Track Pace (30% – 59%)", "count": len(tier_developing), "color": ft.Colors.BLUE_600, "insight": "Actively progressing through core courses"},
            {"label": "Initiating Track (1% – 29%)", "count": len(tier_initiating), "color": ft.Colors.AMBER_600, "insight": "Navigating prerequisite lessons"},
            {"label": "Not Started (0%)", "count": len(tier_unstarted), "color": ft.Colors.GREY_500, "insight": "Enrolled in track, inactive"},
        ]

        # Pedagogical diagnosis
        if len(tier_mastery) / total >= 0.35:
            diag_text = "Exceptional track completion rate: over a third of enrolled pathfinders have achieved mastery."
            diag_color = ft.Colors.GREEN_700
            diag_bg = ft.Colors.GREEN_50
        elif len(tier_unstarted) / total >= 0.5:
            diag_text = "Attention required: High early-stage attrition. Recommend issuing an introductory track reminder."
            diag_color = ft.Colors.AMBER_800
            diag_bg = ft.Colors.AMBER_50
        else:
            diag_text = "Steady pathway flow: Learners are transitioning fluidly across course milestones."
            diag_color = ft.Colors.BLUE_700
            diag_bg = ft.Colors.BLUE_50

        tier_rows = []
        for t in tiers:
            pct = (t["count"] / total) * 100
            tier_rows.append(
                ft.Container(
                    margin=ft.Margin.only(bottom=10),
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                ft.Container(width=10, height=10, border_radius=5, bgcolor=t["color"]),
                                ft.Text(t["label"], size=12, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ], spacing=6),
                            ft.Row([
                                ft.Text(f"{t['count']} learners", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                                ft.Text(f"({int(pct)}%)", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ], spacing=4),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(height=4),
                        # Fluid non-shrinking horizontal bar
                        ft.Container(
                            height=8,
                            border_radius=4,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                            content=ft.Row([
                                ft.Container(
                                    height=8,
                                    border_radius=4,
                                    bgcolor=t["color"],
                                    expand=int(pct) if pct > 0 else 0,
                                ) if pct > 0 else ft.Container(),
                                ft.Container(
                                    height=8,
                                    expand=int(100 - pct) if pct < 100 else 0,
                                ) if pct < 100 else ft.Container(),
                            ], spacing=0),
                        ),
                        ft.Text(t["insight"], size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=2),
                )
            )

        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _section_header("PATHWAY PROGRESSION DISTRIBUTION", "Learner advancement through the complete track"),
                ft.Container(height=8),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border_radius=8,
                    bgcolor=diag_bg,
                    content=ft.Row([
                        ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, size=16, color=diag_color),
                        ft.Text(diag_text, size=11, weight=ft.FontWeight.W_500, color=diag_color, expand=True),
                    ], spacing=8),
                ),
                ft.Container(height=12),
                ft.Column(tier_rows, spacing=0),
            ], spacing=4),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # EXPLANATORY CHART 2: COURSE-BY-COURSE MILESTONE FUNNEL
    # ─────────────────────────────────────────────────────────────────────────
    def build_milestone_funnel_card(courses_list: list, learners: list):
        if not courses_list:
            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=24,
                alignment=ft.Alignment.CENTER,
                content=ft.Column([
                    ft.Icon(ft.Icons.LAYERS_CLEAR_ROUNDED, size=36, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                    ft.Text("No courses mapped to this pathway yet.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
            )

        total_learners = max(len(learners), 1)
        total_courses = len(courses_list)

        course_rows = []
        for idx, c in enumerate(courses_list):
            c_name = c.get("name") or f"Milestone Course {idx + 1}"
            c_id = c.get("id") or ""
            
            # Step threshold in the sequential curriculum
            step_thresh = ((idx + 1) / total_courses) * 100.0
            completed_milestone = sum(1 for l in learners if float(l.get("progress", 0) or 0) >= step_thresh)
            pct_milestone = (completed_milestone / total_learners) * 100

            is_gateway = (idx == 0)
            m_color = ft.Colors.GREEN_600 if pct_milestone >= 70 else (ft.Colors.BLUE_600 if pct_milestone >= 40 else ft.Colors.AMBER_600)

            course_rows.append(
                ft.Container(
                    margin=ft.Margin.only(bottom=10),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                ft.Container(
                                    width=24, height=24, border_radius=12,
                                    bgcolor=ft.Colors.with_opacity(0.12, m_color),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Text(str(idx + 1), size=11, weight=ft.FontWeight.BOLD, color=m_color),
                                ),
                                ft.Text(c_name, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ], spacing=8, expand=True),
                            ft.IconButton(
                                ft.Icons.OPEN_IN_NEW_ROUNDED,
                                icon_size=16,
                                icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                tooltip=f"Open {c_name}",
                                on_click=lambda _, cid=c_id: page.go(f"/courses/{cid}"),
                            ),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(height=4),
                        # Fluid non-shrinking milestone bar
                        ft.Row([
                            ft.Container(
                                height=6,
                                border_radius=3,
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                                expand=True,
                                content=ft.Row([
                                    ft.Container(
                                        height=6,
                                        border_radius=3,
                                        bgcolor=m_color,
                                        expand=int(pct_milestone) if pct_milestone > 0 else 0,
                                    ) if pct_milestone > 0 else ft.Container(),
                                    ft.Container(
                                        height=6,
                                        expand=int(100 - pct_milestone) if pct_milestone < 100 else 0,
                                    ) if pct_milestone < 100 else ft.Container(),
                                ], spacing=0),
                            ),
                            ft.Text(f"{int(pct_milestone)}% reached", size=10, weight=ft.FontWeight.BOLD, color=m_color),
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text(
                            "Primary gateway milestone" if is_gateway else f"Sequential milestone {idx + 1} of {total_courses}",
                            size=10,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], spacing=2),
                )
            )

        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _section_header("COURSE-BY-COURSE MILESTONE FUNNEL", f"{len(courses_list)} milestones sequenced along roadmap"),
                ft.Container(height=8),
                ft.Column(course_rows, spacing=0),
            ], spacing=4),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # MOBILE-RESPONSIVE LEARNER CARD (NEVER SHRINKS / NEVER CRUNCHES)
    # ─────────────────────────────────────────────────────────────────────────
    def build_learner_card(learner: dict):
        name = learner.get("student_name") or "Academy Pathfinder"
        uid = learner.get("student_id") or ""
        enrolled_raw = learner.get("enrolled_at") or ""
        completed_raw = learner.get("completed_at") or ""

        initials = "".join([p[0] for p in name.split()[:2] if p]).upper() or "?"

        raw_p = learner.get("progress", 0.0) or 0.0
        try:
            p_val = float(raw_p)
        except (TypeError, ValueError):
            p_val = 0.0
        p_val = max(0.0, min(100.0, p_val))
        p_ratio = p_val / 100.0
        is_completed = bool(completed_raw) or p_val >= 99.9

        prog_color = ft.Colors.GREEN_600 if is_completed else _progress_color(p_ratio)

        async def _message(e, sid=uid):
            if sid:
                result = await start_direct_message(token, str(sid))
                if result and "error" in result:
                    print(f"DM create failed for {sid}: {result}")
            page.go("/nu-chat")

        return ft.Container(
            padding=ft.Padding.all(12),
            margin=ft.Margin.only(bottom=8),
            border_radius=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
            content=ft.Column([
                # Row 1: Avatar + Name + Action buttons
                ft.Row([
                    ft.Row([
                        ft.CircleAvatar(
                            content=ft.Text(initials, size=12, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                            color=theme_color,
                            radius=18,
                        ),
                        ft.Column([
                            ft.Text(name, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(
                                f"Enrolled {enrolled_raw[:10]}" if enrolled_raw else "Enrolled in pathway",
                                size=11, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ], spacing=2, expand=True),
                    ], spacing=10, expand=True),
                    ft.Row([
                        ft.IconButton(
                            ft.Icons.PERSON_OUTLINE_ROUNDED,
                            icon_size=17,
                            icon_color=ft.Colors.ON_SURFACE_VARIANT,
                            tooltip="View Profile",
                            on_click=lambda _, sid=uid: page.go(f"/member/{sid}") if sid else None,
                        ),
                        ft.IconButton(
                            ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                            icon_size=17,
                            icon_color=theme_color,
                            tooltip=f"Direct Message {name}",
                            on_click=lambda e, sid=uid: page.run_task(_message, e, sid),
                        ),
                    ], spacing=0),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=6),
                # Row 2: Full width progress bar with status pill & percentage
                ft.Row([
                    ft.Container(
                        height=6,
                        border_radius=3,
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                        expand=True,
                        content=ft.ProgressBar(value=p_ratio, color=prog_color, bgcolor=ft.Colors.TRANSPARENT),
                    ),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.1, prog_color),
                        content=ft.Text(f"{int(p_val)}%", size=10, weight=ft.FontWeight.BOLD, color=prog_color),
                    ),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=0),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN LAYOUT BUILDER (SEGMENTED TABS & ZERO CLUTTER)
    # ─────────────────────────────────────────────────────────────────────────
    def build_main_layout():
        title = playlist_data.get("name") or "Curated Learning Pathway"
        desc = playlist_data.get("description") or "Specialized sequential curriculum track."
        is_public = bool(playlist_data.get("public", False))
        raw_courses = playlist_data.get("playlist_courses") or playlist_data.get("courses") or []
        courses = []
        for item in raw_courses:
            if isinstance(item, dict):
                if "course" in item and isinstance(item["course"], dict):
                    c = dict(item["course"])
                    c["order_index"] = item.get("order_index", 0)
                    courses.append(c)
                else:
                    courses.append(item)
            elif isinstance(item, str):
                courses.append({"id": item, "name": f"Course {item[:6]}"})
        course_count = len(courses)

        total_learners = len(analytics_data)

        # Calculations
        all_prog = []
        completions = 0
        in_progress = 0
        not_started = 0

        for l in analytics_data:
            p = float(l.get("progress", 0.0) or 0.0)
            all_prog.append(p)
            if l.get("completed_at") or p >= 99.9:
                completions += 1
            elif p > 0.1:
                in_progress += 1
            else:
                not_started += 1

        avg_progress = (sum(all_prog) / len(all_prog)) if all_prog else 0.0
        avg_prog_str = f"{int(avg_progress)}%"

        total_valid = total_learners if total_learners > 0 else 1
        pct_completed = int((completions / total_valid) * 100)
        pct_active = int((in_progress / total_valid) * 100)

        status_badge = _pill(
            "PUBLIC TRACK" if is_public else "CAMPUS TRACK",
            ft.Colors.GREEN_700 if is_public else ft.Colors.BLUE_700,
            ft.Colors.WHITE,
            ft.Icons.PUBLIC_ROUNDED if is_public else ft.Icons.LOCK_ROUNDED,
        )

        # ── HERO HEADER CARD ───────────────────────────────────────────────────
        hero_card = ft.Container(
            margin=ft.Margin.symmetric(horizontal=16, vertical=8),
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column([
                # Top Gradient Banner
                ft.Container(
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1),
                        end=ft.Alignment(1, 1),
                        colors=[theme_color, ft.Colors.PRIMARY],
                    ),
                    padding=ft.Padding.only(top=10, left=12, right=12, bottom=12),
                    content=ft.Row([
                        ft.Row([
                            ft.IconButton(
                                ft.Icons.ARROW_BACK_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=18,
                                tooltip="Back to Academy",
                                on_click=_go_back,
                            ),
                            ft.Text("Learning Path Telemetry & Analytics", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                        ], spacing=4),
                        ft.Row([
                            ft.IconButton(
                                ft.Icons.EDIT_ROAD_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=17,
                                tooltip="Roadmap Builder",
                                on_click=lambda _: page.go(f"/playlists/{playlist_id}/build"),
                            ),
                            ft.IconButton(
                                ft.Icons.SETTINGS_OUTLINED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=17,
                                tooltip="Path Settings",
                                on_click=lambda _: page.go(f"/playlists/{playlist_id}/settings"),
                            ),
                            ft.IconButton(
                                ft.Icons.VISIBILITY_OUTLINED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=17,
                                tooltip="View Pathway",
                                on_click=lambda _: page.go(f"/playlists/{playlist_id}"),
                            ),
                        ], spacing=2),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ),
                # Header Body
                ft.Container(
                    padding=ft.Padding.all(16),
                    content=ft.Column([
                        ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                        ft.Text(desc, size=12, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Container(height=4),
                        ft.Row([
                            status_badge,
                            ft.Row([
                                ft.Icon(ft.Icons.LAYERS_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"{course_count} Curated Courses in Pathway", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                            ], spacing=4),
                        ], spacing=8, wrap=True),
                    ], spacing=6),
                ),
            ], spacing=0),
        )

        # ── TAB SWITCHER BUTTONS ───────────────────────────────────────────────
        def switch_tab(tab_name):
            nonlocal active_tab
            active_tab = tab_name
            tab_content_container.content = get_active_tab_content()
            for btn in tab_buttons.controls:
                is_sel = btn.data == tab_name
                btn.bgcolor = theme_color if is_sel else ft.Colors.TRANSPARENT
                if hasattr(btn, "content") and hasattr(btn.content, "controls"):
                    btn.content.controls[0].color = ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE_VARIANT
                    btn.content.controls[1].color = ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE
                    btn.content.controls[1].weight = ft.FontWeight.BOLD if is_sel else ft.FontWeight.NORMAL
            try:
                tab_buttons.update()
            except Exception:
                pass
            try:
                tab_content_container.update()
            except Exception:
                pass

        def tab_btn(title: str, key: str, icon):
            is_sel = (active_tab == key)
            return ft.Container(
                data=key,
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=10,
                bgcolor=theme_color if is_sel else ft.Colors.TRANSPARENT,
                ink=True,
                on_click=lambda _, k=key: switch_tab(k),
                content=ft.Row([
                    ft.Icon(icon, size=14, color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(title, size=12, weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.NORMAL, color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE),
                ], spacing=6, tight=True),
            )

        tab_buttons = ft.Row([
            tab_btn("Pathway Performance", "performance", ft.Icons.INSIGHTS_ROUNDED),
            tab_btn("Curriculum Milestones", "milestones", ft.Icons.MAP_ROUNDED),
            tab_btn(f"Pathfinder Cohort ({total_learners})", "learners", ft.Icons.PEOPLE_ROUNDED),
        ], spacing=6, scroll=ft.ScrollMode.AUTO)

        tabs_bar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=4),
            content=tab_buttons,
        )

        # ── TAB 1: PATHWAY PERFORMANCE ─────────────────────────────────────────
        def build_performance_tab():
            return ft.Column([
                ft.ResponsiveRow([
                    bento_stat(
                        ft.Icons.EXPLORE_ROUNDED,
                        "ENROLLED LEARNERS",
                        str(total_learners),
                        f"{in_progress} active learners",
                        ft.Colors.BLUE_500,
                    ),
                    bento_stat(
                        ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                        "TRACK COMPLETIONS",
                        f"{pct_completed}%",
                        f"{completions} path graduates",
                        ft.Colors.GREEN_600,
                    ),
                    bento_stat(
                        ft.Icons.TRENDING_UP_ROUNDED,
                        "AVG. PATH PROGRESS",
                        avg_prog_str,
                        f"Across {course_count} track courses",
                        _progress_color(avg_progress / 100.0),
                    ),
                    bento_stat(
                        ft.Icons.TIMELAPSE_ROUNDED,
                        "ACTIVE RATE",
                        f"{pct_active}%",
                        f"{in_progress} learners in motion",
                        ft.Colors.AMBER_600,
                    ),
                ], spacing=12, run_spacing=12),
                ft.Container(height=12),
                build_pathway_tier_distribution(analytics_data),
            ], spacing=0)

        # ── TAB 2: CURRICULUM MILESTONES ───────────────────────────────────────
        def build_milestones_tab():
            return ft.Column([
                build_milestone_funnel_card(courses, analytics_data),
            ], spacing=0)

        # ── TAB 3: PATHFINDER COHORT (NON-BLOCKING & RESPONSIVE) ───────────────
        def get_filtered_learners():
            res = analytics_data
            if learner_search_query.strip():
                q = learner_search_query.strip().lower()
                res = [e for e in res if q in e.get("student_name", "").lower()]

            if learner_filter_status == "completed":
                res = [e for e in res if e.get("completed_at") or float(e.get("progress", 0.0) or 0.0) >= 99.9]
            elif learner_filter_status == "in_progress":
                res = [e for e in res if 0.1 <= float(e.get("progress", 0.0) or 0.0) < 99.9]
            elif learner_filter_status == "not_started":
                res = [e for e in res if float(e.get("progress", 0.0) or 0.0) < 0.1]
            return res

        def build_learner_items(l_list):
            if not l_list:
                return [
                    ft.Container(
                        padding=32,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column([
                            ft.Icon(ft.Icons.GROUPS_ROUNDED, size=36, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                            ft.Text("No pathfinders match this filter criteria.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    )
                ]
            return [build_learner_card(l) for l in l_list]

        learners_column = ft.Column(controls=build_learner_items(get_filtered_learners()), spacing=0)

        def on_learner_search_change(e):
            nonlocal learner_search_query
            learner_search_query = e.control.value or ""
            learners_column.controls = build_learner_items(get_filtered_learners())
            try:
                learners_column.update()
            except Exception:
                pass

        def set_learner_filter(status_key):
            nonlocal learner_filter_status
            learner_filter_status = status_key
            learners_column.controls = build_learner_items(get_filtered_learners())
            try:
                learners_column.update()
            except Exception:
                pass
            for chip in learner_filter_chips.controls:
                is_active = chip.data == status_key
                chip.bgcolor = theme_color if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
                chip.content.color = ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE
                chip.content.weight = ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL
            try:
                learner_filter_chips.update()
            except Exception:
                pass

        def learner_chip(label: str, key: str):
            is_active = (learner_filter_status == key)
            return ft.Container(
                data=key,
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=14,
                bgcolor=theme_color if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=lambda _, k=key: set_learner_filter(k),
                content=ft.Text(
                    label,
                    size=11,
                    weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                    color=ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE,
                ),
            )

        learner_filter_chips = ft.Row([
            learner_chip(f"All ({total_learners})", "all"),
            learner_chip(f"Completed ({completions})", "completed"),
            learner_chip(f"In Progress ({in_progress})", "in_progress"),
            learner_chip(f"Not Started ({not_started})", "not_started"),
        ], spacing=6, scroll=ft.ScrollMode.AUTO)

        search_box = ft.TextField(
            hint_text="Search pathfinders by student name…",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=10,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            on_change=on_learner_search_change,
            width=float("inf"),
        )

        def build_learners_tab():
            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(16),
                content=ft.Column([
                    _section_header("PATHFINDER COHORT", f"{total_learners} students pursuing learning pathway"),
                    search_box,
                    learner_filter_chips,
                    ft.Container(height=4),
                    learners_column,
                ], spacing=10),
            )

        def get_active_tab_content():
            if active_tab == "milestones":
                return build_milestones_tab()
            elif active_tab == "learners":
                return build_learners_tab()
            return build_performance_tab()

        tab_content_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16),
            content=get_active_tab_content(),
        )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                hero_card,
                tabs_bar,
                ft.Container(height=8),
                tab_content_container,
                ft.Container(height=32),
            ],
            spacing=0,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # DATA FETCHER
    # ─────────────────────────────────────────────────────────────────────────
    async def fetch_analytics_data():
        nonlocal theme_color, playlist_data, analytics_data

        try:
            pl_resp, an_resp, org_data = await asyncio.gather(
                asyncio.wait_for(get_playlist(token, playlist_id), timeout=15),
                asyncio.wait_for(get_playlist_analytics(token, playlist_id), timeout=15),
                asyncio.wait_for(get_my_organisation(token), timeout=15),
                return_exceptions=True,
            )

            # Org Theme
            if isinstance(org_data, dict):
                theme_color = org_data.get("theme_color") or ft.Colors.INDIGO_600

            # Playlist Data
            if isinstance(pl_resp, dict) and "error" not in pl_resp:
                playlist_data = pl_resp

            # Analytics Telemetry
            if isinstance(an_resp, list):
                analytics_data = an_resp
            elif isinstance(an_resp, dict) and "error" not in an_resp:
                analytics_data = an_resp.get("enrollments") or an_resp.get("results") or an_resp.get("data") or []

            # Reveal the bottom appbar only now that content is loaded
            app_bar.visible = True
            content_socket.alignment = None
            content_socket.content = build_main_layout()
            page.update()

        except asyncio.TimeoutError:
            _show_load_error("Connection timed out loading pathway analytics.")
        except Exception as ex:
            _show_load_error(f"Failed to load pathway analytics: {ex}")

    page.run_task(fetch_analytics_data)

    return ft.View(
        route=f"/organisations/{org_id}/playlists/{playlist_id}/analytics",
        padding=0,
        controls=[
            content_socket,
            app_bar,
        ],
    )
