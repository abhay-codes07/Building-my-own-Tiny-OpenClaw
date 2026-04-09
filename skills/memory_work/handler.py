"""
memory_work skill — save, recall, list, and delete user notes.
"""

tools = [
    {
        "name": "save_note",
        "description": "Save a note or fact about the user to persistent memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Short descriptive key (e.g. 'name', 'city', 'hobby')",
                },
                "content": {
                    "type": "string",
                    "description": "The value or fact to store.",
                },
            },
            "required": ["key", "content"],
        },
    },
    {
        "name": "get_note",
        "description": "Retrieve a specific note from memory by key.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The key of the note to retrieve.",
                },
            },
            "required": ["key"],
        },
    },
    {
        "name": "list_notes",
        "description": "List all note keys currently stored in memory.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "delete_note",
        "description": "Delete a note from memory by key.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The key of the note to delete.",
                },
            },
            "required": ["key"],
        },
    },
]


async def execute(tool_name: str, tool_input: dict, context: dict):
    memory = context["memory"]

    if tool_name == "save_note":
        key = f"note:{tool_input['key']}"
        memory.set(key, {"content": tool_input["content"]})
        return {"success": True, "key": tool_input["key"]}

    if tool_name == "get_note":
        key = f"note:{tool_input['key']}"
        value = memory.get(key)
        if value is None:
            return {"found": False, "key": tool_input["key"]}
        content = value.get("content", value) if isinstance(value, dict) else value
        return {"found": True, "key": tool_input["key"], "content": content}

    if tool_name == "list_notes":
        prefix = "note:"
        keys = [k[len(prefix):] for k in memory.keys() if k.startswith(prefix)]
        return {"notes": keys, "count": len(keys)}

    if tool_name == "delete_note":
        key = f"note:{tool_input['key']}"
        deleted = memory.delete(key)
        return {"deleted": deleted, "key": tool_input["key"]}

    return {"error": f"Unknown tool: {tool_name}"}
