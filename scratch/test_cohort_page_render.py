import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath("."))
import flet as ft

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
        pass

    def show_dialog(self, dlg):
        pass

    def pop_dialog(self):
        pass

async def test_full_cohort_page_render():
    from unittest.mock import patch
    from src.cohort_page import cohort_page_view

    page = MockPage()

    mock_backend_response = {
        "cohorts": [
            {
                "id": "c-101",
                "organisation_id": "org-01",
                "organisation_name": "Nu-Age Academy",
                "organisation_logo": None,
                "name": "Full-Stack Web Engineering 2026",
                "description": "Comprehensive engineering curriculum track.",
                "start_date": "2026-09-01T09:00:00Z",
                "end_date": "2026-12-31T18:00:00Z",
                "status": "active",
                "courses": [
                    {
                        "id": "crs-1",
                        "name": "FastAPI Masterclass",
                        "description": "Build high-performance REST APIs.",
                        "image_url": "https://example.com/fastapi.png",
                        "progress": 45.0,
                    },
                    {
                        "id": "crs-2",
                        "name": "Flet Desktop & Mobile Mastery",
                        "description": "Craft cross-platform reactive user interfaces.",
                        "image_url": None,
                        "progress": 100.0,
                    }
                ],
                "exams": [
                    {
                        "id": "ex-1",
                        "title": "Backend Architecture Midterm",
                        "description": "Timed assessment on async python and databases.",
                        "opens_at": "2026-09-20T09:00:00Z",
                        "closes_at": "2026-09-30T18:00:00Z",
                        "duration_minutes": 60,
                        "pass_percentage": 75.0,
                        "max_attempts": 2,
                        "completed_attempts": 1,
                        "attempts_left": 1,
                        "question_count": 25,
                        "status": "OPEN_NOW",
                        "is_completed": True,
                        "is_in_progress": False,
                        "submission": {
                            "score": 82.0,
                            "percentage": 82.0,
                            "passed": True,
                            "status": "graded",
                            "attempt_number": 1,
                        }
                    },
                    {
                        "id": "ex-2",
                        "title": "Cloud Deployment Final",
                        "description": "Docker and Kubernetes orchestrations.",
                        "opens_at": "2026-10-01T09:00:00Z",
                        "closes_at": "2026-10-05T18:00:00Z",
                        "duration_minutes": 90,
                        "pass_percentage": 80.0,
                        "max_attempts": 1,
                        "completed_attempts": 0,
                        "attempts_left": 1,
                        "question_count": 30,
                        "status": "SCHEDULED",
                        "is_completed": False,
                        "is_in_progress": False,
                        "submission": None,
                    }
                ]
            }
        ],
        "active_urgent_exams": [
            {
                "id": "ex-1",
                "title": "Backend Architecture Midterm",
                "closes_at": "2026-09-30T18:00:00Z",
                "status": "OPEN_NOW",
                "is_in_progress": False,
            }
        ]
    }

    with patch("src.cohort_page.get_learner_cohorts", return_value=mock_backend_response):
        view = await cohort_page_view(page, cohort_id="c-101")
        assert isinstance(view, ft.View)
        assert len(view.controls) > 0
        print("View successfully instantiated with populated cohort data!")

    print("ALL TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_full_cohort_page_render())
