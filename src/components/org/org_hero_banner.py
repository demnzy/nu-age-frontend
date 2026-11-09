import flet as ft
from src.utils.file_opener import safe_set_clipboard, show_page_snackbar


def build_org_hero_banner(
    page: ft.Page,
    org_data: dict,
    theme_color: str,
    on_info_click=None,
    on_teacher_portal_click=None,
    on_edit_click=None,
) -> ft.Container:
    """
    Renders an executive, responsive organization header banner.
    Overlapping circular logo avatar, semantic brand gradient, and quick share action.
    """
    org_id = str(org_data.get("id", ""))
    org_name = org_data.get("name", "Academy Workspace")
    org_email = org_data.get("email", "")
    org_phone = org_data.get("number", "")
    org_website = org_data.get("website", "")
    org_logo = org_data.get("logo")
    plan_data = org_data.get("plan") or {}
    plan_name = plan_data.get("name", "Free Plan") if isinstance(plan_data, dict) else "Free Plan"

    share_url = f"https://nu-age.com.ng/organisations/{org_id}/join"

    async def _copy_share_link(e=None):
        try:
            await safe_set_clipboard(page, share_url)
            show_page_snackbar(page, "Shareable Join Link copied to clipboard!")
        except Exception as ex:
            print(f"[org_hero_banner] copy link error: {ex}")

    # Circular logo with surface border ring overlapping banner
    logo_circle = ft.Container(
        width=80,
        height=80,
        border_radius=40,
        bgcolor=ft.Colors.SURFACE,
        alignment=ft.Alignment.CENTER,
        border=ft.Border.all(3, ft.Colors.SURFACE),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.15, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
        ),
        content=ft.CircleAvatar(
            radius=36,
            background_image_src=org_logo if org_logo else None,
            bgcolor=theme_color if not org_logo else ft.Colors.SURFACE,
            content=ft.Text(
                org_name[:2].upper() if org_name else "NU",
                size=22,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.WHITE,
            ) if not org_logo else None,
        ),
    )

    contact_items = []
    if org_email:
        contact_items.append(
            ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.EMAIL_OUTLINED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(org_email, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
            )
        )
    if org_phone and org_phone != "+000 0000 0000":
        contact_items.append(
            ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.PHONE_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(org_phone, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
            )
        )
    if org_website:
        contact_items.append(
            ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.LANGUAGE_ROUNDED, size=13, color=theme_color),
                    ft.Text(org_website, size=12, color=theme_color),
                ],
            )
        )

    return ft.Container(
        margin=ft.Margin.symmetric(horizontal=16, vertical=8),
        border_radius=16,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        ),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column(
            spacing=0,
            tight=True,
            controls=[
                # Top Gradient Banner
                ft.Container(
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1),
                        end=ft.Alignment(1, 1),
                        colors=[theme_color, ft.Colors.PRIMARY],
                    ),
                    padding=ft.Padding.only(top=14, left=16, right=12, bottom=38),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED, size=16, color=ft.Colors.WHITE),
                                    ft.Text("Academy Portal", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                                ],
                            ),
                            ft.Row(
                                spacing=2,
                                tight=True,
                                controls=[
                                    *(
                                        [
                                            ft.IconButton(
                                                icon=ft.Icons.SCHOOL_ROUNDED,
                                                icon_color=ft.Colors.WHITE,
                                                icon_size=18,
                                                tooltip="Switch to Faculty Portal",
                                                on_click=on_teacher_portal_click,
                                            )
                                        ]
                                        if on_teacher_portal_click
                                        else []
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.SHARE_ROUNDED,
                                        icon_color=ft.Colors.WHITE,
                                        icon_size=18,
                                        tooltip="Copy Shareable Join Link",
                                        on_click=lambda _: page.run_task(_copy_share_link),
                                    ),
                                    *(
                                        [
                                            ft.IconButton(
                                                icon=ft.Icons.EDIT_ROUNDED,
                                                icon_color=ft.Colors.WHITE,
                                                icon_size=18,
                                                tooltip="Edit Workspace Details",
                                                on_click=on_edit_click,
                                            )
                                        ]
                                        if on_edit_click
                                        else []
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.INFO_OUTLINE_ROUNDED,
                                        icon_color=ft.Colors.WHITE,
                                        icon_size=18,
                                        tooltip="Organization Details",
                                        on_click=on_info_click,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                # Identity Area
                ft.Container(
                    padding=ft.Padding.only(left=20, right=20, bottom=16),
                    content=ft.Column(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Container(margin=ft.Margin.only(top=-38), content=logo_circle),
                                ],
                                alignment=ft.MainAxisAlignment.START,
                            ),
                            ft.Row(
                                spacing=8,
                                wrap=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text(org_name, size=19, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=2.5),
                                        border_radius=6,
                                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_600),
                                        content=ft.Text(
                                            plan_name.upper(),
                                            size=9,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.PURPLE_600,
                                        ),
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=14,
                                wrap=True,
                                controls=contact_items,
                            ) if contact_items else ft.Container(),
                        ],
                    ),
                ),
            ],
        ),
    )
