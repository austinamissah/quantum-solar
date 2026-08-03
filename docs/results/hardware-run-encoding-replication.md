# Replication + weight/drift decomposition: results

**Headline:** the encoding claim is **replicated across two independent runs**
(Case A). The duplicate-spread gate is **inconclusive** — one replicate pair per
arm cannot estimate the spread precisely enough to adjudicate it.

**Run date:** 2026-08-03 · **Backend:** `ibm_fez` (pinned) · **56.0 QPU-seconds**
(estimated ~83.7) · Job `d9og4hna5u8s73e2n26g`, five circuits, one calibration
snapshot (median 2Q gate error 0.00274, readout 0.00830)

Pre-registered in `docs/plans/hardware-run-encoding-replication.md`.

| circuit | 2Q | TVD(ideal,hw) | normalized | implied `k` |
|---|---:|---:|---:|---:|
| `cp3 @ α=0.021` r1 | 46 | 0.0989 | **0.2590** | 0.00652 |
| `exact @ α=0.021` r1 | 106 | 0.1642 | **0.3623** | 0.00424 |
| `exact @ default` | 106 | 0.2997 | 0.4682 | 0.00596 |
| `cp3 @ α=0.021` r2 | 46 | 0.1137 | 0.2980 | 0.00769 |
| `exact @ α=0.021` r2 | 106 | 0.1613 | 0.3561 | 0.00415 |

## Gate 1 — duplicate spread: **INCONCLUSIVE**

| arm | r1 | r2 | spread |
|---|---:|---:|---:|
| `cp3 @ α=0.021` | 0.2590 | 0.2980 | **0.0389** |
| `exact @ α=0.021` | 0.3623 | 0.3561 | **0.0062** |

**The gate could not be decided on this data, and the reason is statistical, not
editorial.**

A spread estimated from a *single pair* is extremely imprecise. For two draws,

    sd|X₁ − X₂| / E|X₁ − X₂| = √(2 − 4/π) / (2/√π) = 0.756

— **≈76% relative uncertainty** (confirmed by Monte Carlo: 0.7554). So the
observed 0.0389 has a ±1 SD band of **[0.0095, 0.0683]**, which against the
bootstrap median gap of 0.0934 is **10% to 73% of the gap**. That range spans
"negligible" to "comparable". One pair per arm cannot distinguish them.

**Two separate failures, and fixing only the first would not have helped:**

1. *Wording.* The plan said "comparable to or larger than" without quantifying
   *comparable*, and in analysis I operationalised it as ≥50% — a threshold
   chosen **after seeing the data**. That is precisely what pre-registration
   exists to prevent.
2. *Power.* Even with a numeric threshold fixed in advance, **one pair per arm
   could not have adjudicated it.** A 76%-uncertain estimate straddles any
   threshold in the plausible range. Fixing the number is necessary but **not
   sufficient**.

**Requirement for any future use of this gate:** at least **3 replicates per
arm**, and preferably more. Precision of the spread estimate by replicate count:

| replicates | df | relative sd of the estimate |
|---:|---:|---:|
| 2 (this run) | 1 | **71%** |
| 3 | 2 | 50% |
| 5 | 4 | 35% |
| 10 | 9 | 24% |

Three replicates is a floor, not a target — even there the estimate is 50%
uncertain.

### Shot scaling: consistent with shot noise, not evidence against drift

With floors equalized the spread should scale as `1/√N`, predicting a ratio of
`√(65536/4096) = 4.0x` between the two arms. Observed: `0.0389 / 0.0062 = 6.3x`.
Same order of magnitude.

An earlier draft read this as showing "no evidence of large within-job device
drift". **That is too strong and is withdrawn.** A ratio of two single-pair
estimates carries roughly **107%** relative uncertainty, so 6.3x versus a
predicted 4.0x is entirely unremarkable — but by the same token it is far too
imprecise to *exclude* a drift component sitting underneath the shot noise.

The defensible statement is the weaker one: **the duplicate spreads are
consistent with shot noise alone, and this design cannot determine whether a
device-drift component is also present.** The term both bootstraps are blind to
remains unmeasured, not measured-and-found-small.

## Primary — CASE A: the encoding result REPLICATES

Bootstrap on replicate 1 only, hardware-only resampling against an exact
statevector reference, B = 10,000 — identical to the corrected first-run analysis,
with duplicates **not** pooled in:

| | median | 95% CI |
|---|---:|---|
| this run | **0.0934** | **[0.0578, 0.1290]** |
| prior run | 0.0658 | [0.0291, 0.1013] |

The median falls inside the prior interval, the CI excludes zero, and the
direction is the same. **This is case A: replicated.** `cp3` degrades measurably
less than `exact` on real hardware, now on two independent runs.

Per the pre-registered case-A rule, the pooled estimate across the two *runs* is
reported (a meta-analysis of independent measurements — not pooling duplicates
within a run, which stays prohibited), and n = 2 on **one device and one
instance** still does not establish generality.

## Weight / drift — CASE 3: partial, both contribute

At matched 106 gates, with `exact @ default` bit-identical to July's circuit:

| term | comparison | Δ`k` | share |
|---|---|---:|---:|
| **drift** | `exact@default` now (0.00596) vs July (0.00726) | −0.00130 | 43% |
| **weight** | `exact@α=0.021` (0.00424) vs `exact@default` now (0.00596) | −0.00172 | 57% |
| **total** | `exact@α=0.021` now vs July | **−0.00302** | 100% |

The two terms sum to −0.00302 against an observed total of −0.00302. The
decomposition closes almost exactly.

This is row 3 of the pre-registered decision table — `k` between ≈0.0044 and
≈0.0073 — so: **partial, both drift and weight contribute, and neither is claimed
alone.** The weight hypothesis is **supported and is the larger term**, consistent
with the prediction's direction (peakier default distribution degrades more, at
identical gate count). But the predicted magnitude was `k` ≈ 0.0073 near July's
value, and the measured 0.00596 is below that, because drift had also moved the
baseline.

### Correction: my earlier "drift is ruled out" was bad reasoning

The first run's writeup argued drift could not explain the `k` asymmetry because
"drift would have moved both arms, and `cp3` sits on July's mean." **That argument
was invalid**: `cp3` did not exist in July, so it has no July baseline. Comparing
its `k` to July's *range* is not the same as observing that it failed to move, and
the claim was never testable in the form I stated it.

The decomposition above shows drift is real (−0.00130) and accounts for 43% of
the shift. Applying that same drift to `cp3` puts its undrifted `k` at ≈0.0092 —
still inside July's range, which is precisely why the observation I treated as
ruling drift out was in fact consistent with it.

## Standing results, unaffected

The classical findings do not depend on any of this: `cp5band` capturing the full
$455.72/yr at 52 qubits against 117, the 349x ideal-mass improvement at T=3, and
the α\* = span/penalty rule.
