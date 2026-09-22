"""
YouTube integration utilities for Nu-Age LMS.
Provides URL parsing, video ID extraction, high-res thumbnail generation,
and async stream URL extraction via yt-dlp.
"""

import asyncio
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Standard YouTube ID regex (11 characters)
YOUTUBE_ID_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|v\/|shorts\/|live\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
)


def is_youtube_url(url: Optional[str]) -> bool:
    """Check if the provided URL is a valid YouTube link."""
    if not url or not isinstance(url, str):
        return False
    clean_url = url.strip()
    return bool(
        "youtube.com" in clean_url or "youtu.be" in clean_url
    ) and bool(extract_youtube_id(clean_url))


def extract_youtube_id(url: Optional[str]) -> Optional[str]:
    """
    Extract the 11-character video ID from various YouTube URL formats.
    Supports:
      - youtube.com/watch?v=ID
      - youtu.be/ID
      - youtube.com/embed/ID
      - youtube.com/shorts/ID
      - youtube.com/live/ID
    """
    if not url or not isinstance(url, str):
        return None
    
    match = YOUTUBE_ID_REGEX.search(url.strip())
    if match:
        return match.group(1)
    
    # Fallback check for raw 11-char ID
    cleaned = url.strip()
    if len(cleaned) == 11 and re.match(r"^[a-zA-Z0-9_-]{11}$", cleaned):
        return cleaned
        
    return None


def get_youtube_embed_url(video_id_or_url: str, autoplay: bool = False, use_nocookie: bool = True) -> str:
    """
    Generate a clean, cookie-safe embed URL for WebView or Web browsers.
    Uses https://www.youtube-nocookie.com/embed/{video_id} with playsinline and modestbranding.
    """
    video_id = extract_youtube_id(video_id_or_url) or video_id_or_url
    ap = 1 if autoplay else 0
    host = "www.youtube-nocookie.com" if use_nocookie else "www.youtube.com"
    return (
        f"https://{host}/embed/{video_id}"
        f"?autoplay={ap}&playsinline=1&rel=0&modestbranding=1"
    )


def get_youtube_iframe_html(video_id_or_url: str, autoplay: bool = False, use_nocookie: bool = True) -> str:
    """
    Generate responsive HTML containing an embedded YouTube iframe with proper
    Referrer-Policy and viewport configuration to resolve and prevent YouTube
    Error 153 ('Video Player Configuration Error') in native mobile WebViews.
    """
    video_id = extract_youtube_id(video_id_or_url) or video_id_or_url
    embed_url = get_youtube_embed_url(video_id, autoplay=autoplay, use_nocookie=use_nocookie)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="referrer" content="strict-origin-when-cross-origin">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        html, body {{
            width: 100%;
            height: 100%;
            background-color: #000000;
            overflow: hidden;
        }}
        .video-wrapper {{
            position: relative;
            width: 100%;
            height: 100%;
            background-color: #000000;
        }}
        iframe {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border: 0;
        }}
    </style>
</head>
<body>
    <div class="video-wrapper">
        <iframe
            src="{embed_url}"
            frameborder="0"
            referrerpolicy="strict-origin-when-cross-origin"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowfullscreen>
        </iframe>
    </div>
</body>
</html>"""


def get_youtube_thumbnail_url(video_id_or_url: str, quality: str = "maxres") -> str:
    """
    Get YouTube thumbnail URL.
    quality options: 'maxres' (1280x720), 'hq' (480x360), 'mq' (320x180), 'default' (120x90).
    """
    video_id = extract_youtube_id(video_id_or_url) or video_id_or_url
    if quality == "maxres":
        return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    elif quality == "hq":
        return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    elif quality == "mq":
        return f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
    return f"https://img.youtube.com/vi/{video_id}/default.jpg"


def resolve_youtube_stream_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Synchronously extracts direct playable media stream URL and metadata using yt-dlp.
    Returns dict with stream_url, title, thumbnail, duration or None on failure.
    """
    try:
        import yt_dlp
    except ImportError:
        logger.error("yt-dlp is not installed in current environment.")
        return None

    class QuietYtdlLogger:
        def debug(self, msg): pass
        def warning(self, msg): pass
        def error(self, msg): pass

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 10,
        "logger": QuietYtdlLogger(),
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web", "mweb"]
            }
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None
            
            formats = [
                f for f in info.get("formats", [])
                if f.get("vcodec") not in (None, "none")
                and f.get("acodec") not in (None, "none")
                and f.get("url")
            ]

            stream_url = None
            http_headers = None
            if formats:
                # Prefer highest resolution, then bitrate
                formats.sort(key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))
                best_format = formats[-1]
                stream_url = best_format.get("url")
                http_headers = best_format.get("http_headers")
            elif info.get("url"):
                stream_url = info.get("url")
                http_headers = info.get("http_headers")

            if not stream_url:
                return None

            if not http_headers:
                http_headers = {}
            if "Referer" not in http_headers:
                http_headers["Referer"] = "https://www.youtube.com/"
            if "Origin" not in http_headers:
                http_headers["Origin"] = "https://www.youtube.com"

            # Detect YouTube PoToken/SABR rate-limiting stubs (e.g. YouTube sending only a 270KB stub
            # for a multi-minute video, which causes desktop libmpv to immediately reach EOF and jump to the end).
            # When detected, return None so AdaptiveVideoPlayer gracefully mounts the Cinema Card.
            duration = info.get("duration") or 0
            if duration > 30 and stream_url:
                try:
                    import urllib.request
                    req = urllib.request.Request(stream_url, headers=http_headers or {}, method="HEAD")
                    with urllib.request.urlopen(req, timeout=3.5) as resp:
                        cl = resp.headers.get("Content-Length")
                        if cl and int(cl) < 1_000_000:
                            logger.warning(
                                "YouTube throttled stream detected for %r: %s bytes for %ss duration. Falling back to Cinema Card.",
                                url, cl, duration,
                            )
                            return None
                except Exception as check_ex:
                    logger.debug("Stream length pre-check skipped: %s", check_ex)

            return {
                "stream_url": stream_url,
                "http_headers": http_headers or {},
                "title": info.get("title", "YouTube Lesson"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
                "channel": info.get("uploader") or info.get("channel"),
            }
    except Exception as e:
        logger.debug("yt-dlp stream resolution not available for %r: %s", url, e)
        return None


async def resolve_youtube_stream_url_async(url: str) -> Optional[Dict[str, Any]]:
    """
    Asynchronously resolves YouTube stream URL in a worker thread to keep the
    Flet UI event loop responsive.
    """
    try:
        return await asyncio.to_thread(resolve_youtube_stream_url, url)
    except Exception as e:
        logger.exception("Unexpected error in async YouTube stream resolution: %s", e)
        return None


def is_network_available(host: str = "8.8.8.8", port: int = 53, timeout: float = 1.5) -> bool:
    """
    Rapid, lightweight connectivity test checking if internet access is available.
    Uses a quick socket probe to public DNS resolver (default 8.8.8.8 on port 53).
    """
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.timeout, OSError):
        return False


async def is_network_available_async(timeout: float = 1.5) -> bool:
    """Non-blocking asynchronous check for network availability."""
    return await asyncio.to_thread(is_network_available, timeout=timeout)

