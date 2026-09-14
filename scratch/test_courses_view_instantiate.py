import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import flet as ft
from unittest.mock import MagicMock
from src.courses import courses_view

async def run_test():
    mock_page = MagicMock(spec=ft.Page)
    mock_page.web = False
    mock_page.theme_mode = ft.ThemeMode.LIGHT
    mock_page.platform_brightness = ft.Brightness.LIGHT
    mock_page.shared_preferences = MagicMock()
    mock_page.shared_preferences.get = MagicMock(return_value="fake_token")
    mock_page.client_storage = MagicMock()

    view = await courses_view(mock_page)
    assert isinstance(view, ft.View)
    print("[PASS] courses_view instantiated successfully!")

if __name__ == "__main__":
    asyncio.run(run_test())
