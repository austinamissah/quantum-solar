"""Reopen the encoding gate with iterations-per-restart as a rung.

Pre-registered in ``docs/plans/optimizer-budget-study.md`` — read that first.
Every threshold, arm, seed and analysis rule is fixed there; nothing here may be
re-chosen after seeing output.

The question it reopens was closed because "reps=2 ideal mass saturated at ~0.075
against a required 0.078125". That saturation was the evaluation **budget**: every
COBYLA arm in the original study ran at >=99% of its own cap, and the ladder
varied ``n_starts`` only, with ``maxiter`` fixed at 200 on every rung. Restarts and
iterations do different things — more restarts sample more basins, more iterations
descend further into the one you are in — so the axis that was never varied is
also the one that plausibly mattered.

Two arm families:
  (A) iterations ladder   — n_starts fixed at 5, maxiter varied. Isolates the
                            untested axis. `s5_m200` IS the original `cobyla-5`.
  (B) matched-cap split   — cap fixed at 10,000 evaluations, allocated
                            differently. Isolates allocation from total budget.
                            `s50_m200` IS the original `cobyla-50`.

Two arms reproduce original rungs by construction, which is the harness check: if
they do not reproduce the original numbers, the comparison is void and the script
says so rather than reporting.

Run::

    python scripts/optimizer_budget_study.py [--instance-seeds 1] [--arms all]
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

warnings.filterwarnings("ignore")

from optimizer_study import (  # noqa: E402
    ALPHAS,
    BAR,
    PRIMARY_INSTANCE,
    RELIABLE_FRACTION,
    TUNING_SEEDS,
    Objective,
    build_instance,
    multistart,
)

# --- Fixed by the pre-registration -------------------------------------------
# (label, n_starts, maxiter, family, reproduces)
ARM_SPECS = [
    ("s5_m200",   5,  200, "A", "cobyla-5"),
    ("s5_m1000",  5, 1000, "A", ""),
    ("s5_m5000",  5, 5000, "A", ""),
    ("s50_m200", 50,  200, "B", "cobyla-50"),
    ("s10_m1000", 10, 1000, "B", ""),
    ("s2_m5000",  2, 5000, "B", ""),
]
ARMS = {a[0]: a for a in ARM_SPECS}

# Original study's published means on the PRIMARY instance, for the harness check.
# {(arm, alpha): mean ideal mass}. From docs/results/slack-free-encoding.md.
ORIGINAL_MEANS = {
    ("s5_m200", 0.021): 0.06071, ("s5_m200", 0.030): 0.05895,
    ("s50_m200", 0.021): 0.07488, ("s50_m200", 0.030): 0.07500,
}
HARNESS_TOL = 5e-4          # published to 5 d.p.; this is generous against that

CSV_PATH = (Path(__file__).resolve().parent.parent / "docs" / "results"
            / "optimizer_budget.csv")
FIELDS = ["instance_seed", "alpha", "arm", "n_starts", "maxiter", "eval_cap",
          "family", "tuning_seed", "ideal_mass", "achieved_H", "evals",
          "censored", "seconds"]


def run_arm(label, qubo, mask, tuning_seed):
    """One (arm, tuning seed) run. Returns (mass, <H>, evals, seconds)."""
    _, n_starts, maxiter, _, _ = ARMS[label]
    rng = np.random.default_rng(tuning_seed)
    obj = Objective(qubo, reps=2, seed=tuning_seed)
    t0 = time.perf_counter()
    params = multistart(obj.shot, obj.ansatz.num_parameters, rng, n_starts,
                        "COBYLA", maxiter=maxiter)
    seconds = time.perf_counter() - t0
    # obj.exact() increments the counter, so read the optimization spend first.
    evals = obj.evaluations
    return obj.mass(params, mask), obj.exact(params), evals, seconds


def check_harness(rows):
    """Verify the two reproduced arms match their published means.

    A drifted harness makes every comparison meaningless, so this gates the
    report rather than annotating it.
    """
    problems = []
    for (arm, alpha), expected in ORIGINAL_MEANS.items():
        got = [r["ideal_mass"] for r in rows
               if r["arm"] == arm and r["alpha"] == alpha
               and r["instance_seed"] == PRIMARY_INSTANCE]
        if not got:
            continue
        mean = float(np.mean(got))
        ok = abs(mean - expected) <= HARNESS_TOL
        print(f"  harness check  {arm:<10} alpha={alpha}: got {mean:.5f}, "
              f"original {expected:.5f}  {'OK' if ok else 'MISMATCH'}")
        if not ok:
            problems.append(f"{arm}@{alpha}: {mean:.5f} vs {expected:.5f}")
    return problems


def verdict_for(cell_rows):
    """Pre-registered verdict for one (instance, alpha) cell."""
    best = None
    for label, *_ in ARM_SPECS:
        m = np.array([r["ideal_mass"] for r in cell_rows if r["arm"] == label])
        if not m.size:
            continue
        clears = int((m >= BAR).sum())
        passed = m.mean() >= BAR
        reliable = clears >= RELIABLE_FRACTION * len(m)
        rank = (2 if passed and reliable else 1 if passed else 0)
        if best is None or rank > best[0]:
            best = (rank, label)
    return {2: "REOPENED-AND-CLEARED", 1: "PARTIAL",
            0: "CONFIRMED-CLOSED"}[best[0] if best else 0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instance-seeds", default=str(PRIMARY_INSTANCE))
    ap.add_argument("--arms", default="all")
    args = ap.parse_args()
    labels = ([a[0] for a in ARM_SPECS] if args.arms == "all"
              else args.arms.split(","))

    print(f"bar = {BAR:.6f} (5x uniform, m=6)   tuning seeds = {list(TUNING_SEEDS)}")
    print(f"reliable = clears on >= {int(RELIABLE_FRACTION * len(TUNING_SEEDS))}/"
          f"{len(TUNING_SEEDS)} seeds", flush=True)
    print("NOTE: s5_m200 and s50_m200 reproduce the original cobyla-5 / cobyla-50 "
          "rungs; they gate the report.\n", flush=True)

    rows = []
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writeheader()

    for instance_seed in [int(s) for s in args.instance_seeds.split(",")]:
        role = "PRIMARY" if instance_seed == PRIMARY_INSTANCE else "robustness"
        for alpha in ALPHAS:
            _, qubo, mask = build_instance(instance_seed, alpha)
            print(f"=== instance seed {instance_seed} ({role})  alpha={alpha} ===",
                  flush=True)
            print(f"{'arm':<11} {'cap':>7} {'mean':>9} {'sd':>8} {'min':>8} "
                  f"{'max':>8} {'clears':>7} {'evals':>8} {'cens':>5} "
                  f"{'verdict':>18}", flush=True)
            for label in labels:
                _, n_starts, maxiter, family, _ = ARMS[label]
                cap = n_starts * maxiter
                masses, evals, secs = [], [], []
                for tuning_seed in TUNING_SEEDS:
                    mass, energy, ev, sec = run_arm(label, qubo, mask, tuning_seed)
                    row = {
                        "instance_seed": instance_seed, "alpha": alpha,
                        "arm": label, "n_starts": n_starts, "maxiter": maxiter,
                        "eval_cap": cap, "family": family,
                        "tuning_seed": tuning_seed, "ideal_mass": mass,
                        "achieved_H": energy, "evals": ev,
                        "censored": bool(ev == cap), "seconds": sec,
                    }
                    rows.append(row)
                    with open(CSV_PATH, "a", newline="") as f:
                        csv.DictWriter(f, fieldnames=FIELDS).writerow(row)
                    masses.append(mass)
                    evals.append(ev)
                    secs.append(sec)
                m = np.array(masses)
                clears = int((m >= BAR).sum())
                passed = m.mean() >= BAR
                reliable = clears >= RELIABLE_FRACTION * len(m)
                v = ("PASS+RELIABLE" if passed and reliable
                     else "PASS (unreliable)" if passed else "fail")
                n_cens = sum(1 for e in evals if e == cap)
                print(f"{label:<11} {cap:>7} {m.mean():>9.5f} "
                      f"{m.std(ddof=1):>8.5f} {m.min():>8.5f} {m.max():>8.5f} "
                      f"{clears:>4}/{len(m)} {int(np.mean(evals)):>8} "
                      f"{n_cens:>3}/10 {v:>18}", flush=True)
            print(flush=True)

    print(f"wrote {len(rows)} runs -> {CSV_PATH}\n", flush=True)
    print("Harness check (reproduced arms vs the original study's published means):")
    problems = check_harness(rows)
    if problems:
        print("\nHARNESS MISMATCH — the comparison is VOID, not merely noisy:")
        for p in problems:
            print(f"  {p}")
        print("Refusing to report a verdict.", flush=True)
        raise SystemExit(2)

    print("\nPre-registered verdicts (PRIMARY instance only decides):")
    for instance_seed in sorted({r["instance_seed"] for r in rows}):
        for alpha in ALPHAS:
            cell = [r for r in rows if r["instance_seed"] == instance_seed
                    and r["alpha"] == alpha]
            if cell:
                tag = "PRIMARY" if instance_seed == PRIMARY_INSTANCE else "secondary"
                print(f"  instance {instance_seed} ({tag}) alpha={alpha}: "
                      f"{verdict_for(cell)}")


if __name__ == "__main__":
    main()
