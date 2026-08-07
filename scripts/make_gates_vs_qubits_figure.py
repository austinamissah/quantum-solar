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

What it changed: the 6-slot target needs ~269 gates even with the better encoding,
worse than the worst circuit here, which had already produced essentially no usable
signal. **No encoding makes it submittable.** A phase had gone into optimizing a
resource that was not the binding constraint, and fifteen minutes with data already
in hand would have reordered the project.

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
    {"T": 2, "reps": 1, "qubits": 6, "gates": 37, "published": 0.119, "tag": "A"},
    {"T": 2, "reps": 2, "qubits": 6, "gates": 77, "published": 0.203, "tag": "B"},
    {"T": 3, "reps": 1, "qubits": 10, "gates": 124, "published": 0.383, "tag": "C"},
    {"T": 3, "reps": 2, "qubits": 10, "gates": 290, "published": 0.459, "tag": "D"},
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
                f"REFUSING TO DRAW: circuit {circuit['tag']} (T={circuit['T']}, "
                f"reps={circuit['reps']}) rebuilds to TVD(sim,hw)={tvd:.4f}, but "
                f"LESSONS.md §2 publishes {circuit['published']:.3f} "
                f"(tolerance {PUBLISHED_ATOL:g}). The figure and the write-up have "
                f"diverged; fix that before drawing either."
            )
        out.append(tvd)
    return out


def main() -> None:
    degradation = measured_degradation()
    gates = np.array([c["gates"] for c in CIRCUITS], dtype=float)
    qubits = np.array([c["qubits"] for c in CIRCUITS], dtype=float)
    tags = [c["tag"] for c in CIRCUITS]
    y = np.array(degradation)

    fig, (ax_g, ax_q) = plt.subplots(1, 2, figsize=(12.8, 5.4), sharey=True)

    # --- left: against the resource that explains it -------------------------
    ax_g.plot(gates, y, "-o", color=INK, lw=1.8, ms=9, zorder=3)
    for x, yy, tag in zip(gates, y, tags):
        ax_g.annotate(f"  {tag}", (x, yy), fontsize=11, weight="bold", color=INK,
                      va="center")
    ax_g.set_xlabel("two-qubit gates in the transpiled circuit")
    ax_g.set_title("Against gate count\nmonotonic across a 7.8× range", fontsize=12.5)
    ax_g.annotate(
        f"{gates.min():.0f} → {gates.max():.0f} gates\n{y.min():.2f} → {y.max():.2f} degradation",
        xy=(gates[-1], y[-1]), xytext=(gates[-1] - 15, y[-1] - 0.19),
        ha="right", fontsize=10, color=INK,
        arrowprops=dict(arrowstyle="->", color=INK, lw=1.3,
                        connectionstyle="arc3,rad=-0.25"),
    )

    # --- right: against the resource everybody counts -------------------------
    ax_q.scatter(qubits, y, s=95, color=INK, zorder=3)
    # Tags to the LEFT here: the right side of x=6 carries the spread arrow.
    for x, yy, tag in zip(qubits, y, tags):
        ax_q.annotate(f"{tag}  ", (x, yy), fontsize=11, weight="bold", color=INK,
                      va="center", ha="right")
    # The pair that shares a qubit count is the whole point: same x, 71% apart.
    ax_q.annotate(
        "", xy=(6, y[0]), xytext=(6, y[1]),
        arrowprops=dict(arrowstyle="<->", color=ACCENT, lw=2.0),
    )
    ax_q.text(6.12, (y[0] + y[1]) / 2,
              f"same qubit count,\n{100 * (y[1] / y[0] - 1):.0f}% apart",
              color=ACCENT, fontsize=10.5, weight="bold", va="center")
    ax_q.set_xlabel("qubits")
    ax_q.set_xticks([6, 10])
    ax_q.set_xlim(4.6, 11.4)
    ax_q.set_title("Against qubit count\ntwo values, and they explain nothing",
                   fontsize=12.5)

    ax_g.set_ylabel("degradation on real hardware\nTVD(ideal simulation, ibm_fez)")
    for ax in (ax_g, ax_q):
        ax.set_ylim(0, 0.55)
        ax.grid(alpha=0.25, lw=0.7)
        ax.set_axisbelow(True)

    fig.suptitle("We spent a phase optimizing the resource that wasn't the constraint",
                 fontsize=14.5, y=0.98)
    fig.tight_layout(rect=(0, 0.115, 1, 0.94))

    note = (
        "Four QAOA circuits on ibm_fez, 2026-07-11, 4096 shots each (job "
        "d994b5cqp3as739tkvp0). A–D are 2 and 3 time slots at 1 and 2 QAOA layers.\n"
        "Each two-qubit gate is a physical operation with an error rate (~0.3% median "
        "on this device) and errors compound, so gates cost every time; an idle qubit "
        "costs little.\n"
        "What it changed: the 6-slot target needs ~269 gates even with the encoding we "
        "built to save qubits — worse than D, which returned essentially no signal. No "
        "encoding makes it submittable."
    )
    fig.text(0.5, 0.012, note, ha="center", fontsize=8.7, color="0.4")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    for circuit, tvd in zip(CIRCUITS, degradation):
        print(f"  {circuit['tag']}  T={circuit['T']} reps={circuit['reps']}  "
              f"{circuit['qubits']:>2} qubits  {circuit['gates']:>3} gates  "
              f"TVD(sim,hw) = {tvd:.4f}  [reproduces LESSONS §2's "
              f"{circuit['published']:.3f}]")
    print(f"  gate count spans {gates.max() / gates.min():.1f}×; "
          f"the two 6-qubit circuits differ by {100 * (y[1] / y[0] - 1):.0f}%")


if __name__ == "__main__":
    main()
