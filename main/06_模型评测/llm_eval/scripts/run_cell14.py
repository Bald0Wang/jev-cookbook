"""Run only cell 14 of the notebook via nbclient (skip cells 1-13)."""
import sys, json
from pathlib import Path
import nbformat
from nbclient import NotebookClient

PROJ = Path(__file__).resolve().parents[1]
NB_PATH = PROJ / "notebooks" / "jevbench_intro.ipynb"
NB_OUT = PROJ / "notebooks" / "jevbench_intro_executed.ipynb"


def main():
    nb = nbformat.read(NB_PATH, as_version=4)
    target_idx = None
    for i, c in enumerate(nb.cells):
        if c.cell_type == "code":
            src = c.source
            if "Cell 14 — 4 维横评" in src or "# Cell 14" in src[:60]:
                target_idx = i
                break
    if target_idx is None:
        print("cell 14 not found")
        return 1

    # Mark all cells except cell 14 as not-to-execute by emptying outputs.
    # nbclient doesn't have a per-cell skip API for execute(), so we run all
    # but force cells 0..13 to be no-ops. Easier: temporarily replace them
    # with a pass-through, run, then restore.
    backup_cells = list(nb.cells)
    nb.cells[target_idx], nb.cells[0:target_idx] = nb.cells[target_idx], []  # swap so target becomes 0
    # Now prepend cells 14+ so we keep cell 14's intended context (its sibling cells)
    # Actually simpler: just run cell 14 in isolation.

    nb_14 = nbformat.v4.new_notebook()
    nb_14.cells = [backup_cells[target_idx]]
    nb_14.metadata = nb.metadata
    tmp = PROJ / "notebooks" / "_cell14_only.ipynb"
    nbformat.write(nb_14, tmp)

    client = NotebookClient(nb_14, kernel_name="python3", timeout=300)
    client.execute()

    out_nb = nbformat.read(tmp, as_version=4)
    # Find outputs in cell 14
    print("--- cell 14 outputs ---")
    for cell_out in out_nb.cells[0].get("outputs", []):
        if cell_out.get("output_type") == "stream":
            print(cell_out.get("text", "")[:2000])
        elif cell_out.get("output_type") == "display_data":
            data = cell_out.get("data", {})
            if "image/png" in data:
                imgpath = PROJ / "runs" / "notebook-demo" / "multi" / "charts" / "14_real_compare.png"
                if imgpath.exists():
                    print(f"image saved: {imgpath}")
            if "text/plain" in data:
                print("---text/plain:")
                print(data["text/plain"][:3000])
        elif cell_out.get("output_type") == "error":
            print("ERROR:", cell_out.get("ename"), cell_out.get("evalue")[:500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
