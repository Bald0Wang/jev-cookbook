# Subject topics (v1.2.1)

Every JevBench v1.2 decision carries one **subject topic**: what the item is about. This is separate from its
**family** (the task format: intent, extraction, long_policy, multi_hop, ...). Topics were added on 19 Sep 2026 for the
topic radar on benchmarkheaven.com/jev-models. They are not part of the JevBench Score and change no number in it.

| Topic | Covers | Items | easy / standard / judge / hard |
|---|---|---|---|
| Math & numbers | a calculation decides the answer: arithmetic, word problems, probability, dates, units | 129 | 0 / 6 / 86 / 37 |
| Support & operations | support tickets, incidents, logistics, scheduling desks, routing work to a team | 119 | 9 / 31 / 30 / 49 |
| Everyday language | short everyday messages: intents, assistant requests, reading a detail out of a text | 79 | 48 / 26 / 0 / 5 |
| Rules, policy & law | applying written rules: company policies, contracts, regulations, eligibility | 67 | 0 / 18 / 0 / 49 |
| Finance & commerce | money: payments, refunds, invoices, orders, expenses, insurance payouts | 64 | 13 / 8 / 0 / 43 |
| Coding & software | code, SQL, repositories, developer tools and IT systems | 56 | 0 / 7 / 30 / 19 |
| Safety & security | untrusted or injected instructions, fraud, moderation, access and security triage | 20 | 2 / 0 / 0 / 18 |

The items did not carry a subject field (only the family), so the list was fitted to what the 534 items really contain.
Science, medicine and general knowledge were candidates, but fewer than 15 items were about each of them; those items went
to their next-best topic (for example, a health-plan claim to Finance & commerce, a dosing-time question to Math).

## How the labels were made

1. **Draft:** DeepSeek V3.2 (`deepseek-ai/DeepSeek-V3.2-TEE` on Chutes, a confidential-compute endpoint, temperature 0)
   labelled all 534 items in batches of 8 from the question, the options and the first ~1,500 characters of the content.
2. **Hand review** (Claude Opus 5): every item except the 78 imported routing requests was read in a one-line listing
   (question + start of the content); the routing requests take their topic from their upstream request category
   (coding and agentic → coding, math → math, tool use and long documents → support & operations). 57 labels changed:
   - rules applied by item group: the 68 imported judge items are all self-contained math answers → math; the 12
     adversarial items are all about untrusted instructions → safety & security; the short "policy" items → rules, policy &
     law; all easy intent and tool-choice items → everyday language; the delivery-method extraction items → support &
     operations; paraphrase pairs (`...-0` / `...-1`) always share one topic;
   - 16 single items after reading them (the 10 health items, the one knowledge item, date and money calculations that
     had been filed under coding or finance, and similar).
3. **Aggregates:** `scripts/v1.2/topics.py` joins the labels with exactly the run files the published scores came from
   and refuses to write unless its per-tier counts equal `results/v1.2/jevbench-v1.2-per-task.json` for every system.

## What is published

- `datasets/topics.json`: the topic of each of the 231 public items, and for the 303 held-out and imported items only
  counts per topic and tier. Held-out ids and texts stay private (like the items themselves).
- `results/v1.2/jevbench-v1.2-topics.json`: per system and topic `n`, `attempted`, `correct`, `accuracy`.
  Accuracy = correct / attempted over all four tiers; failures count as wrong; items a partial run never attempted are
  left out, and a topic with fewer than 15 attempted items for a system is too thin to read.

## Reading it

Topics differ in their tier mix: Everyday language is mostly easy items, Rules & law and Finance mostly hard ones. Compare
systems **within** a topic, not topics with each other. One model labelled and one reviewer checked the labels; some items
could sit in two topics (an insurance claim is both money and rules), and each got the one a reader would name first.
