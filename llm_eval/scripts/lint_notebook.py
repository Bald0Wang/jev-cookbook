"""Lint / smoke-check the canonical jevbench_intro.ipynb.

Asserts:
  * nbformat v4
  * 17 cells (per PRD)
  * expected cells are markdown / code
  * kernelspec metadata present

Run from repo root:
    python3 scripts/lint_notebook.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import nbformat

REPO = Path(__file__).resolve().parent.parent
CANONICAL = REPO / "notebooks" / "jevbench_intro.ipynb"

EXPECTED_MD = {1, 2, 3, 5, 7, 10, 15, 16}
EXPECTED_CODE = set(range(17)) - EXPECTED_MD


def main() -> int:
    nb = nbformat.read(str(CANONICAL), as_version=4)
    issues = []
    if nb.nbformat != 4:
        issues.append(f"nbformat is {nb.nbformat}, expected 4")
    if len(nb.cells) != 17:
        issues.append(f"cell count is {len(nb.cells)}, expected 17")
    for i, c in enumerate(nb.cells):
        if i in EXPECTED_MD and c.cell_type != "markdown":
            issues.append(f"cell {i} should be markdown, got {c.cell_type}")
        if i in EXPECTED_CODE and c.cell_type != "code":
            issues.append(f"cell {i} should be code, got {c.cell_type}")
    if not nb.metadata.get("kernelspec"):
        issues.append("missing kernelspec in metadata")
    if issues:
        for s in issues:
            print(f"  ✗ {s}")
        return 1
    print(
        f"  ✓ notebook OK (nbformat v{nb.nbformat}, "
        f"{len(nb.cells)} cells, kernel {nb.metadata['kernelspec'].get('name')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())