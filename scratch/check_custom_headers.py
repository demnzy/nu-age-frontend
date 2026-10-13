import os
import re

files_to_check = [
    "src/dashboard.py",
    "src/courses.py",
    "src/profile.py",
    "src/org_view.py",
    "src/cohort_page.py",
    "src/cohort_exam_view.py",
    "src/course_builder.py",
    "src/playlist_builder.py",
    "src/course_settings.py",
    "src/course_analytics.py",
    "src/playlist_settings.py",
    "src/playlist_analytics.py",
    "src/create_course.py",
    "src/create_playlist.py",
    "src/invite_members.py",
    "src/edit_profile.py",
    "src/member_profile.py",
    "src/network.py",
    "src/platform_admin_view.py",
]

for rel in files_to_check:
    full = os.path.join(r"c:\Users\Admin\Desktop\Code\NU-Front", rel)
    if not os.path.exists(full):
        continue
    with open(full, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Check for primary-colored headers or bars
    for match in re.finditer(r'(?:(?:top|header|nav|bar|banner)[^\n]*?(?:bgcolor|color)[^\n]*?(?:PRIMARY|#035800|#4CAF50)[^\n]*)', content, re.IGNORECASE):
        print(f"[{rel}] {match.group(0)[:100]}")
