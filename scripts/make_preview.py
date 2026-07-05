"""Regenerate the README schedule preview image (docs/schedule.png).

Usage:  python scripts/make_preview.py
"""

import matplotlib

matplotlib.use("Agg")

from pathlib import Path

from quantum_solar import dp_solve, synthetic_instance
from quantum_solar.plotting import plot_schedule

# Coarser slots with a clean (noise-free) day so the "charge cheap midday,
# discharge at the evening peak" structure reads clearly in the preview.
problem = synthetic_instance(num_slots=12, seed=1, noise=0.0)
solution = dp_solve(problem)

out = Path(__file__).resolve().parent.parent / "docs" / "schedule.png"
fig = plot_schedule(problem, solution)
fig.savefig(out, dpi=110, bbox_inches="tight")
print(f"wrote {out} (daily cost ${solution.true_energy:.2f})")
