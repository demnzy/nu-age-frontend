import sys
sys.path.append(".")
import asyncio
import flet as ft
from unittest.mock import MagicMock

mock_page = MagicMock(spec=ft.Page)
mock_page.width = 1000
mock_page.height = 800
mock_page.overlay = []

state = {
    "materials": [
        {"id": "mat_1", "title": "Lecture 1: Intro to Psychology.pdf", "source_type": "pdf"},
        {"id": "mat_2", "title": "Midterm Revision Notes", "source_type": "text"},
        {"id": "mat_3", "title": "https://en.wikipedia.org/wiki/Cognition", "source_type": "url"},
    ],
    "selected_mat_ids": {"mat_1"},
    "mat_lim": 10,
    "mat_used": 3,
    "gen_lim": 5,
    "gen_used": 1,
    "generating_mats": set(),
    "poll_strikes": {},
}

def format_material_title(t):
    return t.replace(".pdf", "").replace("_", " ")

def _section_label(text: str) -> ft.Text:
    return ft.Text(
        text.upper(),
        size=10.5,
        weight=ft.FontWeight.W_800,
        color=ft.Colors.GREY_500,
    )

# Test full generate modal builder
def test_full_generate_modal():
    page = mock_page
    token = "test"
    mats = state["materials"]
    panel_selected = set(state["selected_mat_ids"])

    gen_remaining = (state["gen_lim"] - state["gen_used"]) if state["gen_lim"] is not None else None
    at_gen_limit  = state["gen_lim"] is not None and state["gen_used"] >= state["gen_lim"]

    cb_flashcards = ft.Checkbox(value=True, visible=False)
    cb_quiz       = ft.Checkbox(value=False, visible=False)
    cb_exam       = ft.Checkbox(value=False, visible=False)

    counter_chip_text = ft.Text(
        f"{len(panel_selected)} of {len(mats)} selected",
        size=10.5,
        weight=ft.FontWeight.W_700,
        color=ft.Colors.PRIMARY,
    )
    counter_chip = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
        border_radius=ft.BorderRadius.all(6),
        content=counter_chip_text,
    )

    tile_refs = {}

    def update_mat_tile(mid):
        if mid not in tile_refs:
            return
        is_sel = mid in panel_selected
        cont, icon_ctrl = tile_refs[mid]
        cont.bgcolor = ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_sel else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE)
        cont.border = ft.Border.all(
            1.5 if is_sel else 1,
            ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
        )
        icon_ctrl.name = ft.Icons.CHECK_CIRCLE_ROUNDED if is_sel else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED
        icon_ctrl.color = ft.Colors.PRIMARY if is_sel else ft.Colors.GREY_400

    def toggle_mat(mid):
        if mid in panel_selected:
            panel_selected.remove(mid)
        else:
            panel_selected.add(mid)
        update_mat_tile(mid)
        counter_chip_text.value = f"{len(panel_selected)} of {len(mats)} selected"

    def select_all_mats(e):
        for m in mats:
            panel_selected.add(m["id"])
            update_mat_tile(m["id"])
        counter_chip_text.value = f"{len(panel_selected)} of {len(mats)} selected"

    def clear_all_mats(e):
        panel_selected.clear()
        for m in mats:
            update_mat_tile(m["id"])
        counter_chip_text.value = f"0 of {len(mats)} selected"

    mat_cards = []
    for mat in mats:
        mid = mat["id"]
        is_sel = mid in panel_selected
        raw_title = mat.get("title", "Untitled")
        display_title = format_material_title(raw_title)
        stype = (mat.get("source_type") or "text").lower()

        if "pdf" in stype or raw_title.lower().endswith(".pdf"):
            m_icon = ft.Icons.PICTURE_AS_PDF_ROUNDED
            m_color = ft.Colors.RED_400
            m_tag = "PDF"
        elif "url" in stype:
            m_icon = ft.Icons.LINK_ROUNDED
            m_color = ft.Colors.TEAL_400
            m_tag = "URL"
        else:
            m_icon = ft.Icons.DESCRIPTION_ROUNDED
            m_color = ft.Colors.BLUE_400
            m_tag = "NOTES"

        check_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE_ROUNDED if is_sel else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
            color=ft.Colors.PRIMARY if is_sel else ft.Colors.GREY_400,
            size=18,
        )

        tile = ft.Container(
            border_radius=ft.BorderRadius.all(10),
            padding=ft.Padding.symmetric(horizontal=12, vertical=9),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_sel else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
            border=ft.Border.all(
                1.5 if is_sel else 1,
                ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            ),
            ink=True,
            on_click=lambda _, target_id=mid: toggle_mat(target_id),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Container(
                                width=28, height=28,
                                bgcolor=ft.Colors.with_opacity(0.12, m_color),
                                border_radius=ft.BorderRadius.all(7),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(m_icon, color=m_color, size=15),
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                controls=[
                                    ft.Text(display_title, size=12, weight=ft.FontWeight.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text(m_tag, size=9, weight=ft.FontWeight.W_700, color=m_color),
                                ],
                            ),
                        ],
                    ),
                    check_icon,
                ],
            ),
        )
        tile_refs[mid] = (tile, check_icon)
        mat_cards.append(tile)

    def output_card(icon, title, desc, accent_color, cb_control):
        def toggle_output(e):
            cb_control.value = not cb_control.value
            update_card()

        def update_card():
            active = bool(cb_control.value)
            box.bgcolor = ft.Colors.with_opacity(0.08, accent_color) if active else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE)
            box.border = ft.Border.all(1.5 if active else 1, accent_color if active else ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))
            status_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED if active else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED
            status_icon.color = accent_color if active else ft.Colors.GREY_400

        status_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE_ROUNDED if cb_control.value else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
            color=accent_color if cb_control.value else ft.Colors.GREY_400,
            size=18,
        )

        box = ft.Container(
            border_radius=ft.BorderRadius.all(11),
            padding=ft.Padding.symmetric(horizontal=12, vertical=9),
            bgcolor=ft.Colors.with_opacity(0.08, accent_color) if cb_control.value else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1.5 if cb_control.value else 1, accent_color if cb_control.value else ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
            ink=True,
            on_click=toggle_output,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Container(
                                width=32, height=32,
                                bgcolor=ft.Colors.with_opacity(0.12, accent_color),
                                border_radius=ft.BorderRadius.all(8),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(icon, color=accent_color, size=17),
                            ),
                            ft.Column(
                                spacing=2,
                                tight=True,
                                controls=[
                                    ft.Text(title, size=12.5, weight=ft.FontWeight.W_700),
                                    ft.Text(desc, size=10.5, color=ft.Colors.GREY_500),
                                ],
                            ),
                        ],
                    ),
                    status_icon,
                ],
            ),
        )
        return box

    out_flashcards = output_card(ft.Icons.STYLE_ROUNDED, "Flashcards", "Spaced Repetition Deck (SM-2 active recall)", ft.Colors.PURPLE_400, cb_flashcards)
    out_quiz = output_card(ft.Icons.BOLT_ROUNDED, "Quick Quiz", "Targeted Drills with Instant Rationales", ft.Colors.TEAL_500, cb_quiz)
    out_exam = output_card(ft.Icons.TIMER_OUTLINED, "Exam Simulator", "Full-Length Timed Test with Score Breakdown", ft.Colors.ORANGE_500, cb_exam)

    modal = ft.AlertDialog(
        modal=False,
        shape=ft.RoundedRectangleBorder(radius=18),
        bgcolor=ft.Colors.SURFACE,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=10,
                    tight=True,
                    controls=[
                        ft.Container(
                            width=34, height=34,
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_400),
                            border_radius=ft.BorderRadius.all(10),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PURPLE_400, size=18),
                        ),
                        ft.Column(
                            spacing=1,
                            tight=True,
                            controls=[
                                ft.Text("Generate Study Content", size=15.5, weight=ft.FontWeight.W_700),
                                ft.Text("Create cards, quizzes & exams with AI", size=11, color=ft.Colors.GREY_500),
                            ],
                        ),
                    ],
                ),
                ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, icon_color=ft.Colors.GREY_400),
            ],
        ),
        content=ft.Container(
            width=460,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                height=480,
                spacing=14,
                controls=[
                    ft.Row([
                        _section_label("SELECT SOURCE MATERIALS"),
                        counter_chip,
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(
                        height=160,
                        border_radius=ft.BorderRadius.all(12),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                        padding=6,
                        content=ft.Column(
                            scroll=ft.ScrollMode.AUTO,
                            spacing=6,
                            controls=mat_cards,
                        ),
                    ),
                    _section_label("CHOOSE OUTPUT FORMATS"),
                    ft.Column(
                        spacing=8,
                        controls=[out_flashcards, out_quiz, out_exam],
                    ),
                ],
            ),
        ),
    )
    print("Full generate modal structure validated!")

test_full_generate_modal()
