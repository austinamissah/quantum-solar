"""Can any selection rule find the clearing basin?

Pre-registered in ``docs/plans/selection-rule.md`` — read that first. The candidate
rules, the held-out cells, both predictions and their falsification criteria are fixed
by that document.

Simulator and exact computation only. No QPU. Re-runs in seconds: every distribution
was already computed by ``basin_study_reps2.py`` and is read from its ``.npz``.

**The discovery cell is excluded by construction, not by remembering to.** The
candidate rules were chosen by looking at instance 1 at α\\* and that cell cannot be
evidence for them, so it is filtered out here and its exclusion is asserted.

    python scripts/selection_rule_study.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

warnings.filterwarnings("ignore")

import experiment_hardware as hw  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs" / "results"
PLAN = ROOT / "docs" / "plans" / "selection-rule.md"

BAR = 5 / 2**6
ALPHA_STAR = 0.021
DISCOVERY_CELL = (1, ALPHA_STAR)          # instance 1 at α*, where the rules were picked
HELD_OUT_INSTANCES = (2, 3)               # fixed before either was computed
WEAKER_INSTANCE = 1                       # same instance as discovery; reported apart

#: Distribution files per instance, as `basin_study_reps2.py` names them.
NPZ = {1: "basin_distributions_reps2.npz",
       2: "basin_distributions_reps2_i2.npz",
       3: "basin_distributions_reps2_i3.npz"}


def require_registered() -> str:
    """Refuse to run unless the plan is committed and clean."""
    if not PLAN.exists():
        raise SystemExit(f"REFUSING TO RUN: {PLAN.relative_to(ROOT)} does not exist.")
    out = subprocess.run(
        ("git", "-C", str(ROOT), "log", "--format=%H", "-1", "--", str(PLAN)),
        capture_output=True, text=True).stdout.strip()
    if not out:
        raise SystemExit(
            "REFUSING TO RUN: the pre-registration is not committed. The candidate "
            "rules were fitted on 40 points, so this study's only claim to be a "
            "confirmation is that its criteria were fixed first."
        )
    if subprocess.run(("git", "-C", str(ROOT), "status", "--porcelain", "--", str(PLAN)),
                      capture_output=True, text=True).stdout.strip():
        raise SystemExit("REFUSING TO RUN: the pre-registration has uncommitted edits.")
    return out


# --- the rules ------------------------------------------------------------------
#
# Every rule maps a distribution to a score that is MAXIMISED. All are computable
# from the circuit's own output; none needs the optimum handed to it, and the one
# that identifies the optimum does so the way a practitioner would -- by decoding
# samples, keeping the feasible ones and taking the cheapest.


def rules(feas_mask, energies):
    def entropy(p):
        q = np.clip(p, 1e-300, None)
        return float((q * np.log(q)).sum())        # negated: lower entropy scores higher

    feasible_energies = energies[feas_mask]
    cheapest_feasible = int(np.flatnonzero(feas_mask)[int(np.argmin(feasible_energies))])

    return {
        "lowest_H": lambda p: -float(p @ energies),
        "lowest_entropy": entropy,
        "max_probability": lambda p: float(p.max()),
        "lowest_participation": lambda p: -float(1 / np.square(p).sum()),
        "feasible_mass": lambda p: float(p[feas_mask].sum()),
        "best_feasible_mass": lambda p: float(p[cheapest_feasible]),
        "lowest_H_variance": lambda p: -float(p @ (energies**2) - (p @ energies) ** 2),
    }


def cells():
    """Every (instance, α) cell, with its distributions, masses and soundness."""
    for instance, name in NPZ.items():
        path = RESULTS / name
        if not path.exists():
            raise SystemExit(f"REFUSING TO RUN: {path.relative_to(ROOT)} is missing.")
        store = np.load(path)
        alphas = sorted({float(k.split("_")[0][1:]) for k in store.files})
        for alpha in alphas:
            problem, qubo, _ = hw.build_target(3, instance, 2,
                                               encoding="checkpoint3", alpha=alpha)
            opt_mask, feas_mask = hw.basis_masks(problem, qubo)
            X = hw.enumerate_bitstrings(qubo.num_vars).astype(float)
            energies = np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset
            qubo_min = np.flatnonzero(np.isclose(energies, energies.min()))
            yield {
                "instance": instance,
                "alpha": alpha,
                "dists": store[f"a{alpha}_d"],
                "masses": store[f"a{alpha}_m"],
                "sound": bool(feas_mask[qubo_min].all() and opt_mask[qubo_min].any()),
                "feas_mask": feas_mask,
                "energies": energies,
            }


def evaluate(cell):
    """Which tuning each rule selects, and what mass that tuning actually has."""
    scored = {}
    for name, score in rules(cell["feas_mask"], cell["energies"]).items():
        values = np.array([score(p) for p in cell["dists"]])
        pick = int(np.argmax(values))
        scored[name] = {"picked_seed": pick + 1,
                        "picked_mass": float(cell["masses"][pick]),
                        "picked_clears": bool(cell["masses"][pick] >= BAR)}
    return scored


def main():
    commit = require_registered()
    print(f"Pre-registration committed at {commit[:12]} — proceeding.\n")

    records = []
    for cell in cells():
        key = (cell["instance"], cell["alpha"])
        record = {
            "instance": cell["instance"], "alpha": cell["alpha"],
            "sound": cell["sound"],
            "any_clears": bool((cell["masses"] >= BAR).any()),
            "best_mass": float(cell["masses"].max()),
            "is_discovery_cell": key == DISCOVERY_CELL,
            "rules": evaluate(cell),
        }
        records.append(record)

    held_out = [r for r in records if r["instance"] in HELD_OUT_INSTANCES]
    weaker = [r for r in records if r["instance"] == WEAKER_INSTANCE
              and not r["is_discovery_cell"]]
    assert all(not r["is_discovery_cell"] for r in held_out), "discovery cell leaked in"
    assert sum(r["is_discovery_cell"] for r in records) == 1, "discovery cell not found"

    def verdicts(pool, label):
        sound = [r for r in pool if r["sound"]]
        wins = sum(1 for r in sound
                   if r["rules"]["feasible_mass"]["picked_mass"]
                   > r["rules"]["lowest_H"]["picked_mass"])
        losses = sum(1 for r in sound
                     if r["rules"]["feasible_mass"]["picked_mass"]
                     < r["rules"]["lowest_H"]["picked_mass"])
        clearable = [r for r in sound if r["any_clears"]]
        found = sum(1 for r in clearable if r["rules"]["feasible_mass"]["picked_clears"])
        incumbent = sum(1 for r in clearable if r["rules"]["lowest_H"]["picked_clears"])
        return {
            "pool": label, "sound_cells": len(sound),
            "P1_wins": wins, "P1_losses": losses, "P1_ties": len(sound) - wins - losses,
            "P1_falsified": wins <= losses,
            "P2_cells_with_a_clearing_tuning": len(clearable),
            "P2_feasible_mass_found_one": found,
            "P2_lowest_H_found_one": incumbent,
            "P2_falsified": not (clearable and found > len(clearable) / 2),
        }

    result = {
        "_source": "Generated by scripts/selection_rule_study.py; pre-registered in "
                   "docs/plans/selection-rule.md. Simulator only, no QPU.",
        "plan_commit": commit,
        "bar": BAR, "alpha_star": ALPHA_STAR,
        "discovery_cell": {"instance": DISCOVERY_CELL[0], "alpha": DISCOVERY_CELL[1]},
        "held_out_instances": list(HELD_OUT_INSTANCES),
        "verdicts": verdicts(held_out, "held-out (instances 2 and 3)"),
        "weaker_evidence": verdicts(weaker, "instance 1, other sound rungs"),
        "per_rule_held_out": {},
        "cells": records,
    }

    # Every rule scored the same way, so the comparison is not one-sided.
    sound_held = [r for r in held_out if r["sound"]]
    clearable = [r for r in sound_held if r["any_clears"]]
    for name in records[0]["rules"]:
        result["per_rule_held_out"][name] = {
            "mean_picked_mass": float(np.mean([r["rules"][name]["picked_mass"]
                                               for r in sound_held])),
            "clearing_cells_found": sum(1 for r in clearable
                                        if r["rules"][name]["picked_clears"]),
            "of": len(clearable),
        }

    out = RESULTS / "selection_rule.json"
    out.write_text(json.dumps(result, indent=1) + "\n")

    v = result["verdicts"]
    print(f"HELD-OUT: {v['sound_cells']} sound cells on instances {HELD_OUT_INSTANCES}")
    print(f"  P1  feasible_mass vs lowest_H:  {v['P1_wins']} wins, "
          f"{v['P1_losses']} losses, {v['P1_ties']} ties  -> "
          f"{'FALSIFIED' if v['P1_falsified'] else 'held'}")
    print(f"  P2  clearing tuning found in {v['P2_feasible_mass_found_one']}"
          f"/{v['P2_cells_with_a_clearing_tuning']} cells "
          f"(lowest_H: {v['P2_lowest_H_found_one']})  -> "
          f"{'FALSIFIED' if v['P2_falsified'] else 'held'}")
    print(f"\n{'rule':<24}{'mean picked mass':>18}{'clearing cells found':>22}")
    for name, r in sorted(result["per_rule_held_out"].items(),
                          key=lambda kv: -kv[1]["mean_picked_mass"]):
        found = f"{r['clearing_cells_found']}/{r['of']}"
        print(f"{name:<24}{r['mean_picked_mass']:>18.5f}{found:>22}")
    print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
