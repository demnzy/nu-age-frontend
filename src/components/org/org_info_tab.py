import flet as ft
from src.components.org.org_edit_modal import open_org_edit_modal
from src.components.org.org_plan_modal import open_org_plan_modal
from src.requests.payments import get_org_payment_history
from src.utils.file_opener import safe_set_clipboard, show_page_snackbar


def build_org_info_tab(
    page: ft.Page,
    org_data: dict,
    theme_color: str,
    token: str = None,
    on_org_updated=None,
    on_plan_upgraded=None,
) -> ft.Column:
    """
    Renders the Organization Details & Subscription Capacity tab.
    Displays workspace metadata, subscription limits, capacity utilization meters,
    feature bullets, and quick actions to edit details or upgrade plan.
    """
    org_id = str(org_data.get("id", ""))
    org_name = org_data.get("name", "Academy Workspace")
    org_email = org_data.get("email", "")
    org_phone = org_data.get("number", "")
    org_website = org_data.get("website", "")
    org_address = org_data.get("address", "")

    members_count = int(org_data.get("members", 0))
    courses_count = int(org_data.get("courses", 0))

    plan_data = org_data.get("plan") or {}
    if not isinstance(plan_data, dict):
        plan_data = {}
    plan_name = plan_data.get("name", "Standard Academy")
    plan_features = plan_data.get("features", [])
    max_members = plan_data.get("max_members")
    max_courses = plan_data.get("max_courses")

    share_url = f"https://nu-age.com.ng/organisations/{org_id}/join"

    async def _copy_text(text: str, label: str = "Link"):
        try:
            await safe_set_clipboard(page, text)
            show_page_snackbar(page, f"{label} copied to clipboard!")
        except Exception as ex:
            print(f"[org_info_tab] copy error: {ex}")

    # ── Workspace Information Card ──────────────────────────────────────────
    info_card = ft.Container(
        padding=20,
        bgcolor=ft.Colors.SURFACE,
        border_radius=16,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
        ),
        content=ft.Column(
            spacing=16,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.BUSINESS_ROUNDED, color=theme_color, size=20),
                                ft.Text("Academy Information", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                        ft.OutlinedButton(
                            "Edit Details",
                            icon=ft.Icons.EDIT_OUTLINED,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                                side=ft.BorderSide(1, ft.Colors.with_opacity(0.25, theme_color)),
                            ),
                            on_click=lambda _: open_org_edit_modal(
                                page=page,
                                org_data=org_data,
                                theme_color=theme_color,
                                token=token,
                                on_updated=on_org_updated,
                            ),
                        ),
                    ],
                ),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                ft.ResponsiveRow(
                    run_spacing=14,
                    spacing=14,
                    controls=[
                        ft.Column(
                            col={"xs": 12, "sm": 6},
                            spacing=3,
                            controls=[
                                ft.Text("ORGANIZATION ID", size=9.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Row(
                                    spacing=4,
                                    controls=[
                                        ft.Text(org_id, size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.IconButton(
                                            ft.Icons.CONTENT_COPY_ROUNDED,
                                            icon_size=15,
                                            tooltip="Copy Org ID",
                                            on_click=lambda _: page.run_task(_copy_text, org_id, "Organization ID"),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        ft.Column(
                            col={"xs": 12, "sm": 6},
                            spacing=3,
                            controls=[
                                ft.Text("PRIMARY CONTACT EMAIL", size=9.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(org_email or "Not specified", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                        ft.Column(
                            col={"xs": 12, "sm": 6},
                            spacing=3,
                            controls=[
                                ft.Text("CONTACT PHONE", size=9.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(org_phone or "Not specified", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                        ft.Column(
                            col={"xs": 12, "sm": 6},
                            spacing=3,
                            controls=[
                                ft.Text("OFFICIAL WEBSITE", size=9.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    org_website or "Not specified",
                                    size=13,
                                    weight=ft.FontWeight.W_500,
                                    color=theme_color if org_website else ft.Colors.ON_SURFACE,
                                ),
                            ],
                        ),
                        ft.Column(
                            col={"xs": 12},
                            spacing=3,
                            controls=[
                                ft.Text("CAMPUS ADDRESS", size=9.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(org_address or "Not specified", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    )

    # ── Capacity Utilization Bars ────────────────────────────────────────────
    capacity_bars = []

    # Member / Seats Meter
    if max_members:
        member_ratio = min(1.0, members_count / max_members) if max_members > 0 else 0.0
        member_bar_color = (
            ft.Colors.RED_600 if member_ratio >= 0.95
            else (ft.Colors.AMBER_600 if member_ratio >= 0.80 else ft.Colors.INDIGO_500)
        )
        capacity_bars.append(
            ft.Column(
                spacing=4,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Enrolled Seats Usage", size=11.5, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ft.Text(f"{members_count} / {max_members} ({int(member_ratio * 100)}%)", size=11, weight=ft.FontWeight.BOLD, color=member_bar_color),
                        ],
                    ),
                    ft.ProgressBar(
                        value=member_ratio,
                        color=member_bar_color,
                        bgcolor=ft.Colors.with_opacity(0.12, member_bar_color),
                        border_radius=ft.BorderRadius.all(4),
                        height=6,
                    ),
                ],
            )
        )

    # Course Meter
    if max_courses:
        course_ratio = min(1.0, courses_count / max_courses) if max_courses > 0 else 0.0
        course_bar_color = (
            ft.Colors.RED_600 if course_ratio >= 0.95
            else (ft.Colors.AMBER_600 if course_ratio >= 0.80 else ft.Colors.BLUE_500)
        )
        capacity_bars.append(
            ft.Column(
                spacing=4,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Published Curricula Usage", size=11.5, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ft.Text(f"{courses_count} / {max_courses} ({int(course_ratio * 100)}%)", size=11, weight=ft.FontWeight.BOLD, color=course_bar_color),
                        ],
                    ),
                    ft.ProgressBar(
                        value=course_ratio,
                        color=course_bar_color,
                        bgcolor=ft.Colors.with_opacity(0.12, course_bar_color),
                        border_radius=ft.BorderRadius.all(4),
                        height=6,
                    ),
                ],
            )
        )

    # ── Subscription & Capacity Card ─────────────────────────────────────────
    features_controls = []
    if plan_features and isinstance(plan_features, list):
        for feat in plan_features:
            features_controls.append(
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600, size=15),
                        ft.Text(str(feat), size=12.5, color=ft.Colors.ON_SURFACE),
                    ],
                )
            )

    is_mobile_view = (getattr(page, "width", 600) or 600) < 600

    upgrade_plan_btn = ft.FilledButton(
        "Upgrade Plan",
        icon=ft.Icons.ARROW_UPWARD_ROUNDED,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.PURPLE_600,
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        ),
        on_click=lambda _: open_org_plan_modal(
            page=page,
            org_data=org_data,
            theme_color=theme_color,
            token=token,
            on_plan_upgraded=on_plan_upgraded,
        ),
    )

    if is_mobile_view:
        sub_header_block = ft.Column(
            spacing=10,
            tight=True,
            controls=[
                ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=ft.Colors.PURPLE_500, size=20),
                        ft.Text("Subscription & Capacity", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ],
                ),
                ft.Row(
                    controls=[
                        ft.Container(content=upgrade_plan_btn, expand=True),
                    ],
                ),
            ],
        )
    else:
        sub_header_block = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=ft.Colors.PURPLE_500, size=20),
                        ft.Text("Subscription & Capacity", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ],
                ),
                upgrade_plan_btn,
            ],
        )

    plan_card = ft.Container(
        padding=20,
        bgcolor=ft.Colors.SURFACE,
        border_radius=16,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
        ),
        content=ft.Column(
            spacing=14,
            controls=[
                sub_header_block,
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(plan_name, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_600),
                            content=ft.Text("ACTIVE PLAN", size=9.5, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_600),
                        ),
                    ],
                ),
                ft.Row(
                    spacing=20,
                    controls=[
                        ft.Text(f"Max Seats: {max_members or 'Unlimited'}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"Max Courses: {max_courses or 'Unlimited'}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                ),
                *(capacity_bars if capacity_bars else []),
                ft.Container(height=2),
                ft.Text("Included Features:", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Column(features_controls, spacing=6) if features_controls else ft.Text("Standard LMS capabilities included.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
        ),
    )

    # ── Workspace Billing & Transaction History Card ──────────────────────────
    history_list_socket = ft.Column(spacing=8)

    async def _fetch_and_render_history():
        history_list_socket.controls = [
            ft.Container(
                padding=20,
                alignment=ft.Alignment.CENTER,
                content=ft.Row([
                    ft.ProgressRing(width=16, height=16, color=theme_color, stroke_width=2),
                    ft.Text("Loading payment records…", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            )
        ]
        page.update()

        auth_tok = token or await page.shared_preferences.get("auth_token")
        txs = await get_org_payment_history(auth_tok, org_id)

        if not txs:
            history_list_socket.controls = [
                ft.Container(
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column([
                        ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=28, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("No workspace payment records found.", size=12.5, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("Completed plan upgrades and renewals will appear here with invoice receipts.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                )
            ]
            page.update()
            return

        rows = []
        for tx in txs:
            status_val = str(tx.get("status", "pending")).lower()
            if status_val == "success":
                badge_color = ft.Colors.GREEN_600
                badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)
                status_label = "Success"
            elif status_val == "failed":
                badge_color = ft.Colors.RED_600
                badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.RED_600)
                status_label = "Failed"
            else:
                badge_color = ft.Colors.AMBER_600
                badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
                status_label = status_val.capitalize()

            amount_val = float(tx.get("amount", 0.0))
            ref_val = str(tx.get("reference", ""))
            created_str = str(tx.get("created_at") or "")[:10]
            purpose_raw = str(tx.get("purpose", "org_plan")).replace("_", " ").title()

            rows.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                    content=ft.Row([
                        ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.RECEIPT_ROUNDED, size=15, color=theme_color),
                                ft.Text(
                                    purpose_raw,
                                    size=12.5,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.ON_SURFACE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ], spacing=6, tight=True),
                            ft.Row([
                                ft.Text(created_str, size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("•", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Container(
                                    content=ft.Text(
                                        ref_val,
                                        size=10.5,
                                        weight=ft.FontWeight.W_500,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.CONTENT_COPY_ROUNDED,
                                    icon_size=12,
                                    tooltip="Copy reference",
                                    padding=0,
                                    width=20,
                                    height=20,
                                    on_click=lambda _, r=ref_val: page.run_task(_copy_text, r, "Payment reference"),
                                ),
                            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ], spacing=3, expand=True),
                        ft.Column([
                            ft.Text(f"₦{amount_val:,.0f}", size=12.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                border_radius=6,
                                bgcolor=badge_bg,
                                content=ft.Text(
                                    status_label,
                                    size=9,
                                    weight=ft.FontWeight.BOLD,
                                    color=badge_color,
                                    no_wrap=True,
                                ),
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=3),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                )
            )

        history_list_socket.controls = rows
        page.update()

    page.run_task(_fetch_and_render_history)

    history_card = ft.Container(
        padding=20,
        bgcolor=ft.Colors.SURFACE,
        border_radius=16,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
        ),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, color=ft.Colors.BLUE_500, size=20),
                                ft.Text("Billing & Transaction History", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.REFRESH_ROUNDED,
                            icon_size=18,
                            tooltip="Refresh invoices",
                            on_click=lambda _: page.run_task(_fetch_and_render_history),
                        ),
                    ],
                ),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                history_list_socket,
            ],
        ),
    )

    # ── Shareable Invite Card ────────────────────────────────────────────────
    share_card = ft.Container(
        padding=20,
        bgcolor=ft.Colors.SURFACE,
        border_radius=16,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
        ),
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.SHARE_ROUNDED, color=theme_color, size=20),
                        ft.Text("Academy Join Link", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ],
                ),
                ft.Text(
                    "Share this link with your students and faculty to allow them to request enrollment directly.",
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(share_url, size=12, color=ft.Colors.ON_SURFACE, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.FilledButton(
                                "Copy Link",
                                icon=ft.Icons.CONTENT_COPY_ROUNDED,
                                style=ft.ButtonStyle(
                                    bgcolor=theme_color,
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                                ),
                                on_click=lambda _: page.run_task(_copy_text, share_url, "Join Link"),
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )

    return ft.Column(
        spacing=14,
        controls=[
            info_card,
            plan_card,
            history_card,
            share_card,
        ],
    )
