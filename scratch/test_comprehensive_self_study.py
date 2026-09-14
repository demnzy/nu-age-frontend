import sys
sys.path.insert(0, ".")
import asyncio
import flet as ft
from unittest.mock import AsyncMock, MagicMock, patch

from src.self_study import format_material_title, self_study_view

def test_title_formatting():
    test_cases = [
        ("cell_biology_lecture_notes.pdf", "Cell biology lecture notes"),
        ("HUMAN_ANATOMY_DISSECTION_GUIDE.DOCX", "Human anatomy dissection guide"),
        ("dna_and_rna_synthesis_pathways.txt", "DNA and RNA synthesis pathways"),
        ("ai_in_modern_medicine_overview.md", "AI in modern medicine overview"),
        ("https://en.wikipedia.org/wiki/Mitochondrion", "en.wikipedia.org: Mitochondrion"),
        ("sm-2_spaced_repetition_algorithms.pdf", "SM-2 spaced repetition algorithms"),
        ("ATP_production_in_cellular_respiration", "ATP production in cellular respiration"),
        ("already Clean Title", "Already clean title"),
    ]
    for raw, expected in test_cases:
        res = format_material_title(raw)
        print(f"RAW: '{raw}' -> FORMATTED: '{res}'")
        assert res == expected, f"Expected '{expected}', got '{res}'"
    print("[TEST] format_material_title tests PASSED!")

async def test_view_interactions():
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 800
    page.route = "/self-study"
    page.overlay = []
    page.shared_preferences = AsyncMock()
    page.shared_preferences.get = AsyncMock(return_value="fake-token")
    
    # Mock session
    page.session = MagicMock()
    page.session.store = {
        "current_user": {
            "full_name": "Alexander Hayes",
            "email": "alex.hayes@oxford.ac.uk",
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
    assert view.route == "/self-study"

    # Test Mobile Viewport Resizing (360px, 480px, 768px, 1280px)
    for w in [360, 480, 768, 1280]:
        page.width = w
        page.on_resize(MagicMock())
    print("[TEST] Responsive layout resizes PASSED!")

    # Test loading hub data
    sample_materials = [
        {"id": "mat-1", "title": "mitochondrial_dna_analysis.pdf", "source_type": "pdf"},
        {"id": "mat-2", "title": "https://en.wikipedia.org/wiki/Glycolysis", "source_type": "url"},
        {"id": "mat-3", "title": "neuroscience_synaptic_plasticity_notes.txt", "source_type": "text"},
    ]
    sample_due_cards = [
        {"id": "c1", "front": "Q1", "back": "A1"},
        {"id": "c2", "front": "Q2", "back": "A2"},
        {"id": "c3", "front": "Q3", "back": "A3"},
    ]
    sample_sub = {
        "plan_id": "free",
        "label": "Free",
        "materials_used": 3,
        "materials_limit": 5,
        "generations_used": 4,
        "generations_limit": 10,
    }

    with patch("src.self_study.get_due_cards", AsyncMock(return_value=sample_due_cards)), \
         patch("src.self_study.get_materials", AsyncMock(return_value=sample_materials)), \
         patch("src.self_study.get_subscription_status", AsyncMock(return_value=sample_sub)):
        load_task = [fn for fn, args, kwargs in tasks if fn.__name__ == "_load_hub"][0]
        await load_task()

    print("[TEST] Hub data load completed successfully!")

    # 1. Verify user email / name is NOT present anywhere in rendered UI
    def _collect_all_texts(root):
        texts = []
        if hasattr(root, "value") and isinstance(root.value, str):
            texts.append(root.value)
        if hasattr(root, "text") and isinstance(root.text, str):
            texts.append(root.text)
        if hasattr(root, "tooltip") and isinstance(root.tooltip, str):
            texts.append(root.tooltip)
        if hasattr(root, "title") and root.title:
            texts.extend(_collect_all_texts(root.title))
        if hasattr(root, "actions") and isinstance(root.actions, list):
            for a in root.actions:
                texts.extend(_collect_all_texts(a))
        if hasattr(root, "controls") and isinstance(root.controls, list):
            for c in root.controls:
                texts.extend(_collect_all_texts(c))
        if hasattr(root, "content") and root.content:
            if isinstance(root.content, str):
                texts.append(root.content)
            else:
                texts.extend(_collect_all_texts(root.content))
        return texts

    all_ui_texts = _collect_all_texts(view)
    assert "alex.hayes@oxford.ac.uk" not in all_ui_texts, "User email found in view!"
    assert "Alexander Hayes" not in all_ui_texts, "User name found in view!"
    print("[TEST] Requirement 1 PASSED: User account & email footer completely removed.")

    # 2. Verify focus scope toggle is NOT in the slim rail
    assert not any("focus scope" in t.lower() for t in all_ui_texts), "Focus scope toggle found in UI!"
    print("[TEST] Requirement 2 PASSED: Redundant focus scope toggle removed.")

    # 3. Verify Studio & Quotas sidebar menu item exists and opens the Studio & Quotas UI
    assert any("studio & quotas" in t.lower() for t in all_ui_texts), "Studio & Quotas sidebar menu item missing!"
    
    # Find the Studio & Quotas container in sidebar and click it
    def _find_controls_by_type(root, target_type):
        res = []
        if isinstance(root, target_type):
            res.append(root)
        if hasattr(root, "controls") and isinstance(root.controls, list):
            for c in root.controls:
                res.extend(_find_controls_by_type(c, target_type))
        if hasattr(root, "content") and root.content:
            res.extend(_find_controls_by_type(root.content, target_type))
        return res

    containers = _find_controls_by_type(view, ft.Container)
    studio_menu_items = [c for c in containers if any("studio & quotas" in t.lower() for t in _collect_all_texts(c)) and c.on_click]
    assert len(studio_menu_items) > 0, "Studio & Quotas clickable sidebar menu item not found!"
    
    # Trigger Studio modal by clicking the sidebar item
    prev_overlay_count = len(page.overlay)
    studio_menu_items[0].on_click(MagicMock())
    assert len(page.overlay) == prev_overlay_count + 1, "Studio & Quotas modal was not opened into overlay!"
    
    studio_dlg = page.overlay[-1]
    assert isinstance(studio_dlg, ft.AlertDialog), "Studio overlay is not an AlertDialog!"
    assert studio_dlg.open is True, "Studio dialog was not set to open!"
    
    studio_dlg_texts = _collect_all_texts(studio_dlg)
    assert any("upload material" in t.lower() for t in studio_dlg_texts), "Upload Material action missing from Studio UI!"
    assert any("ai synthesis" in t.lower() for t in studio_dlg_texts), "AI Synthesis action missing from Studio UI!"
    assert any("3 / 5" in t for t in studio_dlg_texts), "Materials limit 3 / 5 missing from Studio Quotas!"
    assert any("4 / 10" in t for t in studio_dlg_texts), "Generations limit 4 / 10 missing from Studio Quotas!"
    print("[TEST] Requirement 3 PASSED: Dedicated Studio & Quotas sidebar menu item opens sleek Studio & Quotas UI!")
    
    # Close studio dialog for subsequent tests
    studio_dlg.open = False

    outlined_buttons = _find_controls_by_type(view, ft.OutlinedButton)
    exam_btns = [b for b in outlined_buttons if "Exam" in _collect_all_texts(b)]
    quiz_btns = [b for b in outlined_buttons if "Quiz" in _collect_all_texts(b)]
    card_btns = [b for b in outlined_buttons if "Cards" in _collect_all_texts(b)]

    print(f"Vault Card Buttons: Cards={len(card_btns)}, Quiz={len(quiz_btns)}, Exam={len(exam_btns)}")
    assert len(exam_btns) >= 3, f"Expected at least 3 Exam buttons (one per material card), got {len(exam_btns)}"
    print("[TEST] Requirement 4 PASSED: Material card 'Exam' button present on Vault cards.")

    # 5. Verify Exam Simulator back button safeguard & auto-submit
    sample_exam_questions = [
        {"id": "q1", "question": "What is ATP?", "options": ["Energy", "Water", "Gas", "Metal"], "answer": 0}
    ]
    with patch("src.self_study.get_exam_questions", AsyncMock(return_value=sample_exam_questions)):
        start_exam_task = [fn for fn, args, kwargs in tasks if fn.__name__ == "_start_exam"]
        tasks.clear()
        exam_btns[0].on_click(MagicMock())
        assert len(tasks) > 0, "No task scheduled by Exam button!"
        exam_task_fn, exam_task_args, _ = tasks[0]
        await exam_task_fn(*exam_task_args)

    # In exam mode, app_bar leading on_click should trigger _on_exam_back
    assert view.appbar is not None
    assert view.appbar.leading is not None
    assert view.appbar.leading.on_click is not None

    # Simulate user tapping back during active exam
    initial_overlays = len(page.overlay)
    view.appbar.leading.on_click(MagicMock())
    assert len(page.overlay) == initial_overlays + 1, "Exit confirmation dialog not added to overlay!"
    exit_dlg = page.overlay[-1]
    assert isinstance(exit_dlg, ft.AlertDialog), "Overlay item is not an AlertDialog!"
    assert "Submit & End Exam?" in _collect_all_texts(exit_dlg), "Dialog title mismatch!"

    # Verify dialog actions: Continue Exam vs Submit & Exit
    action_texts = _collect_all_texts(exit_dlg)
    assert any("continue exam" in t.lower() for t in action_texts), "Continue Exam button missing!"
    assert any("submit & exit" in t.lower() for t in action_texts), "Submit & Exit button missing!"

    # Find buttons inside exit_dlg content
    dialog_buttons = _find_controls_by_type(exit_dlg, ft.OutlinedButton) + _find_controls_by_type(exit_dlg, ft.ElevatedButton)
    cancel_btn = [b for b in dialog_buttons if any("continue" in t.lower() for t in _collect_all_texts(b))][0]
    submit_exit_btn = [b for b in dialog_buttons if any("submit & exit" in t.lower() for t in _collect_all_texts(b))][0]

    # Test "Continue Exam" cancels dialog
    cancel_btn.on_click(MagicMock())
    assert exit_dlg.open is False, "Dialog was not closed on cancel!"

    # Test "Submit & Exit" auto-submits exam and triggers results view
    exit_dlg.open = True
    submit_exit_btn.on_click(MagicMock())
    assert exit_dlg.open is False, "Dialog was not closed on submit!"

    # Verify results view was rendered into exam socket
    content_texts = _collect_all_texts(view)
    assert any("results" in t.lower() or "score" in t.lower() or "exam simulator" in t.lower() for t in content_texts)
    print("[TEST] Requirement 5 PASSED: Sleek modal auto-submits and displays exam results on exit.")

    # 6. Verify material selection triggers due cards sync across single and multiple materials
    # Return to hub
    go_hub_task = [fn for fn, args, kwargs in tasks if fn.__name__ == "_load_hub"]
    # Re-trigger hub load
    tasks.clear()
    with patch("src.self_study.get_due_cards", AsyncMock(return_value=sample_due_cards)), \
         patch("src.self_study.get_materials", AsyncMock(return_value=sample_materials)), \
         patch("src.self_study.get_subscription_status", AsyncMock(return_value=sample_sub)):
        # Simulate go_hub
        view.appbar.leading.on_click(MagicMock()) # In exam results view, leading or exit goes to hub
        # Find _load_hub in scheduled tasks
        load_tasks = [fn for fn, args, kwargs in tasks if fn.__name__ == "_load_hub"]
        if load_tasks:
            await load_tasks[0]()

    hub_texts_initial = _collect_all_texts(view)
    assert any("3 due" in t for t in hub_texts_initial), "Initial due count mismatch!"

    # Test selecting material 1: should update due cards to scoped cards for mat-1
    mat1_cards = [{"id": "c1", "front": "Q1", "back": "A1", "material_id": "mat-1"}]
    with patch("src.self_study.get_due_cards", AsyncMock(return_value=mat1_cards)) as mock_due:
        # Find material card on landing page and toggle it
        cards = _find_controls_by_type(view, ft.Container)
        mat_containers = [c for c in cards if c.tooltip == "Click to toggle material selection"]
        assert len(mat_containers) >= 3, f"Expected at least 3 clickable material cards, got {len(mat_containers)}"

        tasks.clear()
        mat_containers[0].on_click(MagicMock())
        assert len(tasks) > 0, "No task scheduled when clicking material card!"
        sync_fn, sync_args, sync_kwargs = tasks[0]
        await sync_fn(*sync_args, **sync_kwargs)

        # Verify get_due_cards was called with mat-1
        mock_due.assert_called_with("fake-token", ["mat-1"])
        texts_after_mat1 = _collect_all_texts(view)
        assert any("1 due" in t for t in texts_after_mat1), "Due count did not update to 1 due after selecting mat-1!"
        print("[TEST] Single material selection updated review cards count to 1 due.")

    # Test selecting material 2 as well: should query with ['mat-1', 'mat-2'] and update count
    mat1_and_2_cards = [
        {"id": "c1", "front": "Q1", "back": "A1", "material_id": "mat-1"},
        {"id": "c2", "front": "Q2", "back": "A2", "material_id": "mat-2"},
    ]
    with patch("src.self_study.get_due_cards", AsyncMock(return_value=mat1_and_2_cards)) as mock_due:
        tasks.clear()
        mat_containers[1].on_click(MagicMock())
        assert len(tasks) > 0, "No task scheduled when clicking second material card!"
        sync_fn, sync_args, sync_kwargs = tasks[0]
        await sync_fn(*sync_args, **sync_kwargs)

        mock_due.assert_called_with("fake-token", ["mat-1", "mat-2"])
        texts_after_mat2 = _collect_all_texts(view)
        assert any("2 due" in t for t in texts_after_mat2), "Due count did not update to 2 due after selecting mat-1 + mat-2!"
        print("[TEST] Multi-material selection updated review cards count to 2 due.")

    print("\n========================================================")
    print(">>> ALL SELF-STUDY REFINEMENT TESTS PASSED 100%! <<<")
    print("========================================================")

if __name__ == "__main__":
    test_title_formatting()
    asyncio.run(test_view_interactions())
