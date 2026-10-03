"""
Deck Inspector & Q&A Browser Component.
Allows learners to browse ALL flashcard questions, answers, explanations,
and SRS mastery states for a study material with rich Markdown support.
"""

import asyncio
import flet as ft
from src.requests.study import get_all_cards
from src.utils.file_opener import safe_set_clipboard, show_page_snackbar


def open_deck_inspector(
    page: ft.Page,
    token: str,
    material: dict | None = None,
    preloaded_cards: list | None = None,
):
    material = material or {}
    mid = str(material.get("id") or "")
    mtitle = material.get("title") or "Study Material"

    cards_state = {
        "all": [],
        "filter": "all",  # "all", "due", "mastered"
        "search": "",
        "loading": True,
    }

    dialog_w = min(page.width - 24, 720) if page.width else 660
    dialog_h = min(page.height - 80, 780) if page.height else 680

    cards_column = ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)

    header_count_badge = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=ft.BorderRadius.all(8),
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        content=ft.Text(
            "Loading…",
            size=11,
            weight=ft.FontWeight.W_800,
            color=ft.Colors.PRIMARY,
        ),
    )

    def _get_card_font_size(text: str) -> int:
        l = len((text or "").strip())
        if l <= 60:
            return 16
        elif l <= 160:
            return 14.5
        elif l <= 300:
            return 13.5
        else:
            return 12.5

    def _render_cards():
        cards_column.controls.clear()

        all_c = cards_state["all"]
        q = cards_state["search"].lower().strip()
        f = cards_state["filter"]

        filtered = []
        for c in all_c:
            front = str(c.get("front") or "")
            back = str(c.get("back") or c.get("explanation") or "")

            if q and (q not in front.lower() and q not in back.lower()):
                continue

            interval = (c.get("srs_state") or {}).get("interval", 0) or 0
            if f == "due" and interval > 1:
                continue
            if f == "mastered" and interval <= 1:
                continue

            filtered.append(c)

        total_cnt = len(all_c)
        due_cnt = sum(1 for c in all_c if ((c.get("srs_state") or {}).get("interval", 0) or 0) <= 1)
        mastered_cnt = sum(1 for c in all_c if ((c.get("srs_state") or {}).get("interval", 0) or 0) > 1)

        header_count_badge.content.value = f"{total_cnt} Cards in Deck"
        try:
            header_count_badge.update()
        except Exception:
            pass

        # Update pill labels
        btn_all.content.controls[0].value = f"All ({total_cnt})"
        btn_due.content.controls[0].value = f"Due Soon ({due_cnt})"
        btn_mastered.content.controls[0].value = f"Mastered ({mastered_cnt})"
        _update_filter_pill_styles()

        if not filtered:
            empty_msg = (
                f"No cards match '{q}'" if q
                else "No cards due for review" if f == "due"
                else "No cards mastered yet" if f == "mastered"
                else "No flashcards generated yet for this material"
            )
            empty_sub = (
                "Try searching for another term" if q
                else "Generate flashcards from the cockpit to populate your deck"
            )
            cards_column.controls.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=60),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=38, color=ft.Colors.GREY_400),
                            ft.Text(empty_msg, size=13.5, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_600),
                            ft.Text(empty_sub, size=11, color=ft.Colors.GREY_500),
                        ],
                    ),
                )
            )
            if not cards_state["loading"] and body_switcher.content != cards_view:
                body_switcher.content = cards_view
            page.update()
            return

        for idx, card in enumerate(filtered, start=1):
            front_text = str(card.get("front") or "—")
            back_text = str(card.get("back") or card.get("explanation") or "—")
            srs = card.get("srs_state") or {}
            interval = srs.get("interval", 0) or 0

            if interval == 0:
                srs_tag = "New Card"
                srs_color = ft.Colors.BLUE_600
            elif interval <= 1:
                srs_tag = "Due Soon · 1d interval"
                srs_color = ft.Colors.AMBER_700
            elif interval <= 6:
                srs_tag = f"Active · {interval}d interval"
                srs_color = ft.Colors.TEAL_600
            else:
                srs_tag = f"Mastered · {interval}d interval"
                srs_color = ft.Colors.GREEN_700

            f_size = _get_card_font_size(front_text)
            b_size = _get_card_font_size(back_text)

            async def _copy_card(e, q_txt=front_text, a_txt=back_text):
                full_txt = f"Q: {q_txt}\n\nA: {a_txt}"
                await safe_set_clipboard(page, full_txt)
                show_page_snackbar(page, "Copied Q&A to clipboard!")

            bento_card = ft.Container(
                border_radius=ft.BorderRadius.all(14),
                bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(14),
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Column(
                    spacing=10,
                    controls=[
                        # Top metadata row: Card number, SRS mastery state, and copy button
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=6,
                                    tight=True,
                                    controls=[
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                            border_radius=ft.BorderRadius.all(6),
                                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                            content=ft.Text(f"#{idx}", size=10, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                                        ),
                                        ft.Container(
                                            padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                            border_radius=ft.BorderRadius.all(6),
                                            bgcolor=ft.Colors.with_opacity(0.10, srs_color),
                                            content=ft.Text(srs_tag, size=9.5, weight=ft.FontWeight.W_700, color=srs_color),
                                        ),
                                    ],
                                ),
                                ft.IconButton(
                                    ft.Icons.COPY_ALL_ROUNDED,
                                    icon_size=15,
                                    icon_color=ft.Colors.GREY_500,
                                    tooltip="Copy Q&A",
                                    on_click=_copy_card,
                                ),
                            ],
                        ),
                        # Question front (with left accent border)
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.PRIMARY),
                            border=ft.Border(left=ft.BorderSide(3.5, ft.Colors.PRIMARY)),
                            content=ft.Column(
                                spacing=4,
                                tight=True,
                                controls=[
                                    ft.Row(
                                        spacing=5,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.HELP_OUTLINE_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                                            ft.Text("QUESTION", size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY),
                                        ],
                                    ),
                                    ft.Text(front_text, size=f_size, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE, selectable=True),
                                ],
                            ),
                        ),
                        # Answer & explanation (Markdown Supported & Adaptive Font Size)
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.GREEN_600),
                            border=ft.Border(left=ft.BorderSide(3.5, ft.Colors.GREEN_600)),
                            content=ft.Column(
                                spacing=4,
                                tight=True,
                                controls=[
                                    ft.Row(
                                        spacing=5,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=13, color=ft.Colors.GREEN_700),
                                            ft.Text("ANSWER & EXPLANATION", size=9.5, weight=ft.FontWeight.W_800, color=ft.Colors.GREEN_700),
                                        ],
                                    ),
                                    ft.Markdown(
                                        back_text,
                                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                                        selectable=True,
                                        auto_follow_links=True,
                                        code_theme="atom-one-dark",
                                        md_style_sheet=ft.MarkdownStyleSheet(
                                            p_text_style=ft.TextStyle(size=b_size, color=ft.Colors.ON_SURFACE),
                                            strong_text_style=ft.TextStyle(size=b_size, weight=ft.FontWeight.W_800),
                                            code_text_style=ft.TextStyle(size=max(11, int(b_size - 1.5))),
                                        ),
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            )
            cards_column.controls.append(bento_card)

        if not cards_state["loading"] and body_switcher.content != cards_view:
            body_switcher.content = cards_view

        page.update()

    # ── Filter buttons ────────────────────────────────────────────────────────
    def _set_filter(f_name: str):
        cards_state["filter"] = f_name
        _render_cards()

    def _make_filter_btn(label: str, f_key: str):
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            border_radius=ft.BorderRadius.all(8),
            ink=True,
            on_click=lambda _: _set_filter(f_key),
            content=ft.Row(
                tight=True,
                spacing=4,
                controls=[
                    ft.Text(label, size=11, weight=ft.FontWeight.W_700),
                ],
            ),
        )

    btn_all = _make_filter_btn("All (0)", "all")
    btn_due = _make_filter_btn("Due Soon (0)", "due")
    btn_mastered = _make_filter_btn("Mastered (0)", "mastered")

    def _update_filter_pill_styles():
        curr = cards_state["filter"]
        for btn, k in [(btn_all, "all"), (btn_due, "due"), (btn_mastered, "mastered")]:
            is_active = (curr == k)
            btn.bgcolor = ft.Colors.PRIMARY if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
            btn.content.controls[0].color = ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE

    _update_filter_pill_styles()

    # ── Search field ─────────────────────────────────────────────────────────
    def _clear_search(e):
        search_field.value = ""
        clear_search_btn.visible = False
        cards_state["search"] = ""
        _render_cards()

    clear_search_btn = ft.IconButton(
        ft.Icons.CLEAR_ROUNDED,
        icon_size=15,
        icon_color=ft.Colors.GREY_500,
        visible=False,
        on_click=_clear_search,
    )

    def _on_search_change(e):
        val = e.control.value or ""
        cards_state["search"] = val
        clear_search_btn.visible = bool(val.strip())
        clear_search_btn.update()
        _render_cards()

    search_field = ft.TextField(
        hint_text="Search questions, answers or keywords…",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        suffix=clear_search_btn,
        dense=True,
        text_size=12,
        height=38,
        border_radius=ft.BorderRadius.all(10),
        expand=True,
        on_change=_on_search_change,
    )

    def _close(e):
        dlg.open = False
        page.update()

    loading_view = ft.Container(
        key="loading",
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            tight=True,
            controls=[
                ft.ProgressRing(width=38, height=38, stroke_width=3, color=ft.Colors.PRIMARY),
                ft.Text("Fetching full deck questions & answers…", size=13.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                ft.Text("Retrieving all active recall cards for this material", size=11, color=ft.Colors.GREY_500),
            ],
        ),
    )

    cards_view = ft.Column(
        key="cards",
        spacing=10,
        expand=True,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(spacing=6, tight=True, controls=[btn_all, btn_due, btn_mastered]),
                ],
            ),
            ft.Row(controls=[search_field]),
            ft.Container(
                expand=True,
                border_radius=ft.BorderRadius.all(12),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                padding=8,
                content=cards_column,
            ),
        ],
    )

    body_switcher = ft.AnimatedSwitcher(
        content=loading_view,
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=250,
        expand=True,
    )

    dlg = ft.AlertDialog(
        modal=False,
        shape=ft.RoundedRectangleBorder(radius=18),
        bgcolor=ft.Colors.SURFACE,
        on_dismiss=_close,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=10,
                    expand=True,
                    controls=[
                        ft.Container(
                            width=36, height=36,
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=20, color=ft.Colors.PRIMARY),
                        ),
                        ft.Column(
                            spacing=1,
                            expand=True,
                            tight=True,
                            controls=[
                                ft.Text(f"Deck: {mtitle}", size=15, weight=ft.FontWeight.W_800, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text("Full Q&A Deck", size=10.5, color=ft.Colors.GREY_500),
                            ],
                        ),
                    ],
                ),
                ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        header_count_badge,
                        ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, icon_color=ft.Colors.GREY_500, on_click=_close),
                    ],
                ),
            ],
        ),
        content=ft.Container(
            width=dialog_w,
            height=dialog_h,
            content=body_switcher,
        ),
        actions=[],
    )

    page.overlay.append(dlg)
    dlg.open = True
    page.update()

    async def _fetch_and_show():
        if mid:
            try:
                # Fetch ALL cards for this particular material, regardless of whether they are due
                fetched = await asyncio.wait_for(get_all_cards(token, [mid]), timeout=15)
                cards_state["all"] = fetched or []
            except Exception as ex:
                print(f"[DECK INSPECTOR] Error fetching all cards for material {mid}: {ex}")
                cards_state["all"] = list(preloaded_cards or [])
        elif preloaded_cards is not None:
            cards_state["all"] = list(preloaded_cards)

        cards_state["loading"] = False
        _render_cards()

    page.run_task(_fetch_and_show)
