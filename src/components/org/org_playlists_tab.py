import asyncio
import base64
import flet as ft
from src.requests.playlists import create_playlist
from src.utils.file_opener import show_page_snackbar


def build_org_playlists_tab(
    page: ft.Page,
    org_id: str,
    playlists: list,
    theme_color: str,
    token: str,
    on_playlist_created=None,
) -> ft.Column:
    """
    Renders the Curated Learning Paths (Tracks) tab for organization administrators.
    Provides roadmap management, pathway analytics, and a modal for creating new paths.
    """
    content_holder = ft.Column(spacing=12)

    def _build_playlist_card(p: dict) -> ft.Container:
        pid = str(p.get("id", ""))
        title = p.get("name", "Learning Track")
        desc = p.get("description", "Curated roadmap for mastering core competencies.")
        img = p.get("image_url")

        return ft.Container(
            col={"xs": 12, "sm": 6, "lg": 4},
            bgcolor=ft.Colors.SURFACE,
            border_radius=16,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                blur_radius=10,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(
                spacing=0,
                controls=[
                    ft.Container(
                        height=120,
                        width=float("inf"),
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        content=ft.Image(
                            src=img or "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
                            fit=ft.BoxFit.COVER,
                        ),
                    ),
                    ft.Container(
                        padding=14,
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Text(
                                    title,
                                    size=14.5,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.ON_SURFACE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    desc,
                                    size=11.5,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Container(height=4),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                                            border_radius=8,
                                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                                            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.AMBER_600)),
                                            content=ft.Text(
                                                "LEARNING PATH",
                                                size=9.5,
                                                weight=ft.FontWeight.BOLD,
                                                color=ft.Colors.AMBER_700,
                                            ),
                                        ),
                                        ft.Row(
                                            spacing=0,
                                            tight=True,
                                            controls=[
                                                ft.IconButton(
                                                    ft.Icons.EDIT_ROAD_ROUNDED,
                                                    tooltip="Manage Roadmap",
                                                    icon_size=17,
                                                    icon_color=theme_color,
                                                    on_click=lambda _, p_id=pid: page.navigate(f"/playlists/{p_id}/build"),
                                                ),
                                                ft.IconButton(
                                                    ft.Icons.BAR_CHART_ROUNDED,
                                                    tooltip="Pathway Analytics",
                                                    icon_size=17,
                                                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                                    on_click=lambda _, p_id=pid: page.navigate(f"/organisations/{org_id}/playlists/{p_id}/analytics"),
                                                ),
                                                ft.IconButton(
                                                    ft.Icons.SETTINGS_OUTLINED,
                                                    tooltip="Playlist Settings",
                                                    icon_size=17,
                                                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                                    on_click=lambda _, p_id=pid: page.navigate(f"/playlists/{p_id}/settings"),
                                                ),
                                                ft.IconButton(
                                                    ft.Icons.VISIBILITY_OUTLINED,
                                                    tooltip="View Learning Path",
                                                    icon_size=17,
                                                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                                    on_click=lambda _, p_id=pid: page.navigate(f"/playlists/{p_id}"),
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

    def _rebuild_cards():
        if playlists:
            cards = [_build_playlist_card(p) for p in playlists]
            content_holder.controls = [ft.ResponsiveRow(controls=cards, run_spacing=14, spacing=14)]
        else:
            content_holder.controls = [
                ft.Container(
                    padding=ft.Padding.symmetric(vertical=48, horizontal=24),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.PLAYLIST_PLAY_ROUNDED, size=46, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                            ft.Text(
                                "No learning paths created yet.",
                                size=14,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.ON_SURFACE,
                            ),
                            ft.Text(
                                "Bundle courses into guided roadmaps to guide student progression.",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=6),
                            ft.FilledButton(
                                "Create Learning Path",
                                icon=ft.Icons.ADD_ROUNDED,
                                style=ft.ButtonStyle(
                                    bgcolor=theme_color,
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                ),
                                on_click=lambda _: open_create_modal(),
                            ),
                        ],
                    ),
                )
            ]

    # Modal for creating a new learning path
    def open_create_modal(e=None):
        name_input = ft.TextField(
            label="Learning Path Title *",
            hint_text="e.g. Fullstack Cloud Track",
            border_radius=8,
            dense=True,
            text_size=13,
            border_color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
        )
        desc_input = ft.TextField(
            label="Short Description",
            hint_text="Curated roadmap to master this track...",
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=8,
            dense=True,
            text_size=13,
            border_color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
        )
        public_switch = ft.Switch(
            label="Public Track (Catalog Visibility)",
            value=True,
            active_color=theme_color,
        )

        selected_bytes = None
        selected_name = None
        logo_icon = ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color=theme_color, size=24)
        logo_text = ft.Text("Upload Track Cover (Optional)", color=ft.Colors.ON_SURFACE_VARIANT, size=12)

        async def _pick_cover(ev=None):
            nonlocal selected_bytes, selected_name
            try:
                files = await ft.FilePicker().pick_files(
                    allow_multiple=False,
                    file_type=ft.FilePickerFileType.IMAGE,
                    with_data=True,
                )
                if files:
                    sel = files[0]
                    selected_bytes = sel.bytes
                    selected_name = sel.name
                    logo_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                    logo_icon.color = ft.Colors.GREEN_600
                    logo_text.value = f"Selected: {selected_name}"
                    logo_text.color = ft.Colors.GREEN_600
                    page.update()
            except Exception as pex:
                print(f"[org_playlists_tab] file picker error: {pex}")

        cover_container = ft.Container(
            width=float("inf"),
            padding=ft.Padding.symmetric(vertical=14, horizontal=16),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)),
            border_radius=10,
            ink=True,
            on_click=lambda _: page.run_task(_pick_cover),
            content=ft.Row([logo_icon, logo_text], spacing=10, alignment=ft.MainAxisAlignment.CENTER),
        )

        error_label = ft.Text("", color=ft.Colors.RED_600, size=12, visible=False, weight=ft.FontWeight.W_500)

        def _close_dialog(ev=None):
            playlist_dialog.open = False
            page.update()

        async def _submit(ev=None):
            nonlocal selected_bytes, selected_name
            title_val = name_input.value.strip() if name_input.value else ""
            if not title_val:
                error_label.value = "Learning Track Title is required."
                error_label.visible = True
                page.update()
                return

            error_label.visible = False
            submit_btn.disabled = True
            submit_btn.content = ft.Row([
                ft.ProgressRing(width=14, height=14, color=ft.Colors.WHITE, stroke_width=2),
                ft.Text("Creating Track…", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_600),
            ], tight=True, spacing=8)
            page.update()

            try:
                logo_b64 = (
                    base64.b64encode(selected_bytes).decode("utf-8")
                    if selected_bytes else None
                )
                payload = {
                    "name": title_val,
                    "description": desc_input.value.strip() if desc_input.value else title_val,
                    "is_public": public_switch.value,
                    "image_bytes": logo_b64,
                    "image_filename": selected_name,
                    "org_id": org_id,
                }

                auth_tok = token or await page.shared_preferences.get("auth_token")
                new_pl = await asyncio.wait_for(create_playlist(auth_tok, payload), timeout=25)

                if isinstance(new_pl, dict) and "id" in new_pl:
                    playlists.insert(0, new_pl)
                    _rebuild_cards()
                    _close_dialog()
                    if on_playlist_created:
                        on_playlist_created(new_pl)
                    show_page_snackbar(page, f"Learning Track '{title_val}' created!")
                else:
                    err_msg = new_pl.get("error", "Failed to create track") if isinstance(new_pl, dict) else "Unknown error"
                    error_label.value = f"Could not create track: {err_msg}"
                    error_label.visible = True
                    submit_btn.disabled = False
                    submit_btn.content = ft.Text("Create Path", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
                    page.update()
            except asyncio.TimeoutError:
                error_label.value = "Request timed out. Please check your playlist catalog."
                error_label.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text("Create Path", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
                page.update()
            except Exception as ex:
                error_label.value = f"Error: {ex}"
                error_label.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text("Create Path", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
                page.update()

        submit_btn = ft.FilledButton(
            "Create Path",
            style=ft.ButtonStyle(bgcolor=theme_color, shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=lambda _: page.run_task(_submit),
        )
        cancel_btn = ft.TextButton("Cancel", on_click=_close_dialog)

        screen_width = getattr(page, "width", 500) or 500
        dialog_width = min(screen_width - 32, 460)

        playlist_dialog = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Row([
                ft.Icon(ft.Icons.PLAYLIST_PLAY_ROUNDED, color=theme_color, size=22),
                ft.Text("Create Learning Path", weight=ft.FontWeight.BOLD, size=16),
            ], spacing=8),
            content=ft.Container(
                width=dialog_width,
                content=ft.Column([
                    name_input,
                    desc_input,
                    public_switch,
                    cover_container,
                    error_label,
                ], tight=True, spacing=10),
            ),
            actions=[cancel_btn, submit_btn],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(playlist_dialog)
        playlist_dialog.open = True
        page.update()

    # Initial setup
    _rebuild_cards()

    # Header Row
    header_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(
                spacing=1,
                expand=True,
                controls=[
                    ft.Text(
                        "Curated Learning Paths",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ON_SURFACE,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        f"{len(playlists)} guided tracks configured",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
            ),
            ft.FilledButton(
                "New Path",
                icon=ft.Icons.ADD_ROUNDED,
                style=ft.ButtonStyle(
                    bgcolor=theme_color,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                ),
                on_click=lambda _: open_create_modal(),
            ),
        ],
    )

    return ft.Column(
        spacing=14,
        controls=[
            header_row,
            content_holder,
        ],
    )

