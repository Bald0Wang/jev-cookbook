"""Proper scoring objectives for parallel categorical decisions.

The sampled objective is our explicit RLCD research candidate, not a disclosed
TypeSafe training recipe. Sampling uses independent draws with replacement.
"""
import math


def _validate(logits, outcome):
    import torch
    if logits.ndim != 1 or logits.numel() < 2 or not logits.is_floating_point():
        raise ValueError("Expected one complete question with at least two logits")
    if not torch.isfinite(logits).all():
        raise ValueError("Logits must be finite; exclude padded candidates")
    if isinstance(outcome, bool) or not isinstance(outcome, int) or not 0 <= outcome < logits.numel():
        raise ValueError("Outcome must be an offered candidate index")


def brier_loss(logits, outcome):
    """Multiclass Brier; the binary value is twice scalar Bernoulli Brier."""
    import torch
    _validate(logits, outcome)
    p = logits.softmax(-1)
    target = torch.zeros_like(p)
    target[outcome] = 1
    return (p - target).square().sum()


def paired_brier_policy_loss(logits, outcome, samples=32, generator=None, baseline=True):
    """Unbiased score-function gradient of negative expected proper reward.

    R = 2/M sum_i 1[A_i=Y] - sum_{i!=j} 1[A_i=A_j]/(M*(M-1)).
    E[R] = 2*p.q - ||p||^2. The action-conditional local rewards keep all
    terms involving A_i; terms independent of A_i have zero expected gradient.
    The detached conditional baseline depends on the other M-1 samples only.
    There is no group standard-deviation normalization, clipping or entropy
    bonus. The returned loss is a gradient surrogate, not a reported score.
    """
    import torch
    _validate(logits, outcome)
    if type(samples) is not int or samples < 2:
        raise ValueError("samples must be an integer >= 2")
    logp = logits.log_softmax(-1)
    p = logp.detach().exp()
    actions = torch.multinomial(p, samples, replacement=True, generator=generator)
    counts = torch.bincount(actions, minlength=logits.numel()).to(logits.dtype)
    hit = (actions == outcome).to(logits.dtype)
    coefficient = 2.0 / (samples * (samples - 1))
    local_reward = (2.0 / samples) * hit - coefficient * (counts[actions] - 1)
    if baseline:
        other_probability_sum = p[actions].sum() - p[actions]
        control = (2.0 / samples) * p[outcome] - coefficient * other_probability_sum
        advantage = local_reward - control
    else:
        advantage = local_reward
    loss = -(advantage.detach() * logp[actions]).sum()
    reward = 2 * hit.mean() - (counts * (counts - 1)).sum() / (samples * (samples - 1))
    return loss, {"reward": float(reward.detach()), "samples": samples,
                  "baseline": bool(baseline), "outcome": outcome,
                  "independent_sampling_with_replacement": True}


def grouped_calibrated_loss(logits, examples, objective, loss_kind, samples=32, generator=None):
    """Equal weight per complete question; all padded logits are excluded."""
    import torch
    from train_pipeline_decisions import target_for
    if loss_kind not in {"ce", "brier", "paired_brier_pg"}:
        raise ValueError("Unknown calibrated loss")
    if loss_kind == "paired_brier_pg" and objective != "observed_outcome":
        raise ValueError("The sampled reward requires observed outcomes, not a policy or API target")
    losses = []
    for values, example in zip(logits, examples):
        z = values[:len(example["candidate_ids"])].float()
        target = target_for(example, objective)
        if target is None:
            raise ValueError("Missing eligible target")
        if loss_kind == "paired_brier_pg":
            loss, _ = paired_brier_policy_loss(z, example["gold_index"], samples, generator)
        else:
            t = torch.tensor(target, dtype=z.dtype, device=z.device)
            if not torch.isfinite(z).all() or not torch.isfinite(t).all():
                raise ValueError("Nonfinite probabilities or logits")
            loss = -(t * z.log_softmax(-1)).sum() if loss_kind == "ce" else (z.softmax(-1) - t).square().sum()
        losses.append(loss)
    return torch.stack(losses)
