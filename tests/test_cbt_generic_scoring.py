import sys
import os
import unittest
from unittest.mock import MagicMock

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import flet as ft
from src.components.cbt_exam_engine import CBTExamEngine
from src.components.question_curator_modal import show_question_curator_dialog
import inspect

def extract_all_text(control):
    texts = []
    if isinstance(control, ft.Text):
        if control.value:
            texts.append(str(control.value))
    if hasattr(control, "content") and control.content:
        texts.extend(extract_all_text(control.content))
    if hasattr(control, "controls") and control.controls:
        for c in control.controls:
            texts.extend(extract_all_text(c))
    return texts

class TestCBTGenericScoring(unittest.TestCase):
    def setUp(self):
        self.mock_page = MagicMock(spec=ft.Page)
        self.mock_page.width = 1000
        self.mock_page.height = 800
        self.mock_page.overlay = []

        dummy_questions = [
            {
                "id": "q1",
                "question": "What is 2+2?",
                "options": ["1", "2", "3", "4"],
                "answer": 3,
                "explanation": "2+2=4",
                "subject": "Mathematics",
            }
        ]
        self.engine = CBTExamEngine(
            page=self.mock_page,
            questions=dummy_questions,
            exam_title="Test Exam",
            exam_type="General CBT"
        )

    def test_general_cbt_summary_card_rendering(self):
        """Verify summary card for general exam renders percentage & raw score without JAMB aggregate."""
        card = self.engine._build_cbt_summary_card(
            score=8,
            percentage=80.0,
            is_jamb=False,
            is_waec=False,
            jamb_aggregate=0,
            jamb_tier_title="",
            jamb_tier_desc="",
            jamb_tier_col="#F59E0B",
            waec_credit_passes=0,
            overall_waec_grade="F9",
            overall_waec_label="Fail",
            overall_waec_credit=False,
            overall_waec_col="#EF4444",
            subject_results=[{"subject": "Mathematics", "correct": 8, "total": 10, "scaled": 80, "percentage": 80}],
            past_attempts=[],
            topic_stats={}
        )
        self.assertIsInstance(card, ft.Control)
        all_text = " ".join(extract_all_text(card))
        self.assertIn("Raw Accuracy", all_text)
        self.assertIn("80.0%", all_text)
        self.assertIn("Exam Completed", all_text)
        self.assertNotIn("Official JAMB UTME Aggregate", all_text)
        self.assertNotIn("Competitive Merit Tier", all_text)

    def test_jamb_summary_card_rendering(self):
        """Verify summary card for real JAMB exam renders JAMB aggregate score."""
        card = self.engine._build_cbt_summary_card(
            score=40,
            percentage=80.0,
            is_jamb=True,
            is_waec=False,
            jamb_aggregate=320,
            jamb_tier_title="Competitive Merit Tier",
            jamb_tier_desc="Eligible for top programs",
            jamb_tier_col="#10B981",
            waec_credit_passes=0,
            overall_waec_grade="F9",
            overall_waec_label="Fail",
            overall_waec_credit=False,
            overall_waec_col="#EF4444",
            subject_results=[{"subject": "Physics", "correct": 40, "total": 50, "scaled": 80, "percentage": 80}],
            past_attempts=[],
            topic_stats={}
        )
        self.assertIsInstance(card, ft.Control)
        all_text = " ".join(extract_all_text(card))
        self.assertIn("Official JAMB UTME Aggregate", all_text)
        self.assertIn("Competitive Merit Tier", all_text)
        self.assertIn("320", all_text)
        self.assertIn("/ 400", all_text)

    def test_cbt_exam_engine_default_exam_type(self):
        """Verify CBTExamEngine defaults to General CBT."""
        sig = inspect.signature(CBTExamEngine.__init__)
        self.assertEqual(sig.parameters["exam_type"].default, "General CBT")

    def test_question_curator_default_exam_type(self):
        """Verify question curator dialog defaults to General CBT."""
        sig = inspect.signature(show_question_curator_dialog)
        self.assertEqual(sig.parameters["exam_type"].default, "General CBT")

if __name__ == "__main__":
    unittest.main()
