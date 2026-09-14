import sys
sys.path.append(".")
import flet as ft

from unittest.mock import MagicMock

# Create a mock page to test main's skeleton functions
mock_page = MagicMock(spec=ft.Page)
mock_page.width = 1000
mock_page.height = 800
mock_page.views = []

# Test compiling main.py
import py_compile
py_compile.compile("main.py", doraise=True)
print("main.py compiled successfully!")

# Let's extract and test _layout_self_study and _collect_boxes directly or by executing
# We can import main or execute the helper in isolation:
def shimmer_box(radius=12, height=None, width=None, expand=False):
    box = ft.Container(
        expand=True if ((height is None and width is None) or expand) else None,
        height=height,
        width=width,
        border_radius=radius,
        bgcolor=ft.Colors.OUTLINE,
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
        opacity=0.35,
    )
    box.data = "shimmer_box"
    return box

def _collect_boxes(control):
    boxes = []

    def walk(c):
        if isinstance(c, ft.Container):
            if getattr(c, "data", None) == "shimmer_box":
                boxes.append(c)
            if c.content is not None:
                walk(c.content)
        elif isinstance(c, (ft.Row, ft.Column, ft.ResponsiveRow, ft.ListView)):
            for child in (c.controls or []):
                walk(child)

    walk(control)
    return boxes

# Let's test the layout instantiation
# We can read the layout code from main.py
import ast
with open("main.py", "r", encoding="utf-8") as f:
    code = f.read()

# Verify that _layout_self_study is in main.py
assert "def _layout_self_study():" in code
print("Found _layout_self_study in main.py!")

# Let's run a test by importing or simulating it
loc = {"ft": ft, "shimmer_box": shimmer_box, "_collect_boxes": _collect_boxes}
# Extract _layout_self_study function
tree = ast.parse(code)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "_layout_self_study":
        module_def = ast.Module(body=[node], type_ignores=[])
        compiled = compile(module_def, "<string>", "exec")
        exec(compiled, loc)
        break

_layout_self_study = loc["_layout_self_study"]
layout = _layout_self_study()
assert layout is not None
print(f"Layout created: {type(layout).__name__}")

boxes = _collect_boxes(layout)
print(f"Total shimmer boxes collected: {len(boxes)}")
assert len(boxes) > 15, "Expected many shimmer boxes to be gathered"

for i, box in enumerate(boxes):
    assert box.data == "shimmer_box"

print("All tests passed successfully!")
