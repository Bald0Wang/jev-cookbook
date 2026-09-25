"""DeepSeek — see adapters/__init__.py for the preset."""
from .openai_compat import OpenAICompatAdapter


class DeepSeekAdapter(OpenAICompatAdapter):
    adapter_name = "deepseek"
    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
    DEFAULT_MODEL = "deepseek-chat"
    DEFAULT_PRICE_IN = 0.27   # USD per 1M tokens, cache miss
    DEFAULT_PRICE_OUT = 1.10