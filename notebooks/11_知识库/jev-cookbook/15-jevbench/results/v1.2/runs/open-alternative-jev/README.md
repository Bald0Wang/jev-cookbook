# open-alternative-jev: both option orders (raw per-decision results, public items only)

- `author-order-yes-first--*` — the ranked v1.2 row. Options listed `A. yes, B. no`, as the author's `yes_no()` helper builds them.
- `reversed-order-no-first--*` — our first adapter listed `A. no, B. yes`. Not ranked: an adapter mistake, not a model weakness.
  With the options in reverse order the same model scored 21 % instead of 72 % on answer-judging items
  (the 68 yes/no items of family `adequacy` from the imported judge set): small models are very sensitive to option order.

Only items whose text is public in `datasets/public/` are included here (easy, the 72 original standard/judge items, the 111
public hard items). Held-out and imported items are left out: their per-item predictions would reveal gold answers or
redistribute third-party items. Aggregates over all items are in `results/v1.2/wip/jevbench-v1.2-wip-results.json`.
