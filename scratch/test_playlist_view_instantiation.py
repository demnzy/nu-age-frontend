import sys, os
sys.path.insert(0, os.path.abspath("."))
import asyncio
import py_compile
import flet as ft
from src.playlist_view import playlist_view

# Mock Page implementation following the conventions
class MockSession:
    def __init__(self):
        self.store = {}

class MockSharedPreferences:
    async def get(self, key):
        return "mock_test_token"

class MockPage:
    def __init__(self, width=1280):
        self.width = width
        self.height = 800
        self.route = "/playlists/test-playlist-id"
        self.session = MockSession()
        self.shared_preferences = MockSharedPreferences()
        self.views = []
        self.dialog = None

    def update(self):
        pass

    def go(self, route):
        self.route = route

    def show_dialog(self, dlg):
        self.dialog = dlg

async def main_test():
    print("Testing static py_compile...")
    py_compile.compile("src/playlist_view.py", doraise=True)
    print("Syntax check passed!")

    # 1. Test Desktop Page Instantiation
    print("Instantiating playlist_view on Desktop (width=1280)...")
    desktop_page = MockPage(width=1280)
    view_desktop = await playlist_view(desktop_page, "test-playlist-123")
    assert isinstance(view_desktop, ft.View), "Should return an ft.View"
    assert view_desktop.appbar is not None, "Should have an AppBar"
    print("Desktop View created successfully!")

    # 2. Test Mobile Page Instantiation
    print("Instantiating playlist_view on Mobile (width=400)...")
    mobile_page = MockPage(width=400)
    view_mobile = await playlist_view(mobile_page, "test-playlist-123")
    assert isinstance(view_mobile, ft.View), "Should return an ft.View"
    print("Mobile View created successfully!")

    # 3. Test with Mock Data directly
    from unittest.mock import patch
    mock_playlist_payload = {
        "id": "pl-001",
        "name": "Full-Stack Machine Learning Pathway",
        "description": "Master data science, deep learning architectures, and scalable cloud deployment in one sequential path.",
        "image_url": "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
        "rating": 4.9,
        "is_public": True,
        "Organisation": "AI Research Lab",
        "playlist_courses": [
            {
                "order_index": 1,
                "course": {
                    "id": "c-001",
                    "name": "Mathematics for Machine Learning",
                    "description": "Linear algebra, multivariable calculus, and matrix decompositions.",
                    "category": {"name": "Foundations"},
                    "rating": 4.9,
                    "admin": {"first_name": "Dr. Sarah", "last_name": "Chen"},
                    "image_url": "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
                }
            },
            {
                "order_index": 2,
                "course": {
                    "id": "c-002",
                    "name": "Deep Learning & Neural Networks",
                    "description": "CNNs, transformers, and backpropagation from scratch.",
                    "category": {"name": "Deep Learning"},
                    "rating": 4.8,
                    "admin": {"first_name": "Prof. Alex", "last_name": "Rivera"},
                    "image_url": "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
                }
            },
            {
                "order_index": 3,
                "course": {
                    "id": "c-003",
                    "name": "Production MLOps & Deployment",
                    "description": "Docker, Kubernetes, and automated CI/CD model serving.",
                    "category": {"name": "MLOps"},
                    "rating": 5.0,
                    "admin": {"first_name": "David", "last_name": "Kowalski"},
                    "image_url": "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
                }
            }
        ]
    }
    mock_enrollments = [
        {"id": "c-001", "progress": 100.0},
        {"id": "c-002", "progress": 45.0},
    ]
    mock_completed = [
        {"id": "c-001", "name": "Mathematics for Machine Learning"}
    ]

    with patch("src.playlist_view.get_playlist", return_value=mock_playlist_payload), \
         patch("src.playlist_view.get_enrollments", return_value=mock_enrollments), \
         patch("src.playlist_view.get_courses", return_value=mock_completed):

        test_page = MockPage(width=1200)
        v = await playlist_view(test_page, "pl-001")
        await asyncio.sleep(0.1)
        print("Populated mock data rendered without errors!")

    # 4. Test with Empty Courses
    empty_playlist = {"id": "pl-002", "name": "Empty Path", "playlist_courses": []}
    with patch("src.playlist_view.get_playlist", return_value=empty_playlist), \
         patch("src.playlist_view.get_enrollments", return_value=[]), \
         patch("src.playlist_view.get_courses", return_value=[]):
        test_page_empty = MockPage(width=800)
        v_empty = await playlist_view(test_page_empty, "pl-002")
        await asyncio.sleep(0.1)
        print("Empty courses playlist rendered without errors!")

    # 5. Test with All Completed
    all_completed_ids = [{"id": "c-001"}, {"id": "c-002"}, {"id": "c-003"}]
    all_enrolled_map = [{"id": "c-001", "progress": 100}, {"id": "c-002", "progress": 100}, {"id": "c-003", "progress": 100}]
    with patch("src.playlist_view.get_playlist", return_value=mock_playlist_payload), \
         patch("src.playlist_view.get_enrollments", return_value=all_enrolled_map), \
         patch("src.playlist_view.get_courses", return_value=all_completed_ids):
        test_page_all = MockPage(width=1400)
        v_all = await playlist_view(test_page_all, "pl-001")
        await asyncio.sleep(0.1)
        print("All completed playlist rendered without errors!")

    print(">>> ALL PLAYLIST VIEW TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    asyncio.run(main_test())
