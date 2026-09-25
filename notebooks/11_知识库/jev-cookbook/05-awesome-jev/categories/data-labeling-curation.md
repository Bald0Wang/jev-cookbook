# Data Labeling & Curation

Use this category for programs where Jev annotates, filters, deduplicates, or triages data at scale, replacing slower or costlier human and LLM labeling steps.

## Submission format

```md
- [Name](URL) - Industry: one-sentence description of the Jev use case.
```

## Entries

- [jev-align (Sutro)](https://github.com/sutro-sh/jev-align) - Dataset engineering: evaluates CSV, Parquet, and JSONL rows with Jev `Choice`, `Score`, or `Boolean` decisions, sends ambiguous and audit samples to a human, and uses accepted human labels to optimize the saved definition with GEPA.
- [jev-curate](https://github.com/AkashPriyadarshii/jev-curate) - Dataset engineering: sifts synthetic JSONL and Parquet rows using Jev Noul checks and calibrated confidence scores, streaming passed records and rejections straight to disk.
- [typeful-triage](https://github.com/cephalization/jev-triage) - Open-source maintenance: multiplayer triage dashboard where Jev answers a fixed set of typed questions per issue — kind, severity, urgency, duplicate, and next step — and every human correction is kept and shown back to the model on later runs.
- [jlink](https://github.com/keltokhy/jlink) - Research data: links records under a plain-English match rule using Jev Noul pair judgments, with local candidate blocking and match resolution.
- [jgrep](https://github.com/keltokhy/jgrep) - Data filtering: filters text, structured records, functions, and diff hunks against plain-English descriptions using Jev Noul judgments.
