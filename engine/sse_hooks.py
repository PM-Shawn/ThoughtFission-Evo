"""RunHooks → SSE event bridge.

Converts AgentX RunHooks callbacks into SSE-compatible events
pushed to an asyncio.Queue for streaming to the browser.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SSEEvent:
    event: str
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def encode(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"


class SSEBridge:
    """Bridges AgentX RunHooks to SSE events via an asyncio.Queue."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
        self._agent_tasks: dict[str, str] = {}  # agent_name -> task description

    def register_agent(self, agent_name: str, task: str, faction: str = "") -> None:
        self._agent_tasks[agent_name] = task

    async def push(self, event: str, data: dict[str, Any]) -> None:
        await self.queue.put(SSEEvent(event=event, data=data))

    async def done(self) -> None:
        await self.queue.put(None)

    async def iter_events(self):
        """Async iterator that yields SSE-encoded strings."""
        while True:
            evt = await self.queue.get()
            if evt is None:
                break
            yield evt.encode()

    # -- Hook callbacks (passed to RunHooks) --

    async def on_model_start(self, ctx) -> None:
        await self.push("agent_thinking", {
            "agent_id": ctx.agent_name,
            "status": "thinking",
        })

    async def on_model_end(self, ctx, usage) -> None:
        await self.push("agent_model_done", {
            "agent_id": ctx.agent_name,
            "tokens": usage.input_tokens + usage.output_tokens,
        })

    async def on_tool_start(self, ctx, tool_name: str, args: dict) -> None:
        safe_args = {k: str(v)[:200] for k, v in args.items()}
        await self.push("tool_call", {
            "agent_id": ctx.agent_name,
            "tool": tool_name,
            "args": safe_args,
        })

    async def on_tool_end(self, ctx, tool_name: str, result) -> None:
        output = str(result.content) if hasattr(result, "content") else str(result)
        # Extract markdown links [title](url) as structured sources
        import re
        sources = []
        for m in re.finditer(r'\[([^\]]+)\]\((https?://[^)]+)\)', output):
            sources.append({"title": m.group(1), "url": m.group(2)})
        await self.push("tool_result", {
            "agent_id": ctx.agent_name,
            "tool": tool_name,
            "result_summary": output[:500],
            "sources": sources,
        })

    def build_hooks(self):
        """Create a RunHooks dataclass wired to this bridge."""
        from agentx.loop.hooks import RunHooks
        return RunHooks(
            on_model_start=self.on_model_start,
            on_model_end=self.on_model_end,
            on_tool_start=self.on_tool_start,
            on_tool_end=self.on_tool_end,
        )
