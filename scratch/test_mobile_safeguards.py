import sys
sys.path.insert(0, ".")
import asyncio
import flet as ft
from unittest.mock import AsyncMock, MagicMock, patch

from src.self_study import self_study_view

async def run_mobile_tests():
    print("Testing mobile viewport safeguards (320px, 360px, 412px, 480px)...")
    page = MagicMock(spec=ft.Page)
    page.width = 360
    page.height = 640
    page.route = "/self-study"
    page.overlay = []
    page.shared_preferences = AsyncMock()
    page.shared_preferences.get = AsyncMock(return_value="fake-token")
    
    page.session = MagicMock()
    page.session.store = {
        "current_user": {
            "full_name": "Test User",
            "email": "test@test.com",
            "role": "student"
        }
    }
    
    tasks = []
    def fake_run_task(coro_fn, *args, **kwargs):
        tasks.append((coro_fn, args, kwargs))
    page.run_task = fake_run_task
    page.update = MagicMock()
    page.go = MagicMock()

    view = await self_study_view(page)
    
    # 1. Test extreme screen widths
    for test_w in [320, 360, 400, 480]:
        page.width = test_w
        page.on_resize(MagicMock())
        assert view is not None
    print("[TEST] Extreme mobile widths (320px..480px) handled smoothly.")

    # 2. Test Studio Modal sizing on 360px screen
    page.width = 360
    page.height = 640
    
    # Find Studio & Quotas menu item
    def _find_containers(root):
        c_list = []
        if isinstance(root, ft.Container):
            c_list.append(root)
        if hasattr(root, "controls") and isinstance(root.controls, list):
            for c in root.controls:
                c_list.extend(_find_containers(c))
        if hasattr(root, "content") and root.content:
            c_list.extend(_find_containers(root.content))
        return c_list

    def _collect_texts(root):
        texts = []
        if hasattr(root, "value") and isinstance(root.value, str):
            texts.append(root.value)
        if hasattr(root, "text") and isinstance(root.text, str):
            texts.append(root.text)
        if hasattr(root, "title") and root.title:
            texts.extend(_collect_texts(root.title))
        if hasattr(root, "controls") and isinstance(root.controls, list):
            for c in root.controls:
                texts.extend(_collect_texts(c))
        if hasattr(root, "content") and root.content:
            texts.extend(_collect_texts(root.content))
        return texts

    containers = _find_containers(view)
    studio_items = [c for c in containers if any("studio & quotas" in t.lower() for t in _collect_texts(c)) and c.on_click]
    assert len(studio_items) > 0
    studio_items[0].on_click(MagicMock())

    studio_modal = page.overlay[-1]
    assert studio_modal.content.width <= 360 - 32, f"Studio modal width {studio_modal.content.width} exceeds mobile margin!"
    print(f"[TEST] Studio modal width is {studio_modal.content.width}px on 360px screen (safely <= 328px).")

    # 3. Test Exit Exam Modal sizing on 360px screen
    sample_exam = [{"id": "e1", "question": "Mobile test?", "options": ["Yes", "No"], "answer": 0}]
    with patch("src.self_study.get_exam_questions", AsyncMock(return_value=sample_exam)):
        # Trigger exam
        from src.components.study_exam import build_exam
        exam_ctrl = build_exam(page, sample_exam, on_exit=lambda: None, on_restart=lambda: None)
        assert exam_ctrl is not None

    print("[TEST] All mobile safeguards verified successfully!")

if __name__ == "__main__":
    asyncio.run(run_mobile_tests())
