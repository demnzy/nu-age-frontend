"""
Test suite for Coding Playground, Code Lab Upgrades, OOP Execution & Stdin Guidance.
"""
import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.utils.code_runner import (
    execute_python,
    execute_sql,
    detects_stdin,
)
from src.utils.playground_templates import LANGUAGES_METADATA, TEMPLATES
import flet as ft


def test_oop_and_classes():
    print("\n--- [1] Testing Python OOP & Class Creation ---")
    code = """
class Animal:
    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def speak(self) -> str:
        return "Generic sound"

class Dog(Animal):
    def speak(self) -> str:
        return f"{self.name} says Woof!"

dog = Dog("Buddy")
print(f"Dog: {dog.name}, says: {dog.speak()}")
"""
    result = execute_python(code)
    print("Result success:", result["success"])
    print("Result output:", result["output"].strip())
    assert result["success"], f"Failed to execute OOP code: {result['error']}"
    assert "Buddy says Woof!" in result["output"], "Expected output not found"
    print("[OK] Python OOP & Class creation PASSED!")


def test_dataclasses_and_safe_imports():
    print("\n--- [2] Testing Safe Imports & Dataclasses ---")
    code = """
from dataclasses import dataclass
import math

@dataclass
class Point:
    x: float
    y: float

    def distance_from_origin(self) -> float:
        return math.hypot(self.x, self.y)

p = Point(3.0, 4.0)
print(f"Distance: {p.distance_from_origin()}")
"""
    result = execute_python(code)
    print("Result success:", result["success"])
    print("Result output:", result["output"].strip())
    assert result["success"], f"Failed dataclass import test: {result['error']}"
    assert "Distance: 5.0" in result["output"]
    print("[OK] Dataclasses and safe math import PASSED!")


def test_stdin_and_eoferror():
    print("\n--- [3] Testing Stdin & Beginner EOFError Advice ---")
    # Test with provided stdin
    code = """
name = input("Enter name: ")
age = input("Enter age: ")
print(f"Hello {name}, you are {age} years old.")
"""
    result = execute_python(code, test_input="Alice\n25\n")
    print("Result with input success:", result["success"])
    print("Result output:", result["output"].strip())
    assert result["success"], f"Failed stdin test: {result['error']}"
    assert "Hello Alice, you are 25 years old." in result["output"]

    # Test with empty stdin -> should return helpful beginner tip
    result_empty = execute_python(code, test_input="")
    print("Result with empty input success (expected False):", result_empty["success"])
    print("Result with empty input error preview:\n", result_empty["error"])
    assert not result_empty["success"], "Should fail gracefully on empty input"
    assert "Beginner Tip:" in result_empty["error"], "Beginner Tip missing from EOFError advice"
    print("[OK] Stdin passing and beginner EOF advice PASSED!")


def test_detects_stdin_helper():
    print("\n--- [4] Testing detects_stdin Detection ---")
    assert detects_stdin("python", 'name = input("Name: ")') is True
    assert detects_stdin("python", "print('Hello World')") is False
    assert detects_stdin("cpp", "cin >> x;") is True
    assert detects_stdin("c", "scanf(\"%d\", &x);") is True
    assert detects_stdin("java", "Scanner sc = new Scanner(System.in);") is True
    assert detects_stdin("javascript", "const rl = readline.createInterface({ input: process.stdin });") is True
    assert detects_stdin("go", "fmt.Scanln(&x)") is True
    assert detects_stdin("rust", "io::stdin().read_line(&mut buffer)") is True
    print("[OK] detects_stdin detects across all supported languages PASSED!")


def test_multi_statement_sql():
    print("\n--- [5] Testing Multi-Statement SQL Sandbox ---")
    query = """
CREATE TABLE inventory (id INTEGER PRIMARY KEY, item TEXT, qty INTEGER);
INSERT INTO inventory (item, qty) VALUES ('Laptops', 10);
INSERT INTO inventory (item, qty) VALUES ('Monitors', 25);
SELECT item, qty FROM inventory WHERE qty > 15;
"""
    result = execute_sql(query)
    print("SQL Success:", result["success"])
    print("SQL Columns:", result["columns"])
    print("SQL Rows:", result["rows"])
    assert result["success"], f"Failed multi-statement SQL: {result['error']}"
    assert result["columns"] == ["item", "qty"]
    assert result["rows"] == [("Monitors", 25)]
    print("[OK] Multi-statement SQL Sandbox PASSED!")


def test_templates_metadata():
    print("\n--- [6] Testing Templates & Language Metadata ---")
    assert len(LANGUAGES_METADATA) >= 10, f"Expected 10 languages, got {len(LANGUAGES_METADATA)}"
    assert "python" in TEMPLATES
    py_template_names = [t["name"] for t in TEMPLATES["python"]]
    assert any("OOP & Classes" in name for name in py_template_names)
    assert any("Interactive Input" in name for name in py_template_names)
    assert "sql" in TEMPLATES
    sql_template_names = [t["name"] for t in TEMPLATES["sql"]]
    assert any("E-Commerce" in name for name in sql_template_names)
    print(f"[OK] Verified {len(LANGUAGES_METADATA)} languages and curated templates!")


async def test_ui_instantiations():
    print("\n--- [7] Testing Flet 0.86.5 UI Instantiations ---")
    # Mock Page
    mock_page = MagicMock(spec=ft.Page)
    mock_page.route = "/courses?tab=playground"
    mock_page.width = 1200
    mock_page.height = 800
    mock_page.session = MagicMock()
    mock_page.session.store = {"current_user": {"name": "Test User", "role": "LEARNER"}}
    mock_page.shared_preferences = MagicMock()
    mock_page.overlay = []
    mock_page.views = []
    mock_page.run_task = lambda func, *args, **kwargs: None
    mock_page.update = lambda: None

    # 1. Instantiate CodingPlayground component
    from src.components.coding_playground import CodingPlayground
    playground = CodingPlayground(mock_page)
    assert playground is not None
    print("[OK] CodingPlayground instantiated cleanly without AttributeError")

    # 2. Instantiate courses_view with playground section
    from src.courses import courses_view, SECTION_PLAYGROUND
    c_view = await courses_view(mock_page)
    assert isinstance(c_view, ft.View)
    print("[OK] courses_view with SECTION_PLAYGROUND instantiated cleanly")

    # 3. Verify course_page.py compilation & course_learner_view import
    import py_compile
    py_compile.compile("src/course_page.py", doraise=True)
    from src.course_page import course_learner_view
    assert course_learner_view is not None
    print("[OK] src/course_page.py compiled and verified cleanly")

    # 4. Instantiate render_preview_code_lab_ui in course_builder.py
    from src.course_builder import render_preview_code_lab_ui
    builder_lesson = {
        "id": "builder_les_01",
        "type": "code_lab",
        "content": {
            "language": "python",
            "instructions": "Test preview code lab in builder.",
            "starter_code": "x = input()\nprint(x)",
            "test_cases": [],
        },
        "_page": mock_page,
    }
    builder_lab_container = render_preview_code_lab_ui(builder_lesson)
    assert isinstance(builder_lab_container, ft.Container)
    print("[OK] course_builder.py render_preview_code_lab_ui instantiated cleanly with new Stdin drawer")


async def main():
    test_oop_and_classes()
    test_dataclasses_and_safe_imports()
    test_stdin_and_eoferror()
    test_detects_stdin_helper()
    test_multi_statement_sql()
    test_templates_metadata()
    await test_ui_instantiations()
    print("\n==========================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==========================================")


if __name__ == "__main__":
    asyncio.run(main())
