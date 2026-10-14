import sys
sys.path.insert(0, ".")
import asyncio
import flet as ft
from unittest.mock import MagicMock
from src.components.cbt_exam_engine import CBTExamEngine

def test_cbt_exam_engine():
    mock_page = MagicMock()
    mock_page.width = 1024
    mock_page.height = 768
    mock_page.overlay = []
    mock_page.on_keyboard_event = None

    sample_questions = [
        {
            "id": "q1",
            "question": "Solve for $x$: $2x + 4 = 10$",
            "options": ["$x = 2$", "$x = 3$", "$x = 4$", "$x = 5$"],
            "answer": 1,
            "explanation": r"Subtract 4 from both sides: $2x = 6 \implies x = 3$.",
            "image_url": "https://example.com/graph.png",
            "subject": "Mathematics",
            "exam_type": "SAT"
        },
        {
            "id": "q2",
            "question": "What is the speed of light?",
            "options": ["$3 \\times 10^8$ m/s", "$3 \\times 10^6$ m/s", "150 m/s"],
            "answer": 0,
            "explanation": "Constant $c = 3 \\times 10^8$ m/s.",
            "subject": "Physics",
            "exam_type": "SAT"
        }
    ]

    engine = CBTExamEngine(
        page=mock_page,
        questions=sample_questions,
        duration_seconds=1800,
        exam_title="SAT Quantitative Assessment",
        exam_type="SAT",
    )

    # 1. Build UI
    root = engine.root
    assert isinstance(root, ft.Control), "engine.root is not a Flet control"
    print("UI built successfully!")

    # 2. Keyboard shortcut test: N should advance question
    assert engine.active_index == 0
    key_event = MagicMock()
    key_event.key = "N"
    engine._on_key_event(key_event)
    assert engine.active_index == 1, f"Expected active_index 1, got {engine.active_index}"
    print("Key N advanced index to 1 successfully!")

    # 3. Key P should go back to question 0
    key_event.key = "p"
    engine._on_key_event(key_event)
    assert engine.active_index == 0, f"Expected active_index 0, got {engine.active_index}"
    print("Key P moved index back to 0 successfully!")

    # 4. Key B should select option index 1
    key_event.key = "B"
    engine._on_key_event(key_event)
    assert engine.answers[0] == 1, f"Expected answer 1, got {engine.answers.get(0)}"
    print("Key B selected option 1 successfully!")

    # 5. Image lightbox modal test
    engine._show_image_lightbox("https://example.com/graph.png")
    assert len(mock_page.overlay) > 0, "Lightbox dialog not added to overlay"
    dlg = mock_page.overlay[-1]
    assert isinstance(dlg, ft.AlertDialog), "Lightbox is not an AlertDialog"
    assert dlg.open is True, "Lightbox dialog not opened"
    print("Image lightbox modal verified successfully!")

    # 6. Teardown keyboard handler
    engine._restore_keyboard_handler()
    print("Keyboard handler restored cleanly!")

    print("ALL CBT EXAM ENGINE TESTS PASSED!")

if __name__ == "__main__":
    test_cbt_exam_engine()
