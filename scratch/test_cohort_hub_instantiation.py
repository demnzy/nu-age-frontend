import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath("."))
import flet as ft
from unittest.mock import AsyncMock, MagicMock

# Mock mock page
class MockSharedPrefs:
    async def get(self, key):
        return "mock_token"
    async def set(self, key, val):
        pass

class MockWindow:
    width = 1200
    height = 900
    full_screen = False

class MockPage:
    def __init__(self):
        self.width = 1200
        self.height = 900
        self.window = MockWindow()
        self.shared_preferences = MockSharedPrefs()
        self.overlay = []
        self.controls = []
        self.views = []
        self.route = "/cohorts/123"
        self.theme = None
        self.dark_theme = None
        self.theme_mode = ft.ThemeMode.LIGHT

    def update(self):
        pass

    def go(self, route):
        self.route = route

    def run_task(self, fn, *args, **kwargs):
        # Synchronously or immediately don't block
        pass

    def show_dialog(self, dlg):
        pass

    def pop_dialog(self):
        pass

async def test_instantiations():
    page = MockPage()

    print("1. Testing cohort_page_view...")
    from src.cohort_page import cohort_page_view
    view = await cohort_page_view(page, cohort_id="cohort-123")
    assert isinstance(view, ft.View)
    assert len(view.controls) > 0
    print("cohort_page_view initialized successfully!")

    print("2. Testing cohort_exam_page_view...")
    from src.cohort_exam_view import cohort_exam_page_view
    exam_view = await cohort_exam_page_view(page, cohort_id="cohort-123", exam_id="exam-456")
    assert isinstance(exam_view, ft.View)
    print("cohort_exam_page_view initialized successfully!")

    print("3. Testing build_learner_cohorts_view...")
    from src.components.learner_cohorts_hub import build_learner_cohorts_view
    hub_container = build_learner_cohorts_view(page, token="mock_token", initial_cohort_id="cohort-123")
    assert isinstance(hub_container, ft.Container)
    print("build_learner_cohorts_view initialized successfully!")

    print("4. Testing build_cohort_exam_view...")
    from src.components.cohort_exam_runner import build_cohort_exam_view
    exam_payload = {
        "exam": {
            "id": "exam-1",
            "title": "Full-Stack Final Exam",
            "duration_minutes": 45,
            "max_attempts": 3,
            "pass_percentage": 75.0,
            "instructions": "Answer all questions carefully.",
            "questions": [
                {
                    "id": "q1",
                    "question_text": "What is Python?",
                    "options": ["A snake", "A language", "Both"],
                    "question_type": "multiple_choice",
                }
            ]
        },
        "submission": {
            "id": "sub-1",
            "status": "in_progress",
            "current_attempt": 2,
            "max_attempts": 3,
            "answers": {},
            "remaining_seconds": 1800,
        },
        "remaining_seconds": 1800,
        "total_duration_minutes": 45,
        "total_duration_seconds": 2700,
        "max_attempts": 3,
        "completed_attempts": 1,
        "attempts_left": 2,
    }
    runner = build_cohort_exam_view(
        page,
        exam_payload,
        "org-1",
        "c-1",
        "exam-1",
        "mock_token",
        lambda: None,
    )
    assert isinstance(runner, ft.Container)
    print("build_cohort_exam_view initialized successfully!")

    print("\nALL INSTANTIATION TESTS PASSED CLEANLY!")

if __name__ == "__main__":
    asyncio.run(test_instantiations())
