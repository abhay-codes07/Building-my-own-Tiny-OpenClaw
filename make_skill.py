#!/usr/bin/env python3
"""
make_skill.py — scaffold a new skill in seconds.

Usage:
    python make_skill.py <skill_name> "<one-line description>"

Example:
    python make_skill.py joke_teller "Tell a random joke on demand."

This creates:
    skills/joke_teller/SKILL.md
    skills/joke_teller/handler.py

Edit handler.py to add your tool logic, then restart main.py.
"""

import os
import sys
import textwrap

SKILL_MD_TEMPLATE = """\
---
name: {name}
description: {description}
---
"""

HANDLER_TEMPLATE = '''\
"""
{name} skill — {description}
"""

tools = [
    {{
        "name": "{tool_name}",
        "description": "{description}",
        "parameters": {{
            "type": "object",
            "properties": {{
                # TODO: add your tool parameters here
                # "my_param": {{
                #     "type": "string",
                #     "description": "What this parameter does.",
                # }},
            }},
            "required": [],
        }},
    }},
]


async def execute(tool_name: str, tool_input: dict, context: dict):
    memory = context["memory"]
    session_id = context["session_id"]

    if tool_name == "{tool_name}":
        # TODO: implement your tool logic here
        return {{"result": "not yet implemented"}}

    return {{"error": f"Unknown tool: {{tool_name}}"}}
'''


def slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    skill_name  = slugify(sys.argv[1])
    description = sys.argv[2].strip()
    tool_name   = skill_name  # default: same as skill name

    skill_dir = os.path.join(os.path.dirname(__file__), "skills", skill_name)

    if os.path.exists(skill_dir):
        print(f"Error: skill '{skill_name}' already exists at {skill_dir}")
        sys.exit(1)

    os.makedirs(skill_dir)

    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(SKILL_MD_TEMPLATE.format(name=skill_name, description=description))

    handler_path = os.path.join(skill_dir, "handler.py")
    with open(handler_path, "w", encoding="utf-8") as f:
        f.write(HANDLER_TEMPLATE.format(
            name=skill_name,
            description=description,
            tool_name=tool_name,
        ))

    print(f"Skill scaffolded:")
    print(f"  {skill_md_path}")
    print(f"  {handler_path}")
    print(f"\nEdit handler.py to implement your tool, then restart main.py.")


if __name__ == "__main__":
    main()
