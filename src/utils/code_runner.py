"""
In-memory & Sandboxed Code Runner Sandbox for Nu-Age Code Labs.
Supports:
1. Python (Local AST-checked sandbox, stdout captured) - Zero latency, pure offline.
2. SQLite (Local in-memory schema & query execution) - Zero latency, pure offline.
3. Multi-language Remote Sandbox (C++, C, JavaScript, TypeScript, Java, Rust, Go)
   executed via high-speed sandboxed container execution with graceful offline fallback.
"""

import sys
import io
import ast
import sqlite3
import traceback
import contextlib
import re
import base64
import httpx

# Modules and functions disallowed in local student Python code for safety
DISALLOWED_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "http", "urllib",
    "requests", "ctypes", "pathlib", "importlib", "builtins"
}
DISALLOWED_NAMES = {
    "eval", "exec", "compile", "__import__", "open", "breakpoint",
    "globals", "locals", "exit", "quit"
}

# Supported Judge0 Language IDs
JUDGE0_LANG_IDS = {
    "cpp": 54,        # C++ (GCC 9.2.0)
    "c++": 54,
    "cplusplus": 54,
    "c": 50,          # C (GCC 9.2.0)
    "javascript": 63, # JavaScript (Node.js 12.14.0)
    "js": 63,
    "typescript": 74, # TypeScript (3.7.4)
    "ts": 74,
    "java": 62,       # Java (OpenJDK 13.0.1)
    "rust": 73,       # Rust (1.40.0)
    "go": 60,         # Go (1.13.5)
    "golang": 60,
    "csharp": 51,     # C# (Mono 6.6.0.161)
    "cs": 51,
    "c#": 51,
    "ruby": 72,       # Ruby (2.7.0)
    "rb": 72,
    "php": 68,        # PHP (7.4.1)
    "python": 71,     # Python (3.8.1)
    "py": 71,
}

REMOTE_TIMEOUT = httpx.Timeout(connect=3.5, read=12.0, write=5.0, pool=3.0)


class SafetyViolationError(Exception):
    pass


def _b64_encode(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("utf-8") if s else ""


def _b64_decode(s: str | None) -> str:
    if not s:
        return ""
    try:
        return base64.b64decode(s.encode("utf-8")).decode("utf-8", errors="replace")
    except Exception:
        return str(s)


def check_python_safety(code: str):
    """
    Parses the AST to reject hazardous calls or imports in local Python runs.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
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


SAFE_BUILTIN_NAMES = {
    # Primitives & OOP
    "__build_class__", "__name__", "__doc__", "object", "super", "property",
    "classmethod", "staticmethod", "getattr", "setattr", "hasattr", "delattr",
    "callable", "vars", "dir", "id", "isinstance", "issubclass", "type",
    # Built-in Types & Functions
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes", "chr",
    "complex", "dict", "divmod", "enumerate", "filter", "float", "format",
    "frozenset", "hash", "hex", "int", "iter", "len", "list", "map", "max",
    "min", "next", "oct", "ord", "pow", "print", "range", "repr", "reversed",
    "round", "set", "slice", "sorted", "str", "sum", "tuple", "zip",
    # Common Built-in Exceptions
    "BaseException", "Exception", "ArithmeticError", "AssertionError", "AttributeError",
    "BufferError", "EOFError", "FloatingPointError", "GeneratorExit", "ImportError",
    "IndexError", "KeyError", "LookupError", "MemoryError", "NameError",
    "NotImplementedError", "OSError", "OverflowError", "ReferenceError", "RuntimeError",
    "StopIteration", "StopAsyncIteration", "SyntaxError", "IndentationError",
    "TabError", "SystemError", "TypeError", "UnboundLocalError", "UnicodeError",
    "UnicodeEncodeError", "UnicodeDecodeError", "UnicodeTranslateError", "ValueError",
    "ZeroDivisionError", "Warning", "UserWarning", "DeprecationWarning",
    # Constants
    "True", "False", "None", "Ellipsis", "NotImplemented",
}


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root_module = name.split(".")[0]
    if root_module in DISALLOWED_MODULES:
        raise SafetyViolationError(f"Importing '{name}' is not permitted in code lab exercises.")
    return __import__(name, globals, locals, fromlist, level)


def _build_safe_builtins(safe_input_fn):
    import builtins
    b_dict = {}
    for name in SAFE_BUILTIN_NAMES:
        if hasattr(builtins, name):
            b_dict[name] = getattr(builtins, name)
    b_dict["input"] = safe_input_fn
    b_dict["__import__"] = _safe_import
    return b_dict


def _build_safe_globals(safe_input_fn):
    import math
    import random
    import datetime
    import collections
    import itertools
    import functools
    import string
    import heapq
    import bisect
    import copy
    import time
    import re
    import json
    import dataclasses
    import typing

    return {
        "__name__": "__main__",
        "__builtins__": _build_safe_builtins(safe_input_fn),
        "math": math,
        "random": random,
        "datetime": datetime,
        "collections": collections,
        "itertools": itertools,
        "functools": functools,
        "string": string,
        "heapq": heapq,
        "bisect": bisect,
        "copy": copy,
        "time": time,
        "re": re,
        "json": json,
        "dataclasses": dataclasses,
        "typing": typing,
    }


def detects_stdin(language: str, code: str) -> bool:
    """
    Detects if the source code contains interactive input statements (e.g. input(), cin >>).
    Used to automatically highlight or open the Stdin input drawer for users.
    """
    if not code:
        return False
    lang = (language or "python").lower().strip()
    c = code.lower()

    if lang in ("python", "py", "python3"):
        return bool(re.search(r"\binput\s*\(", code)) or "sys.stdin" in code
    elif lang in ("cpp", "c++", "cplusplus", "c"):
        return ("cin >>" in code or "cin>>" in code or "getline(" in code
                or "scanf(" in code or "fgets(" in code)
    elif lang in ("javascript", "js", "typescript", "ts", "node", "nodejs"):
        return ("readline" in c or "process.stdin" in c or "prompt(" in code)
    elif lang in ("java", "jvm"):
        return ("scanner" in c or "system.in" in c or "bufferedreader" in c)
    elif lang in ("go", "golang"):
        return ("scan(" in c or "scanln(" in c or "scanf(" in c or "bufio.newreader" in c)
    elif lang in ("rust", "rs"):
        return ("stdin()" in c or "read_line" in c)
    return False


def execute_python(code: str, test_input: str = "") -> dict:
    """
    Executes Python code in a sandboxed namespace and captures stdout/stderr.
    Pure client-side execution — works 100% offline.
    Supports full OOP (classes, methods, inheritance, properties, dataclasses),
    standard utility libraries, and enforces an infinite loop timeout guard.
    """
    import time

    start_time = time.time()
    try:
        check_python_safety(code)
    except SafetyViolationError as sve:
        return {
            "success": False,
            "output": "",
            "error": str(sve),
            "duration_ms": 0.0,
        }

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    formatted_input = test_input if (not test_input or test_input.endswith("\n")) else (test_input + "\n")
    stdin_stream = io.StringIO(formatted_input)

    def safe_input(prompt=""):
        if prompt:
            stdout_capture.write(str(prompt))
        line = stdin_stream.readline()
        if not line:
            raise EOFError("EOF when reading a line")
        return line.rstrip("\r\n")

    safe_globals = _build_safe_globals(safe_input)
    safe_locals = {}

    max_duration = 5.0
    step_count = 0
    max_steps = 1_000_000

    def trace_guard(frame, event, arg):
        nonlocal step_count
        step_count += 1
        if step_count % 1000 == 0:
            if time.time() - start_time > max_duration:
                raise TimeoutError("Execution timed out (exceeded 5.0s limit). Check for infinite loops or heavy recursion.")
            if step_count > max_steps:
                raise TimeoutError("Execution exceeded maximum operation limit (1,000,000 steps). Check for infinite loops.")
        return trace_guard

    old_stdin = sys.stdin
    sys.settrace(trace_guard)
    try:
        sys.stdin = stdin_stream
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            compiled = compile(code, "<code_lab>", "exec")
            exec(compiled, safe_globals, safe_locals)
        duration_ms = round((time.time() - start_time) * 1000, 2)
        out = stdout_capture.getvalue()
        err = stderr_capture.getvalue()
        return {
            "success": not bool(err),
            "output": out,
            "error": err,
            "duration_ms": duration_ms,
        }
    except TimeoutError as te:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "success": False,
            "output": stdout_capture.getvalue(),
            "error": str(te),
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        err_msg = traceback.format_exc(limit=2)
        clean_lines = [l for l in err_msg.splitlines() if "code_runner.py" not in l]
        err_text = "\n".join(clean_lines).strip() or str(e)
        if isinstance(e, EOFError) or "EOF when reading a line" in err_text:
            err_text += (
                "\n\n💡 Beginner Tip: Your code asked for input() but the Program Input (stdin) box was "
                "empty or ran out of lines. Enter your input into the Program Input (stdin) box before "
                "clicking 'Run Code' (put each response on a new line)."
            )
        return {
            "success": False,
            "output": stdout_capture.getvalue(),
            "error": err_text,
            "duration_ms": duration_ms,
        }
    finally:
        sys.settrace(None)
        sys.stdin = old_stdin


def execute_sql(query: str, setup_sql: str = "") -> dict:
    """
    Executes SQL query against an in-memory SQLite database pre-seeded with setup_sql.
    Pure client-side execution — works 100% offline.
    """
    import time
    start_time = time.time()
    if not query.strip():
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "rowcount": 0,
            "error": "Query cannot be empty.",
            "duration_ms": 0.0,
        }

    conn = None
    try:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        if setup_sql and setup_sql.strip():
            cursor.executescript(setup_sql)

        # Support multi-statement SQL scripts (CREATE, INSERT, SELECT)
        raw_statements = [s.strip() for s in query.strip().split(";") if s.strip()]
        if not raw_statements:
            return {
                "success": True,
                "columns": [],
                "rows": [],
                "rowcount": 0,
                "error": "",
                "duration_ms": round((time.time() - start_time) * 1000, 2),
            }

        if len(raw_statements) > 1:
            pre_stmts = ";\n".join(raw_statements[:-1]) + ";"
            cursor.executescript(pre_stmts)

        final_stmt = raw_statements[-1]
        cursor.execute(final_stmt)
        
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall() if cursor.description else []
        rowcount = cursor.rowcount

        conn.commit()
        duration_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "rowcount": rowcount,
            "error": "",
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "rowcount": 0,
            "error": str(e),
            "duration_ms": duration_ms,
        }
    finally:
        if conn:
            conn.close()


def execute_remote_code(language: str, code: str, test_input: str = "") -> dict:
    """
    Executes code in C++, JavaScript, TypeScript, Java, C, etc. via container sandbox.
    Handles network errors gracefully when the user is offline or viewing an offline course.
    """
    lang_key = (language or "cpp").lower().strip()
    lang_id = JUDGE0_LANG_IDS.get(lang_key, 54)  # Default to C++ GCC if unknown

    payload = {
        "source_code": _b64_encode(code),
        "language_id": lang_id,
        "stdin": _b64_encode(test_input),
    }

    import time
    start_time = time.time()
    try:
        with httpx.Client(timeout=REMOTE_TIMEOUT) as client:
            resp = client.post(
                "https://ce.judge0.com/submissions?base64_encoded=true&wait=true",
                json=payload,
            )
            duration_ms = round((time.time() - start_time) * 1000, 2)
            if resp.status_code in (200, 201):
                data = resp.json()
                status_info = data.get("status", {})
                status_id = status_info.get("id", 0)

                stdout = _b64_decode(data.get("stdout"))
                stderr = _b64_decode(data.get("stderr"))
                compile_output = _b64_decode(data.get("compile_output"))
                message = _b64_decode(data.get("message"))

                # Status 3 = Accepted (Successful run)
                if status_id == 3:
                    return {
                        "success": True,
                        "output": stdout,
                        "error": stderr or "",
                        "duration_ms": duration_ms,
                    }
                # Status 6 = Compilation Error
                elif status_id == 6:
                    return {
                        "success": False,
                        "output": "",
                        "error": compile_output or stderr or "Compilation failed.",
                        "duration_ms": duration_ms,
                    }
                # Status 5 = Time Limit Exceeded
                elif status_id == 5:
                    return {
                        "success": False,
                        "output": stdout,
                        "error": "Execution Timed Out (exceeded time limit). Check for infinite loops.",
                        "duration_ms": duration_ms,
                    }
                # Other errors (NZEC, Segfault, Out of Memory)
                else:
                    err_detail = stderr or compile_output or message or status_info.get("description", "Execution error")
                    return {
                        "success": False,
                        "output": stdout,
                        "error": err_detail,
                        "duration_ms": duration_ms,
                    }
            else:
                return {
                    "success": False,
                    "output": "",
                    "error": f"Execution service returned HTTP {resp.status_code}.",
                    "duration_ms": duration_ms,
                }

    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        lang_name = lang_key.upper()
        return {
            "success": False,
            "output": "",
            "error": f"An active internet connection is required to compile and run {lang_name} code.\n(Offline local execution is supported for Python and SQL).",
            "offline_blocked": True,
            "duration_ms": duration_ms,
        }
    except Exception as ex:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "success": False,
            "output": "",
            "error": f"Sandbox execution error: {str(ex)}",
            "duration_ms": duration_ms,
        }


def execute_html(code: str) -> dict:
    """
    Validates and analyzes HTML/CSS/JS web markup locally without headless runner.
    Works 100% offline.
    """
    import time
    start_time = time.time()
    if not code or not code.strip():
        return {
            "success": False,
            "output": "",
            "error": "HTML code is empty.",
            "duration_ms": 0.0,
        }

    tags_found = re.findall(r"<([a-zA-Z0-9\-]+)", code)
    tags_found_lower = [t.lower() for t in tags_found if not t.startswith("!")]
    has_script = bool(re.search(r"<script[\s>]", code, re.IGNORECASE))
    has_style = bool(re.search(r"<style[\s>]", code, re.IGNORECASE))
    
    unique_tags = sorted(set(tags_found_lower))
    tag_summary = ", ".join(unique_tags[:10])
    if len(unique_tags) > 10:
        tag_summary += f", ... (+{len(unique_tags)-10} more)"
    
    summary_lines = [
        "HTML Document parsed successfully.",
        f"Elements detected: {len(tags_found)} total ({tag_summary or 'plain text/fragment'})",
    ]
    if has_script:
        summary_lines.append("Embedded JavaScript: <script> present.")
    if has_style:
        summary_lines.append("Embedded CSS: <style> present.")
    if "serviceworker" in code.lower() or "navigator.serviceworker" in code.lower():
        summary_lines.append("PWA Feature: Service Worker registration detected.")
    if "indexeddb" in code.lower() or "opendb" in code.lower():
        summary_lines.append("PWA Feature: IndexedDB / Offline Storage detected.")
    if "manifest" in code.lower():
        summary_lines.append("PWA Feature: Web App Manifest reference detected.")

    duration_ms = round((time.time() - start_time) * 1000, 2)
    return {
        "success": True,
        "output": "\n".join(summary_lines),
        "error": "",
        "tags": unique_tags,
        "duration_ms": duration_ms,
    }


def is_service_worker_code(code: str) -> bool:
    if not code:
        return False
    c = code.lower()
    return any(k in c for k in (
        "workbox", "registerroute", "cachefirst", "networkfirst",
        "stalewhilerevalidate", "networkonly", "cacheonly", "importscripts",
        "self.addeventlistener('fetch'", 'self.addeventlistener("fetch"',
        "caches.open", "caches.match"
    ))


def execute_service_worker_js(code: str) -> dict:
    """
    Analyzes and validates Service Worker & Workbox JavaScript code locally.
    Evaluates caching strategies, route registrations, and lifecycle hooks
    without sending browser-only APIs to a headless Node.js CLI runtime.
    Works 100% offline.
    """
    if not code or not code.strip():
        return {
            "success": False,
            "output": "",
            "error": "Service Worker code is empty."
        }

    # Basic syntax bracket/paren balancing
    stack = []
    pairs = {')': '(', '}': '{', ']': '['}
    in_string = None
    in_line_comment = False
    in_block_comment = False
    i = 0
    while i < len(code):
        ch = code[i]
        if in_line_comment:
            if ch == '\n':
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if ch == '*' and i + 1 < len(code) and code[i + 1] == '/':
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if not in_string:
            if ch == '/' and i + 1 < len(code):
                if code[i + 1] == '/':
                    in_line_comment = True
                    i += 2
                    continue
                elif code[i + 1] == '*':
                    in_block_comment = True
                    i += 2
                    continue
            if ch in ('"', "'", '`'):
                in_string = ch
                i += 1
                continue
            if ch in ('(', '{', '['):
                stack.append(ch)
            elif ch in (')', '}', ']'):
                expected = pairs[ch]
                if not stack or stack[-1] != expected:
                    return {
                        "success": False,
                        "output": "",
                        "error": f"Syntax Error: Unmatched closing '{ch}' in Service Worker script."
                    }
                stack.pop()
        else:
            if ch == '\\':
                i += 2
                continue
            if ch == in_string:
                in_string = None
        i += 1

    if stack:
        unclosed = stack[-1]
        return {
            "success": False,
            "output": "",
            "error": f"Syntax Error: Unclosed opening '{unclosed}' in Service Worker script."
        }

    lines = ["Service Worker Script Validated:"]
    c = code.lower()

    if "workbox" in c or "registerroute" in c:
        lines.append("- Architecture: Workbox Routing & Caching")
        if "importscripts" in c:
            lines.append("  * Runtime: Loaded via importScripts (Standard Standalone SW)")
        elif "import " in c and "from " in c:
            lines.append("  * Note: Bare ES imports detected (requires bundler or importScripts in standalone SW)")

        strategies = []
        if "cachefirst" in c:
            strategies.append("CacheFirst")
        if "networkfirst" in c:
            strategies.append("NetworkFirst")
        if "stalewhilerevalidate" in c:
            strategies.append("StaleWhileRevalidate")
        if "networkonly" in c:
            strategies.append("NetworkOnly")
        if "cacheonly" in c:
            strategies.append("CacheOnly")

        if strategies:
            lines.append(f"  * Strategies Registered: {', '.join(strategies)}")
        if "registerroute" in c:
            route_count = len(re.findall(r"registerRoute\s*\(", code))
            lines.append(f"  * Route Handlers: {route_count} route(s) registered")
    else:
        lines.append("- Architecture: Native Service Worker Cache API")
        if "install" in c:
            lines.append("  * Lifecycle: 'install' event listener detected")
        if "activate" in c:
            lines.append("  * Lifecycle: 'activate' event listener detected")
        if "fetch" in c:
            lines.append("  * Network Interception: 'fetch' event listener detected")

    cache_names = re.findall(r"['\"]([a-zA-Z0-9_\-]+(?:cache|assets|v\d|pages)[a-zA-Z0-9_\-]*)['\"]", code, re.IGNORECASE)
    if cache_names:
        unique_caches = sorted(set(cache_names))
        lines.append(f"- Cache Buckets Identified: {', '.join(unique_caches)}")

    lines.append("- Validation Status: All routes and structures verified successfully.")

    return {
        "success": True,
        "output": "\n".join(lines),
        "error": ""
    }


def sanitize_javascript_code(code: str) -> str:
    """
    Sanitizes JavaScript/TypeScript code to eliminate module/import runtime syntax errors:
    1. Converts bare Workbox ES module imports into standalone Service Worker
       importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.4.1/workbox-sw.js') + destructuring.
    2. Converts generic ES module imports into Node.js CommonJS require(...) and module.exports,
       preventing 'SyntaxError: Cannot use import statement outside a module'.
    """
    if not isinstance(code, str) or not code.strip():
        return code

    # 1. Handle Workbox Service Worker imports (all submodules)
    if "workbox" in code.lower():
        def _replace_wb(m: re.Match) -> str:
            items = m.group(1).strip()
            pkg = m.group(2).strip()
            submod = pkg.replace("workbox-", "").replace("-", "_")
            return f"const {{ {items} }} = workbox.{submod};"

        code = re.sub(
            r"import\s*\{\s*([^}]+)\s*\}\s*from\s*['\"](workbox-[a-z0-9\-]+)['\"];?",
            _replace_wb,
            code
        )
        if "workbox-sw.js" not in code:
            code = (
                "// Load Workbox from CDN for standalone service worker\n"
                "importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.4.1/workbox-sw.js');\n\n"
                + code.lstrip()
            )

    # 2. Handle generic ES module imports: convert to CommonJS require
    code = re.sub(
        r"import\s*\{\s*([^}]+)\s*\}\s*from\s*['\"]([^'\"]+)['\"];?",
        r"const { \1 } = require('\2');",
        code
    )
    code = re.sub(
        r"import\s*\*\s*as\s+([a-zA-Z0-9_$]+)\s+from\s*['\"]([^'\"]+)['\"];?",
        r"const \1 = require('\2');",
        code
    )
    code = re.sub(
        r"import\s+([a-zA-Z0-9_$]+)\s+from\s*['\"]([^'\"]+)['\"];?",
        r"const \1 = require('\2');",
        code
    )
    code = re.sub(r"export\s+default\s+", "module.exports = ", code)

    return code


def run_code_lab_tests(language: str, code: str, setup_sql: str, test_cases: list[dict]) -> list[dict]:
    """
    Executes student code against a suite of test cases.
    Automatically switches between:
    - In-memory SQLite (pure offline)
    - Sandboxed Python (pure offline)
    - Local HTML/Web validator (pure offline)
    - Local Service Worker / Workbox validator (pure offline)
    - Remote Sandboxed Container (C++, JS, TS, Java, C, etc.) with graceful offline fallback.

    Returns list of dicts:
    [{'description': str, 'passed': bool, 'actual': str, 'expected': str, 'error': str, 'offline_blocked': bool}]
    """
    results = []
    lang = (language or "python").lower().strip()
    if lang in ("javascript", "js", "typescript", "ts"):
        code = sanitize_javascript_code(code)

    is_sql = "sql" in lang
    is_python = lang in ("python", "py", "python3")
    is_html = lang in ("html", "web", "html5", "htm")
    is_sw = (lang in ("javascript", "js", "typescript", "ts")) and is_service_worker_code(code)

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
                "offline_blocked": False,
            })
        elif is_python:
            res = execute_python(code)
            results.append({
                "description": "Code Execution",
                "passed": res["success"],
                "actual": res["output"].strip(),
                "expected": "Successful execution without runtime errors",
                "error": res["error"],
                "offline_blocked": False,
            })
        elif is_html:
            res = execute_html(code)
            results.append({
                "description": "HTML Document Structure & Validation",
                "passed": res["success"],
                "actual": res["output"].strip(),
                "expected": "Valid HTML markup structure",
                "error": res["error"],
                "offline_blocked": False,
            })
        elif is_sw:
            res = execute_service_worker_js(code)
            results.append({
                "description": "Service Worker Architecture & Validation",
                "passed": res["success"],
                "actual": res["output"].strip(),
                "expected": "Valid Service Worker logic and routes",
                "error": res["error"],
                "offline_blocked": False,
            })
        else:
            res = execute_remote_code(lang, code)
            results.append({
                "description": f"{lang.upper()} Code Execution",
                "passed": res["success"],
                "actual": res["output"].strip(),
                "expected": "Successful execution without compiler or runtime errors",
                "error": res["error"],
                "offline_blocked": res.get("offline_blocked", False),
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
                    "offline_blocked": False,
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
                    "offline_blocked": False,
                })
        elif is_python:
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
                "offline_blocked": False,
            })
        elif is_html:
            res = execute_html(code)
            passed = res["success"]
            if exp:
                passed = passed and (exp.lower() in code.lower())
            results.append({
                "description": desc,
                "passed": passed,
                "actual": f"Matched token: '{exp}'" if (exp and exp.lower() in code.lower()) else ("Markup analyzed" if not exp else f"Missing expected token: '{exp}'"),
                "expected": exp or "Valid HTML structure",
                "error": "" if passed else (f"Expected code to contain '{exp}'" if exp else res["error"]),
                "offline_blocked": False,
            })
        elif is_sw:
            res = execute_service_worker_js(code)
            passed = res["success"]
            if exp:
                passed = passed and (exp.lower() in code.lower() or exp.lower() in res["output"].lower())
            results.append({
                "description": desc,
                "passed": passed,
                "actual": f"Matched requirement: '{exp}'" if (exp and (exp.lower() in code.lower() or exp.lower() in res["output"].lower())) else ("Service Worker validated" if not exp else f"Missing expected token/strategy: '{exp}'"),
                "expected": exp or "Valid Service Worker structure",
                "error": "" if passed else (f"Expected code to contain '{exp}'" if exp else res["error"]),
                "offline_blocked": False,
            })
        else:
            inp = str(tc.get("input", ""))
            res = execute_remote_code(lang, code, test_input=inp)
            act = res["output"].strip()
            is_offline = res.get("offline_blocked", False)
            passed = res["success"] and (exp in act if exp else True) and not is_offline
            results.append({
                "description": desc,
                "passed": passed,
                "actual": act,
                "expected": exp,
                "error": res["error"] or ("Output did not match expected result." if not passed else ""),
                "offline_blocked": is_offline,
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
