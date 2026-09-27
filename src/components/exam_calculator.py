"""
In-Exam Floating Calculator Component for NU-Age Assessment Runner.
Provides Basic and Scientific calculator modes with an extensive mathematical engine:
  * Full-width right-aligned digital display (expression history line + active input/result)
  * Implicit multiplication inference: 2(3) -> 6, (2+3)(4) -> 20, 5sin(30) -> 2.5, 2pi -> 6.283
  * Auto-parentheses and smart bracket balancing on evaluation
  * Dedicated 'Ans' memory register
  * Clean typing reset when entering digits after '='
  * Chained operations from previous answer when entering operators
  * Universal candidate branding as 'Calculator'
"""

import math
import re
import flet as ft


def _safe_evaluate_expression(expr: str, ans_val: float = 0.0) -> str:
    """Safely evaluates mathematical expressions supporting basic arithmetic,
    implicit multiplication, trigonometry (in degrees), logarithms, powers,
    roots, and constants without eval() arbitrary code execution risks."""
    if not expr or not expr.strip():
        return "0"

    cleaned = expr.strip()

    # Normalize mathematical operator symbols and unicode constants
    cleaned = cleaned.replace("×", "*").replace("÷", "/").replace("−", "-").replace("π", "pi")
    cleaned = cleaned.replace("^", "**")

    # ── Implicit Multiplication Inference ─────────────────────────────────
    # 1. Number before opening parenthesis: 2(3) -> 2*(3)
    cleaned = re.sub(r"(\d)\s*\(", r"\1*(", cleaned)
    # 2. Closing parenthesis before opening parenthesis: (2)(3) -> (2)*(3)
    cleaned = re.sub(r"\)\s*\(", r")*(", cleaned)
    # 3. Closing parenthesis before number: (2)3 -> (2)*3
    cleaned = re.sub(r"\)\s*(\d)", r")*\1", cleaned)
    # 4. Number or closing parenthesis before function, constant, or variable: 5sin(30) -> 5*sin(30), 2pi -> 2*pi, 2Ans -> 2*Ans
    cleaned = re.sub(
        r"(\d|\))\s*(sin|cos|tan|asin|acos|atan|sqrt|log|ln|abs|pi|e|Ans)\b",
        r"\1*\2",
        cleaned,
        flags=re.IGNORECASE,
    )
    # 5. Constant or variable before opening parenthesis: pi(2) -> pi*(2), Ans(3) -> Ans*(3)
    cleaned = re.sub(
        r"\b(pi|e|Ans)\s*\(",
        r"\1*(",
        cleaned,
        flags=re.IGNORECASE,
    )

    # ── Auto-Parentheses Balancing ────────────────────────────────────────
    # If the user left trailing unclosed parentheses e.g. log(100 or 2*(3+4, automatically balance them
    open_count = cleaned.count("(")
    close_count = cleaned.count(")")
    if open_count > close_count:
        cleaned += ")" * (open_count - close_count)

    # Safe evaluation environment
    safe_env = {
        "sin": lambda x: math.sin(math.radians(x)),
        "cos": lambda x: math.cos(math.radians(x)),
        "tan": lambda x: math.tan(math.radians(x)),
        "asin": lambda x: math.degrees(math.asin(x)),
        "acos": lambda x: math.degrees(math.acos(x)),
        "atan": lambda x: math.degrees(math.atan(x)),
        "sqrt": math.sqrt,
        "log": math.log10,
        "ln": math.log,
        "abs": abs,
        "pi": math.pi,
        "e": math.e,
        "Ans": ans_val,
    }

    # Reject any non-whitelisted characters
    if not re.match(r"^[\d\.\+\-\*\/\(\)\%\,\s\w]+$", cleaned):
        return "Error"

    # Only allow whitelisted function names
    found_words = re.findall(r"[a-zA-Z_]\w*", cleaned)
    for word in found_words:
        if word not in safe_env:
            return "Error"

    try:
        # Safe evaluation with restricted globals
        result = eval(cleaned, {"__builtins__": None}, safe_env)
        if isinstance(result, float):
            if math.isnan(result) or math.isinf(result):
                return "Error"
            if result.is_integer():
                return f"{int(result)}"
            # Round float cleanly without scientific notation artifacts
            rounded = round(result, 8)
            if rounded.is_integer():
                return f"{int(rounded)}"
            return f"{rounded:g}"
        elif isinstance(result, int):
            return f"{result}"
        return str(result)
    except Exception:
        return "Error"


def build_exam_calculator(page: ft.Page, calculator_type: str = "basic", on_close=None) -> ft.Container:
    """Constructs an extensive, sleek floating calculator overlay card for candidates."""
    is_scientific = (calculator_type == "scientific")

    state = {
        "formula": "",
        "history": "",
        "has_evaluated": False,
        "ans": "0",
    }

    expr_text = ft.Text(
        "",
        size=11,
        color=ft.Colors.ON_SURFACE_VARIANT,
        text_align=ft.TextAlign.RIGHT,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    display_text = ft.Text(
        "0",
        size=22,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.ON_SURFACE,
        text_align=ft.TextAlign.RIGHT,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    def refresh_display():
        expr_text.value = state["history"]
        display_text.value = state["formula"] if state["formula"] else "0"
        page.update()

    def handle_btn_click(val: str):
        f = state["formula"]
        if val == "AC":
            state["formula"] = ""
            state["history"] = ""
            state["has_evaluated"] = False
        elif val == "C":
            state["formula"] = ""
            if state["has_evaluated"]:
                state["history"] = ""
                state["has_evaluated"] = False
        elif val == "⌫":
            if state["has_evaluated"]:
                state["formula"] = ""
                state["history"] = ""
                state["has_evaluated"] = False
            elif f:
                if f.endswith("Ans"):
                    state["formula"] = f[:-3]
                elif f.endswith(" "):
                    state["formula"] = f.rstrip()[:-1].rstrip()
                elif f.endswith(("sin(", "cos(", "tan(", "log(", "ln(")):
                    state["formula"] = f[: f.rfind("(") - 2] if f.endswith("ln(") else f[: f.rfind("(") - 3]
                elif f.endswith("sqrt("):
                    state["formula"] = f[:-5]
                else:
                    state["formula"] = f[:-1]
        elif val == "Ans":
            if state["has_evaluated"] or not f or f == "0":
                state["formula"] = "Ans"
                state["history"] = ""
                state["has_evaluated"] = False
            elif f.endswith((" ", "(", "+", "−", "×", "÷", "%", "^")):
                state["formula"] += "Ans"
            else:
                state["formula"] += " × Ans"
        elif val in ("+", "−", "×", "÷", "%", "^"):
            if state["has_evaluated"]:
                state["formula"] = f"Ans {val} "
                state["has_evaluated"] = False
            elif not f or f == "0":
                if val in ("+", "−"):
                    state["formula"] = f"{val} "
                else:
                    state["formula"] = f"Ans {val} "
            elif f.endswith((" + ", " − ", " × ", " ÷ ", " % ", " ^ ")):
                state["formula"] = f[:-3] + f" {val} "
            elif f.endswith(" "):
                state["formula"] = f.rstrip() + f" {val} "
            else:
                state["formula"] += f" {val} "
        elif val in ("sin", "cos", "tan", "sqrt", "log", "ln"):
            if state["has_evaluated"] or not f or f == "0":
                state["formula"] = f"{val}("
                state["history"] = ""
                state["has_evaluated"] = False
            elif f.endswith((" ", "(", "+", "−", "×", "÷", "%", "^")):
                state["formula"] += f"{val}("
            else:
                state["formula"] += f" × {val}("
        elif val in ("(", ")", "π", "e"):
            if state["has_evaluated"] or not f or f == "0":
                state["formula"] = val
                state["history"] = ""
                state["has_evaluated"] = False
            else:
                state["formula"] += val
        elif val == ".":
            if state["has_evaluated"] or not f or f == "0":
                state["formula"] = "0."
                state["history"] = ""
                state["has_evaluated"] = False
            else:
                last_part = re.split(r"[\s\+\−\×\÷\%\^\(\)]", f)[-1]
                if "." not in last_part:
                    state["formula"] += "."
        elif val == "+/-":
            if state["has_evaluated"]:
                state["formula"] = f"-({state['formula']})"
                state["has_evaluated"] = False
            elif f and f != "0":
                if f.startswith("-"):
                    state["formula"] = f[1:]
                else:
                    state["formula"] = "-" + f
        elif val == "=":
            expr_to_eval = f.strip()
            if expr_to_eval:
                try:
                    ans_float = float(state["ans"] or 0)
                except Exception:
                    ans_float = 0.0
                result = _safe_evaluate_expression(expr_to_eval, ans_val=ans_float)
                if result != "Error":
                    state["ans"] = result
                state["history"] = expr_to_eval + " ="
                state["formula"] = result
                state["has_evaluated"] = True
        else:
            # Numeric digit (0 - 9)
            if state["has_evaluated"] or not f or f == "0":
                state["formula"] = val
                state["history"] = ""
                state["has_evaluated"] = False
            elif f.endswith("Ans"):
                state["formula"] += f" × {val}"
            else:
                state["formula"] += val

        refresh_display()

    def make_btn(label: str, is_op: bool = False, is_accent: bool = False, is_sci: bool = False, flex: int = 1):
        bg = ft.Colors.PRIMARY if is_accent else (
            ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_op else (
                ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE) if is_sci else ft.Colors.SURFACE
            )
        )
        fg = ft.Colors.WHITE if is_accent else (
            ft.Colors.PRIMARY if is_op else (
                ft.Colors.ON_SURFACE_VARIANT if is_sci else ft.Colors.ON_SURFACE
            )
        )
        return ft.Container(
            content=ft.Text(label, size=12 if is_sci else 13, weight=ft.FontWeight.BOLD, color=fg),
            alignment=ft.Alignment.CENTER,
            height=34 if is_scientific else 38,
            border_radius=8,
            bgcolor=bg,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            ink=True,
            on_click=lambda _, v=label: handle_btn_click(v),
            expand=flex,
        )

    # Keypads
    if not is_scientific:
        # Standard 4-function layout with Ans and AC (4x5)
        keypad = ft.Column([
            ft.Row([make_btn("AC", is_op=True), make_btn("⌫", is_op=True), make_btn("Ans", is_op=True), make_btn("÷", is_op=True)], spacing=6),
            ft.Row([make_btn("7"), make_btn("8"), make_btn("9"), make_btn("×", is_op=True)], spacing=6),
            ft.Row([make_btn("4"), make_btn("5"), make_btn("6"), make_btn("−", is_op=True)], spacing=6),
            ft.Row([make_btn("1"), make_btn("2"), make_btn("3"), make_btn("+", is_op=True)], spacing=6),
            ft.Row([make_btn("+/-"), make_btn("0"), make_btn("."), make_btn("=", is_accent=True)], spacing=6),
        ], spacing=6)
        calc_width = 250
    else:
        # Scientific layout (5 columns) with Ans, AC, trig, powers, logs
        keypad = ft.Column([
            ft.Row([make_btn("sin", is_sci=True), make_btn("cos", is_sci=True), make_btn("tan", is_sci=True), make_btn("π", is_sci=True), make_btn("e", is_sci=True)], spacing=4),
            ft.Row([make_btn("log", is_sci=True), make_btn("ln", is_sci=True), make_btn("sqrt", is_sci=True), make_btn("(", is_sci=True), make_btn(")", is_sci=True)], spacing=4),
            ft.Row([make_btn("AC", is_op=True), make_btn("⌫", is_op=True), make_btn("Ans", is_op=True), make_btn("^", is_op=True), make_btn("÷", is_op=True)], spacing=4),
            ft.Row([make_btn("7"), make_btn("8"), make_btn("9"), make_btn("+/-", is_sci=True), make_btn("×", is_op=True)], spacing=4),
            ft.Row([make_btn("4"), make_btn("5"), make_btn("6"), make_btn("%", is_sci=True), make_btn("−", is_op=True)], spacing=4),
            ft.Row([make_btn("1"), make_btn("2"), make_btn("3"), make_btn(".", is_sci=True), make_btn("+", is_op=True)], spacing=4),
            ft.Row([make_btn("0", flex=2), make_btn("=", is_accent=True, flex=3)], spacing=4),
        ], spacing=4)
        calc_width = 300

    # Header - Universal Candidate Branding
    header = ft.Row([
        ft.Row([
            ft.Icon(ft.Icons.CALCULATE_ROUNDED, size=16, color=ft.Colors.PRIMARY),
            ft.Text("Calculator", size=13, weight=ft.FontWeight.BOLD),
        ], spacing=6, tight=True),
        ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=16, tooltip="Close Calculator", on_click=on_close),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # Full-Width Right-Aligned Display
    display_box = ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
        content=ft.Column([
            ft.Row([expr_text], alignment=ft.MainAxisAlignment.END),
            ft.Row([display_text], alignment=ft.MainAxisAlignment.END),
        ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
    )

    card = ft.Container(
        width=calc_width,
        padding=12,
        border_radius=14,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)),
        shadow=ft.BoxShadow(
            blur_radius=18,
            color=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
        content=ft.Column([
            header,
            display_box,
            keypad,
        ], spacing=8, tight=True),
    )

    return card
