import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

import flet as ft

class MockPage:
    def __init__(self):
        self.route = "/cohorts/cohort-101/exams/exam-202"
        self.views = []
        self.overlay = []
        self.controls = []
        self.width = 1200
        self.height = 800
        self.theme_mode = ft.ThemeMode.DARK
        self.session = MagicMock()
        self.session.store = {"current_user": {"id": "user-1", "name": "Test Learner", "role": "learner"}}
        self.shared_preferences = AsyncMock()
        self.shared_preferences.get = AsyncMock(return_value="mock_token")
        self.shared_preferences.set = AsyncMock()
        self.shared_preferences.remove = AsyncMock()
        self.window = MagicMock()
        self.window.width = 1200
        self.window.height = 800
        self.window.full_screen = False
        self.window.prevent_close = False
        self.window.on_event = None
        self.on_keyboard_event = None
        self.dialog = None
        self.tasks = []

    def update(self):
        pass

    def run_task(self, coro_fn, *args, **kwargs):
        task = asyncio.create_task(coro_fn(*args, **kwargs))
        self.tasks.append(task)
        return task

    def go(self, route):
        self.route = route

async def run_tests():
    print("--- 1. Testing Route Matching & Exam Route Filter ---")
    def is_shell_route_logic(route: str) -> bool:
        if not route:
            return False
        clean = route.split("?")[0]
        if clean in ("/", "/login", "/signup", "/offline"):
            return False
        if clean.startswith("/cohorts/") and "/exams/" in clean:
            return False
        return True

    assert not is_shell_route_logic("/cohorts/c-1/exams/e-2"), "Exam route must NOT be considered a shell route"
    assert is_shell_route_logic("/cohorts"), "Cohorts list should be a shell route"
    
    raw_route = "/cohorts/c-123/exams/e-456?org_id=org-789"
    clean_route = raw_route.split("?")[0]
    troute = ft.TemplateRoute(clean_route)
    matched = troute.match("/cohorts/:cohort_id/exams/:exam_id")
    assert matched, "TemplateRoute must match /cohorts/:cohort_id/exams/:exam_id"
    assert troute.cohort_id == "c-123"
    assert troute.exam_id == "e-456"
    print("   [PASS] Route parsing and shell route exclusions verified.")

    print("--- 2. Testing build_cohort_exam_view Control Instantiation ---")
    from src.components.cohort_exam_runner import build_cohort_exam_view
    page = MockPage()

    dummy_payload = {
        "exam": {
            "title": "Final Assessment",
            "duration_minutes": 30,
            "pass_percentage": 70,
            "questions": [
                {
                    "id": "q-1",
                    "text": "What is Python?",
                    "options": ["Language", "Snake", "Both", "None"],
                    "points": 5,
                    "chosen_index": 0
                },
                {
                    "id": "q-2",
                    "text": "What is 2 + 2?",
                    "options": ["3", "4", "5", "6"],
                    "points": 5,
                    "chosen_index": None
                }
            ]
        },
        "submission_id": "sub-123",
        "remaining_seconds": 1500
    }

    exam_component = build_cohort_exam_view(
        page=page,
        exam_payload=dummy_payload,
        org_id="org-789",
        cohort_id="c-123",
        exam_id="e-456",
        token="token-abc",
        on_exit=lambda: print("Exit callback invoked"),
    )
    assert isinstance(exam_component, ft.Container), "build_cohort_exam_view should return ft.Container"
    print("   [PASS] build_cohort_exam_view instantiated successfully.")

    print("--- 3. Testing cohort_exam_page_view Full Page Instantiation ---")
    from src.cohort_exam_view import cohort_exam_page_view
    view = await cohort_exam_page_view(page, cohort_id="c-123", exam_id="e-456", org_id="org-789")
    assert isinstance(view, ft.View), "cohort_exam_page_view should return ft.View"
    assert view.route == "/cohorts/c-123/exams/e-456"
    assert len(view.controls) > 0
    print("   [PASS] cohort_exam_page_view instantiated successfully.")

    print("--- 4. Testing learner_cohorts_hub and cohorts_hub imports ---")
    import src.components.learner_cohorts_hub
    import src.components.cohorts_hub
    import src.cohort_page
    print("   [PASS] All cohort modules imported cleanly.")

    print("All tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
