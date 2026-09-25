"""JevBench v1.2 subject topics: datasets/topics.json and results/v1.2/jevbench-v1.2-topics.json.

    python3 scripts/v1.2/topics.py <private topic labels.json> <v1.2 run sources module> <additions runs dir> [<runs dir> ...]

Every one of the 534 v1.2 decisions carries one subject topic (what the item is about: math, coding, rules and law, ...),
separate from its item family (the task format: intent, extraction, long_policy, ...). Method: datasets/TOPICS.md.
Published: the topic of every PUBLIC item, and for held-out / imported items only counts per topic and tier; per system only
aggregates (n, attempted, correct, accuracy) per topic over all four tiers. Held-out item texts and ids never enter the repo.
Accuracy per topic = correct / attempted; failures count as wrong, items a partial run never attempted are left out.
The per-item outcomes come from exactly the run files the published scores came from; the script refuses to write unless
its per-tier counts equal results/v1.2/jevbench-v1.2-per-task.json for every system and every public outcome matches.
"""
import collections, importlib.util, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOPICS = [
    ("math", "Math & numbers", "a calculation decides the answer: arithmetic, word problems, probability, dates, units"),
    ("coding", "Coding & software", "code, SQL, repositories, developer tools and IT systems"),
    ("law_policy", "Rules, policy & law", "applying written rules: company policies, contracts, regulations, eligibility"),
    ("finance_commerce", "Finance & commerce", "money: payments, refunds, invoices, orders, expenses, insurance payouts"),
    ("support_ops", "Support & operations", "support tickets, incidents, logistics, scheduling desks and routing work to a team"),
    ("everyday_language", "Everyday language", "short everyday messages: intents, assistant requests, reading a detail out of a text"),
    ("safety_security", "Safety & security", "untrusted or injected instructions, fraud, moderation, access and security triage"),
]
KEYS = [k for k, _, _ in TOPICS]
MIN_N = 15


def main(labels_path, sources_path, *addition_runs):
    labels = json.loads(Path(labels_path).read_text())["labels"]
    spec = importlib.util.spec_from_file_location("sources", sources_path)
    pt = importlib.util.module_from_spec(spec); spec.loader.exec_module(pt)
    published = json.loads((ROOT / "results/v1.2/jevbench-v1.2-per-task.json").read_text())
    tasks = [(t["id"], tier, public) for tier, files in pt.TIER_FILES.items() for f, public in files for t in pt.load(pt.V11 / f)]
    assert len(tasks) == 534 and all(labels.get(i) in KEYS for i, _, _ in tasks), "every item needs one topic from the fixed list"
    counts = collections.Counter(labels[i] for i, _, _ in tasks)
    assert all(counts[k] >= MIN_N for k in KEYS), counts
    by_tier = {k: {t: 0 for t in pt.TIER_FILES} for k in KEYS}
    hidden = {k: {t: 0 for t in pt.TIER_FILES} for k in KEYS}
    for i, tier, public in tasks:
        by_tier[labels[i]][tier] += 1
        if not public:
            hidden[labels[i]][tier] += 1
    ds = {
        "benchmark": "JevBench", "revision": published.get("revision", "v1.2.1"),
        "note": "One subject topic per item (what it is about), separate from the item family (the task format). "
                "Public items are listed by id; held-out and imported items only as counts. Method: datasets/TOPICS.md.",
        "topics": [{"key": k, "label": l, "covers": c} for k, l, c in TOPICS],
        "public": {i: labels[i] for i, _, public in tasks if public},
        "heldout_or_imported_counts": hidden,
        "n_items": {k: counts[k] for k in KEYS}, "n_items_by_tier": by_tier,
    }
    systems = {}
    # rows added after v1.2 (djev in v1.2.1, the requested systems in v1.2.2+) come from their own jobs' run folders
    extra = {}
    for d in map(Path, addition_runs):
        for v1dir in d.glob("*--v1"):
            extra.setdefault(v1dir.name[: -len("--v1")], d)
    for key, pub in published["systems"].items():
        if key in extra:
            runs = extra[key]
            v1 = pt.rows(runs / f"{key}--v1")
            src = {"easy": pt.rows(runs / f"{key}--easy"), "standard": v1, "judge": v1, "hard": pt.rows(runs / f"{key}--hard")}
        else:  # the ranked open-alternative-jev row is the author's option order (see finalize.py)
            src = pt.sources("open-alternative-jev-yesfirst" if key == "open-alternative-jev" else key)
        tier_c, top = {}, {k: collections.Counter() for k in KEYS}
        for i, tier, public in tasks:
            c = pt.code(src[tier].get(i))
            tier_c.setdefault(tier, collections.Counter())[c] += 1
            top[labels[i]][c] += 1
            if public and pub["public_tasks"][i][0] != c:
                raise SystemExit(f"{key} {i}: outcome differs from the published per-task artifact")
        for tier, cnt in tier_c.items():
            if any(cnt[x] != pub["by_tier"][tier][x] for x in "cwfn"):
                raise SystemExit(f"{key} {tier}: counts differ from the published per-task artifact")
        systems[key] = {"display": pub["display"], "partial": pub["partial"], "topics": {}}
        for k in KEYS:
            n = sum(top[k].values()); att = n - top[k]["n"]
            systems[key]["topics"][k] = {"n": n, "attempted": att, "correct": top[k]["c"], "accuracy": round(top[k]["c"] / att, 4) if att else None}
    res = {
        "benchmark": "JevBench", "protocol": "jevbench::v1.2", "revision": published.get("revision", "v1.2.1"), "status": "final",
        "note": "Accuracy per subject topic over all four tiers (easy, standard, judge, hard): correct / attempted; failures count "
                "as wrong; items a partial run never attempted are left out. Aggregates only; not part of the JevBench Score. "
                f"Topics differ in their tier mix (n_items_by_tier), so compare systems within a topic, not topics with each other. "
                f"A topic with fewer than {MIN_N} attempted items for a system is too thin to read (partial runs).",
        "min_attempted": MIN_N,
        "topics": ds["topics"], "n_items": ds["n_items"], "n_items_by_tier": by_tier,
        "systems": systems,
    }
    (ROOT / "datasets/topics.json").write_text(json.dumps(ds, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "results/v1.2/jevbench-v1.2-topics.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    print("datasets/topics.json and results/v1.2/jevbench-v1.2-topics.json written;", dict(counts))


if __name__ == "__main__":
    main(*sys.argv[1:])
