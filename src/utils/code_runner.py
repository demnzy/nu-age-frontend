"""
In-memory Code Runner Sandbox for Nu-Age Code Labs.
Supports Python (AST-checked, stdout captured) and SQLite (in-memory schema & query execution).
Zero external runtime dependencies.
"""

import sys
import io
import ast
import sqlite3
import traceback
import contextlib
import re

# Modules and functions disallowed in student code for safety
DISALLOWED_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "http", "urllib",
    "requests", "ctypes", "pathlib", "importlib", "builtins"
}
DISALLOWED_NAMES = {
    "eval", "exec", "compile", "__import__", "open", "breakpoint",
    "globals", "locals", "exit", "quit"
}


class SafetyViolationError(Exception):
    pass


def check_python_safety(code: str):
    """
    Parses the AST to reject hazardous calls or imports.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        # Syntax errors are caught during execution
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if root_module in DISALLOWED_MODULES:
                    raise SafetyViolationError(f"Importing '{alias.name}' is not permitted in code lab exercises.")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split(".")[0]
                if root_module in DISALLOWED_MODULES:
                    raise SafetyViolationError(f"Importing from '{node.module}' is not permitted in code lab exercises.")
        elif isinstance(node, ast.Name):
            if node.id in DISALLOWED_NAMES and isinstance(node.ctx, ast.Load):
                raise SafetyViolationError(f"Use of restricted identifier '{node.id}' is not permitted.")


def execute_python(code: str, test_input: str = "") -> dict:
    """
    Executes Python code in a sandboxed namespace and captures stdout/stderr.
    """
    try:
        check_python_safety(code)
    except SafetyViolationError as sve:
        return {
            "success": False,
            "output": "",
            "error": str(sve),
        }

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    # Ensure trailing newline so readline completes properly
    formatted_input = test_input if (not test_input or test_input.endswith("\n")) else (test_input + "\n")
    stdin_stream = io.StringIO(formatted_input)

    def safe_input(prompt=""):
        if prompt:
            stdout_capture.write(str(prompt))
        line = stdin_stream.readline()
        if not line:
            return ""
        return line.rstrip("\r\n")

    # Safe builtins
    safe_globals = {
        "__builtins__": {
            "abs": abs, "all": all, "any": any, "ascii": ascii, "bin": bin,
            "bool": bool, "bytearray": bytearray, "bytes": bytes, "chr": chr,
            "complex": complex, "dict": dict, "dir": dir, "divmod": divmod,
            "enumerate": enumerate, "filter": filter, "float": float,
            "format": format, "frozenset": frozenset, "hasattr": hasattr,
            "hash": hash, "hex": hex, "id": id, "input": safe_input, "int": int,
            "isinstance": isinstance, "issubclass": issubclass, "iter": iter,
            "len": len, "list": list, "map": map, "max": max, "min": min,
            "next": next, "oct": oct, "ord": ord, "pow": pow, "print": print,
            "range": range, "repr": repr, "reversed": reversed, "round": round,
            "set": set, "slice": slice, "sorted": sorted, "str": str,
            "sum": sum, "tuple": tuple, "type": type, "zip": zip,
            "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
            "IndexError": IndexError, "KeyError": KeyError, "ZeroDivisionError": ZeroDivisionError,
            "AssertionError": AssertionError, "True": True, "False": False, "None": None,
        },
        "math": __import__("math"),
        "random": __import__("random"),
        "datetime": __import__("datetime"),
        "collections": __import__("collections"),
        "re": __import__("re"),
        "json": __import__("json"),
    }
    safe_locals = {}

    old_stdin = sys.stdin
    try:
        sys.stdin = stdin_stream
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            compiled = compile(code, "<code_lab>", "exec")
            exec(compiled, safe_globals, safe_locals)
        out = stdout_capture.getvalue()
        err = stderr_capture.getvalue()
        return {
            "success": not bool(err),
            "output": out,
            "error": err,
        }
    except Exception as e:
        err_msg = traceback.format_exc(limit=2)
        clean_lines = [l for l in err_msg.splitlines() if "code_runner.py" not in l]
        return {
            "success": False,
            "output": stdout_capture.getvalue(),
            "error": "\n".join(clean_lines).strip() or str(e),
        }
    finally:
        sys.stdin = old_stdin


def execute_sql(query: str, setup_sql: str = "") -> dict:
    """
    Executes SQL query against an in-memory SQLite database pre-seeded with setup_sql.
    """
    if not query.strip():
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "rowcount": 0,
            "error": "Query cannot be empty.",
        }

    conn = None
    try:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        if setup_sql and setup_sql.strip():
            cursor.executescript(setup_sql)

        cursor.execute(query.strip().rstrip(";"))
        
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall() if cursor.description else []
        rowcount = cursor.rowcount

        conn.commit()
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "rowcount": rowcount,
            "error": "",
        }
    except Exception as e:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "rowcount": 0,
            "error": str(e),
        }
    finally:
        if conn:
            conn.close()


def run_code_lab_tests(language: str, code: str, setup_sql: str, test_cases: list[dict]) -> list[dict]:
    """
    Executes student code against a suite of test cases.
    Returns list of dicts:
    [{'description': str, 'passed': bool, 'actual': str, 'expected': str, 'error': str}]
    """
    results = []
    lang = (language or "python").lower()
    is_sql = "sql" in lang

    if not test_cases:
        if is_sql:
            res = execute_sql(code, setup_sql)
            results.append({
                "description": "SQL Query Execution",
                "passed": res["success"],
                "actual": f"{len(res['rows'])} rows returned" if res["success"] else "",
                "expected": "Successful execution",
                "error": res["error"],
                "columns": res.get("columns", []),
                "rows": res.get("rows", []),
            })
        else:
            res = execute_python(code)
            results.append({
                "description": "Code Execution",
                "passed": res["success"],
                "actual": res["output"].strip(),
                "expected": "Successful execution without runtime errors",
                "error": res["error"],
            })
        return results

    for tc in test_cases:
        desc = tc.get("description", "Test Case")
        exp = str(tc.get("expected_output", "")).strip()

        if is_sql:
            res = execute_sql(code, setup_sql)
            if not res["success"]:
                results.append({
                    "description": desc,
                    "passed": False,
                    "actual": "",
                    "expected": exp,
                    "error": res["error"],
                    "columns": [],
                    "rows": [],
                })
            else:
                actual_str = "\n".join([str(r) for r in res["rows"]]).strip()
                passed = (exp in actual_str) or (not exp and len(res["rows"]) > 0)
                results.append({
                    "description": desc,
                    "passed": passed,
                    "actual": actual_str,
                    "expected": exp,
                    "error": "" if passed else "Query results did not match expected output.",
                    "columns": res["columns"],
                    "rows": res["rows"],
                })
        else:
            inp = str(tc.get("input", ""))
            res = execute_python(code, test_input=inp)
            act = res["output"].strip()
            passed = res["success"] and (exp in act if exp else True)
            results.append({
                "description": desc,
                "passed": passed,
                "actual": act,
                "expected": exp,
                "error": res["error"] or ("Output did not match expected result." if not passed else ""),
            })

    return results


def parse_cloze_text(raw_text: str):
    """
    Parses text with embedded blanks syntax:
    'In Python, [[list|data structure]] is mutable, whereas a [[tuple]] is immutable.'
    Returns:
    (segments: list[dict], blanks: list[dict])
    """
    pattern = r"\[\[(.*?)\]\]"
    segments = []
    blanks = []
    last_idx = 0
    blank_idx = 0

    for match in re.finditer(pattern, raw_text):
        start, end = match.span()
        if start > last_idx:
            segments.append({"type": "text", "content": raw_text[last_idx:start]})

        inner = match.group(1).strip()
        if "|" in inner:
            ans, hint = inner.split("|", 1)
            ans = ans.strip()
            hint = hint.strip()
        else:
            ans = inner
            hint = ""

        blank_info = {
            "index": blank_idx,
            "answer": ans,
            "hint": hint,
        }
        blanks.append(blank_info)
        segments.append({"type": "blank", "info": blank_info})
        blank_idx += 1
        last_idx = end

    if last_idx < len(raw_text):
        segments.append({"type": "text", "content": raw_text[last_idx:]})

    return segments, blanks
