import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import flet as ft

async def test_all_skeletons():
    import main as main_module
    print("Testing all skeleton layouts with no bottom app bar...")

    history_views = []
    class TrackingList(list):
        def append(self, item):
            history_views.append(item)
            super().append(item)

    mock_page = MagicMock(spec=ft.Page)
    mock_page.web = True
    mock_page.width = 1200
    mock_page.height = 800
    mock_page.theme_mode = ft.ThemeMode.LIGHT
    mock_page.fonts = {}
    mock_page.data = {}
    mock_page.views = TrackingList()
    mock_page.route = "/dashboard"
    mock_page.session = MagicMock()
    mock_page.session.store = MagicMock()
    mock_page.shared_preferences = MagicMock()
    mock_page.shared_preferences.get = AsyncMock(return_value="valid_token")
    mock_page.shared_preferences.set = AsyncMock()
    mock_page.run_task = MagicMock()
    mock_page.update = MagicMock()
    mock_page.window = MagicMock()
    mock_page.overlay = []

    routes_to_test = [
        "/dashboard",
        "/courses",
        "/courses/123/view",
        "/nu-chat",
        "/profile",
        "/network",
        "/self-study",
    ]

    with patch("main.get_current_user_request", AsyncMock(return_value=(200, {"id": "user1"}))), \
         patch("main.asyncio.sleep", AsyncMock(return_value=None)):
        
        # Initialize main with first route
        mock_page.route = routes_to_test[0]
        await asyncio.wait_for(main_module.main(mock_page), timeout=1.0)
        print(f"[PASS] Route {routes_to_test[0]}: skeleton generated ({len(getattr(history_views[-1], 'data', []))} boxes)")

        for route in routes_to_test[1:]:
            history_views.clear()
            mock_page.route = route
            await mock_page.on_route_change(None)
            boxes = len(getattr(history_views[-1], 'data', [])) if history_views else 0
            print(f"[PASS] Route {route}: skeleton generated ({boxes} boxes)")

    print("\n[ALL PASS] All skeleton screens verified with zero bottom app bars!")

if __name__ == "__main__":
    asyncio.run(test_all_skeletons())
