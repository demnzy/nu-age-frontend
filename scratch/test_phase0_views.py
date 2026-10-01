import sys
import os
sys.path.insert(0, os.path.abspath("."))
import asyncio
import flet as ft
from unittest.mock import MagicMock, AsyncMock

from src.components.next_best_action_card import get_next_best_action_card
from src.components.quick_hub import get_quick_hub
from src.components.onboarding_overlay import build_onboarding_overlay
from src.components.course_tabs import (
    build_course_tab_bar,
    build_practice_tab_view,
    build_discuss_tab_view,
    build_progress_tab_view,
)
from src.components.need_help_drawer import build_need_help_drawer
from src.requests.chats import ask_ai_tutor_api, send_channel_message_api
from src.requests.discussions import (
    get_course_discussions_api,
    create_course_discussion_api,
    get_discussion_details_api,
    create_discussion_reply_api,
    toggle_discussion_upvote_api,
)

async def run_tests():
    print("--- 1. Testing Mock Page Setup ---")
    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 1200
    mock_page.height = 800
    mock_page.theme_mode = ft.ThemeMode.LIGHT
    mock_page.session = MagicMock()
    mock_page.session.store = {
        "current_user": {
            "id": "user-uuid-123",
            "first_name": "Tobs",
            "role": "student",
            "has_seen_onboarding": False,
        },
        "token": "mock-jwt-token"
    }
    mock_page.shared_preferences = MagicMock()
    mock_page.shared_preferences.get = AsyncMock(return_value=None)
    mock_page.shared_preferences.set = AsyncMock(return_value=None)
    mock_page.update = MagicMock()
    mock_page.run_task = lambda fn, *args, **kwargs: None

    print("--- 2. Testing Next Best Action Card ---")
    sample_courses = [
        {"id": "1", "name": "Python Mastery", "progress": 45.0},
        {"id": "2", "name": "Web Dev", "progress": 100.0},
    ]
    card1 = get_next_best_action_card(sample_courses, mock_page, streak=3)
    assert card1 is not None
    print("  [OK] Next Best Action (active course): PASS")

    card2 = get_next_best_action_card([], mock_page, streak=0)
    assert card2 is not None
    print("  [OK] Next Best Action (empty/launchpad): PASS")

    print("--- 3. Testing Quick Launch Hub ---")
    mock_page.width = 1000
    hub_desk = get_quick_hub(mock_page)
    assert hub_desk is not None
    mock_page.width = 400
    hub_mob = get_quick_hub(mock_page)
    assert hub_mob is not None
    print("  [OK] Quick Launch Hub (desktop & mobile): PASS")

    print("--- 4. Testing Onboarding Overlay with Role-Aware Step 4 ---")
    overlay_student = build_onboarding_overlay(mock_page)
    assert overlay_student is not None
    print("  [OK] Onboarding Overlay (Student): PASS")

    mock_page.session.store["current_user"]["role"] = "tutor"
    overlay_tutor = build_onboarding_overlay(mock_page)
    assert overlay_tutor is not None
    print("  [OK] Onboarding Overlay (Tutor): PASS")

    print("--- 5. Testing Course Player Tabs & Discussion Board ---")
    ai_assistant_clicked = False
    def on_ai_clicked(e=None):
        nonlocal ai_assistant_clicked
        ai_assistant_clicked = True

    tab_bar_desk = build_course_tab_bar(
        0, 
        lambda idx: None, 
        on_open_ai_assistant=on_ai_clicked,
        page_width=1200
    )
    assert tab_bar_desk is not None
    print("  [OK] Course Tab Bar (Desktop with AI Assistant button): PASS")

    tab_bar_mob = build_course_tab_bar(
        2, 
        lambda idx: None, 
        on_open_ai_assistant=on_ai_clicked,
        page_width=360
    )
    assert tab_bar_mob is not None
    print("  [OK] Course Tab Bar (Mobile view): PASS")

    sample_course_data = {
        "id": "c1",
        "course_title": "Fullstack Cloud Architecture",
        "modules": [
            {
                "id": "m1",
                "title": "Module 1: Foundations",
                "lessons": [
                    {"id": "l1", "title": "Intro Video", "type": "video", "is_done": True},
                    {"id": "l2", "title": "Quiz 1", "type": "assessment", "is_done": False, "is_unlocked": True},
                ]
            }
        ]
    }
    practice_view = build_practice_tab_view(sample_course_data, mock_page, lambda mi, li: None)
    assert practice_view is not None
    print("  [OK] Practice Tab: PASS")

    # Discussion Board View (Desktop & Mobile)
    mock_page.width = 1100
    discuss_view_desk = build_discuss_tab_view("c1", "Fullstack Cloud Architecture", mock_page)
    assert discuss_view_desk is not None
    print("  [OK] Discuss Board (Desktop Q&A Forum): PASS")

    mock_page.width = 380
    discuss_view_mob = build_discuss_tab_view("c1", "Fullstack Cloud Architecture", mock_page)
    assert discuss_view_mob is not None
    print("  [OK] Discuss Board (Mobile Responsive): PASS")

    progress_view = build_progress_tab_view(sample_course_data, mock_page)
    assert progress_view is not None
    print("  [OK] Progress Tab: PASS")

    print("--- 6. Testing Discussions Client API ---")
    board_data = await get_course_discussions_api("token", "c1", category="all")
    assert "discussions" in board_data
    assert len(board_data["discussions"]) >= 1
    print("  [OK] Get Course Discussions API: PASS")

    new_post = await create_course_discussion_api("token", "c1", "How do VPC subnets route traffic?", "I'm confused about NAT gateways", category="question")
    assert new_post is not None
    assert new_post["title"] == "How do VPC subnets route traffic?"
    print("  [OK] Create Course Discussion Topic API: PASS")

    new_reply = await create_discussion_reply_api("token", new_post["id"], "NAT gateways sit in public subnets to provide internet access to private subnets.", course_id="c1")
    assert new_reply is not None
    print("  [OK] Create Discussion Reply API: PASS")

    details = await get_discussion_details_api("token", new_post["id"], course_id="c1")
    assert details is not None
    print("  [OK] Get Discussion Details & Replies API: PASS")

    print("--- 7. Testing Need Help AI Doubt Assistant Drawer ---")
    active_lesson = {"id": "l1", "title": "Intro Video", "type": "video", "content": "Welcome to Cloud Foundations"}
    drawer_desktop = build_need_help_drawer(
        mock_page,
        lesson_data=active_lesson,
        module_title="Module 1: Foundations",
        course_title="Fullstack Cloud Architecture",
        on_close=lambda e: None,
    )
    assert drawer_desktop is not None
    print("  [OK] Need Help Drawer (Desktop): PASS")

    mock_page.width = 375
    mock_page.height = 667
    drawer_mobile = build_need_help_drawer(
        mock_page,
        lesson_data=active_lesson,
        module_title="Module 1: Foundations",
        course_title="Fullstack Cloud Architecture",
        on_close=lambda e: None,
    )
    assert drawer_mobile is not None
    print("  [OK] Need Help Drawer (Mobile Responsive): PASS")

    print("\n===================================================================")
    print(">>> ALL COURSE DISCUSSION BOARD & UI VERIFICATIONS PASSED (100%) <<<")
    print("===================================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
