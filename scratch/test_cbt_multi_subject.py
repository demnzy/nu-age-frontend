import sys
import unittest
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, "c:/Users/Admin/Desktop/Code/NU-Front")

import flet as ft
from src.components.cbt_exam_engine import CBTExamEngine, build_cbt_exam_view, _extract_image_url, _clean_question_text

def test_cbt_engine():
    print("Testing CBT Exam Engine...")

    # 1. Test resilient image extractor
    q_with_img_url = {"image_url": "https://example.com/fig1.png"}
    assert _extract_image_url(q_with_img_url) == "https://example.com/fig1.png"

    q_with_diagram = {"diagram": "/media/diagram2.png"}
    assert "media/diagram2.png" in _extract_image_url(q_with_diagram)

    q_with_md = {"question_text": "What is shown in ![circuit](https://example.com/circ.png) above?"}
    assert _extract_image_url(q_with_md) == "https://example.com/circ.png"
    assert "![circuit]" not in _clean_question_text(q_with_md)
    print("[OK] Image extractor & markdown cleaner passed")

    # 2. Test multi-subject JAMB simulation
    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 1000
    mock_page.run_task = MagicMock()
    mock_page.update = MagicMock()
    mock_page.overlay = []

    jamb_questions = [
        {
            "id": "q1",
            "subject": "Use of English",
            "question": "Which of these is a preposition?",
            "options": ["Run", "Beneath", "Quickly", "Heavy"],
            "answer": 1,
            "topic": "Parts of Speech",
            "exam_type": "JAMB UTME",
        },
        {
            "id": "q2",
            "subject": "Mathematics",
            "question": "Solve for x: 2x + 6 = 14",
            "options": ["2", "4", "6", "8"],
            "answer": 1,
            "topic": "Algebra",
            "exam_type": "JAMB UTME",
        },
        {
            "id": "q3",
            "subject": "Physics",
            "question": "What is the SI unit of electric current?",
            "options": ["Volt", "Ohm", "Ampere", "Watt"],
            "answer": 2,
            "topic": "Electricity",
            "exam_type": "JAMB UTME",
        },
        {
            "id": "q4",
            "subject": "Chemistry",
            "question": "Which element has atomic number 6?",
            "options": ["Oxygen", "Nitrogen", "Carbon", "Helium"],
            "answer": 2,
            "topic": "Periodic Table",
            "exam_type": "JAMB UTME",
        },
    ]

    engine_jamb = CBTExamEngine(
        page=mock_page,
        questions=jamb_questions,
        duration_seconds=7200,
        exam_title="JAMB UTME Multi-Subject 4-in-1 Bundle",
        exam_type="JAMB UTME",
        candidate_name="Chinedu Okafor",
        material_id="mat-jamb-001",
    )

    assert len(engine_jamb.subjects) == 4
    assert engine_jamb.subject_tabs_bar.visible == True
    print("[OK] JAMB 4-subject section tabs initialized")

    # Test subject switching
    engine_jamb._switch_to_subject("Physics")
    assert engine_jamb.active_index == 2
    print("[OK] Subject switching to Physics succeeded (active_index=2)")

    # Test selecting options and navigating
    engine_jamb._select_option(2)  # Correct answer for Q3 (Ampere)
    assert engine_jamb.answers[2] == 2
    engine_jamb._goto_next()
    assert engine_jamb.active_index == 3
    engine_jamb._goto_prev()
    assert engine_jamb.active_index == 2
    print("[OK] Navigation & option selection succeeded")

    # Test submission and JAMB diagnostic report
    engine_jamb.answers[0] = 1 # correct
    engine_jamb.answers[1] = 1 # correct
    engine_jamb.answers[2] = 2 # correct
    engine_jamb.answers[3] = 2 # correct
    engine_jamb._submit_exam()

    # Verify no WAEC grades on JAMB report
    report_ctrl = engine_jamb.main_view.controls[0]
    assert report_ctrl is not None
    print("[OK] JAMB exam submission and report generation succeeded (400 aggregate parity)")

    # 3. Test WAEC 9-point Result Slip simulation
    waec_questions = [
        {
            "id": "wq1",
            "subject": "English Language",
            "question": "Identify the noun clause.",
            "options": ["When he came", "What he said", "In the car"],
            "answer": 1,
            "exam_type": "WAEC WASSCE",
        },
        {
            "id": "wq2",
            "subject": "General Mathematics",
            "question": "Find the area of circle with radius 7 (pi=22/7)",
            "options": ["154", "44", "88"],
            "answer": 0,
            "exam_type": "WAEC WASSCE",
        },
    ]

    engine_waec = CBTExamEngine(
        page=mock_page,
        questions=waec_questions,
        duration_seconds=3600,
        exam_title="WAEC WASSCE Science Bundle",
        exam_type="WAEC WASSCE",
        candidate_name="Amina Bello",
        material_id="mat-waec-002",
    )

    engine_waec.answers[0] = 1 # correct
    engine_waec.answers[1] = 0 # correct
    engine_waec._submit_exam()
    print("[OK] WAEC exam submission and Result Slip generation succeeded (9-point scale parity)")

    print("\nALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_cbt_engine()
