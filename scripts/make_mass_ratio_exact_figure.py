"""Web figure: QAOA vs uniform random, measured exactly, at both penalty weights.

The existing `mass_ratio.png` is honest but conservative: it is built on the
*sampled* optimal mass, which floors at 1/4096, so every point where a seed fell
below the floor could only be drawn as an upper limit inside a "too small to
measure" band. That was the right call with the data then available.

It is no longer necessary. The exact optimal mass is available from the
statevector with no sampling floor (quantum_solar.statevector), so the band of
unmeasurable points can be replaced with measured values -- and the answer inside
that band turns out not to be "too small", it is 4-20x.

Two panels, because the comparison only means something at a stated penalty
weight:
  * default weights -- penalties ~48x the objective span, the configuration the
    original figure used. QAOA hovers around parity with random and collapses at
    T=5.
  * alpha* weights -- penalties scaled to the a-priori threshold. QAOA sits at
    4-20x uniform at every size tested, with no decay through T=5.

The gap between the panels is the penalty-weight finding, drawn.

IMPORTANT, and stated on the figure: "beats uniform random sampling" is a low bar.
It is NOT a claim of advantage over classical optimization -- dp_solve returns the
exact optimum for these instances in microseconds. The bar here is whether the
quantum state concentrates on good answers at all.

This figure SUPERSEDES docs/figures/web/mass_ratio.png. That one is not wrong --
it handled its sampling floor correctly, with upper-limit markers and a "too small
to measure" band -- but its conclusion was a property of the floor and of a
mis-scaled penalty weight, not of the algorithm.

Caption (for the site):

  This chart asks a simple question: does the quantum optimizer concentrate on the
  best battery schedule more often than random guessing would? Above the dashed
  line beats random; on it is no better than chance.

  The two panels are the same algorithm on the same problems, run at two different
  settings of a single knob -- the penalty weight, which controls how hard the
  formulation pushes the optimizer to respect the battery's physical limits. On the
  left it is set by the usual rule of thumb, roughly 48x larger than the range of
  the actual electricity cost. The optimizer duly spends almost all its effort
  satisfying constraints and barely any on price: it hovers around random and
  collapses at the largest size. On the right the weight is set to a threshold
  derivable in advance from the problem itself. The same circuits now land on the
  best schedule 4 to 20 times more often than chance, at every size tested, with no
  decline as the problem grows.

  The gap between the two panels is the entire finding. Nothing about the encoding,
  the circuits, or the optimizer differs between them.

  Two honest caveats. Triangles mark points where the classical optimizer ran out
  of its evaluation budget, so those values are lower bounds -- the true numbers are
  at least this good and possibly better. And "better than random guessing" is a
  deliberately low bar: an exact classical solver finds the true optimum for every
  one of these instances in microseconds. What this measures is whether the quantum
  state concentrates on good answers at all, which is a precondition for any future
  advantage, not evidence of one.

  An earlier version of this chart, built by sampling the simulator 4096 times per
  circuit rather than reading the exact probability off it, concluded there was "no
  measurable quantum advantage as the problem scales up". That conclusion was an
  artifact of the measurement: below roughly one part in 4096 the sampled value
  reads zero regardless of the truth, and at the two largest sizes it read zero in
  every cell. Read exactly, the values it called unmeasurable are 4 to 20x.

Run:  python scripts/make_mass_ratio_exact_figure.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from experiment_scaling import RESULTS_DIR, load_results  # noqa: E402

OUT = (Path(__file__).resolve().parent.parent / "docs" / "figures" / "web"
       / "mass_ratio_exact.png")
PANELS = [
    ("qaoa_scaling_T5.csv", "Default weights",
     "penalties ~48x the objective span"),
    ("qaoa_scaling_alphastar_T5.csv", "Rescaled to $\\alpha^*$",
     "penalties at the a-priori threshold"),
]


def main() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.4), sharey=True)
    censored_any = False

    for ax, (csv, title, subtitle) in zip(axes, PANELS):
        rows = load_results(RESULTS_DIR / csv)
        Ts = sorted({r["T"] for r in rows})
        reps_vals = sorted({r["reps"] for r in rows})
        censored_any |= any(r.get("evals_censored") for r in rows)

        for reps in reps_vals:
            ys, cens = [], []
            for T in Ts:
                g = [r for r in rows if r["T"] == T and r["reps"] == reps]
                # Ratio of means, not mean of ratios: the uniform baseline is
                # identical within a (T, seed) cell, and this keeps a single
                # near-zero seed from dominating a mean of ratios.
                ys.append(float(np.mean([r["ideal_opt_mass"] for r in g]))
                          / float(np.mean([r["uniform_opt_mass"] for r in g])))
                cens.append(any(r.get("evals_censored") for r in g))
            line, = ax.plot(Ts, ys, marker="o", label=f"{reps} layer"
                            + ("s" if reps > 1 else ""))
            # Up-arrows where the optimizer ran out of budget: those points are
            # lower bounds, and the bound is one-sided upward.
            cx = [t for t, c in zip(Ts, cens) if c]
            cy = [y for y, c in zip(ys, cens) if c]
            ax.scatter(cx, cy, marker="^", s=85, facecolors="none",
                       edgecolors=line.get_color(), linewidths=1.4, zorder=3)

        ax.axhline(1.0, color="0.35", ls="--", lw=1.2)
        ax.set_yscale("log")
        ax.set_xticks(Ts)
        ax.set_xlabel("problem size (T time slots)")
        ax.set_title(f"{title}\n{subtitle}", fontsize=11.5)
        ax.legend(fontsize=9, loc="lower left")

    axes[0].set_ylabel("how much better than random guessing\n(exact, "
                       "statevector: no sampling floor)")
    # Label the parity line in the right panel: the band just above it is empty
    # there, whereas in the left panel it lands on top of the T=2 points.
    axes[1].text(2.04, 1.12, "parity with random guessing", color="0.35",
                 fontsize=9, va="bottom")

    fig.suptitle("Does the quantum optimizer beat random guessing?",
                 fontsize=14, y=0.995)
    fig.tight_layout(rect=(0, 0.075, 1, 0.97))
    note = ("△ = the classical optimizer hit its evaluation budget, so the point "
            "is a lower bound.\n"
            "'Better than random' is a low bar: the exact classical solver "
            "returns the optimum for every instance here in microseconds. "
            "This measures whether the quantum state concentrates on good "
            "answers at all, not advantage over classical methods.")
    fig.text(0.5, 0.008, note, ha="center", fontsize=9, color="0.35")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}  (censored points marked: {censored_any})")


if __name__ == "__main__":
    main()
