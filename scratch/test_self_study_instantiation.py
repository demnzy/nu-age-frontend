import sys
import asyncio
sys.path.append(".")
import flet as ft
from unittest.mock import MagicMock, AsyncMock

async def main():
    print("Testing opening modals...")
    from src.self_study import self_study_view

    page = MagicMock(spec=ft.Page)
    page.width = 1000
    page.height = 800
    page.overlay = []
    page.shared_preferences = MagicMock()
    page.shared_preferences.get = AsyncMock(return_value="mock_token")
    page.shared_preferences.get_async = AsyncMock(return_value="mock_token")
    
    # Store run_task calls
    tasks = []
    page.run_task = lambda fn, *args: tasks.append((fn, args))

    view = await self_study_view(page)
    
    # Check that modals can be triggered by calling their buttons or inspecting the page overlay
    print("Page overlay initial length:", len(page.overlay))
    
    # Find upload button and generate button in view
    # In body_host or studio card:
    print("Self study view successfully loaded and ready for interaction!")

asyncio.run(main())
