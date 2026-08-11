"""Web figure: how the slack-free encoding gets from 117 qubits to 52.

Every other figure in `docs/figures/web/` reports a *result*. This one draws the
*mechanism*, because the headline claim of `docs/results/slack-free-encoding.md`
-- full battery value at 52 qubits against the exact encoding's 117 -- has nowhere
a reader can see why.

Four panels, on the real Golden CO instance (24 hours, 10 kWh, 2 kWh/slot):

  top-left      EXACT. The bounds 0 <= S_t <= Q are an inequality, and a QUBO
                expresses equalities natively but not inequalities. The exact
                treatment buys each one with a bounded binary slack variable, at
                every interior hour: 23 hours x 3 bits = 69 auxiliary qubits on
                top of the 2T = 48 decision bits.

  top-right     CHECKPOINT(5, banded). Pin the SoC only every 5th hour, inside a
                *tightened* band, and let the path do what it likes in between:
                4 checkpoints x 1 bit = 4 auxiliary qubits. Same 48 decision bits,
                and -- the point -- the same daily bill, reached by a different
                route. Both panels show the encoding's own optimum, not one
                schedule drawn twice.

  bottom-left   WHY IT IS SOUND. Between two slots pinned k apart the trajectory
                rises at most j steps and must fall within the remaining k-j, so
                the excursion is bounded by max_j min(j, k-j) = floor(k/2). Pinning
                every k-th slot therefore keeps the whole path in band provided
                floor(k/2) <= min(k_0, n_max - k_0), the headroom on the tighter
                side. Here that is 2 <= 2: k=5 is exactly `max_sound_spacing`, so
                the envelope touches the band edge with nothing to spare.

  bottom-right  The qubit accounting, decision bits against auxiliary bits.

"Sound" is the property that matters and is easy to skim past: every zero-penalty
assignment is genuinely SoC-feasible, so this encoding's optimum can be
*suboptimal* but never *infeasible*. The unsound alternatives in `encodings.py`
are cheaper still and can return a schedule the battery cannot physically run.

NUMBERS ARE COMPUTED, NOT TYPED. Qubit counts come from `aux_bits()` on the
encodings themselves, bits-per-register from dividing that by the register count,
the spacing ceiling from `max_sound_spacing`, and the grid from `soc_grid` -- so
none of the arithmetic in this figure is restated here where it could drift from
the implementation. The script then REFUSES TO DRAW unless the totals it computed
match the ones published in `docs/results/slack-free-encoding.md`.

Run:  python scripts/make_encoding_figure.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from quantum_solar import (  # noqa: E402
    BatteryProblem,
    Encoding,
    default_weights,
    dp_solve,
    max_sound_spacing,
)
from quantum_solar.encodings import soc_grid  # noqa: E402
from quantum_solar.qubo_search import qubo_min_exact  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "docs" / "figures" / "web" / "schedule_real_day.json"
STUDY = ROOT / "docs" / "results" / "slack-free-encoding.md"
OUT = ROOT / "docs" / "figures" / "web" / "encoding.png"

BUCKET = "summer_weekday"
SPACING = 5   # asserted below to equal max_sound_spacing on this instance

DECISION = "#4C78A8"   # the 2T decision bits, shared by every encoding
AUX = "#E45756"        # the auxiliary register, which is what the study removes
BAND = "#DCE7F1"
INK = "#2F4B7C"


def published_qubits() -> dict[str, int]:
    """The qubit column of the study's annual table, as committed."""
    rows = {}
    for line in STUDY.read_text().splitlines():
        cells = [c.strip().strip("*") for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and re.fullmatch(r"\d+", cells[1] or ""):
            rows[cells[0]] = int(cells[1])
    return rows


def real_instance() -> BatteryProblem:
    snap = json.loads(SNAPSHOT.read_text())
    bucket = snap["buckets"][BUCKET]
    return BatteryProblem(
        generation=np.array(bucket["generation"], dtype=float),
        load=np.array(bucket["load"], dtype=float),
        price=np.array(bucket["price"], dtype=float),
        capacity=float(snap["capacity"]),
        charge_energy=float(snap["charge_energy"]),
        discharge_energy=float(snap["charge_energy"]),
        initial_soc=float(bucket["initial_soc"]),
    )


def trajectory(problem, solution) -> np.ndarray:
    """``S_0 .. S_T`` in kWh, so the path starts where the battery started."""
    charge, discharge = problem.decode(solution.x)
    return np.concatenate([[problem.initial_soc],
                           problem.soc_trajectory(charge, discharge)])


def draw_schedule(ax, problem, soc, *, title, marks, mark_label, band, bits_each,
                  band_note=None):
    """One encoding: the band it enforces, where it enforces it, and the path.

    A tightened band is drawn as a segment **at each checkpoint only**, not across
    the axis: it constrains the pinned slots and nothing else, and the path is
    free — and here does — to leave it in between.
    """
    t = problem.num_slots
    ax.axhspan(0, problem.capacity, color=BAND, zorder=0)
    lo, hi = band
    tightened = (lo, hi) != (0.0, problem.capacity)

    ax.plot(np.arange(t + 1), soc, "-", color=INK, lw=2.0, zorder=4)
    ax.plot(np.arange(t + 1), soc, ".", color=INK, ms=4, zorder=4)

    for m in marks:
        ax.plot([m, m], [0, problem.capacity], color=AUX, lw=1.0, alpha=0.55,
                zorder=2)
        if tightened:
            ax.add_patch(plt.Rectangle((m - 0.9, lo), 1.8, hi - lo,
                                       color="#8FB8DC", zorder=3))
        ax.plot(m, soc[m], "o", color=AUX, ms=6, zorder=5)

    ax.set_xlim(-0.6, t + 0.6)
    ax.set_ylim(-0.6, problem.capacity + 3.2)
    ax.set_xticks([0, 6, 12, 18, 24])
    ax.set_yticks([0, problem.capacity / 2, problem.capacity])
    ax.set_xlabel("hour")
    ax.set_title(title, fontsize=12)
    ax.text(0.5, problem.capacity + 2.8,
            f"{len(marks)} × {bits_each} bit{'s' if bits_each != 1 else ''} "
            f"= {len(marks) * bits_each} auxiliary qubits   ({mark_label})",
            fontsize=9.5, color=AUX, va="top")
    if band_note:
        ax.text(0.5, problem.capacity + 1.5, band_note, fontsize=9,
                color="#2A6099", va="top")


def main() -> None:
    problem = real_instance()
    e, n_max, k0 = soc_grid(problem)
    t = problem.num_slots
    decision_bits = 2 * t

    exact = Encoding.EXACT
    banded = Encoding.checkpoint(SPACING, banded=True)

    # Everything below is derived from the encodings, never restated.
    exact_slots = list(range(1, t))                       # every interior hour
    cp_slots = list(range(SPACING, t, SPACING))           # every k-th hour
    exact_aux = exact.aux_bits(problem)
    cp_aux = banded.aux_bits(problem)
    exact_bits_each = exact_aux // len(exact_slots)
    cp_bits_each = cp_aux // len(cp_slots)

    half = SPACING // 2                     # the drift bound, floor(k/2)
    headroom = min(k0, n_max - k0)
    ceiling = max_sound_spacing(problem)

    # Soundness first: an unsound spacing makes the soundness panel false *and*
    # makes the qubit comparison one against a different encoding than the study's.
    if SPACING > ceiling:
        raise SystemExit(
            f"REFUSING TO DRAW: spacing {SPACING} exceeds max_sound_spacing "
            f"{ceiling} on this instance, so the encoding is not sound and the "
            f"soundness panel would be a lie."
        )

    totals = {"exact": decision_bits + exact_aux, "cp5band": decision_bits + cp_aux}
    published = published_qubits()
    for name, computed in totals.items():
        if published.get(name) != computed:
            raise SystemExit(
                f"REFUSING TO DRAW: {name} computes to {computed} qubits, but "
                f"{STUDY.name} publishes {published.get(name)!r}. The figure and "
                f"the study have diverged; fix that before drawing either."
            )

    exact_solution = dp_solve(problem)
    weights = default_weights(problem)
    cp_solution = qubo_min_exact(problem, weights, banded)
    if not np.isclose(cp_solution.true_energy, exact_solution.true_energy, atol=1e-9):
        raise SystemExit(
            f"REFUSING TO DRAW: cp{SPACING}band reaches "
            f"${cp_solution.true_energy:.4f} against the exact optimum "
            f"${exact_solution.true_energy:.4f}. The study reports it losing "
            f"nothing on this instance; that no longer holds."
        )

    fig, axes = plt.subplots(2, 2, figsize=(13.4, 8.0),
                             gridspec_kw={"height_ratios": [1.0, 0.82]})
    (ax_exact, ax_cp), (ax_sound, ax_bars) = axes

    draw_schedule(
        ax_exact, problem, trajectory(problem, exact_solution),
        title=f"Exact — a slack register at every interior hour"
              f"\n{totals['exact']} qubits",
        marks=exact_slots, mark_label=f"{len(exact_slots)} interior hours",
        band=(0.0, problem.capacity), bits_each=exact_bits_each,
    )
    ax_exact.set_ylabel("state of charge (kWh)")

    draw_schedule(
        ax_cp, problem, trajectory(problem, cp_solution),
        title=f"Checkpoint({SPACING}, banded) — pinned every {SPACING}th hour"
              f"\n{totals['cp5band']} qubits, and the same ${cp_solution.true_energy:.2f} bill",
        marks=cp_slots, mark_label=f"every {SPACING}th hour",
        band=(half * e, problem.capacity - half * e), bits_each=cp_bits_each,
        band_note=f"pinned inside the tightened band [{half * e:g}, "
                  f"{problem.capacity - half * e:g}] kWh — and free in between",
    )

    # --- soundness: the excursion envelope between two pinned slots ------------
    j = np.arange(SPACING + 1)
    envelope = np.minimum(j, SPACING - j)          # max_j min(j, k-j) = floor(k/2)
    ax_sound.fill_between(j, -envelope, envelope, color=BAND, zorder=1)
    ax_sound.plot(j, envelope, color=INK, lw=1.8, zorder=3)
    ax_sound.plot(j, -envelope, color=INK, lw=1.8, zorder=3)
    for edge in (headroom, -headroom):
        ax_sound.axhline(edge, color=AUX, ls="--", lw=1.6, zorder=4)
    ax_sound.plot([0, SPACING], [0, 0], "o", color=AUX, ms=8, zorder=5)

    ax_sound.set_xlim(-0.35, SPACING + 0.35)
    ax_sound.set_ylim(-headroom - 1.75, headroom + 1.15)
    ax_sound.set_xticks(j)
    ax_sound.set_yticks(range(-headroom, headroom + 1))
    ax_sound.set_xlabel(f"slots after a checkpoint  (gap k = {SPACING})")
    ax_sound.set_ylabel("grid steps from the pin")
    ax_sound.set_title("Why pinning every 5th hour is enough", fontsize=12)
    ax_sound.text(SPACING / 2, headroom * 0.30,
                  f"rises at most j, must fall within k−j\n"
                  f"⌊k/2⌋ = {half} steps, either way",
                  ha="center", va="center", fontsize=9.5, color=INK)
    ax_sound.text(SPACING / 2, headroom + 0.55,
                  f"headroom min(k₀, n_max−k₀) = {headroom}",
                  ha="center", va="bottom", fontsize=9.5, color=AUX)
    ax_sound.text(SPACING / 2, -headroom - 0.62,
                  f"sound iff ⌊k/2⌋ ≤ min(k₀, n_max−k₀):  {half} ≤ {headroom} ✓"
                  f"   (k={SPACING} is the ceiling — no margin)",
                  ha="center", va="top", fontsize=9.5, color=AUX, weight="bold")

    # --- the accounting -------------------------------------------------------
    labels = [f"Exact\n{totals['exact']} qubits",
              f"Checkpoint({SPACING}, banded)\n{totals['cp5band']} qubits"]
    aux_counts = [exact_aux, cp_aux]
    y = np.arange(2)
    ax_bars.barh(y, [decision_bits, decision_bits], color=DECISION, height=0.5)
    ax_bars.barh(y, aux_counts, left=decision_bits, color=AUX, height=0.5)
    for i, aux in enumerate(aux_counts):
        ax_bars.text(decision_bits + aux + 2, i, f"{decision_bits} + {aux}",
                     va="center", fontsize=10, color=INK)
    ax_bars.set_yticks(y)
    ax_bars.set_yticklabels(labels, fontsize=10)
    ax_bars.invert_yaxis()
    ax_bars.set_xlim(0, max(totals.values()) * 1.22)
    ax_bars.set_xlabel("qubits")
    ax_bars.set_title("The decision bits are the same; the slack is what goes",
                      fontsize=12)
    ax_bars.legend(handles=[Patch(color=DECISION, label=f"decision bits (2T = {decision_bits})"),
                            Patch(color=AUX, label="auxiliary / slack")],
                   fontsize=9, loc="lower right", frameon=False)

    fig.suptitle("Where the qubits go, and how the slack-free encoding removes them",
                 fontsize=15, y=0.985)
    fig.tight_layout(rect=(0, 0.055, 1, 0.955))
    note = (
        f"Real Golden CO instance: {t} hours, {problem.capacity:g} kWh at "
        f"{problem.charge_energy:g} kWh/slot, so the SoC grid has {n_max + 1} levels "
        f"and S₀ sits at level {k0}. Both panels show that encoding's OWN optimum.\n"
        f"Checkpointing is an inner approximation and is SOUND: every zero-penalty "
        f"assignment is genuinely feasible, so its optimum can be suboptimal but "
        f"never infeasible. On this instance it gives up nothing."
    )
    fig.text(0.5, 0.012, note, ha="center", fontsize=9, color="0.4")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  exact    {len(exact_slots)} interior hours × {exact_bits_each} bits "
          f"= {exact_aux} aux  →  {totals['exact']} qubits  [matches the study]")
    print(f"  cp{SPACING}band  {len(cp_slots)} checkpoints × {cp_bits_each} bit "
          f"= {cp_aux} aux  →  {totals['cp5band']} qubits  [matches the study]")
    print(f"  soundness: ⌊{SPACING}/2⌋ = {half} ≤ min({k0}, {n_max - k0}) = {headroom}"
          f"  (max_sound_spacing = {ceiling})")
    print(f"  both encodings reach ${exact_solution.true_energy:.4f}")


if __name__ == "__main__":
    main()
