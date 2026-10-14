import sys
sys.path.insert(0, ".")
import asyncio
import flet as ft
from unittest.mock import AsyncMock, MagicMock

async def main():
    # Mock Page
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 800
    page.route = "/self-study"
    page.overlay = []
    
    # Mock shared preferences
    page.shared_preferences = AsyncMock()
    page.shared_preferences.get = AsyncMock(return_value="fake-token")
    
    # Mock run_task
    tasks = []
    def fake_run_task(coro_fn, *args, **kwargs):
        tasks.append((coro_fn, args, kwargs))
    page.run_task = fake_run_task
    page.update = MagicMock()
    page.go = MagicMock()

    # Import self_study_view
    from src.self_study import self_study_view
    
    print("[TEST] Instantiating self_study_view...")
    view = await self_study_view(page)
    
    print(f"[TEST] View instantiated successfully! Route: {view.route}")
    assert view.route == "/self-study"
    assert view.appbar is not None
    assert len(view.controls) > 0

    # Test Mobile resize
    print("[TEST] Testing layout resize to mobile (width=400)...")
    page.width = 400
    page.on_resize(MagicMock())
    
    # Test Desktop resize
    print("[TEST] Testing layout resize to desktop (width=1200)...")
    page.width = 1200
    page.on_resize(MagicMock())

    # Execute _load_hub with mock data
    print("[TEST] Testing _load_hub with sample materials...")
    from unittest.mock import patch
    sample_materials = [
        {"id": "mat-1", "title": "Cell Biology Lecture Notes.pdf", "source_type": "pdf"},
        {"id": "mat-2", "title": "https://en.wikipedia.org/wiki/Mitochondrion", "source_type": "url"},
        {"id": "mat-3", "title": "Organic Chemistry Synthesis Summary", "source_type": "text"},
    ]
    sample_due_cards = [
        {"id": "card-1", "front": "What is the powerhouse?", "back": "Mitochondria"},
        {"id": "card-2", "front": "What is ATP?", "back": "Adenosine Triphosphate"},
    ]
    sample_sub = {
        "plan_id": "free",
        "label": "Free",
        "materials_used": 3,
        "materials_limit": 5,
        "generations_used": 2,
        "generations_limit": 10,
    }

    with patch("src.self_study.get_due_cards", AsyncMock(return_value=sample_due_cards)), \
         patch("src.self_study.get_materials", AsyncMock(return_value=sample_materials)), \
         patch("src.self_study.get_subscription_status", AsyncMock(return_value=sample_sub)):
        # Run _load_hub (the first registered task)
        load_task = [fn for fn, args, kwargs in tasks if fn.__name__ == "_load_hub"][0]
        await load_task()

    print("[TEST] _load_hub executed and rendered hub successfully!")

    print("[TEST] All instantiation and layout checks PASSED cleanly!")

if __name__ == "__main__":
    asyncio.run(main())
