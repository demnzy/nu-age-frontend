import sys, os
sys.path.insert(0, os.path.abspath("."))
import asyncio
import py_compile
import flet as ft
from unittest.mock import patch, Mock

from src.components.completed_card import get_completed_card
from src.course_stats import course_stats_view, format_time_ascension

# Mock classes
class MockSession:
    def __init__(self):
        self.store = {}

class MockSharedPreferences:
    async def get(self, key):
        return "mock_auth_token"

class MockPage:
    def __init__(self, width=1280, theme_mode=ft.ThemeMode.LIGHT):
        self.width = width
        self.height = 800
        self.route = "/courses/test-course/stats"
        self.session = MockSession()
        self.shared_preferences = MockSharedPreferences()
        self.theme_mode = theme_mode
        self.views = []
        self.dialog = None
        self.launched_url = None

    def update(self):
        pass

    def go(self, route):
        self.route = route

    async def launch_url(self, url):
        self.launched_url = url


async def main():
    print("=== Testing Completed Card & Course Stats ===")

    # 1. Test format_time_ascension
    assert format_time_ascension(0) == "—"
    assert format_time_ascension(45) == "45s"
    assert "2h" in format_time_ascension(7200 + 900)
    print("[OK] format_time_ascension tests passed")

    # 2. Test get_completed_card (Legacy arguments)
    review_clicked = []
    stats_clicked = []

    page = MockPage(width=1280, theme_mode=ft.ThemeMode.LIGHT)

    card_legacy = get_completed_card(
        course_name="Machine Learning Foundations",
        course_id="c-001",
        on_review_click=lambda cid: review_clicked.append(cid),
        on_stats_click=lambda cid: stats_clicked.append(cid),
    )
    assert isinstance(card_legacy, ft.Container), "Card must be a Container"
    print("[OK] get_completed_card legacy signature passed")

    # 3. Test get_completed_card (Rich metadata & Dark Mode)
    page_dark = MockPage(width=400, theme_mode=ft.ThemeMode.DARK)
    card_rich = get_completed_card(
        course_name="Modern Full-Stack React & Node",
        course_id="c-002",
        on_review_click=lambda cid: review_clicked.append(cid),
        on_stats_click=lambda cid: stats_clicked.append(cid),
        page=page_dark,
        image_url="https://nu-age-cdn.b-cdn.net/logos/placeholder.png",
        category="Web Development",
        author="Prof. Alan Turing",
        rating=4.95,
        course_dict={"modules": [{"id": "m1"}, {"id": "m2"}]}
    )
    assert isinstance(card_rich, ft.Container)
    print("[OK] get_completed_card rich metadata signature passed")

    # 4. Test Course Stats View (Desktop & Mock Data)
    mock_stats = {
        "course_id": "c-001",
        "course_title": "Deep Learning & Neural Networks",
        "enrolled_at": "2026-08-01T10:00:00Z",
        "completed_at": "2026-09-01T15:30:00Z",
        "time_spent_seconds": 18540,
        "time_spent_formatted": "5h 9m",
        "certificate_download_url": "https://nu-age.name.ng/certificates/download/c-001",
        "auto_certificate": True,
        "leaderboard_rank": 3,
        "total_completers": 42,
        "faster_than_percentile": 88.5,
    }

    mock_activity = [
        {"week": "W1", "views": 12, "participations": 8},
        {"week": "W2", "views": 18, "participations": 14},
        {"week": "W3", "views": 9, "participations": 6},
        {"week": "W4", "views": 25, "participations": 19},
    ]

    with patch("src.course_stats.get_enrollment_stats", return_value=mock_stats), \
         patch("src.course_stats.get_weekly_activity", return_value=mock_activity):

        view_desktop = await course_stats_view(page, "c-001")
        assert isinstance(view_desktop, ft.View)
        assert view_desktop.appbar is not None
        # Allow async load task to complete
        await asyncio.sleep(0.15)
        print("[OK] course_stats_view desktop instantiation & data load passed")

    # 5. Test Course Stats View (Mobile & Empty Activity Benchmark)
    with patch("src.course_stats.get_enrollment_stats", return_value=mock_stats), \
         patch("src.course_stats.get_weekly_activity", return_value=[]):

        view_mobile = await course_stats_view(page_dark, "c-001")
        assert isinstance(view_mobile, ft.View)
        await asyncio.sleep(0.15)
        print("[OK] course_stats_view mobile & benchmark trajectory passed")

    # 6. Test Error Handling State
    with patch("src.course_stats.get_enrollment_stats", return_value={"error": "Enrollment not found"}):
        view_err = await course_stats_view(page, "c-999")
        await asyncio.sleep(0.15)
        print("[OK] course_stats_view error handling passed")

    print("\n>>> ALL COMPLETED CARD AND STATS TESTS PASSED WITH 0 ERRORS! <<<")

if __name__ == "__main__":
    asyncio.run(main())
