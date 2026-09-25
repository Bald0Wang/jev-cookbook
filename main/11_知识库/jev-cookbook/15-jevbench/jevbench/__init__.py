"""JevBench v1 - a benchmark harness for Jev-class typed decision models."""

__version__ = "1.2.0"

FAMILIES = (
    "routing",
    "adequacy",
    "policy",
    "intent",
    "ordinal",
    "extraction",
)
# v1.2 hard-tier families (datasets/HARD-TIER.md)
HARD_FAMILIES = ("long_policy", "tradeoff", "ambiguous", "trap", "multi_hop", "temporal_numeric", "adversarial",
                 "judge_hard", "routing_hard", "probability")
