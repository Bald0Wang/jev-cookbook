"""阶跃星辰 StepFun — see adapters/__init__.py for the preset."""
from .openai_compat import OpenAICompatAdapter


class StepFunAdapter(OpenAICompatAdapter):
    adapter_name = "stepfun"
    DEFAULT_BASE_URL = "https://api.stepfun.com/v1"
    DEFAULT_MODEL = "step-1-8k"