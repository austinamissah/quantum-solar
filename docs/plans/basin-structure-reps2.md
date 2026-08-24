# Pre-registration: does the single-basin regime survive a second QAOA layer?

**Status:** registered, not yet run. **Simulator and exact computation only — no QPU
is spent by this study and none is requested by it.**

Written **2026-08-23**, before the sweep runs. Everything below is fixed here first.
Prior observations that bear on the predictions are disclosed in full under
"Disclosed", and nothing else was looked at.

This extends [`basin-structure.md`](basin-structure.md), which mapped basin count
against α at **reps=1** on the hardware instance. That study says explicitly that its
result does **not** transfer here, and it is right: reps=2 doubles the parameter
count, and the one open question in the project lives at reps=2.

## The two questions

1. **Does the single-basin regime survive?** At reps=1, basin count is 1 at α\* and
   at every α below it. Is that still true with four angles instead of two?
2. **Does any basin clear the bar?** The reps=1 study states as a limitation that it
   does *not* address whether any basin reaches **0.078125** (5 × uniform at m=6).
   This one does, because that is the project's open question.

These are separate and are reported separately. A landscape can be reproducible and
short of the bar, which is the outcome the reps=1 work would lead you to expect.

### What this is NOT

- **Not a reopening of the optimizer verdict.** `optimizer-budget-study.md` is
  CONFIRMED-CLOSED: no *arm* at any *budget* reaches the bar. This study introduces
  no arms and no budgets. It asks what the landscape looks like, and whether the best
  basin in it is above or below the bar. If the best basin is below, that is a fact
  about the landscape, not a new failure of a search procedure.
- **Not a hardware claim.** Nothing here is submitted, and no reps=2 cp3 circuit has
  ever been run on a device.
- **Not a claim about instance 0.** The reps=1 study's instance is seed 0. This one
  is seed 1 and the two are not comparable point-for-point; only the *shape* is.

## Instance, designated in advance

**T=3, seed 1, `checkpoint(3)`, reps=2.** Six qubits, so the bar is
`5 / 2**6 = 0.078125` exactly.

Seed 1 is the **optimizer study's pre-designated primary instance**, chosen there in
advance and found to be the hardest of its three. It is designated here for that
reason and not because anything about its landscape has been seen. The reps=1 basin
study's instances (0, 1, 2) are the same seeds; its instance 1 was a *robustness*
instance whose basin counts are in `basin_study.json`, and **those counts are at
reps=1 and are not evidence about this study's outcome.**

No robustness instances are swept here. One instance, one depth, and the verdict
stands or falls on it.

## Pinned before anything runs: what "distinct basin" means

Unchanged in *rule* from the reps=1 study, recomputed in *value*:

- **Distance:** total variation between the two exact ideal output distributions.
- **Cutoff τ:** `E[TVD(ideal, multinomial(4096) / 4096)]` over **400 resamples**,
  `numpy.random.default_rng(0)`. Two distributions closer than τ are
  indistinguishable by the measurement this project performs.
- **Reference for τ:** τ is estimated from the **α\* reference distribution**, and at
  reps=2 there are no recorded hardware angles to supply one. **The rule, fixed
  here:** the reference is the tuning at α\* = 0.021 with the **lowest achieved
  `<H>`** over the pinned seed budget — the same selection rule `QAOASolver` already
  applies and the same one `basin-structure.md` showed is stable in N. The *rule* is
  pinned now; the *value* is computed at run time and reported.
- **Linkage:** **complete**, chosen in advance for the reason the reps=1 study
  chose it — single linkage chains basins together at high α.
- **Headline seed budget:** N = 40 tuning seeds (1..40), `n_starts=5`,
  `maxiter=200`, `shots=4096`.

**Pre-committed sensitivities**, reported whatever they show: τ/2 and 2τ; single
linkage; N ∈ {5, 10, 20, 40}.

## The α ladder

The reps=1 ladder, unchanged, so the two studies are comparable rung for rung:

`0.003, 0.006, 0.010, 0.0209, 0.021, 0.030, 0.060, 0.100, 0.300, 1.000`

α\* = **0.021** is the weight every hardware run used and the anchor for the
reference. 0.0209 is the a-priori span/penalty value and is a separate rung.

## Mass against the bar

At each α, over the 40 tunings, report:

- the **best** ideal optimal mass (`max`), and the mass of the **lowest-`<H>`**
  tuning — the two differ, and the second is what a principled selection rule would
  actually return;
- how many tunings clear **0.078125**;
- the same per **basin**, so "the best basin" is a defined object rather than a
  loose phrase.

**Exactness is reported alongside, and no mass figure may be read without it.** The
reps=1 study's central trap was that α = 0.003 puts *more* mass on the QUBO's
minimizer than α\* does, and that minimizer is infeasible. The same column is
computed here and carries the same warning.

## Predictions, with reasoning

**P1 — the single-basin regime does not survive.** At α\* and reps=2, basin count is
**greater than 1**.

*Reasoning:* basin multiplicity at reps=1 rises with α once the penalty dominates
the objective; a second layer adds two more angles and a periodic, non-convex
landscape in each. The reps=1 result that α ≤ α\* gives exactly one basin is a
statement about a two-parameter landscape, and there is no argument that carries it
to four. The optimizer study's reps=2 spread across tuning seeds (sd 0.0116 on a
mean of 0.0716) is itself evidence that different seeds reach materially different
places at this depth.

**P2 — the best basin falls short of the bar.** The maximum ideal optimal mass over
all 40 tunings at α\* is **below 0.078125**.

*Reasoning:* the optimizer study found every arm's *mean* short of the bar on this
instance at this depth, and lifting the budget 25× moved the mean by +0.0072 against
a 0.0102 shortfall. If the landscape's best reachable point were above the bar, a
50-restart arm would be expected to have found it.

### What would falsify each

- **P1 is falsified** if basin count at α\* is exactly **1** at the pinned τ, complete
  linkage, N = 40. Not "close to 1", not "1 at some cutoff" — 1 at the pinned
  definition.
- **P2 is falsified** if **any** of the 40 tunings at α\* reaches ideal optimal mass
  **≥ 0.078125**.

Both are reported at the pinned definition first. Sensitivities are reported after,
and **may not be used to move a verdict** — they are there to say how firm it is.

If P1 is falsified and P2 is not, the reading is that the landscape is reproducible
and simply does not contain a point above the bar at this depth, which would make
basin structure the wrong suspect for the open question. If P2 is falsified, the
open question has an answer and it is that the search, not the landscape, was the
limit.

## Disclosed: what was already observed before registration

Stated so that neither prediction can be read as sharper than it is:

1. **`optimizer-study.md` / `slack-free-encoding.md`:** at reps=2 on this instance,
   ideal mass reached **0.0716–0.0750** against the 0.078125 bar across 12 arm × α
   combinations, all failing. sd 0.0116 across tuning seeds at one arm.
2. **`optimizer-budget-study.md`:** lifting `maxiter` 25× bought a paired **+0.0072**
   and left **0.0102** to find; the best-funded arm then spent only 38% of its cap.
3. **`optimizer_study.py`'s docstring** records that on *some* instance at reps=2 and
   α\*, **2 of 6 seeds cleared** and the observed maximum was **0.0879**. That is not
   this instance's primary result and is why P2 is a real prediction rather than a
   restatement — individual tunings clearing is known to be possible somewhere.
4. **`basin-structure.md`:** at reps=1, one basin at and below α\*, rising to ~19 at
   the default weight, usable window `0.010 ≤ α ≤ 0.021`.

Nothing about instance 1's reps=2 landscape has been computed or inspected.

## Procedure

1. `python scripts/basin_study_reps2.py` — sweeps the ladder at N = 40, streams
   scalars to `docs/results/basin_study_reps2.csv`, writes
   `docs/results/basin_study_reps2.json`.
2. The script **refuses to run** unless this plan is already committed, so the
   registration cannot be back-dated.
3. Results go to `docs/results/basin-structure-reps2.md`, reporting both predictions
   at the pinned definitions before any sensitivity.

Expected cost: ~45 minutes, simulator only.

## Limitations, recorded in advance

- **One instance, one depth, one encoding.** Nothing here transfers to another seed
  any more than the reps=1 result transferred to this one.
- **Basin count is a property of the pinned search** (`n_starts=5`, `maxiter=200`),
  not of the true stationary-point structure. A different budget finds a different
  number of basins and that is a fact about the search.
- **τ is tied to a 4,096-shot budget.** A different shot count is a different τ and
  therefore a different notion of "distinct".
- **Reproducible is not good.** As at reps=1, the two questions are independent, and
  a single basin below the bar is a coherent and unremarkable outcome.
- **The bar is not moved and the instance is not reselected**, whatever comes out.
