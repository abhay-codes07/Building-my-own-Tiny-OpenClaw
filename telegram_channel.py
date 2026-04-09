"""
telegram_channel.py — Telegram adapter for Tiny-OpenClaw.

Translates between the Telegram Bot API and the agent runtime.
Each Telegram chat gets its own session; replies are split at
Telegram's 4096-character limit.

Special commands
----------------
/start  — greet the user
/reset  — wipe this chat's conversation history
/info   — show session info (message count, creation time)
"""

import time

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from logger import get_logger

log = get_logger(__name__)

TELEGRAM_MAX_CHARS = 4096


class TelegramChannel:
    """Bridges Telegram messages to the agent runtime."""

    def __init__(self, token: str, agent, sessions):
        self.token    = token
        self.agent    = agent
        self.sessions = sessions

    async def start(self) -> None:
        """Build the Telegram app and begin polling."""
        app = (
            Application.builder()
            .token(self.token)
            .build()
        )

        # Register handlers
        app.add_handler(CommandHandler("start", self._on_start))
        app.add_handler(CommandHandler("reset", self._on_reset))
        app.add_handler(CommandHandler("info",  self._on_info))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))

        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        log.info("Telegram polling started — waiting for messages…")

        # Block forever until the process is killed
        import asyncio
        await asyncio.Future()

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    async def _on_start(self, update: Update, _context) -> None:
        chat_id = str(update.effective_chat.id)
        self.sessions.get_or_create_session(chat_id, "telegram")
        await update.message.reply_text(
            "Hey! I'm Tiny-OpenClaw 🦞\n"
            "I can browse the web, remember things, do maths, and more.\n"
            "Just chat with me — or use /reset to start fresh."
        )

    async def _on_reset(self, update: Update, _context) -> None:
        chat_id = str(update.effective_chat.id)
        session_id = self.sessions.get_or_create_session(chat_id, "telegram")
        self.sessions.clear_history(session_id)
        await update.message.reply_text("Done — conversation history wiped. Fresh start! 🧹")

    async def _on_info(self, update: Update, _context) -> None:
        chat_id = str(update.effective_chat.id)
        session_id = self.sessions.get_or_create_session(chat_id, "telegram")
        info = self.sessions.session_info(session_id)
        if info:
            created = time.strftime(
                "%Y-%m-%d %H:%M UTC", time.gmtime(info["created_at"])
            )
            await update.message.reply_text(
                f"Session ID: `{session_id}`\n"
                f"Messages: {info['message_count']}\n"
                f"Created: {created}",
                parse_mode="Markdown",
            )

    # ------------------------------------------------------------------
    # Message handler
    # ------------------------------------------------------------------

    async def _on_message(self, update: Update, _context) -> None:
        chat_id   = str(update.effective_chat.id)
        user_text = update.message.text

        if not user_text:
            return

        session_id = self.sessions.get_or_create_session(chat_id, "telegram")

        # Persist user message
        self.sessions.add_message(session_id, {
            "role":      "user",
            "content":   user_text,
            "timestamp": time.time(),
        })

        # Show typing indicator
        await update.effective_chat.send_action("typing")

        try:
            history = self.sessions.get_history(session_id)
            full_response = ""

            async def on_token(text: str) -> None:
                nonlocal full_response
                full_response += text

            async def on_tool_use(name: str, _input: dict) -> None:
                log.debug("Tool in use: %s", name)
                await update.effective_chat.send_action("typing")

            await self.agent.run(history, session_id, {
                "on_token":    on_token,
                "on_tool_use": on_tool_use,
            })

            # Send reply (split if over Telegram's limit)
            if full_response:
                for i in range(0, len(full_response), TELEGRAM_MAX_CHARS):
                    await update.message.reply_text(full_response[i:i + TELEGRAM_MAX_CHARS])
            else:
                await update.message.reply_text("Sorry, I couldn't come up with a response.")

            # Persist assistant reply
            if full_response:
                self.sessions.add_message(session_id, {
                    "role":      "assistant",
                    "content":   full_response,
                    "timestamp": time.time(),
                })

        except Exception as exc:  # noqa: BLE001
            log.exception("Error handling message from %s", chat_id)
            await update.message.reply_text(f"Something went wrong: {exc}")
