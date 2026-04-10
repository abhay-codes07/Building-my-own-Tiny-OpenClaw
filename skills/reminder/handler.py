"""
reminder skill — schedule async Telegram reminders.

Uses asyncio.create_task() to fire a message after a delay without
blocking the current agent turn.  Requires context["send_message"],
an async callable injected by telegram_channel.py.

Maximum delay is capped at 24 hours to prevent runaway tasks.
"""

import asyncio

MAX_DELAY_SECONDS = 86_400  # 24 hours

tools = [
    {
        "name": "set_reminder",
        "description": (
            "Schedule a reminder message to be sent to the user after a delay. "
            "Returns immediately — the message fires in the background. "
            "Use when the user says 'remind me in X minutes/hours to ...'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The reminder text to send to the user.",
                },
                "delay_seconds": {
                    "type": "integer",
                    "description": "How many seconds from now to send the reminder.",
                },
            },
            "required": ["message", "delay_seconds"],
        },
    },
    {
        "name": "cancel_reminders",
        "description": "Cancel all pending reminders for this session.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# Track pending tasks per session so we can cancel them
_pending: dict[str, list[asyncio.Task]] = {}


async def execute(tool_name: str, tool_input: dict, context: dict):
    session_id   = context.get("session_id", "default")
    send_message = context.get("send_message")

    if tool_name == "set_reminder":
        if not send_message:
            return {"error": "Reminders are not available outside the Telegram channel."}

        delay   = int(tool_input.get("delay_seconds", 0))
        message = tool_input.get("message", "").strip()

        if delay <= 0:
            return {"error": "delay_seconds must be a positive integer."}
        if delay > MAX_DELAY_SECONDS:
            return {"error": f"Maximum delay is {MAX_DELAY_SECONDS} seconds (24 hours)."}
        if not message:
            return {"error": "message must not be empty."}

        async def _fire():
            await asyncio.sleep(delay)
            await send_message(f"⏰ Reminder: {message}")
            # Clean up our reference once it fires
            tasks = _pending.get(session_id, [])
            task  = asyncio.current_task()
            if task in tasks:
                tasks.remove(task)

        task = asyncio.create_task(_fire())

        # Track the task so cancel_reminders can reach it
        _pending.setdefault(session_id, []).append(task)

        # Build a human-friendly time string
        h, remainder = divmod(delay, 3600)
        m, s         = divmod(remainder, 60)
        parts = []
        if h:
            parts.append(f"{h}h")
        if m:
            parts.append(f"{m}m")
        if s or not parts:
            parts.append(f"{s}s")
        time_str = " ".join(parts)

        return {
            "scheduled":  True,
            "fires_in":   time_str,
            "message":    message,
        }

    if tool_name == "cancel_reminders":
        tasks = _pending.pop(session_id, [])
        cancelled = 0
        for t in tasks:
            if not t.done():
                t.cancel()
                cancelled += 1
        return {"cancelled": cancelled}

    return {"error": f"Unknown tool: {tool_name}"}
