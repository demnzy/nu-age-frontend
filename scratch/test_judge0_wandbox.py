import httpx
import json

with httpx.Client(timeout=10.0) as client:
    # 1. Wandbox compilers list
    try:
        r = client.get("https://wandbox.org/api/list.json")
        print("Wandbox list status:", r.status_code)
        if r.status_code == 200:
            compilers = r.json()
            cpp_compilers = [c["name"] for c in compilers if "c++" in c.get("language", "").lower() or "gcc" in c["name"].lower() or "clang" in c["name"].lower()]
            print("Found C++ compilers in Wandbox:", cpp_compilers[:5])
            # Test with valid compiler name
            if cpp_compilers:
                r_comp = client.post("https://wandbox.org/api/compile.json", json={
                    "code": "#include <iostream>\nint main() { std::cout << \"Wandbox Works!\"; return 0; }",
                    "compiler": cpp_compilers[0],
                })
                print("Wandbox execution status:", r_comp.status_code)
                print("Wandbox execution output:", r_comp.json())
    except Exception as e:
        print("Wandbox test error:", e)

    # 2. Judge0 public CE instances
    judge0_urls = [
        "https://ce.judge0.com/submissions?base64_encoded=false&wait=true",
        "https://judge0-extra-ce.p.sulu.sh/submissions?base64_encoded=false&wait=true"
    ]
    for url in judge0_urls:
        try:
            r = client.post(url, json={
                "source_code": "#include <iostream>\nint main() { std::cout << \"Judge0 Works!\"; return 0; }",
                "language_id": 54, # C++ (GCC 9.2.0)
            })
            print(f"Judge0 ({url}) status:", r.status_code)
            if r.status_code in (200, 201):
                print("Judge0 resp:", r.json())
        except Exception as e:
            print(f"Judge0 error for {url}:", e)
