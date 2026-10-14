import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("src"))

import flet as ft
from src.components.learner_cohorts_hub import build_learner_cohorts_view
from src.cohort_page import cohort_page_view
from src.components.cohort_exam_runner import build_cohort_exam_view

class MockSharedPrefs:
    async def get(self, key):
        return "mock_token"
    async def set(self, key, val):
        pass

class MockWindow:
    width = 1200
    height = 900
    full_screen = False

class MockPage:
    def __init__(self):
        self.width = 1200
        self.height = 900
        self.window = MockWindow()
        self.shared_preferences = MockSharedPrefs()
        self.client_storage = MagicMock()
        self.client_storage.get.return_value = "mock_token"
        self.session = MagicMock()
        self.session.get.return_value = None
        self.overlay = []
        self.controls = []
        self.views = []
        self.route = "/cohorts/cohort-123"
        self.theme = None
        self.dark_theme = None
        self.theme_mode = ft.ThemeMode.LIGHT
        self.platform = "windows"

    def update(self):
        pass

    def go(self, route):
        self.route = route

    def run_task(self, fn, *args, **kwargs):
        pass

def find_all_text_values(control):
    texts = []
    if isinstance(control, str):
        return [control]
    if isinstance(control, ft.Text):
        if control.value:
            texts.append(control.value)
    if hasattr(control, "content") and control.content:
        texts.extend(find_all_text_values(control.content))
    if hasattr(control, "controls") and control.controls:
        for c in control.controls:
            texts.extend(find_all_text_values(c))
    return texts

async def test_ux_states():
    page = MockPage()

    print("--- 1. Testing build_cohort_exam_view when UNSTARTED (is_resumed=False) ---")
    unstarted_payload = {
        "exam_title": "Full-Stack Final Exam",
        "duration_minutes": 45,
        "max_attempts": 3,
        "pass_percentage": 75.0,
        "instructions": "Answer all questions carefully.",
        "questions": [
            {
                "id": "q1",
                "question_text": "What is Python?",
                "options": ["A snake", "A language", "Both"],
            }
        ],
        "remaining_seconds": 2700,
        "total_duration_minutes": 45,
        "total_duration_seconds": 2700,
        "max_attempts": 3,
        "completed_attempts": 0,
        "attempts_left": 3,
        "is_resumed": False,
        "is_in_progress": False,
    }
    runner_unstarted = build_cohort_exam_view(
        page, unstarted_payload, "org-1", "c-1", "exam-1", "mock_token", lambda: None
    )
    texts_unstarted = find_all_text_values(runner_unstarted)
    print("Briefing text candidates:", [t for t in texts_unstarted if "ASSESSMENT" in t.upper() or "BEGIN" in t.upper() or "RESUME" in t.upper()])
    has_begin = any("BEGIN ASSESSMENT" in t.upper() for t in texts_unstarted)
    has_resume = any("RESUME ASSESSMENT" in t.upper() for t in texts_unstarted)
    print(f"  - Has 'Begin Assessment': {has_begin}")
    print(f"  - Has 'Resume Assessment': {has_resume}")
    assert has_begin, "Unstarted exam briefing MUST say 'Begin Assessment'"
    assert not has_resume, "Unstarted exam briefing MUST NOT say 'Resume Assessment'"

    print("\n--- 2. Testing build_cohort_exam_view when IN PROGRESS (is_resumed=True) ---")
    resumed_payload = {
        "exam_title": "Full-Stack Final Exam",
        "duration_minutes": 45,
        "max_attempts": 3,
        "pass_percentage": 75.0,
        "instructions": "Answer all questions carefully.",
        "questions": [
            {
                "id": "q1",
                "question_text": "What is Python?",
                "options": ["A snake", "A language", "Both"],
            }
        ],
        "remaining_seconds": 1500,
        "total_duration_minutes": 45,
        "total_duration_seconds": 2700,
        "max_attempts": 3,
        "completed_attempts": 0,
        "attempts_left": 3,
        "is_resumed": True,
        "is_in_progress": True,
    }
    runner_resumed = build_cohort_exam_view(
        page, resumed_payload, "org-1", "c-1", "exam-1", "mock_token", lambda: None
    )
    texts_resumed = find_all_text_values(runner_resumed)
    has_begin_r = any("BEGIN ASSESSMENT" in t.upper() for t in texts_resumed)
    has_resume_r = any("RESUME ASSESSMENT" in t.upper() for t in texts_resumed)
    print(f"  - Has 'Begin Assessment': {has_begin_r}")
    print(f"  - Has 'Resume Assessment': {has_resume_r}")
    assert has_resume_r, "Resumed exam briefing MUST say 'Resume Assessment'"
    assert not has_begin_r, "Resumed exam briefing MUST NOT say 'Begin Assessment'"

    print("\n--- 3. Testing build_learner_cohorts_view component instantiation ---")
    hub = build_learner_cohorts_view(page, token="mock_token", initial_cohort_id="cohort-123")
    assert isinstance(hub, ft.Container)
    print("Learner cohorts hub instantiated cleanly!")

    print("\n--- 4. Testing cohort_page_view component instantiation ---")
    # Mock network call in cohort_page_view
    import src.cohort_page as cp
    original_get = cp.get_learner_cohorts
    unstarted_cohort = {
        "id": "cohort-123",
        "organisation_id": "org-1",
        "name": "Test Cohort",
        "description": "A cohort for testing",
        "start_date": "2026-09-01T00:00:00Z",
        "end_date": "2026-10-01T00:00:00Z",
        "status": "active",
        "courses": [],
        "exams": [
            {
                "id": "exam-1",
                "title": "React Architecture Exam",
                "duration_minutes": 45,
                "pass_percentage": 70,
                "max_attempts": 3,
                "completed_attempts": 0,
                "attempts_left": 3,
                "is_in_progress": False,
                "in_progress_submission": None,
                "user_submission": None,
                "status": "OPEN_NOW",
                "opens_at": "2026-09-01T00:00:00Z",
                "closes_at": "2026-10-01T00:00:00Z",
            }
        ]
    }
    # 4A. Test urgent banner with unstarted exam
    cp.get_learner_cohorts = AsyncMock(return_value={
        "cohorts": [unstarted_cohort],
        "active_urgent_exams": [unstarted_cohort["exams"][0]],
    })
    cview_urgent = await cohort_page_view(page, "cohort-123")
    assert isinstance(cview_urgent, ft.View)
    cview_urgent_texts = find_all_text_values(cview_urgent)
    print("Cohort page (unstarted urgent banner) texts:", [t for t in cview_urgent_texts if "NOT STARTED" in t.upper() or "START" in t.upper() or "RESUME" in t.upper()])
    has_not_started_banner = any("LIVE ASSESSMENT AVAILABLE · NOT STARTED" in t.upper() for t in cview_urgent_texts)
    has_start_exam_btn = any("START ASSESSMENT" in t.upper() for t in cview_urgent_texts)
    has_resume_on_unstarted = any("RESUME" in t.upper() for t in cview_urgent_texts)
    print(f"  - Has 'Live Assessment Available · Not Started' banner: {has_not_started_banner}")
    print(f"  - Has 'Start Assessment' button: {has_start_exam_btn}")
    print(f"  - Has 'Resume' on unstarted: {has_resume_on_unstarted}")
    assert has_not_started_banner, "Urgent banner must say 'Live Assessment Available · Not Started'"
    assert has_start_exam_btn, "Urgent banner must show 'Start Assessment'"
    assert not has_resume_on_unstarted, "Urgent banner MUST NOT say Resume when exam is unstarted"

    # 4B. Test with in-progress attempt on cohort page urgent banner
    inprog_cohort = {
        "id": "cohort-123",
        "organisation_id": "org-1",
        "name": "Test Cohort",
        "description": "A cohort for testing",
        "start_date": "2026-09-01T00:00:00Z",
        "end_date": "2026-10-01T00:00:00Z",
        "status": "active",
        "courses": [],
        "exams": [
            {
                "id": "exam-1",
                "title": "React Architecture Exam",
                "duration_minutes": 45,
                "pass_percentage": 70,
                "max_attempts": 3,
                "completed_attempts": 0,
                "attempts_left": 3,
                "is_in_progress": True,
                "in_progress_submission": {"id": "sub1", "attempt_number": 1},
                "user_submission": {"id": "sub1", "status": "in_progress"},
                "status": "OPEN_NOW",
                "opens_at": "2026-09-01T00:00:00Z",
                "closes_at": "2026-10-01T00:00:00Z",
            }
        ]
    }
    cp.get_learner_cohorts = AsyncMock(return_value={
        "cohorts": [inprog_cohort],
        "active_urgent_exams": [inprog_cohort["exams"][0]],
    })
    cview_inprog = await cohort_page_view(page, "cohort-123")
    cview_inprog_texts = find_all_text_values(cview_inprog)
    has_inprog_banner = any("EXAM IN PROGRESS" in t.upper() for t in cview_inprog_texts)
    has_resume_exam_btn = any("RESUME EXAM" in t.upper() for t in cview_inprog_texts)
    print(f"\nCohort page (in-progress urgent banner) test:")
    print(f"  - Has 'Exam In Progress' banner: {has_inprog_banner}")
    print(f"  - Has 'Resume Exam' button: {has_resume_exam_btn}")
    assert has_inprog_banner, "Urgent banner must say Exam In Progress when attempt is active"
    assert has_resume_exam_btn, "Urgent banner must show Resume Exam button when attempt is active"

    cp.get_learner_cohorts = original_get
    print("\nALL UX VERIFICATION CHECKS PASSED WITH 100% ACCURACY!")
    print("\nALL UX VERIFICATION CHECKS PASSED WITH 100% ACCURACY!")

if __name__ == "__main__":
    asyncio.run(test_ux_states())
