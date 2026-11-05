import asyncio
import flet as ft
from src.requests.organisations import get_org_plans
from src.requests.payments import initialize_payment, verify_payment, get_org_payment_history
from src.utils.file_opener import safe_set_clipboard
from src.utils.file_opener import show_page_snackbar


def open_org_billing_history_modal(page: ft.Page, org_id: str, theme_color: str, token: str):
    def _close_hist(e=None):
        hist_dialog.open = False
        page.update()

    hist_socket = ft.Column(spacing=8)

    async def _copy_ref(text: str):
        await safe_set_clipboard(page, text)
        show_page_snackbar(page, "Reference copied to clipboard!")

    async def _load_txs():
        auth_tok = token or await page.shared_preferences.get("auth_token")
        txs = await get_org_payment_history(auth_tok, org_id)
        if not txs:
            hist_socket.controls = [
                ft.Container(
                    padding=32,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column([
                        ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=32, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("No workspace transaction records yet.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("Plan upgrades and subscription renewals will be listed here.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                )
            ]
            page.update()
            return

        rows = []
        for tx in txs:
            status_val = str(tx.get("status", "pending")).lower()
            if status_val == "success":
                b_color = ft.Colors.GREEN_600
                b_bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)
                lbl = "Success"
            elif status_val == "failed":
                b_color = ft.Colors.RED_600
                b_bg = ft.Colors.with_opacity(0.12, ft.Colors.RED_600)
                lbl = "Failed"
            else:
                b_color = ft.Colors.AMBER_600
                b_bg = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
                lbl = status_val.capitalize()

            amount_val = float(tx.get("amount", 0.0))
            ref_val = str(tx.get("reference", ""))
            created_str = str(tx.get("created_at") or "")[:10]
            purpose_raw = str(tx.get("purpose", "org_plan")).replace("_", " ").title()

            rows.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=ft.Row([
                        ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.RECEIPT_ROUNDED, size=15, color=theme_color),
                                ft.Text(purpose_raw, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ], spacing=6, tight=True),
                            ft.Row([
                                ft.Text(created_str, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("•", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(ref_val, size=11, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.IconButton(
                                    icon=ft.Icons.CONTENT_COPY_ROUNDED,
                                    icon_size=13,
                                    tooltip="Copy reference",
                                    padding=0,
                                    on_click=lambda _, r=ref_val: page.run_task(_copy_ref, r),
                                ),
                            ], spacing=4, tight=True),
                        ], spacing=2, expand=True),
                        ft.Column([
                            ft.Text(f"₦{amount_val:,.0f}", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                border_radius=6,
                                bgcolor=b_bg,
                                content=ft.Text(lbl, size=9.5, weight=ft.FontWeight.BOLD, color=b_color),
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                )
            )
        hist_socket.controls = rows
        page.update()

    hist_socket.controls = [
        ft.Container(
            padding=24,
            alignment=ft.Alignment.CENTER,
            content=ft.Row([
                ft.ProgressRing(width=16, height=16, color=theme_color, stroke_width=2),
                ft.Text("Fetching transactions…", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
        )
    ]

    hist_dialog = ft.AlertDialog(
        modal=True,
        bgcolor=ft.Colors.SURFACE,
        shape=ft.RoundedRectangleBorder(radius=16),
        title=ft.Row([
            ft.Row([
                ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, color=theme_color, size=22),
                ft.Text("Workspace Billing History", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8, tight=True),
            ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=_close_hist),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        content=ft.Container(
            width=500,
            content=ft.Column([hist_socket], tight=True, scroll=ft.ScrollMode.AUTO),
        ),
        actions=[
            ft.TextButton("Close", on_click=_close_hist),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(hist_dialog)
    hist_dialog.open = True
    page.update()
    page.run_task(_load_txs)


def open_org_plan_modal(
    page: ft.Page,
    org_data: dict,
    theme_color: str,
    token: str,
    on_plan_upgraded=None,
):
    """
    Renders an executive, responsive Plan Comparison & Upgrade Modal for organization owners.
    Features tier cards loaded directly from the database with seat/course quotas,
    exact pricing, and direct Paystack checkout integration.
    """
    org_id = str(org_data.get("id", ""))
    plan_data = org_data.get("plan") or {}
    current_plan_name = (plan_data.get("name") if isinstance(plan_data, dict) else "Free Plan") or "Free Plan"
    current_plan_id = str(plan_data.get("id", "")) if isinstance(plan_data, dict) else ""

    loading_container = ft.Container(
        padding=40,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            tight=True,
            controls=[
                ft.ProgressRing(color=theme_color, width=32, height=32),
                ft.Text("Loading academy tier catalog…", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
        ),
    )

    plans_container = ft.Column(spacing=14)
    modal_content = ft.Container(content=loading_container)

    def _format_price(price: float, name: str = "") -> str:
        if name.strip().lower() == "unlimited":
            return "Perpetual Flagship"
        if not price or price <= 0:
            return "Free Forever"
        return f"₦{price:,.0f} / month" 
        return f"₦{price:,.0f} / month"

    async def _start_upgrade(plan: dict):
        plan_id = str(plan.get("id", ""))
        plan_name = plan.get("name", "Academy Tier")
        amount = float(plan.get("price", 0.0))

        if amount <= 0:
            show_page_snackbar(page, f"You are already eligible for {plan_name}.")
            return

        # Show pending payment UI
        upgrade_dialog.open = False
        page.update()

        auth_tok = token or await page.shared_preferences.get("auth_token")
        init_res = await initialize_payment(
            token=auth_tok,
            amount=amount,
            purpose="org_plan",
            organisation_id=org_id,
            metadata={
                "plan_id": plan_id,
            },
        )

        if not isinstance(init_res, dict) or "authorization_url" not in init_res:
            err = init_res.get("error", "Failed to initialize payment gateway.") if isinstance(init_res, dict) else "Error"
            show_page_snackbar(page, f"Payment error: {err}")
            return

        auth_url = init_res.get("authorization_url")
        reference = init_res.get("reference")

        # Open payment checkout in browser
        try:
            await page.launch_url(auth_url)
        except Exception:
            pass

        # Present Verification modal
        def _close_verify(e=None):
            verify_dlg.open = False
            page.update()

        async def _do_verify(e=None):
            verify_btn.disabled = True
            verify_btn.content = ft.Row([
                ft.ProgressRing(width=14, height=14, color=ft.Colors.WHITE, stroke_width=2),
                ft.Text("Verifying Transaction…", size=12, color=ft.Colors.WHITE),
            ], tight=True, spacing=6)
            page.update()

            try:
                v_res = await asyncio.wait_for(verify_payment(auth_tok, reference), timeout=25)
                if isinstance(v_res, dict) and v_res.get("status") == "success":
                    _close_verify()
                    show_page_snackbar(page, f"Success! Workspace upgraded to {plan_name}.")
                    if on_plan_upgraded:
                        on_plan_upgraded(plan)
                else:
                    err_msg = v_res.get("error", "Transaction could not be confirmed.") if isinstance(v_res, dict) else "Incomplete transaction."
                    verify_status.value = f"Verification status: {err_msg}"
                    verify_status.visible = True
                    verify_btn.disabled = False
                    verify_btn.content = ft.Text("Verify Payment", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
                    page.update()
            except Exception as vex:
                verify_status.value = f"Verification error: {vex}"
                verify_status.visible = True
                verify_btn.disabled = False
                verify_btn.content = ft.Text("Verify Payment", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
                page.update()

        verify_btn = ft.FilledButton(
            "Verify Payment",
            style=ft.ButtonStyle(bgcolor=theme_color, shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=lambda _: page.run_task(_do_verify),
        )
        verify_status = ft.Text("", color=ft.Colors.RED_600, size=12, visible=False)

        verify_dlg = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Row([
                ft.Icon(ft.Icons.PAYMENT_ROUNDED, color=theme_color, size=22),
                ft.Text("Complete Upgrade", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=380,
                content=ft.Column([
                    ft.Text(f"A checkout tab was opened for {plan_name}.", size=13, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"Amount: ₦{amount:,.0f}", size=14, weight=ft.FontWeight.BOLD, color=theme_color),
                    ft.Text("After completing payment on Paystack, tap below to confirm and apply your new limits immediately.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    verify_status,
                ], tight=True, spacing=10),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_close_verify),
                verify_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(verify_dlg)
        verify_dlg.open = True
        page.update()

    def _render_plans(plans_list: list):
        if not plans_list:
            modal_content.content = ft.Container(
                padding=ft.Padding.symmetric(vertical=48, horizontal=24),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.WORKSPACE_PREMIUM_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            "No Organization Plans Configured",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.ON_SURFACE,
                        ),
                        ft.Text(
                            "There are currently no active organization subscription tiers configured on the platform.",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )
            page.update()
            return

        col_span = 12 if len(plans_list) == 1 else (6 if len(plans_list) == 2 else 4)
        cards = []
        for p in plans_list:
            p_name = p.get("name", "Tier")
            p_desc = p.get("description", "")
            p_price = float(p.get("price", 0.0))
            max_m = p.get("max_members")
            max_c = p.get("max_courses")
            features = p.get("features", [])

            is_current = (
                p_name.strip().lower() == current_plan_name.strip().lower()
                or (str(p.get("id", "")) == current_plan_id and current_plan_id != "")
            )
            is_popular = "growth" in p_name.lower() or "pro" in p_name.lower()

            feature_widgets = []
            if isinstance(features, list):
                for feat in features:
                    feature_widgets.append(
                        ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=14, color=ft.Colors.GREEN_600),
                                ft.Text(str(feat), size=11.5, color=ft.Colors.ON_SURFACE),
                            ],
                        )
                    )

            badge_row = []
            if is_current:
                badge_row.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2.5),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.GREEN_600)),
                        content=ft.Text("CURRENT PLAN", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
                    )
                )
            elif is_popular:
                badge_row.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2.5),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, theme_color)),
                        content=ft.Text("MOST POPULAR", size=9, weight=ft.FontWeight.BOLD, color=theme_color),
                    )
                )

            is_unlimited = (p_name.strip().lower() == "unlimited")
            if is_unlimited and not is_current:
                badge_row.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2.5),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_600),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.PURPLE_600)),
                        content=ft.Text("FLAGSHIP TIER", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_600),
                    )
                )

            action_button = (
                ft.OutlinedButton(
                    "Current Plan",
                    disabled=True,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                )
                if is_current
                else (
                    ft.OutlinedButton(
                        "Ecosystem Partner",
                        disabled=True,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    )
                    if is_unlimited
                    else ft.FilledButton(
                        "Upgrade Tier" if p_price > 0 else "Select Free",
                        style=ft.ButtonStyle(
                            bgcolor=theme_color if is_popular else ft.Colors.PRIMARY,
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                        on_click=lambda _, pl=p: page.run_task(_start_upgrade, pl),
                    )
                )
            )

            card = ft.Container(
                col={"xs": 12, "md": col_span},
                bgcolor=ft.Colors.SURFACE,
                border_radius=16,
                padding=18,
                border=ft.Border.all(
                    2 if is_popular else 1,
                    theme_color if is_popular else ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE),
                ),
                shadow=ft.BoxShadow(
                    blur_radius=10,
                    color=ft.Colors.with_opacity(0.06 if is_popular else 0.03, ft.Colors.BLACK),
                    offset=ft.Offset(0, 3),
                ),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(p_name, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                                ft.Row(controls=badge_row, tight=True),
                            ],
                        ),
                        ft.Text(p_desc, size=11, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Row([
                            ft.Text(
                                _format_price(p_price, p_name),
                                size=17,
                                weight=ft.FontWeight.W_800,
                                color=theme_color if is_popular else ft.Colors.ON_SURFACE,
                            ),
                        ]),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                        ft.Row(
                            spacing=12,
                            controls=[
                                ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.GROUPS_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ft.Text(f"{max_m or '∞'} Seats", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                                    ],
                                ),
                                ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ft.Text(f"{max_c or '∞'} Courses", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                                    ],
                                ),
                            ],
                        ),
                        ft.Column(spacing=6, controls=feature_widgets) if feature_widgets else ft.Container(),
                        ft.Container(height=4),
                        ft.Row([ft.Container(expand=True, content=action_button)]),
                    ],
                ),
            )
            cards.append(card)

        banner_ctrls = []
        sub_status = org_data.get("subscription_status")
        days_rem = org_data.get("days_remaining", 0)
        if sub_status == "grace_period":
            banner_ctrls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.AMBER_600)),
                    content=ft.Row([
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER_700, size=18),
                        ft.Text(
                            f"Academy plan expired. Grace period active ({days_rem} days remaining before features pause).",
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.AMBER_900,
                            expand=True,
                        ),
                    ], spacing=8),
                )
            )
        elif sub_status == "expired":
            banner_ctrls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED_600),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.RED_600)),
                    content=ft.Row([
                        ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_600, size=18),
                        ft.Text(
                            "Your subscription has expired. Advanced features are paused. Existing data is safe.",
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.RED_700,
                            expand=True,
                        ),
                    ], spacing=8),
                )
            )

        plans_container.controls = banner_ctrls + [
            ft.ResponsiveRow(controls=cards, run_spacing=12, spacing=12),
        ]
        modal_content.content = plans_container
        page.update()

    async def _fetch_and_show():
        auth_tok = token or await page.shared_preferences.get("auth_token")
        try:
            remote_plans = await get_org_plans(auth_tok)
        except Exception:
            remote_plans = []
        _render_plans(remote_plans)

    def _close_dialog(e=None):
        upgrade_dialog.open = False
        page.update()

    w_val = getattr(page, "width", None)
    screen_w = int(w_val) if isinstance(w_val, (int, float)) and w_val > 0 else 800
    dialog_w = min(screen_w - 32, 840)

    upgrade_dialog = ft.AlertDialog(
        modal=True,
        bgcolor=ft.Colors.SURFACE,
        shape=ft.RoundedRectangleBorder(radius=18),
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row([
                    ft.Container(
                        padding=6,
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_600),
                        content=ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=ft.Colors.PURPLE_600, size=20),
                    ),
                    ft.Text("Upgrade Workspace Capacity", weight=ft.FontWeight.BOLD, size=16),
                ], spacing=10),
                ft.Row([
                    ft.TextButton(
                        "Billing History",
                        icon=ft.Icons.RECEIPT_LONG_ROUNDED,
                        style=ft.ButtonStyle(
                            color=theme_color,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        ),
                        on_click=lambda _: open_org_billing_history_modal(page, org_id, theme_color, token),
                    ),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=20, on_click=_close_dialog),
                ], spacing=4),
            ],
        ),
        content=ft.Container(
            width=dialog_w,
            content=ft.Column([
                modal_content,
            ], tight=True, scroll=ft.ScrollMode.AUTO),
        ),
    )

    page.overlay.append(upgrade_dialog)
    upgrade_dialog.open = True
    page.update()
    page.run_task(_fetch_and_show)
