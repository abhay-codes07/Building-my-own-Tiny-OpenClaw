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

Responses are streamed via SSE so the Telegram channel can edit the
message in-place as tokens arrive instead of waiting for the full reply.
"""

import json

import httpx

from context_builder import build_system_prompt
from logger import get_logger

log = get_logger(__name__)

MAX_TOOL_ROUNDS = 5

ANTHROPIC_API_URL     = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class AgentRuntime:
    """Runs the ReAct agent loop for a single user turn."""

    def __init__(self, provider: str, model: str, api_key: str, skills, memory):
        self.provider = provider
        self.model    = model
        self.api_key  = api_key
        self.skills   = skills
        self.memory   = memory

    async def run(self, history: list[dict], session_id: str, callbacks: dict) -> str:
        """
        Execute one full agent turn.

        callbacks keys
        --------------
        on_chunk    : async fn(str)        — called with each streamed text chunk
        on_tool_use : async fn(name, input) — called before each tool execution
        """
        on_chunk    = callbacks.get("on_chunk")
        on_tool_use = callbacks.get("on_tool_use")

        system_prompt = build_system_prompt(
            self.skills.get_active_skills(), self.memory
        )

        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in history
        ]

        tools = self.skills.get_tools()
        response_text = ""
        rounds = 0

        log.info("Agent run started — session=%s  history=%d msgs", session_id, len(messages))

        while rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            log.debug("ReAct round %d/%d", rounds, MAX_TOOL_ROUNDS)

            result = await self._stream_anthropic(
                system_prompt, messages, tools or None, on_chunk=on_chunk
            )

            if result["tool_calls"]:
                messages.append({"role": "assistant", "content": result["raw_content"]})

                tool_results = []
                for tc in result["tool_calls"]:
                    log.info("Tool call: %s  input=%s", tc["name"], tc["input"])
                    if on_tool_use:
                        await on_tool_use(tc["name"], tc["input"])

                    tool_result = await self.skills.execute_tool(
                        tc["name"],
                        tc["input"],
                        {
                            "session_id":   session_id,
                            "memory":       self.memory,
                            "send_message": callbacks.get("send_message"),
                        },
                    )
                    log.debug("Tool result for %s: %s", tc["name"], tool_result)

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tc["id"],
                        "content":     json.dumps(tool_result),
                    })

                messages.append({"role": "user", "content": tool_results})
                continue

            if result["text"]:
                response_text = result["text"]

            break

        if rounds >= MAX_TOOL_ROUNDS and not response_text:
            log.warning("Hit MAX_TOOL_ROUNDS (%d) without a final answer", MAX_TOOL_ROUNDS)
            fallback = "I got stuck in a loop and couldn't finish. Please try rephrasing."
            if on_chunk:
                await on_chunk(fallback)
            response_text = fallback

        log.info("Agent run complete — %d round(s)", rounds)
        return response_text

    # ------------------------------------------------------------------
    # Streaming Anthropic API call
    # ------------------------------------------------------------------

    async def _stream_anthropic(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict] | None,
        on_chunk=None,
    ) -> dict:
        """
        Call the Anthropic Messages API with streaming (SSE) enabled.

        Text deltas are forwarded to on_chunk() as they arrive so the
        caller can display tokens in real time.  Tool-use blocks are
        accumulated silently and returned in the same dict format as
        the old non-streaming _call_anthropic(), so the ReAct loop
        doesn't need to change.
        """
        body: dict = {
            "model":      self.model,
            "max_tokens": 4096,
            "system":     system_prompt,
            "messages":   messages,
            "stream":     True,
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

        # blocks[index] accumulates each content block as SSE events arrive
        blocks: dict[int, dict] = {}

        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         self.api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST", ANTHROPIC_API_URL, headers=headers, json=body
                ) as resp:
                    if resp.status_code != 200:
                        body_text = await resp.aread()
                        raise RuntimeError(
                            f"Anthropic API error {resp.status_code}: {body_text.decode()}"
                        )

                    async for raw_line in resp.aiter_lines():
                        if not raw_line.startswith("data: "):
                            continue
                        payload = raw_line[6:]
                        if payload.strip() == "[DONE]":
                            break

                        try:
                            event = json.loads(payload)
                        except json.JSONDecodeError:
                            continue

                        etype = event.get("type")

                        if etype == "content_block_start":
                            idx = event["index"]
                            cb  = event["content_block"]
                            if cb["type"] == "text":
                                blocks[idx] = {"type": "text", "text": ""}
                            elif cb["type"] == "tool_use":
                                blocks[idx] = {
                                    "type":       "tool_use",
                                    "id":         cb["id"],
                                    "name":       cb["name"],
                                    "input_json": "",
                                }

                        elif etype == "content_block_delta":
                            idx   = event["index"]
                            delta = event["delta"]
                            if delta["type"] == "text_delta":
                                chunk = delta["text"]
                                blocks[idx]["text"] += chunk
                                if on_chunk and chunk:
                                    await on_chunk(chunk)
                            elif delta["type"] == "input_json_delta":
                                blocks[idx]["input_json"] += delta.get("partial_json", "")

        except httpx.ConnectError as exc:
            raise RuntimeError(f"Cannot reach Anthropic API: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"Anthropic API timed out: {exc}") from exc

        # Reconstruct normalised result from accumulated blocks
        text_parts: list[str] = []
        tool_calls: list[dict] = []
        raw_content: list[dict] = []

        for idx in sorted(blocks):
            block = blocks[idx]
            if block["type"] == "text":
                text_parts.append(block["text"])
                raw_content.append({"type": "text", "text": block["text"]})
            elif block["type"] == "tool_use":
                try:
                    input_data = json.loads(block["input_json"]) if block["input_json"] else {}
                except json.JSONDecodeError:
                    input_data = {}
                tool_calls.append({
                    "id":    block["id"],
                    "name":  block["name"],
                    "input": input_data,
                })
                raw_content.append({
                    "type":  "tool_use",
                    "id":    block["id"],
                    "name":  block["name"],
                    "input": input_data,
                })

        return {
            "text":        "".join(text_parts),
            "tool_calls":  tool_calls or None,
            "raw_content": raw_content,
        }
