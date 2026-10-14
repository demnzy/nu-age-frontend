import httpx

with httpx.Client(timeout=15.0) as client:
    # 1. Compilation Error
    res = client.post("https://ce.judge0.com/submissions?base64_encoded=false&wait=true", json={
        "source_code": "#include <iostream>\nint main() { std::cout << \"Missing semi\" return 0; }",
        "language_id": 54,
    })
    print("Compile error status:", res.json().get("status"))
    print("Compile output:", repr(res.json().get("compile_output")))

    # 2. Runtime error (Divide by zero)
    res2 = client.post("https://ce.judge0.com/submissions?base64_encoded=false&wait=true", json={
        "source_code": "#include <iostream>\nint main() { int a = 1; int b = 0; std::cout << a/b; return 0; }",
        "language_id": 54,
    })
    print("Runtime error status:", res2.json().get("status"))
    print("Stderr:", repr(res2.json().get("stderr")))
    print("Message:", repr(res2.json().get("message")))
