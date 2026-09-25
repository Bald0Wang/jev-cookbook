"""Qwen (DashScope) — see adapters/__init__.py for the preset."""
from .openai_compat import OpenAICompatAdapter


class QwenAdapter(OpenAICompatAdapter):
    adapter_name = "qwen"
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL = "qwen-plus"