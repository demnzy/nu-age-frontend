"""
Interactive Study Bundle Builder & Curriculum Studio
Modeled after Nu-Age's Playlist / Learning Path and Curriculum Builder UX.
Provides Super Administrators with a professional studio to compose multi-pack study bundles,
sequence constituent packs with roadmap timeline connectors, pick packs via an intuitive modal,
and compute live bundle economics and discount tiers.
"""

import flet as ft
from typing import List, Dict, Any, Callable, Optional
from src.components import study_ui as ui
from src.utils.file_opener import show_page_snackbar

_THEMES = [
    ("purple_indigo", "Purple Indigo", "#6366F1", "#8B5CF6"),
    ("oceanic_blue", "Oceanic Blue", "#0284C7", "#06B6D4"),
    ("emerald_teal", "Emerald Teal", "#059669", "#10B981"),
    ("sunset_orange", "Sunset Orange", "#EA580C", "#F59E0B"),
    ("rose_amber", "Rose Amber", "#E11D48", "#F43F5E"),
    ("midnight_dark", "Midnight Dark", "#1E293B", "#334155"),
]

_CATEGORIES = [
    "JAMB UTME",
    "WAEC WASSCE",
    "NECO SSCE",
    "University Prep",
    "Medical & Health Sciences",
    "Engineering & Tech",
    "Law & Humanities",
    "General",
]


def show_bundle_builder_dialog(
    page: ft.Page,
    available_packs: List[Dict[str, Any]],
    existing_bundle: Optional[Dict[str, Any]] = None,
    on_save: Optional[Callable[[Dict[str, Any]], Any]] = None,
):
    """
    Renders the Study Bundle Builder Studio.
    Adapts the playlist & curriculum sequential workflow for multi-pack exam bundles.
    """
    screen_width = page.width or 800
    screen_height = page.height or 800
    is_desktop = screen_width >= 920
    is_edit_mode = bool(existing_bundle and existing_bundle.get("id"))

    # Initial state
    init_title = (existing_bundle.get("title") if existing_bundle else "") or ""
    init_desc = (existing_bundle.get("description") if existing_bundle else "") or ""
    init_cat = (existing_bundle.get("category") if existing_bundle else "General") or "General"
    init_theme = (existing_bundle.get("theme_gradient") if existing_bundle else "purple_indigo") or "purple_indigo"
    init_banner = (existing_bundle.get("banner_url") if existing_bundle else "") or ""
    init_disc = int(existing_bundle.get("discount_percentage", 20) if existing_bundle else 20)

    # Initial constituent packs (preserve order if given)
    local_packs: List[Dict[str, Any]] = []
    if existing_bundle and existing_bundle.get("packs"):
        for p in existing_bundle.get("packs", []):
            local_packs.append(p)
    elif existing_bundle and existing_bundle.get("pack_ids"):
        p_map = {str(p.get("id")): p for p in available_packs}
        for pid in existing_bundle.get("pack_ids", []):
            if str(pid) in p_map:
                local_packs.append(p_map[str(pid)])

    # Inputs
    title_field = ft.TextField(
        value=init_title,
        label="Bundle Title (e.g. Science Revision Mega Pack)",
        dense=True,
        border_radius=8,
    )

    category_dropdown = ft.Dropdown(
        label="Exam Category",
        dense=True,
        options=[ft.dropdown.Option(c, c) for c in _CATEGORIES],
        value=init_cat,
        expand=True,
    )

    theme_dropdown = ft.Dropdown(
        label="Theme Gradient",
        dense=True,
        options=[ft.dropdown.Option(k, v) for k, v, _, _ in _THEMES],
        value=init_theme,
        expand=True,
    )

    banner_url_field = ft.TextField(
        value=init_banner,
        label="Banner Image URL (Optional)",
        hint_text="https://...",
        dense=True,
        border_radius=8,
    )

    description_field = ft.TextField(
        value=init_desc,
        label="Bundle Description / Syllabus Scope",
        multiline=True,
        min_lines=2,
        max_lines=3,
        dense=True,
        border_radius=8,
    )

    discount_slider = ft.Slider(
        min=0,
        max=80,
        divisions=16,
        value=init_disc,
        label="{value}% Off",
        expand=True,
    )

    price_coins_field = ft.TextField(
        value=str(existing_bundle.get("price_coins", 0) if existing_bundle else 0),
        label="Bundle Price (Nu-Coins)",
        dense=True,
        width=140,
        border_radius=8,
    )

    # Live summary badges
    summary_pack_count = ft.Text("0 Packs", size=12, weight=ft.FontWeight.BOLD, color=ui.C_INFO)
    summary_total_q = ft.Text("0 Questions", size=12, color=ui.muted(0.80))
    summary_orig_price = ft.Text("Original: 0 Coins", size=12, color=ui.muted(0.70))
    summary_savings_badge = ft.Container(
        content=ft.Text("20% Savings", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        bgcolor=ui.C_CORRECT,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        border_radius=6,
    )

    # Live Banner Gradient Preview
    preview_title = ft.Text(init_title or "Bundle Preview", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, no_wrap=True)
    preview_subtitle = ft.Text(f"{init_cat} • 0 Constituent Packs", size=11, color=ft.Colors.WHITE70)
    preview_banner_container = ft.Container(
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=["#6366F1", "#8B5CF6"],
        ),
        border_radius=10,
        padding=14,
        content=ft.Row([
            ft.Column([
                preview_title,
                preview_subtitle,
            ], spacing=2, expand=True),
            summary_savings_badge,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )

    def _calc_pricing():
        tot_orig = sum(int(p.get("price_coins") or 0) for p in local_packs)
        tot_q = 0
        tot_fc = 0
        for p in local_packs:
            pd = p.get("pack_data") or {}
            tot_q += len(pd.get("questions", []))
            tot_fc += len(pd.get("flashcards", []))

        disc_pct = int(discount_slider.value or 0)
        bundle_price = max(0, int(tot_orig * (1.0 - (disc_pct / 100.0))))

        price_coins_field.value = str(bundle_price)

        summary_pack_count.value = f"{len(local_packs)} Pack{'s' if len(local_packs) != 1 else ''} in Bundle"
        summary_total_q.value = f"{tot_q} Qs • {tot_fc} Flashcards"
        summary_orig_price.value = f"Original Value: {tot_orig} Coins"

        saved_coins = max(0, tot_orig - bundle_price)
        summary_savings_badge.content = ft.Text(
            f"{disc_pct}% Off (Save {saved_coins} Coins)",
            size=10,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE,
        )
        summary_savings_badge.visible = (disc_pct > 0 and tot_orig > 0)

        preview_title.value = title_field.value.strip() or "Bundle Preview"
        preview_subtitle.value = f"{category_dropdown.value or 'General'} • {len(local_packs)} Constituent Packs"

        cur_t = theme_dropdown.value or "purple_indigo"
        for k, _, c1, c2 in _THEMES:
            if k == cur_t:
                preview_banner_container.gradient = ft.LinearGradient(
                    begin=ft.Alignment.TOP_LEFT,
                    end=ft.Alignment.BOTTOM_RIGHT,
                    colors=[c1, c2],
                )
                break

    def _on_input_change(e=None):
        _calc_pricing()
        page.update()

    title_field.on_change = _on_input_change
    category_dropdown.on_change = _on_input_change
    theme_dropdown.on_change = _on_input_change
    discount_slider.on_change = _on_input_change

    # ── Roadmap / Curriculum Sequence Container ──
    roadmap_container = ft.Column(spacing=0)

    # ── Add Pack Modal (Adapted from Playlist Builder's show_add_course_modal) ──
    def show_add_pack_modal(e=None):
        existing_ids = {str(p.get("id")) for p in local_packs}
        avail = [p for p in available_packs if str(p.get("id")) not in existing_ids]

        search_input = ft.TextField(
            hint_text="Search available study packs...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            dense=True,
            border_radius=8,
        )
        packs_list_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

        picker_dlg_ref = [None]

        def _close_picker(ev=None):
            if picker_dlg_ref[0]:
                picker_dlg_ref[0].open = False
                page.update()

        def _add_pack_to_bundle(pack_obj):
            local_packs.append(pack_obj)
            _close_picker()
            _calc_pricing()
            _render_roadmap()
            page.update()

        def _render_picker_items():
            packs_list_col.controls.clear()
            query = (search_input.value or "").lower().strip()
            filtered = [
                p for p in avail
                if not query or query in str(p.get("title", "")).lower() or query in str(p.get("category", "")).lower()
            ]

            if not filtered:
                packs_list_col.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(vertical=30),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column([
                            ft.Icon(ft.Icons.INBOX_ROUNDED, size=32, color=ui.muted(0.4)),
                            ft.Text("No available study packs found", size=13, color=ui.muted()),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    )
                )
                return

            for p in filtered:
                pd = p.get("pack_data") or {}
                q_cnt = len(pd.get("questions", []))
                fc_cnt = len(pd.get("flashcards", []))
                price = int(p.get("price_coins") or 0)
                cat = p.get("category", "General")

                packs_list_col.controls.append(
                    ft.Container(
                        bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.03),
                        border=ft.Border.all(1, ui.hairline(0.15)),
                        border_radius=10,
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        ink=True,
                        on_click=lambda _, po=p: _add_pack_to_bundle(po),
                        content=ft.Row([
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=8,
                                bgcolor=ui.tint(ft.Colors.PRIMARY, 0.12),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                            ),
                            ft.Column([
                                ft.Text(p.get("title", "Untitled"), size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, no_wrap=True),
                                ft.Row([
                                    ui.pill(cat, color=ui.C_INFO, size=9),
                                    ft.Text(f"{q_cnt} Qs • {fc_cnt} Cards", size=11, color=ui.muted()),
                                ], spacing=6, tight=True),
                            ], spacing=2, expand=True),
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=12, color=ui.C_WARN),
                                    ft.Text(f"{price}", size=11, weight=ft.FontWeight.BOLD, color=ui.C_WARN),
                                ], spacing=2, tight=True),
                                bgcolor=ui.tint(ui.C_WARN, 0.12),
                                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                border_radius=6,
                            ),
                            ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED, size=20, color=ft.Colors.PRIMARY),
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    )
                )

        search_input.on_change = lambda _: (_render_picker_items(), page.update())
        _render_picker_items()

        picker_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.LIBRARY_ADD_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                    ft.Text("Add Study Pack to Bundle", size=15, weight=ft.FontWeight.BOLD),
                ], spacing=8, tight=True),
                ft.IconButton(ft.Icons.CLOSE_ROUNDED, on_click=_close_picker),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            content=ft.Container(
                width=520,
                height=420,
                content=ft.Column([
                    search_input,
                    packs_list_col,
                ], spacing=10),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_close_picker),
            ],
        )
        picker_dlg_ref[0] = picker_dlg
        page.overlay.append(picker_dlg)
        picker_dlg.open = True
        page.update()

    def _render_roadmap():
        roadmap_container.controls.clear()
        total_items = len(local_packs)

        if not local_packs:
            empty_state = ft.Container(
                padding=ft.Padding.symmetric(vertical=40, horizontal=16),
                alignment=ft.Alignment.CENTER,
                content=ft.Column([
                    ft.Container(
                        width=56,
                        height=56,
                        border_radius=28,
                        bgcolor=ui.tint(ft.Colors.PRIMARY, 0.10),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.COLLECTIONS_BOOKMARK_ROUNDED, size=26, color=ft.Colors.PRIMARY),
                    ),
                    ft.Text("Bundle Roadmap is Empty", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(
                        "Add individual subject packs to build a comprehensive multi-subject bundle.",
                        size=12,
                        color=ui.muted(),
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=6),
                    ft.FilledButton(
                        "Add First Study Pack",
                        icon=ft.Icons.ADD_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PRIMARY,
                            shape=ft.RoundedRectangleBorder(radius=10),
                        ),
                        on_click=show_add_pack_modal,
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            )
            roadmap_container.controls.append(empty_state)
            return

        for index, p in enumerate(local_packs):
            pid = str(p.get("id"))
            p_title = p.get("title", "Untitled Pack")
            p_cat = p.get("category", "General")
            pd = p.get("pack_data") or {}
            q_cnt = len(pd.get("questions", []))
            fc_cnt = len(pd.get("flashcards", []))
            price_coins = int(p.get("price_coins") or 0)
            step_num = f"{index + 1:02d}"

            def _move_up(idx=index):
                if idx > 0:
                    local_packs[idx], local_packs[idx - 1] = local_packs[idx - 1], local_packs[idx]
                    _calc_pricing()
                    _render_roadmap()
                    page.update()

            def _move_down(idx=index):
                if idx < total_items - 1:
                    local_packs[idx], local_packs[idx + 1] = local_packs[idx + 1], local_packs[idx]
                    _calc_pricing()
                    _render_roadmap()
                    page.update()

            def _remove_pack(idx=index):
                local_packs.pop(idx)
                _calc_pricing()
                _render_roadmap()
                page.update()

            pack_card = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=12,
                border=ft.Border.all(1, ui.hairline(0.18)),
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                content=ft.Row([
                    ft.Container(
                        width=32,
                        height=32,
                        border_radius=8,
                        bgcolor=ui.tint(ft.Colors.PRIMARY, 0.12),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(step_num, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    ),
                    ft.Column([
                        ft.Text(p_title, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, no_wrap=True),
                        ft.Row([
                            ui.pill(p_cat, color=ui.C_INFO, size=9),
                            ft.Text(f"{q_cnt} Qs • {fc_cnt} Cards", size=10.5, color=ui.muted()),
                            ft.Text(f"• 💰 {price_coins} Coins", size=10.5, color=ui.C_WARN, weight=ft.FontWeight.W_700),
                        ], spacing=6, tight=True),
                    ], spacing=2, expand=True),
                    ft.Row([
                        *(
                            [ft.IconButton(ft.Icons.ARROW_UPWARD_ROUNDED, icon_size=16, tooltip="Move Up", on_click=lambda _, i=index: _move_up(i))]
                            if index > 0 else []
                        ),
                        *(
                            [ft.IconButton(ft.Icons.ARROW_DOWNWARD_ROUNDED, icon_size=16, tooltip="Move Down", on_click=lambda _, i=index: _move_down(i))]
                            if index < total_items - 1 else []
                        ),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=18, icon_color=ui.C_WRONG, tooltip="Remove", on_click=lambda _, i=index: _remove_pack(i)),
                    ], spacing=0, tight=True),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )

            # Connector line
            connector = ft.Container(
                width=2,
                height=14,
                bgcolor=ui.hairline(0.25),
                margin=ft.Padding.only(left=28),
            )

            if index < total_items - 1:
                roadmap_container.controls.extend([pack_card, connector])
            else:
                roadmap_container.controls.append(pack_card)

        # "Add More" action button at the bottom of the roadmap
        add_more_btn = ft.Container(
            padding=ft.Padding.only(top=10),
            content=ft.OutlinedButton(
                "Add Another Study Pack to Bundle",
                icon=ft.Icons.ADD_ROUNDED,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    side=ft.BorderSide(1.2, ft.Colors.PRIMARY),
                    color=ft.Colors.PRIMARY,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                ),
                on_click=show_add_pack_modal,
            ),
            alignment=ft.Alignment.CENTER,
        )
        roadmap_container.controls.append(add_more_btn)

    # ── Initial State Preparation ──
    _calc_pricing()
    _render_roadmap()

    # ── Modal Controls ──
    dlg_ref = [None]

    def _close_dlg(e=None):
        if dlg_ref[0]:
            dlg_ref[0].open = False
            page.update()

    publish_btn_content = ft.Row([
        ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED if not is_edit_mode else ft.Icons.SAVE_ROUNDED, size=16, color=ft.Colors.ON_PRIMARY),
        ft.Text("Update Study Bundle" if is_edit_mode else "Publish Study Bundle", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
    ], spacing=6, tight=True)

    publish_btn = ft.FilledButton(
        content=publish_btn_content,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.PRIMARY,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding.symmetric(horizontal=20, vertical=12),
        ),
    )

    async def _execute_submit(_=None):
        title = title_field.value.strip()
        if len(title) < 3:
            show_page_snackbar(page, "Please enter a bundle title of at least 3 characters.")
            return

        if not local_packs:
            show_page_snackbar(page, "Please add at least 1 study pack into the bundle sequence.")
            return

        try:
            price_coins = int(price_coins_field.value.strip())
        except ValueError:
            price_coins = 0

        disc_pct = int(discount_slider.value or 0)
        pack_ids_ordered = [str(p.get("id")) for p in local_packs]

        bundle_payload = {
            "title": title,
            "description": description_field.value.strip(),
            "category": category_dropdown.value or "General",
            "theme_gradient": theme_dropdown.value or "purple_indigo",
            "banner_url": banner_url_field.value.strip() or None,
            "price_coins": max(0, price_coins),
            "discount_percentage": min(100, max(0, disc_pct)),
            "pack_ids": pack_ids_ordered,
        }

        if is_edit_mode:
            bundle_payload["id"] = existing_bundle.get("id")

        publish_btn_content.controls[0] = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
        publish_btn_content.controls[1].value = "Publishing Bundle..."
        publish_btn.disabled = True
        page.update()

        _close_dlg()
        if on_save:
            import inspect
            import asyncio
            if inspect.iscoroutinefunction(on_save):
                await on_save(bundle_payload)
            else:
                res = on_save(bundle_payload)
                if asyncio.iscoroutine(res) or isinstance(res, asyncio.Future):
                    await res

    publish_btn.on_click = lambda e: page.run_task(_execute_submit)

    # ── Left Column: Roadmap List ──
    left_rail = ft.Container(
        width=460 if is_desktop else None,
        bgcolor=ui.tint(ft.Colors.ON_SURFACE, 0.02),
        border=ft.Border.all(1, ui.hairline(0.12)),
        border_radius=12,
        padding=14,
        content=ft.Column([
            ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.ROUTE_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                    ft.Text("Bundle Curriculum Sequence", size=13, weight=ft.FontWeight.BOLD),
                ], spacing=6, tight=True),
                summary_pack_count,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=1, color=ui.hairline(0.12)),
            ft.Column([roadmap_container], scroll=ft.ScrollMode.AUTO, expand=True),
        ], spacing=10, expand=True),
    )

    # ── Right Column: Studio & Economics ──
    right_canvas = ft.Container(
        expand=True,
        content=ft.Column(
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                preview_banner_container,
                ui.surface_card(
                    ft.Column([
                        ui.section_label("1. Bundle Details & Theme"),
                        title_field,
                        ft.Row([category_dropdown, theme_dropdown], spacing=10),
                        banner_url_field,
                        description_field,
                    ], spacing=10),
                    padding=14,
                ),
                ui.surface_card(
                    ft.Column([
                        ui.section_label("2. Bundle Economics & Live Discount"),
                        ft.Row([
                            summary_total_q,
                            summary_orig_price,
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.Text("Discount:", size=12, weight=ft.FontWeight.W_700),
                            discount_slider,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Row([
                            price_coins_field,
                            ft.Text("0 for Free Bundle", size=11, color=ui.muted(0.65)),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    ], spacing=10),
                    padding=14,
                ),
            ],
        ),
    )

    if is_desktop:
        body_content = ft.Row(
            spacing=14,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[left_rail, right_canvas],
        )
    else:
        body_content = ft.Column(
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            controls=[
                preview_banner_container,
                ui.surface_card(
                    ft.Column([
                        ui.section_label("Bundle Details"),
                        title_field,
                        ft.Row([category_dropdown, theme_dropdown], spacing=8),
                        description_field,
                    ], spacing=8),
                    padding=12,
                ),
                ui.surface_card(
                    ft.Column([
                        ui.section_label("Constituent Packs"),
                        roadmap_container,
                    ], spacing=8),
                    padding=12,
                ),
                ui.surface_card(
                    ft.Column([
                        ui.section_label("Pricing & Discount"),
                        discount_slider,
                        price_coins_field,
                    ], spacing=8),
                    padding=12,
                ),
            ],
        )

    modal_width = min(1140, int(screen_width * 0.96))
    modal_height = min(720, int(screen_height * 0.88))

    dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=16),
        bgcolor=ft.Colors.SURFACE,
        title=ft.Row([
            ft.Row([
                ft.Icon(ft.Icons.COLLECTIONS_BOOKMARK_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                ft.Text(
                    "Edit Study Bundle" if is_edit_mode else "Create Multi-Pack Study Bundle",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.ON_SURFACE,
                ),
            ], spacing=8, tight=True),
            ft.IconButton(ft.Icons.CLOSE_ROUNDED, tooltip="Close", on_click=_close_dlg),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        content=ft.Container(
            width=modal_width,
            height=modal_height,
            content=body_content,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=_close_dlg),
            publish_btn,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref[0] = dlg

    page.overlay.append(dlg)
    dlg.open = True
    page.update()
