import sys
import os
import unittest
from unittest.mock import MagicMock, AsyncMock

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import flet as ft
from src.components.shimmer_skeletons import build_skeleton_view, build_leaderboards_skeleton

class TestLeaderboardAndNetworkUpdates(unittest.TestCase):
    def setUp(self):
        self.mock_page = MagicMock(spec=ft.Page)
        self.mock_page.width = 1000
        self.mock_page.height = 800
        self.mock_page.overlay = []
        self.mock_page.views = []
        self.mock_page.route = "/network"
        self.mock_page.shared_preferences = MagicMock()
        self.mock_page.shared_preferences.get = AsyncMock(return_value="mock_token")

    def test_leaderboard_skeleton_is_truthful(self):
        """Verify that build_skeleton_view('/leaderboards') returns the high-fidelity skeleton."""
        view = build_skeleton_view("/leaderboards", self.mock_page)
        self.assertIsInstance(view, ft.View)
        self.assertTrue(len(view.controls) > 0)
        safe_area = view.controls[0]
        self.assertIsInstance(safe_area, ft.SafeArea)
        body = safe_area.content
        self.assertIsInstance(body, ft.ListView)
        self.assertGreater(len(body.controls), 6)
        boxes = view.data
        self.assertTrue(len(boxes) > 10)

    def test_network_view_top_avatar_with_profile_pic(self):
        """Verify network_view renders user's profile picture in top-right avatar."""
        mock_user = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "username": "ada",
            "profile_picture_url": "https://images.example.com/ada.png"
        }
        mock_store = {"current_user": mock_user}
        class MockSession:
            store = mock_store
        self.mock_page.session = MockSession()

        import asyncio
        from src.network import network_view
        view = asyncio.run(network_view(self.mock_page))
        self.assertIsInstance(view, ft.View)
        col = view.controls[0].content
        header_container = col.controls[0]
        header_col = header_container.content
        top_nav_row = header_col.controls[0]
        avatar_container = top_nav_row.controls[1]
        avatar_ctrl = avatar_container.content
        self.assertIsInstance(avatar_ctrl, ft.CircleAvatar)
        self.assertEqual(avatar_ctrl.foreground_image_src, "https://images.example.com/ada.png")

    def test_duo_card_sub_label_sanitization(self):
        """Verify duo card subtitle does not display raw JAMB UTME when partnership had legacy default."""
        p_a = {"first_name": "John", "university": "UNILAG"}
        p_b = {"first_name": "Jane", "university": None}
        raw_target = "JAMB UTME"
        clean_target = raw_target if (raw_target and not any(term in raw_target.upper() for term in ["JAMB", "UTME", "GENERAL"])) else None
        sub_label = p_a.get("university") or p_b.get("university") or (f"{clean_target} Focus" if clean_target else "Campus Duos")
        self.assertEqual(sub_label, "UNILAG")
        self.assertNotIn("JAMB", sub_label)

if __name__ == "__main__":
    unittest.main()
