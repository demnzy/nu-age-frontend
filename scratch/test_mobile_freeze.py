import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import flet as ft
from src.course_page import course_learner_view

class MockPage:
    def __init__(self, width=390, height=800):
        self.width = width
        self.height = height
        self.controls = []
        self.overlay = []
        self.theme_mode = ft.ThemeMode.LIGHT
        self.session = MockSession()
        self.clipboard = ""
        self.tasks = []

    def update(self):
        print("Page updated successfully")

    def run_task(self, func, *args, **kwargs):
        self.tasks.append(func)

    def set_clipboard(self, val):
        self.clipboard = val

class MockSession:
    def __init__(self):
        self.store = {"token": "mock_test_token"}

async def test_mobile():
    page = MockPage(width=390, height=800)
    mock_data = {
        "course_title": "Test Course",
        "modules": [
            {
                "id": "m1",
                "title": "Module 1",
                "lessons": [
                    {
                        "id": "l1",
                        "title": "Lesson 1",
                        "type": "text",
                        "content": {"text": "Hello world"},
                        "is_done": False,
                        "is_unlocked": True,
                    }
                ]
            }
        ]
    }
    async def mock_fetch(cid):
        return mock_data

    view = await course_learner_view(page, "test_course", fetch_course_data=mock_fetch)
    print("View created:", type(view))

    # Execute fetch_initial_data
    if page.tasks:
        for t in page.tasks:
            try:
                res = t()
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                print("Task error:", e)

    print("Now finding and testing menu_button and need_help_btn...")
    # Find menu_button and toggle_sidebar
    appbar = view.appbar
    menu_btn = appbar.actions[2]
    print("Clicking menu_button (toggle_sidebar)...")
    menu_btn.on_click(None)
    print("Sidebar toggled without exception!")

    # Find tab_bar and ai_btn
    body_host = view.controls[0].content.content
    main_cont = body_host.content.controls[0].content
    col = main_cont.content
    tab_bar = col.content.controls[0]
    ai_btn = tab_bar.content.controls[-1]
    print("Found ai_btn:", type(ai_btn), "tooltip:", getattr(ai_btn, "tooltip", None))
    print("Clicking ai_btn...")
    ai_btn.on_click(None)
    await asyncio.sleep(0.1)
    drawer_socket = body_host.content.controls[3]
    sidebar_container = body_host.content.controls[2]

    print("Testing closing ai_btn...")
    ai_btn.on_click(None)
    await asyncio.sleep(0.05)
    assert drawer_socket.visible is False
    print("AI assistant closed cleanly on mobile!")

    print("Testing closing syllabus...")
    menu_btn.on_click(None)
    assert sidebar_container.visible is False
    print("Syllabus closed cleanly on mobile!")

    print("Testing reopening syllabus...")
    menu_btn.on_click(None)
    assert sidebar_container.visible is True
    print("Syllabus reopened cleanly on mobile!")

asyncio.run(test_mobile())
