import os
import re

src_dir = r"c:\Users\Admin\Desktop\Code\NU-Front\src"
results = []

for root, _, files in os.walk(src_dir):
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                lines = fp.readlines()
            for idx, line in enumerate(lines):
                # Search for ft.AppBar
                if "ft.AppBar" in line or "AppBar(" in line:
                    results.append((p, idx + 1, "AppBar", line.strip()))
                # Search for top header containers with primary or green background
                if any(k in line.lower() for k in ["top_bar", "header_container", "nav_bar", "appbar", "app_bar"]):
                    if any(c in line for c in ["PRIMARY", "#035800", "#4CAF50", "primary", "GREEN"]):
                        results.append((p, idx + 1, "HeaderGreen", line.strip()))

for r in results:
    rel = os.path.relpath(r[0], r"c:\Users\Admin\Desktop\Code\NU-Front")
    print(f"[{r[2]}] {rel}:{r[1]} -> {r[3][:110]}")
