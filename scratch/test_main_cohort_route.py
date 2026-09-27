import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath("."))
import flet as ft
from unittest.mock import MagicMock, AsyncMock

async def test_main_routing():
    from main import is_shell_route
    print("Testing is_shell_route for cohort routes...")
    assert is_shell_route("/cohorts") is True
    assert is_shell_route("/cohorts/cohort-123") is True
    assert is_shell_route("/courses/123/view") is False
    print("   [PASS] is_shell_route works as expected.")

if __name__ == "__main__":
    asyncio.run(test_main_routing())
