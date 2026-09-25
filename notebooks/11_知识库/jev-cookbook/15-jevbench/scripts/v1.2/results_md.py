"""RESULTS-v1.2.md from results/v1.2/jevbench-v1.2-results.json.   python3 scripts/v1.2/results_md.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = json.loads((ROOT / "results/v1.2/jevbench-v1.2-results.json").read_text())
S = R["systems"]
ranked = [s for s in S if s["ranked"]]
honorable = [s for s in S if s.get("listing") == "honorable_mention"]
partial = [s for s in S if s["partial"]]
HM = R.get("honorable_mentions") or {"heading": "Honorable mentions", "rule": "", "systems": {}}
f1 = lambda v: "—" if v is None else f"{v:.1f}"
pct = lambda v: "—" if v is None else f"{100 * v:.1f} %"
sec = lambda v: "—" if v is None else f"{v:.2f} s"
SHORT = {
    "jev-1.13.0": "Jev 1.13.0", "gpt-5.6-luna": "GPT-5.6 Luna (low)", "deepseek-flash": "DeepSeek V4.1 Flash",
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite", "needle-3": "Needle 3", "needle-3-tools": "Needle 3, options as tools",
    "qwen3.8-27b": "Qwen3.8 27B", "semif-qwen3.5-4b": "SemIf (Qwen3.5-4B)", "openjev-razorback16": "OpenJev razorback16 (DiffusionGemma 26B)",
    "system-one-sg": "system-one (Qwen3-8B, Goedecke)", "nimble-9b": "Bespoke Nimble 9B", "open-alternative-jev": "open-alternative-jev (Qwen3.5-4B, IkerMoel)",
    "djev": "djev (Maisa, diffusion-gemma)",
    "laya": "Laya (421M)", "jeff": "jeff (GLiFormer 400M)", "gliner2": "GLiNER2 (gliner2.5-base)",
    "openjev-verdict": "openJev Verdict (151M)", "classifier-dev-fast": "classifier.dev (fast tier)",
    "programasweights": "ProgramAsWeights (Qwen3-0.6B)",
}
name = lambda s: SHORT.get(s["key"], s["display"])
TOP_PATH = ROOT / "results/v1.2/jevbench-v1.2-topics.json"
TOP = json.loads(TOP_PATH.read_text()) if TOP_PATH.exists() else None


def topic_table():
    if not TOP:
        return ""
    ks = [t["key"] for t in TOP["topics"]]
    head = "| System | " + " | ".join(f'{t["label"]} ({TOP["n_items"][t["key"]]})' for t in TOP["topics"]) + " |"
    rows = []
    for s in ranked + honorable + partial:
        tp = TOP["systems"][s["key"]]["topics"]
        cell = lambda a: "—" if a["accuracy"] is None else f'{100 * a["accuracy"]:.1f} %' + ("" if a["attempted"] >= TOP["min_attempted"] else f' (n={a["attempted"]}, too few)')
        rows.append(f"| {name(s)}{'' if s['ranked'] else (' (partial)' if s['partial'] else ' (honorable mention)')} | " + " | ".join(cell(tp[k]) for k in ks) + " |")
    return ("\n## Accuracy by subject topic\n\n" + TOP["note"] + " How the topics were assigned: [`datasets/TOPICS.md`](datasets/TOPICS.md).\n\n"
            + head + "\n|---|" + "---|" * len(ks) + "\n" + "\n".join(rows) + "\n")


LIMITS = """
## Limitations

- **The latency adjustment (×2, +0.15 s) is an assumption, not a measurement.** We ran self-hosted and demo endpoints one request at a time (parallelism 1, no other load), so their latency is likely better than the same model on a busy production server; the official Jev API presumably runs under high load, given the public interest. Serving under load trades per-user speed for throughput: in the NVIDIA chart shown by [SemiAnalysis](https://newsletter.semianalysis.com/p/nvidia-blackwell-perf-tco-analysis), moving to the throughput-maximising setting cuts per-user tokens/s by far more than 2×. That chart is a 1.8T MoE on GPU clusters, not a 4B model on one GPU, so it supports the direction and size of the effect, not our exact factor. The +0.15 s stands for infrastructure our self-hosted tests lacked: authentication, load balancing, logging, billing, API gateway. Raw p50/p95 are in the tier table above and in the artifact; a measurement under load is planned.
- 534 decisions is a pilot, not a census, and it is English-only. Held-out decisions are sent to the evaluated services to get predictions: not public is not the same as not seen.
- Latency is one origin (a server in Germany) at one time of day; production APIs, public demos, our GPU and a local CPU are different kinds of latency.
- Estimated costs describe what a large inference provider would charge for a model of that size, not what the author pays.
"""


def usd(s):
    v, kind = s["cost"]["usd_per_1000"], s["cost"]["kind"]
    return f"${v:.4f}" + {"estimate": " est.", "announced": " (announced price, free preview)"}.get(kind, "")


def table(rows, ranked_rows=True):
    out = ["| # | System | **JevBench Score** | Intelligence | Calibration | Speed | Cost | $ per 1,000 decisions | p50 raw → adjusted | Endpoint |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for s in rows:
        a, sp = s["axes"], s["speed"]
        lat = sec(sp["p50_s_raw"]) + ("" if sp["p50_s_adjusted"] == sp["p50_s_raw"] else f" → {sec(sp['p50_s_adjusted'])}")
        tag = " (partial run)" if s["partial"] else ""
        out.append(f"| {s['rank'] or ''} | {name(s)}{tag} | **{f1(s['jevbench_score'])}** | {f1(a['intelligence'])} | "
                   f"{f1(a['calibration']) if a['calibration'] is not None else 'none (label only)'} | {f1(a['speed'])} | {f1(a['cost'])} | {usd(s)} | {lat} | {s['endpoint_condition']} |")
    return "\n".join(out)


def honorable_section():
    if not honorable:
        return ""
    out = [f"\n## {HM['heading']}\n", HM["rule"] + "\n", table(honorable), ""]
    for row in honorable:
        d = HM["systems"][row["key"]]
        out += [f"### {name(row)} — runs on {d['runs_on']}\n",
                d["why_not_ranked"] + "\n",
                "**" + d["tier_measured"] + "**\n",
                "*Price.* " + d["price_note"] + "\n",
                "*Not a pass-through.* " + d["not_pass_through"] + "\n",
                d["credit"] + " Sources, read " + d["sources_read"] + ": "
                + ", ".join(f"<{u}>" for u in d["sources"]) + "\n"]
    return "\n".join(out)


presets = list(R["presets"])
jev = next(s for s in ranked if s["key"] == "jev-1.13.0")
second = ranked[1]
lead = (f"{name(ranked[0])} is #1 with {f1(ranked[0]['jevbench_score'])}; {name(second)} is #2, "
        f"{f1(round(ranked[0]['jevbench_score'], 1) - round(second['jevbench_score'], 1))} points behind (difference of the rounded scores)."
        + ("" if ranked[0] is jev else f" {name(jev)} is #{jev['rank']} with {f1(jev['jevbench_score'])}."))
footnotes = "\n\n".join(f"Footnote — {name(next(x for x in S if x['key'] == k))}: {v}" for k, v in R["footnotes"].items() if k != "open-alternative-jev")
log = "\n".join(f"- **{e['revision']}** ({e['date']}): {e['note']}" for e in R.get("revision_log", []))
md = f"""# JevBench {R['revision']} — results

**JevBench Score** = {R['score_one_liner']}

Artifact: [`results/v1.2/jevbench-v1.2-results.json`](results/v1.2/jevbench-v1.2-results.json) · scoring code:
[`jevbench/composite_v12.py`](jevbench/composite_v12.py) · built by [`scripts/v1.2/finalize.py`](scripts/v1.2/finalize.py) from the
v1.2-wip measurements (tag `v1.2-wip`; no measurement changed; later revisions add systems measured on the same frozen items, see the revision log) · interactive page: [benchmarkheaven.com/jev-models](https://benchmarkheaven.com/jev-models)

![JevBench Score](results/v1.2/charts/main-score.png)

> **Speed note.** {R['speed_note']}

## Ranking

{table(ranked)}

{lead}
""" + honorable_section() + """

**Partial runs** — shown, not ranked (a tier attempted for fewer than 95 % of its decisions):

""" + table(partial, False) + f"""

{footnotes}

Footnote — open-alternative-jev: {R['footnotes']['open-alternative-jev']} The ranked row uses the author's own order
(`A. yes, B. no`, as his `yes_no()` helper builds it); the reversed-order run was our adapter's mistake and is kept only as raw
files (`results/v1.2/wip/`, GPU round runs).

## How the score works

| Axis | Definition |
|---|---|
| **Intelligence** | {R['scoring']['intelligence']} |
| **Calibration** | {R['scoring']['calibration']} |
| **Speed** | {R['scoring']['speed']} |
| **Cost** | {R['scoring']['cost']} |
| **JevBench Score** | {R['scoring']['jevbench_score']} |

![The four axes](results/v1.2/charts/axes.png)

## Other views (not the JevBench Score)

{R['scoring']['presets']} Weights are Intelligence : Calibration : Speed : Cost.

| System | """ + " | ".join(f"{p} ({':'.join(str(round(100 * w)) for w in R['presets'][p].values())})" for p in presets) + " |\n|---|" + "---|" * len(presets) + "\n" + "\n".join(
    f"| {name(s)} | " + " | ".join(f"#{s['rank_under'][p]} {f1(s['presets'][p])}" for p in presets) + " |" for s in ranked) + f"""

## Hard tier

![Hard tier accuracy](results/v1.2/charts/hard-tier.png)
![Hard tier by family](results/v1.2/charts/hard-families.png)
![Calibration](results/v1.2/charts/calibration.png)

{R['scoring']['hard_tier']}

## Tier accuracies and raw latency

| System | easy | standard | judge | hard | p50 raw | p95 raw | hard-tier p50 | Adjustment |
|---|---|---|---|---|---|---|---|---|
""" + "\n".join(f"| {name(s)} | {pct(s['tiers']['easy'])} | {pct(s['tiers']['standard'])} | {pct(s['tiers']['judge'])} | {pct(s['tiers']['hard'])} | "
                 f"{sec(s['speed']['p50_s_raw'])} | {sec(s['speed']['p95_s_raw'])} | {sec(s['speed']['hard_tier_p50_s'])} | {s['speed']['adjustment']} |" for s in S) + """

## Cost basis

**The Cost column is US dollars per 1,000 DECISIONS, not per 1,000 tokens.** One decision is a whole question: its state,
its rubric and its options — hundreds to thousands of input tokens. """ + R["cost_unit"]["worked_example"] + """

""" + "\n".join(f"- **{name(s)}** — {usd(s)}: {s['cost']['basis']}" for s in S) + """
""" + topic_table() + LIMITS + """
## Revision log

""" + log + """

## What changed from v1.2-wip

- Score: four axes (Intelligence, Calibration, Speed, Cost), 25 % each, geometric mean — replaces the Balanced 33:33:33 arithmetic Main Score.
- Intelligence weights hard 30 % (was 50 %); the rest 1 : 2 : 2 over easy : standard : judge.
- Speed scale 20 points per 10× (was 50); Cost scale 30 points per 10× from $0.001 (was 25). Latency of non-production endpoints adjusted (assumption, see the speed note).
- One open-alternative-jev row (author's option order), named plainly; the reversed-order run is a footnote.
- Needle 3 options-as-tools priced on Needle 3's per-token basis ($0.0162 est.; it had no price).
- Qwen3.8 27B on Chutes is treated as a production API (no latency adjustment).

## Cost correction in v1.2.3 (20 September 2026)

Every price on this page was recomputed so that each of the 534 decisions is counted exactly once, and priced exactly
once. No tariff, no measurement, no item, no answer and no rank changed. What was wrong:

""" + "\n".join(f"{i}. {w}" for i, w in enumerate(R["cost_correction"]["what_was_wrong"], 1)) + """

Almost every affected row had been published as slightly **more** expensive than it is: those prices move down by 1.5 %
to 11 % and their JevBench Scores up by at most 0.2 points. DeepSeek V4.1 Flash moves the other way (+2.6 %, score
58.1 → 57.8) because its unparseable-but-billed requests are now priced. No rank changed. Row-by-row figures and
their derivation: [`results/v1.2/cost-correction-v1.2.3.json`](results/v1.2/cost-correction-v1.2.3.json).

| System | published before | corrected | change |
|---|---|---|---|
""" + "\n".join(f"| {name(s)} | ${R['cost_correction_table'][s['key']]['old']:.4f} | ${R['cost_correction_table'][s['key']]['new']:.4f} | "
    f"{R['cost_correction_table'][s['key']]['pct']:+.2f} % |" for s in S if s['key'] in R['cost_correction_table'] and not R['cost_correction_table'][s['key']]['unchanged']) + """
"""
(ROOT / "RESULTS-v1.2.md").write_text(md)
print("RESULTS-v1.2.md written")
