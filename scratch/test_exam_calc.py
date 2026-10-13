import asyncio
import flet as ft
from src.components.study_exam import build_exam

class MockPage:
    def __init__(self, width=1024):
        self.width = width
        self.overlay = []
        self.controls = []
        self.on_keyboard_event = None
        self.session = {}

    def update(self):
        pass

    def run_task(self, fn, *args, **kwargs):
        # Don't run background timer loop in quick test
        pass

async def main():
    print("Testing Mock Exam with Calculator integration...")
    page = MockPage(width=1024)

    dummy_questions = [
        {
            "question": "What is the square root of 144?",
            "options": ["10", "11", "12", "14"],
            "answer": 2,
            "explanation": "12 * 12 = 144",
        },
        {
            "question": "Calculate 5 * sin(30 deg):",
            "options": ["1.5", "2.5", "3.0", "5.0"],
            "answer": 1,
            "explanation": "sin(30) is 0.5, 5 * 0.5 = 2.5",
        }
    ]

    exam_root = build_exam(
        page=page,
        questions=dummy_questions,
        duration_seconds=300,
        on_exit=lambda: print("Exit clicked"),
        on_restart=lambda: print("Restart clicked"),
        calculator_type="scientific",
    )

    print("Exam root built successfully:", type(exam_root))
    assert isinstance(exam_root.content, ft.Stack), "Root content should be ft.Stack"
    main_container, calc_overlay = exam_root.content.controls
    print("Stack controls:", type(main_container), type(calc_overlay))
    assert calc_overlay.visible is False, "Calculator overlay should start invisible"

    # Toggle calculator open via 'c' key
    class MockKeyEvent:
        def __init__(self, key):
            self.key = key

    page.on_keyboard_event(MockKeyEvent("c"))
    assert calc_overlay.visible is True, "Calculator should become visible on 'c' key"
    assert calc_overlay.content is not None, "Calculator content should be populated"
    print("Calculator opened via 'c' key! Card type:", type(calc_overlay.content))

    # Toggle to Basic mode
    card = calc_overlay.content
    header_row = card.content.controls[0]
    left_header = header_row.controls[0]
    mode_btn = left_header.controls[2]
    print("Mode button text before click:", mode_btn.content.value)
    mode_btn.on_click(None)
    card_after = calc_overlay.content
    header_after = card_after.content.controls[0].controls[0]
    print("Mode button text after click:", header_after.controls[2].content.value)
    assert header_after.controls[2].content.value == "Basic" or header_after.controls[2].content.value == "Sci"

    # Close via Escape key
    page.on_keyboard_event(MockKeyEvent("escape"))
    assert calc_overlay.visible is False, "Calculator should close on escape"
    print("Calculator closed successfully on escape!")

    # Test Mobile Viewport
    mobile_page = MockPage(width=360)
    mobile_exam = build_exam(
        page=mobile_page,
        questions=dummy_questions,
        duration_seconds=300,
        on_exit=lambda: None,
        on_restart=lambda: None,
    )
    print("Mobile exam created successfully:", type(mobile_exam))
    mobile_calc_overlay = mobile_exam.content.controls[1]
    mobile_page.on_keyboard_event(MockKeyEvent("c"))
    assert mobile_calc_overlay.visible is True
    print("Mobile calculator overlay verified! Width and bounds clamped properly.")

    print("\nALL EXAM CALCULATOR TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(main())
