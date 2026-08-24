# Does the single-basin regime survive a second layer? — results

**Pre-registered:** [`../plans/basin-structure-reps2.md`](../plans/basin-structure-reps2.md),
committed at `1280f67` **before the sweep ran**; the script refuses to run against an
uncommitted or edited plan. Simulator and exact computation only — **no QPU was
spent**.

**Run:** `python scripts/basin_study_reps2.py` → `basin_study_reps2.csv`,
`basin_study_reps2.json`, `basin_distributions_reps2.npz`. 400 tunings
(10 α × 40 seeds), one instance, ~43 min. **τ = 0.039317** (sd 0.004902), recomputed
at run time from 400 resamples of the α\* reference.

**Instance:** T=3, seed 1, `checkpoint(3)`, **reps=2** — the optimizer study's
pre-designated primary. Bar = `5 / 2**6` = **0.078125**.

## Verdict: one prediction held, one is FALSIFIED

| | prediction | measured | outcome |
|---|---|---:|---|
| **P1** | basin count at α\* > 1 | **15** | **held** |
| **P2** | best mass at α\* < 0.078125 | **0.07952** | **FALSIFIED** |

**P1 held, and not narrowly.** The single-basin regime does not survive a second
layer — it does not even survive at the *bottom* of the ladder. At reps=1 the count
was 1 at α\* and 1 at every α below it. Here the smallest count anywhere is **11**.

**P2 is falsified.** One tuning of 40 reaches **0.07952** against a bar of 0.078125,
at an α where the encoding is sound. **A point above the bar exists in this
landscape**, and that is the first direct evidence of one on the primary instance.

## The sweep

| α | basins @τ | @τ/2 | @2τ | single | best mass | lowest-`<H>` mass | clears | encoding sound? |
|---:|---:|---:|---:|---:|---:|---:|---:|:--:|
| 0.003 | 11 | 22 | 4 | 3 | 0.0672 | 0.0672 | 0 | **no — infeasible** |
| 0.006 | 15 | 26 | 8 | 4 | **0.0959** | 0.0925 | **32** | **no — infeasible** |
| 0.010 | 15 | 25 | 8 | 9 | **0.0951** | 0.0850 | **15** | **no — infeasible** |
| 0.0209 | 17 | 24 | 10 | 11 | 0.0796 | 0.0758 | 1 | yes |
| **0.021 (α\*)** | **15** | 22 | 11 | 13 | **0.0795** | 0.0755 | **1** | yes |
| 0.030 | 18 | 20 | 14 | 12 | 0.0828 | 0.0757 | 1 | yes |
| 0.060 | 22 | 28 | 20 | 21 | 0.0744 | 0.0019 | 0 | yes |
| 0.100 | 20 | 22 | 19 | 19 | 0.0709 | 0.0004 | 0 | yes |
| 0.300 | 34 | 34 | 31 | 34 | 0.0875 | 0.0000 | 1 | yes |
| 1.000 | 37 | 39 | 35 | 36 | 0.0685 | 0.0000 | 0 | yes |

## The finding that matters: the point exists and the rule cannot reach it

P2 falsifying sounds like "the search was the limit, and a better search wins". The
data says something sharper and less convenient.

At α\*, over 40 tunings:

- mean mass **0.06379**, sd 0.00976, max **0.07952** — **1 of 40** clears;
- **1 of 15 basins** is above the bar;
- the clearing tuning is **seed 28**, and it ranks **12th of 40 by `<H>`**;
- the **lowest-`<H>`** tuning — the principled selection rule, the one `QAOASolver`
  already applies and the one `basin-structure.md` showed is stable in N — is seed 24
  at mass **0.07546**, which is **3.4% short of the bar**.

So the rule that this project uses to pick a circuit **does not pick the clearing
one**, and would not have at any seed budget, because the clearing basin is not the
lowest-`<H>` basin.

**`<H>` and mass are strongly correlated and still fail at the top.** Their
correlation at α\* is **−0.918** — this is not a broken proxy. It is a proxy that
works through the bulk and decouples exactly where the decision is made, which is
`basin-structure.md`'s landscape result at reps=1 restated with an operational price
attached: **3.4% of the bar, which is the whole remaining gap.**

## What this does NOT do

**It does not reopen `optimizer-budget-study.md`.** That study is CONFIRMED-CLOSED on
the question of whether any *arm* reaches the bar, where an arm is scored by its
**mean**. The mean here is **0.06379**, nowhere near. This study introduced no arms
and no budgets, exactly as its registration promised, and a single clearing tuning out
of 40 is not an arm clearing a bar.

What it does retire is the *interpretation* that had grown around that verdict — that
concentration on this instance is limited by the landscape, and that basin structure
was the obvious suspect. The landscape contains a clearing point. The obstacle is
**selection**, not existence and not budget.

## The registered trap fired, exactly as written

The plan required exactness beside every mass figure, because the reps=1 study found
that weak penalties put *more* mass on the QUBO's minimiser while that minimiser is
infeasible. Read the `clears` column alone and α = 0.006 is the best setting on the
page: **32 of 40 tunings clear the bar**, nearly a third above it.

It is worthless. At α = 0.006 the QUBO's minimum-energy assignment **is not a
feasible schedule**, so that mass sits on a state that is not an answer. The same
holds at 0.010. **Never read `clears` without `encoding sound?`.**

## The usable window is instance-dependent, and narrower here

`basin-structure.md` found the window `0.010 ≤ α ≤ 0.021` on instance 0, with α\* at
its **upper** edge. On instance 1 the encoding is still unsound at 0.010 and only
becomes sound at **0.0209** — so the window opens one rung later and **α\* sits just
above its lower edge instead.**

Exactness is a property of the QUBO, not of the depth, so this is a difference between
*instances*, not between reps=1 and reps=2. It means the window found on instance 0
**must not be quoted as a general result**: on this instance the sound region begins
where the other one's ended.

## Sensitivities, all pre-committed

- **Cutoff.** P1 holds at every cutoff: at α\*, 22 / 15 / 11 basins at τ/2 / τ / 2τ.
  The *conclusion* is cutoff-independent; the *count* is not, so quote an order —
  "10 to 20 at α\*" — never the integer.
- **Linkage.** Single linkage gives 13 against complete's 15 at α\*, and agrees on the
  verdict at every rung. Unlike reps=1, where the two diverged badly at α = 1.0, they
  track closely here — with this many basins there are no long chains left to make.
- **Seed budget.** Basin count **grows monotonically with N at every α and never
  saturates** (α\*: 3 → 6 → 9 → 15 at N = 5 → 10 → 20 → 40). **15 is a lower bound**,
  and a larger budget would find more. This is the one number here most sensitive to
  the pinned search.

## Limitations

Recorded in advance and all still binding:

- **One instance, one depth, one encoding.** Nothing here transfers to another seed,
  any more than the reps=1 result transferred to this one — which it did not, in the
  strongest possible way.
- **Basin count is a property of the pinned search** (`n_starts=5`, `maxiter=200`),
  not of the true stationary-point structure, and it had not saturated at N=40.
- **τ is tied to a 4,096-shot budget.** A different shot count is a different notion
  of "distinct".
- **The clearing tuning is one parameter vector.** It reproduces deterministically
  from seed 28 at the pinned settings, and nothing here shows it is reachable by any
  rule that does not already know the answer.
- **The bar was not moved and the instance was not reselected.** Both were fixed in
  the registration and both survive it.

## What this changes

- **`slack-free-encoding.md`'s open question has an answer.** "No arm at any budget
  reaches the bar, and what limits concentration is unidentified" — the limit is not
  that the landscape lacks a clearing point. It has one at α\*. The limit is that
  `<H>`-based selection does not find it.
- **`basin-structure.md`'s headline is depth-specific.** "One basin at and below α\*"
  is a reps=1 statement. At reps=2 the minimum count anywhere on the ladder is 11.
- **The α\* rule keeps its footing for a different reason than before.** At reps=1 it
  bought a single basin. Here it buys nothing of the kind — but it is still the best
  rung on the sound part of the ladder by lowest-`<H>` mass (0.0755 against 0.0019 at
  α = 0.060), and the rungs that beat it on *best* mass do so with 34 basins and a
  selection rule returning 0.0000.
