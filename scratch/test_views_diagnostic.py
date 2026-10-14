import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath("."))
import flet as ft
from unittest.mock import MagicMock, AsyncMock

async def run_diagnostic():
    print("=== Starting Views Diagnostic Test ===")
    
    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 1200
    mock_page.height = 800
    mock_page.theme_mode = ft.ThemeMode.LIGHT
    mock_page.platform_brightness = ft.Brightness.LIGHT
    mock_page.platform = ft.PagePlatform.WINDOWS
    mock_page.views = []
    mock_page.overlay = []
    mock_page.session = MagicMock()
    mock_page.session.store = MagicMock()
    mock_page.session.store.get = MagicMock(return_value={"id": "test-user", "username": "test", "email": "test@test.com"})
    mock_page.session.store.set = MagicMock()
    mock_page.shared_preferences = MagicMock()
    mock_page.shared_preferences.get = AsyncMock(return_value="mock-token")
    mock_page.shared_preferences.set = AsyncMock()
    mock_page.run_task = MagicMock(side_effect=lambda fn, *args, **kwargs: None)
    mock_page.update = MagicMock()
    mock_page.go = MagicMock()
    mock_page.show_dialog = MagicMock()
    mock_page.pop_dialog = MagicMock()

    # 1. Test Login View
    print("\n[1] Testing login_view...")
    try:
        from src.Login import login_view
        v_login = login_view(mock_page)
        print(f"login_view instantiated successfully! Route: {v_login.route}")
    except Exception as e:
        print(f"ERROR in login_view: {e}")
        import traceback
        traceback.print_exc()

    # 2. Test Dashboard View
    print("\n[2] Testing dashboard_view...")
    try:
        from src.dashboard import dashboard_view
        v_dashboard = await dashboard_view(mock_page)
        print(f"dashboard_view instantiated successfully! Route: {v_dashboard.route}")
    except Exception as e:
        print(f"ERROR in dashboard_view: {e}")
        import traceback
        traceback.print_exc()

    # 3. Test Self-Study View
    print("\n[3] Testing self_study_view...")
    try:
        from src.self_study import self_study_view
        v_study = await self_study_view(mock_page)
        print(f"self_study_view instantiated successfully! Route: {v_study.route}")
    except Exception as e:
        print(f"ERROR in self_study_view: {e}")
        import traceback
        traceback.print_exc()

    # 4. Test Network View
    print("\n[4] Testing network_view...")
    try:
        from src.network import network_view
        v_network = await network_view(mock_page)
        print(f"network_view instantiated successfully! Route: {v_network.route}")
    except Exception as e:
        print(f"ERROR in network_view: {e}")
        import traceback
        traceback.print_exc()

    print("\n=== Diagnostic Complete ===")

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
