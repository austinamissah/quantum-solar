"""Regenerate the web-facing mass-ratio figure (docs/figures/web/mass_ratio.png).

Reads the committed results CSV only (docs/results/qaoa_scaling.csv) via
experiment_scaling.load_results and re-renders the mass-ratio chart with
non-technical framing and blog-readable fonts. The underlying numbers are
identical to the experiment; no experiments are re-run.

This deliberately writes to docs/figures/web/ (curated figures), NOT to
docs/results/ (which experiment_scaling.make_all_plots regenerates on a full
sweep). Separate paths guarantee a future sweep can never overwrite this polished,
honesty-annotated figure with the plain experiment version.

Presentation choices that keep the picture honest at a glance:
  - Points where at least one seed's optimal mass fell below the 1/4096 shot-noise
    floor are only UPPER LIMITS. They are drawn as unconnected hollow markers with
    a downward arrow (the standard upper-limit convention) and are NEVER joined by
    lines. Earlier dashed lines through these points rose steeply to the right and
    read as "advantage grows with scale" - the exact misreading to avoid. The
    ceilings rise only because the uniform baseline shrinks exponentially with
    qubits, inflating what 4096 shots could even detect; the real signal there is
    unmeasurable, not large.
  - The all-upper-limit region is shaded and labeled "too small to measure".
  - The y-axis is capped near 10 so the inflated large-size ceilings do not
    dominate the frame. Any upper limit above the cap is drawn at the cap with its
    arrow (its true ceiling is off-scale and meaningless).

Caption suggestion (for the blog post):
  This chart asks a simple question: does the quantum optimizer (QAOA) find the
  best battery schedule more often than random guessing? Points above the dashed
  grey line beat random; points on it are no better than chance. Only at the
  smallest problem (2 slots, filled dots) do all our runs place enough
  probability on the best answer to measure this directly, and even there the
  result is mixed: a modest edge at 1 and 3 layers, but worse than random at 2.
  For every larger problem, at least one run's success falls below the resolution
  of 4096 samples, so those values are only upper limits (hollow markers with
  downward arrows in the shaded band) and cannot confirm any advantage; some
  ceilings are off the top of the chart and are drawn at the cap. The honest
  takeaway: a small, depth-dependent edge at the smallest size, and no measurable
  quantum advantage as the problem scales up.

  Each "layer" is one round of the quantum algorithm's shaping process - more
  layers can sharpen the answer in theory, but they also add more settings to tune
  (and, on real hardware, more noise). That is also why deeper is not always
  better in the data itself: each layer adds tunable angles for the classical
  optimizer to set, and it can land badly - which is why the 2-layer point at 2
  slots sits below the 1-layer one.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experiment_scaling as exp  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "figures" / "web" / "mass_ratio.png"
Y_CAP = 10.0  # inflated large-size ceilings are clamped here


def _draw_upper_limit(ax, x, y, color):
    """Hollow marker with a short downward arrow (upper-limit convention)."""
    clamped = y > Y_CAP
    yv = 0.92 * Y_CAP if clamped else y
    ax.plot([x], [yv], marker="o", markersize=8, markerfacecolor="white",
            markeredgecolor=color, markeredgewidth=1.8, linestyle="none", zorder=5)
    ax.annotate("", xy=(x, yv / 1.75), xytext=(x, yv / 1.06),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.5), zorder=5)
    return clamped


def main():
    rows = [r for r in exp.load_results() if not np.isnan(r.get("mass_ratio", float("nan")))]
    slot_counts = sorted({r["T"] for r in rows})
    layer_counts = sorted({r["reps"] for r in rows})
    colors = {reps: f"C{i}" for i, reps in enumerate(layer_counts)}

    fig, ax = plt.subplots(figsize=(7.8, 5.2))

    # For each T, is every layer count only an upper limit? (the unmeasurable region)
    all_bound_T = []
    for T in slot_counts:
        groups = [[r for r in rows if r["T"] == T and r["reps"] == reps] for reps in layer_counts]
        groups = [g for g in groups if g]
        if groups and all(any(r["mass_ratio_is_upper_bound"] for r in g) for g in groups):
            all_bound_T.append(T)

    if all_bound_T:
        ax.axvspan(min(all_bound_T) - 0.5, max(all_bound_T) + 0.5,
                   color="0.5", alpha=0.1, zorder=0)
        ax.text((min(all_bound_T) + max(all_bound_T)) / 2, 0.055,
                "too small to measure with 4,096 shots",
                ha="center", va="bottom", fontsize=10, style="italic", color="0.4")

    clamped_any = False
    for reps in layer_counts:
        color = colors[reps]
        dodge = (reps - np.mean(layer_counts)) * 0.10
        measured = []
        for T in slot_counts:
            group = [r for r in rows if r["T"] == T and r["reps"] == reps]
            if not group:
                continue
            y = float(np.mean([r["mass_ratio"] for r in group]))
            x = T + dodge
            if any(r["mass_ratio_is_upper_bound"] for r in group):
                clamped_any |= _draw_upper_limit(ax, x, y, color)
            else:
                measured.append((x, y))
        if measured:  # solid measured points, joined only to each other
            xs, ys = zip(*measured)
            ax.plot(xs, ys, color=color, marker="o", markersize=8, linewidth=2, zorder=4)

    # Parity reference.
    ax.axhline(1.0, color="0.35", linestyle="--", linewidth=1.4, zorder=1)
    ax.text(slot_counts[-1] + 0.45, 1.0, "no better\nthan random", color="0.35",
            fontsize=10, ha="right", va="center")

    ax.set_yscale("log")
    ax.set_ylim(0.03, Y_CAP)
    ax.set_xlim(slot_counts[0] - 0.6, slot_counts[-1] + 0.6)
    ax.set_xticks(slot_counts)
    ax.set_xticklabels([f"{T} slots\n{4 * T - 2} qubits" for T in slot_counts], fontsize=11)
    ax.tick_params(axis="y", labelsize=11)
    ax.set_xlabel("problem size", fontsize=13, labelpad=8)
    ax.set_ylabel("optimal-answer probability\n(quantum vs random guessing)", fontsize=13)
    ax.set_title("Quantum method vs random guessing", fontsize=16, pad=26)
    ax.text(0.5, 1.03,
            "layers = rounds of the quantum shaping process; more can sharpen the "
            "answer but add settings to tune",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=9.5, color="0.4")

    handles = [Line2D([], [], color=colors[reps], marker="o", linestyle="none",
                      markersize=8, label=f"{reps} layer" + ("s" if reps > 1 else ""))
               for reps in layer_counts]
    handles.append(Line2D([], [], marker="o", markerfacecolor="white", markeredgecolor="0.4",
                          linestyle="none", markersize=8, label="upper limit (unmeasurable)"))
    ax.legend(handles=handles, fontsize=9, loc="upper left", framealpha=0.92)

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=147, bbox_inches="tight")  # ~1140 px wide
    print(f"wrote {OUT}  (off-scale upper limits clamped: {clamped_any})")


if __name__ == "__main__":
    main()
