# Pre-registration: is the α* eval count censored?

> **Outcome: [`docs/results/eval-censoring.md`](../results/eval-censoring.md).**
> Registered verdict fired (16/36 α\* cells censored; capped cells moved
> `ideal_opt_mass` by a median of 100% vs 0.0% for converged cells). One defect in
> this plan is recorded there: the classifier below (`evals == cap`) was left
> loose, and the verdict flips under a more inclusive definition.

Written **before** the sweep was re-run and before any eval count was inspected.
The selection rule below is fixed here so that the choice of which cells get a
raised budget cannot be made after seeing which ones look favourable.

## The problem

`qaoa_evals` is `len(result.cost_history)` — COBYLA function evaluations summed
over all restarts. COBYLA's `maxiter` caps evaluations **per restart**, so

```
qaoa_evals ≤ n_starts × maxiter = 5 × 200 = 1000
```

The α* sweep reported ~1000 evals, which is *exactly* the ceiling. A value at its
own ceiling is not a measurement, it is a bound: the reported α*-vs-default eval
ratio of **1.17×** is therefore a **lower bound**, not an estimate. If α* cells sit
at the cap routinely, then the α* runs are also **under-converged**, and every
`ideal_opt_mass` in that sweep is a lower bound too — which would weaken the
headline "rescaling moved reps=2 ideal mass 440×" from a measured effect to a
floor.

Note the detector is one-sided: `qaoa_evals == 1000` proves *every* restart
exhausted its budget, but a total below 1000 can still hide individual capped
restarts. The aggregate cannot separate them, so counts below are counts of
**fully** censored cells and undercount censoring.

## What is measured

1. **Census.** Re-run the sweep at T ∈ {2,3,4,5} × seeds {0,1,2} × reps {1,2,3}
   (36 cells) at **both** weight modes, at the original `maxiter=200`, recording
   `qaoa_evals` and `evals_censored`. Report how many α* cells sit exactly at
   1000, broken down by T and reps. Report the same for default weights, since
   the 1.17× ratio has a censored denominator if default cells are capped too.

2. **Lift the cap.** Re-run a fixed subset at `maxiter=1000` (cap = 5,000), giving
   COBYLA 5× the budget.

   > **Subset, fixed in advance: `seed=0`, all T ∈ {2,3,4,5}, all reps ∈ {1,2,3}
   > — 12 cells.** Seed 0 is chosen because it is the first seed, not because of
   > anything observed in it. All 12 run regardless of whether they were censored,
   > so the uncensored cells act as a within-experiment control: if raising the
   > cap moves cells that were *not* at the cap, the movement is optimizer
   > stochasticity rather than budget.
   >
   > The α* mode runs unconditionally. The default mode runs **iff** the census
   > shows ≥1 censored default cell in the subset — otherwise its eval count is
   > already an estimate and re-running it measures nothing.

3. **The comparison.** For each of the 12 cells, paired on (T, seed, reps, mode):
   - `Δevals` — does the count exceed 1000 once allowed to?
   - `Δideal_opt_mass` — the question that matters. `ideal_opt_mass` is exact
     (statevector, no sampling floor), so any change is a real change in the
     variational state, not measurement noise.

## Interpretation, fixed in advance

Stated now so the verdict is not chosen to fit the numbers. Let *C* be the number
of censored α* cells out of 36, and let the mass comparison be over the 12-cell
subset.

| condition | verdict |
|---|---|
| C = 0 | 1.17× stands as an estimate. Nothing else follows. |
| C ≥ 1 | 1.17× is a lower bound and must be reported as such. |
| C ≥ 18 (half) | the α* sweep is **systematically** budget-limited, not incidentally |
| median \|Δideal_opt_mass\| ≤ 10% relative, on censored cells | the cap bound the *eval count* but not the *result*; mass values stand |
| median \|Δideal_opt_mass\| > 10% relative, on censored cells | the α* mass values are themselves lower bounds; the 440× and the "concentration is the limiting factor" reading both need restating |

The 10% figure is a judgement call, set before the data: it is well above the
~1–3% run-to-run spread the optimizer study reported for repeated COBYLA arms
(sd 0.0101 on a mean of ~0.06), so a change that clears it is not restart noise.

**Direction of the risk.** If the cap is binding, every α* number in
`docs/results/slack-free-encoding.md` is conservative — the true values are at
least as good. This experiment cannot make the α* result look worse; it can only
fail to improve it, or reveal that the reported improvement was understated.

## What is *not* measured

T=6 is excluded. Its cost is dominated by the optimization itself (m=22, ~2× the
T=5 statevector at every one of ≥1000 evaluations), and the censoring question is
answerable without it. Excluding it is a cost decision, stated rather than
silently dropped.
