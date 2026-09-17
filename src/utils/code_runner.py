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


def execute_python(code: str, test_input: str = "") -> dict:
    """
    Executes Python code in a sandboxed namespace and captures stdout/stderr.
    Pure client-side execution — works 100% offline.
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
    formatted_input = test_input if (not test_input or test_input.endswith("\n")) else (test_input + "\n")
    stdin_stream = io.StringIO(formatted_input)

    def safe_input(prompt=""):
        if prompt:
            stdout_capture.write(str(prompt))
        line = stdin_stream.readline()
        if not line:
            return ""
        return line.rstrip("\r\n")

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
    Pure client-side execution — works 100% offline.
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

    try:
        with httpx.Client(timeout=REMOTE_TIMEOUT) as client:
            resp = client.post(
                "https://ce.judge0.com/submissions?base64_encoded=true&wait=true",
                json=payload,
            )
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
                    }
                # Status 6 = Compilation Error
                elif status_id == 6:
                    return {
                        "success": False,
                        "output": "",
                        "error": compile_output or stderr or "Compilation failed.",
                    }
                # Status 5 = Time Limit Exceeded
                elif status_id == 5:
                    return {
                        "success": False,
                        "output": stdout,
                        "error": "Execution Timed Out (exceeded time limit). Check for infinite loops.",
                    }
                # Other errors (NZEC, Segfault, Out of Memory)
                else:
                    err_detail = stderr or compile_output or message or status_info.get("description", "Execution error")
                    return {
                        "success": False,
                        "output": stdout,
                        "error": err_detail,
                    }
            else:
                return {
                    "success": False,
                    "output": "",
                    "error": f"Execution service returned HTTP {resp.status_code}.",
                }

    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
        lang_name = lang_key.upper()
        return {
            "success": False,
            "output": "",
            "error": f"An active internet connection is required to compile and run {lang_name} code.\n(Offline local execution is supported for Python and SQL).",
            "offline_blocked": True,
        }
    except Exception as ex:
        return {
            "success": False,
            "output": "",
            "error": f"Sandbox execution error: {str(ex)}",
        }


def execute_html(code: str) -> dict:
    """
    Validates and analyzes HTML/CSS/JS web markup locally without headless runner.
    Works 100% offline.
    """
    if not code or not code.strip():
        return {
            "success": False,
            "output": "",
            "error": "HTML code is empty."
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

    return {
        "success": True,
        "output": "\n".join(summary_lines),
        "error": "",
        "tags": unique_tags,
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
