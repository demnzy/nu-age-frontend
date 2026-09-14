import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath("."))
import flet as ft
from unittest.mock import MagicMock, AsyncMock

async def test_studio_modal():
    print("=== Testing Studio Modal ===")
    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 1200
    mock_page.height = 800
    mock_page.theme_mode = ft.ThemeMode.LIGHT
    mock_page.platform_brightness = ft.Brightness.LIGHT
    mock_page.views = []
    mock_page.overlay = []
    mock_page.shared_preferences = MagicMock()
    mock_page.shared_preferences.get = AsyncMock(return_value="fake_token")
    mock_page.update = MagicMock()
    mock_page.go = MagicMock()

    tasks = []
    def fake_run_task(fn, *args, **kwargs):
        tasks.append((fn, args, kwargs))

    mock_page.run_task = fake_run_task

    from src.self_study import self_study_view
    
    view = await self_study_view(mock_page)
    print("View instantiated")

    # Let's inspect sidebar controls and studio modal trigger
    # In sidebar_pane:
    # Let's see if we can trigger the studio modal
    body_host = view.controls[0].content
    print(f"body_host controls: {len(body_host.controls)}")
    sidebar_container = body_host.controls[2]
    sidebar_pane = sidebar_container.content.controls[1]
    
    # Let's find the Studio & Quotas row in sidebar_pane
    middle_col = sidebar_pane.content.controls[1].content.controls[0].content
    studio_row = middle_col.controls[2] # Pinned row 3
    print(f"Found pinned row: {studio_row.content.controls[0].controls[1].value}")
    
    # Trigger studio modal on_click
    print("Triggering studio modal...")
    studio_row.on_click(None)
    
    print(f"Overlay has {len(mock_page.overlay)} items")
    dlg = mock_page.overlay[-1]
    print(f"Dialog open: {dlg.open}")
    print(f"Dialog title: {dlg.title.controls[0].controls[1].controls[0].value}")
    
    print("=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_studio_modal())
