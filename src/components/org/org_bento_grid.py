import flet as ft


def build_org_bento_grid(
    stats: dict,
    on_tab_switch=None,
    on_upgrade_click=None,
) -> ft.ResponsiveRow:
    """
    Renders the 4-card interactive KPI Bento Grid for Organization Admins.
    Fully responsive with clean tap-to-switch tab interactions and direct upgrade action.
    """
    def _card(
        icon_name,
        title: str,
        main_val: str,
        subtitle: str,
        tint_color: str,
        tab_key: str = None,
        custom_on_click=None,
    ) -> ft.Container:
        click_fn = custom_on_click or ((lambda _: on_tab_switch(tab_key)) if (tab_key and on_tab_switch) else None)
        return ft.Container(
            col={"xs": 6, "sm": 6, "md": 3},
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            padding=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            ink=bool(click_fn),
            on_click=click_fn,
            content=ft.Column(
                spacing=2,
                tight=True,
                controls=[
                    ft.Row(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.Container(
                                padding=6,
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.12, tint_color),
                                content=ft.Icon(icon_name, size=16, color=tint_color),
                            ),
                            ft.Text(
                                title,
                                size=9.5,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    ft.Container(height=2),
                    ft.Text(
                        str(main_val),
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    ft.Text(
                        subtitle,
                        size=10.5,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
            ),
        )

    return ft.ResponsiveRow(
        spacing=10,
        run_spacing=10,
        controls=[
            _card(
                ft.Icons.GROUPS_ROUNDED,
                "TOTAL MEMBERS",
                str(stats.get("members", 0)),
                f"{stats.get('students', 0)} Learners · {stats.get('staff', 0)} Faculty",
                ft.Colors.INDIGO_500,
                "members",
            ),
            _card(
                ft.Icons.AUTO_STORIES_ROUNDED,
                "COURSE CATALOG",
                str(stats.get("courses", 0)),
                f"{stats.get('public_courses', 0)} Public · {stats.get('campus_courses', 0)} Campus",
                ft.Colors.BLUE_500,
                "courses",
            ),
            _card(
                ft.Icons.PLAYLIST_PLAY_ROUNDED,
                "LEARNING TRACKS",
                str(stats.get("playlists", 0)),
                "Curated roadmaps",
                ft.Colors.AMBER_600,
                "playlists",
            ),
            _card(
                ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                "TIER & CAPACITY",
                str(stats.get("plan", "Standard")),
                f"{stats.get('members', 0)} / {stats.get('max_members') or '∞'} Seats",
                ft.Colors.PURPLE_500,
                "info",
                custom_on_click=(lambda _: on_upgrade_click()) if on_upgrade_click else None,
            ),
        ],
    )

