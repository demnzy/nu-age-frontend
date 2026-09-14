import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import flet as ft
from unittest.mock import MagicMock

def test_skeleton_screens():
    print("Testing new skeleton screens for Course Engine View and Learn Tab...")

    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 1200
    mock_page.height = 800
    mock_page.theme_mode = ft.ThemeMode.LIGHT

    # Helper shimmer box
    def shimmer_box(radius=12, height=None, width=None, expand=False):
        box = ft.Container(
            expand=True if ((height is None and width is None) or expand) else None,
            height=height,
            width=width,
            border_radius=radius,
            bgcolor=ft.Colors.OUTLINE,
            opacity=0.35,
        )
        box.data = "shimmer_box"
        return box

    def _collect_boxes(control):
        boxes = []
        def walk(c):
            if isinstance(c, ft.Container):
                if getattr(c, "data", None) == "shimmer_box":
                    boxes.append(c)
                if c.content is not None:
                    walk(c.content)
            elif isinstance(c, (ft.Row, ft.Column, ft.ResponsiveRow, ft.ListView)):
                for child in (c.controls or []):
                    walk(child)
        walk(control)
        return boxes

    def _bottom_navbar():
        def nav_item_skel():
            return ft.Column(
                [
                    shimmer_box(radius=6, width=22, height=22),
                    shimmer_box(radius=3, width=32, height=7),
                ],
                spacing=3,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        return ft.Container(
            height=60,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE))),
            border_radius=ft.BorderRadius.only(top_left=16, top_right=16),
            padding=ft.Padding.symmetric(horizontal=16, vertical=6),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[nav_item_skel() for _ in range(5)],
            ),
        )

    # Test Learn Tab Skeleton
    def _layout_course_grid():
        header_title = shimmer_box(radius=6, height=24, width=90)
        header_subtitle = shimmer_box(radius=4, height=12, width=240)
        tabs_row = ft.Row(
            spacing=8,
            controls=[
                shimmer_box(radius=6, height=28, width=105),
                shimmer_box(radius=6, height=28, width=90),
                shimmer_box(radius=6, height=28, width=85),
                shimmer_box(radius=6, height=28, width=95),
            ],
            scroll=ft.ScrollMode.AUTO,
        )
        header_container = ft.Container(
            padding=ft.Padding.only(left=16, right=16, top=14, bottom=12),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Column(spacing=4, controls=[header_title, header_subtitle]),
                    tabs_row,
                ],
            ),
        )
        search_box = shimmer_box(radius=10, height=42, expand=True)
        filter_chips = ft.Row(
            spacing=8,
            controls=[
                shimmer_box(radius=8, height=30, width=105),
                shimmer_box(radius=8, height=30, width=110),
            ],
        )
        search_filter_container = ft.Container(
            padding=ft.Padding.only(left=16, right=16, top=10, bottom=6),
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row([search_box]),
                    filter_chips,
                ],
            ),
        )
        def card_skeleton():
            category_badge = shimmer_box(radius=10, height=18, width=65)
            title_line = shimmer_box(radius=6, height=15, width=140)
            desc_line1 = shimmer_box(radius=4, height=10, expand=True)
            desc_line2 = shimmer_box(radius=4, height=10, width=130)
            meta_chips = ft.Row(
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    shimmer_box(radius=4, height=10, width=55),
                    shimmer_box(radius=1.5, width=3, height=3),
                    shimmer_box(radius=4, height=10, width=45),
                ],
            )
            left_col = ft.Column(
                expand=True,
                spacing=6,
                controls=[category_badge, title_line, desc_line1, desc_line2, meta_chips],
            )
            vertical_divider = ft.Container(
                width=1,
                height=75,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                margin=ft.Margin.symmetric(horizontal=8),
            )
            avatar_box = shimmer_box(radius=18, width=80, height=80)
            top_row = ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[left_col, vertical_divider, avatar_box],
            )
            progress_row = ft.Column(
                spacing=4,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            shimmer_box(radius=4, height=10, width=45),
                            shimmer_box(radius=4, height=10, width=25),
                        ],
                    ),
                    shimmer_box(radius=2, height=4, expand=True),
                ],
            )
            top_body = ft.Container(
                padding=ft.Padding.only(left=16, right=16, top=14, bottom=12),
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                content=ft.Column(
                    spacing=10,
                    controls=[top_row, progress_row],
                ),
            )
            footer_bar = ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                border_radius=ft.BorderRadius.only(bottom_left=22, bottom_right=22),
                border=ft.Border.only(
                    top=ft.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))
                ),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        shimmer_box(radius=4, height=11, width=100),
                        shimmer_box(radius=16, height=28, width=82),
                    ],
                ),
            )
            return ft.Container(
                col={"xs": 12, "sm": 6},
                border_radius=ft.BorderRadius.all(22),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[top_body, footer_bar],
                ),
            )

        cards_grid = ft.ResponsiveRow(
            spacing=14,
            run_spacing=14,
            controls=[card_skeleton() for _ in range(4)],
        )
        scrollable_content = ft.ListView(
            expand=True,
            padding=ft.Padding.only(left=16, right=16, top=4, bottom=12),
            controls=[cards_grid],
        )
        return ft.Column(
            controls=[
                header_container,
                search_filter_container,
                scrollable_content,
                _bottom_navbar(),
            ],
            spacing=0,
            expand=True,
        )

    # Test Course Engine View Skeleton
    def _layout_course_reader(page=mock_page):
        appbar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            shimmer_box(radius=8, width=32, height=32),
                            ft.Column(
                                spacing=3,
                                tight=True,
                                controls=[
                                    shimmer_box(radius=5, height=15, width=170),
                                    shimmer_box(radius=4, height=11, width=120),
                                ],
                            ),
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            shimmer_box(radius=999, height=28, width=64),
                            shimmer_box(radius=8, height=30, width=78),
                        ],
                    ),
                ],
            ),
        )

        header_card = ft.Container(
            padding=ft.Padding.symmetric(horizontal=20, vertical=16),
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Column(
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            shimmer_box(radius=4, height=12, width=130),
                            shimmer_box(radius=1.5, width=3, height=3),
                            shimmer_box(radius=999, height=20, width=80),
                            shimmer_box(radius=4, height=11, width=75),
                        ],
                    ),
                    shimmer_box(radius=6, height=22, width=300),
                    shimmer_box(radius=2, height=3.5, expand=True),
                ],
            ),
        )

        media_block = shimmer_box(radius=12, height=190, expand=True)

        content_card = ft.Container(
            padding=ft.Padding.all(20),
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
            content=ft.Column(
                spacing=12,
                controls=[
                    shimmer_box(radius=5, height=16, width=210),
                    shimmer_box(radius=4, height=11, expand=True),
                    shimmer_box(radius=4, height=11, expand=True),
                    shimmer_box(radius=4, height=11, width=380),
                    ft.Container(height=4),
                    ft.Container(
                        padding=ft.Padding.all(14),
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)),
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                shimmer_box(radius=4, height=12, width=120),
                                shimmer_box(radius=4, height=10, expand=True),
                            ],
                        ),
                    ),
                    ft.Container(height=4),
                    shimmer_box(radius=4, height=11, expand=True),
                    shimmer_box(radius=4, height=11, width=280),
                ],
            ),
        )

        action_footer = ft.Container(
            padding=ft.Padding.symmetric(horizontal=20, vertical=14),
            border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    shimmer_box(radius=8, height=42, width=110),
                    shimmer_box(radius=8, height=42, width=180),
                ],
            ),
        )

        def sidebar_skel():
            sidebar_header = ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    shimmer_box(radius=5, height=14, width=110),
                    shimmer_box(radius=6, width=18, height=18),
                ],
            )
            progress_strip = ft.Column(
                spacing=4,
                controls=[
                    shimmer_box(radius=4, height=10, width=80),
                    shimmer_box(radius=2, height=4, expand=True),
                ],
            )
            def mod_item(num_lessons=3, is_active=False):
                return ft.Container(
                    padding=ft.Padding.all(10),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.06 if is_active else 0.02, ft.Colors.ON_SURFACE),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            shimmer_box(radius=4, height=13, width=130),
                            ft.Column(
                                spacing=4,
                                controls=[
                                    shimmer_box(radius=4, height=10, width=150)
                                    for _ in range(num_lessons)
                                ],
                            ),
                        ],
                    ),
                )
            return ft.Container(
                width=270,
                padding=ft.Padding.all(14),
                border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        sidebar_header,
                        progress_strip,
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                        mod_item(3, is_active=True),
                        mod_item(2, is_active=False),
                        mod_item(2, is_active=False),
                    ],
                ),
            )

        is_desktop = (getattr(page, "width", None) or 0) >= 900
        main_scroll_pane = ft.ListView(
            expand=True,
            padding=ft.Padding.symmetric(horizontal=20, vertical=14),
            controls=[
                header_card,
                ft.Container(height=14),
                media_block,
                ft.Container(height=14),
                content_card,
                ft.Container(height=14),
            ],
        )
        main_content_column = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                main_scroll_pane,
                action_footer,
            ],
        )
        if is_desktop:
            body = ft.Row(
                expand=True,
                spacing=0,
                controls=[
                    sidebar_skel(),
                    main_content_column,
                ],
            )
        else:
            body = main_content_column

        return ft.Column(
            controls=[
                appbar,
                ft.Container(content=body, expand=True),
            ],
            spacing=0,
            expand=True,
        )

    # Test Learn Tab
    learn_ctrl = _layout_course_grid()
    learn_boxes = _collect_boxes(learn_ctrl)
    print(f"[PASS] Learn Tab skeleton built with {len(learn_boxes)} shimmer boxes")
    assert len(learn_boxes) > 10, "Learn tab should have plenty of shimmer boxes"

    # Test Course Engine View (Desktop)
    mock_page.width = 1050
    reader_desktop = _layout_course_reader(mock_page)
    reader_desktop_boxes = _collect_boxes(reader_desktop)
    print(f"[PASS] Course Engine (Desktop) skeleton built with {len(reader_desktop_boxes)} shimmer boxes")
    assert len(reader_desktop_boxes) > 15, "Reader desktop should have plenty of shimmer boxes"

    # Test Course Engine View (Mobile)
    mock_page.width = 450
    reader_mobile = _layout_course_reader(mock_page)
    reader_mobile_boxes = _collect_boxes(reader_mobile)
    print(f"[PASS] Course Engine (Mobile) skeleton built with {len(reader_mobile_boxes)} shimmer boxes")
    assert len(reader_mobile_boxes) > 10, "Reader mobile should have plenty of shimmer boxes"

    print("\nAll skeleton screen tests passed successfully!")

if __name__ == "__main__":
    test_skeleton_screens()
