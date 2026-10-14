import json

path = r"C:\Users\Admin\.gemini\antigravity-ide\brain\9f0d952f-2526-44e0-a5c0-aba3dd8f6b63\.system_generated\logs\transcript_full.jsonl"
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        if '"step_index":8240' in line:
            data = json.loads(line)
            content = data["tool_calls"][0]["args"]["CodeContent"]
            with open("scratch/prev_playlist_view.py", "w", encoding="utf-8") as out:
                out.write(content)
            print("Extracted step 8240 successfully!")
            break
