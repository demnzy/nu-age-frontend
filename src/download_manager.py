"""
src/download_manager.py

Handles downloading a course for offline use: calls
GET /courses/{id}/download, walks the returned module/lesson tree,
downloads any binary assets referenced inside each lesson's `content`
dict, rewrites those content keys to point at local file paths, and
writes everything into the local SQLite tables defined in local_db.py.

The asset-key list below (ASSET_CONTENT_KEYS) is deliberately kept in
lockstep with course_page.py's CONTENT_RENDERERS registrations:
"video_url", "audio_path", "document_url" are the three keys whose
values are URLs/paths handed directly to a player or launch_url — every
other key (text, accompanying_text, cards, and the assessment/scenario-
specific keys) is inline data already, nothing to fetch.

This is the piece that makes offline_course_page.py's claim true: "the
renderers don't need to know online vs offline, they just get handed
whatever path is in content." That's only true because THIS file already
did the work of swapping remote URLs for local ones at download time.

NOTE on video_url: these are HLS streams (.m3u8), not single files. A
master playlist lists one or more variant playlists (one per quality),
and each variant playlist lists a sequence of .ts (or fMP4) segments —
all referenced by paths *relative* to the playlist that lists them. To
make one of these playable offline we have to download the whole tree
(master + every variant + every segment + any encryption key / init
segment) and lay the files out on disk in the same relative structure
they had remotely, so the relative references inside the .m3u8 files
keep resolving without any rewriting. See _download_hls_asset.
"""

import os
import re
import json
import uuid
import shutil
import asyncio
import httpx
import flet as ft
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from src.local_db import get_local_db
from src.local_media_server import ensure_started

# Keys inside a lesson's `content` dict whose value is a URL pointing at
# a downloadable asset (as opposed to inline text/data). Must stay in
# sync with course_page.py's @register_content_renderer(...) keys.
ASSET_CONTENT_KEYS = {"video_url", "audio_path", "document_url"}

BASE_URL = "https://api.nu-age.name.ng"  # reuse your existing API base, same as src/requests/*

# How many segment/key/init-map files to fetch concurrently per HLS asset.
HLS_CONCURRENCY = 6


class DownloadProgress:
    """Simple mutable progress holder a caller can poll or bind to a
    progress bar. Not a callback-based design on purpose — Flet UIs
    polling a shared object every N ms during a page.run_task is simpler
    to wire up than plumbing a callback through every download step."""

    def __init__(self):
        self.status = "pending"          # pending | fetching | downloading_assets | writing_db | done | error
        self.total_assets = 0
        self.completed_assets = 0
        self.error_message = None


async def download_course(page: ft.Page, course_id: str, progress: DownloadProgress = None) -> bool:
    """
    Downloads a course for offline use. Returns True on success. On
    partial asset failure, the course is still saved (with whatever
    assets succeeded) rather than aborting the whole download — a course
    with one broken video thumbnail shouldn't block someone from reading
    the text lessons offline. progress.error_message will be set to
    describe what partially failed.
    """
    progress = progress or DownloadProgress()
    if getattr(page, "web", False):
        progress.status = "error"
        progress.error_message = "Offline downloads are not supported on web."
        return False
    token = await page.shared_preferences.get("auth_token")

    if not token:
        progress.status = "error"
        progress.error_message = "Not logged in."
        return False

    # ── 1. Fetch the course tree ──────────────────────────────────
    progress.status = "fetching"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/courses/{course_id}/download",
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError as ex:
        progress.status = "error"
        progress.error_message = f"Network error: {ex}"
        return False

    if resp.status_code != 200:
        progress.status = "error"
        progress.error_message = f"Server rejected download request ({resp.status_code})."
        return False

    course_json = resp.json()

    # ── 2. Set up local asset folder ──────────────────────────────
    assets_dir = _course_assets_dir(course_id)
    os.makedirs(assets_dir, exist_ok=True)

    # Make sure the local HTTP asset server is up before we start
    # writing files, and definitely before playback is attempted.
    ensure_started(_course_assets_root())

    # ── 3. Walk lessons, download assets, rewrite content ─────────
    progress.status = "downloading_assets"

    all_lessons = [
        lesson
        for module in course_json.get("modules", [])
        for lesson in module.get("lessons", [])
    ]

    asset_jobs = []  # (lesson, content_key, remote_url)
    for lesson in all_lessons:
        content = lesson.get("content") or {}
        for key in ASSET_CONTENT_KEYS:
            url = content.get(key)
            if url and isinstance(url, str) and url.startswith("http"):
                asset_jobs.append((lesson, key, url))

    progress.total_assets = len(asset_jobs)
    downloaded_asset_rows = []  # for the downloaded_assets table
    had_asset_failure = False

    # Longer read timeout here than the course-tree fetch above: an HLS
    # asset can mean dozens of sequential requests (playlists + every
    # segment), and a slow CDN edge on one segment shouldn't blow the
    # whole asset up. Each individual request still gets its own budget.
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
        for lesson, key, url in asset_jobs:
            try:
                local_path, size_bytes = await _download_asset(client, url, assets_dir)
                lesson["content"][key] = local_path  # rewrite in place —
                                                       # this is what makes
                                                       # course_page.py's
                                                       # renderers "just work"
                downloaded_asset_rows.append({
                    "id": str(uuid.uuid4()),
                    "lesson_id": lesson["id"],
                    "remote_url": url,
                    "local_path": local_path,
                    "size_bytes": size_bytes,
                })
            except Exception as ex:
                # Don't abort the whole course over one bad asset. Leave
                # this lesson's content key pointing at the remote URL —
                # course_page.py's video/audio/document renderers will
                # then simply fail to load THAT ONE lesson's media if
                # opened fully offline, same as any broken-link case
                # they'd already need to tolerate online.
                had_asset_failure = True
                print(f"Asset download failed for lesson {lesson.get('id')}, key {key}: {ex!r}")

            progress.completed_assets += 1

    # ── 4. Write everything to SQLite ──────────────────────────────
    progress.status = "writing_db"
    db = get_local_db(page)
    now = datetime.now(timezone.utc).isoformat()

    try:
        db.execute("BEGIN")

        # Wipe any prior local copy of this course first (re-download /
        # re-sync case) — CASCADE handles modules/lessons/assets, but NOT
        # lesson_progress, which must survive across re-downloads.
        db.execute("DELETE FROM downloaded_courses WHERE id = ?", (course_id,))

        db.execute(
            """
            INSERT INTO downloaded_courses
                (id, name, description, category_id, objectives, downloaded_at, server_updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                course_json["id"],
                course_json["name"],
                course_json.get("description"),
                course_json.get("category_id"),
                json.dumps(course_json.get("objectives") or []),
                now,
                course_json.get("server_updated_at"),
            ),
        )

        for module in course_json.get("modules", []):
            db.execute(
                "INSERT INTO downloaded_modules (id, course_id, title, order_index) VALUES (?, ?, ?, ?)",
                (module["id"], course_id, module["title"], module["order_index"]),
            )
            for lesson in module.get("lessons", []):
                db.execute(
                    """
                    INSERT INTO downloaded_lessons (id, module_id, title, order_index, type, content)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lesson["id"],
                        module["id"],
                        lesson["title"],
                        lesson["order_index"],
                        lesson["type"],
                        json.dumps(lesson["content"]),  # already rewritten to local paths above
                    ),
                )

        for row in downloaded_asset_rows:
            db.execute(
                """
                INSERT INTO downloaded_assets (id, lesson_id, remote_url, local_path, size_bytes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (row["id"], row["lesson_id"], row["remote_url"], row["local_path"], row["size_bytes"]),
            )

        total_size = sum(r["size_bytes"] for r in downloaded_asset_rows)
        db.execute(
            "UPDATE downloaded_courses SET total_size_bytes = ? WHERE id = ?",
            (total_size, course_id),
        )

        db.commit()
    except Exception as ex:
        db.rollback()
        progress.status = "error"
        progress.error_message = f"Local storage error: {ex}"
        return False

    progress.status = "done"
    if had_asset_failure:
        progress.error_message = "Course saved, but some media files failed to download."
    return True


async def delete_downloaded_course(page: ft.Page, course_id: str):
    """Removes a course's local copy, including its downloaded asset
    files on disk. Does NOT touch lesson_progress — completion history
    survives so a re-download doesn't look like starting over.

    Every downloaded asset lives in its own subfolder of the course's
    assets dir (see _download_asset), so removing an asset means
    removing that whole subfolder, not just the one local_path file —
    an HLS video's local_path is only its master playlist; the dozens
    of variant playlists and .ts segments living alongside it need to
    go too, or they'd sit around as orphaned data forever.
    """
    db = get_local_db(page)

    asset_rows = db.execute(
        "SELECT local_path FROM downloaded_assets da "
        "JOIN downloaded_lessons dl ON da.lesson_id = dl.id "
        "JOIN downloaded_modules dm ON dl.module_id = dm.id "
        "WHERE dm.course_id = ?",
        (course_id,),
    ).fetchall()

    for (local_path,) in asset_rows:
        try:
            asset_folder = os.path.dirname(local_path)
            if asset_folder and os.path.isdir(asset_folder):
                shutil.rmtree(asset_folder, ignore_errors=True)
            elif os.path.exists(local_path):
                os.remove(local_path)
        except OSError:
            pass  # best-effort cleanup; DB row removal below is authoritative

    db.execute("DELETE FROM downloaded_courses WHERE id = ?", (course_id,))
    db.commit()

    assets_dir = _course_assets_dir(course_id)
    if os.path.isdir(assets_dir) and not os.listdir(assets_dir):
        os.rmdir(assets_dir)


def is_course_downloaded(page: ft.Page, course_id: str) -> bool:
    if page is not None and getattr(page, "web", False):
        return False
    try:
        db = get_local_db(page)
        row = db.execute(
            "SELECT 1 FROM downloaded_courses WHERE id = ?", (course_id,)
        ).fetchone()
        return row is not None
    except Exception:
        return False


# ── internal helpers ────────────────────────────────────────────────
_platform_storage_dir = None

async def init_download_manager(page: ft.Page):
    """
    Initialize the course assets directory using Flet's cross-platform storage paths,
    preventing issues on mobile where os.getcwd() is read-only.
    """
    global _platform_storage_dir
    if getattr(page, "web", False):
        _platform_storage_dir = None
        return
    try:
        _platform_storage_dir = await page.storage_paths.get_application_support_directory()
    except Exception:
        _platform_storage_dir = None

def _course_assets_root() -> str:
    """Parent folder holding every course's assets subfolder. This is
    what local_media_server serves from — one server instance, rooted
    here, covers all downloaded courses."""
    if _platform_storage_dir:
        base = _platform_storage_dir
    else:
        base = os.environ.get("FLET_APP_STORAGE_DATA") or os.path.join(os.getcwd(), "app_data")
    return os.path.join(base, "course_assets")

def _course_assets_dir(course_id: str) -> str:
    return os.path.join(_course_assets_root(), course_id)


def _is_hls_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".m3u8")


async def _download_asset(client: httpx.AsyncClient, url: str, assets_dir: str) -> tuple[str, int]:
    """Downloads a single lesson asset and returns (local_path, size_bytes).

    Plain files (documents, audio files that really are one file) get a
    single streamed GET, same as before. .m3u8 URLs are HLS streams and
    get routed to _download_hls_asset instead, which pulls down the
    whole playlist/segment tree.

    Every asset — HLS or plain — gets its own uuid-named subfolder under
    assets_dir. For plain files this is mild overkill; for HLS assets
    it's what makes delete_downloaded_course's cleanup correct and
    simple: "the folder this asset's local_path lives in" is always
    exactly the set of files that belong to that one asset, no more, no
    less.
    """
    asset_dir = os.path.join(assets_dir, uuid.uuid4().hex)
    os.makedirs(asset_dir, exist_ok=True)

    if _is_hls_url(url):
        return await _download_hls_asset(client, url, asset_dir)

    filename = _safe_filename_from_url(url)
    local_path = os.path.join(asset_dir, filename)
    async with client.stream("GET", url) as resp:
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            async for chunk in resp.aiter_bytes(chunk_size=65536):
                f.write(chunk)

    return local_path, os.path.getsize(local_path)


async def _download_hls_asset(client: httpx.AsyncClient, master_url: str, asset_dir: str) -> tuple[str, int]:
    """Downloads a full HLS stream — master playlist, every variant
    playlist it points to, and every segment (plus any encryption key /
    fMP4 init segment) those variants reference — and returns the local
    path to the master playlist plus the total bytes written.

    Files are laid out under asset_dir mirroring their remote host+path
    exactly (e.g. <asset_dir>/vz-7ab772e0-7bf.b-cdn.net/72403a.../playlist.m3u8,
    .../72403a.../360p/video.m3u8, .../72403a.../360p/seg_0.ts, ...).
    Because HLS playlists reference each other with paths *relative* to
    themselves, preserving that same relative layout locally means none
    of the URIs inside the downloaded .m3u8 files need to be rewritten —
    a player opening the local master playlist can walk straight down to
    local variant playlists and local segments exactly as if it were
    still talking to the CDN.

    Only the highest-bandwidth quality variant is downloaded (trick-play
    #EXT-X-I-FRAME-STREAM-INF variants are skipped entirely) — an
    offline copy doesn't need adaptive-bitrate switching between
    qualities, so there's no reason to pay for every resolution's worth
    of segments.
    """
    downloaded_paths: dict[str, str] = {}   # remote url -> local path, dedupes shared refs
    total_bytes = 0
    sem = asyncio.Semaphore(HLS_CONCURRENCY)

    def local_path_for(url: str) -> str:
        parsed = urlparse(url)
        # Keyed by host too, not just path — some CDNs serve segments
        # from a different host/edge than the playlist itself, and we
        # don't want two different hosts' /same/path.ts colliding.
        return os.path.join(asset_dir, parsed.netloc, parsed.path.lstrip("/"))

    def rel_uri(from_local_path: str, to_local_path: str) -> str:
        # URI to write *inside* a saved .m3u8, relative to the playlist
        # that references it. HLS/M3U8 requires '/' as the separator
        # regardless of OS, so os.path.relpath's result (which uses
        # os.sep) has to be normalized before writing it out.
        rel = os.path.relpath(to_local_path, os.path.dirname(from_local_path))
        return rel.replace(os.sep, "/")

    async def fetch_binary(url: str):
        nonlocal total_bytes
        if url in downloaded_paths:
            return
        local_path = local_path_for(url)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        async with sem:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
        downloaded_paths[url] = local_path
        total_bytes += os.path.getsize(local_path)

    async def fetch_and_process_playlist(url: str):
        nonlocal total_bytes
        if url in downloaded_paths:
            return

        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text
        lines = text.splitlines()

        local_path = local_path_for(url)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        # Reserve the mapping before recursing/writing so a shared ref
        # (or a self-reference) can't cause a double-fetch/double-write.
        downloaded_paths[url] = local_path

        refs = _parse_m3u8_refs(text, url)
        variants = [(u, bw) for u, kind, bw in refs if kind == "variant"]
        other_urls = [u for u, kind, _ in refs if kind not in ("variant", "iframe_variant")]

        # Pick the single highest-bandwidth variant rather than
        # downloading every quality — this is what makes "pick the
        # highest quality" actually save space instead of just being a
        # preference used at playback time. #EXT-X-I-FRAME-STREAM-INF
        # entries are excluded entirely: those are trick-play scrubbing
        # thumbnails, not a playable video track, so they're just
        # wasted bytes for an offline download.
        chosen_variant_url = None
        if variants:
            chosen_variant_url, _ = max(variants, key=lambda pair: pair[1])
            await fetch_and_process_playlist(chosen_variant_url)

        # Segments (and keys/init-maps) within one playlist have no
        # ordering dependency on each other, so fetch those concurrently.
        if other_urls:
            await asyncio.gather(*(fetch_binary(u) for u in other_urls))

        # ── Rewrite the text before saving ──────────────────────────
        # The player opens whatever we write here directly off disk, so
        # every URI in it has to resolve to a file that actually exists
        # locally. Two things need fixing vs. the raw fetched text:
        #   1. A master playlist otherwise still lists EVERY quality
        #      variant, even though only `chosen_variant_url` was
        #      downloaded — the player's own ABR logic can pick one of
        #      the un-downloaded ones and fail to find it on disk. Those
        #      entries (and all #EXT-X-I-FRAME-STREAM-INF entries, which
        #      were never downloaded either) get dropped entirely.
        #   2. Every remaining URI (variant/key/map/segment) is still
        #      the original remote URL/path — some CDNs hand out
        #      absolute, token-signed URLs even for what look like
        #      "relative" playlists, so leaving them as-is means the
        #      player reaches for the network (and a possibly-expired
        #      token) instead of the local copy. Every one gets
        #      rewritten to a relative path pointing at the local file.
        out_lines = []
        drop_next_uri_line = False
        for i, raw in enumerate(lines):
            line = raw.strip()

            if not line:
                out_lines.append(raw)
                continue

            if line.startswith("#EXT-X-I-FRAME-STREAM-INF"):
                continue  # trick-play variant, never downloaded

            if line.startswith("#EXT-X-STREAM-INF"):
                this_url = None
                for j in range(i + 1, len(lines)):
                    nxt = lines[j].strip()
                    if not nxt:
                        continue
                    if not nxt.startswith("#"):
                        this_url = urljoin(url, nxt)
                    break
                if this_url == chosen_variant_url:
                    out_lines.append(raw)
                    drop_next_uri_line = False
                else:
                    drop_next_uri_line = True  # drop this un-downloaded variant + its URI
                continue

            if drop_next_uri_line:
                drop_next_uri_line = False
                continue

            if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-SESSION-KEY"):
                m = re.search(r'URI="([^"]+)"', line)
                if m:
                    abs_url = urljoin(url, m.group(1))
                    if abs_url in downloaded_paths:
                        raw = raw.replace(m.group(1), rel_uri(local_path, downloaded_paths[abs_url]))
                out_lines.append(raw)
                continue

            if line.startswith("#EXT-X-MAP"):
                m = re.search(r'URI="([^"]+)"', line)
                if m:
                    abs_url = urljoin(url, m.group(1))
                    if abs_url in downloaded_paths:
                        raw = raw.replace(m.group(1), rel_uri(local_path, downloaded_paths[abs_url]))
                out_lines.append(raw)
                continue

            if not line.startswith("#"):
                # The chosen variant's URI (in the master) or a media
                # segment URI (in a variant) — either way it's something
                # we already downloaded and have a local path for.
                abs_url = urljoin(url, line)
                out_lines.append(rel_uri(local_path, downloaded_paths[abs_url])
                                  if abs_url in downloaded_paths else raw)
                continue

            out_lines.append(raw)

        with open(local_path, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines) + "\n")
        total_bytes += os.path.getsize(local_path)

    await fetch_and_process_playlist(master_url)
    return downloaded_paths[master_url], total_bytes


def _parse_m3u8_refs(text: str, base_url: str) -> list[tuple[str, str, int]]:
    """Parses an .m3u8 playlist's text and returns every URI it
    references as (absolute_url, kind, bandwidth), kind being one of:
      - "variant":         a quality-variant playlist (#EXT-X-STREAM-INF)
      - "iframe_variant":  a trick-play/scrubbing playlist (#EXT-X-I-FRAME-STREAM-INF)
      - "media_segment":   a .ts / .m4s media segment
      - "key":             an #EXT-X-KEY encryption key
      - "map":              an #EXT-X-MAP fMP4 initialization segment

    bandwidth is the variant's BANDWIDTH attribute (bits/sec) for
    "variant"/"iframe_variant" entries, used to pick the highest-quality
    track; it's 0 for every other kind, where it's meaningless.

    All URIs in HLS playlists may be relative to the playlist that
    references them, so every result is resolved to an absolute URL via
    urljoin(base_url, ...) before being returned.
    """
    refs: list[tuple[str, str, int]] = []
    lines = [line.strip() for line in text.splitlines()]
    consumed: set[int] = set()

    def _bandwidth(line: str) -> int:
        m = re.search(r'BANDWIDTH=(\d+)', line)
        return int(m.group(1)) if m else 0

    for i, line in enumerate(lines):
        if not line or i in consumed:
            continue

        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-SESSION-KEY"):
            m = re.search(r'URI="([^"]+)"', line)
            if m:
                refs.append((urljoin(base_url, m.group(1)), "key", 0))

        elif line.startswith("#EXT-X-MAP"):
            m = re.search(r'URI="([^"]+)"', line)
            if m:
                refs.append((urljoin(base_url, m.group(1)), "map", 0))

        elif line.startswith("#EXT-X-I-FRAME-STREAM-INF"):
            # Trick-play playlist; URI is an inline attribute, not on
            # the next line. We record it (with "iframe_variant" kind)
            # only so callers can deliberately skip it — see
            # _download_hls_asset, which never downloads these.
            m = re.search(r'URI="([^"]+)"', line)
            if m:
                refs.append((urljoin(base_url, m.group(1)), "iframe_variant", _bandwidth(line)))

        elif line.startswith("#EXT-X-STREAM-INF"):
            # Regular quality-variant playlist; URI is on the next
            # non-blank, non-comment line.
            bandwidth = _bandwidth(line)
            for j in range(i + 1, len(lines)):
                if not lines[j]:
                    continue
                if not lines[j].startswith("#"):
                    refs.append((urljoin(base_url, lines[j]), "variant", bandwidth))
                    consumed.add(j)
                break

        elif not line.startswith("#"):
            # A bare URI not already claimed above is a media segment —
            # either following an #EXTINF line, or (for a media playlist
            # fetched directly, with no #EXT-X-STREAM-INF at all) just a
            # segment in a single-quality playlist.
            refs.append((urljoin(base_url, line), "media_segment", 0))

    return refs


def _safe_filename_from_url(url: str) -> str:
    # Keep the extension (renderers/players may care), but namespace with
    # a uuid prefix to avoid collisions between assets that happen to
    # share a filename across different lessons.
    base_name = url.split("?")[0].rstrip("/").split("/")[-1] or "asset"
    return f"{uuid.uuid4().hex}_{base_name}"