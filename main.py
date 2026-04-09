"""
main.py — entry point for Tiny-OpenClaw.

Wires together all components and starts the Telegram bot.
"""

import asyncio
import os

from dotenv import load_dotenv

from agent_runtime import AgentRuntime
from logger import get_logger
from memory import Memory
from session_manager import SessionManager
from skill_loader import SkillLoader
from telegram_channel import TelegramChannel

load_dotenv()

log = get_logger("main")


def _require(key: str) -> str:
    """Read an env var and raise a clear error if it's missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Check your .env file."
        )
    return value


async def main() -> None:
    log.info("=" * 50)
    log.info("  Tiny-OpenClaw starting up…")
    log.info("=" * 50)

    # ── Environment ──────────────────────────────────────────────────
    api_key       = _require("ANTHROPIC_API_KEY")
    model_name    = os.getenv("MODEL_NAME", "claude-opus-4-6")
    model_provider = os.getenv("MODEL_PROVIDER", "anthropic")
    bot_token     = _require("TELEGRAM_BOT_TOKEN")

    log.info("Model: %s / %s", model_provider, model_name)

    # ── Core components ──────────────────────────────────────────────
    memory   = Memory()
    sessions = SessionManager()

    # ── Skills ───────────────────────────────────────────────────────
    skills = SkillLoader()
    skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    skills.load_from_directory(skills_dir)

    loaded = skills.get_active_skills()
    log.info("Active skills: %s", [s["name"] for s in loaded])

    # ── Agent runtime ────────────────────────────────────────────────
    agent = AgentRuntime(
        provider = model_provider,
        model    = model_name,
        api_key  = api_key,
        skills   = skills,
        memory   = memory,
    )

    # ── Telegram channel ─────────────────────────────────────────────
    telegram = TelegramChannel(
        token    = bot_token,
        agent    = agent,
        sessions = sessions,
    )

    log.info("Tiny-OpenClaw is live on Telegram — Go CLAW! 🦞")
    await telegram.start()


if __name__ == "__main__":
    asyncio.run(main())
