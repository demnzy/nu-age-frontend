import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flet as ft
from unittest.mock import MagicMock, AsyncMock, patch
from src.org_view import organisations_view

mock_org = {
    "id": "584b537e-6521-4852-a7e4-18f6c095126d",
    "name": "Apex Engineering Institute",
    "email": "contact@apex.edu",
    "owner_id": "owner-1234-uuid",
    "logo": "",
    "theme_color": "#4338CA",
    "plan": {"name": "Enterprise Academy", "max_members": 100, "max_courses": 50, "features": []}
}

mock_members = [
    {"id": "user-owner", "first_name": "Daniel", "last_name": "Davids", "email": "daniel@apex.edu", "role": "OWNER"},
    {"id": "user-teacher-1", "first_name": "Sarah", "last_name": "Connor", "email": "sarah@apex.edu", "role": "TEACHER"},
    {"id": "user-teacher-2", "first_name": "Ada", "last_name": "Lovelace", "email": "ada@apex.edu", "role": "TEACHER"},
    {"id": "user-student", "first_name": "Alex", "last_name": "Rivera", "email": "alex.r@apex.edu", "role": "STUDENT"},
]

mock_courses = [
    {
        "id": "c-1",
        "name": "Cloud Computing 101",
        "description": "AWS & Azure.",
        "public": "true",
        "total_students": 45,
        "category_id": "cat-cloud",
        "category": {"id": "cat-cloud", "name": "Cloud Infrastructure"},
        "teacher_id": "user-teacher-1"
    },
    {
        "id": "c-2",
        "name": "Algorithms & Complexity",
        "description": "Sorting, graphs.",
        "public": "organisation",
        "total_students": 30,
        "category_id": "cat-cs",
        "category": {"id": "cat-cs", "name": "Computer Science"},
        "teacher_id": "user-teacher-2"
    },
    {
        "id": "c-3",
        "name": "Container Orchestration",
        "description": "Kubernetes.",
        "public": "organisation",
        "total_students": 12,
        "category_id": "cat-cloud",
        "category": {"id": "cat-cloud", "name": "Cloud Infrastructure"},
        "teacher_id": "user-teacher-1"
    },
]

mock_categories = [
    {"id": "cat-cloud", "name": "Cloud Infrastructure"},
    {"id": "cat-cs", "name": "Computer Science"},
]

async def test_filtering():
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 800
    page.session = MagicMock()
    page.session.store = {"current_user": {"id": "owner-1234-uuid", "role": "OWNER"}}
    page.shared_preferences = MagicMock()
    page.shared_preferences.get = AsyncMock(return_value="mock_jwt_token")
    page.go = MagicMock()
    page.update = MagicMock()
    page.overlay = []
    page.show_dialog = MagicMock()

    tasks = []
    def run_task(handler, *args):
        task = asyncio.create_task(handler(*args))
        tasks.append(task)
        return task
    page.run_task = run_task

    with patch("src.org_view.get_my_organisation", new=AsyncMock(return_value=mock_org)), \
         patch("src.org_view.get_organisation_members", new=AsyncMock(return_value=mock_members)), \
         patch("src.org_view.get_organisation_courses", new=AsyncMock(return_value=mock_courses)), \
         patch("src.org_view.get_org_playlists", new=AsyncMock(return_value=[])), \
         patch("src.org_view.get_categories", new=AsyncMock(return_value=mock_categories)):

        view = await organisations_view(page)
        await asyncio.gather(*tasks)

        content_socket = view.controls[0].content
        dashboard_col = content_socket.content
        body_col = dashboard_col.controls[1].content
        tab_content_wrapper = body_col.controls[4]
        tab_content = tab_content_wrapper.content.content

        dialogs_shown = []
        page.show_dialog = lambda d: dialogs_shown.append(d)

        # Initial render: all 3 courses shown
        courses_grid = tab_content.controls[3]
        assert len(courses_grid.controls) == 3, f"Expected 3 courses initially, got {len(courses_grid.controls)}"
        print("Verified: Initial course count = 3")

        # 1. Test Category Filter Drawer -> Click Category Chip
        filter_bar = tab_content.controls[2]
        cat_chip = filter_bar.controls[4]
        cat_chip.on_click(None)

        assert len(dialogs_shown) >= 1
        cat_sheet = dialogs_shown[-1]
        assert isinstance(cat_sheet, ft.BottomSheet)
        sheet_container = cat_sheet.content
        sheet_col = sheet_container.content
        assert sheet_col.controls[0].controls[0].value == "Filter by Category"
        rg = sheet_col.controls[2].content
        options = [r.label for r in rg.content.controls]
        assert "Computer Science" in options
        assert "Cloud Infrastructure" in options
        print(f"Verified: Category BottomSheet drawer opened with options = {options}!")

        # Select "Computer Science" via drawer RadioGroup
        ev = MagicMock()
        ev.control = MagicMock()
        ev.control.value = "Computer Science"
        rg.on_change(ev)

        updated_tab_content = tab_content_wrapper.content.content
        updated_grid = updated_tab_content.controls[3]
        assert len(updated_grid.controls) == 1
        filtered_card = updated_grid.controls[0].content
        card_title = filtered_card.content.controls[1].content.controls[0].value
        assert card_title == "Algorithms & Complexity"
        print(f"Verified: Category filter isolated '{card_title}' (1 course)!")

        # 2. Reset Category Filter via drawer Reset button
        reset_btn = sheet_col.controls[4]
        reset_btn.on_click(None)
        assert len(tab_content_wrapper.content.content.controls[3].controls) == 3
        print("Verified: Category filter reset back to 3 courses!")

        # 3. Test Instructor Filter Drawer -> Click Instructor Chip
        inst_chip = tab_content_wrapper.content.content.controls[2].controls[5]
        inst_chip.on_click(None)

        assert len(dialogs_shown) >= 2
        inst_sheet = dialogs_shown[-1]
        assert isinstance(inst_sheet, ft.BottomSheet)
        inst_sheet_col = inst_sheet.content.content
        assert inst_sheet_col.controls[0].controls[0].value == "Filter by Instructor"
        inst_rg = inst_sheet_col.controls[2].content
        inst_options = [r.label for r in inst_rg.content.controls]
        assert "Sarah Connor" in inst_options
        print(f"Verified: Instructor BottomSheet drawer opened with options = {inst_options}!")

        # Select "Sarah Connor"
        ev.control.value = "Sarah Connor"
        inst_rg.on_change(ev)

        teacher_filtered_grid = tab_content_wrapper.content.content.controls[3]
        assert len(teacher_filtered_grid.controls) == 2
        print("Verified: Instructor filter isolated 2 courses taught by Sarah Connor!")

        # 4. Combine Filters: Instructor "Sarah Connor" + Status "campus" (should only show Container Orchestration)
        status_chips_row = tab_content_wrapper.content.content.controls[2]
        campus_chip = status_chips_row.controls[2] # All, Public, Campus, Drafts
        campus_chip.on_click(None)

        combo_grid = tab_content_wrapper.content.content.controls[3]
        assert len(combo_grid.controls) == 1
        combo_card = combo_grid.controls[0].content
        combo_title = combo_card.content.controls[1].content.controls[0].value
        assert combo_title == "Container Orchestration"
        print(f"Verified: Combined status ('Campus') + instructor filter isolated '{combo_title}'!")

        print("\nALL CATEGORY & INSTRUCTOR DRAWER FILTERING TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_filtering())
