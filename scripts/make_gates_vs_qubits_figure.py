"""Web figure: the resource that actually limited us was not the one we counted.

Everyone counts qubits. Qubits are how quantum computers are advertised, and this
project's first phase went into an encoding that cut a 6-slot problem from 22
qubits to 12. Then we looked at data from a run that had already happened, and the
qubit count explained nothing.

This draws that. Four circuits ran on `ibm_fez` on 2026-07-11; each one's
degradation is the total-variation distance between its ideal-simulated output and
what the device returned. Plotted against **two-qubit gate count** the four points
rise monotonically across a 7.8x range. Plotted against **qubit count** they
collapse onto two x-positions, and the two circuits sharing 6 qubits differ by 71%
in degradation -- the same width as the whole trend the left panel shows.

Gates matter because each two-qubit gate is a physical operation with an error
rate (~0.3% median on this device, recorded at submission) and errors compound
multiplicatively. An idle qubit costs comparatively little; a gate costs every
time it runs.

What it changed: the 6-slot target needs ~348 gates even with the better encoding,
more than the worst circuit here (290), which had already produced essentially no
usable signal. **No encoding makes it submittable.** A phase had gone into
optimizing a resource that was not the binding constraint, and fifteen minutes with
data already in hand would have reordered the project.

COMPILE THE COMPARISON THE SAME WAY. LESSONS.md section 2 used to put ~269 gates
against circuit D's 290, which reads as *fewer* and makes a true claim look false.
Those are different transpiler settings: 269 is the 6-slot circuit at
`optimization_level=3`, while 290 -- and this figure's whole x-axis -- is level 1,
which is what the run actually used. Like for like it is 348 vs 290 at level 1, or
269 vs 237 at level 3; the gap holds at either, and only the mixed pairing was
wrong. Both columns are committed in `docs/results/slack-free-encoding.md`. If you
ever change which level this axis carries, change the 348 with it.

DATA PROVENANCE, all committed, nothing re-run:
  * degradation -- TVD(ideal-sim, hardware), rebuilt here from the raw device
    counts in `hardware_counts.json` and the tuned angles in
    `hardware_params.json`, through `experiment_hardware.py`'s own functions. Not
    transcribed: the script REFUSES TO DRAW unless all four values reproduce
    LESSONS.md section 2's published table.
  * two-qubit gate counts -- the transpiled `optimization_level=1` counts recorded
    for the July circuits in `docs/results/slack-free-encoding.md`. Deliberately
    NOT re-transpiled: transpilation is not deterministic across calls, and one
    circuit compiled to 113 and 98 two-qubit gates on consecutive runs, which is
    the exact failure this project already hit once (LESSONS.md section 6).

Run:  python scripts/make_gates_vs_qubits_figure.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experiment_hardware as hw  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs" / "results"
OUT = ROOT / "docs" / "figures" / "web" / "gates_vs_qubits.png"

# The four circuits of the 2026-07-11 run, in the order they are reported.
# `gates` are the committed optimization_level=1 transpiled two-qubit counts
# (slack-free-encoding.md, "Transpiler optimization level"); `published` is
# LESSONS.md section 2's degradation column, which this script must reproduce.
CIRCUITS = [
    {"T": 2, "reps": 1, "qubits": 6, "gates": 37, "published": 0.119},
    {"T": 2, "reps": 2, "qubits": 6, "gates": 77, "published": 0.203},
    {"T": 3, "reps": 1, "qubits": 10, "gates": 124, "published": 0.383},
    {"T": 3, "reps": 2, "qubits": 10, "gates": 290, "published": 0.459},
]
PUBLISHED_ATOL = 5e-4   # the published table is quoted to three decimals

INK = "#2F4B7C"
ACCENT = "#E45756"


def measured_degradation() -> list[float]:
    """TVD(ideal-sim, hardware) per circuit, rebuilt from the committed run."""
    params = {(r["T"], r["reps"]): r
              for r in json.loads((RESULTS / "hardware_params.json").read_text())}
    counts = json.loads((RESULTS / "hardware_counts.json").read_text())
    device = {(c["T"], c["reps"]): c["counts"] for c in counts["results"]}

    out = []
    for circuit in CIRCUITS:
        key = (circuit["T"], circuit["reps"])
        record = params[key]
        _problem, _qubo, ansatz = hw.build_target(record["T"], record["seed"],
                                                  record["reps"])
        simulated = hw.counts_to_probs(hw.ideal_sim_counts(ansatz, record["params"]),
                                       record["m"])
        hardware = hw.counts_to_probs(device[key], record["m"])
        tvd = float(hw.tv_distance(simulated, hardware))

        if abs(tvd - circuit["published"]) > PUBLISHED_ATOL:
            raise SystemExit(
                f"REFUSING TO DRAW: the T={circuit['T']}, reps={circuit['reps']} "
                f"circuit rebuilds to TVD(sim,hw)={tvd:.4f}, but LESSONS.md §2 "
                f"publishes {circuit['published']:.3f} (tolerance "
                f"{PUBLISHED_ATOL:g}). The figure and the write-up have diverged; "
                f"fix that before drawing either."
            )
        out.append(tvd)
    return out


def _describe(circuit) -> str:
    """What a point actually is, in words rather than a letter."""
    return (f"{circuit['T']} slots · {circuit['reps']} "
            f"layer{'s' if circuit['reps'] > 1 else ''}")


def main() -> None:
    degradation = measured_degradation()
    gates = np.array([c["gates"] for c in CIRCUITS], dtype=float)
    qubits = np.array([c["qubits"] for c in CIRCUITS], dtype=float)
    labels = [_describe(c) for c in CIRCUITS]
    y = np.array(degradation)
    spread = 100 * (y[1] / y[0] - 1)

    fig, (ax_g, ax_q) = plt.subplots(1, 2, figsize=(13.2, 6.2), sharey=True)

    # --- left: against the resource that explains it -------------------------
    # No connecting line. These are four discrete circuits, not a sampled curve,
    # and a line implies a continuum that was never measured.
    ax_g.scatter(gates, y, s=110, color=INK, zorder=3)
    for x, yy, label in zip(gates, y, labels):
        ax_g.annotate(label, (x, yy), xytext=(0, 13), textcoords="offset points",
                      ha="center", fontsize=10, color=INK)
    ax_g.set_xlabel("two-qubit gates in the circuit that actually ran")
    ax_g.set_xlim(0, 330)
    ax_g.set_title("Against gate count: it tracks, across a 7.8× range",
                   fontsize=12.5)
    ax_g.text(
        18, 0.605,
        "Every two-qubit gate is a physical operation that can fail\n"
        "(~0.3% of the time on this machine), and the errors compound.\n"
        "Gates cost you every time one runs; an idle qubit costs little.",
        fontsize=9.5, color="0.35", va="top",
    )

    # --- right: against the resource everybody counts -------------------------
    ax_q.scatter(qubits, y, s=110, color=INK, zorder=3)
    for x, yy, label in zip(qubits, y, labels):
        ax_q.annotate(label, (x, yy), xytext=(-11, 0), textcoords="offset points",
                      ha="right", va="center", fontsize=10, color=INK)
    # The pair that shares a qubit count is the whole point: same x, 71% apart.
    ax_q.annotate("", xy=(6, y[0]), xytext=(6, y[1]),
                  arrowprops=dict(arrowstyle="<->", color=ACCENT, lw=2.0))
    ax_q.text(6.18, (y[0] + y[1]) / 2,
              f"same qubit count,\n{spread:.0f}% apart",
              color=ACCENT, fontsize=10.5, weight="bold", va="center")
    ax_q.set_xlabel("qubits")
    ax_q.set_xticks([6, 10])
    # Room to the right for the explanation, and the emptiness is itself the
    # message rather than wasted space.
    ax_q.set_xlim(4.4, 14.0)
    ax_q.set_title("Against qubit count: it cannot tell them apart",
                   fontsize=12.5)
    # Say what the emptiness means, so the panel reads as the argument rather
    # than as a chart that failed to render.
    ax_q.text(
        11.4, 0.335,
        "Only two values on this axis.\n"
        f"The two 6-qubit circuits differ by {spread:.0f}%,\n"
        "as much as the entire range on the left.\n"
        "Qubit count cannot explain the damage;\n"
        "the sparseness here is the finding.",
        fontsize=9.5, color="0.35", va="top", ha="center",
    )

    ax_g.set_ylabel("how far the real machine's output landed from\n"
                    "the perfect simulated answer   (0 = identical)")
    for ax in (ax_g, ax_q):
        ax.set_ylim(0, 0.62)
        ax.grid(alpha=0.25, lw=0.7)
        ax.set_axisbelow(True)

    fig.suptitle("We spent a phase optimizing the resource that wasn't the constraint",
                 fontsize=15, y=0.985)
    fig.tight_layout(rect=(0, 0.195, 1, 0.945))

    # The consequence, in the figure rather than under it: this is the reason the
    # result mattered, and an attachment gets read without its surrounding text.
    # 348, not the 269 quoted in LESSONS.md §2: that is the same circuit compiled
    # at optimization_level=3, while this axis carries the level-1 counts the run
    # actually used. Comparing 269 against 290 mixes transpiler settings and makes
    # a true claim look false. Like for like it is 348 vs 290, or 269 vs 237.
    fig.text(
        0.5, 0.105,
        "What it changed: the 6-slot problem we were building toward needs ~348 gates "
        "even with the encoding we designed to save qubits,\ncompiled the same way as "
        "the circuits above. That is more than the worst of them, which returned no "
        "usable signal.\nNo encoding makes it submittable. We had spent a phase on the "
        "wrong axis.",
        ha="center", va="center", fontsize=10.5, color=INK,
        bbox=dict(boxstyle="round,pad=0.6", facecolor="#EEF2F8", edgecolor="#C6D3E4"),
    )
    fig.text(
        0.5, 0.018,
        "Four QAOA circuits on IBM's ibm_fez, 11 July 2026, 4,096 shots each "
        "(job d994b5cqp3as739tkvp0); vertical axis is total-variation distance "
        "from the ideal simulation.",
        ha="center", fontsize=8.5, color="0.45",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    for circuit, tvd in zip(CIRCUITS, degradation):
        print(f"  {_describe(circuit):<18} {circuit['qubits']:>2} qubits  "
              f"{circuit['gates']:>3} gates  TVD(sim,hw) = {tvd:.4f}  "
              f"[reproduces LESSONS §2's {circuit['published']:.3f}]")
    print(f"  gate count spans {gates.max() / gates.min():.1f}×; "
          f"the two 6-qubit circuits differ by {spread:.0f}%")


if __name__ == "__main__":
    main()
