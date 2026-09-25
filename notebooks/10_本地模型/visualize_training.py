#!/usr/bin/env python3
"""Create a self-contained HTML training report from experiment.json."""

import argparse
import html
import json
from pathlib import Path


def line_chart(title, series, *, percent=False, width=900, height=340):
    left, right, top, bottom = 70, 30, 54, 54
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [value for _, _, points in series for _, value in points]
    if not values:
        return "<section><h2>%s</h2><p>没有可绘制的数据。</p></section>" % html.escape(title)
    if percent:
        y_min, y_max = 0.0, 1.0
        ticks = [0, .25, .5, .75, 1]
    else:
        y_min, y_max = min(values), max(values)
        spread = max(y_max - y_min, .05)
        y_min = max(0.0, y_min - spread * .12)
        y_max += spread * .12
        ticks = [y_min + (y_max - y_min) * i / 4 for i in range(5)]
    x_values = [x for _, _, points in series for x, _ in points]
    x_min, x_max = min(x_values), max(x_values)
    if x_min == x_max:
        x_max = x_min + 1

    def x_pos(x):
        return left + (x - x_min) / (x_max - x_min) * plot_w

    def y_pos(y):
        return top + (y_max - y) / (y_max - y_min) * plot_h

    pieces = [
        '<section class="chart"><h2>%s</h2><svg viewBox="0 0 %d %d" role="img" aria-label="%s">'
        % (html.escape(title), width, height, html.escape(title))
    ]
    for tick in ticks:
        y = y_pos(tick)
        label = ("%d%%" % round(tick * 100)) if percent else ("%.3f" % tick)
        pieces.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="grid" />' % (left, y, width - right, y))
        pieces.append('<text x="%d" y="%.1f" text-anchor="end" class="axis">%s</text>' % (left - 10, y + 4, label))
    for x in sorted(set(x_values)):
        xpos = x_pos(x)
        pieces.append('<text x="%.1f" y="%d" text-anchor="middle" class="axis">%s</text>' % (xpos, height - 24, "基座" if x == 0 else str(int(x))))
    pieces.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="axis-line" />' % (left, top, left, height - bottom))
    pieces.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="axis-line" />' % (left, height - bottom, width - right, height - bottom))
    for name, color, points in series:
        if not points:
            continue
        path = " ".join(("M" if i == 0 else "L") + " %.1f %.1f" % (x_pos(x), y_pos(y)) for i, (x, y) in enumerate(points))
        pieces.append('<path d="%s" fill="none" stroke="%s" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />' % (path, color))
        for x, y in points:
            pieces.append('<circle cx="%.1f" cy="%.1f" r="4" fill="%s" />' % (x_pos(x), y_pos(y), color))
    legend_x = left
    for name, color, _ in series:
        pieces.append('<circle cx="%.1f" cy="24" r="5" fill="%s" /><text x="%.1f" y="29" class="legend">%s</text>' % (legend_x, color, legend_x + 11, html.escape(name)))
        legend_x += 155
    pieces.append("</svg></section>")
    return "".join(pieces)


def bar_chart(title, before, after, width=900, height=300):
    names = [name for name in ("choice", "noul", "score") if name in before or name in after]
    if not names:
        return ""
    left, right, top, bottom = 70, 30, 48, 50
    plot_w, plot_h = width - left - right, height - top - bottom
    group_w = plot_w / len(names)
    bar_w = min(46, group_w * .25)
    pieces = ['<section class="chart"><h2>%s</h2><svg viewBox="0 0 %d %d" role="img" aria-label="%s">' % (html.escape(title), width, height, html.escape(title))]
    for tick in (0, .25, .5, .75, 1):
        y = top + (1 - tick) * plot_h
        pieces.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="grid" /><text x="%d" y="%.1f" text-anchor="end" class="axis">%d%%</text>' % (left, y, width - right, y, left - 10, y + 4, round(tick * 100)))
    for i, name in enumerate(names):
        center = left + group_w * (i + .5)
        for offset, value, color in ((-bar_w * .55, before.get(name), "#8b98a7"), (bar_w * .55, after.get(name), "#2478d4")):
            if value is None:
                continue
            value = max(0.0, min(1.0, float(value)))
            y = top + (1 - value) * plot_h
            pieces.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="5" fill="%s" />' % (center + offset - bar_w / 2, y, bar_w, max(0, top + plot_h - y), color))
            pieces.append('<text x="%.1f" y="%.1f" text-anchor="middle" class="bar-label">%d%%</text>' % (center + offset, max(top + 12, y - 7), round(value * 100)))
        pieces.append('<text x="%.1f" y="%d" text-anchor="middle" class="axis">%s</text>' % (center, height - 22, html.escape(name)))
    pieces.append('<rect x="%d" y="20" width="12" height="12" rx="3" fill="#8b98a7" /><text x="%d" y="31" class="legend">微调前</text>' % (left, left + 18))
    pieces.append('<rect x="%d" y="20" width="12" height="12" rx="3" fill="#2478d4" /><text x="%d" y="31" class="legend">微调后</text>' % (left + 110, left + 128))
    pieces.append("</svg></section>")
    return "".join(pieces)


def build_report(report):
    history = report.get("history", [])
    baseline = report.get("dev_before", {})
    final = report.get("dev_after", {})
    loss_series = [
        ("训练损失", "#18a58a", [(item["epoch"], item["train_loss"]) for item in history]),
        ("Dev 交叉熵", "#2478d4", [(0, baseline["soft_cross_entropy"])] + [
            (item["epoch"], item["dev"]["soft_cross_entropy"]) for item in history
        ]),
    ]
    accuracy_series = [("Dev 准确率", "#7757c7", [(0, baseline.get("argmax_accuracy", 0))] + [
        (item["epoch"], item["dev"]["argmax_accuracy"]) for item in history
    ])]
    before_by_type = baseline.get("by_qtype_accuracy", {})
    after_by_type = final.get("by_qtype_accuracy", {})
    ce_before = baseline.get("soft_cross_entropy", 0)
    ce_after = final.get("soft_cross_entropy", 0)
    acc_before = baseline.get("argmax_accuracy", 0)
    acc_after = final.get("argmax_accuracy", 0)
    delta_ce = (ce_after - ce_before) / ce_before * 100 if ce_before else 0
    delta_acc = (acc_after - acc_before) * 100
    review = report.get("review_status_counts", {})
    review_text = ", ".join("%s: %s" % (k, v) for k, v in sorted(review.items())) or "未记录"
    cards = [
        ("GPU", report.get("gpu", "未知")),
        ("训练 / Dev 组", "%s / %s" % (report.get("train_groups", "—"), report.get("dev_groups", "—"))),
        ("Dev 交叉熵", "%.4f → %.4f (%+.1f%%)" % (ce_before, ce_after, delta_ce)),
        ("Dev 准确率", "%.1f%% → %.1f%% (%+.1f pp)" % (acc_before * 100, acc_after * 100, delta_acc)),
        ("峰值显存 / 时间", "%s GiB / %s s" % (report.get("peak_vram_gib", "—"), report.get("training_seconds", "—"))),
        ("审核状态", review_text),
    ]
    card_html = "".join('<div class="card"><span>%s</span><strong>%s</strong></div>' % (html.escape(str(k)), html.escape(str(v))) for k, v in cards)
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Laya 微调效果报告</title><style>
:root{color-scheme:light;--ink:#172432;--muted:#657487;--line:#dce3eb;--paper:#f3f6fa;--white:#fff;--blue:#2478d4}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}
main{max-width:1100px;margin:36px auto;padding:0 22px 48px}header{padding:26px 30px;background:linear-gradient(125deg,#132d4e,#236aab);color:#fff;border-radius:18px;margin-bottom:18px}
h1{margin:0 0 6px;font-size:28px}header p{margin:0;color:#dcecff}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:16px 0}
.card,.chart,.note{background:var(--white);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:0 4px 16px #1e35520a}
.card span{display:block;color:var(--muted);font-size:12px;margin-bottom:6px}.card strong{font-size:18px;overflow-wrap:anywhere}
.chart{margin:14px 0}.chart h2{font-size:17px;margin:0 0 5px}.chart svg{width:100%%;height:auto;display:block}.grid{stroke:#e7ecf2;stroke-width:1}.axis-line{stroke:#9aa8b7;stroke-width:1}.axis,.legend{fill:#637184;font:12px -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}.bar-label{fill:#26394d;font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.note{margin-top:16px;border-left:4px solid #e4a62a}.note strong{display:block;margin-bottom:5px}.note p{margin:4px 0;color:#46566a}.foot{color:var(--muted);font-size:12px;margin:18px 2px}
@media(max-width:600px){main{margin:14px auto;padding:0 12px 28px}header{padding:20px}h1{font-size:23px}.chart{padding:12px 8px}.legend,.axis{font-size:10px}}
</style></head><body><main>
<header><h1>Laya 中文微调效果</h1><p>基座与最佳 Dev checkpoint 对照 · 训练曲线 · 按题型准确率</p></header>
<section class="cards">%s</section>
%s%s%s
<section class="note"><strong>如何解读</strong><p>准确率来自有限 Dev 样本，百分点变化可能只代表少数题目；交叉熵反映概率预测误差，越低越好。</p><p>若审核状态是 assistant-reviewed pilot，数据由模型生成并经过 AI 辅助抽检，不是人工 gold。当前 Dev 与训练数据使用同一任务规范，不代表真实业务或 OOD 泛化；模型未做概率校准。</p></section>
<p class="foot">数据文件 SHA256：%s · 基座权重 SHA256：%s · 微调权重 SHA256：%s</p>
</main></body></html>""" % (
        card_html,
        line_chart("逐 epoch 损失", loss_series),
        line_chart("验证集准确率", accuracy_series, percent=True),
        bar_chart("各题型准确率：基座 vs 最佳微调", before_by_type, after_by_type),
        html.escape(str(report.get("data_sha256", "未记录"))),
        html.escape(str(report.get("base_model_sha256", "未记录"))),
        html.escape(str(report.get("tuned_model_sha256", "未记录"))),
    )


def main():
    parser = argparse.ArgumentParser(description="把 Laya experiment.json 转成可分享的自包含 HTML 图表")
    parser.add_argument("--run-dir", required=True, help="包含 experiment.json 的训练目录")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    report_path = run_dir / "experiment.json"
    with report_path.open("r", encoding="utf-8") as f:
        report = json.load(f)
    output = run_dir / "training_report.html"
    output.write_text(build_report(report), encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    main()
