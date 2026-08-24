# Pre-registration: does the selection rule replicate on fresh instances?

**Status:** registered, not yet run. **Simulator and exact computation only — no QPU.**
Written **2026-08-24**.

## Why this exists

[`selection-rule.md`](../results/selection-rule.md) confirmed that selecting on total
feasible mass beats lowest-`<H>`, and [`selection-rule-scaling.md`](../results/selection-rule-scaling.md)
showed the property surviving to 14 qubits. Both are on record and **neither verdict
can be changed by this study** — their held-out sets were fixed and scored.

What both share is a weakness the first one states plainly: **the only comparison that
actually discriminated between the two rules came from instance 1 — the instance the
rules were fitted on.** The two genuinely held-out instances (2 and 3) turned out
*easy*: best masses 0.08–0.14 against a 0.078125 bar, so every sane rule cleared and
the comparison said nothing.

This runs three fresh instances to find out whether the finding replicates where it
can actually be tested.

## Design, fixed here

**Instances 4, 5 and 6** — seeds never used in any study in this repository, verified
to build at T=3, `checkpoint(3)`, 6 qubits, 7 feasible states, 1 optimum, and sound at
α\*. **reps=2, the full α ladder, N=40**, `n_starts=5`, `maxiter=200`, `shots=4096` —
identical to the study being replicated, so cells are comparable one to one.

Bar = `5 / 2**6` = **0.078125**, unchanged and not up for revision here.

Cost ~45 min per instance.

**The "sound and reproducible" band is α ≤ 0.03**, the same cut
`selection-rule.md` used, fixed before these instances are computed.

## Predictions

**P1 — the argmax property replicates.** Across the sound, reproducible cells of the
three fresh instances, feasible mass selects the **argmax** tuning in **at least 80%**
of cells.

*Falsified below 80%.* It was 9 of 9 and then 4 of 4 in the two prior studies; 80% is
set as a floor that tolerates some failure while still meaning something.

**P2 — it still beats the incumbent.** Across those same cells, feasible mass returns a
tuning whose optimal mass is at least as high as lowest-`<H>`'s in **strictly more
cells than it loses**.

*Falsified if losses ≥ wins.*

**P3 — the discriminating test, if the data supplies one.** Restricted to cells where
lowest-`<H>`'s pick does **not** clear the bar but **some** tuning does — the situation
that made instance 1 informative and instances 2 and 3 useless — feasible mass clears
in **more than half**.

*Falsified if it clears in half or fewer.* **If there are no such cells, P3 is
"not estimable" and will be reported that way** — not quietly dropped, and not
converted into a claim about some other subset. That is what happened to the reps=3
stratum in `eval-censoring.md` and it is the honest outcome when a stratum is empty.

## What would make this uninformative, stated in advance

**If all three fresh instances are easy** — every sound cell clearing under every rule
— then P1 and P2 will likely hold and **P3 will be not estimable, and this study will
have replicated the uninformative half of the original.** That is a real possible
outcome, it is not a failure of the rule, and it will be reported as "no discriminating
evidence found" rather than as support.

Instance hardness cannot be chosen in advance without inspecting the instances, which
would defeat the point. Three were picked to raise the chance that at least one is
hard, not because anything is known about them.

## Procedure

1. `python scripts/basin_study_reps2.py --instance N --tag iN` for N in 4, 5, 6.
2. `python scripts/selection_rule_replication.py` scores every rule on every cell and
   writes `docs/results/selection_rule_replication.json`. It refuses to run unless
   this plan is committed and clean.
3. Results to `docs/results/selection-rule-replication.md`, with P1, P2 and P3 at the
   pinned definitions before any other cut.

## Limitations, recorded in advance

- **Three instances at one depth and one T.** Instance-dependence is documented in
  this project; three more samples is better than two and is not many.
- **Nothing here revisits** `selection-rule.md` or `selection-rule-scaling.md`, whose
  verdicts are fixed, or `optimizer-budget-study.md`, whose verdict concerns arms
  scored on their means.
- **The rules are unchanged.** No new candidate is introduced here; introducing one
  after seeing three more instances would be the fitting problem all over again.
- **No hardware claim.**
