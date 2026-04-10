"""
telegram_channel.py — Telegram adapter for Tiny-OpenClaw.

Translates between the Telegram Bot API and the agent runtime.
Each Telegram chat gets its own session; replies stream in real-time
by editing a single message in-place as tokens arrive.

Special commands
----------------
/start  — greet the user
/reset  — wipe this chat's conversation history
/info   — show session info (message count, creation time)
"""

import asyncio
import base64
import time

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from logger import get_logger

log = get_logger(__name__)

TELEGRAM_MAX_CHARS   = 4096
STREAM_THROTTLE_CHARS = 60   # edit message after every N new chars
STREAM_THROTTLE_SECS  = 1.0  # but never more often than once per second


class _StreamEditor:
    """
    Edits a single Telegram message in-place as text chunks arrive.

    Throttling: edits fire when either STREAM_THROTTLE_CHARS new chars
    have accumulated OR STREAM_THROTTLE_SECS has elapsed — whichever
    comes first — to respect Telegram's ~20 edits/min/chat rate limit.
    """

    def __init__(self, update: Update):
        self._update     = update
        self._message    = None   # the Telegram Message object once sent
        self._text       = ""
        self._last_len   = 0
        self._last_time  = 0.0

    async def on_chunk(self, chunk: str) -> None:
        self._text += chunk

        if self._message is None:
            self._message  = await self._update.message.reply_text(self._text)
            self._last_len  = len(self._text)
            self._last_time = time.monotonic()
            return

        chars_since = len(self._text) - self._last_len
        secs_since  = time.monotonic() - self._last_time

        if chars_since >= STREAM_THROTTLE_CHARS or secs_since >= STREAM_THROTTLE_SECS:
            await self._edit()

    async def finalize(self) -> str:
        """Do a final edit with the complete text and return it."""
        if self._message:
            await self._edit()
        elif self._text:
            # on_chunk was never called (e.g. empty response)
            await self._update.message.reply_text(self._text or "…")
        return self._text

    async def _edit(self) -> None:
        if not self._message:
            return
        trimmed = self._text[:TELEGRAM_MAX_CHARS]
        if trimmed == (self._message.text or ""):
            return
        try:
            await self._message.edit_text(trimmed)
            self._last_len  = len(self._text)
            self._last_time = time.monotonic()
        except Exception:
            pass   # Telegram may reject identical text or rate-limit us


class TelegramChannel:
    """Bridges Telegram messages and photos to the agent runtime."""

    def __init__(self, token: str, agent, sessions):
        self.token    = token
        self.agent    = agent
        self.sessions = sessions

    async def start(self) -> None:
        app = Application.builder().token(self.token).build()

        app.add_handler(CommandHandler("start", self._on_start))
        app.add_handler(CommandHandler("reset", self._on_reset))
        app.add_handler(CommandHandler("info",  self._on_info))
        app.add_handler(MessageHandler(filters.PHOTO,                      self._on_photo))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,    self._on_message))

        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        log.info("Telegram polling started — waiting for messages…")
        await asyncio.Future()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def _on_start(self, update: Update, _ctx) -> None:
        chat_id = str(update.effective_chat.id)
        self.sessions.get_or_create_session(chat_id, "telegram")
        await update.message.reply_text(
            "Hey! I'm Tiny-OpenClaw 🦞\n"
            "I can browse the web, remember things, do maths, check weather,\n"
            "analyse photos, set reminders, and more.\n"
            "Chat with me — or use /reset to start fresh."
        )

    async def _on_reset(self, update: Update, _ctx) -> None:
        chat_id    = str(update.effective_chat.id)
        session_id = self.sessions.get_or_create_session(chat_id, "telegram")
        self.sessions.clear_history(session_id)
        await update.message.reply_text("Done — conversation history wiped. Fresh start! 🧹")

    async def _on_info(self, update: Update, _ctx) -> None:
        chat_id    = str(update.effective_chat.id)
        session_id = self.sessions.get_or_create_session(chat_id, "telegram")
        info = self.sessions.session_info(session_id)
        if info:
            created = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(info["created_at"]))
            await update.message.reply_text(
                f"Session ID: `{session_id}`\n"
                f"Messages: {info['message_count']}\n"
                f"Created: {created}",
                parse_mode="Markdown",
            )

    # ------------------------------------------------------------------
    # Photo handler — image understanding via Claude Vision
    # ------------------------------------------------------------------

    async def _on_photo(self, update: Update, ctx) -> None:
        chat_id    = str(update.effective_chat.id)
        session_id = self.sessions.get_or_create_session(chat_id, "telegram")
        caption    = update.message.caption or "What's in this image?"

        await update.effective_chat.send_action("typing")

        try:
            # Get highest-resolution photo variant
            photo_file = await ctx.bot.get_file(update.message.photo[-1].file_id)
            image_bytes = await photo_file.download_as_bytearray()
            image_b64   = base64.standard_b64encode(bytes(image_bytes)).decode()

            # Build a vision content block for the Anthropic API
            vision_content = [
                {
                    "type": "image",
                    "source": {
                        "type":       "base64",
                        "media_type": "image/jpeg",
                        "data":       image_b64,
                    },
                },
                {"type": "text", "text": caption},
            ]

            # Store vision message in history (content is a list, not a string)
            self.sessions.add_message(session_id, {
                "role":      "user",
                "content":   vision_content,
                "timestamp": time.time(),
            })

            await self._run_agent(update, ctx, session_id)

        except Exception as exc:
            log.exception("Error handling photo from %s", chat_id)
            await update.message.reply_text(f"Couldn't analyse the image: {exc}")

    # ------------------------------------------------------------------
    # Text message handler
    # ------------------------------------------------------------------

    async def _on_message(self, update: Update, ctx) -> None:
        chat_id   = str(update.effective_chat.id)
        user_text = update.message.text

        if not user_text:
            return

        session_id = self.sessions.get_or_create_session(chat_id, "telegram")

        self.sessions.add_message(session_id, {
            "role":      "user",
            "content":   user_text,
            "timestamp": time.time(),
        })

        await update.effective_chat.send_action("typing")
        await self._run_agent(update, ctx, session_id)

    # ------------------------------------------------------------------
    # Shared agent runner
    # ------------------------------------------------------------------

    async def _run_agent(self, update: Update, ctx, session_id: str) -> None:
        """Run the agent and stream the reply back to Telegram."""
        chat_id = str(update.effective_chat.id)

        async def send_message(text: str) -> None:
            """Callback used by skills (e.g. reminder) to push a message later."""
            try:
                await ctx.bot.send_message(chat_id=chat_id, text=text)
            except Exception as exc:
                log.warning("send_message callback failed: %s", exc)

        try:
            history = self.sessions.get_history(session_id)
            editor  = _StreamEditor(update)

            async def on_chunk(text: str) -> None:
                await editor.on_chunk(text)

            async def on_tool_use(name: str, _input: dict) -> None:
                log.debug("Tool in use: %s", name)
                await update.effective_chat.send_action("typing")

            await self.agent.run(history, session_id, {
                "on_chunk":    on_chunk,
                "on_tool_use": on_tool_use,
                "send_message": send_message,
            })

            full_response = await editor.finalize()

            if not full_response:
                await update.message.reply_text("Sorry, I couldn't come up with a response.")
                return

            # Persist assistant reply (store plain text for history)
            self.sessions.add_message(session_id, {
                "role":      "assistant",
                "content":   full_response[:TELEGRAM_MAX_CHARS],
                "timestamp": time.time(),
            })

        except Exception as exc:
            log.exception("Error in agent run for %s", chat_id)
            await update.message.reply_text(f"Something went wrong: {exc}")
