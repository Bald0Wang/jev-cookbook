#!/usr/bin/env python3
"""Render raster charts for the WeChat article from the checked-in experiment snapshot."""

import json
from pathlib import Path

import matplotlib.pyplot as plt


ARTICLE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]
SNAPSHOT = REPO_ROOT / "main/08_前沿研究/jev_mem/figures/jev-mem-2026-09-25/snapshot.json"
MEDIA = ARTICLE_DIR / "media"

COLORS = {
    "A 滑动窗口": "#8C9AA3",
    "B 全上下文": "#E3A34B",
    "C 朴素 RAG": "#4D8DB5",
    "D Jev-Mem": "#2A9D8F",
}
BG = "#F3F7F6"
INK = "#172B36"
MUTED = "#647780"
GRID = "#DCE6E3"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["PingFang SC", "Arial Unicode MS", "Songti SC", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": BG,
    "axes.facecolor": "#FFFFFF",
    "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": INK,
    "text.color": INK,
    "axes.titleweight": "bold",
})


def style_axis(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.9)
    ax.set_axisbelow(True)


def render_scaling(data):
    scale = data["synthetic_scaling"]
    turns = scale["dialogue_turns"]
    arms = scale["arms"]
    fig, axes = plt.subplots(1, 3, figsize=(15.2, 5.4), constrained_layout=False)
    fig.suptitle("Jev-Mem 长程缩放：质量、输入成本与查询延迟", fontsize=20, fontweight="bold", x=0.5, y=0.98)

    panels = [
        ("judge_score", "答案质量 · 评审分", "LLM-as-a-Judge", (0, 1.05), None),
        ("prompt_tokens_per_question", "每题输入 token", "tokens（纵轴对数刻度）", None, "log"),
        ("latency_seconds_per_question", "查询延迟", "秒 / 题", None, None),
    ]
    for ax, (key, title, ylabel, ylim, yscale) in zip(axes, panels):
        style_axis(ax)
        ax.set_title(title, fontsize=14, pad=14)
        ax.set_xlabel("对话轮数", fontsize=11)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_xticks(turns, [str(n) for n in turns])
        if ylim:
            ax.set_ylim(*ylim)
        if yscale:
            ax.set_yscale(yscale)
            ax.set_ylim(70, 15000)
        if key == "latency_seconds_per_question":
            ax.set_ylim(.3, 1.85)
            ax.grid(axis="x", visible=False)
        for arm in arms:
            vals = scale[key][arm]
            ax.plot(turns, vals, marker="o", markersize=6, linewidth=2.5,
                    color=COLORS[arm], label=arm)
        if key == "judge_score":
            ax.annotate("B 0.88", (384, .88), xytext=(-12, -22), textcoords="offset points",
                        color=COLORS["B 全上下文"], fontsize=9, ha="right")
            ax.annotate("D 0.90", (384, .90), xytext=(-12, 12), textcoords="offset points",
                        color=COLORS["D Jev-Mem"], fontsize=9, ha="right")
        elif key == "prompt_tokens_per_question":
            ax.annotate("B 9,778", (384, 9778), xytext=(-8, -18), textcoords="offset points",
                        color=COLORS["B 全上下文"], fontsize=9, ha="right")
            ax.annotate("D 120", (384, 120), xytext=(-8, 12), textcoords="offset points",
                        color=COLORS["D Jev-Mem"], fontsize=9, ha="right")
        elif key == "latency_seconds_per_question":
            ax.annotate("B 0.68s", (384, .68), xytext=(-8, -18), textcoords="offset points",
                        color=COLORS["B 全上下文"], fontsize=9, ha="right")
            ax.annotate("D 1.66s", (384, 1.66), xytext=(-8, 10), textcoords="offset points",
                        color=COLORS["D Jev-Mem"], fontsize=9, ha="right")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.925), ncol=4,
               frameon=False, fontsize=10, handlelength=2.2, columnspacing=2.0)
    fig.text(.5, .045,
             "每个规模 10 题 · 384 轮时全上下文约 9,778 tokens，Jev-Mem 约 120 tokens（81.5×）· Jev-Mem 查询仍较慢",
             ha="center", va="center", fontsize=10, color=MUTED)
    fig.subplots_adjust(top=.78, bottom=.18, left=.07, right=.98, wspace=.32)
    fig.savefig(MEDIA / "chapter-08-jev-mem-scaling.png", dpi=190, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def render_locomo(data):
    exp = data["locomo_sample_0"]
    labels = exp["methods"]
    colors = ["#E3A34B", "#2A9D8F"]
    metrics = [
        ("judge_score", exp["judge_score"], "答案质量", "Judge 分数", (0, 1.12), ["0", ".5", "1.0"], lambda v: f"{v:.2f}"),
        ("tokens", exp["prompt_tokens_per_question"], "输入成本", "prompt tokens / 题", (0, 22000), None, lambda v: f"{v:,.0f}"),
        ("latency", exp["latency_seconds_per_question"], "查询延迟", "秒 / 题", (0, 4.4), None, lambda v: f"{v:.2f}s"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(14.7, 4.5), constrained_layout=False)
    fig.suptitle("LoCoMo 样本 0：质量与成本的真实取舍", fontsize=20, fontweight="bold", y=.98)
    for ax, (_, values, title, xlabel, limits, xticks, formatter) in zip(axes, metrics):
        style_axis(ax)
        ax.set_title(title, fontsize=14, pad=13)
        y = [1, 0]
        bars = ax.barh(y, values, color=colors, height=.52, edgecolor="white", linewidth=1)
        ax.set_yticks(y, labels, fontsize=10)
        ax.set_xlabel(xlabel, fontsize=10)
        ax.set_xlim(*limits)
        if xticks:
            ax.set_xticks([0, .5, 1.0], xticks)
        ax.grid(axis="x", color=GRID, linewidth=.8)
        ax.grid(axis="y", visible=False)
        for bar, value in zip(bars, values):
            ax.text(min(bar.get_width() + limits[1] * .025, limits[1] * .83), bar.get_y() + bar.get_height()/2,
                    formatter(value), va="center", ha="left", fontsize=11, fontweight="bold", color=INK)
    fig.text(.5, .105,
             f"样本 0 · {exp['dialogue_turns']} 轮 · 同题 {exp['questions']} 题 · Jev-Mem 建图 {exp['jev_mem_build_seconds']} 秒（一次性）",
             ha="center", va="center", fontsize=10, color=MUTED)
    fig.text(.5, .055,
             "Jev-Mem 得分更高、输入 token 更少；本次每题查询更慢。小样本结果不代表完整 LoCoMo 基准。",
             ha="center", va="center", fontsize=10, color=MUTED)
    fig.subplots_adjust(top=.78, bottom=.24, left=.085, right=.98, wspace=.36)
    fig.savefig(MEDIA / "chapter-08-locomo-sample-0.png", dpi=190, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def main():
    MEDIA.mkdir(parents=True, exist_ok=True)
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    render_scaling(snapshot)
    render_locomo(snapshot)
    print(f"Rendered article charts from {SNAPSHOT}")


if __name__ == "__main__":
    main()
