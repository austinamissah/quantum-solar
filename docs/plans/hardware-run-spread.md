# Pre-registration: powered within-job spread + third gap measurement

**Date:** 2026-08-03 — written **before** submission. Nothing has been run for
this plan. All circuit numbers below are from a real `ibm_fez` dry run.

Follows `docs/plans/hardware-run-encoding-replication.md` and its result.

## Purpose

**1. A properly-powered within-job spread estimate.** The replication run's
duplicate gate was **inconclusive**, and not merely for want of a stated
threshold: a spread from a *single pair* carries ~76% relative uncertainty, so
0.0389 was consistent with anything from 10% to 73% of the gap. Five replicates on
the `cp3` arm estimates the spread properly enough to adjudicate — within the
limits set out below, which are real.

**2. A third independent between-run gap measurement.** Two runs so far: gap
medians 0.0658 and 0.0934.

## Circuits — one job, seven circuits

| # | circuit | m | 2Q | depth | shots | role |
|---:|---|---:|---:|---:|---:|---|
| 1 | `cp3 @ α=0.021` r1 | 6 | 46 | 120 | 4,096 | **PRIMARY gap** |
| 2 | `exact @ α=0.021` r1 | 10 | 106 | 182 | 65,536 | **PRIMARY gap** |
| 3–6 | `cp3 @ α=0.021` r2–r5 | 6 | 46 | 120 | 4,096 | spread only |
| 7 | `exact @ α=0.021` r2 | 10 | 106 | 182 | 65,536 | spread only |

One job, one calibration snapshot. Backend pinned `ibm_fez`,
`optimization_level=3`, `seed_transpiler` pinned, params and counts guarded
against overwrite.

**Estimated ~66.6 QPU seconds** — not the ~41 assumed when this run was proposed.
The `exact` arm dominates: two circuits at 65,536 shots and depth 182 cost ~51.7 s
of the total, against ~14.9 s for all five `cp3` circuits. Recorded here so the
budget is not a surprise.

## The threshold, fixed and derived

The statistic is **σ̂**, the sample standard deviation of the five `cp3`
normalized-TVD values, expressed as a ratio to the measured gap.

**Derivation.** The primary gap is a difference between *one* measurement of each
arm. If a single measurement carries within-job SD σ_w, the gap's device-variance
standard error is `√2·σ_w`. For the gap to be resolvable at conventional
two-sided 95%:

```
|gap| > 1.96 · √2 · σ_w      ⟺      σ_w / |gap| < 1 / (1.96·√2) = 0.3608
```

> **Threshold: σ̂ / gap = 0.361.**

The number is not chosen for roundness — it is `1/(z₀.₉₇₅·√2)`, the point at which
device variance alone consumes the whole 95% interval of a one-replicate-per-arm
difference. Measuring σ̂ on `cp3` (4,096 shots, the noisier arm) and applying it to
both arms **overestimates** the gap's SE, since `exact` at 65,536 shots is
quieter. The threshold is therefore conservative — it declares "unresolved" more
readily than a two-arm estimate would.

### Point estimate or interval bound? — a three-way rule

The ambiguity that sank the last gate was never resolving this. It is resolved
here by refusing the binary. With 5 replicates σ̂ has 4 df, giving a 95% CI of
`[0.599, 2.874]·σ̂` — a span of 4.8x. Applying the threshold to the **interval**
yields three regions, all fixed now:

| region | condition | verdict |
|---|---|---|
| **RESOLVED** | σ̂/gap < **0.126** (CI upper bound below threshold) | Spread is confidently small. The gap stands. |
| **UNRESOLVED** | σ̂/gap > **0.602** (CI lower bound above threshold) | Spread is confidently large. The gap is not resolvable; see below. |
| **INDETERMINATE** | 0.126 ≤ σ̂/gap ≤ 0.602 | Neither. Reported as still undetermined — *not* forced to a verdict. |

**The indeterminate band is wide, and that is stated in advance rather than
discovered afterwards.** Five replicates is a real improvement on one pair, but it
does not make this test decisive across the plausible range. If the outcome lands
in the band, that is a legitimate and pre-registered result, and the correct
report is "still undetermined at n = 5", not a nudge to whichever side is closer.

Narrowing the band needs more replicates: the bounds scale as `√(df/χ²)`, so 10
replicates would give `[0.688, 1.826]·σ̂` and a band of `[0.198, 0.525]` — better,
but still wide. This gate does not become sharp cheaply.

## Primary gap — fixed rules

- The primary gap is **replicate 1 of each arm** (rows 1–2), fixed here and in
  `SPREAD_TARGETS` order in `scripts/experiment_hardware.py` before submission.
- **The extra `cp3` replicates are never pooled into the gap or its CI.** They
  estimate σ̂ and nothing else. Pooling would convert a variance measurement into
  a precision gain — the manoeuvre that makes a marginal result look solid.
- Analysis is identical to both prior runs: hardware-only bootstrap, B = 10,000,
  against an exactly-known statevector reference.

## This test can only weaken the headline

Stated plainly because it is the point of running it. There is **no outcome here
that strengthens the encoding claim.** A small σ̂ leaves the claim exactly where
two runs already put it; a large σ̂ removes it. Language for that outcome, written
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
  state; runs separated by hours or weeks do not. A small σ̂ therefore licenses no
  claim about run-to-run stability, and the three between-run gap medians remain
  three points.
- **`exact`-arm spread stays at n = 2** (one pair, ~76% uncertain) and is reported
  as a descriptive number only. It is not used in the gate, which is defined on
  `cp3` alone.
- One device, one instance, one depth, one day. Unchanged from the prior runs.
