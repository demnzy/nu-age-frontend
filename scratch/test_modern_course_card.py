import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import flet as ft
from unittest.mock import MagicMock
from src.components.course_card import get_course_card
from src.components.enrolled_card import get_enrolled_card
from src.components.course_card_theme import get_card_palette, get_course_module_meta


def test_course_cards():
    print("Testing course card and enrolled card instantiation...")

    mock_page = MagicMock(spec=ft.Page)
    mock_page.web = False
    mock_page.theme_mode = ft.ThemeMode.LIGHT
    mock_page.platform_brightness = ft.Brightness.LIGHT

    # 4 Test courses matching the 4 reference cards
    test_cases = [
        {
            "title": "UI/UX Designer",
            "category": "Design",
            "author": "Sarah Jenkins",
            "desc": "Master the principles of user interface and user experience design.",
            "modules": [{"id": i} for i in range(16)],
            "progress": 72.0,
            "image_url": None,
        },
        {
            "title": "QA Engineer",
            "category": "Quality Assurance",
            "author": "David Lee",
            "desc": "Learn the fundamentals of quality assurance and software testing.",
            "modules": [{"id": i} for i in range(12)],
            "progress": 0.0,
            "image_url": "https://example.com/qa.png",
        },
        {
            "title": "Recruiter",
            "category": "Human Resources",
            "author": "Marcus Brown",
            "desc": "Understand the hiring process, talent acquisition strategies.",
            "modules": None,
            "progress": 25.0,
            "image_url": None,
        },
        {
            "title": "Front-end Developer",
            "category": "Web Development",
            "author": "Emily Chen",
            "desc": "Build stunning and responsive websites using modern front-end technologies.",
            "modules": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}],
            "progress": 100.0,
            "image_url": None,
        },
    ]

    for tc in test_cases:
        # Available course card
        avail_card = get_course_card(
            course_title=tc["title"],
            course_category=tc["category"],
            course_author=tc["author"],
            image_url=tc["image_url"],
            created_at="11/09/2026",
            description=tc["desc"],
            modules=tc["modules"],
            page=mock_page,
            on_view_click=lambda _: print("Clicked view"),
        )
        assert isinstance(avail_card, ft.Container), f"Available card failed for {tc['title']}"

        # Enrolled course card
        enrolled_card = get_enrolled_card(
            page=mock_page,
            course_id=f"cid_{tc['title']}",
            course_title=tc["title"],
            course_category=tc["category"],
            course_author=tc["author"],
            image_url=tc["image_url"],
            progress=tc["progress"],
            rating=4.9,
            description=tc["desc"],
            modules=tc["modules"],
        )
        assert isinstance(enrolled_card, ft.Container), f"Enrolled card failed for {tc['title']}"

        tot, comp, t_str = get_course_module_meta(tc["modules"], tc["title"], tc["progress"])
        print(f"[PASS] {tc['title']}: {comp}/{tot} modules (~{t_str}), progress={tc['progress']}%")

    print("\nAll 4 pastel card configurations instantiated successfully without error!")


if __name__ == "__main__":
    test_course_cards()
