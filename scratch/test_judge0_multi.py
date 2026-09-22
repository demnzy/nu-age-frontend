import httpx

LANG_MAP = {
    "cpp": 54, # C++ (GCC 9.2.0)
    "c": 50, # C (GCC 9.2.0)
    "javascript": 63, # Node.js 12.14.0
    "typescript": 74, # TypeScript 3.7.4
    "java": 62, # Java (OpenJDK 13.0.1)
    "python": 71, # Python (3.8.1)
}

test_snippets = {
    "cpp": ('#include <iostream>\nint main() { std::cout << "Hello C++"; return 0; }', ""),
    "javascript": ('console.log("Hello JS");', ""),
    "typescript": ('let msg: string = "Hello TS"; console.log(msg);', ""),
    "java": ('public class Main { public static void main(String[] args) { System.out.println("Hello Java"); } }', ""),
}

with httpx.Client(timeout=15.0) as client:
    for lang, (code, stdin) in test_snippets.items():
        lang_id = LANG_MAP[lang]
        payload = {
            "source_code": code,
            "language_id": lang_id,
            "stdin": stdin,
        }
        res = client.post("https://ce.judge0.com/submissions?base64_encoded=false&wait=true", json=payload)
        print(f"--- {lang.upper()} (ID {lang_id}) ---")
        print("Status Code:", res.status_code)
        data = res.json()
        print("Status:", data.get("status"))
        print("Stdout:", repr(data.get("stdout")))
        print("Stderr:", repr(data.get("stderr")))
        print("Compile Output:", repr(data.get("compile_output")))
