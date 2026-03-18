"""Agent factory — self-evolving architecture.

Supervisor dynamically designs expert teams with custom methodologies.
No predefined factions — LLM generates roles, tasks, and analysis frameworks.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentx.loop.agent import Agent
from agentx.loop.hooks import RunHooks

from skills.web_search import web_search
from skills.analyze import deep_analyze


# ── Pydantic models ──


class AgentSpec(BaseModel):
    """Expert agent specification — fully dynamic, no fixed factions."""
    name: str = Field(description="角色名称，如'财报分析师'")
    task: str = Field(description="该角色需要完成的具体任务")
    methodology: str = Field(
        description="分析方法论和思维框架，3-5句话，写清楚用什么方法、关注什么指标"
    )
    needs_search: bool = Field(default=True, description="是否需要搜索工具获取实时信息")


class FissionPlan(BaseModel):
    """Supervisor's team design output."""
    rationale: str = Field(description="团队设计理由，说明为什么选择这些角色")
    agents: list[AgentSpec] = Field(description="团队成员，3-5人")


# Forward ref rebuild
FissionPlan.model_rebuild()


class KeyPoint(BaseModel):
    """A single key point with its supporting sources."""
    point: str = Field(description="关键论据，一句话")
    sources: list[str] = Field(default_factory=list, description="支撑该论据的信息来源URL")


class Finding(BaseModel):
    """Structured output for each expert agent."""
    finding: str = Field(description="核心发现，2-3句话概括")
    confidence: float = Field(description="置信度 0.0-1.0", ge=0.0, le=1.0)
    key_points: list[KeyPoint] = Field(description="关键论据，5-8条，每条附带信息来源")
    detailed_report: str = Field(
        default="",
        description="该维度的深度分析章节，Markdown格式，500-1000字。"
        "包含：背景分析、数据论证、趋势判断、风险提示。"
        "用具体数据说话，引用[来源](url)标注信息出处。"
        "可使用Markdown表格对比数据。"
    )


class SupervisorAction(BaseModel):
    """A single action the Supervisor wants to take."""
    type: str = Field(description="行动类型: spawn(新增角色) / redirect(重定向) / drop(移除)")
    target_agent: str = Field(default="", description="目标Agent名称（redirect/drop时填）")
    new_spec: AgentSpec | None = Field(
        default=None, description="新Agent的规格（spawn时填）"
    )
    reason: str = Field(description="为什么要执行这个操作")


class SupervisorJudgment(BaseModel):
    """Supervisor's evaluation of current findings."""
    assessment: str = Field(description="对当前所有结果的总体评价，3-5句话")
    is_sufficient: bool = Field(description="当前结果是否足以全面回答用户问题")
    actions: list[SupervisorAction] = Field(
        default_factory=list,
        description="如果不充分，需要采取的行动列表；如果充分则留空"
    )


# Rebuild forward refs for nested models
SupervisorJudgment.model_rebuild()


class SynthesisInput(BaseModel):
    """Supervisor's executive summary — the '总' part of the report."""
    title: str = Field(description="报告标题，反映核心结论，如'TikTok禁令：短期阵痛与长期重构'")
    executive_summary: str = Field(
        description="执行摘要，Markdown格式，200-400字。"
        "结论先行，综合所有专家发现，给出全局判断。"
        "用具体数据支撑，引用各专家的关键发现。"
    )
    risk_assessment: str = Field(description="整体风险评估，Markdown格式，100-200字")
    actionable_insights: list[str] = Field(description="可行动的建议/下一步，3-5条，每条要具体可执行")
    dissenting_views: list[str] = Field(default_factory=list, description="团队内部分歧，0-3条")
    confidence: float = Field(description="综合置信度 0.0-1.0")


# ── Agent factories ──


def create_supervisor(
    model, hooks: RunHooks | None = None, scenario_hint: str = "",
) -> Agent:
    """Create the Supervisor agent that designs the research team."""
    hint = f"\n\n场景提示: {scenario_hint}" if scenario_hint else ""
    return Agent(
        name="supervisor",
        instructions=(
            "你是一位资深分析主管，具备跨领域的专业知识和方法论储备。\n\n"
            "用户会提出一个问题，你需要:\n"
            "1. 判断这个问题属于什么领域\n"
            "2. 设计一个最合适的分析团队（3-5人）\n"
            "3. 为每个人指定：角色名称、具体任务、分析方法论\n\n"
            "核心要求:\n"
            "- 根据问题领域，自主选择最合适的专业分析框架\n"
            "- 每个角色的 methodology 必须写明：用什么具体框架、分析什么指标、产出什么结论\n"
            "- 如果你熟悉该领域的经典方法论，主动使用\n"
            "- 如果问题跨领域或非常规，自行设计分析框架\n"
            "- 角色之间要互补，覆盖不同维度\n"
            "- 至少有一个角色负责质疑和风险检查\n"
            f"{hint}\n\n"
            "重要: 你必须只输出纯JSON，不要包含任何markdown格式(不要```json```)，"
            "不要有任何前缀或后缀文字。"
        ),
        model=model,
        output_type=FissionPlan,
        hooks=hooks,
    )


def create_judge(model, hooks: RunHooks | None = None) -> Agent:
    """Create the Judge agent that evaluates current findings."""
    return Agent(
        name="supervisor_judge",
        instructions=(
            "你是分析主管。你的团队已经完成了一轮调研，你需要评判:\n\n"
            "评判维度（必须逐一检查）:\n"
            "1. 覆盖面: 是否有重要维度被遗漏？\n"
            "2. 深度: 是否有发现太浅、缺乏具体数据或论据？\n"
            "3. 矛盾点: 发现之间是否有矛盾需要补充调查？\n"
            "4. 信息源: 是否有关键信息缺乏可靠来源？\n\n"
            "如果不够充分，你可以采取行动:\n"
            "- spawn: 生成一个新角色去调查缺失的维度（必须提供完整的 new_spec）\n"
            "- redirect: 让某个现有角色换方向重新调查（reason 中写明新方向）\n"
            "- drop: 去掉一个不相关或重复的角色\n\n"
            "如果已经充分，设 is_sufficient=true，actions 留空。\n"
            "注意: 不要过于苛刻，3-4个维度覆盖到、论据充实就够了。\n\n"
            "重要: 你必须只输出纯JSON，不要包含任何markdown格式(不要```json```)，"
            "不要有任何前缀或后缀文字。"
        ),
        model=model,
        output_type=SupervisorJudgment,
        hooks=hooks,
    )


def create_expert(
    spec: AgentSpec, model, hooks: RunHooks | None = None,
) -> Agent:
    """Create an expert agent using LLM-generated methodology."""
    use_tools = spec.needs_search
    tools_instruction = (
        "- 使用搜索工具获取最新信息\n" if use_tools
        else "- 基于你的知识进行分析\n"
    )
    return Agent(
        name=spec.name,
        instructions=(
            f"{spec.methodology}\n\n"
            f"你的任务:\n{spec.task}\n\n"
            "调研要求:\n"
            f"{tools_instruction}"
            "- 必须从多个角度搜索，至少搜索3-5次，用不同关键词覆盖不同信息源\n"
            "- 不要只搜一次就下结论，确保数据充分再分析\n"
            "- 优先搜索：权威媒体报道、行业研究报告、官方数据、专家观点\n"
            "- 每次搜索后评估：是否还有遗漏的重要维度？\n\n"
            "输出要求:\n"
            "- 给出你的核心发现和置信度(0-1)\n"
            "- 列出5-8个关键论据，每个论据必须标注支撑它的信息来源URL\n"
            "- key_points 格式: [{\"point\": \"论据内容\", \"sources\": [\"url1\", \"url2\"]}, ...]\n"
            "- detailed_report: 撰写该维度的深度分析章节（Markdown格式，500-1000字）\n"
            "  章节标准（参考专业研报水平）:\n"
            "  * 用具体数据说话，不说'增长很快'，说'同比增长34.2%'\n"
            "  * 引用信息来源，格式: [来源名](url)\n"
            "  * 可用Markdown表格对比关键数据\n"
            "  * 包含趋势判断和风险提示\n"
            "  * 达到'可以直接发给客户'的深度\n\n"
            "重要: 你必须只输出纯JSON，不要包含任何markdown格式(不要```json```)，"
            "不要有任何前缀或后缀文字。"
        ),
        model=model,
        tools=[web_search, deep_analyze] if use_tools else [],
        output_type=Finding,
        hooks=hooks,
    )


def create_synthesis_agent(model, hooks: RunHooks | None = None) -> Agent:
    """Create the synthesis agent — Supervisor writes the executive overview."""
    return Agent(
        name="supervisor",
        instructions=(
            "你是主分析师，全程主导了本次调研。现在你需要撰写报告的「总论」部分。\n"
            "各专家已经各自撰写了深度分析章节，你不需要重复他们的内容。\n\n"
            "你负责的部分:\n"
            "1. title: 报告标题——反映核心结论，有洞察力，如'短期阵痛与长期重构'\n"
            "2. executive_summary: 执行摘要（Markdown格式，200-400字）\n"
            "   - 结论先行：读完摘要就知道最终判断\n"
            "   - 综合各专家发现，提炼全局洞察\n"
            "   - 用具体数据支撑，不要空话\n"
            "   - 指出各维度之间的关联和矛盾\n"
            "3. risk_assessment: 整体风险评估（Markdown格式，100-200字）\n"
            "4. actionable_insights: 可执行建议，3-5条\n"
            "   - 不说'加强创新'，说'Q2前完成X，预算Y万'\n"
            "5. dissenting_views: 团队内部的主要分歧\n\n"
            "标准: 达到'可以直接发给老板/客户'的水平。\n\n"
            "重要: 你必须只输出纯JSON，不要包含任何markdown格式标记(不要```json```)，"
            "不要有任何前缀或后缀文字。JSON中的字符串值可以包含Markdown内容。"
        ),
        model=model,
        output_type=SynthesisInput,
        hooks=hooks,
    )
