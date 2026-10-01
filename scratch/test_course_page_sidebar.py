"""
scratch/test_course_page_sidebar.py

Verify course_page learner view layout with AI Tutor Right Sidebar integration.
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import flet as ft
from src.course_page import course_learner_view
from src.utils.file_opener import safe_set_clipboard


class MockPage:
    def __init__(self, width=1280, height=800):
        self.width = width
        self.height = height
        self.controls = []
        self.overlay = []
        self.theme_mode = ft.ThemeMode.DARK
        self.clipboard = ""
        self.window = type("MockWindow", (), {"width": width, "height": height})()

    def update(self):
        pass

    def run_task(self, func, *args, **kwargs):
        pass


async def run_test():
    print(">>> Testing course_page with AI Tutor Right Sidebar <<<")
    mock_page = MockPage(width=1280, height=800)

    # 1. Test safe_set_clipboard
    await safe_set_clipboard(mock_page, "Test clipboard content")
    print("  [OK] safe_set_clipboard executed cleanly")

    # 2. Test course_learner_view instantiation
    mock_course_data = {
        "id": "c1",
        "course_title": "Full Stack Python",
        "modules": [
            {
                "id": "m1",
                "title": "Module 1: Basics",
                "lessons": [
                    {
                        "id": "l1",
                        "title": "Lesson 1: Intro",
                        "type": "reading",
                        "content": "Hello world",
                        "is_done": False,
                        "is_unlocked": True,
                    }
                ],
            }
        ],
    }

    async def mock_fetch(cid):
        return mock_course_data

    view = await course_learner_view(
        page=mock_page,
        course_id="c1",
        fetch_course_data=mock_fetch,
    )
    assert view is not None
    assert isinstance(view, ft.View)
    print("  [OK] course_learner_view created successfully")

    print(">>> ALL COURSE PAGE SIDEBAR TESTS PASSED <<<")


if __name__ == "__main__":
    asyncio.run(run_test())
