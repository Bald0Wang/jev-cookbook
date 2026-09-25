"""Zhipu GLM — see adapters/__init__.py for the preset."""
from .openai_compat import OpenAICompatAdapter


class GLMAdapter(OpenAICompatAdapter):
    adapter_name = "glm"
    DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    DEFAULT_MODEL = "glm-4-plus"