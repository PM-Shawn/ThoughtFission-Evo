"""ThoughtFission — FastAPI server.

Endpoints:
    GET  /              → Serve the web UI
    POST /api/think     → Start a fission thinking session
    GET  /api/think/stream?session_id=xxx → SSE event stream
    POST /api/intervene → User intervention (deep_drill / dismiss / redirect)
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from agentx.providers.openai import OpenAIProvider
from config import HOST, PORT
from engine.session import SessionState
from engine.sse_hooks import SSEBridge
from engine.thinker import deep_drill, think
from skills.web_search import configure_search

app = FastAPI(title="ThoughtFission", version="0.1.0")

# Active sessions: session_id -> (SSEBridge, SessionState)
sessions: dict[str, tuple[SSEBridge, SessionState]] = {}

WEB_DIR = Path(__file__).parent / "web"


class ThinkRequest(BaseModel):
    question: str = Field(description="用户的问题")
    scenario_hint: str = Field(default="", description="场景提示，如'股票分析'")
    max_rounds: int = Field(default=4, description="最大调研轮次", ge=1, le=8)
    api_key: str = Field(default="", description="API Key")
    base_url: str = Field(default="https://openrouter.ai/api/v1", description="API Base URL")
    model: str = Field(default="stepfun/step-3.5-flash:free", description="模型名称")
    search_provider: str = Field(default="", description="搜索引擎: tavily/bing/duckduckgo")
    search_api_key: str = Field(default="", description="搜索 API Key")


class InterveneRequest(BaseModel):
    session_id: str = Field(description="会话ID")
    agent_id: str = Field(description="目标Agent ID")
    action: str = Field(description="操作: deep_drill / dismiss / redirect")
    prompt: str = Field(default="", description="自定义提示（redirect时使用）")
    api_key: str = Field(default="", description="API Key")
    base_url: str = Field(default="https://openrouter.ai/api/v1", description="API Base URL")
    model: str = Field(default="stepfun/step-3.5-flash:free", description="模型名称")
    search_provider: str = Field(default="", description="搜索引擎")
    search_api_key: str = Field(default="", description="搜索 API Key")


@app.get("/")
async def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/web/{path:path}")
async def static_files(path: str):
    file = WEB_DIR / path
    if file.exists() and file.is_file():
        return FileResponse(file)
    return HTMLResponse("Not found", status_code=404)


@app.post("/api/think")
async def start_think(req: ThinkRequest):
    if not req.api_key:
        return HTMLResponse(
            '{"error": "请先在设置中填写 API Key"}',
            status_code=400,
            media_type="application/json",
        )

    provider = OpenAIProvider(model=req.model, api_key=req.api_key, base_url=req.base_url)
    configure_search(req.search_provider, req.search_api_key)

    session_id = str(uuid.uuid4())[:8]
    bridge = SSEBridge()
    state = SessionState(session_id=session_id, question=req.question, model=provider)
    sessions[session_id] = (bridge, state)

    asyncio.create_task(_run_and_cleanup(
        session_id, req.question, bridge, req.scenario_hint, req.max_rounds, provider, state,
    ))

    return {"session_id": session_id}


async def _run_and_cleanup(session_id, question, bridge, scenario_hint, max_rounds, model, state):
    try:
        await think(
            question, bridge,
            scenario_hint=scenario_hint, model=model,
            session=state, max_rounds=max_rounds,
        )
    finally:
        # Keep session alive for interventions (clean up after 5 minutes)
        await asyncio.sleep(300)
        sessions.pop(session_id, None)


@app.post("/api/intervene")
async def intervene(req: InterveneRequest):
    entry = sessions.get(req.session_id)
    if not entry:
        return HTMLResponse(
            '{"error": "会话已过期或不存在"}',
            status_code=404,
            media_type="application/json",
        )

    bridge, state = entry

    if req.action == "dismiss":
        state.dismiss(req.agent_id)
        await bridge.push("agent_dismissed", {"agent_id": req.agent_id})
        return {"ok": True, "action": "dismiss", "agent_id": req.agent_id}

    elif req.action in ("deep_drill", "redirect"):
        # Update session model if client provided credentials
        if req.api_key:
            state.model = OpenAIProvider(model=req.model, api_key=req.api_key, base_url=req.base_url)
            configure_search(req.search_provider, req.search_api_key)

        drill_bridge = SSEBridge()
        drill_session_id = f"{req.session_id}_drill_{str(uuid.uuid4())[:4]}"
        sessions[drill_session_id] = (drill_bridge, state)

        custom_prompt = req.prompt if req.action == "redirect" else None

        asyncio.create_task(_run_drill_and_cleanup(
            drill_session_id, state, req.agent_id, drill_bridge, custom_prompt
        ))

        return {"ok": True, "action": req.action, "drill_session_id": drill_session_id}

    else:
        return HTMLResponse(
            f'{{"error": "未知操作: {req.action}"}}',
            status_code=400,
            media_type="application/json",
        )


async def _run_drill_and_cleanup(drill_session_id, state, agent_id, bridge, custom_prompt):
    try:
        await deep_drill(state, agent_id, bridge, custom_prompt=custom_prompt)
    finally:
        await asyncio.sleep(300)
        sessions.pop(drill_session_id, None)


@app.get("/api/think/stream")
async def stream_think(session_id: str):
    entry = sessions.get(session_id)
    if not entry:
        return HTMLResponse("Session not found", status_code=404)

    bridge, _ = entry

    return StreamingResponse(
        bridge.iter_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
