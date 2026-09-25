"""Moonshot / Kimi — see adapters/__init__.py for the preset."""
from .openai_compat import OpenAICompatAdapter


class MoonshotAdapter(OpenAICompatAdapter):
    adapter_name = "moonshot"
    DEFAULT_BASE_URL = "https://api.moonshot.cn/v1"
    DEFAULT_MODEL = "moonshot-v1-32k"