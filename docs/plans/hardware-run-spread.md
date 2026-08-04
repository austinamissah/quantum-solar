# Pre-registration: powered within-job spread + third gap measurement

**Date:** 2026-08-03 — written **before** submission. Nothing has been run for
this plan. All circuit numbers below are from a real `ibm_fez` dry run.

Follows `docs/plans/hardware-run-encoding-replication.md` and its result.

## Purpose

**1. A properly-powered within-job spread estimate.** The replication run's
duplicate gate was **inconclusive**, and not merely for want of a stated
threshold: a spread from a *single pair* carries ~76% relative uncertainty, so
0.0389 was consistent with anything from 10% to 73% of the gap. **Ten** replicates
on the `cp3` arm estimates it well enough to adjudicate.

Ten, not five: at n = 5 the **RESOLVED verdict is unreachable**. With χ² upper
factor 2.874 on 4 df, even *zero* true device variance leaves the upper bound on
σ_device at 0.048 against a cap of 0.034 — the test could only ever return
UNRESOLVED or INDETERMINATE, never confirm. n = 8 is marginal (0.032 vs 0.034);
n = 10 gives real margin (0.027) for ~15 extra QPU-seconds. A test that cannot
return one of its own verdicts is not a test.

**2. A third independent between-run gap measurement.** Two runs so far: gap
medians 0.0658 and 0.0934.

## Circuits — one job, twelve circuits

| # | circuit | m | 2Q | depth | shots | role |
|---:|---|---:|---:|---:|---:|---|
| 1 | `cp3 @ α=0.021` r1 | 6 | 46 | 120 | 4,096 | **PRIMARY gap** |
| 2 | `exact @ α=0.021` r1 | 10 | 106 | 182 | 65,536 | **PRIMARY gap** |
| 3–11 | `cp3 @ α=0.021` r2–r10 | 6 | 46 | 120 | 4,096 | spread only |
| 12 | `exact @ α=0.021` r2 | 10 | 106 | 182 | 65,536 | spread only |

One job, one calibration snapshot. Backend pinned `ibm_fez`,
`optimization_level=3`, `seed_transpiler` pinned, params and counts guarded
against overwrite.

**Estimated ~81.5 QPU seconds** — not the ~41 assumed when this run was proposed.
The `exact` arm dominates: two circuits at 65,536 shots and depth 182 cost ~51.7 s
of the total, against ~29.8 s for all ten `cp3` circuits. Recorded here so the
budget is not a surprise.

## The threshold, fixed and derived

The statistic is **σ_device** (defined in the next subsection — the device-only
component of the ten `cp3` replicates' spread), expressed as a ratio to the
measured gap.

**Derivation.** The primary gap is a difference between *one* measurement of each
arm. If a single measurement carries within-job SD σ_w, the gap's device-variance
standard error is `√2·σ_w`. For the gap to be resolvable at conventional
two-sided 95%:

```
|gap| > 1.96 · √2 · σ_w      ⟺      σ_w / |gap| < 1 / (1.96·√2) = 0.3608
```

> **Threshold: σ_device / gap = 0.361.**

The number is not chosen for roundness — it is `1/(z₀.₉₇₅·√2)`, the point at which
device variance alone consumes the whole 95% interval of a one-replicate-per-arm
difference.

#### The gap's SE is BOUNDED, not estimated — and two `exact` replicates cannot check it

Using `√2·σ_cp3` in place of `√(σ_cp3² + σ_exact²)` is conservative **iff
σ_cp3 ≥ σ_exact**. Measured on the replication run:

| arm | shots | σ_total | σ_shot | σ_device |
|---|---:|---:|---:|---:|
| `cp3` | 4,096 | 0.02754 | 0.01789 | **0.02094** |
| `exact` | 65,536 | 0.00440 | 0.00396 | **0.00191** |

On point estimates the condition holds with an **11x margin**, and there is a
physical reason to expect it: a 65,536-shot circuit takes 16x longer to acquire
and so averages over more of the drift timescale.

**But this cannot be verified at two replicates.** With 1 df the χ² 95% upper
factor is **31.9**, putting `exact`'s σ_device upper bound at 0.140 — 6.7x
`cp3`'s. The bound is vacuous. So:

> **The gap's standard error is bounded by a proxy, not estimated. Two `exact`
> replicates cannot test whether that proxy is conservative.**

**The direction of the residual risk matters and is stated rather than left
implicit.** If `exact`'s device variance were in fact large, the true gap SE would
*exceed* the proxy, so the gate would declare UNRESOLVED **less** readily than it
should — i.e. it would err toward *keeping* the headline. That is the opposite of
this run's stated purpose, and it is the one way this design can fail quietly.

Fixing it properly needs `exact` at **4 replicates** (3 df, upper factor 3.73 →
σ_device upper 0.0159 < `cp3`'s 0.0209, so the condition would be verified at the
95% bound). Three is not enough (upper 0.0274, still above). Four costs **~51.7
extra QPU-seconds**, taking the run from ~81.5 s to ~133 s — a 63% increase to
bound a term that point-estimates at one-eleventh of the other. **Not taken
here**, and recorded as the known limitation rather than an oversight.

### σ must be the DEVICE component, not the total spread

The replicate spread contains **both** device variance and shot noise. The
bootstrap CI on the gap already accounts for shot noise. Comparing *total* spread
against the gap therefore charges the result twice for the same term, and would
declare "unresolved" on the strength of noise the primary analysis has already
handled.

The gate is therefore defined on the device-only component:

```
σ_device = √( σ_total² − σ_shot² )
```

- **σ_total** — the sample standard deviation of the ten `cp3` normalized-TVD
  values.
- **σ_shot** — the mean per-measurement bootstrap standard deviation across those
  same ten counts, i.e. shot noise estimated from the identical data rather than
  assumed.

Both are computed from this run's own counts; nothing is imported.

#### If the subtraction goes negative

`σ_total² < σ_shot²` is a real possibility — it means the observed replicate
spread is smaller than shot noise alone predicts, which happens by fluctuation.
**It must not be silently clamped to zero and read as RESOLVED.** Pre-committed
reading:

- The **point estimate** of device variance is reported as *consistent with zero*
  and explicitly as **not resolvable at this shot count** — not as "zero".
- **The verdict is still decided by the upper confidence bound**, which remains
  positive and finite. A negative point estimate with a large upper bound is
  **INDETERMINATE**, not RESOLVED.
- **UNRESOLVED can never be triggered** by a negative point estimate, since the
  lower bound clamps at zero.
- If σ_total falls *far* below σ_shot (below the χ² lower bound on σ_total given
  σ_shot), that is a **diagnostic finding, not a result**: it would mean the
  bootstrap overestimates shot noise, and the primary analysis's CIs — which rest
  on that same bootstrap — would need re-examining before any verdict is issued.

### The three-way rule

With 10 replicates σ̂_total has 9 df and a 95% CI of `[0.688, 1.826]·σ̂_total`.
Propagating through the subtraction (treating σ_shot as known — it is estimated
from 20,000 bootstrap draws, so its own uncertainty is negligible beside σ̂'s)
gives an interval for σ_device. Against `cap = 0.361 × gap`:

| region | condition | verdict |
|---|---|---|
| **RESOLVED** | upper bound of σ_device < cap | Device spread confidently below what would obscure the gap. The gap stands. |
| **UNRESOLVED** | lower bound of σ_device > cap | Device spread confidently large enough to obscure it. See withdrawal language below. |
| **INDETERMINATE** | interval straddles cap | Neither. Reported as undetermined — *not* forced to a verdict. |

This is stated on the interval rather than the point estimate deliberately: the
unstated point-vs-bound choice is what sank the previous gate, and picking one
side would merely relocate the ambiguity rather than remove it.

## Primary gap — fixed rules

- The primary gap is **replicate 1 of each arm** (rows 1–2), fixed here and in
  `SPREAD_TARGETS` order in `scripts/experiment_hardware.py` before submission.
- **The extra `cp3` replicates are never pooled into the gap or its CI.** They
  estimate σ_device and nothing else. Pooling would convert a variance measurement into
  a precision gain — the manoeuvre that makes a marginal result look solid.
- Analysis is identical to both prior runs: hardware-only bootstrap, B = 10,000,
  against an exactly-known statevector reference.

## This test can only weaken the headline

Stated plainly because it is the point of running it. There is **no outcome here
that strengthens the encoding claim.** A small σ_device leaves the claim exactly
where two runs already put it; a large σ_device removes it. Language for that
outcome, written
now:

> **UNRESOLVED outcome.** The within-job spread on the `cp3` arm is large enough
> that a gap measured from one replicate per arm cannot be distinguished from
> device variance. The two prior runs' gap measurements — medians 0.0658 and
> 0.0934, both with bootstrap intervals excluding zero — are therefore **not
> evidence of an encoding effect on hardware**, because their intervals captured
> only sampling variance and omitted a device term now measured to be comparable
> to the effect. The headline "the slack-free encoding reduces device degradation"
> is **withdrawn**, in `docs/results/slack-free-encoding.md`,
> `hardware-run-encoding.md`, and `hardware-run-encoding-replication.md` alike.
>
> The two prior runs are **not** reinterpreted as having been unlucky, and their
> agreement with each other is **not** offered as evidence against this finding —
> two measurements sharing an uncorrected bias agree with each other precisely
> because they share it. No further hardware run is proposed on the strength of
> disliking this outcome.

The classical results are untouched in every case: `cp5band` at 52 qubits for
$0.00/yr, the 349x ideal-mass improvement, and the α\* = span/penalty rule. None
of them depend on any hardware measurement.

## What this still cannot measure

- **Between-run variance remains n = 3.** Within-job spread does **not** bound it.
  The replicates here share a calibration window, a queue position, and a thermal
  state; runs separated by hours or weeks do not. A small σ_device therefore licenses no
  claim about run-to-run stability, and the three between-run gap medians remain
  three points.
- **`exact`-arm spread stays at n = 2** (one pair, ~76% uncertain) and is reported
  as a descriptive number only. It is not used in the gate, which is defined on
  `cp3` alone.
- One device, one instance, one depth, one day. Unchanged from the prior runs.
