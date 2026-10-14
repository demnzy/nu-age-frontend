import httpx
import json

# Test 1: Wandbox API (Supports C++, JS, Python, Java, Rust, Go, etc. - Free, no auth required)
wandbox_payload = {
    "code": "#include <iostream>\nint main() { std::cout << \"Wandbox C++ OK\" << std::endl; return 0; }",
    "compiler": "gcc-head",
    "stdin": "",
}

try:
    with httpx.Client(timeout=10.0) as client:
        r1 = client.post("https://wandbox.org/api/compile.json", json=wandbox_payload)
        print("Wandbox Status:", r1.status_code)
        if r1.status_code == 200:
            print("Wandbox Resp:", json.dumps(r1.json(), indent=2))
except Exception as e:
    print("Wandbox Error:", e)

# Test 2: Glot.io API
try:
    glot_payload = {
        "files": [{"name": "main.cpp", "content": "#include <iostream>\nint main() { std::cout << \"Glot C++ OK\" << std::endl; return 0; }"}]
    }
    with httpx.Client(timeout=10.0) as client:
        r2 = client.post("https://glot.io/api/run/cpp/latest", json=glot_payload)
        print("Glot Status:", r2.status_code)
        if r2.status_code == 200:
            print("Glot Resp:", json.dumps(r2.json(), indent=2))
except Exception as e:
    print("Glot Error:", e)
