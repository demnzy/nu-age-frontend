import asyncio
import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.playlists import get_playlist, update_playlist
from src.requests.organisations import get_my_organisation


# ═══════════════════════════════════════════════════════════════════════════════
# MODERN LEARNING PATH (PLAYLIST) SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

def _pill(label: str, bg, fg, icon=None) -> ft.Container:
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=11, color=fg))
    controls.append(ft.Text(label, size=10, color=fg, weight=ft.FontWeight.BOLD))
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        bgcolor=bg,
        border_radius=8,
        content=ft.Row(controls, spacing=4, tight=True),
    )


def _card_header(title: str, subtitle: str = None, action: ft.Control = None) -> ft.Row:
    text_col = ft.Column([
        ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
    ], spacing=2, expand=True)
    if subtitle:
        text_col.controls.append(
            ft.Text(subtitle, size=11, color=ft.Colors.ON_SURFACE_VARIANT)
        )
    controls = [text_col]
    if action:
        controls.append(action)
    return ft.Row(controls, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)


async def playlist_settings_view(page: ft.Page, playlist_id: str) -> ft.View:
    app_bar = get_bottom_appbar(page)
    token = await page.shared_preferences.get("auth_token")
    if not token:
        return _error_view(playlist_id, "Authentication failed. Please log in again.")

    def _go_back(e=None):
        if len(page.views) > 1:
            page.views.pop()
            page.update()
        elif hasattr(page, "on_view_pop") and callable(page.on_view_pop):
            page.on_view_pop(None)
        else:
            page.go("/organisations")

    theme_color = ft.Colors.INDIGO_600

    def show_toast(message: str, color=ft.Colors.GREEN_700):
        snack = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_500),
            bgcolor=color,
            duration=2800,
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def show_error_toast(message: str):
        show_toast(message, color=ft.Colors.RED_700)

    # ── Centered Loading Socket ───────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=44, height=44, stroke_width=3.5),
                ft.Container(height=16),
                ft.Text("Loading Learning Path Configuration…", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
        ),
    )

    async def load_all_data():
        nonlocal theme_color
        try:
            pl_task = get_playlist(token, playlist_id)
            org_task = get_my_organisation(token)

            playlist_data, org_data = await asyncio.gather(pl_task, org_task, return_exceptions=True)

            if not playlist_data or (isinstance(playlist_data, dict) and "error" in playlist_data):
                content_socket.content = _build_error_widget("Learning pathway not found or could not be loaded.")
                page.update()
                return

            if isinstance(org_data, dict) and org_data.get("theme_color"):
                theme_color = org_data.get("theme_color")

            content_socket.alignment = None
            content_socket.content = build_settings_ui(playlist_data)
            page.update()

        except Exception as ex:
            content_socket.content = _build_error_widget(f"Failed to load pathway settings: {ex}")
            page.update()

    def _build_error_widget(msg: str):
        return ft.Container(
            padding=32,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=48, color=ft.Colors.RED_400),
                    ft.Text("Configuration Unavailable", size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(msg, size=12, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=8),
                    ft.FilledButton(
                        "Return to Dashboard",
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: page.go("/organisations"),
                    ),
                ],
            ),
        )

    def build_settings_ui(playlist_data: dict):
        path_name = playlist_data.get("name") or "Untitled Learning Pathway"
        path_desc = playlist_data.get("description") or ""
        effective_org_id = playlist_data.get("org_id") or ""
        is_public_track = bool(playlist_data.get("is_public") if "is_public" in playlist_data else playlist_data.get("public", False))

        raw_courses = playlist_data.get("playlist_courses") or playlist_data.get("courses") or []
        courses_list = []
        for item in raw_courses:
            if isinstance(item, dict):
                if "course" in item and isinstance(item["course"], dict):
                    courses_list.append(item["course"])
                else:
                    courses_list.append(item)
            elif isinstance(item, str):
                courses_list.append({"name": f"Course {item[:6]}"})

        num_courses = len(courses_list)

        # ── HERO HEADER CARD ─────────────────────────────────────────────────
        pub_badge = (
            _pill("PUBLIC TRACK", ft.Colors.GREEN_700, ft.Colors.WHITE, ft.Icons.PUBLIC_ROUNDED)
            if is_public_track
            else _pill("CAMPUS TRACK", ft.Colors.BLUE_700, ft.Colors.WHITE, ft.Icons.LOCK_ROUNDED)
        )

        hero_card = ft.Container(
            margin=ft.Margin.symmetric(horizontal=16, vertical=8),
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column([
                # Top Gradient
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
                                tooltip="Back",
                                on_click=_go_back,
                            ),
                            ft.Text("Pathway Configuration & Settings", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                        ], spacing=4),
                        ft.Row([
                            ft.IconButton(
                                ft.Icons.BAR_CHART_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=17,
                                tooltip="Pathway Analytics",
                                on_click=lambda _: page.go(f"/organisations/{effective_org_id}/playlists/{playlist_id}/analytics" if effective_org_id else f"/playlists/{playlist_id}/analytics"),
                            ),
                            ft.IconButton(
                                ft.Icons.EDIT_ROAD_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=17,
                                tooltip="Curriculum Roadmap Builder",
                                on_click=lambda _: page.go(f"/playlists/{playlist_id}/build"),
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
                # Breadcrumb & Info Body
                ft.Container(
                    padding=ft.Padding.all(16),
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.HOME_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("Academy", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("Learning Paths", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(path_name, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ], spacing=4, wrap=True),
                        ft.Text(path_name, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                        ft.Row([
                            pub_badge,
                            ft.Row([
                                ft.Icon(ft.Icons.LAYERS_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"{num_courses} Sequenced Courses in Pathway", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                            ], spacing=4),
                        ], spacing=8),
                    ], spacing=6),
                ),
            ], spacing=0),
        )

        # ── CARD 1: GENERAL INFORMATION ───────────────────────────────────────
        name_input = ft.TextField(
            value=path_name,
            label="Learning Path Name",
            hint_text="e.g. Distributed Systems & Site Reliability Track",
            prefix_icon=ft.Icons.ROUTE_ROUNDED,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
            dense=True,
            expand=True,
        )

        desc_input = ft.TextField(
            value=path_desc,
            label="Track Curriculum Overview & Learning Objectives",
            hint_text="Explain the goal of this sequential curriculum and what competencies graduates achieve…",
            prefix_icon=ft.Icons.DESCRIPTION_OUTLINED,
            multiline=True,
            min_lines=2,
            max_lines=4,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
            dense=True,
            expand=True,
        )

        save_general_btn = ft.FilledButton(
            "Save Changes",
            icon=ft.Icons.CHECK_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=theme_color,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            ),
        )

        async def on_save_general(e):
            save_general_btn.disabled = True
            save_general_btn.text = "Saving…"
            page.update()

            title_val = name_input.value.strip()
            if not title_val:
                show_error_toast("Pathway name cannot be empty.")
                save_general_btn.disabled = False
                save_general_btn.text = "Save Changes"
                page.update()
                return

            try:
                res1 = await update_playlist(token, playlist_id, {"name": title_val})
                res2 = await update_playlist(token, playlist_id, {"description": desc_input.value.strip()})
                if (isinstance(res1, dict) and "error" in res1) or (isinstance(res2, dict) and "error" in res2):
                    show_error_toast("Failed to update pathway details.")
                else:
                    show_toast("Pathway details saved successfully.")
            except Exception as ex:
                show_error_toast(f"Error saving pathway: {ex}")
            finally:
                save_general_btn.disabled = False
                save_general_btn.text = "Save Changes"
                page.update()

        save_general_btn.on_click = lambda e: page.run_task(on_save_general, e)

        general_card = ft.Container(
            margin=ft.Margin.symmetric(horizontal=16, vertical=6),
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _card_header(
                    "General Information",
                    "Foundational pathway identity and pedagogical overview",
                    save_general_btn,
                ),
                ft.Container(height=10),
                name_input,
                ft.Container(height=4),
                desc_input,
            ], spacing=6),
        )

        # ── CARD 2: ACCESS & DISCOVERABILITY ──────────────────────────────────
        selected_is_public = is_public_track

        def build_track_access_card(is_pub: bool, title: str, subtitle: str, icon):
            is_active = (selected_is_public == is_pub)
            border_col = theme_color if is_active else ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)
            bg_col = ft.Colors.with_opacity(0.08, theme_color) if is_active else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE)

            def select_access(e):
                nonlocal selected_is_public
                selected_is_public = is_pub
                access_card.content.controls[2] = render_access_options()
                page.update()

            return ft.Container(
                expand=True,
                bgcolor=bg_col,
                border_radius=10,
                border=ft.Border.all(1.5 if is_active else 1, border_col),
                padding=ft.Padding.all(14),
                ink=True,
                on_click=select_access,
                content=ft.Row([
                    ft.Container(
                        width=36, height=36, border_radius=18,
                        bgcolor=ft.Colors.with_opacity(0.12, theme_color if is_active else ft.Colors.ON_SURFACE),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=18, color=theme_color if is_active else ft.Colors.ON_SURFACE_VARIANT),
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color=theme_color if is_active else ft.Colors.ON_SURFACE),
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=14, color=theme_color) if is_active else ft.Container(),
                        ], spacing=4),
                        ft.Text(subtitle, size=11, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2),
                    ], spacing=2, expand=True),
                ], spacing=12),
            )

        def render_access_options():
            return ft.ResponsiveRow([
                ft.Container(content=build_track_access_card(False, "Campus Track", "Exclusively accessible to verified students & faculty of this academy", ft.Icons.LOCK_ROUNDED), col={"xs": 12, "md": 6}),
                ft.Container(content=build_track_access_card(True, "Public Track", "Discoverable and open to all learners across Nu-Age worldwide", ft.Icons.PUBLIC_ROUNDED), col={"xs": 12, "md": 6}),
            ], spacing=8, run_spacing=8)

        save_access_btn = ft.FilledButton(
            "Save Visibility",
            icon=ft.Icons.CHECK_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=theme_color,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            ),
        )

        async def on_save_access(e):
            save_access_btn.disabled = True
            save_access_btn.text = "Saving…"
            page.update()

            try:
                res = await update_playlist(token, playlist_id, {"is_public": selected_is_public})
                if isinstance(res, dict) and "error" in res:
                    show_error_toast(f"Failed to update visibility: {res['error']}")
                else:
                    show_toast("Pathway visibility updated.")
            except Exception as ex:
                show_error_toast(f"Error saving visibility: {ex}")
            finally:
                save_access_btn.disabled = False
                save_access_btn.text = "Save Visibility"
                page.update()

        save_access_btn.on_click = lambda e: page.run_task(on_save_access, e)

        access_card = ft.Container(
            margin=ft.Margin.symmetric(horizontal=16, vertical=6),
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _card_header(
                    "Track Access & Visibility",
                    "Control whether this sequential pathway is restricted to campus or published globally",
                    save_access_btn,
                ),
                ft.Container(height=8),
                render_access_options(),
            ], spacing=6),
        )

        # ── CARD 3: CURRICULUM ROADMAP BUILDER LINK ───────────────────────────
        roadmap_preview_items = []
        if courses_list:
            for idx, c in enumerate(courses_list[:4]):
                c_title = c.get("name") or f"Course {idx + 1}"
                roadmap_preview_items.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        content=ft.Row([
                            ft.Container(
                                width=20, height=20, border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(str(idx + 1), size=10, weight=ft.FontWeight.BOLD, color=theme_color),
                            ),
                            ft.Text(c_title, size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                        ], spacing=8),
                    )
                )
            if len(courses_list) > 4:
                roadmap_preview_items.append(
                    ft.Text(f"+ {len(courses_list) - 4} more courses in sequence", size=11, color=ft.Colors.ON_SURFACE_VARIANT, italic=True)
                )
        else:
            roadmap_preview_items.append(
                ft.Text("No courses mapped to this roadmap yet. Open the builder to drag and map courses.", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
            )

        curriculum_card = ft.Container(
            margin=ft.Margin.symmetric(horizontal=16, vertical=6),
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _card_header(
                    "Curated Curriculum Roadmap",
                    "Sequence courses, set prerequisites, and organize sequential milestones",
                ),
                ft.Container(height=6),
                ft.Column(roadmap_preview_items, spacing=6),
                ft.Container(height=8),
                ft.Row([
                    ft.FilledButton(
                        "Launch Roadmap Builder",
                        icon=ft.Icons.EDIT_ROAD_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=theme_color,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                        ),
                        on_click=lambda _: page.go(f"/playlists/{playlist_id}/build"),
                    ),
                ], alignment=ft.MainAxisAlignment.START),
            ], spacing=6),
        )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                hero_card,
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    content=ft.Container(
                        width=860,
                        content=ft.Column([
                            general_card,
                            access_card,
                            curriculum_card,
                            ft.Container(height=32),
                        ], spacing=4),
                    ),
                ),
            ],
            spacing=0,
        )

    page.run_task(load_all_data)

    return ft.View(
        route=f"/playlists/{playlist_id}/settings",
        padding=0,
        bottom_appbar=app_bar,
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket,
            )
        ],
    )


def _error_view(playlist_id: str, message: str) -> ft.View:
    return ft.View(
        route=f"/playlists/{playlist_id}/settings",
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=52, color=ft.Colors.RED_400),
                            ft.Text(message, size=15, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                        ],
                    ),
                ),
            )
        ],
    )
