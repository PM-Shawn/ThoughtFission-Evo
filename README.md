# ThoughtFission Evo

[中文文档](README_CN.md)

**Self-evolving multi-agent deep research engine.** Ask a question, AI assembles a professional team, researches in parallel, self-corrects, and delivers a deep analysis report.

Built on [AgentX](https://github.com/anthropics/agentx) framework.

## How It Works

```
User Question
     |
Supervisor designs expert team (3-5 agents)
     |
Round 1: Experts research in parallel (web search + analysis)
     |
Supervisor evaluates: sufficient?
     |-- NO --> spawn new experts / redirect / drop --> Round 2...
     |-- YES --> Synthesis report
     |
Deep Analysis Report (executive summary + expert chapters + sources)
```

**Key difference from ChatGPT / Perplexity:**
- Not one model answering once -- multiple agents collaborating, supplementing, self-correcting
- Full process visualization (knowledge graph on canvas)
- Transparent decision log (why Round 2 happened, what was added)

## Features

| Feature | Description |
|---------|-------------|
| Dynamic Role Generation | No predefined roles. Supervisor designs expert team based on question domain, using appropriate professional methodologies |
| Self-evolving Loop | Supervisor judges results, can spawn/redirect/drop agents. Up to 4 rounds of iterative refinement |
| Knowledge Graph | Canvas visualization: Expert nodes -> Insight nodes -> Source nodes, growing in real-time |
| Deep Report | Executive summary (Supervisor) + detailed chapters (each expert, 500-1000 words with data and citations) |
| Research Log | Click "Round X/Y" to see full decision history: why new round started, what experts were added |
| Live Status Feed | Real-time activity: "Expert A searching...", "Expert B found 7 sources", "Supervisor evaluating..." |
| Scenario Hints | Quick presets (General / Hot Events / People / Stocks / Gossip) to guide Supervisor's team design |
| 4-layer Retry | Tools -> no tools -> JSON hint -> raw text fallback. Never loses an agent's work |

## Screenshots

*Coming soon*

## Quick Start

### Prerequisites

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- An API key for any OpenAI-compatible service (OpenRouter recommended for free models)

### Install

```bash
git clone https://github.com/YOUR_USERNAME/ThoughtFission-Evo.git
cd ThoughtFission-Evo
uv sync
```

### Run

```bash
uv run python main.py
```

Open http://localhost:8299 in your browser.

### Configure

Click the gear icon in the top-right corner:

1. **API Key**: Your OpenRouter API key (get one free at [openrouter.ai](https://openrouter.ai))
2. **Model**: Default is `stepfun/step-3.5-flash:free` (free). For better results, try `anthropic/claude-sonnet-4` or `openai/gpt-4o`
3. **Search Engine** (optional): Tavily / Bing / DuckDuckGo for web search capability

### Environment Variables (optional)

```bash
export OPENROUTER_API_KEY="sk-or-..."
export OPENROUTER_MODEL="stepfun/step-3.5-flash:free"
export THOUGHTFISSION_PORT=8299
```

## Usage Guide

### Basic Flow

1. (Optional) Select a scenario hint at the bottom: General / Hot Events / People / Stocks / Gossip
2. Type your question in the input box
3. Watch the canvas as agents appear and research in parallel
4. Click any agent node to see its findings, methodology, and sources
5. Click "Round X/Y" indicator to see the research decision log
6. When complete, the report panel appears on the right with the full analysis

### Example Questions

```
TikTok faces a US ban. What are ByteDance's options? How will this end?

Analyze whether Nvidia stock is overvalued at current levels.

Who is Jensen Huang? Map his career, relationships, and key decisions.

A company's marketing keeps going viral for controversial ads.
Is this strategy sustainable? What are the risks?
```

### Node Interactions

- **Left-click** an agent node: View detailed findings card
- **Right-click** an agent node: Context menu with:
  - **Deep Drill**: Re-fission this agent's finding into 2-3 sub-agents for deeper investigation
  - **Redirect**: Give this agent a new research direction
  - **Dismiss**: Remove this agent from the analysis
- **Drag** nodes to rearrange the canvas layout

### Understanding the Canvas

| Node Type | Appearance | Meaning |
|-----------|------------|---------|
| Supervisor (large purple) | Center node with glow | Main analyst coordinating the team |
| Expert (colored circle) | Surrounding the supervisor | Domain expert conducting research |
| Insight (small dot) | Connected to expert | A key finding/argument from the expert |
| Source (tiny dot) | Connected to insight | A web source supporting the argument |
| Synthesis (white) | Appears at the end | Final report node |

### Understanding the Report

The report follows a **Summary + Detail** structure:

- **Executive Summary**: Supervisor's overall judgment (the "so what")
- **Risk Assessment**: Key risks identified across all dimensions
- **Actionable Insights**: Concrete next steps
- **Expert Chapters**: Each expert's detailed analysis (500-1000 words each)
- **Sources**: All web sources collected during research

## Server Deployment

### Quick Deploy

```bash
# On your server
git clone https://github.com/YOUR_USERNAME/ThoughtFission-Evo.git
cd ThoughtFission-Evo

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Install dependencies
uv sync

# Run in background
nohup uv run python main.py > /var/log/thoughtfission.log 2>&1 &
```

### Systemd Service (Recommended)

```bash
cat > /etc/systemd/system/thoughtfission.service << 'EOF'
[Unit]
Description=ThoughtFission Evo Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/ThoughtFission-Evo
ExecStart=/root/.local/bin/uv run python main.py
Restart=always
RestartSec=5
Environment=PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable thoughtfission
systemctl start thoughtfission
```

### Firewall

```bash
# Open port 8299
firewall-cmd --permanent --add-port=8299/tcp && firewall-cmd --reload  # CentOS
ufw allow 8299  # Ubuntu
```

Also open port 8299 in your cloud provider's security group.

## Architecture

```
ThoughtFission-Evo/
├── main.py              # FastAPI server (API endpoints + SSE streaming)
├── config.py            # Environment config (model, API keys, port)
├── engine/
│   ├── agents.py        # Agent factories + Pydantic models (Finding, FissionPlan, etc.)
│   ├── thinker.py       # Core pipeline: think() -> _run_experts() -> synthesis
│   ├── session.py       # Session state management
│   └── sse_hooks.py     # RunHooks -> SSE event bridge
├── skills/
│   ├── web_search.py    # @tool: Tavily / Bing / DuckDuckGo search
│   └── analyze.py       # @tool: deep_analyze (analysis helper)
└── web/
    └── index.html       # Single-page Canvas visualization app
```

### AgentX APIs Used

| API | Purpose |
|-----|---------|
| `Agent(name, instructions, model, output_type, tools, hooks)` | Create all agent roles |
| `Runner.run(agent, prompt)` | Execute agents, get `parsed_output` |
| `output_type=PydanticModel` | Structured output validation (6 models) |
| `@tool` | Web search and analysis tools |
| `RunHooks` | Real-time SSE event streaming |
| `OpenAIProvider` | Model backend (OpenRouter compatible) |

### SSE Events

| Event | When |
|-------|------|
| `phase` | Pipeline stage changes (planning/exploring/judging/synthesizing) |
| `fission` | Supervisor creates expert team |
| `agent_finding` | Expert completes research |
| `judgment` | Supervisor evaluates results |
| `agent_spawn` | New expert added in later round |
| `agent_redirect` | Expert redirected to new direction |
| `agent_dropped` | Expert removed |
| `synthesis` | Final report ready |

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, uvicorn
- **Agent Framework**: [AgentX](https://github.com/anthropics/agentx) (model-agnostic, structured output, tool use, hooks)
- **Frontend**: Vanilla JavaScript + HTML5 Canvas (zero dependencies)
- **Streaming**: Server-Sent Events (SSE)
- **Model**: Any OpenAI-compatible API (OpenRouter, OpenAI, Anthropic, local Ollama)

## License

MIT
