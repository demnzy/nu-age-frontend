import asyncio
import flet as ft
from typing import Optional, Dict, Any, List

from src.requests.payments import (
    get_store_catalog,
    initialize_payment,
    verify_payment,
    get_payment_history,
    exchange_coins_api,
)
from src.requests.subscription import get_subscription_status
from src.utils.file_opener import show_page_snackbar, safe_set_clipboard
from src.components.nu_coin_icon import nu_coin_icon


async def store_view(page: ft.Page, initial_tab: str = "plans", back_target: str = "/dashboard") -> ft.View:
    """
    Universal In-App Storefront View for Nu-Age.
    Allows learners, scholars, and institutions to:
    1. Upgrade Learning Plans (Free -> Pro -> Unlimited) with live Paystack integration
    2. Purchase Non-Expiring AI Generation & Material Upload Booster Packs
    3. Purchase Organisation Member Seats and Pro Tools
    """
    token = ""
    if hasattr(page, "shared_preferences") and page.shared_preferences:
        try:
            token = await page.shared_preferences.get("auth_token") or ""
        except Exception:
            token = ""

    from src.utils.session_utils import get_session_user
    user_data = get_session_user(page)

    is_mobile = bool(page.width and page.width < 768)
    is_small = bool(page.width and page.width < 450)

    mapped_tab = "plans"
    if str(initial_tab or "").lower() in ("boosters", "coins"):
        mapped_tab = "boosters"
    elif str(initial_tab or "").lower() in ("exchange", "swap", "credits", "nu-coins", "nu_coins"):
        mapped_tab = "exchange"
    elif str(initial_tab or "").lower() in ("history", "receipts"):
        mapped_tab = "history"

    # ── STATE ────────────────────────────────────────────────────────────────
    state = {
        "catalog": None,
        "selected_tab": mapped_tab,  # "plans", "boosters", "exchange", "history"
        "is_loading": True,
        "is_checking_out": False,
        "is_exchanging": False,
        "active_reference": None,
        "user_sub": None,
        "history": [],
        "is_loading_history": False,
    }

    # Determine back navigation destination
    def _handle_back(_):
        if back_target and back_target != page.route:
            page.go(back_target)
        elif "/profile" in (page.route or ""):
            page.go("/profile")
        elif "/self-study" in (page.route or ""):
            page.go("/self-study")
        else:
            page.go("/dashboard")

    # ── APP BAR ──────────────────────────────────────────────────────────────
    app_bar = ft.AppBar(
        title=ft.Row(
            spacing=8,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=32,
                    height=32,
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.STOREFRONT_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                ),
                ft.Text("Nu Age Store", size=17, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
            ],
        ),
        center_title=False,
        bgcolor=ft.Colors.SURFACE,
        elevation=0,
        elevation_on_scroll=0.0,
        shadow_color=ft.Colors.TRANSPARENT,
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.ON_SURFACE,
            tooltip="Back",
            on_click=_handle_back,
        ),
        actions=[
            ft.IconButton(
                icon=ft.Icons.REFRESH_ROUNDED,
                icon_color=ft.Colors.ON_SURFACE,
                tooltip="Refresh Catalog",
                on_click=lambda _: page.run_task(_fetch_catalog_and_sub, True),
            ),
            ft.Container(width=8),
        ],
    )

    content_area = ft.Column(
        spacing=20,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # ── CHECKOUT FLOW & VERIFICATION ─────────────────────────────────────────
    async def _handle_checkout(item: dict, item_type: str, trigger_btn: ft.Control = None):
        """
        Initiates the secure Paystack checkout flow.
        1. Calls backend /payments/initialize
        2. Launches authorization in user's browser via page.launch_url
        3. Opens an in-app verification dialog with automatic status polling
        """
        if state["is_checking_out"]:
            return

        price = float(item.get("price", 0))
        if price <= 0:
            show_page_snackbar(page, "This plan is already active or free.")
            return

        state["is_checking_out"] = True
        if trigger_btn and hasattr(trigger_btn, "disabled"):
            trigger_btn.disabled = True
            trigger_btn.update()

        progress_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=ft.Colors.SURFACE,
            content=ft.Container(
                width=320,
                padding=ft.Padding.all(18),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.ProgressRing(width=34, height=34, stroke_width=3, color=ft.Colors.PRIMARY),
                        ft.Text("Preparing Secure Checkout…", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                        ft.Text("Connecting to Paystack gateway", size=11.5, color=ft.Colors.GREY_500),
                    ],
                ),
            ),
        )
        page.overlay.append(progress_dlg)
        progress_dlg.open = True
        page.update()

        # Build payload based on item type
        if item_type == "plan":
            purpose = "plan_upgrade"
            meta = {
                "product_id": item.get("id"),
                "plan_id": item.get("plan_id") or item["id"],
                "plan_name": item["name"],
                "bonus_materials": item.get("bonus_materials", 0),
                "bonus_generations": item.get("bonus_generations", 0),
                "bonus_coins": item.get("bonus_coins", 0),
            }
        elif item_type == "booster":
            purpose = "study_credits"
            meta = {
                "product_id": item.get("id"),
                "pack_id": item["id"],
                "extra_materials": item.get("bonus_materials") or item.get("materials", 10),
                "extra_generations": item.get("bonus_generations") or item.get("generations", 25),
                "bonus_materials": item.get("bonus_materials") or item.get("materials", 10),
                "bonus_generations": item.get("bonus_generations") or item.get("generations", 25),
                "bonus_coins": item.get("bonus_coins", 0),
            }
        elif item_type == "coins":
            purpose = "study_credits"
            meta = {
                "product_id": item.get("id"),
                "pack_id": item["id"],
                "extra_coins": item.get("bonus_coins") or item.get("coins", 0),
                "bonus_coins": item.get("bonus_coins") or item.get("coins", 0),
            }
        else:
            purpose = "org_seats"
            meta = {"product_id": item["id"], "extra_seats": item.get("org_seats", 1)}

        res = await initialize_payment(
            token=token,
            amount=price,
            purpose=purpose,
            metadata=meta,
        )

        progress_dlg.open = False
        page.update()
        state["is_checking_out"] = False
        if trigger_btn and hasattr(trigger_btn, "disabled"):
            trigger_btn.disabled = False
            trigger_btn.update()

        if "error" in res or not res.get("authorization_url"):
            err_msg = res.get("error") or "Failed to initiate payment."
            show_page_snackbar(page, f"Checkout Error: {err_msg}")
            return

        auth_url = res["authorization_url"]
        reference = res["reference"]
        state["active_reference"] = reference

        # 1. Launch external browser for payment processing
        try:
            await page.launch_url(auth_url)
        except Exception as ex:
            print(f"[STORE] Failed to launch checkout URL: {ex}")

        # 2. Open Verification Waiting Sheet
        _open_verification_sheet(reference, item["name"], price)

    def _open_verification_sheet(reference: str, item_name: str, price: float):
        polling_active = True

        status_text = ft.Text(
            "Waiting for payment completion in your browser…",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            text_align=ft.TextAlign.CENTER,
            expand=True,
        )
        status_spinner = ft.ProgressRing(width=22, height=22, stroke_width=2.5, color=ft.Colors.PRIMARY)
        check_button = ft.ElevatedButton(
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
            height=40,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
            on_click=lambda e: page.run_task(_check_now, e),
        )

        async def _check_now(e=None):
            status_text.value = "Verifying transaction with Paystack…"
            status_spinner.visible = True
            check_button.disabled = True
            v_dlg.update()

            v_res = await verify_payment(token, reference)
            if v_res.get("status") == "success":
                _on_payment_success()
            elif v_res.get("status") in ("failed", "abandoned"):
                status_text.value = f"Transaction marked as {v_res.get('status')}. You may retry."
                status_spinner.visible = False
                check_button.disabled = False
                v_dlg.update()
            else:
                status_text.value = "Payment is still processing. Please finish in your browser or retry in a moment."
                check_button.disabled = False
                v_dlg.update()

        def _on_payment_success():
            nonlocal polling_active
            polling_active = False
            v_dlg.open = False
            page.update()
            # Refresh subscription status in background
            page.run_task(_fetch_catalog_and_sub)
            _show_success_dialog(item_name)

        async def _poll_verification():
            strikes = 0
            while polling_active and strikes < 30:  # Poll every 4s for up to 2 minutes
                await asyncio.sleep(4)
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
                                    ft.Text(f"Total: ₦{price:,.0f}", size=16, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                                    ft.Text(f"Ref: {reference[:16]}…", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                            ),
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                            controls=[status_spinner, status_text],
                        ),
                        ft.Text(
                            "Complete payment using your debit card, bank transfer, or USSD in the opened browser tab.",
                            size=10.5,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        check_button,
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
                            f"Your purchase of '{item_name}' has been activated! Your study benefits and quotas are now ready.",
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
                                    ft.Text("Continue Studying", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                ],
                            ),
                            bgcolor=ft.Colors.PRIMARY,
                            height=42,
                            width=float("inf"),
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                            on_click=lambda _: (setattr(success_dlg, "open", False), page.update(), _handle_back(None)),
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
            padding=ft.Padding.symmetric(horizontal=14, vertical=9),
            border_radius=ft.BorderRadius.all(10),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_active else ft.Colors.TRANSPARENT,
            ink=True,
            on_click=lambda _: _switch_tab(tab_id),
            content=ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(icon, size=16, color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(
                        label,
                        size=12,
                        weight=ft.FontWeight.W_800 if is_active else ft.FontWeight.W_600,
                        color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
            ),
        )

    def _switch_tab(tab_id: str):
        state["selected_tab"] = tab_id
        if tab_id == "history" and not state["history"]:
            page.run_task(_fetch_payment_history)
        _render_view()

    # ── RENDER CARD GENERATORS ───────────────────────────────────────────────
    def _render_plan_card(plan: dict):
        current_sub = state.get("user_sub") or {}
        user_plan_id = (current_sub.get("subscribed_plan_id") or current_sub.get("plan_id") or "free").lower()
        is_current = user_plan_id == plan.get("id", "").lower()
        is_free = plan.get("id") == "free"
        is_rec = plan.get("recommended", False)
        price_val = plan.get("price", 0)
        price_str = "Free" if is_free else f"₦{price_val:,.0f}"

        sub_status = (current_sub.get("status") or "active").lower() if is_current else "active"
        days_left = current_sub.get("days_remaining") if is_current else None

        badge_container = ft.Container()
        if is_current:
            if is_free:
                badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)
                badge_fg = ft.Colors.PRIMARY
                badge_lbl = "CURRENT PLAN"
                badge_ico = ft.Icons.CHECK_CIRCLE_ROUNDED
            elif sub_status == "expired":
                badge_bg = ft.Colors.with_opacity(0.14, ft.Colors.RED_600)
                badge_fg = ft.Colors.RED_600
                badge_lbl = "PLAN EXPIRED"
                badge_ico = ft.Icons.LOCK_CLOCK_ROUNDED
            elif sub_status == "grace_period":
                badge_bg = ft.Colors.with_opacity(0.14, ft.Colors.AMBER_700)
                badge_fg = ft.Colors.AMBER_800
                badge_lbl = "GRACE PERIOD (3D)"
                badge_ico = ft.Icons.WARNING_AMBER_ROUNDED
            elif days_left is not None and days_left <= 7:
                badge_bg = ft.Colors.with_opacity(0.14, ft.Colors.AMBER_700)
                badge_fg = ft.Colors.AMBER_800
                badge_lbl = f"RENEWS IN {days_left}D"
                badge_ico = ft.Icons.SCHEDULE_ROUNDED
            else:
                badge_bg = ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY)
                badge_fg = ft.Colors.PRIMARY
                badge_lbl = "CURRENT PLAN"
                badge_ico = ft.Icons.CHECK_CIRCLE_ROUNDED

            badge_container = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=badge_bg,
                border=ft.Border.all(1, badge_fg),
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(badge_ico, size=11, color=badge_fg),
                        ft.Text(badge_lbl, size=9, weight=ft.FontWeight.W_900, color=badge_fg),
                    ],
                ),
            )
        elif plan.get("badge") or is_rec:
            b_text = plan.get("badge") or ("MOST POPULAR" if is_rec else "PLAN")
            badge_color = ft.Colors.PRIMARY if is_rec else ft.Colors.PURPLE_600
            badge_container = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=ft.Colors.with_opacity(0.12, badge_color),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, badge_color)),
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED if is_rec else ft.Icons.STAR_ROUNDED, size=10, color=badge_color),
                        ft.Text(str(b_text).upper(), size=9, weight=ft.FontWeight.W_900, color=badge_color),
                    ],
                ),
            )

        features_col = ft.Column(spacing=7)
        for feat in plan.get("features", []):
            features_col.controls.append(
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                        ft.Text(feat, size=11.5, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE, expand=True),
                    ],
                )
            )

        # Action CTA Button
        if is_current:
            if is_free:
                action_btn = ft.ElevatedButton(
                    content=ft.Row(
                        tight=True,
                        spacing=6,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                            ft.Text("Active Free Plan", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                        ],
                    ),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                    disabled=True,
                    height=40,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                )
            elif sub_status == "expired":
                action_btn = ft.ElevatedButton(
                    content=ft.Row(
                        tight=True,
                        spacing=6,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.AUTORENEW_ROUNDED, size=15, color=ft.Colors.WHITE),
                            ft.Text(f"Renew Subscription • {price_str}", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                        ],
                    ),
                    bgcolor=ft.Colors.RED_600,
                    height=40,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                    on_click=lambda e: page.run_task(_handle_checkout, plan, "plan", action_btn),
                )
            elif sub_status == "grace_period":
                action_btn = ft.ElevatedButton(
                    content=ft.Row(
                        tight=True,
                        spacing=6,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.AUTORENEW_ROUNDED, size=15, color=ft.Colors.WHITE),
                            ft.Text(f"Renew Now • {price_str}", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                        ],
                    ),
                    bgcolor=ft.Colors.AMBER_700,
                    height=40,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                    on_click=lambda e: page.run_task(_handle_checkout, plan, "plan", action_btn),
                )
            elif days_left is not None and days_left <= 7:
                action_btn = ft.ElevatedButton(
                    content=ft.Row(
                        tight=True,
                        spacing=6,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.AUTORENEW_ROUNDED, size=15, color=ft.Colors.WHITE),
                            ft.Text(f"Renew / Extend • {price_str}", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                        ],
                    ),
                    bgcolor=ft.Colors.PRIMARY,
                    height=40,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                    on_click=lambda e: page.run_task(_handle_checkout, plan, "plan", action_btn),
                )
            else:
                action_btn = ft.ElevatedButton(
                    content=ft.Row(
                        tight=True,
                        spacing=6,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                            ft.Text(f"Active Plan ({days_left}d left)" if days_left is not None else "Active Plan", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                        ],
                    ),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                    disabled=True,
                    height=40,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                )
        else:
            action_label = f"Upgrade to {plan['name']}" if price_val > 0 else "Select Plan"
            action_btn = ft.ElevatedButton(
                content=ft.Row(
                    tight=True,
                    spacing=6,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=14, color=ft.Colors.WHITE),
                        ft.Text(action_label, size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                    ],
                ),
                bgcolor=ft.Colors.PRIMARY,
                height=40,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                on_click=lambda e: page.run_task(_handle_checkout, plan, "plan", action_btn),
            )

        return ft.Container(
            col={"xs": 12, "sm": 6, "md": 4},
            border_radius=ft.BorderRadius.all(18),
            bgcolor=ft.Colors.SURFACE,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY),
                    ft.Colors.SURFACE,
                ],
            ) if is_rec else None,
            border=ft.Border.all(
                1.8 if (is_rec or is_current) else 1,
                ft.Colors.PRIMARY if (is_rec or is_current) else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)
            ),
            padding=ft.Padding.all(18),
            shadow=ft.BoxShadow(
                blur_radius=14 if is_rec else 8,
                color=ft.Colors.with_opacity(0.08 if is_rec else 0.03, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[badge_container]),
                    ft.Column(
                        spacing=3,
                        controls=[
                            ft.Text(plan["name"], size=16, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                            ft.Text(plan.get("description", ""), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        spacing=4,
                        controls=[
                            ft.Text(price_str, size=24, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                            ft.Text(f"/{plan.get('interval', 'mo')}" if not is_free else "", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
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
        price_val = pack.get("price", 0)
        price_str = f"₦{price_val:,.0f}"

        badge_text = pack.get("badge") or ("POPULAR VALUE" if price_val >= 2500 else "BOOSTER")
        badge_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_600),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.PURPLE_600)),
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.BOLT_ROUNDED, size=11, color=ft.Colors.PURPLE_600),
                    ft.Text(str(badge_text).upper(), size=9, weight=ft.FontWeight.W_900, color=ft.Colors.PURPLE_600),
                ],
            ),
        )

        features_col = ft.Column(spacing=7)
        for feat in pack.get("features", []):
            features_col.controls.append(
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Icon(ft.Icons.BOLT_ROUNDED, size=15, color=ft.Colors.PURPLE_600),
                        ft.Text(feat, size=11.5, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE, expand=True),
                    ],
                )
            )

        action_btn = ft.ElevatedButton(
            content=ft.Row(
                tight=True,
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=14, color=ft.Colors.WHITE),
                    ft.Text(f"Get Pack • {price_str}", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                ],
            ),
            bgcolor=ft.Colors.PURPLE_700,
            height=40,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
            on_click=lambda e: page.run_task(_handle_checkout, pack, "booster", action_btn),
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
                            ft.Text(pack["name"], size=16, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                            ft.Text(pack.get("description", ""), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        spacing=4,
                        controls=[
                            ft.Text(price_str, size=24, weight=ft.FontWeight.W_900, color=ft.Colors.PURPLE_600),
                            ft.Text("one-time • permanent", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    features_col,
                    ft.Container(height=6),
                    action_btn,
                ],
            ),
        )

    def _render_org_card(prod: dict):
        price_val = prod.get("price", 0)
        price_str = f"₦{price_val:,.0f}"

        badge_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.TEAL_600),
            content=ft.Text(prod.get("badge", "INSTITUTION"), size=9, weight=ft.FontWeight.W_900, color=ft.Colors.TEAL_600),
        )

        features_col = ft.Column(spacing=7)
        for feat in prod.get("features", []):
            features_col.controls.append(
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Icon(ft.Icons.CORPORATE_FARE_ROUNDED, size=15, color=ft.Colors.TEAL_600),
                        ft.Text(feat, size=11.5, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE, expand=True),
                    ],
                )
            )

        action_btn = ft.ElevatedButton(
            content=ft.Row(
                tight=True,
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, size=14, color=ft.Colors.WHITE),
                    ft.Text(f"Add Seats • {price_str}", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                ],
            ),
            bgcolor=ft.Colors.TEAL_700,
            height=40,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
            on_click=lambda e: page.run_task(_handle_checkout, prod, "org", action_btn),
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
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[badge_container]),
                    ft.Column(
                        spacing=3,
                        controls=[
                            ft.Text(prod["name"], size=16, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                            ft.Text(prod.get("description", ""), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        spacing=4,
                        controls=[
                            ft.Text(price_str, size=24, weight=ft.FontWeight.W_900, color=ft.Colors.TEAL_600),
                            ft.Text(f"/{prod.get('interval', 'mo')}", size=11.5, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    features_col,
                    ft.Container(height=6),
                    action_btn,
                ],
            ),
        )
    def _render_coin_card(pack: dict):
        price_val = pack.get("price", 0)
        price_str = f"₦{price_val:,.0f}"
        coins_val = pack.get("coins") or pack.get("bonus_coins") or 0

        badge_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_700),
            content=ft.Text(pack.get("badge", "NU-COINS"), size=9, weight=ft.FontWeight.W_900, color=ft.Colors.AMBER_800),
        )

        features_col = ft.Column(spacing=7)
        for feat in pack.get("features", []):
            features_col.controls.append(
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        nu_coin_icon(size=15),
                        ft.Text(feat, size=11.5, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE, expand=True),
                    ],
                )
            )

        action_btn = ft.ElevatedButton(
            content=ft.Row(
                tight=True,
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    nu_coin_icon(size=15),
                    ft.Text(f"Get {coins_val} Coins • {price_str}", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                ],
            ),
            bgcolor=ft.Colors.AMBER_800,
            height=40,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
            on_click=lambda e: page.run_task(_handle_checkout, pack, "coins", action_btn),
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
                            ft.Text(pack["name"], size=16, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                            ft.Text(pack.get("description", ""), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        spacing=4,
                        controls=[
                            ft.Text(price_str, size=24, weight=ft.FontWeight.W_900, color=ft.Colors.AMBER_800),
                            ft.Text("Nu-Coins wallet", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    features_col,
                    ft.Container(height=6),
                    action_btn,
                ],
            ),
        )

    # ── EXPLICIT NU-COINS -> AI CREDITS EXCHANGE ─────────────────────────────
    EXCHANGE_TIERS = [
        {
            "id": "ai_gen_1",
            "generations": 1,
            "coins": 25,
            "label": "1 AI Generation",
            "badge": "STARTER",
            "badge_color": ft.Colors.BLUE_700,
            "discount": None,
            "description": "Generate 1 targeted study deck, custom mock exam, or course summary.",
        },
        {
            "id": "ai_gen_5",
            "generations": 5,
            "coins": 100,
            "label": "5 AI Generations",
            "badge": "POPULAR",
            "badge_color": ft.Colors.PRIMARY,
            "discount": "Save 25 Coins (20% Off)",
            "description": "5 full AI generations for course materials, flashcard decks, and quiz packs.",
        },
        {
            "id": "ai_gen_12",
            "generations": 12,
            "coins": 200,
            "label": "12 AI Generations",
            "badge": "SCHOLAR PACK",
            "badge_color": ft.Colors.PURPLE_700,
            "discount": "Save 100 Coins (33% Off)",
            "description": "12 bonus generations for comprehensive multi-chapter exam preparation.",
        },
        {
            "id": "ai_gen_25",
            "generations": 25,
            "coins": 400,
            "label": "25 AI Generations",
            "badge": "MAX VALUE",
            "badge_color": ft.Colors.AMBER_800,
            "discount": "Save 225 Coins (36% Off)",
            "description": "25 heavy-duty AI generations for end-to-end semester course creation.",
        },
    ]

    async def _handle_exchange(tier: dict, trigger_btn: ft.Control = None):
        if state.get("is_exchanging"):
            return

        u_data = page.session.store.get("current_user") or {} if hasattr(page, "session") and hasattr(page.session, "store") else {}
        user_coins = int(u_data.get("coins_balance") or 0)
        coins_required = tier["coins"]
        gen_awarded = tier["generations"]

        if user_coins < coins_required:
            show_page_snackbar(
                page,
                f"Insufficient Nu-Coins. You have {user_coins} coins, but this package requires {coins_required} Nu-Coins. Win duels or maintain study streaks to earn more!"
            )
            return

        state["is_exchanging"] = True
        if trigger_btn and hasattr(trigger_btn, "disabled"):
            trigger_btn.disabled = True
            trigger_btn.update()

        progress_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=ft.Colors.SURFACE,
            content=ft.Container(
                width=320,
                padding=ft.Padding.all(18),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.ProgressRing(width=34, height=34, stroke_width=3, color=ft.Colors.PRIMARY),
                        ft.Text("Exchanging Nu-Coins…", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                        ft.Text(f"Converting {coins_required} Nu-Coins to +{gen_awarded} AI Credits", size=11.5, color=ft.Colors.GREY_500),
                    ],
                ),
            ),
        )
        page.overlay.append(progress_dlg)
        progress_dlg.open = True
        page.update()

        try:
            res = await exchange_coins_api(token, tier["id"])
            progress_dlg.open = False
            page.update()

            if res and res.get("success"):
                new_bonus = res.get("new_bonus_generations")
                new_bal = res.get("new_coins_balance")

                if state.get("user_sub") is None:
                    state["user_sub"] = {}
                if new_bonus is not None:
                    state["user_sub"]["bonus_generations"] = new_bonus

                if hasattr(page, "session") and hasattr(page.session, "store"):
                    cur_u = page.session.store.get("current_user") or {}
                    if new_bal is not None:
                        cur_u["coins_balance"] = new_bal
                    page.session.store.set("current_user", cur_u)

                show_page_snackbar(page, res.get("message", f"🎉 Exchanged {coins_required} Nu-Coins for +{gen_awarded} AI Credits!"))
                _render_view()
            else:
                err_msg = res.get("error", "Exchange failed. Please try again.")
                show_page_snackbar(page, f"Exchange failed: {err_msg}")
        except Exception as ex:
            progress_dlg.open = False
            page.update()
            show_page_snackbar(page, f"Exchange error: {ex}")
        finally:
            state["is_exchanging"] = False
            if trigger_btn and hasattr(trigger_btn, "disabled"):
                trigger_btn.disabled = False
                try:
                    trigger_btn.update()
                except Exception:
                    pass

    def _render_exchange_card(tier: dict):
        u_data = page.session.store.get("current_user") or {} if hasattr(page, "session") and hasattr(page.session, "store") else {}
        user_coins = int(u_data.get("coins_balance") or 0)
        coins_required = tier["coins"]
        can_afford = user_coins >= coins_required

        badge_color = tier.get("badge_color", ft.Colors.PRIMARY)
        badge_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ft.Colors.with_opacity(0.12, badge_color),
            content=ft.Text(tier.get("badge", "EXCHANGE"), size=9, weight=ft.FontWeight.W_900, color=badge_color),
        )

        discount_pill = None
        if tier.get("discount"):
            discount_pill = ft.Container(
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=ft.BorderRadius.all(4),
                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.GREEN_700),
                content=ft.Text(tier["discount"], size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.GREEN_700),
            )

        action_btn = ft.ElevatedButton(
            content=ft.Row(
                tight=True,
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    nu_coin_icon(size=14),
                    ft.Text(
                        f"Exchange {coins_required} Coins",
                        size=12,
                        weight=ft.FontWeight.W_700,
                        color=ft.Colors.WHITE,
                    ),
                ],
            ),
            bgcolor=ft.Colors.AMBER_800 if can_afford else ft.Colors.with_opacity(0.65, ft.Colors.GREY_700),
            height=38,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
            on_click=lambda e: page.run_task(_handle_exchange, tier, action_btn),
        )

        status_note = ft.Text(
            "✓ Ready to convert" if can_afford else f"Need {coins_required - user_coins} more coins",
            size=10.5,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.GREEN_700 if can_afford else ft.Colors.GREY_500,
        )

        return ft.Container(
            col={"xs": 12, "sm": 6, "md": 6, "lg": 3},
            border_radius=ft.BorderRadius.all(18),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(
                1.5 if tier.get("badge") == "POPULAR" else 1.2,
                ft.Colors.PRIMARY if tier.get("badge") == "POPULAR" else ft.Colors.with_opacity(0.25, badge_color)
            ),
            padding=ft.Padding.all(18),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            badge_container,
                            discount_pill if discount_pill else ft.Container(),
                        ],
                    ),
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text(tier["label"], size=16, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                            ft.Text(tier.get("description", ""), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            nu_coin_icon(size=20),
                            ft.Text(f"{coins_required}", size=24, weight=ft.FontWeight.W_900, color=ft.Colors.AMBER_800),
                            ft.Text("Nu-Coins", size=11.5, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                            ft.Text(f"+{tier['generations']} AI Generation Quota", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE, expand=True),
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.ALL_INCLUSIVE_ROUNDED, size=15, color=ft.Colors.BLUE_600),
                            ft.Text("Non-expiring bonus credit", size=11, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
                        ],
                    ),
                    ft.Container(height=4),
                    action_btn,
                    ft.Row([status_note], alignment=ft.MainAxisAlignment.CENTER),
                ],
            ),
        )

    def _render_exchange_section():
        u_data = page.session.store.get("current_user") or {} if hasattr(page, "session") and hasattr(page.session, "store") else {}
        user_coins = int(u_data.get("coins_balance") or 0)
        sub = state.get("user_sub") or {}
        bonus_gens = int(sub.get("bonus_generations") or 0)

        overview_card = ft.Container(
            border_radius=ft.BorderRadius.all(18),
            bgcolor=ft.Colors.SURFACE,
            padding=ft.Padding.all(16),
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.ResponsiveRow(
                spacing=12,
                run_spacing=12,
                controls=[
                    ft.Container(
                        col={"xs": 12, "sm": 6},
                        border_radius=ft.BorderRadius.all(14),
                        bgcolor=ft.Colors.SURFACE,
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment.TOP_LEFT,
                            end=ft.Alignment.BOTTOM_RIGHT,
                            colors=[
                                ft.Colors.with_opacity(0.14, ft.Colors.AMBER_700),
                                ft.Colors.with_opacity(0.04, ft.Colors.AMBER_900),
                            ],
                        ),
                        padding=ft.Padding.all(14),
                        border=ft.Border.all(1.2, ft.Colors.with_opacity(0.32, ft.Colors.AMBER_700)),
                        content=ft.Row(
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=46,
                                    height=46,
                                    border_radius=ft.BorderRadius.all(12),
                                    bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.AMBER_700),
                                    alignment=ft.Alignment.CENTER,
                                    content=nu_coin_icon(size=26),
                                ),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text("Nu-Coins Balance", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_700),
                                        ft.Text(f"{user_coins:,} Coins", size=19, weight=ft.FontWeight.W_900, color=ft.Colors.AMBER_800),
                                        ft.Text("Available to convert into AI generation credits", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "sm": 6},
                        border_radius=ft.BorderRadius.all(14),
                        bgcolor=ft.Colors.SURFACE,
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment.TOP_LEFT,
                            end=ft.Alignment.BOTTOM_RIGHT,
                            colors=[
                                ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
                                ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
                            ],
                        ),
                        padding=ft.Padding.all(14),
                        border=ft.Border.all(1.2, ft.Colors.with_opacity(0.32, ft.Colors.PRIMARY)),
                        content=ft.Row(
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=46,
                                    height=46,
                                    border_radius=ft.BorderRadius.all(12),
                                    bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PRIMARY, size=24),
                                ),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text("Bonus AI Credits Quota", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_700),
                                        ft.Text(f"{bonus_gens:,} Generations", size=19, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                                        ft.Text("Permanent quota; used when monthly plan limit is reached", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )
        section_title = ft.Row(
            spacing=8,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=28,
                    height=28,
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER_700),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.SWAP_HORIZ_ROUNDED, size=16, color=ft.Colors.AMBER_800),
                ),
                ft.Text("Nu-Coins to AI Credits Exchange", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
            ],
        )

        grid = ft.ResponsiveRow(
            spacing=14,
            run_spacing=14,
            controls=[_render_exchange_card(t) for t in EXCHANGE_TIERS],
        )

        earn_bullets = [
            {
                "icon": "⚔️",
                "color": ft.Colors.AMBER_700,
                "title": "Wagered Partner Duels",
                "desc": "Stake 10–100 Nu-Coins in 15-question quickfire duels against your study partner and claim 90% of the pot on victory.",
            },
            {
                "icon": "🔥",
                "color": ft.Colors.DEEP_ORANGE_600,
                "title": "Daily Duo Study Streaks",
                "desc": "Review shared flashcards daily with your partner to build streaks and unlock escalating Nu-Coin multiplier bonuses.",
            },
            {
                "icon": "🎯",
                "color": ft.Colors.PRIMARY,
                "title": "Platform Quests & Milestones",
                "desc": "Complete practice exam simulations, finish course drills, and reach weekly challenge milestones for quest coin rewards.",
            },
            {
                "icon": "🪙",
                "color": ft.Colors.PURPLE_600,
                "title": "Instant Coin Pack Top-Ups",
                "desc": "Need an immediate wallet boost? Top up Nu-Coin bundles anytime from the Boosters & Coins tab.",
            },
        ]

        bullet_controls = [
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.06, b["color"]),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, b["color"])),
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Container(
                            width=32,
                            height=32,
                            border_radius=ft.BorderRadius.all(8),
                            bgcolor=ft.Colors.with_opacity(0.16, b["color"]),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text(b["icon"], size=16),
                        ),
                        ft.Column(
                            spacing=2,
                            expand=True,
                            controls=[
                                ft.Text(b["title"], size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                ft.Text(b["desc"], size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                        ),
                    ],
                ),
            )
            for b in earn_bullets
        ]

        earn_tips = ft.Container(
            border_radius=ft.BorderRadius.all(16),
            bgcolor=ft.Colors.SURFACE,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.08, ft.Colors.AMBER_700),
                    ft.Colors.with_opacity(0.03, ft.Colors.PURPLE_600),
                ],
            ),
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.25, ft.Colors.AMBER_700)),
            padding=ft.Padding.all(16),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                        spacing=8,
                        controls=[
                            ft.Row(
                                spacing=8,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    nu_coin_icon(size=20),
                                    ft.Text("How to Earn More Nu-Coins", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                ],
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.AMBER_700),
                                content=ft.Text("REWARDS GUIDE", size=9.5, weight=ft.FontWeight.W_900, color=ft.Colors.AMBER_800),
                            ),
                        ],
                    ),
                    ft.Text(
                        "Nu-Coins are earned through active study habits and friendly competition. Complete these activities to stack coins:",
                        size=11.5,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Column(
                        spacing=8,
                        controls=bullet_controls,
                    ),
                ],
            ),
        )

        return ft.Column(
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                overview_card,
                section_title,
                grid,
                earn_tips,
            ],
        )

    def _render_history_tab():
        history_items = state.get("history") or []
        is_loading = state.get("is_loading_history", False)

        if is_loading:
            return ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(40),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.ProgressRing(width=28, height=28, stroke_width=2.5, color=ft.Colors.PRIMARY),
                        ft.Text("Loading payment receipts…", size=13, color=ft.Colors.GREY_500),
                    ],
                ),
            )

        if not history_items:
            return ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(40),
                border_radius=ft.BorderRadius.all(16),
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=48, color=ft.Colors.GREY_400),
                        ft.Text("No Transaction History Yet", size=15, weight=ft.FontWeight.W_700),
                        ft.Text(
                            "Your payments, subscription renewals, booster receipts, and references will appear here.",
                            size=12,
                            color=ft.Colors.GREY_500,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )

        cards = []
        for tx in history_items:
            status = (tx.get("status") or "pending").lower()
            ref = tx.get("reference") or "N/A"
            amt = float(tx.get("amount") or 0)
            purpose = (tx.get("purpose") or "store_purchase").replace("_", " ").title()
            date_str = tx.get("created_at") or ""
            if "T" in date_str:
                date_str = date_str.split("T")[0] + " " + date_str.split("T")[1][:5]

            if status == "success":
                status_color = ft.Colors.GREEN_600
                status_bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)
                status_label = "SUCCESSFUL"
                status_icon = ft.Icons.CHECK_CIRCLE_ROUNDED
            elif status == "pending":
                status_color = ft.Colors.ORANGE_700
                status_bg = ft.Colors.with_opacity(0.12, ft.Colors.ORANGE_700)
                status_label = "PENDING"
                status_icon = ft.Icons.PENDING_ACTIONS_ROUNDED
            else:
                status_color = ft.Colors.RED_600
                status_bg = ft.Colors.with_opacity(0.12, ft.Colors.RED_600)
                status_label = "FAILED"
                status_icon = ft.Icons.ERROR_OUTLINE_ROUNDED

            async def _copy_ref(r=ref):
                await safe_set_clipboard(page, r)
                show_page_snackbar(page, f"Transaction reference copied: {r}")

            async def _retry_verify(r=ref):
                v_res = await verify_payment(token, r)
                if v_res.get("status") == "success":
                    show_page_snackbar(page, "Transaction verified and fulfilled successfully!")
                    await _fetch_payment_history()
                    await _fetch_catalog_and_sub()
                else:
                    show_page_snackbar(page, f"Status: {v_res.get('status', 'Could not verify')}")

            actions_row = ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    ft.TextButton(
                        content=ft.Row(
                            tight=True,
                            spacing=4,
                            controls=[
                                ft.Icon(ft.Icons.COPY_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                                ft.Text("Copy Ref", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                            ],
                        ),
                        on_click=lambda _, r=ref: page.run_task(_copy_ref, r),
                    ),
                ],
            )
            if status == "pending":
                actions_row.controls.append(
                    ft.ElevatedButton(
                        content=ft.Row(
                            tight=True,
                            spacing=4,
                            controls=[
                                ft.Icon(ft.Icons.REFRESH_ROUNDED, size=12, color=ft.Colors.WHITE),
                                ft.Text("Verify Now", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                            ],
                        ),
                        bgcolor=ft.Colors.ORANGE_700,
                        height=28,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6), elevation=0),
                        on_click=lambda _, r=ref: page.run_task(_retry_verify, r),
                    )
                )

            card = ft.Container(
                border_radius=ft.BorderRadius.all(14),
                bgcolor=ft.Colors.SURFACE,
                width=float("inf"),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                    spacing=12,
                    controls=[
                        ft.Row(
                            spacing=12,
                            tight=True,
                            controls=[
                                ft.Container(
                                    width=40,
                                    height=40,
                                    border_radius=ft.BorderRadius.all(10),
                                    bgcolor=status_bg,
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(status_icon, color=status_color, size=20),
                                ),
                                ft.Column(
                                    spacing=2,
                                    tight=True,
                                    controls=[
                                        ft.Text(purpose, size=13.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                        ft.Text(f"Ref: {ref}", size=11, color=ft.Colors.ON_SURFACE_VARIANT, font_family="monospace"),
                                        ft.Text(date_str, size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=14,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Column(
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    spacing=2,
                                    tight=True,
                                    controls=[
                                        ft.Text(f"₦{amt:,.2f}", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.ON_SURFACE),
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=ft.BorderRadius.all(4),
                                            bgcolor=status_bg,
                                            content=ft.Text(status_label, size=9, weight=ft.FontWeight.W_900, color=status_color),
                                        ),
                                    ],
                                ),
                                actions_row,
                            ],
                        ),
                    ],
                ),
            )
            cards.append(card)

        return ft.Column(spacing=10, controls=cards)

    async def _fetch_payment_history():
        if not token:
            return
        state["is_loading_history"] = True
        _render_view()
        try:
            txs = await get_payment_history(token)
            state["history"] = txs or []
        except Exception as ex:
            print(f"[STORE] Error in _fetch_payment_history: {ex}")
        finally:
            state["is_loading_history"] = False
            _render_view()
    # ── VIEW COMPILER ────────────────────────────────────────────────────────
    def _render_view():
        content_area.controls.clear()

        # If catalog or subscription status is loading, show loading spinner first
        # so incorrect details never render and cannot trigger accidental wrong upgrades
        if state.get("is_loading", True):
            content_area.controls.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=90),
                    expand=True,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        tight=True,
                        controls=[
                            ft.ProgressRing(width=44, height=44, stroke_width=3.5, color=ft.Colors.PRIMARY),
                            ft.Text(
                                "Loading Nu Age Learning Store…",
                                size=16,
                                weight=ft.FontWeight.W_800,
                                color=ft.Colors.ON_SURFACE,
                            ),
                            ft.Text(
                                "Verifying your active plan and checking catalog pricing",
                                size=12.5,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                    ),
                )
            )
            if page:
                try:
                    page.update()
                except Exception:
                    pass
            return

        # 1. Hero Trust Banner (Full Width & Theme-Adaptive Contrast)
        is_mobile_screen = bool((page.width or 0) < 680)
        is_small_screen = bool((page.width or 0) < 450)

        hero_banner = ft.Container(
            width=float("inf"),
            bgcolor=ft.Colors.SURFACE,
            padding=ft.Padding.symmetric(horizontal=14 if is_small_screen else 20, vertical=16 if is_small_screen else 22),
            border_radius=ft.BorderRadius.all(18),
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.16, ft.Colors.PRIMARY),
                    ft.Colors.with_opacity(0.06, ft.Colors.AMBER_700),
                ],
            ),
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.28, ft.Colors.PRIMARY)),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        wrap=True,
                        spacing=8,
                        controls=[
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
                                content=ft.Row(
                                    tight=True,
                                    spacing=4,
                                    controls=[
                                        ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=12, color=ft.Colors.PRIMARY),
                                        ft.Text("Paystack Verified Merchant", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                    ],
                                ),
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLUE_400),
                                content=ft.Row(
                                    tight=True,
                                    spacing=4,
                                    controls=[
                                        ft.Icon(ft.Icons.LOCK_ROUNDED, size=12, color=ft.Colors.BLUE_400),
                                        ft.Text("256-Bit SSL Encrypted", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                    ],
                                ),
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_400),
                                content=ft.Row(
                                    tight=True,
                                    spacing=4,
                                    controls=[
                                        ft.Icon(ft.Icons.BOLT_ROUNDED, size=12, color=ft.Colors.PURPLE_400),
                                        ft.Text("Instant Activation", size=10, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                    ],
                                ),
                            ),
                        ],
                    ),
                    ft.Text("Supercharge Your Learning Studio", size=18 if not is_small_screen else 16, weight=ft.FontWeight.W_900, color=ft.Colors.ON_SURFACE),
                    ft.Text(
                        "Upgrade personal scholar plans or top-up non-expiring AI generations and upload quotas using your debit card, bank transfer, or USSD.",
                        size=12 if not is_small_screen else 11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
            ),
        )
        content_area.controls.append(hero_banner)

        # 2. Consolidated Segmented Navigation Tabs
        tab_row = ft.Container(
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)),
            padding=4,
            content=ft.Row(
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    _tab_button("Plans & Subscriptions", "plans", ft.Icons.STARS_ROUNDED),
                    _tab_button("Boosters & Coins", "boosters", ft.Icons.BOLT_ROUNDED),
                    _tab_button("Nu-Coins Exchange", "exchange", ft.Icons.SWAP_HORIZ_ROUNDED),
                    _tab_button("Receipts & History", "history", ft.Icons.RECEIPT_LONG_ROUNDED),
                ],
            ),
        )
        content_area.controls.append(tab_row)

        def _render_subscription_status_banner():
            sub = state.get("user_sub")
            if not sub or not isinstance(sub, dict):
                return None

            status = (sub.get("status") or "active").lower()
            sub_plan_id = (sub.get("subscribed_plan_id") or sub.get("plan_id") or "free").lower()
            if sub_plan_id == "free" and status == "active":
                return None

            label = sub.get("label") or sub_plan_id.title()
            days_left = sub.get("days_remaining")
            cycle = (sub.get("billing_cycle") or "month").title()
            m_used = sub.get("materials_used", 0)
            m_limit = sub.get("materials_limit")
            g_used = sub.get("generations_used", 0)
            g_limit = sub.get("generations_limit")

            catalog_plans = state.get("catalog", {}).get("plans", [])
            matched_plan = next((p for p in catalog_plans if p.get("id") == sub_plan_id), None)
            if not matched_plan:
                matched_plan = {"id": sub_plan_id, "name": label, "price": 4500, "interval": "month"}

            if status == "expired":
                border_col = ft.Colors.RED_600
                bg_col = ft.Colors.with_opacity(0.08, ft.Colors.RED_600)
                icon = ft.Icons.LOCK_CLOCK_ROUNDED
                icon_col = ft.Colors.RED_600
                title = f"{label} Subscription Expired"
                desc = "Your subscription has reached its renewal date. Upload privileges are temporarily locked to free tier. Your existing study materials remain saved in read-only mode."
                btn_text = "Renew Subscription"
                btn_bg = ft.Colors.RED_600
                show_btn = True
            elif status == "grace_period":
                border_col = ft.Colors.AMBER_700
                bg_col = ft.Colors.with_opacity(0.08, ft.Colors.AMBER_700)
                icon = ft.Icons.WARNING_AMBER_ROUNDED
                icon_col = ft.Colors.AMBER_800
                title = f"{label} • 3-Day Grace Period Active"
                desc = "Your subscription renewal was due. You have a 3-day grace period to renew before features revert to the free plan."
                btn_text = "Renew Now"
                btn_bg = ft.Colors.AMBER_800
                show_btn = True
            else:
                border_col = ft.Colors.PRIMARY
                bg_col = ft.Colors.with_opacity(0.06, ft.Colors.PRIMARY)
                icon = ft.Icons.VERIFIED_ROUNDED
                icon_col = ft.Colors.PRIMARY
                title = f"{label} Active • {cycle} Cycle"
                days_str = f" • {days_left} day(s) remaining" if days_left is not None else ""
                desc = f"Uploads: {m_used}/{m_limit if m_limit is not None else '∞'} | AI Generations: {g_used}/{g_limit if g_limit is not None else '∞'}{days_str}"
                btn_text = "Renew / Extend"
                btn_bg = ft.Colors.PRIMARY
                show_btn = (days_left is not None and days_left <= 7)

            cta_btn = None
            if show_btn:
                cta_btn = ft.ElevatedButton(
                    content=ft.Row(
                        tight=True,
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.AUTORENEW_ROUNDED, size=14, color=ft.Colors.WHITE),
                            ft.Text(btn_text, size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                        ],
                    ),
                    bgcolor=btn_bg,
                    height=36,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                    on_click=lambda e: page.run_task(_handle_checkout, matched_plan, "plan", cta_btn),
                )

            is_mobile_sub = bool((page.width or 0) < 680)

            sub_banner_content = (
                ft.Column(
                    spacing=12,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        ft.Row(
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                ft.Icon(icon, size=24, color=icon_col),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text(title, size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                        ft.Text(desc, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                            ],
                        ),
                        cta_btn if cta_btn else ft.Container(),
                    ],
                )
                if is_mobile_sub
                else ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.Row(
                            spacing=12,
                            expand=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(icon, size=24, color=icon_col),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text(title, size=13.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                        ft.Text(desc, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                            ],
                        ),
                        cta_btn if cta_btn else ft.Container(),
                    ],
                )
            )

            return ft.Container(
                border_radius=ft.BorderRadius.all(14),
                bgcolor=bg_col,
                border=ft.Border.all(1.2, border_col),
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                content=sub_banner_content,
            )

        catalog = state.get("catalog")
        cur_tab = state.get("selected_tab", "plans")

        if not catalog and not state.get("is_loading"):
            if cur_tab not in ("exchange", "history"):
                content_area.controls.append(
                    ft.Container(
                        alignment=ft.Alignment.CENTER,
                        padding=ft.Padding.all(40),
                        content=ft.Column(
                            tight=True,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                            controls=[
                                ft.Icon(ft.Icons.STOREFRONT_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("Store Catalog Unavailable", size=16, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                ft.Text("Unable to load store products from the server. Check your connection.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Container(height=8),
                                ft.ElevatedButton(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.REFRESH_ROUNDED, size=16, color=ft.Colors.WHITE),
                                        ft.Text("Retry", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                    ], spacing=6, tight=True),
                                    bgcolor=ft.Colors.PRIMARY,
                                    on_click=lambda _: page.run_task(_fetch_catalog_and_sub, True),
                                ),
                            ],
                        ),
                    )
                )
                if page:
                    try:
                        page.update()
                    except Exception:
                        pass
                return

        catalog_data = catalog or {}

        if cur_tab in ("plans", "org_plans", "org_seats", "org"):
            plans = catalog_data.get("plans", [])

            sub_banner = _render_subscription_status_banner()
            if sub_banner:
                content_area.controls.append(sub_banner)
                content_area.controls.append(ft.Container(height=4))

            content_area.controls.append(
                ft.Row([
                    ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                    ft.Text("Individual Scholar Plans", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                ], spacing=6, tight=True)
            )
            grid = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[_render_plan_card(p) for p in plans])
            content_area.controls.append(grid)

        elif cur_tab in ("boosters", "coins"):
            packs = catalog_data.get("packs", [])
            coin_packs = catalog_data.get("coins", [])

            # Nu-Coins Exchange Teaser Banner in Boosters & Coins tab
            u_data_b = page.session.store.get("current_user") or {} if hasattr(page, "session") and hasattr(page.session, "store") else {}
            u_coins_b = int(u_data_b.get("coins_balance") or 0)
            
            is_mobile_teaser = bool((page.width or 0) < 680)
            teaser_content = (
                ft.Column(
                    spacing=12,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        ft.Row(
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                ft.Container(
                                    width=40,
                                    height=40,
                                    border_radius=ft.BorderRadius.all(10),
                                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.AMBER_700),
                                    alignment=ft.Alignment.CENTER,
                                    content=nu_coin_icon(size=24),
                                ),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text("Have Nu-Coins? Exchange directly for AI Credits", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                        ft.Text(f"Convert your duel winnings into AI Generations without cash • Balance: {u_coins_b:,} Coins", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                            ],
                        ),
                        ft.ElevatedButton(
                            content=ft.Row([
                                ft.Icon(ft.Icons.SWAP_HORIZ_ROUNDED, size=15, color=ft.Colors.WHITE),
                                ft.Text("Exchange Coins for AI Credits", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                            bgcolor=ft.Colors.AMBER_800,
                            height=38,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                            on_click=lambda _: _switch_tab("exchange"),
                        ),
                    ],
                )
                if is_mobile_teaser
                else ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.Row(
                            spacing=12,
                            expand=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=44,
                                    height=44,
                                    border_radius=ft.BorderRadius.all(12),
                                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.AMBER_700),
                                    alignment=ft.Alignment.CENTER,
                                    content=nu_coin_icon(size=26),
                                ),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text("Have Nu-Coins? Exchange directly for AI Credits", size=13.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                        ft.Text(f"Convert your duel winnings into AI Generations without cash • Current Balance: {u_coins_b:,} Coins", size=11.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                            ],
                        ),
                        ft.ElevatedButton(
                            content=ft.Row([
                                ft.Icon(ft.Icons.SWAP_HORIZ_ROUNDED, size=15, color=ft.Colors.WHITE),
                                ft.Text("Exchange Coins", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                            ], spacing=6, tight=True),
                            bgcolor=ft.Colors.AMBER_800,
                            height=38,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                            on_click=lambda _: _switch_tab("exchange"),
                        ),
                    ],
                )
            )

            exchange_teaser = ft.Container(
                border_radius=ft.BorderRadius.all(16),
                bgcolor=ft.Colors.SURFACE,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment.TOP_LEFT,
                    end=ft.Alignment.BOTTOM_RIGHT,
                    colors=[
                        ft.Colors.with_opacity(0.14, ft.Colors.AMBER_700),
                        ft.Colors.with_opacity(0.04, ft.Colors.AMBER_900),
                    ],
                ),
                border=ft.Border.all(1.2, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_700)),
                padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                content=teaser_content,
            )
            content_area.controls.append(exchange_teaser)
            content_area.controls.append(ft.Container(height=4))

            content_area.controls.append(
                ft.Row([
                    ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=16, color=ft.Colors.PURPLE_600),
                    ft.Text("Permanent Study Booster Packs", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                ], spacing=6, tight=True)
            )
            grid = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[_render_booster_card(b) for b in packs])
            content_area.controls.append(grid)

            if coin_packs:
                content_area.controls.append(ft.Container(height=12))
                content_area.controls.append(
                    ft.Row([
                        nu_coin_icon(size=18),
                        ft.Text("Nu-Coins Credit Bundles", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                    ], spacing=6, tight=True)
                )
                coin_grid = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[_render_coin_card(c) for c in coin_packs])
                content_area.controls.append(coin_grid)

        elif cur_tab == "exchange":
            content_area.controls.append(_render_exchange_section())

        elif cur_tab == "history":
            content_area.controls.append(_render_history_tab())

        content_area.controls.append(ft.Container(height=36))
        if page:
            try:
                page.update()
            except Exception:
                pass

    async def _fetch_catalog_and_sub(show_spinner: bool = True):
        if show_spinner:
            state["is_loading"] = True
            _render_view()

        try:
            if token:
                cat_res, sub_res = await asyncio.gather(
                    get_store_catalog(),
                    get_subscription_status(token),
                    return_exceptions=True,
                )
                if not isinstance(cat_res, Exception) and isinstance(cat_res, dict) and cat_res:
                    state["catalog"] = cat_res

                if not isinstance(sub_res, Exception) and isinstance(sub_res, dict) and "plan_id" in sub_res:
                    state["user_sub"] = sub_res
            else:
                cat_res = await get_store_catalog()
                if isinstance(cat_res, dict) and cat_res:
                    state["catalog"] = cat_res
        except asyncio.CancelledError:
            # Task cancelled by timeout; do not clear is_loading so spinner remains active
            raise
        except Exception as ex:
            print(f"[STORE] Failed to fetch catalog and subscription: {ex}")
            state["is_loading"] = False
            _render_view()
        else:
            state["is_loading"] = False
            _render_view()

    # 1. Initial render shows the loading spinner so no stale or wrong plan details appear
    _render_view()

    # 2. Fast-fetch catalog and verified subscription status; if network responds promptly,
    # the view renders 100% verified and correct without any late visual mutation.
    # If network takes longer, the spinner stays on screen until background task completes.
    try:
        await asyncio.wait_for(_fetch_catalog_and_sub(show_spinner=False), timeout=2.0)
    except (asyncio.TimeoutError, TimeoutError):
        page.run_task(_fetch_catalog_and_sub, False)
    except Exception as ex:
        print(f"[STORE] Initial fetch error: {ex}")
        state["is_loading"] = False
        _render_view()

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
