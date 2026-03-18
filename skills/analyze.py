"""Analysis tools for agents."""

from __future__ import annotations

from agentx.tools.decorator import tool


@tool(description="对文本进行深度分析，提取关键论点、数据和逻辑关系。")
async def deep_analyze(text: str, focus: str = "") -> str:
    """Analyze text deeply, extracting key arguments, data points, and logical relationships."""
    prompt = f"请深度分析以下内容"
    if focus:
        prompt += f"，重点关注: {focus}"
    prompt += f"\n\n内容:\n{text}"
    return prompt


@tool(description="比较两个或多个观点，找出共识和分歧。")
async def compare_viewpoints(viewpoints: str) -> str:
    """Compare multiple viewpoints to find consensus and disagreements."""
    return f"请比较以下观点，找出共识和分歧:\n{viewpoints}"
