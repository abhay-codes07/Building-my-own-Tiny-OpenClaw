"""
agent_runtime.py — the ReAct (Reason + Act) loop.

On each user turn the runtime:
  1. Builds a system prompt (SOUL + skills + memory + time)
  2. Sends it to the Anthropic Messages API together with the
     conversation history and all tool schemas
  3. If the model requests a tool, executes it via SkillLoader and
     feeds the result back as a new user message
  4. Repeats until the model returns a plain text answer or the
     MAX_TOOL_ROUNDS cap is reached

Only the Anthropic API is wired up, but the provider/model fields are
kept in __init__ so swapping to OpenAI is a one-function change.
"""

import json

import httpx

from context_builder import build_system_prompt
from logger import get_logger

log = get_logger(__name__)

# Hard cap: prevents runaway tool loops
MAX_TOOL_ROUNDS = 5

# Anthropic API endpoint
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class AgentRuntime:
    """Runs the agent loop for a single user turn."""

    def __init__(self, provider: str, model: str, api_key: str, skills, memory):
        self.provider = provider
        self.model    = model
        self.api_key  = api_key
        self.skills   = skills
        self.memory   = memory

    async def run(self, history: list[dict], session_id: str, callbacks: dict) -> str:
        """
        Execute one full agent turn.

        Parameters
        ----------
        history    : full conversation history for this session
        session_id : used to pass session context to skills
        callbacks  : {
            "on_token":    async fn(text)   — called with the final response
            "on_tool_use": async fn(name, input) — called before each tool call
          }

        Returns the final text response.
        """
        on_token    = callbacks.get("on_token")
        on_tool_use = callbacks.get("on_tool_use")

        system_prompt = build_system_prompt(
            self.skills.get_active_skills(), self.memory
        )

        # Convert history entries to Anthropic message format
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in history
        ]

        tools = self.skills.get_tools()
        response_text = ""
        rounds = 0

        log.info("Agent run started — session=%s, history=%d msgs", session_id, len(messages))

        while rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            log.debug("ReAct round %d/%d", rounds, MAX_TOOL_ROUNDS)

            result = await self._call_anthropic(system_prompt, messages, tools or None)

            if result["tool_calls"]:
                # Append the assistant's tool-request message
                messages.append({"role": "assistant", "content": result["raw_content"]})

                # Execute every requested tool and collect results
                tool_results = []
                for tc in result["tool_calls"]:
                    log.info("Tool call: %s  input=%s", tc["name"], tc["input"])
                    if on_tool_use:
                        await on_tool_use(tc["name"], tc["input"])

                    tool_result = await self.skills.execute_tool(
                        tc["name"],
                        tc["input"],
                        {"session_id": session_id, "memory": self.memory},
                    )
                    log.debug("Tool result for %s: %s", tc["name"], tool_result)

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tc["id"],
                        "content":     json.dumps(tool_result),
                    })

                messages.append({"role": "user", "content": tool_results})
                continue  # next ReAct round

            # No tool calls — we have the final answer
            if result["text"]:
                response_text = result["text"]
                if on_token:
                    await on_token(response_text)

            break

        if rounds >= MAX_TOOL_ROUNDS and not response_text:
            log.warning("Hit MAX_TOOL_ROUNDS (%d) without a final answer", MAX_TOOL_ROUNDS)
            response_text = "I ran into a loop and couldn't complete the task. Please try rephrasing."
            if on_token:
                await on_token(response_text)

        log.info("Agent run complete — %d round(s)", rounds)
        return response_text

    # ------------------------------------------------------------------
    # Anthropic API
    # ------------------------------------------------------------------

    async def _call_anthropic(
        self, system_prompt: str, messages: list[dict], tools: list[dict] | None
    ) -> dict:
        """POST to the Anthropic Messages API and return a normalised result."""
        body: dict = {
            "model":      self.model,
            "max_tokens": 4096,
            "system":     system_prompt,
            "messages":   messages,
        }

        if tools:
            body["tools"] = [
                {
                    "name":         t["name"],
                    "description":  t["description"],
                    "input_schema": t["parameters"],
                }
                for t in tools
            ]

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                res = await client.post(
                    ANTHROPIC_API_URL,
                    headers={
                        "Content-Type":    "application/json",
                        "x-api-key":       self.api_key,
                        "anthropic-version": ANTHROPIC_API_VERSION,
                    },
                    json=body,
                )
        except httpx.ConnectError as exc:
            raise RuntimeError(f"Cannot reach Anthropic API: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"Anthropic API timed out: {exc}") from exc

        if res.status_code != 200:
            raise RuntimeError(
                f"Anthropic API error {res.status_code}: {res.text}"
            )

        data = res.json()
        text_parts: list[str] = []
        tool_calls: list[dict] = []

        for block in data.get("content", []):
            if block["type"] == "text":
                text_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append({
                    "id":    block["id"],
                    "name":  block["name"],
                    "input": block["input"],
                })

        return {
            "text":        "".join(text_parts),
            "tool_calls":  tool_calls or None,
            "raw_content": data["content"],
        }
