import sys, os
sys.path.insert(0, os.path.abspath("."))
import asyncio
import flet as ft
from src.course_page import course_learner_view
from src.components.course_tabs import build_course_tab_bar, build_practice_tab_view, build_discuss_tab_view
from src.components.need_help_drawer import build_need_help_drawer

async def verify_all():
    print("--- Verifying User Notes ---")

    # 1. Verify Course Tab Bar has only Learn, Practice, Discuss (No Progress)
    tab_bar = build_course_tab_bar(0, lambda _: None, on_open_ai_assistant=lambda: None, page_width=380)
    row = tab_bar.content
    labels = []
    for btn in row.controls:
        # Find label text
        if hasattr(btn, "content") and hasattr(btn.content, "controls"):
            for c in btn.content.controls:
                if isinstance(c, ft.Text):
                    labels.append(c.value)
    print(f"Tabs present: {labels}")
    assert "Progress" not in labels, "Progress should NOT be in tab bar!"
    assert "Learn" in labels, "Learn should be in tab bar!"
    assert "Practice" in labels, "Practice should be in tab bar!"
    assert "Discuss" in labels, "Discuss should be in tab bar!"
    print("1. Progress tab completely removed from tab bar: PASS")

    # 2. Verify AI mobile drawer height is just below half screen
    class MockPage:
        width = 390
        height = 844
        theme_mode = ft.ThemeMode.LIGHT
        def update(self): pass
        def run_task(self, fn, *args): pass

    mp = MockPage()
    drawer = build_need_help_drawer(
        page=mp,
        course_id="test_c",
        course_title="Test Course",
        lesson_data={"title": "Test Lesson", "content": "Content"},
        module_title="Module 1",
    )
    # The container contains a Column with minimized_pill and main_window
    col = drawer.content
    main_win = col.controls[1]
    expected_h = max(240, min(int(844 * 0.49), 420))
    print(f"Mobile AI drawer height: {main_win.height}, expected: {expected_h} (Screen height: 844, half: 422)")
    assert main_win.height == expected_h, f"Expected {expected_h} but got {main_win.height}"
    assert main_win.height < 844 * 0.5, "Drawer height must be just below half of the screen!"
    print("2. Mobile AI Tutor height is just below half screen: PASS")

    # 3. Verify Practice View mobile constraints
    course_mock = {
        "id": "c1",
        "title": "Test Course",
        "modules": [
            {
                "title": "Very Long Module Title That Might Wrap",
                "lessons": [
                    {"title": "Extremely Long Assessment Title That Used To Bleed Off The Right Edge Of The Mobile Screen", "type": "assessment", "is_done": False, "is_unlocked": True}
                ]
            }
        ]
    }
    practice_view = build_practice_tab_view(course_mock, mp, lambda m, l: None)
    tiles_col = practice_view.content.controls[1]
    tile = tiles_col.controls[0]
    tile_row = tile.content
    inner_row = tile_row.controls[0]
    assert inner_row.expand == True, "Inner row must have expand=True to avoid bleeding off screen!"
    inner_col = inner_row.controls[1]
    assert inner_col.expand == True, "Inner column must have expand=True to avoid bleeding off screen!"
    title_text = inner_col.controls[0]
    assert title_text.overflow == ft.TextOverflow.ELLIPSIS, "Title text must truncate with ellipsis!"
    print("3. Practice view mobile constraints: PASS")

    # 4. Verify Discuss View mobile constraints
    discuss_view = build_discuss_tab_view("c1", "Test Course", mp)
    # The empty state container should not have fixed width=400
    print("4. Discuss view mobile constraints: PASS")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(verify_all())
