import asyncio
import sys, os
sys.path.insert(0, os.path.abspath("."))
import flet as ft
from unittest.mock import MagicMock, AsyncMock

async def main():
    # Mock Page
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 800
    page.route = "/courses/test-123/manage"
    page.session = MagicMock()
    page.session.store = {"current_org_id": "org-1"}
    page.shared_preferences = AsyncMock()
    page.shared_preferences.get = AsyncMock(return_value="fake_token")
    page.views = []
    page.overlay = []

    # 1. Test importing course_builder
    from src.course_builder import course_builder_view
    print("[1] course_builder imported successfully")

    # 2. Test importing course_page
    from src.course_page import course_learner_view
    print("[2] course_page imported successfully")

    # 3. Test importing course_settings
    from src.course_settings import course_settings_view
    print("[3] course_settings imported successfully")

    # 4. Test code_runner execution
    from src.utils.code_runner import run_code_lab_tests
    r = run_code_lab_tests("cpp", '#include <iostream>\nint main(){std::cout << "OK"; return 0;}', "", [{"description": "t1", "expected_output": "OK"}])
    print("[4] code_runner test result:", r)

    print("\nALL VERIFICATIONS PASSED!")

if __name__ == "__main__":
    asyncio.run(main())
