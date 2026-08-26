# Does depth help, net of noise? — results

> **Replicated 2026-08-26, with one part corrected.** The primary result below
> reproduced in a second job:
> [`hardware-run-depth-replication.md`](hardware-run-depth-replication.md).
> **The mechanism proposed in this document did not**, and the section claiming it
> carries a correction in place.

**Pre-registered:** [`../plans/hardware-run-depth.md`](../plans/hardware-run-depth.md),
committed at `d0dbca7` **before submission**. One job
`da75ik6sidac73aetu50` on `ibm_fez`, four circuits, **6.0 QPU seconds** (the
pre-submission estimate was ~14.0). One calibration snapshot: median 2Q gate error
**0.0026924**, median readout error **0.0097656**, dated 2026-08-25 22:30:37-04:00.

## Verdict: the registered prediction is FALSIFIED, and the outcome is DEPTH HELPS

| | registered | measured | outcome |
|---|---|---|---|
| primary: Δ hardware optimal mass | **+0.000003** (a dead heat) | **+0.03613** | **falsified** |
| secondary: Δ hardware feasible mass | **−0.018976** (depth loses) | **+0.07959** | **falsified, and in the opposite direction** |

The threshold was 0.00765. The measured primary effect is **4.7x** that, and the
second replicate reproduces it independently at +0.03320. Both bootstrap intervals
exclude zero by a wide margin.

**The depolarizing model was wrong in the optimistic direction.** It predicted the
ideal 1.93x advantage of the deeper circuit would be exactly cancelled by 2.4x the
two-qubit gates. It was not cancelled; most of it survived.

**This is the third failure of that model, and the third in the same direction.**
[`hardware-run-encoding.md`](hardware-run-encoding.md) records the second, where
`exact` "degraded substantially *less* than predicted" and fell below its
pre-registered band, with the mass-fitted version having already failed against
July's normalized TVD before that. A model that has now missed three times, always
by predicting more degradation than occurs, is not merely wrong on this instance:
it is **systematically pessimistic about gate count**, and no result in this
repository should lean on it for a forward prediction. The registered prediction
above leaned on it, which is why the falsification was available to be had.

## The circuits

| circuit | 2Q | hw optimal mass | hw feasible mass | TVD(ideal,hw) | TVD(ideal,unif) | normalized |
|---|---:|---:|---:|---:|---:|---:|
| `cp3` reps=1 r1 | 46 | 0.03931 | 0.25488 | 0.1228 | 0.3945 | **0.3114** |
| `cp3` reps=2 r1 | 112 | **0.07544** | **0.33447** | 0.1556 | 0.5211 | **0.2986** |
| `cp3` reps=1 r2 | 46 | 0.03467 | 0.25146 | 0.1260 | 0.3945 | 0.3195 |
| `cp3` reps=2 r2 | 112 | 0.06787 | 0.33423 | 0.1708 | 0.5211 | 0.3278 |

Ideal (exact statevector) optimal mass is 0.04625 at reps=1 and 0.08925 at reps=2;
ideal feasible mass 0.28735 and 0.45313.

**Primary comparison, replicate 1** — fixed in the plan before submission:

| statistic | reps=1 | reps=2 | difference | bootstrap 95% CI |
|---|---:|---:|---:|---|
| optimal mass | 0.03931 | 0.07544 | **+0.03613** | [+0.02588, +0.04614] |
| feasible mass | 0.25488 | 0.33447 | **+0.07959** | [+0.06006, +0.09912] |

Replicate 2, which the plan reserved as a variance estimate and never pools into
the primary: +0.03320 [+0.02344, +0.04272] and +0.08276 [+0.06323, +0.10278].

## The mechanism proposed here, and withdrawn

> **Correction, 2026-08-26.** Everything in this section is what one job showed,
> and it did **not** replicate. In a second job 36 minutes later, with the same
> angles, the two arms' retention differed by **0.063** on the primary replicate
> against the **0.005** below, and normalized TVD went from flat (0.3114 against
> 0.2986) to plainly not flat (**0.2670 against 0.4585**). The reps=2 arm's
> retention alone moved from 0.845 to 0.771 between windows, a swing larger than
> the entire gap this section rested on.
>
> **Equal retention was a property of that job, not of these circuits.** The
> paragraphs below are left standing rather than edited, because the claim was
> published and deleting it would hide that it was made.
>
> **What replaces it.** The deeper circuit *does* degrade more; its ideal advantage
> of 1.93x is simply larger than the extra degradation, so it finishes ahead
> anyway. That is the weaker and correct statement, and it is enough to explain the
> falsification. The registered prediction is still falsified and the primary
> result still replicates; only this explanation of it goes.
>
> Detail in
> [`hardware-run-depth-replication.md`](hardware-run-depth-replication.md).

This is the part that explains the falsification, and it was not predicted.

| replicate | reps=1 retention | reps=2 retention |
|---|---:|---:|
| r1 | 0.850 | **0.845** |
| r2 | 0.750 | **0.760** |

Retention is measured hardware optimal mass over ideal optimal mass. Within each
replicate the two depths retain **the same fraction** — 85% against 85%, then 75%
against 76% — despite the deeper circuit carrying 2.4x the two-qubit gates. The
depolarizing model, fitted to July's circuits at ~1.32% effective error per gate,
implies retention should fall roughly from 0.54 to 0.23 across that gate increase.
It does not fall at all.

Normalized TVD says the same thing from the other side: **0.3114 against 0.2986**
in replicate 1, i.e. the deeper circuit is marginally *closer* to its own ideal,
and 0.3195 against 0.3278 in replicate 2, marginally further. Across a 2.4x gate
increase the normalized degradation is flat to within the replicate spread.

So the per-gate error rate fitted to the July circuits **does not transfer** to
these. Whether that is because the fit was calibrated on a worse device day, or
because normalized TVD is not linear in gate count in this regime, or because these
particular circuits transpile into cheaper structure, is **not determined here.**

## What the plan pre-committed for this outcome

> This is the only outcome that argues for deeper circuits, and it would need
> replication before being reported as more than one job's result.

The two replicates here **share one job, one calibration snapshot, one queue
position and one thermal state**, so they are a within-job consistency check and
not the replication that sentence asks for.

**That replication was run on 2026-08-26 and the primary result held**, at +0.03027
and +0.03394 against this run's +0.03613 and +0.03320. The requirement is met for
the primary claim. It is not met for the mechanism, which the same run withdrew.

## Limits

- **One job here, two across both runs** — T=3, seed 0, `checkpoint(3)`, α = 0.021,
  `ibm_fez` throughout. The reps=1 arm's normalized TVD here (0.3114, 0.3195) sits
  above the same circuit's 0.2590 and 0.2980 in
  [`hardware-run-encoding-replication.md`](hardware-run-encoding-replication.md),
  which is between-run drift of the size that study already recorded, and n for
  between-run variance remains small.
- **The replicate spread is not negligible and cannot be bounded.** The two
  identical reps=1 circuits differ by 0.00464 in optimal mass, which is 61% of the
  registered threshold. The effect is about 8x that spread, so the verdict is not
  in doubt, but with 2 replicates the device variance itself is unestimable — the
  1-df χ² upper factor of 31.9 that [`hardware-run-spread.md`](hardware-run-spread.md)
  records makes any such bound vacuous.
- **Two depths, not a depth curve.** reps=3 was not submitted. Nothing here says
  the trend continues, and the gate count at reps=3 would leave the range in which
  any of these measurements were made.
- **This says nothing about legs 2 and 3.** A reps=2 circuit reaching hardware does
  not make the penalty-weight or selection-rule findings hardware results. Both
  remain simulator findings and [`../FINDINGS.md`](../FINDINGS.md) continues to say
  so.
- **The circuits were tuned by feasible-mass selection**, declared in the plan, not
  by the lowest-⟨H⟩ default. Both arms were tuned identically, so the depth
  comparison is internally consistent, but these are not the circuits a default
  `QAOASolver` run would have produced. See
  [`selection-rule-hardware-tuning.md`](selection-rule-hardware-tuning.md).
