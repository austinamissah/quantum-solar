# Does depth help, net of noise? — results

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

## The mechanism: both depths retain the same fraction of their ideal

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

That stands. The two replicates here **share one job, one calibration snapshot, one
queue position and one thermal state**, so they are a within-job consistency check
and not the replication that sentence asks for.

## Limits

- **One job, one device, one day, one instance** — T=3, seed 0, `checkpoint(3)`,
  α = 0.021, `ibm_fez`. The reps=1 arm's normalized TVD here (0.3114, 0.3195) sits
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
