import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath("."))
import flet as ft
from unittest.mock import MagicMock, AsyncMock

async def test_self_study_hub():
    print("=== Testing Self Study Hub Load & Build ===")
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
    
    # Instantiate view
    view = await self_study_view(mock_page)
    print(f"View instantiated. Tasks registered: {len(tasks)}")

    from unittest.mock import patch
    sample_materials = [
        {"id": "mat-1", "title": "Calculus 101 Lecture Notes.pdf", "source_type": "pdf"},
        {"id": "mat-2", "title": "https://en.wikipedia.org/wiki/Neural_network", "source_type": "url"},
        {"id": "mat-3", "title": "Biology SM-2 Summary Notes", "source_type": "text"},
    ]
    sample_due_cards = [
        {"id": "card-1", "front": "Q1", "back": "A1"},
        {"id": "card-2", "front": "Q2", "back": "A2"},
    ]

    with patch("src.self_study.get_due_cards", AsyncMock(return_value=sample_due_cards)), \
         patch("src.self_study.get_materials", AsyncMock(return_value=sample_materials)), \
         patch("src.self_study.get_subscription_status", AsyncMock(return_value={"plan_id": "free", "label": "Free Tier", "materials_used": 2, "materials_limit": 5, "generations_used": 1, "generations_limit": 10})):
        
        # Execute the registered tasks (like _load_hub)
        for fn, args, kwargs in tasks:
            print(f"Running registered task: {fn.__name__}")
            if fn.__name__ == "_load_hub":
                await fn(*args, **kwargs)
                print("_load_hub executed successfully!")

    print("=== Test Completed Successfully ===")

if __name__ == "__main__":
    asyncio.run(test_self_study_hub())
