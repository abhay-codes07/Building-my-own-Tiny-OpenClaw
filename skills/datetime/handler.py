"""
datetime skill — returns the current UTC date and time.
"""

from datetime import datetime, timezone

tools = [
    {
        "name": "get_current_time",
        "description": "Get the current date and time in UTC.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }
]


async def execute(tool_name: str, tool_input: dict, context: dict):
    if tool_name == "get_current_time":
        now = datetime.now(timezone.utc)
        return {
            "iso":      now.isoformat(),
            "readable": now.strftime("%A, %B %d, %Y %I:%M:%S %p UTC"),
            "unix":     int(now.timestamp()),
        }
    return {"error": f"Unknown tool: {tool_name}"}
