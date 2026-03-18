import os

from agentx.providers.openai import OpenAIProvider

# ── Model config ──
# Supports OpenRouter or any OpenAI-compatible API.
# Set env vars:
#   OPENROUTER_API_KEY  — your OpenRouter key
#   OPENROUTER_MODEL    — model name (default: anthropic/claude-sonnet-4)
#   OPENROUTER_BASE_URL — base URL (default: https://openrouter.ai/api/v1)
#
# Or for direct providers:
#   ANTHROPIC_API_KEY / OPENAI_API_KEY (auto-detected by AgentX)

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_NAME = os.environ.get("OPENROUTER_MODEL", "stepfun/step-3.5-flash:free")

if API_KEY:
    # Use OpenRouter (OpenAI-compatible)
    MODEL = OpenAIProvider(model=MODEL_NAME, api_key=API_KEY, base_url=BASE_URL)
else:
    # Fallback: use model string, let AgentX auto-detect provider
    MODEL = os.environ.get("THOUGHTFISSION_MODEL", "claude-sonnet-4-20250514")

HOST = os.environ.get("THOUGHTFISSION_HOST", "0.0.0.0")
PORT = int(os.environ.get("THOUGHTFISSION_PORT", "8299"))
