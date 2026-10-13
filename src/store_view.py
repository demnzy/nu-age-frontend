import asyncio
import flet as ft
from typing import Optional, Dict, Any, List

from src.requests.payments import get_store_catalog, initialize_payment, verify_payment, DEFAULT_STORE_CATALOG
from src.utils.file_opener import show_page_snackbar


async def store_view(page: ft.Page, initial_tab: str = "plans") -> ft.View:
    """
    Universal In-App Storefront View for Nu-Age.
    Allows students, educators, and organizations to:
    1. Upgrade Personal Learning Plans (Free -> Pro -> Unlimited)
    2. Purchase Non-Expiring AI Generation & Material Upload Booster Packs
    3. Purchase Organisation Member Seats and Team Tools
    """
    token = ""
    if hasattr(page, "shared_preferences") and page.shared_preferences:
        try:
            token = await page.shared_preferences.get("auth_token") or ""
        except Exception:
            token = ""

    user_data = {}
    if hasattr(page, "session") and hasattr(page.session, "store"):
        user_data = page.session.store.get("current_user") or {}

    is_mobile = bool(page.width and page.width < 768)
    is_small = bool(page.width and page.width < 450)

    # ── STATE ────────────────────────────────────────────────────────────────
    state = {
        "catalog": DEFAULT_STORE_CATALOG,
        "selected_tab": initial_tab,  # "plans", "boosters", "org"
        "is_loading": False,
        "is_checking_out": False,
        "active_reference": None,
        "poll_task": None,
    }

    # ── HEADER & NAVIGATION ──────────────────────────────────────────────────
    app_bar = ft.AppBar(
        title=ft.Row(
            spacing=8,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.STOREFRONT_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                ft.Text("Nu-Age Store", size=18, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
            ],
        ),
        center_title=False,
        bgcolor=ft.Colors.SURFACE,
        elevation=0,
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.ON_SURFACE,
            tooltip="Back",
            on_click=lambda _: page.go("/self-study" if "/self-study" in page.route else "/dashboard"),
        ),
        actions=[
            ft.IconButton(
                icon=ft.Icons.REFRESH_ROUNDED,
                tooltip="Refresh Catalog",
                on_click=lambda _: page.run_task(_fetch_catalog),
            ),
            ft.Container(width=8),
        ],
    )

    content_area = ft.Column(spacing=20, expand=True, scroll=ft.ScrollMode.AUTO)

    # ── CHECKOUT MODAL & WEB LAUNCHER ────────────────────────────────────────
    async def _handle_checkout(item: dict, item_type: str):
        """
        Triggers the Paystack checkout flow.
        1. Calls backend /payments/initialize
        2. Launches checkout in external browser via page.launch_url
        3. Opens an in-app verification dialog with automatic status poller
        """
        if state["is_checking_out"]:
            return

        price = float(item.get("price", 0))
        if price <= 0:
            show_page_snackbar(page, "This plan is already active or free.")
            return

        state["is_checking_out"] = True
        progress_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=ft.Colors.SURFACE,
            content=ft.Container(
                width=320,
                padding=ft.Padding.all(16),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.ProgressRing(width=32, height=32, stroke_width=3, color=ft.Colors.PRIMARY),
                        ft.Text("Preparing secure checkout…", size=13, weight=ft.FontWeight.W_700),
                        ft.Text("Connecting to Paystack", size=11, color=ft.Colors.GREY_500),
                    ],
                ),
            ),
        )
        page.overlay.append(progress_dlg)
        progress_dlg.open = True
        page.update()

        # Determine purpose and metadata
        if item_type == "plan":
            purpose = "plan_upgrade"
            meta = {"plan_id": item["id"], "plan_name": item["name"]}
        elif item_type == "booster":
            purpose = "study_credits"
            meta = {
                "pack_id": item["id"],
                "extra_materials": item.get("materials", 10),
                "extra_generations": item.get("generations", 25),
            }
        else:
            purpose = "org_seats"
            meta = {"product_id": item["id"], "extra_seats": 1}

        res = await initialize_payment(
            token=token,
            amount=price,
            purpose=purpose,
            metadata=meta,
        )

        progress_dlg.open = False
        page.update()
        state["is_checking_out"] = False

        if "error" in res or not res.get("authorization_url"):
            err_msg = res.get("error") or "Failed to initiate payment."
            show_page_snackbar(page, f"Checkout Error: {err_msg}")
            return

        auth_url = res["authorization_url"]
        reference = res["reference"]
        state["active_reference"] = reference

        # 1. Launch in user's browser for Paystack payment processing
        try:
            await page.launch_url(auth_url)
        except Exception as ex:
            print(f"[STORE] Failed to launch external url: {ex}")

        # 2. Open Verification Waiting Sheet
        _open_verification_sheet(reference, item["name"], price)

    def _open_verification_sheet(reference: str, item_name: str, price: float):
        polling_active = True

        status_text = ft.Text("Waiting for payment completion in your browser…", size=12, color=ft.Colors.GREY_600, text_align=ft.TextAlign.CENTER)
        status_spinner = ft.ProgressRing(width=20, height=20, stroke_width=2.5, color=ft.Colors.PRIMARY)

        async def _check_now(e=None):
            status_text.value = "Checking payment status with Paystack…"
            v_dlg.update()
            v_res = await verify_payment(token, reference)
            if v_res.get("status") == "success":
                _on_payment_success()
            elif v_res.get("status") in ("failed", "abandoned"):
                status_text.value = f"Transaction marked as {v_res.get('status')}. You may retry."
                status_spinner.visible = False
                v_dlg.update()
            else:
                status_text.value = "Payment is still processing. Please finish in browser or retry in a moment."
                v_dlg.update()

        def _on_payment_success():
            nonlocal polling_active
            polling_active = False
            v_dlg.open = False
            page.update()
            _show_success_dialog(item_name)

        async def _poll_verification():
            strikes = 0
            while polling_active and strikes < 40:  # Poll for up to 3 minutes
                await asyncio.sleep(5)
                if not polling_active:
                    break
                v_res = await verify_payment(token, reference)
                if v_res.get("status") == "success":
                    _on_payment_success()
                    break
                strikes += 1

        def _close_sheet(e):
            nonlocal polling_active
            polling_active = False
            v_dlg.open = False
            page.update()

        v_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=20),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.PAYMENTS_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                            ft.Text("Payment in Progress", size=15, weight=ft.FontWeight.W_800),
                        ],
                    ),
                    ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=_close_sheet),
                ],
            ),
            content=ft.Container(
                width=340,
                padding=ft.Padding.symmetric(vertical=10),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.all(14),
                            border_radius=ft.BorderRadius.all(12),
                            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY)),
                            content=ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=4,
                                controls=[
                                    ft.Text(item_name, size=13, weight=ft.FontWeight.W_700),
                                    ft.Text(f"Total: ₦{price:,.0f}", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                                ],
                            ),
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=10,
                            controls=[status_spinner, status_text],
                        ),
                        ft.Text(
                            "Complete payment using your card, bank transfer, or USSD in the opened browser tab.",
                            size=10.5,
                            color=ft.Colors.GREY_500,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.ElevatedButton(
                            content=ft.Row(
                                tight=True,
                                spacing=6,
                                alignment=ft.MainAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=15, color=ft.Colors.WHITE),
                                    ft.Text("I Have Completed Payment", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                ],
                            ),
                            bgcolor=ft.Colors.PRIMARY,
                            height=38,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                            on_click=lambda e: page.run_task(_check_now, e),
                        ),
                    ],
                ),
            ),
        )

        page.overlay.append(v_dlg)
        v_dlg.open = True
        page.update()
        page.run_task(_poll_verification)

    def _show_success_dialog(item_name: str):
        success_dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=20),
            bgcolor=ft.Colors.SURFACE,
            content=ft.Container(
                width=340,
                padding=ft.Padding.all(16),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.Container(
                            width=56,
                            height=56,
                            border_radius=ft.BorderRadius.all(28),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600, size=32),
                        ),
                        ft.Text("Payment Verified!", size=17, weight=ft.FontWeight.W_900, color=ft.Colors.ON_SURFACE),
                        ft.Text(
                            f"Your purchase of '{item_name}' has been activated. Quotas and benefits have been credited to your account!",
                            size=12,
                            color=ft.Colors.GREY_600,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.ElevatedButton(
                            content=ft.Row(
                                tight=True,
                                spacing=8,
                                alignment=ft.MainAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16, color=ft.Colors.WHITE),
                                    ft.Text("Return to Self-Study Hub", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                ],
                            ),
                            bgcolor=ft.Colors.PRIMARY,
                            height=42,
                            width=float("inf"),
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                            on_click=lambda _: (setattr(success_dlg, "open", False), page.update(), page.go("/self-study")),
                        ),
                    ],
                ),
            ),
        )
        page.overlay.append(success_dlg)
        success_dlg.open = True
        page.update()

    # ── TAB SWITCHER ─────────────────────────────────────────────────────────
    def _tab_button(label: str, tab_id: str, icon):
        is_active = state["selected_tab"] == tab_id
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border_radius=ft.BorderRadius.all(10),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_active else ft.Colors.TRANSPARENT,
            ink=True,
            on_click=lambda _: _switch_tab(tab_id),
            content=ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(icon, size=16, color=ft.Colors.PRIMARY if is_active else ft.Colors.GREY_500),
                    ft.Text(
                        label,
                        size=12,
                        weight=ft.FontWeight.W_800 if is_active else ft.FontWeight.W_600,
                        color=ft.Colors.PRIMARY if is_active else ft.Colors.GREY_600,
                    ),
                ],
            ),
        )

    def _switch_tab(tab_id: str):
        state["selected_tab"] = tab_id
        _render_view()

    # ── RENDER CARD GENERATORS ───────────────────────────────────────────────
    def _render_plan_card(plan: dict):
        is_free = plan.get("id") == "free"
        is_rec = plan.get("recommended", False)
        price_val = plan.get("price", 0)
        price_str = "Free" if is_free else f"₦{price_val:,.0f}"

        badge_container = ft.Container()
        if plan.get("badge"):
            badge_color = ft.Colors.PRIMARY if is_rec else ft.Colors.GREY_500
            badge_container = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=ft.Colors.with_opacity(0.12, badge_color),
                content=ft.Text(plan["badge"], size=9, weight=ft.FontWeight.W_900, color=badge_color),
            )

        features_col = ft.Column(spacing=6)
        for feat in plan.get("features", []):
            features_col.controls.append(
                ft.Row(
                    spacing=8,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                        ft.Text(feat, size=11.5, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                    ],
                )
            )

        btn_content = "Current Tier" if is_free else "Coming Soon"
        action_btn = ft.ElevatedButton(
            content=ft.Row(
                tight=True,
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.HOURGLASS_EMPTY_ROUNDED if not is_free else ft.Icons.CHECK_ROUNDED, size=14, color=ft.Colors.WHITE),
                    ft.Text(btn_content, size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                ],
            ),
            bgcolor=ft.Colors.GREY_600,
            disabled=True,
            height=40,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
            tooltip="Subscription plans are coming soon! Enjoying beta access.",
        )

        return ft.Container(
            col={"xs": 12, "sm": 6, "md": 4},
            border_radius=ft.BorderRadius.all(18),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1.5 if is_rec else 1, ft.Colors.PRIMARY if is_rec else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(18),
            shadow=ft.BoxShadow(
                blur_radius=10,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[badge_container]),
                    ft.Column(
                        spacing=3,
                        controls=[
                            ft.Text(plan["name"], size=16, weight=ft.FontWeight.W_800),
                            ft.Text(plan.get("description", ""), size=11, color=ft.Colors.GREY_500),
                        ],
                    ),
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        spacing=4,
                        controls=[
                            ft.Text(price_str, size=24, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                            ft.Text(f"/{plan.get('interval', 'mo')}" if not is_free else "", size=12, color=ft.Colors.GREY_500),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    features_col,
                    ft.Container(height=6),
                    action_btn,
                ],
            ),
        )

    def _render_booster_card(pack: dict):
        price_str = f"₦{pack.get('price', 0):,.0f}"

        badge_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_600),
            content=ft.Text(pack.get("badge", "BOOSTER"), size=9, weight=ft.FontWeight.W_900, color=ft.Colors.PURPLE_600),
        )

        features_col = ft.Column(spacing=6)
        for feat in pack.get("features", []):
            features_col.controls.append(
                ft.Row(
                    spacing=8,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.BOLT_ROUNDED, size=15, color=ft.Colors.PURPLE_600),
                        ft.Text(feat, size=11.5, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                    ],
                )
            )

        return ft.Container(
            col={"xs": 12, "sm": 6, "md": 4},
            border_radius=ft.BorderRadius.all(18),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(18),
            shadow=ft.BoxShadow(
                blur_radius=10,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[badge_container]),
                    ft.Column(
                        spacing=3,
                        controls=[
                            ft.Text(pack["name"], size=16, weight=ft.FontWeight.W_800),
                            ft.Text(pack.get("description", ""), size=11, color=ft.Colors.GREY_500),
                        ],
                    ),
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        spacing=4,
                        controls=[
                            ft.Text(price_str, size=24, weight=ft.FontWeight.W_900, color=ft.Colors.PURPLE_600),
                            ft.Text("one-time", size=11.5, color=ft.Colors.GREY_500),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    features_col,
                    ft.Container(height=6),
                    ft.ElevatedButton(
                        content=ft.Row(
                            tight=True,
                            spacing=6,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.HOURGLASS_EMPTY_ROUNDED, size=14, color=ft.Colors.WHITE),
                                ft.Text("Coming Soon", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                            ],
                        ),
                        bgcolor=ft.Colors.GREY_600,
                        disabled=True,
                        height=40,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                        tooltip="Packs are coming soon! Enjoying beta access.",
                    ),
                ],
            ),
        )

    def _render_org_card(prod: dict):
        price_str = f"₦{prod.get('price', 0):,.0f}"

        features_col = ft.Column(spacing=6)
        for feat in prod.get("features", []):
            features_col.controls.append(
                ft.Row(
                    spacing=8,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.CORPORATE_FARE_ROUNDED, size=15, color=ft.Colors.TEAL_600),
                        ft.Text(feat, size=11.5, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                    ],
                )
            )

        return ft.Container(
            col={"xs": 12, "sm": 6, "md": 6},
            border_radius=ft.BorderRadius.all(18),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(18),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Text(prod["name"], size=16, weight=ft.FontWeight.W_800),
                    ft.Text(prod.get("description", ""), size=11, color=ft.Colors.GREY_500),
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        spacing=4,
                        controls=[
                            ft.Text(price_str, size=24, weight=ft.FontWeight.W_900, color=ft.Colors.TEAL_600),
                            ft.Text(f"/{prod.get('interval', 'mo')}", size=11.5, color=ft.Colors.GREY_500),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    features_col,
                    ft.Container(height=6),
                    ft.ElevatedButton(
                        content=ft.Row(
                            tight=True,
                            spacing=6,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.HOURGLASS_EMPTY_ROUNDED, size=14, color=ft.Colors.WHITE),
                                ft.Text("Coming Soon", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                            ],
                        ),
                        bgcolor=ft.Colors.GREY_600,
                        disabled=True,
                        height=40,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                        tooltip="Institutional seats are coming soon! Enjoying beta access.",
                    ),
                ],
            ),
        )

    # ── VIEW COMPILER ────────────────────────────────────────────────────────
    def _render_view():
        content_area.controls.clear()

        # Banner Header
        hero_banner = ft.Container(
            padding=ft.Padding.symmetric(horizontal=18, vertical=20),
            border_radius=ft.BorderRadius.all(18),
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
                    ft.Colors.with_opacity(0.04, ft.Colors.PURPLE_600),
                ],
            ),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY)),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        spacing=4,
                        expand=True,
                        controls=[
                            ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.SECURITY_ROUNDED, size=14, color=ft.Colors.GREEN_700),
                                    ft.Text("Secure Nigerian Payments via Paystack", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.GREEN_800),
                                ],
                            ),
                            ft.Text("Supercharge Your Learning Studio", size=18 if not is_small else 16, weight=ft.FontWeight.W_900),
                            ft.Text("Upgrade subscriptions or top-up consumable packs with debit card, bank transfer, or USSD.", size=11.5, color=ft.Colors.GREY_600),
                        ],
                    ),
                ],
            ),
        )
        content_area.controls.append(hero_banner)

        # Segmented Tab Row
        tab_row = ft.Container(
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            padding=4,
            content=ft.Row(
                spacing=4,
                controls=[
                    _tab_button("Monthly Plans", "plans", ft.Icons.STARS_ROUNDED),
                    _tab_button("Study Boosters", "boosters", ft.Icons.BOLT_ROUNDED),
                    _tab_button("Organisation Seats", "org", ft.Icons.CORPORATE_FARE_ROUNDED),
                ],
            ),
        )
        content_area.controls.append(tab_row)

        catalog = state.get("catalog", {})
        cur_tab = state.get("selected_tab", "plans")

        if cur_tab == "plans":
            plans = catalog.get("plans", [])
            grid = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[_render_plan_card(p) for p in plans])
            content_area.controls.append(grid)
        elif cur_tab == "boosters":
            packs = catalog.get("packs", [])
            grid = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[_render_booster_card(b) for b in packs])
            content_area.controls.append(grid)
        elif cur_tab == "org":
            org_items = catalog.get("org_products", [])
            grid = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[_render_org_card(o) for o in org_items])
            content_area.controls.append(grid)

        content_area.controls.append(ft.Container(height=36))
        if page:
            try:
                page.update()
            except Exception:
                pass

    async def _fetch_catalog():
        cat = await get_store_catalog()
        state["catalog"] = cat or DEFAULT_STORE_CATALOG
        state["is_loading"] = False
        _render_view()

    # Pre-render initial controls with catalog data, then sync in background
    _render_view()
    page.run_task(_fetch_catalog)

    return ft.View(
        route="/store",
        appbar=app_bar,
        controls=[
            ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=14 if is_small else 24, vertical=16),
                content=content_area,
            ),
        ],
    )
