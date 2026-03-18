"""Web search tool — supports multiple search backends.

Backends:
- tavily:    Tavily Search API (default, requires TAVILY_API_KEY)
- bing:      Bing Web Search API (requires BING_API_KEY)
- duckduckgo: DuckDuckGo HTML scraper (free, no key required)
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from agentx.tools.decorator import tool

# Module-level config — set by main.py before agents run
_search_config: dict[str, str] = {
    "provider": "tavily",   # tavily | bing | duckduckgo
    "api_key": "",
}


def configure_search(provider: str = "tavily", api_key: str = ""):
    """Called by main.py to update search config from user settings."""
    _search_config["provider"] = provider
    _search_config["api_key"] = api_key


@tool(description="搜索互联网获取最新信息。返回搜索结果摘要，包含来源链接。")
async def web_search(query: str) -> str:
    """Search the web for information on a given query."""
    provider = _search_config["provider"]
    api_key = _search_config["api_key"]

    if provider == "tavily" and api_key:
        return await _tavily_search(query, api_key)
    elif provider == "bing" and api_key:
        return await _bing_search(query, api_key)
    else:
        # Fallback to DuckDuckGo (free, no key)
        return await _ddg_search(query)


async def _tavily_search(query: str, api_key: str) -> str:
    """Search via Tavily API — high quality, structured results."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": 8,
                "include_answer": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for i, r in enumerate(data.get("results", [])[:8], 1):
        title = r.get("title", "")
        url = r.get("url", "")
        snippet = r.get("content", "")[:200]
        entry = f"{i}. [{title}]({url})"
        if snippet:
            entry += f"\n   {snippet}"
        results.append(entry)

    if not results:
        return f"No results found for: {query}"
    return f"Search results for '{query}':\n" + "\n".join(results)


async def _bing_search(query: str, api_key: str) -> str:
    """Search via Bing Web Search API."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.bing.microsoft.com/v7.0/search",
            params={"q": query, "count": 8, "mkt": "zh-CN"},
            headers={"Ocp-Apim-Subscription-Key": api_key},
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for i, r in enumerate(data.get("webPages", {}).get("value", [])[:8], 1):
        title = r.get("name", "")
        url = r.get("url", "")
        snippet = r.get("snippet", "")[:200]
        entry = f"{i}. [{title}]({url})"
        if snippet:
            entry += f"\n   {snippet}"
        results.append(entry)

    if not results:
        return f"No results found for: {query}"
    return f"Search results for '{query}':\n" + "\n".join(results)


async def _ddg_search(query: str) -> str:
    """Search via DuckDuckGo HTML scraper — free, no key required."""
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0 (ThoughtFission/1.0)"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, data={"q": query}, headers=headers)
        resp.raise_for_status()

    text = resp.text
    results = []

    # Extract links with titles
    links = []
    for m in re.finditer(r'class="result__a"\s+href="([^"]+)"[^>]*>(.*?)</a>', text, re.DOTALL):
        link_url = m.group(1).strip()
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        links.append((title, link_url))

    # Extract snippets
    snippets = []
    for m in re.finditer(r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)', text, re.DOTALL):
        snippet = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        snippets.append(snippet)

    for i in range(min(8, len(links))):
        title, link = links[i]
        snippet = snippets[i] if i < len(snippets) else ""
        entry = f"{i+1}. [{title}]({link})"
        if snippet:
            entry += f"\n   {snippet}"
        results.append(entry)

    if not results:
        return f"No results found for: {query}"
    return f"Search results for '{query}':\n" + "\n".join(results)
