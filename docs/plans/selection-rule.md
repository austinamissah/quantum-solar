# Pre-registration: can any selection rule find the clearing basin?

**Status:** registered, not yet confirmed. **Simulator and exact computation only —
no QPU.** Written **2026-08-23**.

[`basin-structure-reps2.md`](../results/basin-structure-reps2.md) found that a point
above the 0.078125 bar exists on the primary instance at reps=2, and that the rule
this project uses — **lowest `<H>`** — does not find it: the clearing tuning ranks
**12th of 40** by `<H>`, and the rule returns a tuning 3.4% short. This registers the
follow-up: **is there a rule that does find it?**

## Disclosed in full: this began as an exploratory search, and that search is not the result

**Candidate rules were chosen by looking at the 40 tunings at α\* on instance 1.**
That is a fitted choice on 40 points with roughly seven observables tried, and it is
disclosed here rather than presented as evidence. What was seen:

| rule (maximize) | rank it gives the clearing tuning | corr. with optimal mass |
|---|---:|---:|
| lowest `<H>` *(incumbent)* | 12 | 0.918 |
| lowest entropy | 1 | 0.925 |
| max single probability | 4 | 0.933 |
| lowest participation ratio | 1 | 0.959 |
| **total feasible mass** | **1** | **0.985** |
| mass on the best feasible state | 1 | 1.000 |
| lowest `<H>` variance | 39 | 0.117 |

Two things about that table are structural rather than empirical, and are stated so
they are not mistaken for findings:

- **"Mass on the best feasible state" is not a separate rule.** On this instance only
  7 of 64 states are feasible and the cheapest of them *is* the optimum, so that
  column is optimal mass computed without prior knowledge. Its correlation of 1.000 is
  an identity, not a discovery.
- **The optimum is identifiable from samples at this size.** Decode 4096 shots, keep
  the feasible outcomes, take the cheapest: this recovers the true optimum in **40 of
  40** tunings. So "optimal mass" is a *measurable* quantity here, not a privileged
  one, and any rule may use it — at m=6.

## The two questions, separated

**Q1 — the direct rule.** Select the tuning with the highest *measured* optimal mass.
This must work by construction; the only question is **cost**. Already measured on
instance 1 α\*, disclosed here: it picks the clearing tuning **26%** of the time at
4,096 shots, 46% at 16,384, 73% at 65,536, **98%** at 262,144. The gap between the
best tuning (0.07952) and the runner-up (0.07791) is 0.00162, against a shot-noise sd
of 0.00424 at 4,096 shots — **the margin is smaller than the noise the study used.**

**Q2 — a rule that generalizes.** At m=6 you can enumerate; at the sizes this project
cares about you cannot, and then a rule may use only the shape of the output
distribution. **Primary candidate: total feasible mass.** It needs no knowledge of the
optimum, only a feasibility check, which is cheap at any size. It is also the
physically motivated choice — the penalty weight exists to move mass onto the feasible
subspace, so this selects on whether the penalty did its job.

## What is predicted, and what would falsify it

**P1 — feasible mass beats `<H>` out of sample.** Across the held-out cells defined
below, selecting by highest total feasible mass returns a tuning whose optimal mass is
**at least as high** as the one lowest-`<H>` returns, in **strictly more cells than it
loses**.

*Falsified if* it loses in as many cells as it wins, or more.

**P2 — feasible mass finds the clearing tuning where one exists.** In held-out cells
that contain at least one tuning at or above the bar, selecting by feasible mass
returns a clearing tuning in **more than half** of them.

*Falsified if* it does so in half or fewer.

Both are reported at these definitions before any other cut.

## Held-out cells, fixed before they are computed

**Instances 2 and 3 at reps=2, the full α ladder, N=40** — swept fresh by
`python scripts/basin_study_reps2.py --instance 2` and `--instance 3`. Neither has been
computed at reps=2 and neither was used to pick the candidate rules.

Also reported, and **explicitly weaker evidence** because they share an instance with
the discovery set: the sound α rungs of instance 1 other than α\* — 0.0209, 0.030,
0.060, 0.100, 0.300, 1.000.

**α = 0.021 on instance 1 is the discovery cell and is excluded from both verdicts.**
It cannot be evidence for a rule that was chosen by looking at it.

**Unsound rungs are excluded from P2** (0.003, 0.006, 0.010 on instance 1, and
whichever rungs prove unsound on the new instances). A tuning "clearing the bar" where
the QUBO's minimizer is infeasible is the trap `basin-structure-reps2.md` documents,
and a rule that wins there has won nothing.

## Procedure

1. Sweep instances 2 and 3 at reps=2. ~45 min each, simulator only.
2. `python scripts/selection_rule_study.py` evaluates every rule on every held-out
   cell and writes `docs/results/selection_rule.json`.
3. Results to `docs/results/selection-rule.md`, reporting P1 and P2 at the pinned
   definitions before any other comparison.

The evaluation script **refuses to run** unless this plan is committed, and
**excludes the discovery cell by construction** rather than by remembering to.

## Limitations, recorded in advance

- **Seven observables were tried on 40 points.** Even a clean out-of-sample result
  makes feasible mass *a* rule that works here, not *the* rule, and not one shown to
  work at a size where the optimum cannot be enumerated.
- **Two held-out instances is a small sample.** With 10 rungs each, the cell count is
  adequate; the *instance* count is 2, and instance-dependence is a documented feature
  of this problem.
- **Nothing here is a hardware claim**, and nothing here reopens
  `optimizer-budget-study.md`, whose verdict concerns arms scored on their means.
- **The bar stays at 0.078125 and instance 1 stays primary.** Both are pre-registered
  elsewhere and are not touched by this study.
