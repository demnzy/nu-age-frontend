"""
Comprehensive verification test for Adaptive Video Player and YouTube integration.
Tests static syntax, YouTube utilities, yt-dlp resolution, and runtime instantiation
of course_page.py and course_builder.py video components.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import py_compile
import asyncio
from unittest.mock import MagicMock

# 1. Static py_compile
files_to_compile = [
    "src/utils/youtube.py",
    "src/components/adaptive_video_player.py",
    "src/course_page.py",
    "src/course_builder.py",
]

for f in files_to_compile:
    py_compile.compile(f, doraise=True)
    print(f"Syntax OK: {f}")

# 2. Test YouTube utilities
from src.utils.youtube import (
    is_youtube_url,
    extract_youtube_id,
    get_youtube_embed_url,
    get_youtube_thumbnail_url,
    resolve_youtube_stream_url_async,
)

test_urls = [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://example.com/lecture.mp4", None),
]

for url, expected_id in test_urls:
    is_yt = is_youtube_url(url)
    yt_id = extract_youtube_id(url)
    assert is_yt == (expected_id is not None), f"Failed is_youtube_url for {url}"
    assert yt_id == expected_id, f"Failed extract_youtube_id for {url} (got {yt_id}, expected {expected_id})"

print("All YouTube URL utility assertions passed!")

# 3. Test AdaptiveVideoPlayer and Page mock instantiation
import flet as ft
from src.components.adaptive_video_player import AdaptiveVideoPlayer
from src.course_builder import render_preview_video_block

mock_page = MagicMock(spec=ft.Page)
mock_page.platform = ft.PagePlatform.WINDOWS
mock_page.web = False
mock_page.run_task = MagicMock()

# Direct MP4
player_mp4 = AdaptiveVideoPlayer(
    media_url="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    title="Sample MP4 Lesson",
)
assert player_mp4._is_youtube is False
print("AdaptiveVideoPlayer (MP4) instantiated successfully.")

# YouTube Watch URL
player_yt = AdaptiveVideoPlayer(
    media_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    title="Rick Astley - Never Gonna Give You Up",
)
assert player_yt._is_youtube is True
assert player_yt._video_id == "dQw4w9WgXcQ"
print("AdaptiveVideoPlayer (YouTube) instantiated successfully.")

# Empty URL
player_empty = AdaptiveVideoPlayer(media_url="")
print("AdaptiveVideoPlayer (Empty) instantiated successfully.")

# Test builder preview block
lesson_mock = {
    "id": "lesson_123",
    "content": {"file_name": "Course Intro.mp4", "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
}
preview_row = render_preview_video_block(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    lesson_mock,
)
assert isinstance(preview_row, ft.ResponsiveRow)
print("Course Builder render_preview_video_block instantiated successfully.")

# Test cinema card construction directly
cinema_card = player_yt._build_cinema_card()
assert isinstance(cinema_card, ft.Stack)
print("YouTube Cinema Card constructed successfully.")

# Test offline card construction directly
offline_card = player_yt._build_offline_card()
assert isinstance(offline_card, ft.Container)
print("Offline Learning Card constructed successfully.")

# Test web client resolution directly
player_web = AdaptiveVideoPlayer(media_url="https://youtu.be/aFDOzpTeg0s")
mock_web_page = MagicMock(spec=ft.Page)
mock_web_page.web = True
player_web._get_page = lambda: mock_web_page
asyncio.run(player_web._resolve_and_mount())
assert isinstance(player_web.content, ft.Stack)
print("Web client correctly mounts Cinema Card without raw COEP-blocked iframes.")

# 4. Test course_learner_view instantiation with YouTube lesson
from src.course_page import course_learner_view

class MockLearnerPage:
    def __init__(self):
        self.width = 1200
        self.height = 800
        self.overlay = []
        self.controls = []
        self.route = "/courses/test_c/view"
        self.platform = ft.PagePlatform.WINDOWS
        self.web = False
        self.shared_preferences = MagicMock()
        self.shared_preferences.get = MagicMock(return_value=asyncio.Future())
        self.shared_preferences.get.return_value.set_result("mock_token")
        self.session = MagicMock()
        self.session.store = {}
        self.tasks = []

    def update(self):
        pass

    def run_task(self, handler, *args):
        self.tasks.append((handler, args))

    def go(self, route):
        pass

async def test_learner_view_with_youtube():
    mock_learner_page = MockLearnerPage()
    mock_data = {
        "course_title": "Adaptive Video Test Course",
        "completed_lesson_ids": [],
        "modules": [
            {
                "id": "mod_yt",
                "title": "Module 1: Video Mastery",
                "lessons": [
                    {
                        "id": "les_yt_1",
                        "title": "YouTube Masterclass",
                        "type": "video",
                        "content": {
                            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                            "accompanying_text": "Notes for the YouTube lesson.",
                        },
                    },
                    {
                        "id": "les_mp4_2",
                        "title": "Local/Hosted MP4 Lesson",
                        "type": "video",
                        "content": {
                            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                            "accompanying_text": "Direct MP4 streaming.",
                        },
                    },
                ],
            }
        ],
    }

    async def mock_fetch(c_id):
        return mock_data

    async def mock_save(c_id, l_id):
        return True

    view = await course_learner_view(
        mock_learner_page,
        "test_course_id",
        fetch_course_data=mock_fetch,
        save_progress=mock_save,
        back_target="/courses",
    )
    assert isinstance(view, ft.View)
    print("course_learner_view rendered with YouTube & MP4 lessons successfully!")

    # Verify user's specific test link resolves directly
    user_stream = await resolve_youtube_stream_url_async("https://youtu.be/aFDOzpTeg0s")
    assert user_stream is not None, "Failed to resolve stream for user link https://youtu.be/aFDOzpTeg0s"
    assert user_stream.get("stream_url"), "No stream_url in resolved info"
    assert "Linear Regression" in user_stream.get("title", ""), f"Unexpected title: {user_stream.get('title')}"
    print(f"Direct stream resolved successfully for user link: {user_stream['title']} ({user_stream.get('stream_url')[:45]}...)")

asyncio.run(test_learner_view_with_youtube())

print("\n>>> ALL VERIFICATION TESTS PASSED SUCCESSFULLY! <<<")
