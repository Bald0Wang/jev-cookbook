"""Render the curated 2026-09-26 JevBench snapshot as self-contained SVG charts.

The compact snapshot intentionally excludes raw prompts, provider responses,
ledgers, and credentials. This renderer uses only the Python standard library.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path


CHAPTER = Path(__file__).resolve().parents[2]
FIGURES = CHAPTER / "figures" / "jevbench-2026-09-26"
SNAPSHOT = FIGURES / "snapshot.json"

BG = "#F3F7F6"
CARD = "#FFFFFF"
INK = "#172B36"
MUTED = "#647780"
GRID = "#DCE6E3"
TEAL = "#2A9D8F"
TEAL_DARK = "#1E716B"
AMBER = "#E9A35B"
CORAL = "#D97767"
GRAY = "#D9E1E4"
PALE = "#EDF2F1"

FAMILY_LABELS = {
    "intent": "Intent",
    "fact": "Fact",
    "extraction": "Extraction",
    "tool_selection": "Tool selection",
    "policy": "Policy",
    "ordinal": "Ordinal score",
    "adequacy": "Answer adequacy",
    "routing": "Routing",
    "long_policy": "Long policy",
    "probability": "Probability",
    "temporal_numeric": "Temporal / numeric",
    "ambiguous": "Ambiguity",
    "multi_hop": "Multi-hop",
    "tradeoff": "Trade-off",
    "adversarial": "Adversarial",
    "trap": "Trap question",
    "judge_hard": "Hard judge",
    "routing_hard": "Hard routing",
}

MODEL_COLORS = {
    "deepseek-flash": "#2A9D8F",
    "doubao-2.1-pro": "#E5A15A",
    "glm-5.3-codeplan": "#718596",
    "jev": "#1E716B",
    "kimi-k3": "#8A78AC",
}


def text(x, y, value, size=16, color=INK, weight=400, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" font-family="Inter, Avenir, Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}" '
        f'text-anchor="{anchor}" dominant-baseline="middle">{escape(str(value))}</text>'
    )


def rect(x, y, width, height, fill, radius=0, stroke="none", stroke_width=1):
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )


def line(x1, y1, x2, y2, color=GRID, width=1, dash=None):
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{color}" stroke-width="{width}"{extra}/>'
    )


def circle(cx, cy, radius, fill, stroke="none", stroke_width=1):
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )


def start(width, height, title, subtitle):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="' + BG + '"/>',
        text(58, 54, title, 30, INK, 700),
        text(58, 91, subtitle, 15, MUTED),
    ]


def panel(parts, x, y, width, height, title, subtitle):
    parts.append(rect(x, y, width, height, CARD, 18, GRID, 1))
    parts.append(text(x + 24, y + 34, title, 20, INK, 700))
    parts.append(text(x + 24, y + 62, subtitle, 13, MUTED))


def end(parts, path):
    parts.append("</svg>")
    Path(path).write_text("\n".join(parts) + "\n", encoding="utf-8")


def axis(parts, x, y, width, ticks, maximum, suffix=""):
    for value in ticks:
        px = x + width * value / maximum
        parts.append(line(px, y - 5, px, y, GRID, 1))
        parts.append(text(px, y + 18, f"{value:g}{suffix}", 11, MUTED, anchor="middle"))


def render_dashboard(models):
    width, height = 1500, 970
    parts = start(
        width,
        height,
        "JevBench | five-provider snapshot",
        "Public task set · 231 planned tasks per provider · 26 Sep 2026 · one run each",
    )
    x1, x2, panel_w = 58, 766, 676
    y1, y2, panel_h = 132, 520, 356

    panel(parts, x1, y1, panel_w, panel_h, "Conditional accuracy", "Only scorable responses · label includes n")
    bar_x, bar_w = x1 + 208, 300
    row_y = [y1 + 117 + 39 * i for i in range(5)]
    for model, cy in zip(models, row_y):
        name = model["display_name"]
        value = model["conditional_accuracy"] or 0
        parts.append(text(x1 + 22, cy, name, 14, INK, 600))
        parts.append(rect(bar_x, cy - 8, bar_w, 16, PALE, 8))
        parts.append(rect(bar_x, cy - 8, bar_w * value, 16, TEAL, 8))
        parts.append(text(x1 + 530, cy, f"{value * 100:.1f}%  (n={model['n_valid']})", 13, INK, 600))
    axis(parts, bar_x, y1 + 326, bar_w, [0, 50, 100], 100, "%")

    panel(parts, x2, y1, panel_w, panel_h, "Task outcomes", "Counts out of 231 rows · valid / failed / not attempted")
    legend_y = y1 + 91
    for i, (label, color) in enumerate([("Valid", TEAL), ("Error / invalid", CORAL), ("Not attempted", GRAY)]):
        lx = x2 + 27 + i * 188
        parts.append(rect(lx, legend_y - 7, 14, 14, color, 4))
        parts.append(text(lx + 22, legend_y, label, 12, MUTED))
    stack_x, stack_w = x2 + 185, 300
    for model, cy in zip(models, row_y):
        counts = model["status_counts"]
        valid = counts.get("ok", 0)
        failed = counts.get("error", 0) + counts.get("invalid", 0)
        unattempted = counts.get("unattempted", 0)
        parts.append(text(x2 + 22, cy, model["display_name"], 14, INK, 600))
        parts.append(rect(stack_x, cy - 9, stack_w, 18, PALE, 8))
        wx = 0
        for count, color in [(valid, TEAL), (failed, CORAL), (unattempted, GRAY)]:
            segment = stack_w * count / model["n_tasks"]
            if segment > 0:
                parts.append(rect(stack_x + wx, cy - 9, segment, 18, color, 0))
            wx += segment
        parts.append(text(x2 + 500, cy, f"{valid} / {model['n_tasks']} valid", 12, INK, 600))
    axis(parts, stack_x, y1 + 326, stack_w, [0, 50, 100], 100, "%")

    panel(parts, x1, y2, panel_w, panel_h, "Observed latency", "Line spans p50 → p95 · attempted rows with latency")
    time_x, time_w = x1 + 208, 300
    for model, cy in zip(models, [y2 + 117 + 39 * i for i in range(5)]):
        name = model["display_name"]
        p50, p95 = model["p50_s"] or 0, model["p95_s"] or 0
        parts.append(text(x1 + 22, cy, name, 14, INK, 600))
        parts.append(line(time_x, cy, time_x + time_w, cy, PALE, 7))
        parts.append(line(time_x, cy, time_x + time_w * p95 / 16, cy, "#AABAB7", 5))
        parts.append(circle(time_x + time_w * p50 / 16, cy, 7, TEAL, CARD, 2))
        parts.append(circle(time_x + time_w * p95 / 16, cy, 5, CARD, TEAL_DARK, 2))
        parts.append(text(x1 + 530, cy, f"{p50:.2f} / {p95:.2f}s", 13, INK, 600))
    axis(parts, time_x, y2 + 326, time_w, [0, 4, 8, 12, 16], 16, "s")

    cost_models = models
    panel(parts, x2, y2, panel_w, panel_h, "Observed cost per 1,000 valid answers", "Recorded spend / valid responses × 1,000 · partial-run snapshot")
    cost_x, cost_w = x2 + 208, 300
    for model, cy in zip(cost_models, [y2 + 117 + 39 * i for i in range(5)]):
        cost = (model["observed_cost_per_valid_usd"] or 0) * 1000
        parts.append(text(x2 + 22, cy, model["display_name"], 14, INK, 600))
        parts.append(rect(cost_x, cy - 8, cost_w, 16, PALE, 8))
        parts.append(rect(cost_x, cy - 8, cost_w * min(cost / 0.42, 1), 16, TEAL, 8))
        parts.append(text(x2 + 530, cy, f"${cost:.2f}", 13, INK, 600))
    axis(parts, cost_x, y2 + 326, cost_w, [0, 0.1, 0.2, 0.3, 0.4], 0.42, "")

    parts.append(text(60, 915, "Accuracy excludes invalid / missing answers; valid rate uses all 231 tasks.", 13, MUTED))
    parts.append(text(60, 939, "Latency and cost are observed in incomplete runs, not steady-state estimates.", 13, MUTED))
    end(parts, FIGURES / "dashboard.svg")


def render_composite(models):
    width, height = 1450, 770
    ordered = sorted(models, key=lambda m: m["jevbench_score"] or 0, reverse=True)
    parts = start(
        width,
        height,
        "JevBench-style composite | uploaded summaries",
        "Four-axis formula output · values are provisional because valid-response counts differ",
    )
    x, bar_w = 330, 780
    top, gap = 205, 82
    for tick in [0, 20, 40, 60, 80, 100]:
        px = x + bar_w * tick / 100
        parts.append(line(px, top - 28, px, top + 4 * gap + 32, GRID, 1, "4 6"))
        parts.append(text(px, top - 45, str(tick), 12, MUTED, anchor="middle"))
    for i, model in enumerate(ordered):
        cy = top + i * gap
        score = model["jevbench_score"] or 0
        parts.append(text(76, cy, model["display_name"], 18, INK, 600))
        parts.append(rect(x, cy - 18, bar_w, 36, PALE, 18))
        parts.append(rect(x, cy - 18, bar_w * score / 100, 36, TEAL, 18))
        parts.append(text(x + bar_w * score / 100 + 16, cy, f"{score:.1f}", 17, TEAL_DARK, 700))
        parts.append(text(1260, cy, f"valid {model['n_valid']} / 231", 14, MUTED, 600))
    parts.append(rect(58, 650, 1334, 72, "#FFF4E7", 14, "#F0D2A8", 1))
    parts.append(text(82, 676, "Read as a snapshot diagnostic, not a final model ranking.", 15, INK, 700))
    parts.append(text(82, 703, "The source formula uses conditional accuracy and divides spend by 231 planned tasks even when many tasks were not completed.", 13, MUTED))
    end(parts, FIGURES / "composite.svg")


def heat_color(ratio):
    if ratio is None:
        return "#E8ECEB"
    stops = [(0.0, (249, 235, 231)), (0.5, (244, 215, 169)), (0.8, (150, 207, 190)), (1.0, (42, 157, 143))]
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if ratio <= b:
            t = 0 if b == a else (ratio - a) / (b - a)
            rgb = tuple(round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
            return "#%02X%02X%02X" % rgb
    return "#2A9D8F"


def render_split_coverage(models):
    width, height = 1540, 790
    parts = start(
        width,
        height,
        "Valid responses by task group",
        "Cell = valid typed responses / planned tasks in the ID-prefix group",
    )
    groups = [("easy", "Easy", 48), ("original", "Original", 72), ("hard", "Hard", 111)]
    left, top, cw, ch, gap = 340, 260, 207, 124, 16
    for col, model in enumerate(models):
        cx = left + col * (cw + gap) + cw / 2
        parts.append(text(cx, top - 59, model["display_name"], 14, INK, 700, anchor="middle"))
    for row, (key, label, total) in enumerate(groups):
        y = top + row * (ch + 20)
        parts.append(text(70, y + 37, label, 20, INK, 700))
        parts.append(text(70, y + 69, f"n = {total} tasks", 13, MUTED))
        for col, model in enumerate(models):
            x = left + col * (cw + gap)
            stats = model["split"].get(key, {})
            valid = stats.get("valid", 0)
            ratio = valid / total
            parts.append(rect(x, y, cw, ch, heat_color(ratio), 14, CARD, 2))
            parts.append(text(x + cw / 2, y + 47, f"{valid} / {total}", 22, INK, 700, anchor="middle"))
            parts.append(text(x + cw / 2, y + 82, f"{ratio * 100:.1f}% valid", 13, INK, 500, anchor="middle"))
    parts.append(rect(70, 704, 1380, 52, CARD, 12, GRID, 1))
    parts.append(text(92, 730, "Task groups are inferred from easy / original / hard ID prefixes. A missing or malformed answer is not a valid response.", 13, MUTED))
    end(parts, FIGURES / "split_coverage.svg")


def render_family_yield(models):
    width, height = 1740, 1350
    parts = start(
        width,
        height,
        "Correct-answer yield by task family",
        "Cell = correct outputs / all planned tasks in that family · errors and unattempted rows are not successes",
    )
    order = list(FAMILY_LABELS)
    left, top, cw, ch, gap = 430, 250, 235, 45, 10
    parts.append(text(86, top - 44, "Task family", 13, MUTED, 700))
    parts.append(text(354, top - 44, "N", 13, MUTED, 700, anchor="middle"))
    for col, model in enumerate(models):
        cx = left + col * (cw + gap) + cw / 2
        parts.append(text(cx, top - 44, model["display_name"], 14, INK, 700, anchor="middle"))
    for row, family in enumerate(order):
        y = top + row * (ch + 5)
        total = models[0]["family"].get(family, {}).get("total", 0)
        parts.append(text(86, y + ch / 2, FAMILY_LABELS[family], 14, INK, 500))
        parts.append(text(354, y + ch / 2, total, 13, MUTED, 600, anchor="middle"))
        for col, model in enumerate(models):
            x = left + col * (cw + gap)
            stats = model["family"].get(family, {})
            planned = stats.get("total", total)
            correct = stats.get("correct", 0)
            ratio = correct / planned if planned else None
            parts.append(rect(x, y, cw, ch, heat_color(ratio), 7, CARD, 1))
            pct = "—" if ratio is None else f"{ratio * 100:.0f}%"
            parts.append(text(x + cw / 2, y + ch / 2, f"{correct} / {planned}   {pct}", 13, INK, 600, anchor="middle"))
    legend_y = top + len(order) * (ch + 5) + 14
    parts.append(text(86, legend_y + 12, "Correct yield", 13, MUTED, 700))
    for i, (label, color) in enumerate([("0%", heat_color(0)), ("50%", heat_color(.5)), ("80%", heat_color(.8)), ("100%", heat_color(1))]):
        x = 225 + i * 150
        parts.append(rect(x, legend_y + 4, 74, 20, color, 6, GRID, 1))
        parts.append(text(x + 87, legend_y + 14, label, 12, MUTED))
    parts.append(text(86, height - 36, "This is end-to-end yield for one partial run, not isolated model accuracy. Family sample sizes range from 5 to 24.", 13, MUTED))
    end(parts, FIGURES / "family_yield.svg")


def render_failure_breakdown(models):
    width, height = 1540, 690
    parts = start(
        width,
        height,
        "Where planned tasks ended",
        "Counts from each provider's 231 task rows · one run per provider",
    )
    x, bar_w, top, gap = 330, 900, 235, 68
    colors = {
        "valid": TEAL,
        "empty_probs": CORAL,
        "other_errors": AMBER,
        "invalid": "#8A78AC",
        "unattempted": GRAY,
    }
    labels = [
        ("valid", "Valid response"),
        ("empty_probs", "Empty probs parse error"),
        ("other_errors", "Other error"),
        ("invalid", "Invalid"),
        ("unattempted", "Not attempted"),
    ]
    legend_x = [78, 340, 660, 895, 1090]
    for (key, label), lx in zip(labels, legend_x):
        parts.append(rect(lx, 165, 15, 15, colors[key], 4))
        parts.append(text(lx + 24, 173, label, 12, MUTED))

    for tick in [0, 50, 100, 150, 200, 231]:
        px = x + bar_w * tick / 231
        parts.append(line(px, top - 27, px, top + gap * 4 + 24, GRID, 1, "4 6"))
        parts.append(text(px, top - 46, tick, 12, MUTED, anchor="middle"))

    for index, model in enumerate(models):
        cy = top + index * gap
        counts = model["status_counts"]
        error_count = counts.get("error", 0)
        values = [
            counts.get("ok", 0),
            model.get("empty_probability_parse_errors", 0),
            max(0, error_count - model.get("empty_probability_parse_errors", 0)),
            counts.get("invalid", 0),
            counts.get("unattempted", 0),
        ]
        parts.append(text(78, cy, model["display_name"], 15, INK, 600))
        cursor = x
        for count, (key, _) in zip(values, labels):
            segment = bar_w * count / 231
            if segment > 0:
                parts.append(rect(cursor, cy - 16, segment, 32, colors[key], 0))
                if segment >= 42:
                    parts.append(text(cursor + segment / 2, cy, count, 12, "#FFFFFF" if key in ("valid", "empty_probs", "other_errors") else INK, 700, anchor="middle"))
                cursor += segment
        total_failed = error_count + counts.get("invalid", 0)
        parts.append(text(1255, cy, f"valid {values[0]} · failed {total_failed} · not run {values[4]}", 12, MUTED, 600))

    for tick in [0, 50, 100, 150, 200, 231]:
        px = x + bar_w * tick / 231
        parts.append(text(px, top + gap * 5 - 8, tick, 11, MUTED, anchor="middle"))
    parts.append(rect(78, 605, 1384, 46, "#FFF4E7", 12, "#F0D2A8", 1))
    parts.append(text(98, 628, "Empty-probs counts are a recorded parse-error subtype; they describe this run's output path, not the model's underlying capability.", 12, INK, 500))
    end(parts, FIGURES / "failure_breakdown.svg")


def main():
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    models = data["models"]
    render_dashboard(models)
    render_composite(models)
    render_split_coverage(models)
    render_family_yield(models)
    render_failure_breakdown(models)
    for name in ["dashboard.svg", "composite.svg", "split_coverage.svg", "family_yield.svg", "failure_breakdown.svg"]:
        print(FIGURES / name)


if __name__ == "__main__":
    main()
