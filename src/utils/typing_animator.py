"""
typing_animator.py
──────────────────────────────────────────────────────────────────────────────
High-performance asynchronous typing animation engine for Flet AI chatbots.
Provides silky-smooth, adaptive human-cadence streaming (with markdown-safe
cursor auto-balancing and physics-friendly throttled auto-scroll).
Resilient against dismounts, fast navigation, and control detachment.
──────────────────────────────────────────────────────────────────────────────
"""
import asyncio
import re
import time
from typing import Optional, Callable
import flet as ft


def _make_safe_markdown_cursor(text: str, cursor: str) -> str:
    """
    Auto-balances unclosed markdown delimiters (code fences, bold, italic, code spans)
    around the terminal cursor, preventing Flutter Markdown from flashing raw syntax
    or snapping abruptly between unparsed and styled tokens.
    """
    if not cursor:
        return text

    # Check for open triple backtick code fence
    fence_count = text.count("```")
    if fence_count % 2 == 1:
        return f"{text}\n{cursor}\n```"

    # Check for open inline code `
    non_fence = re.sub(r"```[\s\S]*?```", "", text)
    if non_fence.count("`") % 2 == 1:
        return f"{text}{cursor}`"

    # Check for open bold **
    if non_fence.count("**") % 2 == 1:
        return f"{text}{cursor}**"

    # Check for open italic * (excluding **)
    italic_sample = non_fence.replace("**", "")
    if italic_sample.count("*") % 2 == 1:
        return f"{text}{cursor}*"

    return f"{text}{cursor}"


async def stream_typing_animation(
    target_control: ft.Control,
    full_text: str,
    page: ft.Page,
    scroll_container: Optional[ft.Control] = None,
    words_per_chunk: int = 1,
    chunk_interval_ms: int = 16,
    show_cursor: bool = True,
    cursor_char: str = " ▍",
    on_complete: Optional[Callable[[], None]] = None,
) -> None:
    """
    Smoothly streams incoming text into `target_control` (ft.Markdown or ft.Text)
    using adaptive human-cadence pacing and non-breaking markdown cursor balancing.
    """
    if not full_text:
        return

    # Split into word and whitespace/punctuation tokens
    tokens = re.split(r"(\s+)", full_text)
    if len(tokens) <= 2:
        try:
            target_control.value = full_text
            page.update()
        except Exception:
            pass
        if on_complete:
            try:
                on_complete()
            except Exception:
                pass
        return

    # Calculate dynamic chunk step and base delay based on length
    total_tokens = len(tokens)
    if total_tokens > 500:
        step = 4  # ~2 words per chunk for very long text
        base_delay = 0.012
    elif total_tokens > 200:
        step = 2  # 1 word per chunk
        base_delay = 0.014
    else:
        step = 2  # 1 word per chunk for short/medium text
        base_delay = max(0.012, chunk_interval_ms / 1000.0)

    accumulated = []
    last_scroll_time = 0.0

    for i in range(0, total_tokens, step):
        batch = "".join(tokens[i : i + step])
        accumulated.append(batch)
        current_str = "".join(accumulated)

        try:
            is_mid_stream = (i + step < total_tokens)
            if show_cursor and is_mid_stream:
                target_control.value = _make_safe_markdown_cursor(current_str, cursor_char)
            else:
                target_control.value = current_str

            page.update()

            # Throttled auto-scrolling to prevent fighting Flutter's physics controller
            now = time.monotonic()
            if scroll_container and hasattr(scroll_container, "scroll_to"):
                if (now - last_scroll_time >= 0.14) or ("\n" in batch):
                    last_scroll_time = now
                    try:
                        await scroll_container.scroll_to(offset=-1, duration=0)
                    except Exception:
                        pass

        except Exception:
            # Control or page was unmounted / closed mid-stream, abort cleanly
            return

        # Adaptive human-cadence delay:
        # Micro-pause on commas, semicolons, and colons (+30ms)
        # Sentence-ending pause on periods, question marks, and exclamation marks (+65ms)
        # Paragraph break pause on double newlines (+90ms)
        extra_pause = 0.0
        if batch.endswith((",", ";", ":")):
            extra_pause = 0.030
        elif batch.endswith((".", "!", "?")):
            extra_pause = 0.065
        elif "\n\n" in batch:
            extra_pause = 0.090

        await asyncio.sleep(base_delay + extra_pause)

    # Final cleanup: set exact final text without cursor and ensure final pinned scroll
    try:
        target_control.value = full_text
        page.update()
        if scroll_container and hasattr(scroll_container, "scroll_to"):
            try:
                await scroll_container.scroll_to(offset=-1, duration=60)
            except Exception:
                pass
    except Exception:
        pass

    if on_complete:
        try:
            on_complete()
        except Exception:
            pass

