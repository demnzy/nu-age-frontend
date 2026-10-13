"""
scratch/test_partnerships_frontend_overhaul.py
──────────────────────────────────────────────────────────────────────────────
Verifies that all modified frontend views, modals, and requests compile and
instantiate cleanly with zero AttributeErrors or syntax bugs in Flet 0.86.5.
Strictly verifies that page.run_task only receives coroutine functions.
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
import inspect
import py_compile
import unittest.mock as mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import flet as ft

def test_syntax():
    print(">>> 1. COMPILING PYTHON FILES VIA py_compile <<<")
    files_to_compile = [
        "src/requests/study_partners.py",
        "src/requests/objectives.py",
        "src/components/partner_challenge_modal.py",
        "src/components/objectives_and_leaderboard_modal.py",
        "src/components/study_partner_cockpit.py",
        "src/self_study.py",
    ]
    for rel_path in files_to_compile:
        full_path = os.path.join(os.path.dirname(__file__), "..", rel_path)
        py_compile.compile(full_path, doraise=True)
        print(f"  [PASS] {rel_path} compiled cleanly.")


def test_instantiations():
    print("\n>>> 2. TESTING COMPONENT INSTANTIATIONS WITH STRICT COROUTINE CHECKS <<<")
    mock_page = mock.MagicMock(spec=ft.Page)
    mock_page.overlay = []
    mock_page.width = 1200
    mock_page.height = 800

    def strict_run_task(fn, *args, **kwargs):
        if not inspect.iscoroutinefunction(fn):
            raise TypeError(f"handler must be a coroutine function, got: {type(fn)} ({fn})")
        return None

    mock_page.run_task = strict_run_task
    mock_page.update = lambda: None

    # Test 1: Study Partner Cockpit
    from src.components.study_partner_cockpit import build_study_partner_cockpit
    cockpit = build_study_partner_cockpit(
        page=mock_page,
        token="mock_token",
        available_materials=[{"id": "mat_1", "title": "Cell Biology", "source_type": "text"}],
    )
    assert isinstance(cockpit, ft.Container), "Cockpit must be an ft.Container"
    print("  [PASS] build_study_partner_cockpit instantiated successfully.")

    # Test 2: Duel Results Dialog
    from src.components.partner_challenge_modal import show_duel_results_dialog, show_create_duel_dialog
    sample_challenge = {
        "id": "chal_1",
        "status": "challenger_done",
        "challenger_id": "user_a",
        "challenged_id": "user_b",
        "challenger_score": 12,
        "challenger_time_seconds": 95,
        "total_questions": 15,
        "question_snapshot": [
            {
                "id": f"q_{i}",
                "question": f"Question {i+1}",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            }
            for i in range(15)
        ]
    }
    show_duel_results_dialog(
        page=mock_page,
        challenge=sample_challenge,
        current_user_id="user_b",
        token="mock_token",
        partnership_id="p_123",
    )
    assert len(mock_page.overlay) > 0, "Overlay must contain duel results dialog"
    print("  [PASS] show_duel_results_dialog instantiated successfully.")

    # Test 3: Create Duel Dialog
    show_create_duel_dialog(
        page=mock_page,
        token="mock_token",
        partnership_id="p_123",
        partner={"id": "user_b", "first_name": "Sam", "last_name": "Smith"},
        available_materials=[{"id": "pack_1", "title": "Immunology Review", "pack_id": "pack_1"}],
    )
    print("  [PASS] show_create_duel_dialog instantiated successfully.")

    # Test 4: Objectives and Leaderboard Dialog (with active tab clicking simulation)
    from src.components.objectives_and_leaderboard_modal import show_objectives_and_leaderboard_dialog
    overlay_count_before = len(mock_page.overlay)
    show_objectives_and_leaderboard_dialog(
        page=mock_page,
        token="mock_token",
        partnership_id="p_123",
        partner={"id": "user_b", "first_name": "Sam"},
        initial_tab="objectives",
    )
    assert len(mock_page.overlay) > overlay_count_before, "Dialog must be appended to overlay"
    dlg = mock_page.overlay[-1]

    # Verify tab clicking triggers strict_run_task without TypeError
    # Tab header is dlg.content.content.controls[0]
    tab_header = dlg.content.content.controls[0]
    # Click 2: Shared Packs Tab
    shared_packs_btn = tab_header.controls[1]
    shared_packs_btn.on_click(None)
    print("  [PASS] Shared Packs tab switched without error.")

    # Click 3: Leaderboards Tab (the user's failing step)
    leaderboard_btn = tab_header.controls[2]
    leaderboard_btn.on_click(None)
    print("  [PASS] Leaderboards tab switched without error.")

    # Click 1: Back to Objectives Tab
    objectives_btn = tab_header.controls[0]
    objectives_btn.on_click(None)
    print("  [PASS] Objectives tab switched without error.")

    print("\n=====================================================================")
    print(">>> ALL FRONTEND COMPONENT INSTANTIATION & TAB SWITCH TESTS PASSED <<<")
    print("=====================================================================")


if __name__ == "__main__":
    test_syntax()
    test_instantiations()
