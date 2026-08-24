# Pre-registration: does α\* buy reproducibility?

**Status:** registered, not yet run. **Simulator and exact computation only — no
QPU is spent by this study and none is requested by it.**

Written **2026-08-07**, before the sweep runs. Two anchor observations were already
in hand and are disclosed in full below; everything else is fixed here first.

## The one question

**Does the penalty weight control how reproducible QAOA tuning is?** Concretely:
sweep α from 0.003 to 1.0 on a designated instance, and at each α count how many
*distinct basins* independent tuning runs land in.

That is the whole question. Basin **count** as a function of α, nothing else.

### What this is NOT

- **Not the optimizer study** (`optimizer-study.md`, `optimizer-budget-study.md`).
  Those asked whether any search procedure reaches the 0.078125 bar. Answer:
  **CONFIRMED-CLOSED**, no arm at any budget. This study does not measure mass
  against the bar, does not introduce new arms, and cannot reopen that verdict.
- **Not the encoding × weight 2×2.** That was designed and declined
  (`slack-free-encoding.md`, "Device degradation"). This study characterizes the
  landscape's *shape*; it says nothing about device degradation or the encoding gap.
- **Not a claim about solution quality.** A landscape with one basin is
  reproducible, not necessarily good. Reproducibility and optimality are separate
  and this study measures only the first.

If a later reader finds this being cited for any of the three, it is being
misread.

## Instance, designated in advance

**T=3, instance seed 0, `Encoding.checkpoint(3)`, reps=1** — the instance every
hardware run used, so the result transfers to the circuits already published.
`capacity=3.0`, `charge_energy=1.0`, `initial_soc=1.0` (i.e. `experiment_hardware`'s
`build_target(3, 0, 1, encoding="checkpoint3", alpha=α)`), m=6.

Robustness instances **seeds 1 and 2**, reported but **not permitted to decide the
verdict** — the primary is designated here and stays designated. (LESSONS §5: pin
the population, not just the threshold.)

## Pinned before anything runs: what "distinct basin" means

This is the definition that has decided the outcome in three prior
pre-registrations, so it is fixed here in full — quantity, metric, cutoff, and
clustering rule.

**Quantity.** The **ideal output distribution** of the tuned circuit: the `2^m`
probability vector from `exact_distribution(qubo, tuned_params, reps)`. Not the
angles (periodic and non-unique — different angles can give the same circuit), and
not the achieved `<H>` (distinct basins can tie in `<H>`; two of them do here).
The distribution is what the circuit *does*, and it is what every downstream
measurement in this project consumes.

**Metric.** Total variation distance, the same metric used throughout the hardware
analysis.

**Cutoff τ = 0.0433.** Two runs are in the same basin iff their distributions are
within τ. This is the **expected shot-noise floor** at m=6 and 4,096 shots —
`E[TVD(ideal, multinomial sample)]` over 400 resamples, **computed rather than
assumed**. Justification: below τ, two distributions are indistinguishable by the
measurement this project actually performs, so a finer distinction is one without
an operational difference. The cutoff is derived from the design, not chosen for
roundness.

> Note it is **not** the 0.0497 that appears in the `hardware-run-encoding.md`
> result table. Three distinct quantities have been called "the floor": the
> analytic design target `√(2^m / 2πN)` ≈ 0.042; the **expected** floor 0.0433
> (sd 0.0048); and a **single realized** Aer draw, 0.0497, which is what that table
> reports and which sits 1.3 sd above its own mean. Using a one-draw realization as
> a threshold would import ±11% of its own noise. τ is the expected floor.

**Clustering rule: complete linkage.** A cluster is a set in which *every* pair is
within τ. Single linkage would let a chain of near-neighbors merge two genuinely
separated basins, and at α values with many near-degenerate optima that is a real
risk, not a theoretical one. Complete linkage is the headline; **single linkage is
reported alongside as a sensitivity**, and any α where the two disagree is flagged
rather than silently resolved.

**Sensitivity, pre-committed:** basin counts are additionally reported at **τ/2**
and **2τ**. If the qualitative conclusion flips between them, the conclusion is
reported as cutoff-dependent, not as a result.

## Seed budget is an axis, not a setting

Tuning is run `N` independent times per α — seeds `1..N` — each run being
`QAOASolver(reps=1, n_starts=5, shots=4096, maxiter=200)`, the pinned hardware
settings. `n_starts` stays at 5 because that is what the hardware pipeline does per
target; `N` is the number of independent tunings, which is the thing that varies in
practice between one person's run and another's.

**Headline N = 40.** Basin count is additionally reported at **N ∈ {5, 10, 20, 40}**
by taking the first N seeds, so the curve is visible rather than a single point.

Also reported per α, because the selection rule is itself unstable: **which basin
the lowest-`<H>` rule picks, as a function of N.** Already measured at α=1.0, that
rule picks TVD 0.1466 at N=8 and 0.1488 at N=20 on an `<H>` difference of **0.14%** —
so "the tuned circuit" is not well defined without stating N.

## The α ladder

`0.003, 0.006, 0.010, 0.0209, 0.021, 0.030, 0.060, 0.100, 0.300, 1.000`

Both **0.0209** (the α\* rule) and **0.021** (what the hardware runs used) are
included deliberately: `eval-censoring.md` documents this instance being sensitive
to α *in its third decimal* — 0.0209 and 0.021 move ideal mass by 22% — so
collapsing them would hide exactly the resolution this study operates at.

## Prediction, with reasoning

> **Basin count is minimized at or near α\*, and rises on both sides.** A U-shape,
> not a cliff.

Reasoning, one mechanism per branch:

- **Below α\***: penalties are too weak to dominate, so many cheap-but-infeasible
  assignments sit near the QUBO minimum. The landscape has many competitive optima
  and the search distributes across them. This is the same failure the exactness
  cliff measures — 61% optimal at α=0.010, 6% at 0.005, 1.5% at 0.003.
- **Above α\***: penalties swamp the objective. At default weight the penalty scale
  is 14.81 against an objective span of 0.3095, a **48× overshoot** (LESSONS §1), so
  cost is nearly invisible to `<H>` and the landscape becomes a set of
  near-degenerate feasible configurations that the objective cannot separate.

### What would falsify it

The prediction fails if, at the pinned N=40 and τ, **basin count at α\* is not a
strict minimum over the ladder** — specifically if any of:

- basin count is **flat** across the ladder (weight does not control reproducibility
  at all — the null this study is built to be able to return);
- basin count **decreases monotonically** with α, i.e. default weight is at least as
  reproducible as α\* (this is what "collapses to one at or above α\*" would predict,
  and it is the reading the disclosure below already contradicts);
- basin count at α\* exceeds basin count at **either** endpoint.

A U-shape whose minimum sits at an α other than α\* is a **partial** result: it
would confirm that weight controls reproducibility while refuting that α\* is the
optimum, and must be reported that way rather than as confirmation.

## Disclosed: what was already observed before registration

Pre-registration means declaring what is known and fixing the rule before the rest
runs — not pretending to know nothing. Two anchors were measured while evaluating a
different proposal, and they are why the prediction above is a U-shape rather than
the cliff originally proposed:

| α | seeds run | TVD spread across seeds | basins (τ, complete linkage) |
|---:|---:|---:|---:|
| 0.021 | 6 | 0.0002 | **1** |
| 1.000 | 20 | 0.740 (range 0.015–0.755) | **≥3** |

Both of these are *at or above* α\*, and they differ by three orders of magnitude in
spread. **An earlier draft of this study predicted "basin count collapses to one at
or above α\*, mirroring the exactness cliff." That is contradicted by the second row
before any new data is collected**, which is why it is not the registered
prediction. The α=0.021 row is 6 seeds and will be re-run at N=40; it may not stay
at 1.

## Procedure

1. Compute τ by resampling (400 multinomial draws at 4,096 shots) and record it.
2. For each α in the ladder, for seeds 1..40: tune, record `optimal_params`, the
   ideal distribution, and achieved `<H>`.
3. Cluster per α at τ (complete linkage), record basin count, and repeat for
   τ/2, 2τ, single linkage, and N ∈ {5,10,20,40}.
4. Record the lowest-`<H>` selection and its TVD to the α\* reference per N.
5. Repeat on robustness seeds 1 and 2; report, do not re-decide.
6. Write results to `docs/results/basin-structure.md` with the verdict stated
   against the falsification criteria above, whichever way it goes.

Artifacts are tagged so a re-run cannot clobber a prior one. Library versions
(`qiskit`, `qiskit-aer`, `scipy`, `numpy`) are recorded beside the results: a
patch-level difference can move which basin a tuning run lands in.

## Limitations, recorded in advance

- **One instance, one depth, one encoding.** reps=1, checkpoint(3), T=3. Nothing
  here generalizes to reps=2 (where the optimizer study's open question lives)
  without being measured there.
- **Basin count is a function of the search, not only the landscape.** At
  `n_starts=5` a run can fail to find a basin that exists. This study measures what
  *the pinned procedure* reaches, which is the operationally relevant quantity and
  is not the same as the true stationary-point structure.
- **τ is tied to a 4,096-shot budget.** A different shot budget implies a different
  operational resolution and could merge or split basins.
- **Reproducibility is not quality.** See "What this is NOT".
