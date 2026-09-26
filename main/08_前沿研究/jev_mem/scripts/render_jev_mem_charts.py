#!/usr/bin/env python3
"""Render README-ready SVG figures from the checked-in Jev-Mem run snapshot."""

import json
from html import escape
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
DATA = HERE / "figures" / "jev-mem-2026-09-25" / "snapshot.json"
OUT = DATA.parent

BG = "#F3F7F6"
INK = "#172B36"
MUTED = "#647780"
GRID = "#DCE6E3"
TEAL = "#2A9D8F"
BLUE = "#4D8DB5"
AMBER = "#E3A34B"
SLATE = "#8C9AA3"
PALE = "#EAF1EF"
ARM_COLORS = {
    "A 滑动窗口": SLATE,
    "B 全上下文": AMBER,
    "C 朴素 RAG": BLUE,
    "D Jev-Mem": TEAL,
}


def t(x, y, value, size=15, color=INK, weight=400, anchor="start", extra=""):
    return (f'<text x="{x}" y="{y}" font-family="Inter, PingFang SC, Microsoft YaHei, Arial, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}" '
            f'dominant-baseline="middle" {extra}>{escape(str(value))}</text>')


def rect(x, y, w, h, fill, rx=12, stroke="none", sw=1):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def ln(x1, y1, x2, y2, color=GRID, sw=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{d}/>'


def path(points, color, sw=3, dash=None):
    d = " ".join(("M" if i == 0 else "L") + f" {x:.1f} {y:.1f}" for i, (x, y) in enumerate(points))
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"{dash_attr}/>'


def shell(width, height, title, subtitle):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{BG}"/>',
        t(58, 52, title, 28, INK, 700),
        t(58, 88, subtitle, 14, MUTED),
    ]


def color_for_score(value):
    low = (243, 216, 209)
    high = (211, 237, 228)
    c = tuple(round(a + (b - a) * value) for a, b in zip(low, high))
    return "#" + "".join(f"{v:02X}" for v in c)


def render_short(data):
    exp = data["walkthrough_16_turn"]
    arms = exp["arms"]
    rows = list(exp["category_scores"])
    w, h = 1450, 790
    s = shell(w, h, "16 轮短对话｜记忆决策的收益落在哪类问题？",
              "中文合成对话 · 10 道题 · 同一答案模型与 judge · 分数为 0–1 语义评分")
    s.append(rect(50, 130, 1350, 540, "#FFFFFF", 18, "#E2EBE8"))
    s.append(t(92, 165, "问题类型 / 样本量", 13, MUTED, 600))
    x0, cw, gap = 365, 225, 20
    for j, arm in enumerate(arms):
        x = x0 + j * (cw + gap)
        s.append(rect(x, 145, cw, 42, "#E5F3EF" if j == 3 else PALE, 12))
        s.append(t(x + cw / 2, 166, arm, 15, TEAL if j == 3 else INK, 700, "middle"))
    row_y = [245, 333, 421, 509]
    for y, category in zip(row_y, rows):
        count = exp["category_counts"][category]
        s.append(t(92, y, category, 17, INK, 650))
        s.append(t(92, y + 24, f"{count} 题", 12, MUTED))
        for j, value in enumerate(exp["category_scores"][category]):
            x = x0 + j * (cw + gap)
            s.append(rect(x, y - 23, cw, 52, color_for_score(value), 12,
                          TEAL if j == 3 else "none", 2 if j == 3 else 1))
            s.append(t(x + cw / 2, y + 3, f"{value:.2f}", 18, INK, 700, "middle"))
    s.append(ln(90, 575, 1360, 575, GRID, 1))
    s.append(t(92, 621, "按各题型题数加权的平均分", 14, MUTED, 600))
    for j, value in enumerate(exp["aggregate_scores"]):
        x = x0 + j * (cw + gap)
        s.append(rect(x, 595, cw, 52, TEAL if j == 3 else "#EAF1EF", 12))
        s.append(t(x + cw / 2, 622, f"{value:.2f}", 20, "#FFFFFF" if j == 3 else INK, 700, "middle"))
    s.append(rect(50, 690, 1350, 58, "#E7F2EF", 14, "#D1E5DF"))
    s.append(t(76, 715, "读图", 14, TEAL, 700))
    s.append(t(140, 715, "D 相对 C 总分 +0.12；时间题从 0.00 升到 0.50。短对话里，B 全上下文仍以 0.96 最高。", 14, INK))
    s.append(t(58, 772, "单轮小样本观察；总体分由已显示的题型均分按题数加权，不能外推为通用排名。", 12, MUTED))
    s.append("</svg>")
    (OUT / "short-dialogue.svg").write_text("\n".join(s), encoding="utf-8")


def chart_panel(s, y, height, title, values, low, high, ticks, formatter, log=False):
    x_left, x_right = 170, 1320
    top, bottom = y + 64, y + height - 43
    s.append(rect(50, y, 1350, height, "#FFFFFF", 16, "#E2EBE8"))
    s.append(t(78, y + 30, title, 17, INK, 700))
    xs = [x_left + i * (x_right - x_left) / 3 for i in range(4)]

    def yy(v):
        if log:
            import math
            a, b, x = math.log10(low), math.log10(high), math.log10(v)
        else:
            a, b, x = low, high, v
        return bottom - (x - a) / (b - a) * (bottom - top)

    for tick in ticks:
        yv = yy(tick)
        s.append(ln(x_left, yv, x_right, yv, GRID, 1, "4 6"))
        s.append(t(148, yv, formatter(tick), 12, MUTED, 400, "end"))
    turns = [48, 96, 192, 384]
    for x, n in zip(xs, turns):
        s.append(ln(x, top, x, bottom, "#EEF2F0", 1, "2 6"))
        s.append(t(x, bottom + 20, str(n), 12, MUTED, 500, "middle"))
    for arm_index, (arm, series) in enumerate(values.items()):
        pts = [(x, yy(v)) for x, v in zip(xs, series)]
        s.append(path(pts, ARM_COLORS[arm], 3.2))
        for point_index, ((x, py), value) in enumerate(zip(pts, series)):
            s.append(f'<circle cx="{x:.1f}" cy="{py:.1f}" r="5.2" fill="{ARM_COLORS[arm]}" stroke="#FFFFFF" stroke-width="2"/>')
            if point_index == len(series) - 1 and arm in ("B 全上下文", "D Jev-Mem"):
                label_offset = -12 if arm_index == 1 else 16
                s.append(t(x + 12, py + label_offset, formatter(value), 11, ARM_COLORS[arm], 700))


def render_scaling(data):
    exp = data["synthetic_scaling"]
    w, h = 1450, 1050
    s = shell(w, h, "长程缩放｜全上下文的输入成本线性增长",
              "合成对话从 48 扩展到 384 轮 · 每个规模 10 道问题 · 展示同一轮 API 实测均值")
    legend_x = 520
    for i, arm in enumerate(exp["arms"]):
        x = legend_x + i * 205
        s.append(f'<circle cx="{x}" cy="126" r="5" fill="{ARM_COLORS[arm]}"/>')
        s.append(t(x + 12, 126, arm, 12, MUTED, 600))
    chart_panel(s, 155, 240, "答案质量 · 评审均分（越高越好）", exp["judge_score"], 0, 1,
                [0, .25, .5, .75, 1], lambda v: f"{v:.2f}")
    chart_panel(s, 415, 270, "输入成本 · 每题 prompt tokens（纵轴为对数刻度）", exp["prompt_tokens_per_question"], 100, 10000,
                [100, 1000, 10000], lambda v: f"{v:,.0f}" if v >= 1000 else str(int(v)), log=True)
    chart_panel(s, 705, 240, "查询延迟 · 每题端到端秒数（越低越好）", exp["latency_seconds_per_question"], .3, 1.8,
                [.5, 1.0, 1.5], lambda v: f"{v:.2f}s")
    s.append(rect(50, 965, 1350, 58, "#FFF4E7", 14, "#F0D2A8"))
    s.append(t(76, 989, "关键观察", 14, "#A7661D", 700))
    s.append(t(170, 989, "384 轮时 B/D 输入 token 为 81.5×；D 得分 0.90、B 为 0.88，但 D 查询延迟仍高于 B。", 14, INK))
    s.append(t(58, 1040, "D 建图另需一次性投入：48→384 轮对应 28.3→173.6 秒。短期收益、查询频率与延迟预算需一起权衡。", 12, MUTED))
    s.append("</svg>")
    (OUT / "scaling.svg").write_text("\n".join(s), encoding="utf-8")


def metric_card(s, x, title, unit, vals, maxval, ratio_note, fmt):
    y, width, height = 160, 415, 460
    s.append(rect(x, y, width, height, "#FFFFFF", 18, "#E2EBE8"))
    s.append(t(x + 26, y + 38, title, 19, INK, 700))
    s.append(t(x + 26, y + 66, unit, 12, MUTED))
    start, end = x + 126, x + width - 95
    bar_max = end - start
    labels = ["B 全上下文", "D Jev-Mem"]
    colors = [AMBER, TEAL]
    for i, (label, value, color) in enumerate(zip(labels, vals, colors)):
        yy = y + 174 + i * 108
        s.append(t(x + 26, yy, label, 12, MUTED, 600))
        bw = max(13, value / maxval * bar_max)
        s.append(rect(start, yy + 21, bw, 28, color, 9))
        s.append(t(x + width - 22, yy + 35, fmt(value), 17, INK, 700, "end"))
    s.append(ln(x + 26, y + 332, x + width - 26, y + 332, GRID, 1))
    s.append(t(x + 26, y + 376, ratio_note, 14, TEAL if "更多" in ratio_note or "更高" in ratio_note else INK, 700))


def render_locomo(data):
    exp = data["locomo_sample_0"]
    w, h = 1450, 770
    s = shell(w, h, "LoCoMo 样本 0｜419 轮对话中的质量与成本权衡",
              "10 道同题对照 · 约 19.8k 对话 token · 本地实测；不是论文全量评测复现")
    scores = exp["judge_score"]
    tokens = exp["prompt_tokens_per_question"]
    latencies = exp["latency_seconds_per_question"]
    metric_card(s, 60, "答案质量", "LLM-as-a-Judge 均分 · 0–1", scores, 1,
                f"Jev-Mem 高 {scores[1] - scores[0]:.2f} 分", lambda v: f"{v:.2f}")
    ratio = tokens[0] / tokens[1]
    saved = (1 - tokens[1] / tokens[0]) * 100
    metric_card(s, 518, "输入 token", "每题 prompt tokens · 越少越省", tokens, max(tokens),
                f"减少 {saved:.1f}% · 约省 {ratio:.1f} 倍 token", lambda v: f"{v:,.0f}")
    slow = latencies[1] / latencies[0]
    metric_card(s, 976, "查询延迟", "每题端到端秒数 · 越低越快", latencies, 4,
                f"Jev-Mem 查询约慢 {slow:.1f} 倍", lambda v: f"{v:.2f}s")
    s.append(rect(60, 650, 1330, 68, "#E7F2EF", 14, "#D1E5DF"))
    s.append(t(84, 674, "一次性建图", 13, TEAL, 700))
    s.append(t(84, 697, f"{exp['jev_mem_build_seconds']} 秒", 18, INK, 700))
    s.append(t(290, 685, "本次小样本显示：质量与 token 账单明显改善，但查询延迟更高，且建图需要先投入。", 14, INK))
    s.append(t(60, 746, "样本仅 10 题；Notebook 同时提示本轮 judge 的 F1 为 57.3%。将数字视为方向性观察，不外推为全 LoCoMo 结论。", 12, MUTED))
    s.append("</svg>")
    (OUT / "locomo-sample-0.svg").write_text("\n".join(s), encoding="utf-8")


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    render_short(data)
    render_scaling(data)
    render_locomo(data)
    for name in ["short-dialogue.svg", "scaling.svg", "locomo-sample-0.svg"]:
        print(OUT / name)


if __name__ == "__main__":
    main()
