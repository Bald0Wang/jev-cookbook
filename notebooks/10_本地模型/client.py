"""Small Jev-shaped client around the downloaded Laya checkpoints."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


MODEL_DIRS = {
    "laya": "",
    "laya-english": "",
    "laya-multilingual": "multilingual",
    "laya-typed-decisions": "typed-decisions",
}


def _default_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class LayaClient:
    """Expose a single Laya checkpoint with Jev's ``state + questions`` shape.

    Chinese and other non-English input should use the multilingual checkpoint.
    Set ``LAYA_MODEL_DIR`` to point at a different local checkpoint directory.
    """

    def __init__(
        self,
        model_dir: str | Path | None = None,
        *,
        model_name: str | None = None,
        device: str | None = None,
    ) -> None:
        root = Path(__file__).resolve().parent / "models"
        configured = model_dir or os.environ.get("LAYA_MODEL_DIR")
        self.model_dir = Path(configured).expanduser() if configured else root / "multilingual"
        self.model_dir = self.model_dir.resolve()
        if not (self.model_dir / "model.safetensors").is_file():
            raise FileNotFoundError(
                f"No model.safetensors in {self.model_dir}; download a Laya checkpoint or set LAYA_MODEL_DIR"
            )

        if model_name:
            self.model_name = model_name
        elif self.model_dir.name == "multilingual":
            self.model_name = "laya-multilingual"
        elif self.model_dir.name == "typed-decisions":
            self.model_name = "laya-typed-decisions"
        else:
            self.model_name = "laya"

        # The inference modules live next to the `models/` checkpoint folders;
        # each checkpoint directory itself only contains its weights/config.
        module_path = str(Path(__file__).resolve().parent / "models")
        if module_path not in sys.path:
            sys.path.insert(0, module_path)
        from rl_agent_api import RLAgent

        self.device = device or _default_device()
        self._agent = RLAgent(str(self.model_dir), device=self.device)

    def system_one(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, dict[str, Any]],
        *,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate independent typed questions in one model call."""
        if not isinstance(state, (str, dict, list)):
            raise TypeError("state must be a string, object, or array")
        if not isinstance(questions, dict) or not questions:
            raise ValueError("questions must be a non-empty object")
        if model and model not in {self.model_name, "laya-latest"}:
            raise ValueError(
                f"This server has {self.model_name!r} loaded; start another instance to use {model!r}"
            )

        result = self._agent.system_one(state, questions)
        result["model"] = self.model_name
        # Keep the public shape close to Jev; expose no training/runtime internals.
        for answer in result["answers"].values():
            answer.pop("rl_agent", None)
        return result
