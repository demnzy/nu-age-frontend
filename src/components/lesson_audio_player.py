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
from typing import Optional, List, Dict, Any
import httpx
import flet as ft
import flet_audio as fta

from src.local_db import (
    get_offline_lesson_audio,
    save_offline_lesson_audio,
    is_lesson_audio_cached,
)
from src.local_media_server import asset_url
from src.utils.file_opener import show_page_snackbar

logger = logging.getLogger("lesson_audio_player")

BASE_URL = os.getenv("API_URL", "https://api.nu-age.name.ng").rstrip("/")

LANGUAGES = [
    {"code": "en", "label": "English", "flag": "🇬🇧"},
    {"code": "ha", "label": "Hausa", "flag": "🇳🇬"},
    {"code": "fr", "label": "French", "flag": "🇫🇷"},
]


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
        self._is_scrubbing = False
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
            on_seek_complete=self._on_player_seek_complete,
        )

        # Attach audio service to Page services lifecycle
        if hasattr(self.target_page, "services"):
            if self.audio_service not in self.target_page.services:
                self.target_page.services.append(self.audio_service)

        # 2. Direct-Tap Play / Pause Button
        self.play_icon = ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=20, color=ft.Colors.ON_PRIMARY)
        self.spinner = ft.ProgressRing(width=18, height=18, stroke_width=2.5, color=ft.Colors.ON_PRIMARY)

        # 2b. Mini pulsing sound wave for preparation state
        self.prep_wave_bars = [
            ft.Container(
                width=2.5,
                height=6,
                border_radius=ft.BorderRadius.all(1.5),
                bgcolor=ft.Colors.ON_PRIMARY,
                animate=ft.Animation(160, ft.AnimationCurve.EASE_IN_OUT),
            )
            for _ in range(3)
        ]
        self.prep_wave_row = ft.Row(
            controls=self.prep_wave_bars,
            spacing=2.5,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.play_button = ft.Container(
            content=self.play_icon,
            width=36,
            height=36,
            border_radius=ft.BorderRadius.all(18),
            bgcolor=ft.Colors.PRIMARY,
            alignment=ft.Alignment.CENTER,
            ink=True,
            on_click=self._toggle_play_click,
            tooltip="Play audio narration",
        )

        # 3. Waveform Visualizer
        self.wave_bars = [
            ft.Container(
                width=3,
                height=6,
                border_radius=2,
                bgcolor=ft.Colors.PRIMARY,
                animate=ft.Animation(180, ft.AnimationCurve.EASE_IN_OUT),
            )
            for _ in range(4)
        ]
        self.waveform_row = ft.Row(
            controls=self.wave_bars,
            spacing=2.5,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 4. Interactive Scrubber Slider
        self.slider = ft.Slider(
            min=0,
            max=100,
            value=0,
            active_color=ft.Colors.PRIMARY,
            inactive_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
            on_change=self._on_slider_change,
            on_change_end=self._on_slider_change_end,
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

        # 7. Offline Download / Cached Badge
        self.offline_action_btn = ft.IconButton(
            icon=ft.Icons.DOWNLOAD_FOR_OFFLINE_ROUNDED,
            icon_size=18,
            width=34,
            height=34,
            icon_color=ft.Colors.ON_SURFACE_VARIANT,
            tooltip="Save audio offline",
            on_click=self._on_download_offline_click,
        )

    def _build_lang_selector(self) -> ft.Row:
        is_mobile = self._is_mobile()
        lang_items = []
        for l in LANGUAGES:
            is_sel = l["code"] == self.current_lang
            lang_items.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(l["flag"], size=12),
                            ft.Text(
                                l["code"].upper(),
                                size=11,
                                weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500,
                                color=ft.Colors.PRIMARY if is_sel else ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=3,
                        tight=True,
                    ),
                    padding=ft.Padding.symmetric(horizontal=6, vertical=3) if is_mobile else ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(6),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_sel else ft.Colors.TRANSPARENT,
                    border=ft.Border.all(
                        1.2 if is_sel else 1,
                        ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE),
                    ),
                    ink=True,
                    data=l["code"],
                    on_click=self._on_select_language_click,
                )
            )
        return ft.Row(controls=lang_items, spacing=4, tight=True)

    def render_ui(self):
        """Assembles a permanent, stable layout with zero invisible video controls."""
        is_cached = is_lesson_audio_cached(self.lesson_id, self.current_lang, self.target_page)
        is_mobile = self._is_mobile()

        if is_cached:
            self.offline_action_btn.icon = ft.Icons.OFFLINE_PIN_ROUNDED
            self.offline_action_btn.icon_color = ft.Colors.GREEN_600
            self.offline_action_btn.tooltip = "Audio saved for offline study"
        else:
            self.offline_action_btn.icon = ft.Icons.DOWNLOAD_FOR_OFFLINE_ROUNDED
            self.offline_action_btn.icon_color = ft.Colors.ON_SURFACE_VARIANT
            self.offline_action_btn.tooltip = "Save audio offline"

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
                                expand=True,
                            ),
                            lang_selector,
                            self.offline_action_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            self.play_button,
                            self.slider,
                            self.time_label,
                            self.speed_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                ],
                spacing=6,
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
                    self.offline_action_btn,
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

    async def _prefetch_and_preload(self):
        """Proactively checks local offline DB and remote CDN cache, preloading audio onto the service."""
        if self.is_disposed:
            return

        # 1. Check local offline SQLite cache first
        local_path = get_offline_lesson_audio(self.lesson_id, self.current_lang, self.target_page)
        if local_path and os.path.exists(local_path):
            uri = asset_url(local_path)
            self._current_loaded_uri = uri
            self.audio_service.src = uri
            try:
                self.audio_service.update()
            except Exception:
                pass
            return

        # 2. If not offline, query backend info
        await self._prefetch_audio_info()
        cdn_url = self._cached_audio_urls.get(self.current_lang)
        if cdn_url and not self.audio_service.src:
            self._current_loaded_uri = cdn_url
            self.audio_service.src = cdn_url
            try:
                self.audio_service.update()
            except Exception:
                pass

    async def _prefetch_audio_info(self):
        """Fetches cached audio availability and active status from Nu-Age backend."""
        if self.is_disposed or self.is_offline_mode:
            return
        try:
            token = await self._get_auth_token_async()
            url = f"{self.api_base_url}/courses/lessons/{self.lesson_id}/narrate/info"
            if token:
                url += f"?token={token}"
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    self._cached_audio_urls = data.get("cached_languages", {}) or {}
                    logger.info(f"Loaded cached audio info for lesson {self.lesson_id}: {list(self._cached_audio_urls.keys())}")
        except Exception as ex:
            logger.debug(f"Audio info prefetch notice: {ex}")

    def _is_audio_ready(self, lang: Optional[str] = None) -> bool:
        check_lang = lang or self.current_lang
        # 1. Local offline SQLite cache
        if is_lesson_audio_cached(self.lesson_id, check_lang, self.target_page):
            return True
        # 2. Bunny CDN cache
        if check_lang in self._cached_audio_urls and self._cached_audio_urls[check_lang]:
            return True
        return False

    async def _resolve_stream_uri(self) -> str:
        local_path = get_offline_lesson_audio(self.lesson_id, self.current_lang, self.target_page)
        if local_path and os.path.exists(local_path):
            logger.info(f"Serving offline audio: {local_path}")
            return asset_url(local_path)

        if self.is_offline_mode:
            return ""

        # Return static Bunny CDN URL if already confirmed ready
        cdn_url = self._cached_audio_urls.get(self.current_lang)
        if cdn_url:
            return cdn_url

        return ""

    def _update_play_button_ui(self):
        """Immediately and reactively updates the play button icon and repaints the container."""
        if self.is_preparing:
            self.play_button.content = self.prep_wave_row
            self.play_button.tooltip = "Preparing audio..."
        elif self.is_loading:
            self.play_button.content = self.spinner
            self.play_button.tooltip = "Connecting audio..."
        elif self.is_playing:
            self.play_icon.icon = ft.Icons.PAUSE_ROUNDED
            self.play_button.content = self.play_icon
            self.play_button.tooltip = "Pause narration"
        else:
            self.play_icon.icon = ft.Icons.PLAY_ARROW_ROUNDED
            self.play_button.content = self.play_icon
            self.play_button.tooltip = "Play audio narration"

        # Explicitly flush updates to the icon, container, and page
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
            if self.target_page:
                self.target_page.update()
        except Exception:
            pass

    def _toggle_play_click(self, e=None):
        logger.info(f"Play clicked! playing={self.is_playing}, preparing={self.is_preparing}")
        if self.is_playing:
            self.is_playing = False
            self._update_play_button_ui()
            self._stop_waveform_animation()
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self.pause_playback)
            return

        if self.is_preparing:
            self._show_snackbar("Audio is preparing for this lesson. Check back in a bit!")
            return

        if self.is_loading:
            return

        # Offline mode guard: if running in offline mode and audio is not cached locally, never reach out to network
        if self.is_offline_mode:
            local_path = get_offline_lesson_audio(self.lesson_id, self.current_lang, self.target_page)
            if local_path and os.path.exists(local_path):
                self.is_loading = True
                self._update_play_button_ui()
                self.target_page.run_task(self.start_playback)
            else:
                self._show_snackbar("Audio narration is not cached offline. You can still read the lesson below.")
            return

        # Check if current language is already ready
        if self._is_audio_ready(self.current_lang):
            self.is_loading = True
            self._update_play_button_ui()
            self.target_page.run_task(self.start_playback)
        else:
            # Trigger preparation flow with pulsing waveform!
            self.is_preparing = True
            self._update_play_button_ui()
            self._start_prep_wave_animation()
            self._show_snackbar("Audio is preparing for this lesson. Check back in a bit!")
            self.target_page.run_task(self._prepare_and_poll_audio, self.current_lang)

    async def _prepare_and_poll_audio(self, lang: str):
        """Asynchronously requests synthesis and polls until cached in DB / Bunny CDN."""
        token = await self._get_auth_token_async()
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        # 1. Trigger backend preparation endpoint
        should_poll = False
        try:
            prep_url = f"{self.api_base_url}/courses/lessons/{self.lesson_id}/narrate/prepare?lang={lang}"
            if token:
                prep_url += f"&token={token}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(prep_url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("cached") and data.get("audio_url"):
                        self._cached_audio_urls[lang] = data["audio_url"]
                        self._on_audio_preparation_ready(lang)
                        return
                    elif data.get("status") == "generating":
                        should_poll = True
                elif res.status_code == 404:
                    logger.warning(f"Lesson {self.lesson_id} not found (404) during audio prepare.")
                    self._stop_prep_wave_animation()
                    self.is_preparing = False
                    self._update_play_button_ui()
                    self._show_snackbar("Lesson audio narration is not available.")
                    return
                elif res.status_code in (400, 401, 403, 422, 500, 502, 503):
                    logger.warning(f"Audio prepare returned status {res.status_code} for lesson {self.lesson_id}")
                    self._stop_prep_wave_animation()
                    self.is_preparing = False
                    self._update_play_button_ui()
                    self._show_snackbar("Audio narration is temporarily unavailable.")
                    return
        except Exception as ex:
            logger.debug(f"Prepare trigger notice: {ex}")

        if not should_poll:
            self._stop_prep_wave_animation()
            self.is_preparing = False
            self._update_play_button_ui()
            return

        # 2. Poll /narrate/info every 1.5 seconds directly from PostgreSQL (up to 90s)
        max_attempts = 60
        for _ in range(max_attempts):
            if self.is_disposed or not self.is_preparing or self.current_lang != lang:
                return
            await asyncio.sleep(1.5)
            if self.is_disposed or not self.is_preparing or self.current_lang != lang:
                return

            try:
                info_url = f"{self.api_base_url}/courses/lessons/{self.lesson_id}/narrate/info"
                if token:
                    info_url += f"?token={token}"
                async with httpx.AsyncClient(timeout=8.0) as client:
                    res = await client.get(info_url, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        cached_map = data.get("cached_languages", {}) or {}
                        self._cached_audio_urls.update(cached_map)
                        if lang in cached_map and cached_map[lang]:
                            logger.info(f"Audio ready for lesson {self.lesson_id} [{lang}] -> {cached_map[lang]}")
                            self._on_audio_preparation_ready(lang)
                            return
                    elif res.status_code == 404:
                        logger.warning(f"Lesson {self.lesson_id} not found (404) during info poll. Aborting.")
                        self._stop_prep_wave_animation()
                        self.is_preparing = False
                        self._update_play_button_ui()
                        self._show_snackbar("Lesson audio narration is not available.")
                        return
                    elif res.status_code in (401, 403):
                        self._stop_prep_wave_animation()
                        self.is_preparing = False
                        self._update_play_button_ui()
                        return
            except Exception as ex:
                logger.debug(f"Poll info notice: {ex}")

        # If timed out without caching
        if self.is_preparing and self.current_lang == lang:
            self._stop_prep_wave_animation()
            self.is_preparing = False
            self._update_play_button_ui()
            self._show_snackbar("Audio is taking longer than usual. Please check back shortly.")

    def _on_audio_preparation_ready(self, lang: str):
        """Called as soon as backend signals audio is synthesized and cached."""
        self._stop_prep_wave_animation()
        self.is_preparing = False
        if self.current_lang == lang:
            self._update_play_button_ui()
            self._show_snackbar("The transcript audio for this lesson is ready!")
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self.start_playback)

    def _start_prep_wave_animation(self):
        async def _animate():
            heights = [6, 16, 10]
            step = 0
            while self.is_preparing and not self.is_disposed:
                step = (step + 1) % len(heights)
                for i, bar in enumerate(self.prep_wave_bars):
                    bar.height = heights[(step + i) % len(heights)]
                try:
                    self.target_page.update()
                except Exception:
                    break
                await asyncio.sleep(0.18)
            for bar in self.prep_wave_bars:
                bar.height = 6
            try:
                self.target_page.update()
            except Exception:
                pass

        if hasattr(self.target_page, "run_task"):
            self.target_page.run_task(_animate)

    def _stop_prep_wave_animation(self):
        for bar in self.prep_wave_bars:
            bar.height = 6
        try:
            self.target_page.update()
        except Exception:
            pass

    async def start_playback(self):
        """Starts audio playback cleanly using flet_audio.Audio service."""
        if self.is_disposed:
            return

        uri = await self._resolve_stream_uri()
        if not uri:
            self.is_loading = False
            self.is_playing = False
            self._update_play_button_ui()
            self._show_snackbar("Audio not cached offline. You can still read the lesson below.")
            return

        try:
            logger.info(f"Connecting flet_audio service to: {uri}")
            self.is_loading = False
            self.is_playing = True
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

            if self._current_loaded_uri == uri:
                try:
                    await self.audio_service.resume()
                except Exception:
                    await self.audio_service.play()
            else:
                self._current_loaded_uri = uri
                self.audio_service.src = uri
                self.audio_service.playback_rate = self.current_speed
                try:
                    self.audio_service.update()
                except Exception:
                    try:
                        self.target_page.update()
                    except Exception:
                        pass
                await self.audio_service.play()

            # Schedule background duration fetch
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self._refresh_duration)

        except Exception as e:
            logger.warning(f"Error starting audio: {e}")
            self.is_loading = False
            self.is_playing = False
            self._update_play_button_ui()
            self._stop_waveform_animation()

    async def pause_playback(self):
        self.is_playing = False
        self.is_loading = False
        self._update_play_button_ui()
        self._stop_waveform_animation()
        try:
            await self.audio_service.pause()
        except Exception as ex:
            logger.debug(f"Pause notice: {ex}")

    def dispose(self):
        self.is_disposed = True
        self.is_playing = False
        self.is_loading = False
        self.is_preparing = False
        self._stop_waveform_animation()
        self._stop_prep_wave_animation()
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
        new_lang = e.control.data
        if new_lang == self.current_lang:
            return

        # 1. Immediately terminate active playback and animation
        self.is_playing = False
        self.is_loading = False
        self._stop_waveform_animation()
        if self.is_preparing:
            self._stop_prep_wave_animation()
            self.is_preparing = False

        try:
            if hasattr(self.target_page, "run_task"):
                self.target_page.run_task(self.audio_service.pause)
        except Exception:
            pass

        self.current_lang = new_lang
        self._current_loaded_uri = None
        self.slider.value = 0
        self.position_seconds = 0.0
        self.duration_seconds = 0.0
        self.time_label.value = "00:00 / 00:00"

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
        if not self.is_playing and self.is_loading:
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
            self._update_play_button_ui()
            self._start_waveform_animation()
        elif state_val in ("paused", "stopped"):
            if not self._is_scrubbing:
                self.is_playing = False
                self.is_loading = False
                self._update_play_button_ui()
                self._stop_waveform_animation()
        elif state_val == "completed":
            self._on_player_completed()

    def _on_player_seek_complete(self, e=None):
        logger.debug(f"Seek completed for lesson {self.lesson_id}")

    def _on_player_completed(self, e=None):
        logger.info(f"Audio playback completed for lesson {self.lesson_id}")
        self.is_playing = False
        self.is_loading = False
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
        """Queries audio duration from the service if on_duration_change has not fired yet."""
        await asyncio.sleep(0.5)
        if self.is_disposed or not hasattr(self, "audio_service"):
            return
        try:
            dur = await self.audio_service.get_duration()
            sec = self._extract_duration_seconds(dur)
            if sec > 0:
                self.duration_seconds = sec
                self.slider.max = max(1.0, self.duration_seconds)
                dur_str = self._format_time(self.duration_seconds)
                pos_str = self._format_time(self.position_seconds)
                self.time_label.value = f"{pos_str} / {dur_str}"
                try:
                    self.target_page.update()
                except Exception:
                    pass
        except Exception as ex:
            logger.debug(f"Refresh duration notice: {ex}")

    def _on_player_duration_changed(self, e=None):
        try:
            dur_val = getattr(e, "duration", None)
            if dur_val is None:
                dur_val = getattr(e, "data", None)
            sec = self._extract_duration_seconds(dur_val)
            if sec > 0:
                self.duration_seconds = sec
                self.slider.max = max(1.0, self.duration_seconds)
                dur_str = self._format_time(self.duration_seconds)
                pos_str = self._format_time(self.position_seconds)
                self.time_label.value = f"{pos_str} / {dur_str}"
                try:
                    self.target_page.update()
                except Exception:
                    pass
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
                if sec > 0 and not self.is_playing and not self._is_scrubbing:
                    self.is_playing = True
                    self.is_loading = False
                    self._update_play_button_ui()
                    self._start_waveform_animation()
                if not self._is_scrubbing and self.duration_seconds > 0:
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

    def _on_slider_change(self, e):
        self._is_scrubbing = True
        target_sec = float(e.control.value)
        self.position_seconds = target_sec
        pos_str = self._format_time(self.position_seconds)
        dur_str = self._format_time(self.duration_seconds)
        self.time_label.value = f"{pos_str} / {dur_str}"
        try:
            self.target_page.update()
        except Exception:
            pass

    def _on_slider_change_end(self, e):
        target_sec = float(e.control.value)
        self.position_seconds = target_sec
        self._is_scrubbing = False
        if hasattr(self.target_page, "run_task"):
            self.target_page.run_task(self._safe_seek, int(target_sec * 1000))

    async def _safe_seek(self, position_ms: int):
        try:
            await self.audio_service.seek(ft.Duration(milliseconds=position_ms))
        except Exception as ex:
            logger.debug(f"Seek notice: {ex}")

    # =========================================================================
    # OFFLINE DOWNLOAD HANDLING
    # =========================================================================

    def _on_download_offline_click(self, e=None):
        if is_lesson_audio_cached(self.lesson_id, self.current_lang, self.target_page):
            self._show_snackbar("This audio lesson is already saved for offline study.")
            return
        if self.is_offline_mode:
            self._show_snackbar("Connect to internet to download this lesson audio.")
            return
        if hasattr(self.target_page, "run_task"):
            self.target_page.run_task(self._download_audio_for_offline)

    async def _download_audio_for_offline(self):
        self.offline_action_btn.disabled = True
        try:
            self.target_page.update()
        except Exception:
            pass
        self._show_snackbar(f"Downloading {self.current_lang.upper()} audio for offline study...")

        try:
            app_dir = getattr(self.target_page, "storage_paths", None)
            base_path = await app_dir.get_application_support_directory() if app_dir else os.path.join(os.getcwd(), "app_data")
            audio_dir = os.path.join(base_path, "courses", self.course_id, "audio")
            os.makedirs(audio_dir, exist_ok=True)
            local_filename = f"lesson_{self.lesson_id}_{self.current_lang}.mp3"
            local_filepath = os.path.join(audio_dir, local_filename)

            token = await self._get_auth_token_async()
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            url = f"{self.api_base_url}/courses/lessons/{self.lesson_id}/narrate/stream?lang={self.current_lang}"
            if token:
                url += f"&token={token}"

            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    download_bytes = res.content
                    with open(local_filepath, "wb") as f:
                        f.write(download_bytes)

                    save_offline_lesson_audio(
                        lesson_id=self.lesson_id,
                        course_id=self.course_id,
                        language=self.current_lang,
                        local_path=local_filepath,
                        remote_url=url,
                        size_bytes=len(download_bytes),
                        page=self.target_page,
                    )

                    self._show_snackbar("✓ Lesson audio saved offline! Ready for zero-data study.")
                    self.offline_action_btn.icon = ft.Icons.OFFLINE_PIN_ROUNDED
                    self.offline_action_btn.icon_color = ft.Colors.GREEN_600
                else:
                    self._show_snackbar("Could not download audio. Please retry in a moment.")

        except Exception as ex:
            logger.error(f"Download failed: {ex}")
            self._show_snackbar(f"Download error: {str(ex)[:40]}")
        finally:
            self.offline_action_btn.disabled = False
            try:
                self.target_page.update()
            except Exception:
                pass

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _start_waveform_animation(self):
        async def _animate():
            heights = [6, 12, 18, 10]
            step = 0
            while self.is_playing and not self.is_disposed:
                step = (step + 1) % 4
                for i, bar in enumerate(self.wave_bars):
                    bar.height = heights[(step + i) % len(heights)]
                try:
                    self.target_page.update()
                except Exception:
                    break
                await asyncio.sleep(0.18)
            for bar in self.wave_bars:
                bar.height = 6
            try:
                self.target_page.update()
            except Exception:
                pass

        if hasattr(self.target_page, "run_task"):
            self.target_page.run_task(_animate)

    def _stop_waveform_animation(self):
        for bar in self.wave_bars:
            bar.height = 6
        try:
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
