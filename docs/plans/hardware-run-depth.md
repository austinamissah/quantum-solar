# Pre-registration: does depth help, net of noise? (T3/cp3 at reps 1 and 2)

**Status: REGISTERED** by the commit that adds this file — written **before**
submission, with nothing yet run against it. Any later change to the prediction,
threshold or outcome sections is an amendment and has to say so. Every circuit
number here is from a real `ibm_fez` dry run on 2026-08-25; no QPU has been spent.

Follows `docs/plans/hardware-run-spread.md` and its result.

## Purpose

**H1 — does depth help, net of noise? — has never been asked on hardware.** The
July run defined it and never submitted it: the gate was not met on the
pre-designated instance. `docs/results/slack-free-encoding.md` §Circuit cost then
ruled out T=4 and T=6 for a specific reason, stated there as a general principle:

> a candidate that can only run one depth cannot answer a question about depth.

**T3/cp3 is the first circuit that can run both depths.** At 46 two-qubit gates
(reps=1) and 112 (reps=2), both sit inside the 37–290 range already flown, where
signal above the measurement floor has actually been observed. That is what makes
this run possible now and not before, and it is the whole reason to run it.

**The ideal headroom is large**, from the tuning stage of this plan
(`docs/results/hardware_params_depth.json`, simulator, exact statevector):

| depth | ideal optimal mass | ideal feasible mass |
|---|---:|---:|
| reps=1 | 0.0462 | 0.2874 |
| reps=2 | **0.0893** (1.93x) | **0.4531** (1.58x) |

**The reps=2 arm clears the H1 bar; the reps=1 arm does not.** The bar is
**0.078125** (5 x uniform at m=6), the gate `slack-free-encoding.md` records H1 as
having failed on the pre-designated instance. 0.0893 clears it, 0.0462 does not.
(Whether that instance is this one, seed 0, is unverified — if it is not, this
reads as "clears the same bar on this instance".)

So the noiseless circuit almost exactly doubles optimal mass when the layer is
added. **The question is how much of that doubling the device leaves standing**,
against a two-qubit gate count that also grows 2.4x.

## Circuits — one job, four circuits

Numbers from the dry run, `optimization_level=3`, backend pinned `ibm_fez`.

| # | circuit | m | 2Q | depth | shots | role |
|---:|---|---:|---:|---:|---:|---|
| 1 | `cp3 @ α=0.021` reps=1 r1 | 6 | 46 | 119 | 4,096 | **PRIMARY pair** |
| 2 | `cp3 @ α=0.021` reps=2 r1 | 6 | 112 | 245 | 4,096 | **PRIMARY pair** |
| 3 | `cp3 @ α=0.021` reps=1 r2 | 6 | 46 | 119 | 4,096 | variance only |
| 4 | `cp3 @ α=0.021` reps=2 r2 | 6 | 112 | 245 | 4,096 | variance only |

**Estimated ~14.0 QPU seconds** (coarse; actual is recorded post-run from job
metadata). That is about a tenth of the 153 seconds spent to date.

### Four design choices, and why

**One job.** Both depths share a calibration snapshot. Between-run variance is
bounded by nothing here — it remains n = 3 — so comparing this reps=2 circuit
against July's or August's reps=1 numbers would confound depth with drift. The
reps=1 arm is re-run for that reason, not for want of prior measurements.

**Equal shots, unlike the encoding plans.** There the arms differed in qubit
count, so the TVD shot-noise floor differed and unequal shots equalized it. Here
both arms are the same encoding on the same 6 qubits, so the floor is already
identical and unequal shots would introduce the very bias unequal shots exist to
remove.

**Order is load-bearing.** The primary comparison is replicate 1 of each depth,
listed first in `DEPTH_TARGETS` and fixed before submission, so it cannot be
chosen after seeing which pair is more favorable. Replicate 2 of each is a
variance estimate and is never pooled into the primary comparison.

**Backend pinned.** Per-device error rates do not transfer across Heron devices
and the reps=1 arm's prior numbers are `ibm_fez` numbers. Unavailable means fail,
never substitute.

## The statistic

> **Provenance.** This section and the three that follow were drafted by an AI
> assistant at the author's request and **adopted by the author as written**, on
> 2026-08-25, before submission. The prediction is registered as the author's own;
> the drafting is recorded here because the README discloses the assistant's role
> and reserves the registered predictions to the author, and a reader checking that
> claim should be able to see how this one was arrived at.

**Primary: hardware optimal mass** — the fraction of the 4,096 shots landing on the
QUBO's minimizer. It is the quantity H1 was defined on, both arms share one
optimum so it is directly comparable across depths, and it is the quantity the
project cares about (does the device find the answer).

**Secondary, pre-declared: hardware feasible mass.** Larger and better resolved,
and it is leg 3's quantity.

**Reported but not gating: normalized TVD** against the exact statevector,
for comparability with the three prior runs. It is not the gate because it measures
*distance from ideal*, and the two arms have different ideals, so it answers "which
circuit is executed more faithfully" rather than "which circuit is more useful".

## The prediction

**The calibrated noise model predicts a dead heat on the primary statistic, and
that is the prediction registered here.**

Applying the depolarizing model fitted to July (~1.32% effective error per
two-qubit gate) as `hardware ≈ (1 − ε)·ideal + ε·uniform`, with ε = 0.4573 at 46
gates and 0.7742 at 112, and uniform = 1/64 = 0.015625 on the single optimum:

| arm | ideal optimal mass | ε | predicted hardware optimal mass |
|---|---:|---:|---:|
| reps=1 | 0.046249 | 0.4573 | **0.032244** |
| reps=2 | 0.089250 | 0.7742 | **0.032247** |

**Predicted difference: +0.000003.** The ideal 1.93x gain from the extra layer is
almost exactly cancelled by the extra noise from 2.4x the gates. This is not a
number that was tuned to come out flat; it is what the existing model says when
this plan's two circuits are put through it, and its flatness to five decimal
places is a coincidence of this instance.

**On the secondary statistic the model predicts depth loses.** Uniform feasible
mass is 7/64 = 0.109375, which is much closer to the reps=2 ideal, so noise erodes
the deeper arm's advantage further:

| arm | ideal feasible mass | predicted hardware feasible mass |
|---|---:|---:|
| reps=1 | 0.287354 | **0.205960** |
| reps=2 | 0.453128 | **0.186984** |

**Predicted difference: −0.018976**, against the deeper circuit.

So the registered directional claim is: **depth does not help on hardware here, and
on feasible mass it actively hurts.** The run is worth making because that
prediction is sharp enough to be wrong in an informative way — the model has never
been tested at this depth on this encoding.

## The threshold

**Derived, not chosen for roundness.** At 4,096 shots the standard error on a
measured mass `p` is `√(p(1−p)/4096)`, and a difference between two arms carries
the root-sum-square of the two. Against the predicted masses:

| statistic | SE per arm | SE of the difference | resolvable at 95% (1.96·SE) |
|---|---:|---:|---:|
| optimal mass | 0.00276 | 0.00390 | **0.00765** |
| feasible mass | 0.00632 / 0.00609 | 0.00878 | **0.01721** |

> **Threshold: a difference in hardware optimal mass of 0.00765**, which is 23.7%
> of the predicted mass itself.

Two consequences, both stated now rather than discovered later.

**The primary prediction cannot be "confirmed", only left unrefuted.** A predicted
difference of 0.000003 is a null, and no shot budget makes a null positive
evidence. The verdicts below are written accordingly: the informative outcomes are
the ones that *break* the model.

**The secondary statistic is marginal by design, and is not rescued by being
larger.** Its predicted difference of 0.018976 exceeds its resolvable margin of
0.01721 by 10%. So a correct model would produce a *just* significant result, and
anything that adds variance — device drift, a calibration shift mid-job — pushes it
under. It is a secondary for that reason and gates nothing on its own.

**Device variance is not bounded here.** The spread study measured
σ_device = 0.02094 for `cp3` at 4,096 shots, but on *normalized TVD*, not on mass,
and at 46 gates rather than 112. Nothing transfers. The two replicates per arm are
a consistency check, not an estimate: at 1 df the χ² upper factor is 31.9, which
`hardware-run-spread.md` already records as producing a vacuous bound. **The
threshold above is therefore a shot-noise floor, not a total-error bound**, and a
difference just past it should be read as "not explained by shot noise" rather than
"real".

## What each outcome means

Written before the run, including the outcome that flatters nothing.

| region | condition on optimal mass | verdict |
|---|---|---|
| **MODEL HOLDS** | \|Δ\| < 0.00765 | Consistent with the dead heat predicted. Depth neither helps nor hurts at a resolution of 0.0077. **Not** evidence that depth is useless — evidence that this instrument cannot separate them. |
| **DEPTH HELPS** | reps=2 exceeds reps=1 by > 0.00765 | The model is wrong in the optimistic direction: the deeper circuit retains more than the per-gate error rate predicts. This is the only outcome that argues for deeper circuits, and it would need replication before being reported as more than one job's result. |
| **DEPTH HURTS** | reps=1 exceeds reps=2 by > 0.00765 | The model is wrong in the pessimistic direction: depth costs more than gate count alone explains. |

**Pre-committed language for MODEL HOLDS**, the most likely outcome:

> The reps=2 circuit did not measurably outperform reps=1 on hardware, as the
> depolarizing model predicted. H1 is **answered in the negative for this instance
> at this depth**: the ideal doubling of optimal mass does not survive the gate
> count that buys it. This is one instance, one encoding, one device and one job,
> and it is not a general claim that depth does not help QAOA. No further hardware
> run is proposed on the strength of disliking this outcome.

**What none of the three outcomes licenses.** No verdict here bears on legs 2 or 3
as claims. A reps=2 circuit finally reaching hardware does not make the
penalty-weight or selection-rule findings hardware results; both remain simulator
findings, and `docs/FINDINGS.md` should continue to say so whatever this run
returns.

## Tuning and selection — declared before the candidates were generated

**The rule is fixed here, in advance, because the alternative is indistinguishable
from choosing on the outcome.** This section was written and the plan saved before
the 40 tunings below were run.

- **40 independent tunings per arm.** `QAOASolver(reps=r, n_starts=1, maxiter=200)`
  called 40 times with seeds `QAOA_SEED + 0 … QAOA_SEED + 39`. One restart per
  call, so each tuning is independent, matching how the selection-rule studies
  drew their 40.
- **Selection: argmax of feasible mass** on the exact (noiseless) statevector
  distribution — `p[feas_mask].sum()`, the same quantity `rules()` in
  `scripts/selection_rule_study.py` calls `feasible_mass`. Ties break to the
  lowest seed index, so the choice is deterministic.
- **Applied identically to both arms.** The reps=1 landscape is single-basin at
  α\*, so the rule is expected to change nothing there. It is applied anyway:
  a depth comparison in which the arms were tuned by different rules would not be
  a depth comparison.
- **All 40 candidates recorded** per arm — ⟨H⟩, optimal mass, feasible mass — in
  `docs/results/hardware_params_depth.json`, so the rank disagreement between the
  two rules is in the artifact rather than asserted.

### Why the rule is not ⟨H⟩, with the measurement that decided it

Both rules applied to **one identical pool** — the 40 restarts a single
`QAOASolver(n_starts=40, seed=1234)` run draws, which is exactly the candidate set
the default rule chooses between:

| arm | rule | ⟨H⟩ | optimal mass | feasible mass | rank by mass |
|---|---|---:|---:|---:|---:|
| reps=1 | lowest ⟨H⟩ | 0.461316 | 0.0449 | 0.2785 | 13/40 |
| reps=1 | **feasible mass** | 0.465339 | **0.0462** | **0.2874** | 1/40 |
| reps=2 | lowest ⟨H⟩ | 0.328999 | 0.0838 | 0.4289 | 2/40 |
| reps=2 | **feasible mass** | 0.336258 | **0.0893** | **0.4531** | 1/40 |

The rule gains **3.18% feasible mass at reps=1 and 5.65% at reps=2** (optimal mass
3.11% and 6.54%), and in both arms it accepts a *worse* ⟨H⟩ to get there. The
published leg-3 margin is a median 5.0%, so this is a **replication on a fresh
instance** — seed 0 here against seed 1 there, written up separately in
[`../results/selection-rule-hardware-tuning.md`](../results/selection-rule-hardware-tuning.md). ⟨H⟩ and mass correlate at −0.968
(reps=1) and −0.955 (reps=2), against −0.918 published: the proxy is good through
the bulk and wrong at the top, which is the whole of leg 3.

A corollary worth recording, because it is how this was found. Raising the ⟨H⟩
restart budget from 5 to 40 — changing nothing else — moved the reps=2 arm from
⟨H⟩ = 0.336258 to 0.328999 and feasible mass from 0.4531 **down** to 0.4289. The
5-start run had landed on the mass-best point by luck; the larger ⟨H⟩ search walked
off it. **Searching the proxy harder produced a worse circuit**, which is a sharper
statement than the ranking result and is what makes the selection rule load-bearing
here rather than a refinement.

The reps=1 arm is bit-identical between 5 and 40 starts under lowest ⟨H⟩, as a
single-basin landscape implies, and only moves once the rule changes.

## What this run cannot measure

- **One instance, one encoding, one weight, one device, one day.** T=3, seed 0,
  `checkpoint(3)`, α = 0.021, `ibm_fez`. Nothing here generalizes past that.
- **Two depths, not a depth curve.** reps=3 is not submitted, so no trend is
  established, only a single step from 1 to 2.
- **Between-run variance stays n = 3.** Four circuits in one job share a
  calibration window, a queue position, and a thermal state. A within-job result
  licenses no claim about run-to-run stability.
- **The reps=2 arm's within-job spread is unmeasured**, and two replicates cannot
  measure it — that is the same 1-df problem `hardware-run-spread.md` records,
  where the χ² upper factor of 31.9 makes the bound vacuous.
- **Nothing here bears on legs 2 and 3 as claims.** A reps=2 circuit finally
  reaching hardware does not make the penalty-weight or selection-rule findings
  hardware results; both remain simulator findings.
