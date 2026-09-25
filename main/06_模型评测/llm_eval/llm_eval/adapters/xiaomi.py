"""小米 MiMo — see adapters/__init__.py for the preset.

The base URL is a placeholder until Xiaomi publishes the public API endpoint.
Adjust DEFAULT_BASE_URL when the public endpoint is confirmed.
"""
from .openai_compat import OpenAICompatAdapter


class XiaomiAdapter(OpenAICompatAdapter):
    adapter_name = "xiaomi"
    DEFAULT_BASE_URL = "https://api.xiaomi.com/v1"  # placeholder
    DEFAULT_MODEL = "mimo"