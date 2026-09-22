import httpx
import base64
import json

def b64_encode(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("utf-8") if s else None

def b64_decode(s: str | None) -> str:
    if not s:
        return ""
    try:
        return base64.b64decode(s.encode("utf-8")).decode("utf-8", errors="replace")
    except Exception:
        return s

with httpx.Client(timeout=15.0) as client:
    # 1. Successful C++ execution
    payload1 = {
        "source_code": b64_encode("#include <iostream>\nint main() { std::cout << \"C++ Base64 Success!\"; return 0; }"),
        "language_id": 54,
        "stdin": b64_encode(""),
    }
    r1 = client.post("https://ce.judge0.com/submissions?base64_encoded=true&wait=true", json=payload1)
    d1 = r1.json()
    print("Test 1 Status:", d1.get("status"))
    print("Test 1 Stdout:", repr(b64_decode(d1.get("stdout"))))

    # 2. Syntax / Compilation Error
    payload2 = {
        "source_code": b64_encode("#include <iostream>\nint main() { int a = ; return 0; }"),
        "language_id": 54,
        "stdin": b64_encode(""),
    }
    r2 = client.post("https://ce.judge0.com/submissions?base64_encoded=true&wait=true", json=payload2)
    d2 = r2.json()
    print("Test 2 Status:", d2.get("status"))
    print("Test 2 Compile Output:", repr(b64_decode(d2.get("compile_output"))))
    print("Test 2 Stderr:", repr(b64_decode(d2.get("stderr"))))
