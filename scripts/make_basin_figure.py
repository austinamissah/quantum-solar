"""Web figure: what the basin study predicted, and what it actually found.

`docs/results/basin-structure.md` records a pre-registered prediction that was
falsified, and a replacement finding that is more useful than the prediction would
have been. Neither had a picture.

THE PREDICTION. A U-shape in distinct basin count against the penalty weight, with
a strict minimum at alpha*. Weak penalties below it were expected to leave many
competitive infeasible assignments and so many basins; the known 48x overshoot above
it was expected to do the same from the other side.

WHAT THE DATA SHOWS. There is no lower branch. Basin count is 1 at alpha* and 1 at
every alpha below it, rising only above. The mechanism posited for the lower branch
is real but invisible to this metric: below alpha* the search converges just as
reproducibly, to a single WRONG basin. The prediction was wrong about the shape, not
about the physics.

WHY THAT MATTERS, and why the figure marks two things rather than one. Basin count
alone is the wrong lens, because a single basin can be the wrong basin. Crossed with
whether the QUBO's own minimum is still the true optimum, the structure appears: the
encoding breaks below 0.010, reproducibility breaks above 0.021, and **alpha* sits at
the UPPER EDGE of that narrow window, not in the middle of a safe one.** Going 1.4x
above it already doubles the basin count. The alpha* rule buys the largest penalty
margin still inside the single-basin regime and nothing more, which is a warning the
project did not have before this ran.

The trap the study exists to prevent is drawn as the hollow markers on the left: at
alpha = 0.003 the tuned circuit puts *more* mass on the QUBO minimizer than at
alpha*, and it is worthless, because that minimizer is infeasible. Never read basin
count without the exactness column.

EVERYTHING IS DERIVED, NOTHING TRANSCRIBED. Basin counts are re-clustered here from
the 1,200 committed tunings in `basin_study.csv`: distributions are rebuilt from each
row's recorded angles and clustered with `basin_study.cluster_count` at the
pre-registered cutoff, which is the study's own function and its own tau. Exactness
is recomputed from each QUBO's minimum-energy assignments against `dp_solve`. The
script refuses to draw unless the counts it computes match every count committed in
`basin_study.json`, and unless the exactness boundary is where the write-up says.

Run:  python scripts/make_basin_figure.py
"""

from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experiment_hardware as hw  # noqa: E402
from basin_study import ALPHAS, ENCODING, REPS, cluster_count  # noqa: E402

from quantum_solar import dp_solve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs" / "results"
CSV = RESULTS / "basin_study.csv"
STUDY = RESULTS / "basin_study.json"
OUT = ROOT / "docs" / "figures" / "web" / "basin.png"

INSTANCE = 0             # the primary instance, designated in the pre-registration
ALPHA_STAR = 0.0209      # span / penalty, the a-priori threshold
WINDOW = (0.010, 0.021)  # the usable window this study found

INK = "#2F4B7C"
ACCENT = "#E45756"
GOOD = "#CFE3D4"
BAD = "#F6DCDC"


def measure():
    """Re-cluster the committed tunings, and recompute where the encoding breaks."""
    meta = json.loads(STUDY.read_text())
    tau = meta["tau"]
    committed = {row["alpha"]: row["basins_complete_tau"]
                 for row in meta["by_instance"][str(INSTANCE)]}

    params = collections.defaultdict(list)
    for row in csv.DictReader(CSV.open()):
        if int(row["instance_seed"]) == INSTANCE:
            params[float(row["alpha"])].append(json.loads(row["params"]))

    basins, exact = [], []
    for alpha in ALPHAS:
        problem, qubo, _ = hw.build_target(3, INSTANCE, REPS, encoding=ENCODING,
                                           alpha=alpha)
        tunings = params[alpha]
        count = cluster_count([hw.exact_distribution(qubo, p, REPS) for p in tunings],
                              tau, "complete")
        if count != committed[alpha]:
            raise SystemExit(
                f"REFUSING TO DRAW: re-clustering the committed tunings at "
                f"alpha={alpha} gives {count} basins, but basin_study.json records "
                f"{committed[alpha]}. The figure and the study have diverged."
            )

        # Is the QUBO's own minimum still the true optimum? A single basin is
        # worth nothing if it is the wrong one, which is the whole point below.
        x = hw.enumerate_bitstrings(qubo.num_vars)
        energies = (np.einsum("bi,ij,bj->b", x.astype(float), qubo.Q, x.astype(float))
                    + qubo.offset)
        optimum = dp_solve(problem).true_energy
        minimizers = x[np.isclose(energies, energies.min(), atol=1e-9)]
        exact.append(all(problem.is_feasible(m)
                         and np.isclose(problem.energy(m), optimum, atol=1e-9)
                         for m in minimizers))
        basins.append(count)
        print(f"  alpha={alpha:<7} basins={count:<3} exact={exact[-1]}  "
              f"({len(tunings)} tunings)")

    alphas = np.array(ALPHAS, dtype=float)
    exact = np.array(exact)
    first_exact = float(alphas[exact.argmax()])
    if first_exact != WINDOW[0]:
        raise SystemExit(
            f"REFUSING TO DRAW: the encoding first becomes exact at alpha="
            f"{first_exact}, but the write-up puts the usable window at "
            f"{WINDOW}. The boundary this figure marks has moved."
        )
    return alphas, np.array(basins), exact, tau, len(params[ALPHAS[0]])


def main() -> None:
    alphas, basins, exact, tau, n_seeds = measure()
    top = int(basins.max())

    fig, ax = plt.subplots(figsize=(12.4, 6.9))

    # The two failure regimes, and the strip of usable weight between them.
    ax.axvspan(alphas.min() * 0.75, WINDOW[0], color=BAD, zorder=0)
    ax.axvspan(*WINDOW, color=GOOD, zorder=0)
    ax.axvline(ALPHA_STAR, color=INK, ls="--", lw=1.8, zorder=4)

    ax.plot(alphas, basins, "-", color=INK, lw=1.6, alpha=0.5, zorder=2)
    ax.plot(alphas[exact], basins[exact], "o", color=INK, ms=11, zorder=5)
    ax.plot(alphas[~exact], basins[~exact], "o", ms=11, zorder=5,
            markerfacecolor="white", markeredgecolor=ACCENT, markeredgewidth=2.2)
    for a, b in zip(alphas, basins):
        ax.annotate(str(b), (a, b), xytext=(0, 13), textcoords="offset points",
                    ha="center", fontsize=10.5, weight="bold", color=INK)

    # Left: the branch the pre-registration predicted and the data does not have.
    ax.text(0.0042, top * 0.68,
            "The registered prediction was a U-shape\n"
            "with a strict minimum at alpha*.\n"
            "There is no lower branch: the count is 1\n"
            "at alpha* and 1 at every alpha below it.",
            fontsize=10, color="0.3", va="top")
    ax.text(0.0042, top * 0.40,
            "1 basin here, but the WRONG one.\n"
            "Below 0.010 the QUBO's own minimum is\n"
            "infeasible, so the search converges just\n"
            "as reproducibly to an unusable answer.",
            fontsize=9.5, color=ACCENT, va="top")

    # Right: reproducibility going, immediately above the window.
    ax.annotate(
        f"1.4x above alpha* already\ndoubles the count",
        xy=(0.030, 2), xytext=(0.055, top * 0.30),
        fontsize=10, color=INK,
        arrowprops=dict(arrowstyle="->", color=INK, lw=1.4),
    )
    ax.text(0.42, top * 0.80,
            "and keeps rising: the 48x\novershoot costs reproducibility,\n"
            "not just solution quality",
            fontsize=10, color="0.3", ha="center", va="top")

    ax.text(np.sqrt(WINDOW[0] * WINDOW[1]), top * 0.93,
            f"usable window\n{WINDOW[0]:g} to {WINDOW[1]:g}",
            ha="center", va="top", fontsize=10.5, weight="bold", color="#2F6B43")
    ax.annotate(
        f"alpha* = {ALPHA_STAR}\nat the UPPER EDGE,\nnot the middle",
        xy=(ALPHA_STAR, top * 0.94), xytext=(0.075, top * 0.98),
        fontsize=11, weight="bold", color=INK, va="top",
        arrowprops=dict(arrowstyle="->", color=INK, lw=1.6),
    )

    ax.set_xscale("log")
    ax.set_xlim(alphas.min() * 0.75, alphas.max() * 1.35)
    ax.set_ylim(0, top * 1.22)
    ax.set_xlabel("penalty weight alpha (log scale)", fontsize=11.5)
    ax.set_ylabel("distinct basins the tuner converges to\n"
                  f"over {n_seeds} independent restarts", fontsize=11.5)
    ticks = [a for a in alphas if a != ALPHA_STAR]   # see the dashed line for alpha*
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{a:g}" for a in ticks], fontsize=9.5)
    ax.minorticks_off()
    ax.grid(axis="y", alpha=0.25, lw=0.7)
    ax.set_axisbelow(True)

    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", color=INK, ms=10,
               label="the QUBO's minimum is the true optimum"),
        Line2D([], [], marker="o", ls="", markerfacecolor="white",
               markeredgecolor=ACCENT, markeredgewidth=2.2, ms=10,
               label="it is infeasible: reproducible and wrong"),
    ], loc="upper left", fontsize=9.5, frameon=False, bbox_to_anchor=(0.012, 0.99))

    fig.suptitle("alpha* is a boundary, not a safe midpoint",
                 fontsize=15.5, y=0.975)
    fig.tight_layout(rect=(0, 0.175, 1, 0.945))
    fig.text(
        0.5, 0.092,
        "The prediction was falsified and the replacement is more useful: below "
        "0.010 the encoding breaks, above 0.021 reproducibility breaks, and the "
        "a-priori alpha* rule lands on the upper edge of what is left.",
        ha="center", va="center", fontsize=10.5, color=INK,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#EEF2F8",
                  edgecolor="#C6D3E4"),
    )
    fig.text(0.5, 0.026,
             f"{n_seeds} restarts at each of 10 penalty weights, 1,200 tunings in "
             f"all. A basin is a cluster of the tuned output distributions, at a "
             f"cutoff fixed in advance (tau = {tau:.4f}).",
             ha="center", fontsize=10, color="0.35")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  every basin count matches basin_study.json; encoding first exact at "
          f"alpha={WINDOW[0]:g}")


if __name__ == "__main__":
    main()
