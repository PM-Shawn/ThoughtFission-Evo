# ThoughtFission Evo

**自进化多智能体深度调研引擎。** 提出一个问题，AI 自动组建专业团队、并行调研、自我修正，产出深度分析报告。

基于 [AgentX](https://github.com/anthropics/agentx) 框架构建。

## 工作原理

```
用户提问
   |
主分析师设计专家团队（3-5人，自动选择领域方法论）
   |
Round 1: 专家并行调研（搜索 + 分析）
   |
主分析师评判：结果充分吗？
   |-- 不够 --> 新增专家 / 重定向 / 移除 --> Round 2...
   |-- 够了 --> 汇报
   |
深度分析报告（总论 + 各专家章节 + 信源汇总）
```

**和 ChatGPT / Perplexity 的区别：**
- 不是一个模型回答一次，而是多个 Agent 协作、互相补充、自我修正
- 全程可视化（画布上实时生长知识图谱）
- 决策透明（为什么有第二轮、新增了谁、重定向了谁）

## 功能特性

| 特性 | 说明 |
|------|------|
| 动态角色生成 | 无预定义角色。主分析师根据问题领域自主设计专家团队，自动选用对应的专业方法论 |
| 自进化循环 | 主分析师评判结果，可新增/重定向/移除专家。最多 4 轮迭代直到判定充分 |
| 知识图谱 | Canvas 实时可视化：专家节点 → 观点节点 → 信源节点，三层结构实时生长 |
| 深度报告 | 总论（主分析师综合判断）+ 分论（各专家深度分析章节，500-1000字，含数据和引用） |
| 调研日志 | 点击 Round 指示器查看每轮决策历史：主分析师的评判理由、新增/重定向/移除操作 |
| 实时动态 | 状态栏实时显示每个 Agent 的搜索动态、完成情况、论据数量、置信度 |
| 场景提示 | 5 个快捷场景（通用/热点/人物/股票/八卦），辅助主分析师更快进入专业状态 |
| 4 层容错 | 带工具 → 去工具 → JSON提示 → 原始文本兜底，不丢失任何 Agent 的调研成果 |

## 快速开始

### 环境要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) 包管理器
- 一个 OpenAI 兼容的 API Key（推荐使用 OpenRouter，有免费模型）

### 安装

```bash
git clone https://github.com/PM-Shawn/ThoughtFission-Evo.git
cd ThoughtFission-Evo
uv sync
```

### 运行

```bash
uv run python main.py
```

浏览器打开 http://localhost:8299

### 配置

点击页面右上角 ⚙ 齿轮图标：

1. **API Key**: 你的 OpenRouter API Key（在 [openrouter.ai](https://openrouter.ai) 免费注册）
2. **模型**: 默认 `stepfun/step-3.5-flash:free`（免费）。效果更好可选 `anthropic/claude-sonnet-4` 或 `openai/gpt-4o`
3. **搜索引擎**（可选）: Tavily / Bing / DuckDuckGo，提供实时搜索能力

### 环境变量（可选）

```bash
export OPENROUTER_API_KEY="sk-or-..."
export OPENROUTER_MODEL="stepfun/step-3.5-flash:free"
export THOUGHTFISSION_PORT=8299
```

## 使用手册

### 基本流程

1. （可选）在底部选择场景提示：通用 / 热点 / 人物 / 股票 / 八卦
2. 在输入框输入你的问题
3. 观察画布上专家节点出现并并行调研
4. 点击任意专家节点查看其发现、方法论和信源
5. 点击右上角 `Round X/Y` 查看调研决策日志
6. 完成后右侧弹出报告面板，展示完整分析

### 示例问题

```
TikTok 在美国面临禁令，字节跳动有哪些选择？最终可能怎么收场？

分析英伟达当前股价是否被高估。

椰树椰汁再因擦边广告语翻车，产品力过硬的椰树坚持「擦边」二十年，为什么？

2025年多地取消公摊面积，对房价、开发商、购房者分别有什么影响？
```

### 节点交互

- **左键点击** 专家节点：查看详细分析卡片
- **右键点击** 专家节点：弹出操作菜单
  - **深钻**：对该专家的发现进行二次裂变，派出 2-3 个子专家深入调查
  - **重定向**：给该专家一个新的调研方向
  - **移除**：从分析中移除该专家
- **拖拽** 节点：调整画布布局

### 画布节点说明

| 节点类型 | 外观 | 含义 |
|---------|------|------|
| 主分析师（大紫色圆） | 画布中央，带光晕 | 负责团队设计、评判、汇报的主管 |
| 专家（彩色圆） | 围绕主分析师分布 | 负责某个维度调研的专家 |
| 观点（小圆点） | 连接到专家 | 该专家的一个关键论据 |
| 信源（更小圆点） | 连接到观点 | 支撑该论据的网页来源 |
| 汇报（白色圆） | 最后出现 | 最终汇报节点 |

### 报告结构

报告采用 **总分结构**：

- **总论**（主分析师撰写）
  - 报告标题（反映核心结论）
  - 执行摘要（200-400字，结论先行）
  - 风险评估
  - 可执行建议（3-5条）
  - 团队分歧
- **分论**（各专家撰写）
  - 每位专家的深度分析章节（500-1000字）
  - 含具体数据、信息来源引用、趋势判断
- **信源汇总**
  - 所有调研过程中收集的网页来源

## 服务器部署

### 快速部署

```bash
# 在服务器上
git clone https://github.com/PM-Shawn/ThoughtFission-Evo.git
cd ThoughtFission-Evo

# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# 安装依赖
uv sync

# 后台运行
nohup uv run python main.py > /var/log/thoughtfission.log 2>&1 &
```

### Systemd 服务（推荐）

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

常用命令：

```bash
systemctl status thoughtfission    # 查看状态
systemctl restart thoughtfission   # 重启
journalctl -u thoughtfission -f    # 查看日志
```

### 防火墙

```bash
# CentOS
firewall-cmd --permanent --add-port=8299/tcp && firewall-cmd --reload

# Ubuntu
ufw allow 8299
```

同时在云服务商控制台的**安全组**中放行 8299 端口。

### 多用户并发

当前架构中每个请求生成独立的 `session_id`，多用户同时使用**不会串台**。但注意：

- 服务重启后进行中的会话丢失
- 内存占用随并发会话数增长
- 单进程模式，高并发下可能响应变慢

个人或小团队使用完全够用。

## 技术架构

```
ThoughtFission-Evo/
├── main.py              # FastAPI 服务器（API 端点 + SSE 流式推送）
├── config.py            # 环境配置（模型、API Key、端口）
├── engine/
│   ├── agents.py        # Agent 工厂 + Pydantic 数据模型
│   ├── thinker.py       # 核心流程：think() → _run_experts() → synthesis
│   ├── session.py       # 会话状态管理
│   └── sse_hooks.py     # RunHooks → SSE 事件桥接
├── skills/
│   ├── web_search.py    # @tool: Tavily / Bing / DuckDuckGo 搜索
│   └── analyze.py       # @tool: 分析辅助工具
└── web/
    └── index.html       # 单页 Canvas 可视化应用
```

### AgentX 框架集成

| API | 用途 |
|-----|------|
| `Agent(name, instructions, model, output_type, tools, hooks)` | 创建所有角色 |
| `Runner.run(agent, prompt)` | 执行 Agent，获取 `parsed_output` |
| `output_type=PydanticModel` | 结构化输出验证（6 个模型） |
| `@tool` | 搜索和分析工具 |
| `RunHooks` | 实时 SSE 事件推送 |
| `OpenAIProvider` | 模型后端（OpenRouter 兼容） |

### SSE 事件列表

| 事件 | 触发时机 |
|------|---------|
| `phase` | 流程阶段变化（planning/exploring/judging/synthesizing） |
| `fission` | 主分析师创建专家团队 |
| `agent_finding` | 专家完成调研 |
| `judgment` | 主分析师评判结果 |
| `agent_spawn` | 新一轮中新增专家 |
| `agent_redirect` | 专家被重定向到新方向 |
| `agent_dropped` | 专家被移除 |
| `synthesis` | 最终报告就绪 |

## 技术栈

- **后端**: Python 3.11+, FastAPI, uvicorn
- **Agent 框架**: [AgentX](https://github.com/anthropics/agentx)（模型无关、结构化输出、工具调用、流式回调）
- **前端**: 原生 JavaScript + HTML5 Canvas（零依赖）
- **流式通信**: Server-Sent Events (SSE)
- **模型**: 任何 OpenAI 兼容 API（OpenRouter、OpenAI、Anthropic、本地 Ollama）

## 开源协议

MIT
