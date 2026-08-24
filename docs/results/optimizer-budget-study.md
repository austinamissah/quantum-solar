# The budget was binding, the budget was not the problem

Pre-registration: [`docs/plans/optimizer-budget-study.md`](../plans/optimizer-budget-study.md).
Artifact: `optimizer_budget.csv` (120 runs). Simulator only — no quantum time.

**Verdict: CONFIRMED-CLOSED at both α.** The encoding gate closed in
[`hardware-run-encoding.md`](hardware-run-encoding.md) was closed correctly. The
qualification added to it on 2026-08-04 was **cautionary, not consequential**, and
is downgraded accordingly.

## Why this was reopened

That gate was closed because "reps=2 ideal mass saturated at ~0.075 against a
required 0.078125". [`eval-censoring.md`](eval-censoring.md) then showed every
COBYLA arm in the supporting study had run at ≥99% of its evaluation cap, with the
ladder varying `n_starts` only — `maxiter` was pinned at 200 on every rung. So
"saturated" might have been the budget rather than a ceiling, and the gap that
closed the question might not have existed. The gap is real: it survives the
budget lift, which is what Family A below measures.

## The harness reproduces the original exactly

Two arms are the original rungs by construction. This gates the report: a drifted
harness makes every comparison meaningless, so the script refuses to print a
verdict if these miss.

| arm | α | reproduced | original | |
|---|---|---:|---:|---|
| `s5_m200` = `cobyla-5` | 0.021 | 0.06071 | 0.06071 | OK |
| `s5_m200` = `cobyla-5` | 0.030 | 0.05895 | 0.05895 | OK |
| `s50_m200` = `cobyla-50` | 0.021 | 0.07488 | 0.07488 | OK |
| `s50_m200` = `cobyla-50` | 0.030 | 0.07500 | 0.07500 | OK |

Five decimal places, four for four.

## Family A — the axis that was never varied

`n_starts` fixed at 5; `maxiter` 200 → 1000 → 5000. Bar = **0.078125**.

| arm (α=0.021) | cap | actual spend | mean mass | sd | clears |
|---|---:|---:|---:|---:|---:|
| `s5_m200` *(original)* | 1,000 | 1,000 (100%) | 0.06071 | 0.01246 | 1/10 |
| `s5_m1000` | 5,000 | 4,273 (85%) | 0.06632 | 0.00937 | 0/10 |
| `s5_m5000` | 25,000 | 9,483 (38%) | 0.06790 | 0.00698 | 0/10 |

**The premise was right and the conclusion still holds.** The budget was binding
— `s5_m200` hit its cap on **10/10** seeds — and lifting it helped: spend rose
on 10/10 seeds, mass improved on 9/10, and the paired gain is **+0.00719 (95% CI
[+0.0025, +0.0119])**, which excludes zero.

It is not enough. 25× the per-restart budget moves the mean from 0.0607 to
0.0679 and leaves **0.0102 still to find**. The improvement is real, measurable,
and roughly a third of what would be needed.

Crucially, `s5_m5000` spends only **38% of its cap**: COBYLA is now stopping
because it has converged, not because it was cut off. The ceiling that remains is
the optimizer's basin structure, not its budget. That is the distinction the
original study could not draw and this one can.

**One run in 120 cleared the bar** (0.08031) — and it came from `s5_m200`, the
*weakest* arm, the one run at the original budget. No arm with more budget ever
cleared. That is the signature of a lucky basin draw, not of a resource
constraint: if budget were the binding limit, the well-funded arms would clear and
the starved one would not. The opposite happened.

## Family B — the confound the original study carried

`cobyla-5/25/50` changed restarts **and** total budget together, so it could not
separate "more budget doesn't help" from "budget spent on restarts doesn't help".
Fixing the cap at 10,000 evaluations and splitting it three ways separates them:

| arm | allocation | mean (α=0.021) | mean (α=0.030) | spend |
|---|---|---:|---:|---:|
| `s50_m200` | 50 shallow restarts | **0.07488** | **0.07500** | 100% |
| `s10_m1000` | 10 medium | 0.07361 | 0.07025 | 84% |
| `s2_m5000` | 2 deep | 0.05353 | 0.05576 | 37% |

**At equal budget, allocation dominates.** Many shallow restarts beat few deep
ones by **40%**, consistently across both α. `s2_m5000` leaves 63% of its budget
unspent and still loses badly — more iterations cannot rescue too few basins.

So the original study's reading, that restarts were the productive axis, was
correct. It was correct for a reason it had not isolated, and now has.

## The pre-specified secondary: monotonicity

Family A means are monotone in budget at both α (0.06071 → 0.06632 → 0.06790, and
0.05895 → 0.06289 → 0.06290), consistent with extra evaluations descending further
rather than finding different basins.

The α=0.030 top rung is the exception worth flagging rather than smoothing: mass
is **identical to five decimals** between `s5_m1000` and `s5_m5000` (0.06289 vs
0.06290) while spending 36% more evaluations. Those extra evaluations bought
nothing at all. Consistent with fully converged basins, and the clearest single
illustration that the remaining gap is not a budget gap.

## What this changes

**The bar did not move and the primary instance was not reselected**, per the
pre-registration. Both were fixed before the run, and CONFIRMED-CLOSED is the
verdict that required neither.

- [`hardware-run-encoding.md`](hardware-run-encoding.md): the 2026-08-04
  qualification is downgraded from "the gap may not exist" to "the gap is real and
  survives 25× the per-restart budget". The closure stands.
- [`eval-censoring.md`](eval-censoring.md): an overstatement is corrected there.
  It said the optimizer study's budget-ladder conclusion "is not supported". Too
  strong. The untested axis was real and does help; testing it confirms the
  conclusion rather than overturning it.
- The **censoring finding itself is unaffected**. Capped counts were still bounds,
  the α\*-vs-default ratio was still censored on both sides, and α\* mass values
  are still lower bounds. What is now settled is that the bound, once lifted, does
  not reach the bar.

## The lesson that generalizes

The censoring study established that a metric sitting on its ceiling is a bound,
not a measurement. The natural next inference — *therefore the conclusion drawn
from it is wrong* — does not follow, and this is the counterexample.

> A censored measurement invalidates the **precision** of a claim, not
> automatically its **direction**. Lifting the cap here moved the number by a
> statistically clear +0.0072 and left the verdict untouched, because the gap was
> 3× larger than the effect the cap was hiding.

Both steps were necessary. Finding the censoring was right; assuming it overturned
the result was not. The only way to know which was to lift the cap and look.
