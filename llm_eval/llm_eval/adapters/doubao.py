"""ByteDance 豆包 via 火山方舟 — see adapters/__init__.py for the preset."""
from .openai_compat import OpenAICompatAdapter


class DoubaoAdapter(OpenAICompatAdapter):
    adapter_name = "doubao"
    DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    DEFAULT_MODEL = ""  # user must pass --model as endpoint id