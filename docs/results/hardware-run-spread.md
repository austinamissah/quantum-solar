# Within-job spread + third gap measurement: results

**Verdict: INDETERMINATE** on the pre-registered gate. Device variance is real and
substantial (70% of the replicate spread), the point estimate **fails** the
threshold, and the interval straddles it. Three runs now agree in direction and
the pooled estimate excludes zero, but **the individual runs' published intervals
were too narrow** — they omitted a device term this run measures for the first
time.

**Run date:** 2026-08-03 · `ibm_fez` (pinned) · **48.0 QPU-seconds** (estimated
~81.3) · Job `d9ojlotoh1qc73bc2b8g`, twelve circuits, one calibration snapshot
(median 2Q error 0.00274, readout 0.00891)

Pre-registered in `docs/plans/hardware-run-spread.md`.

## Step 1 — σ_device decomposition

Ten `cp3` replicates, normalized TVD:

```
0.2845  0.2688  0.2985  0.2278  0.2473  0.2859  0.2792  0.3058  0.2967  0.2557
mean 0.2750    sample sd 0.02496    range 0.0780
```

| quantity | value |
|---|---:|
| σ_total (sample sd, 10 replicates) | 0.02496 |
| σ_shot (bootstrap, same counts) | 0.01787 |
| **σ_device = √(σ_total² − σ_shot²)** | **0.01743** |

The subtraction is comfortably positive — **device variance is 70% of the total
spread**, not a residual. The negative-case rules did not need to be invoked.

This is the first direct measurement of the term both prior bootstraps were blind
to, and it is not small.

## Step 2 — the three-way gate: INDETERMINATE

| quantity | value |
|---|---:|
| gap (replicate 1 only) | 0.0448, CI [0.0068, 0.0807] |
| cap = 0.3608 × gap | 0.01616 |
| σ_device point estimate | **0.01743** |
| σ_device 95% interval (9 df) | [0.00000, 0.04192] |

**The point estimate exceeds the cap** — σ_device/gap = **0.389** against a
threshold of 0.361 — meaning the best available estimate says a gap measured from
one replicate per arm is *not* resolvable against device variance. But the
interval straddles the cap, so by the pre-registered rule the verdict is
**INDETERMINATE**, not UNRESOLVED.

That is an uncomfortable split and it is reported as it fell, not resolved toward
either side. The rule was fixed on the interval precisely so this could not be
argued after the fact.

**A third unstated choice, flagged.** The plan said `cap = 0.361 × gap` without
specifying *which* gap — this run's, or the pooled estimate. Both were computed:

| denominator | gap | cap | point ratio | interval verdict |
|---|---:|---:|---:|---|
| this run's | 0.0448 | 0.01616 | 0.389 (fails) | INDETERMINATE |
| pooled mean | 0.0680 | 0.02453 | 0.256 (passes) | INDETERMINATE |

**The verdict is the same either way**, so nothing turns on it here — but the
point estimate flips, and that is the third consecutive plan in which an
unspecified analysis choice could have decided an outcome. The pattern is the
finding: stating a threshold is not enough; every quantity entering it must be
pinned too.

## Step 3 — third between-run gap, and what it does to the earlier two

| run | gap | shot-only CI (as published) | **+ device CI** | excludes 0? |
|---|---:|---|---|---|
| 1 | 0.0658 | [0.0291, 0.1013] | [+0.0055, +0.1261] | yes |
| 2 | 0.0934 | [0.0578, 0.1290] | [+0.0334, +0.1534] | yes |
| 3 | **0.0448** | [0.0068, 0.0807] | **[−0.0160, +0.1056]** | **no** |

Adding the now-measured device term (`√2·σ_device` = 0.02465 on a
one-replicate-per-arm gap) widens every interval. **Run 3 no longer excludes
zero.** Runs 1 and 2 still do, run 1 only narrowly.

**The published intervals in the two prior results documents are therefore too
narrow.** They captured sampling variance only. That is a correction to those
documents, not a reinterpretation of their data.

### Pooled across three runs

| | |
|---|---:|
| mean gap | 0.0680 |
| between-run sd | 0.02437 |
| t(2) 95% CI | **[+0.0075, +0.1285]** |
| all three positive | yes (sign test p = 0.25) |

The pooled estimate still excludes zero and the direction is consistent 3/3.

**This interval needs no device correction.** Unlike the per-run intervals above,
it derives from the between-run scatter, which already subsumes every variance
component — shot noise, within-job device variance, and between-run drift — since
each run's gap is one realization of all three. Adding σ_device to it would
double-count.

**Between-run variance remains unbounded, and is *not* measured to exceed
σ_device.** On 2 df the between-run sd of 0.02437 carries a 95% interval of
**[0.0127, 0.1532]**, and σ_device = 0.01743 falls inside it. The two are
statistically **indistinguishable**, and the data are consistent with either
ordering.

An earlier draft of this document said run-to-run variation "exceeds what
within-job replication explains", from a bare point comparison of 0.02437 against
0.01743. **That is retracted.** It is the same failure this document criticises
one level up — comparing point estimates without their intervals — and at n = 3
the interval is far too wide to support it. What holds is only that within-job
spread does not *bound* between-run variance, which was known in advance.

## Where this leaves the headline

Not withdrawn — the pre-registered UNRESOLVED trigger was not met, and the pooled
three-run interval excludes zero with consistent direction. But **weakened, and
specifically so**:

- Single-run intervals overstated precision by omitting device variance. Any
  claim resting on one run is not supported at the precision it was published
  with.
- The best point estimate of σ_device/gap (0.389) says a single-pair gap is not
  resolvable. Only the width of the χ² interval prevents that from being the
  verdict.
- The honest statement is now: **across three runs the slack-free encoding shows
  a consistently positive but small reduction in device degradation, pooled
  [+0.0075, +0.1285], with run-to-run variation of the same order as the effect.**

The classical results are untouched and depend on none of this: `cp5band` at 52
qubits for $0.00/yr, the 349x ideal-mass improvement at T=3, and the
α\* = span/penalty rule.

## Still unmeasured

- **Between-run variance is n = 3**, with 2 df and a 95% interval of
  [0.0127, 0.1532] — a 12x span. It is neither bounded nor distinguishable from
  σ_device, and no claim about their relative size is supported.
- **`exact`-arm device variance remains unbounded** (n = 2, σ_total 0.00434). As
  pre-registered, if it were large the gate would err toward *keeping* the
  headline. This run cannot test that, and the risk direction is unchanged.
- One device, one instance, one depth.
