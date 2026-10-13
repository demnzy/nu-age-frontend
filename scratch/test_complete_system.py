import sys, os
sys.path.insert(0, os.path.abspath("."))
import asyncio
from unittest.mock import MagicMock, AsyncMock
import flet as ft

from src.utils.code_runner import run_code_lab_tests, execute_python, execute_sql, execute_remote_code
from src.course_settings import course_settings_view

async def run_all_tests():
    print("========================================")
    print("RUNNING COMPLETE COMPREHENSIVE TEST SUITE")
    print("========================================")

    # 1. Test CodeLab Local Python
    res_py = run_code_lab_tests("python", "print(10 + 20)", "", [{"description": "Addition", "expected_output": "30"}])
    assert res_py[0]["passed"], "Python test failed"
    print("[OK] [1/5] Python CodeLab Passed (Offline capable)")

    # 2. Test CodeLab Local SQLite
    res_sql = run_code_lab_tests("sql", "SELECT 42 AS val;", "", [{"description": "Select", "expected_output": "42"}])
    assert res_sql[0]["passed"], "SQL test failed"
    print("[OK] [2/5] SQLite CodeLab Passed (Offline capable)")

    # 3. Test CodeLab Remote C++
    res_cpp = run_code_lab_tests("cpp", '#include <iostream>\nint main(){ std::cout << "C++ SUCCESS"; return 0; }', "", [{"description": "Output", "expected_output": "C++ SUCCESS"}])
    assert res_cpp[0]["passed"], "C++ test failed"
    print("[OK] [3/5] C++ Remote CodeLab Execution Passed")

    # 4. Test CodeLab Offline Graceful Fallback (Simulated network drop)
    import httpx
    from unittest.mock import patch
    with patch("httpx.Client.post", side_effect=httpx.ConnectError("No internet connection")):
        res_offline = run_code_lab_tests("cpp", '#include <iostream>\nint main(){ return 0; }', "", [{"description": "Offline Check", "expected_output": ""}])
        assert res_offline[0]["offline_blocked"] == True
        assert not res_offline[0]["passed"]
        assert "internet connection is required" in res_offline[0]["error"].lower()
    print("[OK] [4/5] CodeLab Offline Graceful Fallback Verified")

    # 5. Test Course Settings View Instantiation
    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 1280
    mock_page.height = 800
    mock_page.session = MagicMock()
    mock_page.session.store = {"current_org_id": "org-xyz"}
    mock_page.shared_preferences = AsyncMock()
    mock_page.shared_preferences.get = AsyncMock(return_value="mock_token")
    mock_page.views = []
    mock_page.overlay = []

    # Call course_settings_view with keyword parameters as fixed in main.py
    v = await course_settings_view(mock_page, course_id="course-123", org_id="org-xyz")
    assert v is not None
    assert "/organisations/org-xyz/courses/course-123/settings" in v.route or "/courses/course-123/settings" in v.route
    print("[OK] [5/5] Course Settings View Instantiated with Correct Route & Argument Mapping")

    print("\n========================================")
    print("ALL 5/5 SYSTEM TESTS COMPLETED SUCCESSFULLY!")
    print("========================================")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
