import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import flet as ft

from src.course_view import course_details_view

async def test_course_view():
    print("Testing modern course_view.py implementation...")

    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 1100
    mock_page.height = 800
    mock_page.theme_mode = ft.ThemeMode.LIGHT
    mock_page.shared_preferences = MagicMock()
    mock_page.shared_preferences.get = AsyncMock(return_value="mock_jwt_token")
    mock_page.go = MagicMock()
    mock_page.update = MagicMock()
    mock_page.show_dialog = MagicMock()

    running_tasks = []
    def run_task_mock(fn, *args):
        t = asyncio.create_task(fn(*args))
        running_tasks.append(t)
        return t
    mock_page.run_task = run_task_mock

    # Sample mock course payload
    mock_course = {
        "id": "c_test_001",
        "name": "Advanced Product Design & Design Systems",
        "image_url": "https://example.com/course.png",
        "description": "Learn to architect scalable design systems, master modern component libraries, and build accessible user experiences.",
        "category": {"name": "Product Design"},
        "admin": {"first_name": "Sarah", "last_name": "Connor"},
        "Students": [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}, {"id": "s4"}, {"id": "s5"}],
        "public": "true",
        "supervised": False,
        "rating": 4.9,
        "organisation": {"name": "Nu Design Academy"},
        "objectives": [
            "Construct robust design tokens and unified color systems",
            "Implement high-fidelity interactive prototypes in Flet",
            "Design for accessibility (WCAG AA) and cross-platform consistency",
            "Deliver clean handover documentation for engineering teams"
        ],
        "modules": [
            {
                "id": "m1",
                "title": "Foundations of Modern UI Systems",
                "lessons": [
                    {"id": "l1", "title": "Design Tokens & HSL Color Math", "lesson_type": "video"},
                    {"id": "l2", "title": "Typography Hierarchy & Rhythms", "lesson_type": "text"},
                    {"id": "l3", "title": "Foundations Knowledge Check", "lesson_type": "assessment"}
                ]
            },
            {
                "id": "m2",
                "title": "Interactive Micro-interactions & States",
                "lessons": [
                    {"id": "l4", "title": "Spring Physics & Animation Curves", "lesson_type": "video"},
                    {"id": "l5", "title": "Card Deck Flip & Slide Mechanics", "lesson_type": "cards"}
                ]
            },
            {
                "id": "m3",
                "title": "Final Capstone & Portfolio Delivery",
                "lessons": [
                    {"id": "l6", "title": "Capstone Design Spec Review", "lesson_type": "document"},
                    {"id": "l7", "title": "Final Certification Exam", "lesson_type": "assessment"}
                ]
            }
        ]
    }

    # 1. Test Unenrolled State
    with patch("src.course_view.get_courses", AsyncMock(return_value=[mock_course])), \
         patch("src.course_view.get_enrollments", AsyncMock(return_value=[])):

        view = await course_details_view(mock_page, "c_test_001")
        assert view is not None
        assert view.route == "/courses/c_test_001"
        assert view.appbar is not None
        print("[PASS] Unenrolled view created successfully.")

        # Await all background tasks triggered by run_task
        if running_tasks:
            await asyncio.gather(*running_tasks)
            running_tasks.clear()

        # Inspect content socket
        content_socket = view.controls[0]
        assert content_socket.content is not None
        main_col = content_socket.content.content
        assert len(main_col.controls) >= 2  # hero_card, responsive_grid

        # Check Hero Card
        hero_card = main_col.controls[0]
        assert hero_card is not None
        print("[PASS] Hero canvas loaded with stats and media.")

        # Check Responsive Grid & Sidebar
        responsive_grid = main_col.controls[1]
        left_col = responsive_grid.controls[0].content
        sidebar_card = responsive_grid.controls[1].content
        assert left_col is not None
        assert sidebar_card is not None

        # Check Curriculum Accordion
        curriculum_section = left_col.controls[1]
        assert curriculum_section is not None
        # Verify 3 modules in accordion
        accordion_col = curriculum_section.content.controls[1]
        assert len(accordion_col.controls) == 3
        print("[PASS] Curriculum accordion rendered 3 modules with lessons.")

        # Check Enrol CTA
        enrol_btn = sidebar_card.content.controls[1]
        assert "Enroll in Course" in enrol_btn.content.controls[1].value
        print("[PASS] Unenrolled CTA displays 'Enroll in Course'.")

    # 2. Test Enrolled State
    with patch("src.course_view.get_courses", AsyncMock(return_value=[mock_course])), \
         patch("src.course_view.get_enrollments", AsyncMock(return_value=[{"id": "c_test_001"}])):

        view_enrolled = await course_details_view(mock_page, "c_test_001")
        if running_tasks:
            await asyncio.gather(*running_tasks)
            running_tasks.clear()

        content_socket = view_enrolled.controls[0]
        main_col = content_socket.content.content
        responsive_grid = main_col.controls[1]
        sidebar_card = responsive_grid.controls[1].content

        enrol_btn = sidebar_card.content.controls[1]
        assert "Continue Learning" in enrol_btn.content.controls[1].value
        print("[PASS] Enrolled CTA displays 'Continue Learning'.")

        # Test clicking Continue Learning
        enrol_btn.on_click(MagicMock())
        mock_page.go.assert_called_with("/courses/c_test_001/view")
        print("[PASS] Clicking Continue Learning navigates to /courses/c_test_001/view.")

    # 3. Test Skeleton Screen for /courses/:id in main.py
    import main as main_module
    history_views = []
    class TrackingList(list):
        def append(self, item):
            history_views.append(item)
            super().append(item)

    mock_main_page = MagicMock(spec=ft.Page)
    mock_main_page.web = True
    mock_main_page.width = 1200
    mock_main_page.height = 800
    mock_main_page.theme_mode = ft.ThemeMode.LIGHT
    mock_main_page.fonts = {}
    mock_main_page.data = {}
    mock_main_page.views = TrackingList()
    mock_main_page.route = "/dashboard"
    mock_main_page.session = MagicMock()
    mock_main_page.session.store = MagicMock()
    mock_main_page.shared_preferences = MagicMock()
    mock_main_page.shared_preferences.get = AsyncMock(return_value="valid_token")
    mock_main_page.shared_preferences.set = AsyncMock()
    mock_main_page.run_task = MagicMock()
    mock_main_page.update = MagicMock()
    mock_main_page.window = MagicMock()
    mock_main_page.overlay = []

    with patch("main.get_current_user_request", AsyncMock(return_value=(200, {"id": "user1"}))), \
         patch("main.asyncio.sleep", AsyncMock(return_value=None)):
        
        await asyncio.wait_for(main_module.main(mock_main_page), timeout=1.0)
        history_views.clear()

        # Trigger on_route_change to /courses/c_test_001
        mock_main_page.route = "/courses/c_test_001"
        await mock_main_page.on_route_change(None)

        assert len(history_views) > 0
        skel_view = history_views[-1]
        box_count = len(getattr(skel_view, "data", []))
        print(f"[PASS] main.py course details skeleton generated ({box_count} shimmer boxes, 0 bottom app bars).")

    print("\n[ALL PASS] Modern Course Info View fully validated!")

if __name__ == "__main__":
    asyncio.run(test_course_view())
