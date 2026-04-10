"""
file_ops skill — sandboxed read/write/list for local files.

All paths are resolved relative to the workspace/ directory that sits
next to this project's root.  Any attempt to escape the sandbox via
path traversal (../../etc/passwd) is blocked.
"""

import os

# All file ops are confined to this directory
_WORKSPACE = os.path.join(
    os.path.dirname(__file__),  # skills/file_ops/
    "..",                        # skills/
    "..",                        # project root
    "workspace",
)
_WORKSPACE = os.path.realpath(_WORKSPACE)

MAX_READ_BYTES = 50_000  # 50 KB — keeps large files out of the LLM context

tools = [
    {
        "name": "read_file",
        "description": (
            "Read the text contents of a file in the workspace folder. "
            "Returns the file contents as a string."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename inside workspace/ (e.g. 'notes.txt'). No slashes.",
                },
            },
            "required": ["filename"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write or append text to a file in the workspace folder. "
            "Use mode='append' to add to an existing file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename inside workspace/ (e.g. 'notes.txt').",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["write", "append"],
                    "description": "'write' overwrites the file; 'append' adds to it. Default: 'write'.",
                },
            },
            "required": ["filename", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List all files currently in the workspace folder.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "delete_file",
        "description": "Permanently delete a file from the workspace folder.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename inside workspace/ to delete.",
                },
            },
            "required": ["filename"],
        },
    },
]


def _safe_path(filename: str) -> str:
    """
    Resolve *filename* inside the workspace and raise if it tries to
    escape via path traversal.
    """
    # Strip any leading slashes/dots to block obvious traversal
    basename = os.path.basename(filename)
    if not basename or basename.startswith("."):
        raise ValueError(f"Invalid filename: {filename!r}")
    full = os.path.realpath(os.path.join(_WORKSPACE, basename))
    if not full.startswith(_WORKSPACE):
        raise ValueError("Path traversal attempt blocked.")
    return full


async def execute(tool_name: str, tool_input: dict, context: dict):
    os.makedirs(_WORKSPACE, exist_ok=True)

    try:
        if tool_name == "read_file":
            path = _safe_path(tool_input["filename"])
            if not os.path.exists(path):
                return {"found": False, "filename": tool_input["filename"]}
            size = os.path.getsize(path)
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read(MAX_READ_BYTES)
            truncated = size > MAX_READ_BYTES
            return {
                "filename":  tool_input["filename"],
                "content":   content,
                "size_bytes": size,
                "truncated": truncated,
            }

        if tool_name == "write_file":
            path    = _safe_path(tool_input["filename"])
            content = tool_input["content"]
            mode    = "a" if tool_input.get("mode") == "append" else "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            return {
                "written":   True,
                "filename":  tool_input["filename"],
                "mode":      "append" if mode == "a" else "write",
                "chars":     len(content),
            }

        if tool_name == "list_files":
            entries = []
            for name in sorted(os.listdir(_WORKSPACE)):
                full = os.path.join(_WORKSPACE, name)
                if os.path.isfile(full):
                    entries.append({
                        "filename":   name,
                        "size_bytes": os.path.getsize(full),
                    })
            return {"files": entries, "count": len(entries)}

        if tool_name == "delete_file":
            path = _safe_path(tool_input["filename"])
            if not os.path.exists(path):
                return {"deleted": False, "filename": tool_input["filename"]}
            os.remove(path)
            return {"deleted": True, "filename": tool_input["filename"]}

        return {"error": f"Unknown tool: {tool_name}"}

    except ValueError as exc:
        return {"error": str(exc)}
    except OSError as exc:
        return {"error": f"File system error: {exc}"}
