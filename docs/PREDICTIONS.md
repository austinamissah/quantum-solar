# Registered predictions and how each resolved

One row per prediction registered in `docs/plans/` before its run, scored against
the write-up that resolved it. A plan that registered two predictions has two rows.
`tests/test_predictions_ledger.py` pins the table: every plan has a row, every link
resolves, and the counts match the prose in [`FINDINGS.md`](FINDINGS.md).

*held* and *falsified* are decided at the definition the plan pinned. *rule verdict*
marks the five studies that registered a decision rule rather than a directional
claim; the rule's own verdict word is quoted in the outcome column, and the value is
never used where a falsification condition was met. *not run* is empty: all fourteen
plans ran. The experiment I designed, costed and declined never had a plan file; it
is in [`DECISIONS.md`](DECISIONS.md).

**Counts: 26 predictions — 13 held, 8 falsified, 5 rule verdicts, 0 not run.**

| plan | what was predicted | what happened | verdict | result |
|---|---|---|---|---|
| [basin-structure.md](plans/basin-structure.md) | basin count is minimized at α\*, rising on both sides: a U-shape with a strict minimum | no lower branch; count is 1 at α\* and at every rung below it, rising to 19 at the default weight | **falsified** | [basin-structure.md](results/basin-structure.md) |
| [basin-structure-reps2.md](plans/basin-structure-reps2.md) | P1: at reps=2 the single-basin regime does not survive, so basin count at α\* exceeds 1 | 15 basins at α\*, and 11 is the smallest count anywhere on the ladder | **held** | [basin-structure-reps2.md](results/basin-structure-reps2.md) |
| [basin-structure-reps2.md](plans/basin-structure-reps2.md) | P2: the best of 40 tunings at α\* stays below the 0.078125 bar | one tuning reached 0.07952 | **falsified** | [basin-structure-reps2.md](results/basin-structure-reps2.md) |
| [eval-censoring.md](plans/eval-censoring.md) | a verdict ladder on the censored-cell count and the median mass shift, not a directional claim | ladder fired: 16 of 36 α\* cells at the cap, and censored cells moved a median 100% against a 10% threshold, so every α\* mass is a lower bound | *rule verdict* | [eval-censoring.md](results/eval-censoring.md) |
| [hardware-run.md](plans/hardware-run.md) | device-noise distance rises with transpiled two-qubit gate count | monotonic across 37, 77, 124 and 290 gates: 0.119, 0.203, 0.383, 0.459 | **held** | [experiment_hardware.ipynb](../notebooks/experiment_hardware.ipynb) |
| [hardware-run.md](plans/hardware-run.md) | H1: at each size, reps=1 hardware optimal mass is at least reps=2's; refuted, the plan says, if reps=2 exceeds reps=1 | reps=1 won at 2 slots and reps=2 at 3 slots, which is the stated refutation; the notebook records it as "partially supported at best" because the 3-slot counts sit at the shot floor (1 and 9 of 4096) and the ordering mirrors the ideal one | **falsified** | [experiment_hardware.ipynb](../notebooks/experiment_hardware.ipynb) |
| [hardware-run-depth.md](plans/hardware-run-depth.md) | primary: a dead heat on hardware optimal mass, the depolarizing model's +0.000003, against a 0.00765 threshold | +0.03613, and +0.03320 on the second replicate | **falsified** | [hardware-run-depth.md](results/hardware-run-depth.md) |
| [hardware-run-depth.md](plans/hardware-run-depth.md) | secondary: depth loses on feasible mass, −0.018976 | +0.07959, the opposite direction | **falsified** | [hardware-run-depth.md](results/hardware-run-depth.md) |
| [hardware-run-depth-replication.md](plans/hardware-run-depth-replication.md) | primary: the depth effect reproduces, positive and past 0.00765, in a new calibration window | +0.03027, with all four measurements across two windows spanning +0.03027 to +0.03613 | **held** | [hardware-run-depth-replication.md](results/hardware-run-depth-replication.md) |
| [hardware-run-depth-replication.md](plans/hardware-run-depth-replication.md) | secondary: the two depths' retention of ideal optimal mass agrees within 0.02 in each replicate | 0.063 in replicate 1, 0.017 in replicate 2, so the result's stated mechanism is unsupported | **falsified** | [hardware-run-depth-replication.md](results/hardware-run-depth-replication.md) |
| [hardware-run-encoding.md](plans/hardware-run-encoding.md) | primary ordering test: `cp3`'s normalized TVD is lower than `exact`'s | 0.3043 against 0.3708, bootstrap gap CI [0.0291, 0.1013] excluding zero | **held** | [hardware-run-encoding.md](results/hardware-run-encoding.md) |
| [hardware-run-encoding.md](plans/hardware-run-encoding.md) | secondary magnitude test: `cp3` at 0.301 in [0.237, 0.349] and `exact` at 0.562 in [0.463, 0.628] | `cp3` inside its band; `exact` at 0.3708, below its band, the second time the noise model predicted more degradation than occurred | **falsified** | [hardware-run-encoding.md](results/hardware-run-encoding.md) |
| [hardware-run-encoding.md](plans/hardware-run-encoding.md) | secondary: `cp3` retains a larger fraction of its ideal feasible mass than `exact` | 84.7% against 87.9%, so the predicted direction on the fraction is wrong, though `cp3` still delivers more usable output in absolute terms | **falsified** | [hardware-run-encoding.md](results/hardware-run-encoding.md) |
| [hardware-run-encoding-replication.md](plans/hardware-run-encoding-replication.md) | primary: the normalized gap reproduces inside the prior interval [0.0291, 0.1013] | 0.0934, inside it, so case A: replicated | **held** | [hardware-run-encoding-replication.md](results/hardware-run-encoding-replication.md) |
| [hardware-run-encoding-replication.md](plans/hardware-run-encoding-replication.md) | weight arm: `exact @ default` shows a higher implied `k` than `exact @ α=0.021` and lands near July's 0.00726 | "partial, both drift and weight contribute", decision-table row 3: `k` = 0.00596, higher as predicted but short of July's value, splitting 43% drift and 57% weight | *rule verdict* | [hardware-run-encoding-replication.md](results/hardware-run-encoding-replication.md) |
| [hardware-run-spread.md](plans/hardware-run-spread.md) | a three-way variance gate on σ_device against a cap of 0.361 × gap | "INDETERMINATE": the point estimate 0.01743 fails the 0.01616 cap, and only the width of the χ² interval keeps that from being the verdict | *rule verdict* | [hardware-run-spread.md](results/hardware-run-spread.md) |
| [optimizer-budget-study.md](plans/optimizer-budget-study.md) | a three-way verdict ladder on whether any arm clears the bar once the capped axis is varied | "CONFIRMED-CLOSED at both α": the gap survives 25× the per-restart budget | *rule verdict* | [optimizer-budget-study.md](results/optimizer-budget-study.md) |
| [optimizer-budget-study.md](plans/optimizer-budget-study.md) | secondary: mass increases monotonically with evaluations actually spent | monotone at both α, 0.06071 → 0.06632 → 0.06790 | **held** | [optimizer-budget-study.md](results/optimizer-budget-study.md) |
| [optimizer-study.md](plans/optimizer-study.md) | a PASS criterion on the pre-designated primary instance, with three interpretation rules covering the outcomes | "INSTANCE-DEPENDENT", rule 2: all 12 arm × α combinations fail on primary instance 1, while every cell on instances 2 and 3 has a passing arm | *rule verdict* | [slack-free-encoding.md](results/slack-free-encoding.md) |
| [selection-rule.md](plans/selection-rule.md) | P1: feasible mass beats `⟨H⟩` in strictly more held-out cells than it loses | 7 wins, 2 losses, 6 ties | **held** | [selection-rule.md](results/selection-rule.md) |
| [selection-rule.md](plans/selection-rule.md) | P2: feasible mass finds a clearing tuning in more than half the cells that contain one | 7 of 9, as did `⟨H⟩`, so the cells discriminated nothing | **held** | [selection-rule.md](results/selection-rule.md) |
| [selection-rule-replication.md](plans/selection-rule-replication.md) | P1: feasible mass picks the argmax tuning in at least 80% of band cells | 12 of 12 | **held** | [selection-rule-replication.md](results/selection-rule-replication.md) |
| [selection-rule-replication.md](plans/selection-rule-replication.md) | P2: it beats `⟨H⟩` in strictly more cells than it loses | 12 wins, 0 losses | **held** | [selection-rule-replication.md](results/selection-rule-replication.md) |
| [selection-rule-replication.md](plans/selection-rule-replication.md) | P3: where `⟨H⟩` misses the bar but some tuning clears it, feasible mass clears in more than half, or is reported not estimable if no such cell exists | 3 of 3, the stratum being non-empty after all | **held** | [selection-rule-replication.md](results/selection-rule-replication.md) |
| [selection-rule-scaling.md](plans/selection-rule-scaling.md) | P1: at T=7 the true optimum is present in a 4,096-shot sample in fewer than half of 20 tunings | 7 of 20 | **held** | [selection-rule-scaling.md](results/selection-rule-scaling.md) |
| [selection-rule-scaling.md](plans/selection-rule-scaling.md) | P2: feasible mass matches or beats `⟨H⟩` in at least 3 of the 4 sizes | 4 wins, 0 losses | **held** | [selection-rule-scaling.md](results/selection-rule-scaling.md) |

## Amendments, and where the falsified count comes from

`hardware-run-encoding.md`'s magnitude prediction is scored on its amended form. The
first draft predicted 0.486 and 0.765 from a model fitted to optimal mass; checked
against normalized TVD, that model overpredicted by +33%, +76%, +36% and +6% on
July's four circuits, and the per-circuit decay-rate bands in the row replaced it
before submission. The amended form is the one that failed. The same plan was also
amended to real-backend gate counts before submission, which widened the predicted
separation slightly.

Four write-ups headline a falsification in their verdict line, which is the number
`FINDINGS.md` and the README give. Counted per prediction there are eight: both
secondaries in `hardware-run-encoding.md` failed under headings that name the noise
model rather than the prediction, and H1 in `hardware-run.md` met its own refutation
condition and is recorded in the notebook as "partially supported at best". The test
pins both numbers; they count different things.
