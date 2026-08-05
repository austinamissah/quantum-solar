"""Census and cap-lift analysis for the QAOA evaluation-budget censoring question.

`qaoa_evals` counts COBYLA function evaluations summed over restarts, and COBYLA's
`maxiter` caps evaluations *per restart*, so the total is bounded by
`n_starts * maxiter`. A total sitting exactly on that bound is not a measurement of
optimizer effort -- it is the budget, and any ratio built from it is a lower bound.

This script answers three questions, in the order fixed by
`docs/plans/eval-censoring.md`:

  (a) how many cells sit exactly at the cap, per weight mode, broken down by T/reps;
  (b) what the alpha*-vs-default eval ratio is, and whether either side is censored;
  (c) whether lifting the cap moves `ideal_opt_mass` -- the question that decides
      whether the alpha* sweep's mass values are estimates or lower bounds.

Usage:
    python scripts/eval_censoring.py                 # census only
    python scripts/eval_censoring.py --lift          # census + paired cap-lift table
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from experiment_scaling import N_STARTS, RESULTS_DIR, load_results

CENSUS_CSVS = {
    "default": RESULTS_DIR / "qaoa_scaling_T5.csv",
    "alphastar": RESULTS_DIR / "qaoa_scaling_alphastar_T5.csv",
}
LIFT_CSVS = {
    "default": RESULTS_DIR / "qaoa_scaling_T5_maxiter1000.csv",
    "alphastar": RESULTS_DIR / "qaoa_scaling_alphastar_T5_maxiter1000.csv",
}

# Pre-registered threshold (docs/plans/eval-censoring.md): a median relative move
# in ideal_opt_mass above this means the cap bound the RESULT, not just the count.
MASS_MOVE_THRESHOLD = 0.10


def _cap(rows) -> int:
    """The eval ceiling implied by the rows' own recorded settings."""
    caps = {r["n_starts"] * r["maxiter"] for r in rows}
    if len(caps) != 1:
        raise SystemExit(f"rows mix eval caps {caps}; refusing to pool them")
    return caps.pop()


def census(mode_rows: dict[str, list]) -> None:
    print("=" * 74)
    print("(a) CENSUS -- cells sitting exactly at the evaluation cap")
    print("=" * 74)
    for mode, rows in mode_rows.items():
        cap = _cap(rows)
        cens = [r for r in rows if r["qaoa_evals"] == cap]
        print(f"\n  weight={mode}  cap = {N_STARTS} starts x {rows[0]['maxiter']} "
              f"maxiter = {cap} evals")
        print(f"  CENSORED: {len(cens)}/{len(rows)} cells at exactly {cap}")
        Ts = sorted({r["T"] for r in rows})
        reps_vals = sorted({r["reps"] for r in rows})
        print("    " + "reps".ljust(6) + "".join(f"T={T}".rjust(9) for T in Ts)
              + "   (n censored / n cells)")
        for reps in reps_vals:
            cells = "".join(
                f"{sum(1 for r in rows if r['T'] == T and r['reps'] == reps and r['qaoa_evals'] == cap)}"
                f"/{sum(1 for r in rows if r['T'] == T and r['reps'] == reps)}".rjust(9)
                for T in Ts)
            print("    " + str(reps).ljust(6) + cells)
        ev = np.array([r["qaoa_evals"] for r in rows], dtype=float)
        print(f"    evals: min={ev.min():.0f} median={np.median(ev):.0f} max={ev.max():.0f}")


def eval_ratio(mode_rows: dict[str, list]) -> None:
    print()
    print("=" * 74)
    print("(b) alpha*-vs-default evaluation ratio, and whether it is censored")
    print("=" * 74)
    d = {(r["T"], r["seed"], r["reps"]): r for r in mode_rows["default"]}
    a = {(r["T"], r["seed"], r["reps"]): r for r in mode_rows["alphastar"]}
    keys = sorted(set(d) & set(a))
    cap_d, cap_a = _cap(mode_rows["default"]), _cap(mode_rows["alphastar"])
    ratios = np.array([a[k]["qaoa_evals"] / d[k]["qaoa_evals"] for k in keys])
    n_a = sum(1 for k in keys if a[k]["qaoa_evals"] == cap_a)
    n_d = sum(1 for k in keys if d[k]["qaoa_evals"] == cap_d)
    print(f"\n  paired cells: {len(keys)}")
    print(f"  mean alpha*/default eval ratio: {ratios.mean():.3f}  "
          f"(median {np.median(ratios):.3f}, range {ratios.min():.3f}-{ratios.max():.3f})")
    print(f"  numerator censored (alpha* at cap):  {n_a}/{len(keys)}")
    print(f"  denominator censored (default at cap): {n_d}/{len(keys)}")
    if n_a and not n_d:
        print("  => ratio is a LOWER BOUND (numerator capped, denominator free)")
    elif n_a and n_d:
        print("  => ratio is INDETERMINATE in direction: BOTH sides capped, so the "
              "ratio\n     tends to 1.0 by construction regardless of the truth")
    elif n_d and not n_a:
        print("  => ratio is an UPPER BOUND (denominator capped, numerator free)")
    else:
        print("  => neither side censored: the ratio is an estimate")


def cap_lift(mode_rows: dict[str, list], lift_rows: dict[str, list]) -> None:
    print()
    print("=" * 74)
    print("(c) CAP LIFT -- paired, same (T, seed, reps, mode), maxiter 200 -> raised")
    print("=" * 74)
    for mode, base in mode_rows.items():
        lifted = lift_rows.get(mode)
        if not lifted:
            continue
        b = {(r["T"], r["seed"], r["reps"]): r for r in base}
        l = {(r["T"], r["seed"], r["reps"]): r for r in lifted}
        keys = sorted(set(b) & set(l))
        cap_b = _cap(base)
        print(f"\n  weight={mode}   {len(keys)} paired cells   "
              f"cap {cap_b} -> {_cap(lifted)}")
        print("    T seed reps | censored |    evals ->  evals |   "
              "ideal_mass ->  ideal_mass |   rel d")
        rel_censored, rel_free = [], []
        for k in keys:
            was = b[k]["qaoa_evals"] == cap_b
            m0, m1 = b[k]["ideal_opt_mass"], l[k]["ideal_opt_mass"]
            rel = (m1 - m0) / m0 if m0 > 0 else float("nan")
            (rel_censored if was else rel_free).append(rel)
            print(f"    {k[0]} {k[1]:4d} {k[2]:4d} | {'YES' if was else ' no':>8} |"
                  f" {b[k]['qaoa_evals']:8d} -> {l[k]['qaoa_evals']:6d} |"
                  f" {m0:12.6f} -> {m1:11.6f} | {rel:+7.1%}")

        def _summary(label, vals):
            if not vals:
                print(f"    {label}: (none)")
                return None
            v = np.abs(np.array(vals, dtype=float))
            v = v[~np.isnan(v)]
            print(f"    {label}: n={len(v)} median |rel change| = {np.median(v):.1%} "
                  f"(max {v.max():.1%})")
            return float(np.median(v))

        print()
        med_c = _summary("cells that WERE at the cap  ", rel_censored)
        _summary("cells that were NOT at the cap (control)", rel_free)
        if med_c is not None:
            verdict = ("the cap bound the EVAL COUNT but not the RESULT; "
                       "mass values stand"
                       if med_c <= MASS_MOVE_THRESHOLD else
                       "the cap bound the RESULT; alpha* mass values are "
                       "themselves LOWER BOUNDS")
            print(f"\n    VERDICT (pre-registered threshold "
                  f"{MASS_MOVE_THRESHOLD:.0%}): {verdict}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lift", action="store_true",
                    help="also load the raised-maxiter CSVs and print the paired table")
    args = ap.parse_args()

    mode_rows = {}
    for mode, path in CENSUS_CSVS.items():
        if Path(path).exists():
            mode_rows[mode] = load_results(path)
        else:
            print(f"missing: {path}")
    if not mode_rows:
        raise SystemExit("no census CSVs found -- run experiment_scaling.py --tag T5")

    census(mode_rows)
    if len(mode_rows) == 2:
        eval_ratio(mode_rows)
    if args.lift:
        lift_rows = {m: load_results(p) for m, p in LIFT_CSVS.items() if Path(p).exists()}
        cap_lift(mode_rows, lift_rows)


if __name__ == "__main__":
    main()
