"""Core engine — self-evolving agent loop.

Orchestrates: Supervisor designs team → [experts execute → judge evaluates → actions] loop → synthesis
"""

from __future__ import annotations

import asyncio
from typing import Any

from agentx.loop.runner import Runner

from config import MODEL
from engine.agents import (
    AgentSpec,
    Finding,
    FissionPlan,
    KeyPoint,
    SupervisorJudgment,
    SynthesisInput,
    create_expert,
    create_judge,
    create_supervisor,
    create_synthesis_agent,
)
from engine.session import SessionState
from engine.sse_hooks import SSEBridge


async def think(
    question: str,
    bridge: SSEBridge,
    scenario_hint: str = "",
    model=None,
    session: SessionState | None = None,
    max_rounds: int = 4,
) -> None:
    """Run the self-evolving pipeline, pushing events to SSEBridge."""
    hooks = bridge.build_hooks()
    if model is None:
        model = MODEL

    try:
        # ── Phase 1: Supervisor designs the team ──
        await bridge.push("phase", {"phase": "planning", "question": question})

        supervisor = create_supervisor(model, hooks=hooks, scenario_hint=scenario_hint)
        plan = None
        for attempt in range(3):
            try:
                result = await Runner.run(supervisor, f"用户问题: {question}")
                plan = result.parsed_output
                break
            except Exception as e:
                print(f"[SUPERVISOR RETRY {attempt + 1}] {e}")
                if attempt == 2:
                    await bridge.push("error", {"message": f"主分析师设计团队失败: {str(e)}"})
                    await bridge.done()
                    return

        await bridge.push("fission", {
            "rationale": plan.rationale,
            "agents": [
                {"name": s.name, "task": s.task, "methodology": s.methodology}
                for s in plan.agents
            ],
        })

        # Active agent list (can grow/shrink dynamically)
        active_specs: list[AgentSpec] = list(plan.agents)
        all_findings: dict[str, tuple[AgentSpec, Finding]] = {}
        round_num = 0

        for round_num in range(1, max_rounds + 1):
            # ── Phase 2: Execute agents that need running ──
            specs_to_run = [s for s in active_specs if s.name not in all_findings]

            if specs_to_run:
                await bridge.push("phase", {
                    "phase": "exploring",
                    "round": round_num,
                    "total_agents": len(active_specs),
                    "running": len(specs_to_run),
                })

                new_findings = await _run_experts(
                    specs_to_run, question, bridge, model, hooks, session,
                )
                all_findings.update(new_findings)

            # All agents failed
            if not all_findings:
                await bridge.push("error", {"message": "所有Agent都失败了"})
                await bridge.done()
                return

            # Last round — skip judgment, go to synthesis
            if round_num >= max_rounds:
                break

            # ── Phase 3: Supervisor judges results ──
            await bridge.push("phase", {
                "phase": "judging",
                "round": round_num,
                "max_rounds": max_rounds,
            })

            judge = create_judge(model, hooks=hooks)
            judgment_prompt = _build_judgment_prompt(question, all_findings)

            try:
                j_result = await Runner.run(judge, judgment_prompt)
                judgment: SupervisorJudgment = j_result.parsed_output
            except Exception as e:
                print(f"[JUDGE ERROR] Round {round_num}: {e}")
                # If judge fails, assume sufficient and move to synthesis
                judgment = SupervisorJudgment(
                    assessment="评判失败，默认进入汇报阶段。",
                    is_sufficient=True,
                    actions=[],
                )

            await bridge.push("judgment", {
                "round": round_num,
                "assessment": judgment.assessment,
                "is_sufficient": judgment.is_sufficient,
                "actions": [
                    {
                        "type": a.type,
                        "target_agent": a.target_agent,
                        "new_spec": {
                            "name": a.new_spec.name,
                            "task": a.new_spec.task,
                            "methodology": a.new_spec.methodology,
                        } if a.new_spec else None,
                        "reason": a.reason,
                    }
                    for a in judgment.actions
                ],
            })

            if judgment.is_sufficient:
                break

            # ── Execute Supervisor's actions ──
            for action in judgment.actions:
                if action.type == "spawn" and action.new_spec:
                    active_specs.append(action.new_spec)
                    await bridge.push("agent_spawn", {
                        "name": action.new_spec.name,
                        "task": action.new_spec.task,
                        "methodology": action.new_spec.methodology,
                        "reason": action.reason,
                    })

                elif action.type == "redirect" and action.target_agent:
                    # Remove old finding so it re-runs next loop
                    all_findings.pop(action.target_agent, None)
                    # Update the spec's task with the new direction
                    for s in active_specs:
                        if s.name == action.target_agent:
                            s.task = action.reason
                            break
                    await bridge.push("agent_redirect", {
                        "agent_id": action.target_agent,
                        "new_direction": action.reason,
                    })

                elif action.type == "drop" and action.target_agent:
                    active_specs = [
                        s for s in active_specs
                        if s.name != action.target_agent
                    ]
                    all_findings.pop(action.target_agent, None)
                    await bridge.push("agent_dropped", {
                        "agent_id": action.target_agent,
                        "reason": action.reason,
                    })

        # ── Phase 4: Synthesis ──
        await bridge.push("phase", {"phase": "synthesizing"})
        await _run_synthesis(
            question, all_findings, bridge, model, hooks, round_num,
        )

    except Exception as e:
        await bridge.push("error", {"message": f"Engine error: {str(e)}"})

    finally:
        await bridge.done()


async def _run_experts(
    specs: list[AgentSpec],
    question: str,
    bridge: SSEBridge,
    model,
    hooks,
    session: SessionState | None,
) -> dict[str, tuple[AgentSpec, Finding]]:
    """Run a batch of expert agents in parallel. Returns {name: (spec, finding)}."""
    results: dict[str, tuple[AgentSpec, Finding]] = {}

    async def run_one(spec: AgentSpec):
        prompt = f"原始问题: {question}\n\n你的具体任务: {spec.task}"

        # Attempt 1: with tools
        try:
            agent = create_expert(spec, model, hooks=hooks)
            r = await Runner.run(agent, prompt)
            finding = r.parsed_output
        except Exception as e:
            print(f"[AGENT RETRY] {spec.name}: {e} — retrying without tools")
            # Attempt 2: without tools
            try:
                no_search_spec = AgentSpec(
                    name=spec.name, task=spec.task,
                    methodology=spec.methodology, needs_search=False,
                )
                fallback = create_expert(no_search_spec, model, hooks=hooks)
                r = await Runner.run(fallback, prompt)
                finding = r.parsed_output
            except Exception as e2:
                # Attempt 3: explicit JSON hint
                print(f"[AGENT RETRY2] {spec.name}: {e2} — retrying with JSON hint")
                try:
                    no_search_spec = AgentSpec(
                        name=spec.name, task=spec.task,
                        methodology=spec.methodology, needs_search=False,
                    )
                    fallback2 = create_expert(no_search_spec, model, hooks=hooks)
                    json_hint = (
                        prompt + '\n\n请严格按以下JSON格式输出，不要有任何其他文字:\n'
                        '{"finding":"你的核心发现","confidence":0.8,'
                        '"key_points":[{"point":"论据1","sources":["url1"]},{"point":"论据2","sources":[]}],'
                        '"detailed_report":"## 分析\\n详细分析内容"}'
                    )
                    r = await Runner.run(fallback2, json_hint)
                    finding = r.parsed_output
                except Exception as e3:
                    print(f"[AGENT FALLBACK] {spec.name}: {e3} — extracting raw text")
                    # Layer 4: try to get raw text from last model response
                    raw_text = ""
                    try:
                        # Run without output_type to get raw text
                        from agentx.loop.agent import Agent as _Agent
                        raw_agent = _Agent(
                            name=spec.name,
                            instructions=spec.methodology + f"\n\n任务: {spec.task}",
                            model=model,
                        )
                        raw_result = await Runner.run(raw_agent, prompt)
                        raw_text = raw_result.output or ""
                    except Exception:
                        raw_text = f"模型输出格式异常，无法解析。错误: {str(e3)[:200]}"

                    finding = Finding(
                        finding=f"{spec.name}完成了调研分析（输出格式异常，原始分析见详情）。",
                        confidence=0.5,
                        key_points=[KeyPoint(point=f"任务: {spec.task[:80]}", sources=[])],
                        detailed_report=raw_text[:2000] if raw_text else "",
                    )

        # Serialize key_points for SSE (each with its own sources)
        kp_data = [
            {"point": kp.point, "sources": kp.sources}
            for kp in finding.key_points
        ]
        all_sources = []
        for kp in finding.key_points:
            all_sources.extend(kp.sources)

        await bridge.push("agent_finding", {
            "agent_id": spec.name,
            "methodology": spec.methodology[:100],
            "finding": finding.finding,
            "confidence": finding.confidence,
            "key_points": kp_data,
            "sources": list(set(all_sources)),
            "detailed_report": finding.detailed_report,
        })
        if session:
            session.add_finding(
                agent_id=spec.name, faction="auto", task=spec.task,
                finding=finding.finding, confidence=finding.confidence,
                key_points=[kp.point for kp in finding.key_points],
                sources=list(set(all_sources)),
            )
        results[spec.name] = (spec, finding)

    await asyncio.gather(*[run_one(s) for s in specs])
    return results


def _build_judgment_prompt(
    question: str,
    all_findings: dict[str, tuple[AgentSpec, Finding]],
) -> str:
    """Build the prompt for the Supervisor's judgment."""
    parts = [f"用户原始问题: {question}\n\n当前团队调研结果:\n"]
    for name, (spec, finding) in all_findings.items():
        parts.append(
            f"## {spec.name}\n"
            f"方法论: {spec.methodology[:150]}\n"
            f"任务: {spec.task}\n"
            f"发现: {finding.finding}\n"
            f"置信度: {finding.confidence}\n"
            f"关键论据: {', '.join(kp.point for kp in finding.key_points)}\n"
            f"信息来源: {', '.join(s for kp in finding.key_points for s in kp.sources[:1]) or '无'}\n"
        )
    parts.append(
        "\n请逐一检查覆盖面、深度、矛盾点、信息源四个维度，"
        "判断以上结果是否足以全面回答用户的问题。"
    )
    return "\n".join(parts)


async def _run_synthesis(
    question: str,
    all_findings: dict[str, tuple[AgentSpec, Finding]],
    bridge: SSEBridge,
    model,
    hooks,
    total_rounds: int,
) -> None:
    """Run the synthesis agent to produce final report."""
    synth = None
    for attempt in range(3):
        try:
            synthesis_agent = create_synthesis_agent(model, hooks=hooks)
            synthesis_prompt = _build_synthesis_prompt(question, all_findings, total_rounds)
            synth_result = await Runner.run(synthesis_agent, synthesis_prompt)
            synth = synth_result.parsed_output
            break
        except Exception as e:
            print(f"[SYNTHESIS RETRY {attempt + 1}] {e}")
            if attempt == 2:
                # Fallback: manual synthesis
                synth = SynthesisInput(
                    title="调研分析报告",
                    executive_summary="综合分析完成。" + "; ".join(
                        f"{name}: {f.finding[:80]}"
                        for name, (_, f) in all_findings.items()
                    ),
                    risk_assessment="综合阶段模型输出解析失败，无法生成风险评估。",
                    actionable_insights=["请查看各专家的原始分析结果。"],
                    dissenting_views=[],
                    confidence=sum(
                        f.confidence for _, f in all_findings.values()
                    ) / max(len(all_findings), 1),
                )

    if synth is None:
        synth = SynthesisInput(
            title="调研分析报告",
            executive_summary="综合分析完成（模型输出异常，以下为原始汇总）。",
            risk_assessment="无法生成风险评估。",
            actionable_insights=["请查看各专家的原始分析结果。"],
            dissenting_views=[], confidence=0.5,
        )

    # Build expert sections for the report
    expert_sections = []
    all_sources_list = []
    for name, (spec, finding) in all_findings.items():
        kp_data = [{"point": kp.point, "sources": kp.sources} for kp in finding.key_points]
        for kp in finding.key_points:
            all_sources_list.extend(kp.sources)
        expert_sections.append({
            "name": spec.name,
            "methodology": spec.methodology,
            "task": spec.task,
            "finding": finding.finding,
            "confidence": finding.confidence,
            "key_points": kp_data,
            "detailed_report": finding.detailed_report,
        })

    await bridge.push("synthesis", {
        "title": synth.title,
        "executive_summary": synth.executive_summary,
        "risk_assessment": synth.risk_assessment,
        "actionable_insights": synth.actionable_insights,
        "dissenting_views": synth.dissenting_views,
        "confidence": synth.confidence,
        "expert_sections": expert_sections,
        "all_sources": list(set(all_sources_list)),
        "total_rounds": total_rounds,
        "total_agents": len(all_findings),
    })


def _build_synthesis_prompt(
    question: str,
    all_findings: dict[str, tuple[AgentSpec, Finding]],
    total_rounds: int,
) -> str:
    """Build prompt for synthesis with all findings context."""
    parts = [
        f"用户原始问题: {question}\n",
        f"经过 {total_rounds} 轮调研，共 {len(all_findings)} 位专家参与分析。\n",
        "以下是各专家的分析结果:\n",
    ]
    for name, (spec, finding) in all_findings.items():
        parts.append(
            f"## {spec.name}（置信度: {finding.confidence}）\n"
            f"方法论: {spec.methodology[:150]}\n"
            f"核心发现: {finding.finding}\n"
            f"关键论据:\n"
            + "\n".join(f"  - {kp.point}" for kp in finding.key_points)
            + "\n"
        )
    parts.append(
        "\n各专家已经各自撰写了深度分析章节，你不需要重复他们的具体分析。\n"
        "你需要撰写报告的「总论」部分：\n"
        "- 综合所有专家发现，提炼全局洞察\n"
        "- 指出各维度之间的关联和矛盾\n"
        "- 给出整体判断和可执行建议\n"
        "- 达到'可以直接发给老板/客户'的水平"
    )
    return "\n".join(parts)


async def deep_drill(
    session: SessionState,
    agent_id: str,
    bridge: SSEBridge,
    custom_prompt: str | None = None,
) -> None:
    """Deep-drill into a specific agent's finding — re-fission into sub-agents."""
    hooks = bridge.build_hooks()
    model = session.model
    finding = session.findings.get(agent_id)

    if not finding:
        await bridge.push("error", {"message": f"找不到Agent: {agent_id}"})
        await bridge.done()
        return

    try:
        drill_context = custom_prompt or finding.finding
        await bridge.push("phase", {"phase": "deep_drilling", "parent": agent_id})

        supervisor = create_supervisor(model, hooks=hooks)
        router_prompt = (
            f"原始问题: {session.question}\n\n"
            f"一位专家({agent_id})给出了以下发现:\n"
            f"{finding.finding}\n\n"
            f"置信度: {finding.confidence}\n"
            f"关键论据: {', '.join(finding.key_points)}\n\n"
            f"用户希望深入探索这个方向。请将这个发现裂变为2-3个更深入的子问题，"
            f"派出新的专家进行深度调查。"
        )

        result = await Runner.run(supervisor, router_prompt)
        plan: FissionPlan = result.parsed_output

        sub_agents_info = [
            {"name": s.name, "task": s.task, "methodology": s.methodology}
            for s in plan.agents
        ]
        await bridge.push("deep_fission", {
            "parent_id": agent_id,
            "rationale": plan.rationale,
            "sub_agents": sub_agents_info,
        })

        # Run sub-agents
        async def run_sub_expert(spec: AgentSpec):
            prompt = (
                f"原始问题: {session.question}\n\n"
                f"上级发现: {finding.finding}\n\n"
                f"你的深度任务: {spec.task}"
            )
            try:
                agent = create_expert(spec, model, hooks=hooks)
                r = await Runner.run(agent, prompt)
                sub_finding: Finding = r.parsed_output
            except Exception as e:
                print(f"[DRILL RETRY] {spec.name}: {e}")
                try:
                    no_search = AgentSpec(
                        name=spec.name, task=spec.task,
                        methodology=spec.methodology, needs_search=False,
                    )
                    fallback = create_expert(no_search, model, hooks=hooks)
                    r = await Runner.run(fallback, prompt)
                    sub_finding: Finding = r.parsed_output
                except Exception as e2:
                    print(f"[DRILL ERROR] {spec.name}: {e2}")
                    await bridge.push("agent_error", {
                        "agent_id": spec.name, "error": str(e2),
                    })
                    return

            await bridge.push("agent_finding", {
                "agent_id": spec.name,
                "methodology": spec.methodology[:80],
                "finding": sub_finding.finding,
                "confidence": sub_finding.confidence,
                "key_points": sub_finding.key_points,
                "sources": sub_finding.sources,
                "parent_id": agent_id,
            })
            if session:
                session.add_finding(
                    agent_id=spec.name, faction="auto", task=spec.task,
                    finding=sub_finding.finding, confidence=sub_finding.confidence,
                    key_points=sub_finding.key_points, sources=sub_finding.sources,
                )

        await asyncio.gather(*[run_sub_expert(s) for s in plan.agents])

    except Exception as e:
        await bridge.push("error", {"message": f"Deep drill error: {str(e)}"})

    finally:
        await bridge.done()
