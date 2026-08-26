# Pre-registration: does the depth result replicate across runs?

**Status: REGISTERED** by the commit that adds this file — written **before**
submission, with nothing yet run against it. Any later change to the prediction,
threshold or verdict sections is an amendment and has to say so. Circuit numbers
are from a real `ibm_fez` dry run on 2026-08-26; no QPU has been spent for this
plan.

Follows [`hardware-run-depth.md`](hardware-run-depth.md) and
[`../results/hardware-run-depth.md`](../results/hardware-run-depth.md).

## Purpose

The depth run returned **DEPTH HELPS**, and its own pre-registration said that
outcome needs replication before it counts as more than one job:

> This is the only outcome that argues for deeper circuits, and it would need
> replication before being reported as more than one job's result.

Its two replicates shared one calibration snapshot, one queue position and one
thermal state, so they measured within-job consistency and not this. **This run is
that replication**, and it is the only reason to spend the QPU seconds.

**It also gives the depth effect its first between-run estimate.** Between-run
variance is the term this project has repeatedly found it cannot bound: it stands
at n = 3 for the encoding gap and n = 1 for depth. After this run it is n = 2 for
depth, which is still small, and the plan says so rather than pretending otherwise.

## Circuits — identical to the depth run, one job

| # | circuit | m | 2Q | depth | shots | role |
|---:|---|---:|---:|---:|---:|---|
| 1 | `cp3 @ α=0.021` reps=1 r1 | 6 | 46 | 120 | 4,096 | **PRIMARY pair** |
| 2 | `cp3 @ α=0.021` reps=2 r1 | 6 | 112 | 245 | 4,096 | **PRIMARY pair** |
| 3 | `cp3 @ α=0.021` reps=1 r2 | 6 | 46 | 120 | 4,096 | within-job spread |
| 4 | `cp3 @ α=0.021` reps=2 r2 | 6 | 112 | 245 | 4,096 | within-job spread |

**Estimated ~14.0 QPU seconds.** The depth run's actual was 6.0 against the same
estimate, so 6 is the likelier figure.

**The angles are the depth run's angles, not re-tuned.** The plan entry points at
`hardware_params_depth.json` deliberately. A replication of a between-run question
has to hold the circuits fixed; re-tuning would introduce new angles as a second
variable alongside the calibration window, and the window is the thing under test.

## The statistic, the prediction, and the threshold

> **Provenance.** Drafted by an AI assistant at the author's request and **adopted
> by the author as written**, on 2026-08-26, before submission. The prediction is
> registered as the author's own; the drafting is recorded because the README
> discloses the assistant's role and reserves the registered predictions to the
> author. Same arrangement as [`hardware-run-depth.md`](hardware-run-depth.md).

**Statistic: unchanged from the depth run** — hardware optimal mass, replicate 1 of
each depth, difference reps=2 minus reps=1. Feasible mass secondary, normalized TVD
reported and not gating. Using a different statistic here would make the two runs
incomparable, which would defeat the purpose.

**Prediction: the effect reproduces.** The difference in hardware optimal mass is
**positive and exceeds 0.00765**, the same threshold the depth run registered and
derived as the 95% shot-noise floor.

**This prediction is not a bold one, and that is worth stating.** The answer from
run 1 is known: +0.03613 and +0.03320 on two replicates, roughly 4.7x the
threshold. A replication's prediction is nearly free to get right, so its value is
not in the prediction surviving. It is in the **measurement** reproducing, and in
the between-run difference being recorded whatever it is. The informative content
of this run is the magnitude, not the sign.

**Secondary, and the part that could actually surprise.** Run 1's two arms retained
the **same fraction** of their ideal optimal mass: 0.850 against 0.845, and 0.750
against 0.760. That is the mechanism the write-up rests on, and it is a much
sharper claim than the sign of a difference. **Predicted: the two arms' retention
again agree within 0.02** in each replicate.

## Verdicts, written now

| region | condition on the primary difference | verdict |
|---|---|---|
| **REPLICATED** | > 0.00765, same sign as run 1 | The depth effect survives a change of calibration window. Combined with run 1 it is n = 2 runs, which is what the depth write-up's caveat asks for and no more. |
| **FAILS TO REPLICATE** | ≤ 0.00765, or opposite in sign | Run 1's result does not survive, and the language below applies. |

**Pre-committed language for FAILS TO REPLICATE:**

> The depth effect measured on 2026-08-25 did not reproduce in a second job on the
> same device with the same circuits. A single-job result that does not replicate
> is **withdrawn**, not averaged: `docs/results/hardware-run-depth.md`, the README
> roadmap entry and the README hardware narrative all lose the DEPTH HELPS claim,
> and the falsification of the depolarizing model that rests on it is reduced to a
> claim about one job. The registered prediction of that run was still falsified,
> which is independent of whether the direction replicates.

**On the retention check specifically:** if the difference replicates but retention
does *not* agree between arms, the result stands and its stated mechanism does not.
That would be reported as the mechanism being unsupported, not quietly dropped.

## What this still cannot do

- **n = 2 runs is not a variance estimate.** Two runs give a difference, and the
  1-df χ² upper factor of 31.9 that
  [`hardware-run-spread.md`](hardware-run-spread.md) records makes any bound from
  it vacuous. This run makes the depth effect *replicated*, not *characterized*.
- **Same device, same instance, same encoding, same weight, same angles.** Only the
  calibration window moves. Nothing here generalizes past `ibm_fez` on this
  problem, and a result that replicates across two windows on one device says
  nothing about another device.
- **It does not revisit the noise model.** That model has now missed three times in
  the same direction (`docs/LESSONS.md` §3); this run neither refits nor tests it.
- **Legs 2 and 3 remain simulator findings** whatever this returns.
