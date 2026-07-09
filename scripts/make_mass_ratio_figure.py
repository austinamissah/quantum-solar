"""Regenerate docs/results/mass_ratio.png as a presentation figure for the web.

Reads the committed results CSV only (docs/results/qaoa_scaling.csv) via
experiment_scaling.load_results and re-renders the mass-ratio chart with
non-technical framing and blog-readable fonts. The underlying numbers are
identical to the experiment; no experiments are re-run.

    python scripts/make_mass_ratio_figure.py

Caption suggestion (for the blog post):
  This chart asks a simple question: does the quantum optimizer (QAOA) find the
  best battery schedule more often than random guessing? Points above the dashed
  grey line beat random; points on it are no better than chance. Only at the
  smallest problem (2 slots, filled dots) do all our runs place enough
  probability on the best answer to measure this directly, and even there the
  result is mixed: a modest edge at 1 and 3 quantum layers, but worse than random
  at 2. For every larger problem, at least one run's success falls below the
  resolution of 4096 samples, so those values are only upper bounds (hollow
  triangles, dashed lines) and cannot confirm any advantage. The honest takeaway:
  a small, depth-dependent edge at the smallest size, and no measurable quantum
  advantage as the problem scales up.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experiment_scaling as exp  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "results" / "mass_ratio.png"


def main():
    rows = [r for r in exp.load_results() if not np.isnan(r.get("mass_ratio", float("nan")))]
    slot_counts = sorted({r["T"] for r in rows})
    layer_counts = sorted({r["reps"] for r in rows})

    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    colors = [f"C{i}" for i in range(len(layer_counts))]

    for color, reps in zip(colors, layer_counts):
        pts = []  # (T, ratio, is_upper_bound)
        for T in slot_counts:
            group = [r for r in rows if r["T"] == T and r["reps"] == reps]
            if not group:
                continue
            # The plotted value is a seed-average; if ANY seed fell below the
            # measurement floor (its ratio used 1/4096 as a placeholder), the
            # average is itself only an upper bound.
            pts.append((T, float(np.mean([r["mass_ratio"] for r in group])),
                        any(r["mass_ratio_is_upper_bound"] for r in group)))

        # Draw each segment solid where measured, dashed/faded where it leads into
        # an upper-bound point, so a rising line is never mistaken for a real gain.
        for (x0, y0, u0), (x1, y1, u1) in zip(pts, pts[1:]):
            uncertain = u0 or u1
            ax.plot([x0, x1], [y0, y1], color=color, linewidth=2, zorder=2,
                    linestyle="--" if uncertain else "-", alpha=0.45 if uncertain else 1.0)
        conf = [(x, y) for x, y, u in pts if not u]
        if conf:
            ax.plot(*zip(*conf), linestyle="none", marker="o", markersize=7, color=color)
        ub = [(x, y) for x, y, u in pts if u]
        if ub:
            ax.scatter(*zip(*ub), marker="v", s=130, facecolors="white",
                       edgecolors=color, linewidths=1.8, zorder=4)

    # Reference line: parity with random guessing.
    ax.axhline(1.0, color="0.35", linestyle="--", linewidth=1.4)
    ax.text(slot_counts[-1], 1.06, "no better than random", color="0.35",
            fontsize=12, ha="right", va="bottom")

    ax.set_yscale("log")
    ax.set_xticks(slot_counts)
    ax.set_xticklabels([f"{T} slots\n{4 * T - 2} qubits" for T in slot_counts], fontsize=11)
    ax.tick_params(axis="y", labelsize=11)
    ax.set_xlabel("problem size", fontsize=13, labelpad=8)
    ax.set_ylabel("optimal-answer probability\n(quantum vs random guessing)", fontsize=13)
    ax.set_title("Quantum method vs random guessing", fontsize=16, pad=12)

    # Legend: one entry per layer count, plus plain-language notes on the markers.
    handles = [
        plt.Line2D([], [], color=color, marker="o", markersize=7, linewidth=2,
                   label=f"{reps} quantum layer" + ("s" if reps > 1 else ""))
        for color, reps in zip(colors, layer_counts)
    ]
    handles += [
        plt.Line2D([], [], marker="v", markerfacecolor="white", markeredgecolor="0.4",
                   linestyle="none", markersize=11,
                   label="upper bound (below what we can measure)"),
        plt.Line2D([], [], color="0.4", linestyle="--", linewidth=2, alpha=0.6,
                   label="dashed: unmeasurable region"),
    ]
    ax.legend(handles=handles, fontsize=11, loc="upper left", framealpha=0.9)

    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
