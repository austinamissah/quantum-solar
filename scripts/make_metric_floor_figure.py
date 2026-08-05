"""The before/after pair: one dataset, two ways of reading it.

The scaling chart once showed optimal-state probability declining to zero with
problem size, and the decline was the headline. At the largest sizes the value was
exactly zero in every cell — not because the probability was zero, but because it
was three orders of magnitude below what 4096 shots can resolve. The metric had
bottomed out and reported a number anyway.

Both panels here are built from the **same CSV, same runs, same seeds, same T
range**. The only thing that differs is how the quantity was obtained: sampling
the simulator (left) versus reading the exact probability off the statevector
(right). That is deliberate — pairing the original July figure against the current
one would differ in the T range as well, and a comparison that differs in two
things measures neither (docs/LESSONS.md section 6).

Run:  python scripts/make_metric_floor_figure.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from experiment_scaling import RESULTS_DIR, load_results  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "figures" / "web" / "metric_floor.png"
CSV = RESULTS_DIR / "qaoa_scaling_T5.csv"


def main() -> None:
    rows = load_results(CSV)
    shots = rows[0]["shots"]
    Ts = sorted({r["T"] for r in rows})
    reps_vals = sorted({r["reps"] for r in rows})

    def series(key, agg):
        return {rp: [agg([r[key] for r in rows if r["T"] == T and r["reps"] == rp])
                     for T in Ts] for rp in reps_vals}

    n_zero = sum(1 for r in rows if r["opt_prob_mass"] == 0.0)
    exact = np.array([r["ideal_opt_mass"] for r in rows])

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(12.5, 5.2))

    # --- left: what we plotted -----------------------------------------------
    means = series("opt_prob_mass", np.mean)
    lo, hi = series("opt_prob_mass", np.min), series("opt_prob_mass", np.max)
    for rp in reps_vals:
        line, = ax0.plot(Ts, means[rp], marker="o", label=f"reps={rp}")
        ax0.fill_between(Ts, lo[rp], hi[rp], alpha=0.15, color=line.get_color())
    ax0.set_ylim(-0.02, 1.02)
    ax0.set_ylabel(f"prob. mass on optimal bitstrings ({shots} shots)")
    ax0.set_title("What we plotted\nsampled — reads exactly 0 in "
                  f"{n_zero} of {len(rows)} cells", fontsize=11)
    ax0.annotate("the 'trend' is the metric\nhitting its floor",
                 xy=(Ts[-1], 0.0), xytext=(Ts[1] + 0.35, 0.34),
                 arrowprops=dict(arrowstyle="->", color="crimson", lw=1.3),
                 color="crimson", fontsize=9.5, ha="left")

    # --- right: what was true ------------------------------------------------
    means = series("ideal_opt_mass", np.mean)
    lo, hi = series("ideal_opt_mass", np.min), series("ideal_opt_mass", np.max)
    for rp in reps_vals:
        line, = ax1.plot(Ts, means[rp], marker="o", label=f"reps={rp}")
        ax1.fill_between(Ts, lo[rp], hi[rp], alpha=0.15, color=line.get_color())
    ax1.set_yscale("log")
    ax1.axhline(1.0 / shots, color="crimson", ls=":", lw=1.3)
    # Label goes in the empty bottom-left, not against the line: at the line the
    # text lands on top of the reps=1/reps=2 curves and is unreadable.
    ax1.annotate(f"1/{shots} shot floor —\neverything below reads 0 on the left",
                 xy=(Ts[0] + 0.06, 1.0 / shots), xytext=(Ts[0] + 0.06, 3e-11),
                 arrowprops=dict(arrowstyle="->", color="crimson", lw=1.2),
                 color="crimson", fontsize=9.5, va="bottom", ha="left")
    ax1.set_ylabel("prob. mass on optimal bitstrings (exact, statevector)")
    ax1.set_title("What was true\nsame runs, read off the statevector: "
                  f"{exact.min():.0e} to {exact.max():.0e}", fontsize=11)

    for ax in (ax0, ax1):
        ax.set_xticks(Ts)
        ax.set_xlabel("T (time slots)")
        ax.legend(fontsize=9)

    fig.suptitle("The same 36 runs, measured two ways", fontsize=13.5, y=0.99)
    fig.tight_layout(rect=(0, 0.035, 1, 0.98))
    fig.text(0.5, 0.005,
             "Identical data, seeds and problem sizes — the only difference is "
             "sampling the simulator vs. reading the exact probability off it. "
             "Cost: one extra computation.",
             ha="center", fontsize=9, color="0.35")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}  ({n_zero}/{len(rows)} sampled cells are exactly zero; "
          f"exact range {exact.min():.2e}-{exact.max():.2e})")


if __name__ == "__main__":
    main()
