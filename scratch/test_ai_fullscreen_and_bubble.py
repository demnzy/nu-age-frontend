import sys, os
sys.path.insert(0, os.path.abspath("."))
import asyncio
import flet as ft
from src.components.need_help_drawer import build_need_help_drawer

async def verify():
    print("--- Verifying AI Fullscreen & User Bubble Wrap ---")

    class MockPage:
        width = 390
        height = 844
        theme_mode = ft.ThemeMode.LIGHT
        def update(self): pass
        def run_task(self, fn, *args): pass

    mp = MockPage()

    # 1. Build mobile drawer
    drawer = build_need_help_drawer(
        page=mp,
        course_id="c_test",
        course_title="Test Course",
        lesson_data={"title": "Introduction to AI", "content": "Content here..."},
        module_title="Module 1",
    )

    main_win = drawer.content.controls[1]
    col = main_win.content
    header = col.controls[0]
    right_controls = header.controls[1]
    fullscreen_btn = right_controls.controls[0]
    close_btn = right_controls.controls[1]

    # Verify initial state
    print(f"Initial main_win.height: {main_win.height}")
    assert fullscreen_btn.visible == True, "Fullscreen button should be visible on mobile!"
    assert fullscreen_btn.icon == ft.Icons.FULLSCREEN_ROUNDED, "Initial icon should be FULLSCREEN_ROUNDED!"
    print("1. Fullscreen button initialized on mobile header: PASS")

    # 2. Toggle to Full Screen
    fullscreen_btn.on_click(None)
    print(f"Expanded main_win.height: {main_win.height} (expand: {main_win.expand}, drawer.top: {drawer.top})")
    assert main_win.expand is True, "Expected main_win.expand to be True"
    assert drawer.top == 8, f"Expected drawer.top == 8, got {drawer.top}"
    assert drawer.bottom == 8, f"Expected drawer.bottom == 8, got {drawer.bottom}"
    assert fullscreen_btn.icon == ft.Icons.FULLSCREEN_EXIT_ROUNDED, "Icon should be FULLSCREEN_EXIT_ROUNDED!"
    print("2. Grow to full screen overlay within screen bounds: PASS")

    # 3. Minimize back to normal size
    fullscreen_btn.on_click(None)
    print(f"Restored main_win.height: {main_win.height}")
    expected_normal_h = max(240, min(int(844 * 0.49), 420))
    assert main_win.height == expected_normal_h, f"Expected {expected_normal_h} but got {main_win.height}"
    assert fullscreen_btn.icon == ft.Icons.FULLSCREEN_ROUNDED, "Icon should restore to FULLSCREEN_ROUNDED!"
    print("3. Minimise back to normal half-screen size: PASS")

    # 4. Verify Long User Message Bubble Constraints
    messages_col = col.controls[3].content
    input_field = col.controls[5].controls[0]
    send_btn = col.controls[5].controls[1]

    long_text = "This is an extremely long user query sent on a mobile device that contains lots of detailed explanations and questions that would previously stretch the row infinitely wide and bleed off the screen completely!"
    input_field.value = long_text
    send_btn.on_click(None)

    # Check the newly added bubble
    user_bubble_row = messages_col.controls[-1]
    assert isinstance(user_bubble_row, ft.Row), "User bubble should be an ft.Row"
    user_container = user_bubble_row.controls[0]
    assert user_container.width is not None, "Long user bubble must have bounded width to prevent mobile bleed!"
    print(f"User bubble width: {user_container.width} (Mobile screen width: 390)")
    assert user_container.width < 390, "Bubble width must be strictly less than phone width!"
    assert user_container.width <= 390 * 0.82, "Bubble width should comfortably occupy around 80% of width!"
    user_text_control = user_container.content
    assert user_text_control.no_wrap == False, "Text no_wrap should be False so it wraps lines!"
    print("4. Long user message wraps and is bounded without bleeding off screen: PASS")

    print("\nALL FULLSCREEN & USER BUBBLE TESTS PASSED SUCCESSFULLY (100%)!")

if __name__ == "__main__":
    asyncio.run(verify())
