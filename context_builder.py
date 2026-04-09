"""
context_builder.py — assembles the system prompt sent to the LLM on
every turn.

The prompt is built from four layers:
  1. SOUL.md  — agent personality and rules
  2. Active skills — names + descriptions (so the LLM knows what tools exist)
  3. User memory notes — facts saved by the memory_work skill
  4. Current UTC timestamp — so the LLM always knows the real time
"""

import os
from datetime import datetime, timezone

from logger import get_logger

log = get_logger(__name__)

_FALLBACK_SOUL = """You are Tiny-OpenClaw, a personal AI assistant.
Be concise, friendly, and helpful. Use tools when they would help."""


def _load_soul() -> str:
    soul_path = os.path.join(os.path.dirname(__file__), "SOUL.md")
    try:
        with open(soul_path, encoding="utf-8") as f:
            content = f.read()
        log.debug("SOUL.md loaded (%d chars)", len(content))
        return content
    except FileNotFoundError:
        log.warning("SOUL.md not found — using fallback prompt")
        return _FALLBACK_SOUL


def build_system_prompt(active_skills: list[dict], memory=None) -> str:
    """
    Combine SOUL, skills, user memory, and current time into one
    system prompt string.

    Parameters
    ----------
    active_skills : list of {"name": str, "description": str}
    memory        : Memory instance (optional)
    """
    sections: list[str] = [_load_soul()]

    # ── Skills ──────────────────────────────────────────────────────────
    if active_skills:
        lines = ["\n\n## Available Skills"]
        for skill in active_skills:
            lines.append(f"### {skill['name']}")
            lines.append(f"{skill['description']}\n")
        sections.append("\n".join(lines))

    # ── User memory ─────────────────────────────────────────────────────
    if memory:
        prefix = "note:"
        notes = {
            k[len(prefix):]: memory.get(k)
            for k in memory.keys()
            if k.startswith(prefix)
        }
        if notes:
            lines = ["\n\n## What you know about the user"]
            for key, value in notes.items():
                content = (
                    value.get("content", value)
                    if isinstance(value, dict)
                    else value
                )
                lines.append(f"- {key}: {content}")
            sections.append("\n".join(lines))
            log.debug("Injected %d memory note(s) into prompt", len(notes))

    # ── Current time ────────────────────────────────────────────────────
    now_iso = datetime.now(timezone.utc).isoformat()
    sections.append(f"\nCurrent UTC time: {now_iso}")

    prompt = "".join(sections)
    log.debug("System prompt built (%d chars)", len(prompt))
    return prompt
