import httpx
import json

payload = {
    "language": "cpp",
    "version": "*",
    "files": [
        {
            "name": "main.cpp",
            "content": "#include <iostream>\nint main() {\n    std::cout << \"C++ Piston Test OK\" << std::endl;\n    return 0;\n}\n"
        }
    ],
    "stdin": ""
}

try:
    with httpx.Client(timeout=10.0) as client:
        resp = client.post("https://emkc.org/api/v2/piston/execute", json=payload)
        print("Status:", resp.status_code)
        print("Response:", json.dumps(resp.json(), indent=2))
except Exception as e:
    print("Error:", e)
