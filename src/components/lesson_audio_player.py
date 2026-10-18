"""
src/components/lesson_audio_player.py

Definitive Lesson Audio Narration Player for Nu-Age LMS.
Built using the official flet_audio.Audio service.

Features:
- Official flet_audio.Audio service attached cleanly to page.services.
- Zero UI freeze: No invisible video renderers or GPU surfaces.
- Instant responsive play/pause toggle.
- Multi-language narration (English, Hausa, French).
- Real-time duration & position tracking via on_duration_change and on_position_change.
- Interactive slider scrubbing and playback speed toggle (1.0x, 1.25x, 1.5x, 2.0x).
- Dancing waveform visualizer during active playback.
- Offline playback & 1-tap download with local media server.
- Fail-fast error handling for 404s and offline mode guards.
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
import httpx
import flet as ft
import flet_audio as fta

from src.local_db import (
    get_offline_lesson_audio,
    save_offline_lesson_audio,
    is_lesson_audio_cached,
    _resolve_db_path,
)
from src.download_manager import _course_assets_root
from src.local_media_server import asset_url, ensure_started
from src.utils.file_opener import show_page_snackbar

logger = logging.getLogger("lesson_audio_player")

BASE_URL = os.getenv("API_URL", "https://api.nu-age.name.ng").rstrip("/")

LANGUAGES = [
    {"code": "en", "label": "English"},
    {"code": "ha", "label": "Hausa"},
    {"code": "fr", "label": "French"},
]

# Process-wide lock tracking active in-flight audio downloads to prevent duplicate network calls
_global_active_downloads: set = set()


class LessonAudioPlayer(ft.Container):
    """
    Definitive audio narration bar embedded in course lessons.
    Uses official flet_audio.Audio service with pure UI layout encapsulation.
    """

    def __init__(
        self,
        page: ft.Page,
        lesson_id: str,
        course_id: str,
        lesson_title: str = "",
        lesson_type: str = "text",
        is_offline_mode: bool = False,
        api_base_url: str = BASE_URL,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.target_page = page
        self.lesson_id = str(lesson_id or "").strip()
        self.course_id = str(course_id or "").strip()
        self.lesson_title = lesson_title or "Lesson"
        self.lesson_type = lesson_type
        self.is_offline_mode = is_offline_mode
        self.api_base_url = (api_base_url or BASE_URL).rstrip("/")

        # Playback state
        self._cached_token: Optional[str] = None
        self.current_lang = "en"
        self.is_playing = False
        self.is_loading = False
        self.is_preparing = False
        self.is_service_loaded = False
        self.is_verified_ready = False
        self._is_busy = False
        self.pending_play_request = False
        self._cached_audio_urls: Dict[str, str] = {}
        self.duration_seconds = 0.0
        self.position_seconds = 0.0
        self.current_speed = 1.0
        self.is_disposed = False
        self._current_loaded_uri: Optional[str] = None

        # Container styling
        self.border_radius = ft.BorderRadius.all(12)
        self.bgcolor = ft.Colors.SURFACE
        self.border = ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE))
        self.padding = ft.Padding.symmetric(horizontal=14, vertical=10)

        # Build controls and mount permanent UI
        self._build_subcontrols()
        self.render_ui()

        # Proactively check offline and prefetch backend audio metadata & cache status
        if hasattr(self.target_page, "run_task"):
            self.target_page.run_task(self._prefetch_and_preload)

    def _is_mobile(self) -> bool:
        width = getattr(self.target_page, "width", None)
        if width is None:
            width = getattr(getattr(self.target_page, "window", None), "width", 800) or 800
        return width < 760

    def _build_subcontrols(self):
        # 1. Official Flet Audio Service (No UI texture, zero freeze)
        self.audio_service = fta.Audio(
            src=None,
            autoplay=False,
            volume=1.0,
            playback_rate=self.current_speed,
            release_mode=fta.ReleaseMode.STOP,
            on_loaded=self._on_player_loaded,
            on_duration_change=self._on_player_duration_changed,
            on_position_change=self._on_player_position_changed,
            on_state_change=self._on_player_state_changed,
        )

        # Attach audio service to Page services lifecycle
        if hasattr(self.target_page, "services"):
            if self.audio_service not in self.target_page.services:
                self.target_page.services.append(self.audio_service)

        # 2. Direct-Tap Play / Pause Button - verified ready state styling
        self.play_icon = ft.Icon(
            ft.Icons.PLAY_ARROW_ROUNDED,
            size=20,
            color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE),
        )
        self.spinner = ft.ProgressRing(
            width=18,
            height=18,
            stroke_width=2.5,
            color=ft.Colors.PRIMARY,
        )

        self.play_button = ft.Container(
            content=self.play_icon,
            width=36,
            height=36,
            border_radius=ft.BorderRadius.all(18),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            alignment=ft.Alignment.CENTER,
            ink=True,
            on_click=self._toggle_play_click,
            tooltip="Checking audio narration...",
        )

        # 3. Waveform Indicator
        self.wave_bars = [
            ft.Container(
                width=3,
                height=6,
                border_radius=2,
                bgcolor=ft.Colors.PRIMARY,
                animate_size=150,
            )
            for _ in range(4)
        ]
        self.waveform_row = ft.Row(
            controls=self.wave_bars,
            spacing=2.5,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 4. Accurate Read-Only Progress Bar (Seeking disabled to prevent desync, thumb vibrant green when ready/playing)
        self.slider = ft.Slider(
            min=0,
            max=100,
            value=0,
            disabled=False,
            active_color=ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE),
            inactive_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
            thumb_color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE),
            mouse_cursor=ft.MouseCursor.BASIC,
            on_change=self._on_slider_prevent_seek,
            on_change_end=self._on_slider_prevent_seek,
            expand=True,
        )

        # 5. Timestamps
        self.time_label = ft.Text(
            "00:00 / 00:00",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
            weight=ft.FontWeight.W_500,
        )

        # 6. Speed Toggle
        self.speed_btn = ft.Container(
            content=ft.Text(f"{self.current_speed}x", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=ft.BorderRadius.all(6),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            ink=True,
            on_click=self._toggle_speed_click,
            tooltip="Playback speed",
        )

    def _get_current_lang_label(self) -> str:
        for l in LANGUAGES:
            if l["code"] == self.current_lang:
                return l["label"]
        return self.current_lang.title()

    def _build_lang_selector(self) -> ft.Container:
        """Sleek, modern dropdown button that scales cleanly from 3 to 31+ languages without clutter."""
        self.lang_label_text = ft.Text(
            self._get_current_lang_label(),
            size=11 if self._is_mobile() else 12,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.ON_SURFACE,
        )
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.LANGUAGE_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                    self.lang_label_text,
                    ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, size=15, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=5,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            border_radius=ft.BorderRadius.all(20),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            ink=True,
            on_click=self._open_language_modal,
            tooltip="Choose narration language",
        )

    def _open_language_modal(self, e=None):
        """Opens a sleek, scrollable modal picker that supports 31+ languages cleanly."""
        if not self.target_page:
            return

        items = []
        for l in LANGUAGES:
            is_sel = l["code"] == self.current_lang
            code = l["code"]
            label = l["label"]

            def _on_pick(evt, picked_code=code):
                self._on_select_language_click(picked_code)
                dlg.open = False
                try:
                    self.target_page.update()
                except Exception:
                    pass

            items.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(
                                label,
                                size=13,
                                weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500,
                                color=ft.Colors.PRIMARY if is_sel else ft.Colors.ON_SURFACE,
                                expand=True,
                            ),
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_ROUNDED,
                                size=18,
                                color=ft.Colors.PRIMARY,
                                visible=is_sel,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_sel else ft.Colors.TRANSPARENT,
                    ink=True,
                    on_click=_on_pick,
                )
            )

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.TRANSLATE_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                    ft.Text("Narration Language", size=16, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.ListView(
                    controls=items,
                    spacing=4,
                ),
                width=320,
                height=min(360, len(LANGUAGES) * 48 + 10),
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda evt: self._close_dialog(dlg),
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        if dlg not in self.target_page.overlay:
            self.target_page.overlay.append(dlg)
        dlg.open = True
        try:
            self.target_page.update()
        except Exception:
            pass

    def _close_dialog(self, dlg: ft.AlertDialog):
        dlg.open = False
        try:
            self.target_page.update()
        except Exception:
            pass

    def render_ui(self):
        """Assembles a permanent, stable layout with zero invisible video controls."""
        is_mobile = self._is_mobile()
        lang_selector = self._build_lang_selector()

        if is_mobile:
            main_bar = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.HEADPHONES_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                                        padding=ft.Padding.all(5),
                                        border_radius=ft.BorderRadius.all(6),
                                        bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
                                    ),
                                    ft.Text("Listen to Lesson", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, no_wrap=True),
                                    self.waveform_row,
                                ],
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Row(
                                [
                                    self.speed_btn,
                                    lang_selector,
                                ],
                                spacing=6,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            self.play_button,
                            self.slider,
                            self.time_label,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        else:
            main_bar = ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(ft.Icons.HEADPHONES_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                padding=ft.Padding.all(6),
                                border_radius=ft.BorderRadius.all(8),
                                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
                            ),
                            ft.Text("Listen", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            self.waveform_row,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.play_button,
                    self.slider,
                    self.time_label,
                    self.speed_btn,
                    lang_selector,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            )

        self.content = main_bar

    # =========================================================================
    # AUDIO STREAMING & PLAYBACK LOGIC
    # =========================================================================

    async def _get_auth_token_async(self) -> str:
        if self._cached_token:
            return self._cached_token
        try:
            if hasattr(self.target_page, "session") and hasattr(self.target_page.session, "store"):
                tok = self.target_page.session.store.get("token") or self.target_page.session.store.get("auth_token")
                if tok:
                    self._cached_token = str(tok)
                    return self._cached_token
        except Exception:
            pass
        try:
            sp = ft.SharedPreferences()
            tok = await sp.get("auth_token")
            if tok:
                self._cached_token = str(tok)
                return self._cached_token
        except Exception:
            pass
        tok = getattr(self.target_page, "session_token", "") or ""
        if tok:
            self._cached_token = str(tok)
            return self._cached_token
        return ""

    def _get_auth_token_sync(self) -> str:
        if self._cached_token:
            return self._cached_token
        try:
            if hasattr(self.target_page, "session") and hasattr(self.target_page.session, "store"):
                tok = self.target_page.session.store.get("token") or self.target_page.session.store.get("auth_token")
                if tok:
                    self._cached_token = str(tok)
                    return self._cached_token
        except Exception:
            pass
        return getattr(self.target_page, "session_token", "") or ""

    def _safe_asset_url(self, local_path: str) -> str:
        """
        Returns the optimal audio playback source URI:
        On Android/iOS/Linux, returns direct local filesystem path so audioplayers uses native DeviceFileSource,
        completely avoiding cleartext HTTP localhost (127.0.0.1) network policy blocks.
        On Windows, routes through local_media_server on 127.0.0.1 for RFC 7233 range-request seeking.
        """
        if not local_path or not os.path.exists(local_path):
            return ""

        import platform as sys_platform
        if sys_platform.system() == "Windows":
            try:
                from src.local_media_server import asset_url
                return asset_url(local_path)
            except Exception as ex:
                logger.error(f"Error resolving local_media_server URL for {local_path}: {ex}")
                return Path(local_path).as_uri()
        else:
            # Android/Linux/macOS/iOS: native local file path
            return str(local_path).replace("\\", "/")

    def _on_slider_prevent_seek(self, e=None):
        """Prevents manual seeking while keeping the thumb indicator vibrant green."""
        if self.duration_seconds > 0:
            self.slider.value = min(self.position_seconds, self.slider.max)
        else:
            self.slider.value = 0
        try:
            if getattr(self.slider, "page", None):
                self.slider.update()
        except Exception:
            pass

    async def _silent_verify_uri(self, uri: str) -> bool:
        """
        Silently tests in the background if the audio stream is genuinely accessible and ready to play,
        not just a validly formatted URL string.
        """
        if not uri or self.is_disposed:
            return False

        try:
            # Local loopback server (127.0.0.1)
            if "127.0.0.1" in uri or "localhost" in uri:
                async with httpx.AsyncClient(timeout=1.0) as client:
                    resp = await client.head(uri)
                    return resp.status_code in (200, 206)

            # Local file URI or Windows/POSIX local path
            if uri.startswith("file://") or (os.name == "nt" and ":\\" in uri) or uri.startswith("/"):
                clean_path = uri.replace("file:///", "").replace("file://", "")
                if os.path.exists(clean_path) and os.path.getsize(clean_path) > 500:
                    return True
                return False

            # If it's already an authenticated CDN URL from Nu-Age / Bunny CDN, it is verified by definition
            if "nu-age-cdn.b-cdn.net" in uri or "b-cdn.net" in uri or "bunny" in uri:
                return True

            # HTTP or HTTPS streaming URL
            async with httpx.AsyncClient(timeout=2.5, follow_redirects=True) as client:
                head_resp = await client.head(uri)
                if head_resp.status_code in (200, 206, 302, 307):
                    return True
        except Exception as ex:
            logger.debug(f"Silent audio verification notice for {uri}: {ex}")
            return False
        return False

    async def _prefetch_and_preload(self):
        """Proactively checks local offline DB and remote CDN cache, silently testing readiness before preloading."""
        if self.is_disposed:
            return

        # 1. Check local offline SQLite cache first (0ms load from disk)
        local_path = get_offline_lesson_audio(self.lesson_id, self.current_lang, self.target_page)
        if local_path and os.path.exists(local_path) and os.path.getsize(local_path) > 500:
            uri = self._safe_asset_url(local_path)
            print(f"[AUDIO] Found local disk cache for lesson {self.lesson_id} [{self.current_lang.upper()}]: {uri}", flush=True)
            self.is_verified_ready = self.duration_seconds > 0
            if self._current_loaded_uri != uri:
                self._current_loaded_uri = uri
                self.is_service_loaded = False
                self.audio_service.src = uri
                try:
                    self.audio_service.update()
                except Exception:
                    pass
            self._update_play_button_ui()
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self._refresh_duration)
            return

        # 2. If not on local disk, query backend info
        await self._prefetch_audio_info()
        cdn_url = self._cached_audio_urls.get(self.current_lang)
        if cdn_url:
            print(f"[AUDIO] Detected CDN audio URL for lesson {self.lesson_id} [{self.current_lang.upper()}]: {cdn_url}", flush=True)
            self.is_verified_ready = self.duration_seconds > 0
            if self._current_loaded_uri != cdn_url:
                self._current_loaded_uri = cdn_url
                self.is_service_loaded = False
                self.audio_service.src = cdn_url
                try:
                    self.audio_service.update()
                except Exception:
                    pass
                if hasattr(self.target_page, "run_task"):
                    self.target_page.run_task(self._refresh_duration)

            self._update_play_button_ui()
            # Automatically cache to local device storage in background for 0ms subsequent loads & offline play
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self._auto_cache_audio_to_disk, self.current_lang, cdn_url)
            return

        self.is_verified_ready = False
        self._update_play_button_ui()

    async def _prefetch_audio_info(self):
        """Fetches cached audio availability and active status from Nu-Age backend."""
        if self.is_disposed:
            return
        try:
            token = await self._get_auth_token_async()
            url = f"{self.api_base_url}/courses/lessons/{self.lesson_id}/narrate/info"
            params = {}
            if token:
                params["token"] = token
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url, headers=headers, params=params)
                if res.status_code == 200:
                    data = res.json()
                    self._cached_audio_urls = data.get("cached_languages", {}) or {}
                    print(f"[AUDIO] Available cached languages for lesson {self.lesson_id}: {list(self._cached_audio_urls.keys())}", flush=True)
        except Exception as ex:
            print(f"[AUDIO-NOTICE] Audio info prefetch notice: {ex}", flush=True)

    def _is_audio_ready(self, lang: Optional[str] = None) -> bool:
        check_lang = lang or self.current_lang
        # 1. Local offline SQLite cache
        if is_lesson_audio_cached(self.lesson_id, check_lang, self.target_page):
            return True
        # 2. Bunny CDN cache
        if check_lang in self._cached_audio_urls and self._cached_audio_urls[check_lang]:
            return True
        return False

    async def _resolve_stream_uri(self) -> Optional[str]:
        """
        Resolves audio URI strictly following:
        1. Check offline local disk cache first (0ms instantaneous playback).
        2. If not cached offline, check if URL is online (via cached metadata or GET /narrate/info).
           If online -> triggers background auto-caching to disk and returns the online URL.
        3. Returns None if audio is neither cached locally nor online (needs generation cycle).
        """
        # Step 1: Check offline local disk cache first
        local_path = get_offline_lesson_audio(self.lesson_id, self.current_lang, self.target_page)
        if local_path and os.path.exists(local_path):
            uri = self._safe_asset_url(local_path)
            print(f"[AUDIO] Serving from local disk cache: {uri}", flush=True)
            return uri

        # Step 2: Not cached offline -> check if URL is online
        cdn_url = self._cached_audio_urls.get(self.current_lang)
        if not cdn_url:
            try:
                await self._prefetch_audio_info()
                cdn_url = self._cached_audio_urls.get(self.current_lang)
            except Exception as ex:
                print(f"[AUDIO] Online check error: {ex}", flush=True)

        if cdn_url:
            print(f"[AUDIO] Serving from online URL: {cdn_url}", flush=True)
            # Cache offline in background so subsequent visits are 0ms & offline-ready
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self._auto_cache_audio_to_disk, self.current_lang, cdn_url)
            return cdn_url

        return None

    def _update_play_button_ui(self):
        """Immediately and reactively updates the play button icon, container, and slider."""
        if self.is_preparing:
            self.play_button.content = self.spinner
            self.play_button.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)
            self.play_button.tooltip = "Preparing audio..."
            self.slider.thumb_color = ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE)
            self.slider.active_color = ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE)
        elif self.is_loading:
            self.play_button.content = self.spinner
            self.play_button.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)
            self.play_button.tooltip = "Connecting audio..."
            self.slider.thumb_color = ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE)
            self.slider.active_color = ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE)
        elif self.is_playing:
            self.play_icon.icon = ft.Icons.PAUSE_ROUNDED
            self.play_icon.color = ft.Colors.ON_PRIMARY
            self.play_button.content = self.play_icon
            self.play_button.bgcolor = ft.Colors.PRIMARY
            self.play_button.tooltip = "Pause narration"
            self.slider.thumb_color = ft.Colors.PRIMARY
            self.slider.active_color = ft.Colors.PRIMARY
        else:
            if self.is_verified_ready:
                self.play_icon.icon = ft.Icons.PLAY_ARROW_ROUNDED
                self.play_icon.color = ft.Colors.ON_PRIMARY
                self.play_button.content = self.play_icon
                self.play_button.bgcolor = ft.Colors.PRIMARY
                self.play_button.tooltip = "Play audio narration"
                self.slider.thumb_color = ft.Colors.PRIMARY
                self.slider.active_color = ft.Colors.PRIMARY
            else:
                self.play_icon.icon = ft.Icons.PLAY_ARROW_ROUNDED
                self.play_icon.color = ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE)
                self.play_button.content = self.play_icon
                self.play_button.bgcolor = ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)
                self.play_button.tooltip = "Audio not ready yet (tap to prepare)"
                self.slider.thumb_color = ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE)
                self.slider.active_color = ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE)

        # Explicitly flush updates to the icon, container, slider, and page
        try:
            if getattr(self.play_icon, "page", None):
                self.play_icon.update()
        except Exception:
            pass
        try:
            if getattr(self.play_button, "page", None):
                self.play_button.update()
        except Exception:
            pass
        try:
            if getattr(self.slider, "page", None):
                self.slider.update()
        except Exception:
            pass
        try:
            if self.target_page:
                self.target_page.update()
        except Exception:
            pass

    def _toggle_play_click(self, e=None):
        if self._is_busy:
            return

        logger.info(f"Play clicked! playing={self.is_playing}, preparing={self.is_preparing}, ready={self.is_verified_ready}")
        if self.is_playing:
            self.is_playing = False
            self.pending_play_request = False
            self._update_play_button_ui()
            self._stop_waveform_animation()
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self.pause_playback)
            return

        if self.is_preparing:
            self._show_snackbar("Audio is being prepared for this lesson. Check back in a moment!")
            return

        # Definitively disallow play unless absolutely ready (audio loaded and total duration minutes known)
        if not self.is_verified_ready or self.duration_seconds <= 0:
            self._show_snackbar("Loading audio narration... Please wait a second.")
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self._refresh_duration)
            return

        if self.is_loading:
            return

        # Start playback resolution task with zero delay
        self._is_busy = True
        self.pending_play_request = True
        self.is_loading = True
        self._update_play_button_ui()
        if hasattr(self.target_page, "run_task"):
            self.target_page.run_task(self._resolve_and_play)

    async def _resolve_and_play(self):
        """
        Orchestrates playback lifecycle:
        1. Checks offline local disk cache -> if found, plays immediately (0ms).
        2. If not cached offline, checks if audio URL is online (via cached metadata or GET /narrate/info).
           If online -> caches offline in background and plays immediately.
        3. If not online, transitions to the generation cycle -> auto-plays upon completion.
        """
        if self.is_disposed:
            self._is_busy = False
            return

        lang = self.current_lang
        try:
            uri = await self._resolve_stream_uri()
            if uri:
                self.is_verified_ready = True
                await self.start_playback(resolved_uri=uri)
                self._is_busy = False
                return
        except Exception as ex:
            print(f"[AUDIO] Error resolving stream URI: {ex}", flush=True)

        # Step 3: Not cached offline and not online -> Go into generation cycle
        print(f"[AUDIO] Audio for lesson {self.lesson_id} [{lang.upper()}] is not cached locally or online. Initiating generation cycle...", flush=True)
        self.is_loading = False
        self.is_preparing = True
        self._update_play_button_ui()
        self._show_snackbar("Preparing audio narration for this lesson. Please wait a moment...")
        try:
            await self._prepare_and_poll_audio(lang)
        finally:
            self._is_busy = False

    async def _prepare_and_poll_audio(self, lang: str):
        """Asynchronously requests synthesis and polls until cached in DB / Bunny CDN."""
        print(f"[AUDIO-POLLER] Requesting audio preparation from backend for lesson {self.lesson_id} [{lang.upper()}]...", flush=True)
        token = await self._get_auth_token_async()
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        # 1. Trigger backend preparation endpoint
        should_poll = False
        try:
            prep_url = f"{self.api_base_url}/courses/lessons/{self.lesson_id}/narrate/prepare"
            params = {"lang": lang}
            if token:
                params["token"] = token
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(prep_url, headers=headers, params=params)
                print(f"[AUDIO-POLLER] Prepare endpoint responded: HTTP {res.status_code}", flush=True)
                if res.status_code == 200:
                    data = res.json()
                    print(f"[AUDIO-POLLER] Prepare payload: {data}", flush=True)
                    if (data.get("cached") or data.get("status") == "ready") and data.get("audio_url"):
                        self._cached_audio_urls[lang] = data["audio_url"]
                        self._on_audio_preparation_ready(lang)
                        return
                    elif data.get("status") == "generating" or not data.get("cached"):
                        should_poll = True
                elif res.status_code == 404:
                    print(f"[AUDIO-POLLER] Lesson {self.lesson_id} not found (404) during audio prepare.", flush=True)
                    self.is_preparing = False
                    self._update_play_button_ui()
                    self._show_snackbar("Lesson audio narration is not available.")
                    return
                elif res.status_code in (400, 401, 403, 422, 500, 502, 503):
                    print(f"[AUDIO-POLLER] Audio prepare returned status {res.status_code} for lesson {self.lesson_id}", flush=True)
                    self.is_preparing = False
                    self._update_play_button_ui()
                    self._show_snackbar("Audio narration is temporarily unavailable.")
                    return
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as ex:
            print(f"[AUDIO-POLLER] Network error: {ex}", flush=True)
            self.is_preparing = False
            self._update_play_button_ui()
            self._show_snackbar("Audio narration is not cached offline and you appear to be offline.")
            return
        except Exception as ex:
            print(f"[AUDIO-POLLER] Prepare trigger notice: {ex}", flush=True)
            should_poll = True

        if not should_poll:
            self.is_preparing = False
            self._update_play_button_ui()
            return

        # 2. Poll /narrate/info every 1.5 seconds directly from PostgreSQL (up to 90s)
        max_attempts = 60
        print(f"[AUDIO-POLLER] Audio is generating on backend. Polling /narrate/info every 1.5s for up to 90s...", flush=True)
        for attempt in range(max_attempts):
            if self.is_disposed or not self.is_preparing or self.current_lang != lang:
                print(f"[AUDIO-POLLER] Polling terminated (player closed or language switched).", flush=True)
                return
            await asyncio.sleep(1.5)
            if self.is_disposed or not self.is_preparing or self.current_lang != lang:
                return

            try:
                info_url = f"{self.api_base_url}/courses/lessons/{self.lesson_id}/narrate/info"
                info_params = {}
                if token:
                    info_params["token"] = token
                async with httpx.AsyncClient(timeout=8.0) as client:
                    res = await client.get(info_url, headers=headers, params=info_params)
                    if res.status_code == 200:
                        data = res.json()
                        cached_map = data.get("cached_languages", {}) or {}
                        self._cached_audio_urls.update(cached_map)
                        if lang in cached_map and cached_map[lang]:
                            print(f"[AUDIO-POLLER] >>> AUDIO READY DETECTED on poll #{attempt+1}! URL: {cached_map[lang]}", flush=True)
                            self._on_audio_preparation_ready(lang)
                            return
                        else:
                            print(f"[AUDIO-POLLER] Poll #{attempt+1}/{max_attempts}: Still generating... (cached: {list(cached_map.keys())})", flush=True)
                    elif res.status_code == 404:
                        print(f"[AUDIO-POLLER] Lesson {self.lesson_id} not found (404) during info poll. Aborting.", flush=True)
                        self.is_preparing = False
                        self._update_play_button_ui()
                        self._show_snackbar("Lesson audio narration is not available.")
                        return
                    elif res.status_code in (401, 403):
                        self.is_preparing = False
                        self._update_play_button_ui()
                        return
            except Exception as ex:
                print(f"[AUDIO-POLLER] Poll #{attempt+1} notice: {ex}", flush=True)

        # If timed out without caching
        if self.is_preparing and self.current_lang == lang:
            print(f"[AUDIO-POLLER] Generation timed out after 90 seconds.", flush=True)
            self.is_preparing = False
            self._update_play_button_ui()
            self._show_snackbar("Audio is taking longer than usual. Please check back shortly.")

    def _on_audio_preparation_ready(self, lang: str):
        """Called as soon as backend signals audio is synthesized and cached."""
        print(f"[AUDIO-POLLER] >>> PREPARATION COMPLETED for lesson={self.lesson_id} [{lang.upper()}]!", flush=True)
        self.is_preparing = False
        self.is_verified_ready = True
        if self.current_lang == lang:
            self._update_play_button_ui()
            self._show_snackbar("The transcript audio for this lesson is ready!")
            cdn_url = self._cached_audio_urls.get(lang)
            if cdn_url:
                # Automatically download and cache to local disk in background
                if hasattr(self.target_page, "run_task"):
                    self.target_page.run_task(self._auto_cache_audio_to_disk, lang, cdn_url)

                # Automatically start playback!
                if hasattr(self.target_page, "run_task"):
                    self.target_page.run_task(self.start_playback, cdn_url)

    async def start_playback(self, resolved_uri: Optional[str] = None):
        """Starts audio playback cleanly using flet_audio.Audio service."""
        if self.is_disposed:
            return

        uri = resolved_uri or await self._resolve_stream_uri()
        if not uri:
            self.is_loading = False
            self.is_playing = False
            self.pending_play_request = False
            self._update_play_button_ui()
            self._show_snackbar("Audio narration is not cached offline and you appear to be offline.")
            return

        try:
            target_pos_ms = int(self.position_seconds * 1000)
            print(f"[AUDIO] Starting playback from {self.position_seconds:.1f}s ({target_pos_ms}ms) -> URI: {uri}", flush=True)
            self.is_loading = False
            self.is_playing = True
            self.pending_play_request = False
            self._update_play_button_ui()
            self._start_waveform_animation()

            # Ensure audio_service is registered in page.services
            if hasattr(self.target_page, "services"):
                if self.audio_service not in self.target_page.services:
                    self.target_page.services.append(self.audio_service)
                    try:
                        self.target_page.update()
                    except Exception:
                        pass

            async def _do_play(target_uri: str, pos_ms: int):
                if self._current_loaded_uri != target_uri or not self.audio_service.src:
                    self._current_loaded_uri = target_uri
                    self.audio_service.src = target_uri
                    self.audio_service.playback_rate = self.current_speed
                    try:
                        self.audio_service.update()
                    except Exception:
                        pass
                    # Yield slightly so the Flutter audio plugin attaches the source
                    await asyncio.sleep(0.1)

                import platform as sys_platform
                is_windows = sys_platform.system() == "Windows"
                if is_windows:
                    # In audioplayers_windows/Flutter, calling play(position=int) attempts concurrent
                    # seek+init in Windows Media Foundation which hangs indefinitely.
                    # Calling seek(pos_ms) followed by resume() starts playback immediately without hanging.
                    if pos_ms > 0:
                        try:
                            await self.audio_service.seek(pos_ms)
                        except Exception as s_ex:
                            print(f"[AUDIO] Seek notice: {s_ex}", flush=True)
                    await self.audio_service.resume()
                else:
                    # On Android, iOS, macOS, Linux: Audio.play() transitions the player into PLAYING state.
                    # Resume() on a stopped/newly assigned source is a silent no-op on Android audioplayers.
                    if pos_ms > 0:
                        try:
                            await self.audio_service.play(position=pos_ms)
                        except Exception:
                            await self.audio_service.play()
                    else:
                        await self.audio_service.play()

            try:
                # 6-second bounded execution
                await asyncio.wait_for(_do_play(uri, target_pos_ms), timeout=6.0)
            except Exception as play_ex:
                print(f"[AUDIO-RECOVERY] Playback attempt notice: {play_ex}", flush=True)

                # 1. If starting from position > 0 failed, retry from beginning (0ms)
                recovered = False
                if target_pos_ms > 0:
                    try:
                        print(f"[AUDIO-RECOVERY] Retrying playback from beginning (0s)...", flush=True)
                        self.position_seconds = 0.0
                        await asyncio.wait_for(_do_play(uri, 0), timeout=5.0)
                        recovered = True
                    except Exception as r_ex:
                        print(f"[AUDIO-RECOVERY] Beginning retry notice: {r_ex}", flush=True)

                # 2. If playing local file failed, fall back to remote CDN stream if available
                cdn_url = self._cached_audio_urls.get(self.current_lang)
                if not recovered and not cdn_url:
                    try:
                        await self._prefetch_audio_info()
                        cdn_url = self._cached_audio_urls.get(self.current_lang)
                    except Exception:
                        pass

                if not recovered and cdn_url and uri != cdn_url:
                    try:
                        print(f"[AUDIO-RECOVERY] Falling back to remote CDN stream: {cdn_url}", flush=True)
                        await asyncio.wait_for(_do_play(cdn_url, 0), timeout=6.0)
                        recovered = True
                    except Exception as cdn_ex:
                        print(f"[AUDIO-RECOVERY] CDN fallback notice: {cdn_ex}", flush=True)

                if not recovered:
                    raise play_ex

            # Schedule background duration fetch
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self._refresh_duration)

        except Exception as e:
            print(f"[AUDIO-ERROR] Error starting audio: {type(e).__name__}: {e}", flush=True)
            self.is_loading = False
            self.is_playing = False
            self.pending_play_request = False
            self._update_play_button_ui()
            self._stop_waveform_animation()
            self._show_snackbar("Could not start audio playback. Please retry.")

    async def pause_playback(self):
        print(f"[AUDIO] Paused audio at {self.position_seconds:.1f}s", flush=True)
        self.is_playing = False
        self.is_loading = False
        self._update_play_button_ui()
        self._stop_waveform_animation()
        try:
            await self.audio_service.pause()
        except Exception as ex:
            print(f"[AUDIO-ERROR] Pause notice: {ex}", flush=True)
            logger.debug(f"Pause notice: {ex}")

    def dispose(self):
        self.is_disposed = True
        self.is_playing = False
        self.is_loading = False
        self.is_preparing = False
        self._is_busy = False
        self._stop_waveform_animation()
        if hasattr(self, "audio_service") and self.audio_service:
            try:
                self.audio_service.volume = 0.0
            except Exception:
                pass
            try:
                if hasattr(self.target_page, "run_task"):
                    self.target_page.run_task(self._safe_async_release)
            except Exception:
                pass
            if hasattr(self.target_page, "services") and self.audio_service in self.target_page.services:
                try:
                    self.target_page.services.remove(self.audio_service)
                except Exception:
                    pass

    async def _safe_async_release(self):
        try:
            await self.audio_service.pause()
        except Exception:
            pass
        try:
            await self.audio_service.release()
        except Exception:
            pass

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_select_language_click(self, e):
        if isinstance(e, str):
            new_lang = e
        elif hasattr(e, "control") and hasattr(e.control, "data"):
            new_lang = e.control.data
        elif hasattr(e, "data"):
            new_lang = e.data
        else:
            new_lang = str(e)

        if new_lang == self.current_lang:
            return

        # 1. Immediately terminate active playback and animation
        self.is_playing = False
        self.is_loading = False
        self.is_service_loaded = False
        self.is_verified_ready = False
        self._is_busy = False
        self.pending_play_request = False
        self._stop_waveform_animation()
        self.is_preparing = False

        try:
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self.audio_service.pause)
        except Exception:
            pass

        self.current_lang = new_lang
        self._current_loaded_uri = None
        self.slider.value = 0
        self.slider.thumb_color = ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE)
        self.slider.active_color = ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE)
        self.position_seconds = 0.0
        self.duration_seconds = 0.0
        self.time_label.value = "00:00 / 00:00"

        if hasattr(self, "lang_label_text") and self.lang_label_text:
            self.lang_label_text.value = self._get_current_lang_label()

        # 2. Proactively preload the new language if already cached
        if hasattr(self.target_page, "run_task"):
            self.target_page.run_task(self._prefetch_and_preload)

        self._update_play_button_ui()
        self.render_ui()
        try:
            self.target_page.update()
        except Exception:
            pass

    def _toggle_speed_click(self, e=None):
        speeds = [1.0, 1.25, 1.5, 2.0]
        curr_idx = speeds.index(self.current_speed) if self.current_speed in speeds else 0
        self.current_speed = speeds[(curr_idx + 1) % len(speeds)]
        self.speed_btn.content.value = f"{self.current_speed}x"
        try:
            self.audio_service.playback_rate = self.current_speed
            self.audio_service.update()
        except Exception:
            pass
        try:
            self.target_page.update()
        except Exception:
            pass

    def _on_player_loaded(self, e=None):
        logger.info(f"Audio loaded for lesson {self.lesson_id}")
        self.is_service_loaded = True
        self.is_verified_ready = True
        self._is_busy = False
        self._update_play_button_ui()
        if self.pending_play_request:
            self.pending_play_request = False
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self.start_playback)
        elif not self.is_playing and self.is_loading:
            self.is_loading = False
            self.is_playing = True
            self._update_play_button_ui()
            self._start_waveform_animation()

    def _on_player_state_changed(self, e=None):
        raw_state = getattr(e, "state", None)
        if raw_state is None:
            raw_state = getattr(e, "data", None)
        if isinstance(raw_state, dict):
            raw_state = raw_state.get("state") or raw_state.get("data")
        state_val = getattr(raw_state, "value", str(raw_state or "")).lower()
        if "." in state_val:
            state_val = state_val.split(".")[-1]
        logger.info(f"Audio state changed: {state_val}")

        if state_val == "playing":
            self.is_playing = True
            self.is_loading = False
            self._is_busy = False
            self._update_play_button_ui()
            self._start_waveform_animation()
        elif state_val in ("paused", "stopped"):
            self.is_playing = False
            self.is_loading = False
            self._is_busy = False
            self._update_play_button_ui()
            self._stop_waveform_animation()
        elif state_val == "completed":
            self._on_player_completed()

    def _on_player_completed(self, e=None):
        logger.info(f"Audio playback completed for lesson {self.lesson_id}")
        self.is_playing = False
        self.is_loading = False
        self._is_busy = False
        self.slider.value = 0
        self.position_seconds = 0.0
        self._update_play_button_ui()
        self._stop_waveform_animation()
        dur_str = self._format_time(self.duration_seconds)
        self.time_label.value = f"00:00 / {dur_str}"
        try:
            self.target_page.update()
        except Exception:
            pass

    def _extract_duration_seconds(self, dur_val: Any) -> float:
        if dur_val is None:
            return 0.0
        if hasattr(dur_val, "in_seconds") and dur_val.in_seconds is not None:
            try:
                return float(dur_val.in_seconds)
            except Exception:
                pass
        if hasattr(dur_val, "in_milliseconds") and dur_val.in_milliseconds is not None:
            try:
                return float(dur_val.in_milliseconds) / 1000.0
            except Exception:
                pass
        if hasattr(dur_val, "total_seconds"):
            try:
                return float(dur_val.total_seconds())
            except Exception:
                pass
        try:
            val = float(dur_val)
            if val > 1000:
                return val / 1000.0
            return val
        except Exception:
            return 0.0

    def _extract_position_seconds(self, pos_val: Any) -> float:
        if pos_val is None:
            return 0.0
        if hasattr(pos_val, "in_seconds") and pos_val.in_seconds is not None:
            try:
                return float(pos_val.in_seconds)
            except Exception:
                pass
        if hasattr(pos_val, "in_milliseconds") and pos_val.in_milliseconds is not None:
            try:
                return float(pos_val.in_milliseconds) / 1000.0
            except Exception:
                pass
        try:
            val = float(pos_val)
            # Audioplayers emits position in milliseconds as an int
            return val / 1000.0
        except Exception:
            return 0.0

    async def _refresh_duration(self):
        """Queries audio duration from the service with retries if on_duration_change has not fired yet."""
        if self.is_disposed or not hasattr(self, "audio_service"):
            return

        for attempt in range(6):
            if self.is_disposed:
                return
            await asyncio.sleep(0.3 * (attempt + 1))
            if self.is_disposed or self.duration_seconds > 0:
                return
            try:
                dur = await asyncio.wait_for(self.audio_service.get_duration(), timeout=2.0)
                sec = self._extract_duration_seconds(dur)
                if sec > 0:
                    self.duration_seconds = sec
                    self.slider.max = max(1.0, self.duration_seconds)
                    self.is_service_loaded = True
                    self.is_verified_ready = True
                    dur_str = self._format_time(self.duration_seconds)
                    pos_str = self._format_time(self.position_seconds)
                    self.time_label.value = f"{pos_str} / {dur_str}"
                    self._update_play_button_ui()
                    try:
                        self.target_page.update()
                    except Exception:
                        pass

                    if self.pending_play_request:
                        self.pending_play_request = False
                        if hasattr(self.target_page, "run_task"):
                            self.target_page.run_task(self.start_playback)
                    return
            except Exception as ex:
                logger.debug(f"Refresh duration attempt #{attempt+1} notice: {ex}")

    def _on_player_duration_changed(self, e=None):
        try:
            dur_val = getattr(e, "duration", None)
            if dur_val is None:
                dur_val = getattr(e, "data", None)
            sec = self._extract_duration_seconds(dur_val)
            if sec > 0:
                self.duration_seconds = sec
                self.slider.max = max(1.0, self.duration_seconds)
                self.is_service_loaded = True
                self.is_verified_ready = True
                dur_str = self._format_time(self.duration_seconds)
                pos_str = self._format_time(self.position_seconds)
                self.time_label.value = f"{pos_str} / {dur_str}"
                self._update_play_button_ui()
                try:
                    self.target_page.update()
                except Exception:
                    pass

                if self.pending_play_request:
                    self.pending_play_request = False
                    if hasattr(self.target_page, "run_task"):
                        self.target_page.run_task(self.start_playback)
        except Exception as ex:
            logger.debug(f"Duration event notice: {ex}")

    def _on_player_position_changed(self, e=None):
        try:
            pos_val = getattr(e, "position", None)
            if pos_val is None:
                pos_val = getattr(e, "data", None)
            sec = self._extract_position_seconds(pos_val)
            if sec >= 0:
                self.position_seconds = sec
                # If audio is progressing, ensure playing state and UI icon reflect it
                if sec > 0 and not self.is_playing:
                    self.is_playing = True
                    self.is_loading = False
                    self._is_busy = False
                    self._update_play_button_ui()
                    self._start_waveform_animation()

                if self.duration_seconds > 0:
                    self.slider.max = max(1.0, self.duration_seconds)
                    self.slider.value = min(self.position_seconds, self.slider.max)

                dur_str = self._format_time(self.duration_seconds)
                pos_str = self._format_time(self.position_seconds)
                self.time_label.value = f"{pos_str} / {dur_str}"
                try:
                    self.target_page.update()
                except Exception:
                    pass
        except Exception as ex:
            logger.debug(f"Position event notice: {ex}")

    # =========================================================================
    # AUTOMATIC LOCAL CACHING (0ms subsequent loads, seamless offline playback)
    # =========================================================================

    async def _auto_cache_audio_to_disk(self, lang: str, cdn_url: str):
        """Seamlessly downloads audio into local device storage with single-flight locking for 0ms subsequent loads."""
        if not cdn_url or self.is_disposed:
            return

        download_key = f"{self.lesson_id}:{lang}"
        if download_key in _global_active_downloads:
            print(f"[AUDIO-CACHE] Download already in-flight for {download_key}, skipping duplicate task.", flush=True)
            return

        existing = get_offline_lesson_audio(self.lesson_id, lang, self.target_page)
        if existing and os.path.exists(existing) and os.path.getsize(existing) > 1000:
            print(f"[AUDIO-CACHE] Audio already cached locally: {existing}", flush=True)
            return

        _global_active_downloads.add(download_key)
        print(f"[AUDIO-CACHE] Downloading {lang.upper()} audio for offline & fast local playback from {cdn_url}...", flush=True)
        try:
            root = _course_assets_root()
            if str(root).startswith('/'):
                audio_dir = f"{root.rstrip('/')}/audio/{self.course_id or 'default'}"
            else:
                audio_dir = os.path.normpath(os.path.join(root, "audio", str(self.course_id or "default")))
            os.makedirs(audio_dir, exist_ok=True)
            local_filename = f"lesson_{self.lesson_id}_{lang}.mp3"
            if str(audio_dir).startswith('/'):
                local_filepath = f"{audio_dir.rstrip('/')}/{local_filename}"
            else:
                local_filepath = os.path.normpath(os.path.join(audio_dir, local_filename))

            posix_filepath = str(local_filepath).replace('\\', '/')

            async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
                res = await client.get(cdn_url)
                if res.status_code == 200:
                    with open(posix_filepath, "wb") as f:
                        f.write(res.content)
                    save_offline_lesson_audio(
                        lesson_id=self.lesson_id,
                        course_id=self.course_id,
                        language=lang,
                        local_path=posix_filepath,
                        remote_url=cdn_url,
                        size_bytes=len(res.content),
                        page=self.target_page,
                    )
                    print(f"[AUDIO-CACHE] [SUCCESS] Audio cached to device storage: {posix_filepath} ({len(res.content)} bytes)", flush=True)
                    # If this language is currently active and playback is not active, upgrade to local file
                    if self.current_lang == lang and not self.is_playing:
                        local_uri = self._safe_asset_url(posix_filepath)
                        self._current_loaded_uri = local_uri
                        self.audio_service.src = local_uri
                        try:
                            self.audio_service.update()
                        except Exception:
                            pass
                        if self.duration_seconds <= 0 and hasattr(self.target_page, "run_task"):
                            self.target_page.run_task(self._refresh_duration)
        except Exception as ex:
            print(f"[AUDIO-CACHE] [NOTICE] Auto-caching notice (playback continues via CDN): {ex}", flush=True)
        finally:
            _global_active_downloads.discard(download_key)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _start_waveform_animation(self):
        if getattr(self, "_is_animating_waveform", False):
            return
        self._is_animating_waveform = True

        async def _animate():
            patterns = [
                [6, 14, 18, 10],
                [12, 18, 8, 16],
                [18, 8, 16, 12],
                [10, 16, 12, 6],
                [14, 10, 18, 8],
            ]
            step = 0
            while self.is_playing and not self.is_disposed:
                curr_pattern = patterns[step % len(patterns)]
                step += 1
                for i, bar in enumerate(self.wave_bars):
                    bar.height = curr_pattern[i]
                try:
                    if getattr(self.waveform_row, "page", None):
                        self.waveform_row.update()
                    elif self.target_page:
                        self.target_page.update()
                except Exception:
                    break
                await asyncio.sleep(0.18)

            self._is_animating_waveform = False
            for bar in self.wave_bars:
                bar.height = 6
            try:
                if getattr(self.waveform_row, "page", None):
                    self.waveform_row.update()
                elif self.target_page:
                    self.target_page.update()
            except Exception:
                pass

        if hasattr(self.target_page, "run_task"):
            self.target_page.run_task(_animate)

    def _stop_waveform_animation(self):
        self._is_animating_waveform = False
        for bar in self.wave_bars:
            bar.height = 6
        try:
            if getattr(self.waveform_row, "page", None):
                self.waveform_row.update()
            elif self.target_page:
                self.target_page.update()
        except Exception:
            pass

    def _format_time(self, total_seconds: float) -> str:
        s = int(total_seconds or 0)
        m = s // 60
        sec = s % 60
        return f"{m:02d}:{sec:02d}"

    def _show_snackbar(self, message: str):
        try:
            show_page_snackbar(self.target_page, message)
        except Exception:
            pass
