"""Frozen pure-vision Sonic Doom PP inference; no author code is imported.

Architecture and normalization follow the checkpoint's declared source commit
392f036b62e48f4be4394651a646182cb91a14ff. Only restricted weights loading is used.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

SOURCE_COMMIT = "392f036b62e48f4be4394651a646182cb91a14ff"
CHECKPOINT_SHA256 = "59756ba40d0e98140893548a576e1a2d024cdc201624a7964f9aca8a8ec98e37"
ACTIONS = ("noop", "left", "right", "shoot")


def resize_nearest(frame):
    """Exact source-index floor convention of OpenCV INTER_NEAREST."""
    rows = np.arange(72, dtype=np.int64) * 120 // 72
    columns = np.arange(128, dtype=np.int64) * 160 // 128
    return frame[rows[:, None], columns[None, :], :]


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tensor_sha(value):
    return hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


def branch(**children):
    module = nn.Module()
    for name, child in children.items():
        module.add_module(name, child)
    return module


class RMS(nn.Module):
    def __init__(self, shape):
        super().__init__()
        self.register_buffer("running_mean", torch.zeros(shape, dtype=torch.float64))
        self.register_buffer("running_var", torch.ones(shape, dtype=torch.float64))
        self.register_buffer("count", torch.ones(1, dtype=torch.float64))


class VisionActor(nn.Module):
    """Exact saved key hierarchy, including unused sound/return RMS buffers."""
    def __init__(self):
        super().__init__()
        self.obs_normalizer = branch(running_mean_std=branch(running_mean_std=nn.ModuleDict({
            "img": RMS((3, 72, 128)), "sound": RMS((2520, 2))})))
        self.returns_normalizer = RMS((1,))
        conv = nn.Sequential(nn.Conv2d(3, 32, 8, 4), nn.ELU(),
                             nn.Conv2d(32, 64, 4, 2), nn.ELU(),
                             nn.Conv2d(64, 128, 3, 2), nn.ELU())
        enc = branch(conv_head=conv, mlp_layers=nn.Sequential(nn.Linear(2304, 512), nn.ELU()))
        self.encoder = branch(basic_encoder=branch(enc=enc))
        self.core = branch(core=nn.GRU(512, 512, num_layers=1))
        self.critic_linear = nn.Linear(512, 1)
        self.action_parameterization = branch(distribution_linear=nn.Linear(512, 4))

    def normalize(self, pixels):
        # Match source's FP32 reciprocal multiplication and clip exactly.
        x = pixels.float().clone().mul_(1.0 / 255.0)
        rms = self.obs_normalizer.running_mean_std.running_mean_std["img"]
        sigma = torch.sqrt(rms.running_var.float() + 1e-5)
        return x.sub_(rms.running_mean.float()).mul_(1.0 / sigma).clamp_(-5.0, 5.0)

    def forward(self, pixels, hidden):
        normalized = self.normalize(pixels)
        enc = self.encoder.basic_encoder.enc
        x = enc.conv_head(normalized).contiguous().view(-1, 2304)
        x = enc.mlp_layers(x)
        core, following = self.core.core(x.unsqueeze(0), hidden.unsqueeze(0))
        core = core.squeeze(0)
        logits = self.action_parameterization.distribution_linear(core)
        values = self.critic_linear(core).squeeze(-1)
        return logits, following.squeeze(0), values, normalized


def validate_config(cfg):
    expected = {"env": "doom_predict_position", "algo": "APPO", "use_sound": False,
                "use_auto_aim_support": False, "use_sonic_aim_support": False,
                "encoder_conv_architecture": "convnet_simple", "encoder_conv_mlp_layers": [512],
                "use_rnn": True, "rnn_type": "gru", "rnn_size": 512, "rnn_num_layers": 1,
                "decoder_mlp_layers": [], "nonlinearity": "elu", "actor_critic_share_weights": True,
                "normalize_input": True, "normalize_input_keys": None, "normalize_returns": True,
                "obs_subtract_mean": 0.0, "obs_scale": 255.0, "pixel_format": "CHW",
                "res_w": 128, "res_h": 72, "wide_aspect_ratio": False,
                "env_frameskip": 4, "env_framestack": 1, "git_hash": SOURCE_COMMIT}
    for key, value in expected.items():
        if cfg.get(key) != value:
            raise ValueError(f"Unsupported expert configuration: {key}={cfg.get(key)!r}")


class SonicVisionPolicy:
    def __init__(self, checkpoint, cfg_path, device="cpu"):
        torch.set_num_threads(1)
        cfg = json.loads(Path(cfg_path).read_text())
        validate_config(cfg)
        observed_sha = file_sha(checkpoint)
        if observed_sha != CHECKPOINT_SHA256:
            raise ValueError("Checkpoint SHA256 differs from the frozen expert")
        core = getattr(np, "_core", None)
        if core is None:
            core = np.core
        allowed = [(core.multiarray.scalar, "numpy.core.multiarray.scalar"),
                   np.dtype, type(np.dtype(np.float64))]
        with torch.serialization.safe_globals(allowed):
            payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("model"), dict):
            raise ValueError("Expected model state dictionary")
        state = payload["model"]
        model = VisionActor()
        template = model.state_dict()
        if set(state) != set(template):
            raise ValueError("Checkpoint key set mismatch")
        for key, value in state.items():
            if not isinstance(value, torch.Tensor) or value.shape != template[key].shape or value.dtype != template[key].dtype:
                raise ValueError(f"Checkpoint tensor contract mismatch: {key}")
            if not torch.isfinite(value).all():
                raise ValueError(f"Nonfinite checkpoint tensor: {key}")
        model.load_state_dict(state, strict=True)
        for key, value in model.state_dict().items():
            if not torch.equal(value, state[key]):
                raise ValueError(f"Loaded tensor changed: {key}")
        self.device = torch.device(device)
        self.model = model.to(self.device).eval().requires_grad_(False)
        self.hidden = None
        self.forward_count = self.reset_count = 0
        self.identity = {"engine": "sonic_doom_pure_vision_pp", "checkpoint_sha256": observed_sha,
                         "config_sha256": file_sha(cfg_path), "source_commit": SOURCE_COMMIT,
                         "adapter_sha256": file_sha(__file__), "weights_only": True,
                         "numeric_allowlist": ["numpy.core.multiarray.scalar", "numpy.dtype", "numpy.float64_dtype"],
                         "strict_state_load": True, "state_tensors": len(state),
                         "parameter_count": sum(v.numel() for v in model.parameters()),
                         "train_step": int(payload["train_step"]), "env_steps": int(payload["env_steps"]),
                         "reported_training_reward": float(payload["best_performance"]),
                         "action_order": list(ACTIONS), "device": str(self.device),
                         "precision": "float32", "rnn": "GRU 512, zero state per episode",
                         "input": "uint8 RGB HWC 120x160 -> nearest 72x128 -> CHW -> /255 -> saved RMS",
                         "sound_encoder": False, "aim_assistance": False,
                         "raw_state_tensor_sha256": {k: tensor_sha(v) for k, v in state.items()}}

    def reset(self):
        self.hidden = torch.zeros((1, 512), dtype=torch.float32, device=self.device)
        self.reset_count += 1

    def predict(self, frame_hwc_uint8_160x120):
        frame = frame_hwc_uint8_160x120
        if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.shape != (120, 160, 3):
            raise ValueError("Expected uint8 RGB pixels with HWC shape (120,160,3)")
        if self.hidden is None:
            raise RuntimeError("Call reset() at the beginning of each episode")
        resized = resize_nearest(frame)
        chw = np.ascontiguousarray(resized.transpose(2, 0, 1))
        pixels = torch.from_numpy(chw).unsqueeze(0).to(self.device)
        before = tensor_sha(self.hidden)
        with torch.inference_mode():
            logits, following, values, normalized = self.model(pixels, self.hidden)
            probabilities = torch.softmax(logits, dim=-1)
            if any(not torch.isfinite(t).all() for t in (logits, following, values, probabilities)):
                raise ValueError("Nonfinite inference output")
            self.hidden = following.detach().clone()
        self.forward_count += 1
        raw = probabilities[0].cpu().tolist()
        total = math.fsum(raw)
        return {"probabilities": dict(zip(ACTIONS, (v / total for v in raw))),
                "raw_probabilities": dict(zip(ACTIONS, raw)),
                "raw_probability_sum": total,
                "logits": dict(zip(ACTIONS, logits[0].cpu().tolist())),
                "value_normalized": float(values[0]),
                "pixel_sha256": hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest(),
                "resized_chw_sha256": hashlib.sha256(chw.tobytes()).hexdigest(),
                "normalized_input_sha256": tensor_sha(normalized),
                "rnn_before_sha256": before, "rnn_after_sha256": tensor_sha(self.hidden),
                "forward_count": self.forward_count}


def self_check(policy):
    """Finite outputs, reset reproducibility and an independent functional GRU check."""
    generator = np.random.default_rng(20260920)
    frame = generator.integers(0, 256, (120, 160, 3), dtype=np.uint8)
    policy.reset()
    first = policy.predict(frame)
    policy.predict(frame)
    policy.reset()
    repeated = policy.predict(frame)
    assert first["logits"] == repeated["logits"]
    state = policy.model.state_dict()
    torch.manual_seed(17)
    pixels = torch.randint(0, 256, (3, 3, 72, 128), dtype=torch.uint8, device=policy.device)
    hidden = torch.randn(3, 512, device=policy.device)
    with torch.inference_mode():
        actual, following, _, norm = policy.model(pixels, hidden)
        x = norm
        prefix = "encoder.basic_encoder.enc."
        for i, stride in ((0, 4), (2, 2), (4, 2)):
            key = prefix + f"conv_head.{i}."
            x = F.elu(F.conv2d(x, state[key+"weight"], state[key+"bias"], stride=stride))
        x = F.elu(F.linear(x.flatten(1), state[prefix+"mlp_layers.0.weight"], state[prefix+"mlp_layers.0.bias"]))
        gi = F.linear(x, state["core.core.weight_ih_l0"], state["core.core.bias_ih_l0"])
        gh = F.linear(hidden, state["core.core.weight_hh_l0"], state["core.core.bias_hh_l0"])
        ir, iz, inn = gi.chunk(3, 1)
        hr, hz, hn = gh.chunk(3, 1)
        reset, update = torch.sigmoid(ir + hr), torch.sigmoid(iz + hz)
        candidate = torch.tanh(inn + reset * hn)
        expected_h = (1 - update) * candidate + update * hidden
        expected = F.linear(expected_h, state["action_parameterization.distribution_linear.weight"], state["action_parameterization.distribution_linear.bias"])
        hidden_delta = float((following - expected_h).abs().max())
        logits_delta = float((actual - expected).abs().max())
        assert hidden_delta < 3e-6 and logits_delta < 3e-5
    return {"passed": True, "reset_reproducible": True, "functional_gru_max_hidden_delta": hidden_delta,
            "functional_path_max_logit_delta": logits_delta, "identity": policy.identity,
            "random_frame_prediction": first, "scope": "CPU/model structure check; not gameplay performance"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    report = self_check(SonicVisionPolicy(args.checkpoint, args.config))
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("identity", "random_frame_prediction")}, indent=2))
