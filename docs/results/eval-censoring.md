# The optimizer budget was the measurement, not a setting

Pre-registration: [`docs/plans/eval-censoring.md`](../plans/eval-censoring.md).
Artifacts: `qaoa_scaling{,_alphastar}_T5.csv` (36 cells each, `maxiter=200`),
`qaoa_scaling{,_alphastar}_T5_maxiter1000.csv` (12 cells each, 5× budget).

`qaoa_evals` counts COBYLA function evaluations summed over restarts, and COBYLA's
`maxiter` caps evaluations **per restart**, so the total can never exceed
`n_starts × maxiter = 5 × 200 = 1000`. The α\* sweep reported ~1000. A number
sitting exactly on its own ceiling is not a measurement of optimizer effort; it is
the ceiling. This document is what happened when the ceiling was lifted.

**Headline: the cap bound the *result*, not just the count.** On the α\* arm, cells
at the cap moved a median of **100%** in `ideal_opt_mass` when given 5× the
budget, against a pre-registered threshold of 10%. Every α\* mass value in
[`slack-free-encoding.md`](slack-free-encoding.md) is therefore a **lower bound**,
and the numbers there are conservative rather than wrong.

---

## 0. The metric had never run at the sizes it was being asked about

Before any of this could be measured, a bug had to be fixed, and it is the most
transferable part of the episode.

The `ideal_opt_mass` column computed the exact distribution with
`Statevector(QAOAAnsatz(...))` on an **un-decomposed** ansatz. `QAOAAnsatz` holds
the phase separator as a single `PauliEvolutionGate`, and realizing that gate
means **exponentiating a 2^m × 2^m operator**. It is fine at m=6 and raises
`MemoryError` inside SciPy's sparse `expm` at m=14.

> The column had **never produced a value above T=3**. It was added, committed, and
> run, and the sweep died hours in, at T=4, every time.

The cost Hamiltonian is diagonal — `qubo_to_ising` emits only I and Z terms — so no
exponentiation is needed at all: the cost layer is an elementwise phase and the
mixer is a per-qubit rotation. `quantum_solar/statevector.py` does that in NumPy,
agrees with Qiskit to **2.9×10⁻¹⁶**, and handles m=22 in 5.3 s where the old path
failed at m=14. `main()` now runs that cross-check *before* spending anything and
refuses to proceed if it drifts.

**The lesson is not "Qiskit is slow."** It is that the expensive object was never
the statevector — 2^18 amplitudes is 4 MB — but the *operator* the library built
on the way there. The failure scaled with a quantity nobody was tracking.

---

## 1. Census: how much was at the cap

36 cells per arm (T ∈ {2,3,4,5} × 3 seeds × 3 reps), `maxiter=200`.

| cells at exactly 1000 evals | reps=1 | reps=2 | reps=3 | total |
|---|---:|---:|---:|---:|
| **α\*** | 0/12 | 5/12 | 11/12 | **16/36** |
| **default** | 0/12 | 1/12 | 5/12 | **6/36** |

**Censoring is a `reps` effect, not a `T` effect.** At reps=1 nothing is censored
in either arm at any size; at reps=3 almost everything is. More variational
parameters need more evaluations, and problem size barely enters. The question was
posed as a property of "the α\* sweep"; it is a property of circuit depth.

Against the pre-registered ladder: C=16 clears "C ≥ 1 → the ratio is a bound" and
**does not** clear "C ≥ 18 → systematically budget-limited". Reported as it fell.
44% is close enough to half that a threshold chosen afterward would have been
tempting.

### The detector undercounts, by construction

`qaoa_evals == 1000` proves *every* restart exhausted its budget. A total below
1000 can still hide individual capped restarts, and the aggregate cannot separate
them. The cap-lift data shows how bad this is: cells that grew their eval count
when offered more budget — the operational definition of "was budget-limited" —
number **8/12 (α\*)** and **11/12 (default)**, where the aggregate test flagged
only 5 and 2. **Every count in the table above is a floor.**

---

## 2. The ratio: both sides were pinned, so it read as a null

The claim under test was an α\*-vs-default eval ratio of 1.17×, said to be a lower
bound because the numerator was censored.

**It is worse than a lower bound. The denominator is censored too** (6/36), so both
sides are pinned at 1000 and the ratio is dragged toward 1.0 *by construction*.
Pooled over all 36 pairs it reads mean-of-ratios **1.033**, median **1.000**,
ratio-of-totals **0.998** — a tidy "no difference" that is an artifact of the cap.

Restricting to pairs uncensored on both sides — the only unbiased estimate
available — and stratifying by reps, because pooling hides a sign flip:

| stratum | clean pairs | α\*/default evals | 95% CI |
|---|---:|---:|---|
| reps=1 | 12/12 | **0.593** | [0.479, 0.708] |
| reps=2 | 7/12 | 1.361 | [0.960, 1.761] |
| reps=3 | **0/12** | — | not estimable |

**At reps=1, where nothing is censored, α\* converges in ~41% *fewer* evaluations
than default weights** — the opposite direction to "α\* costs more iterations", and
the only interval here that excludes 1.0. The reps=2 point estimate is above 1 but
its interval contains 1.0, so it supports nothing on its own. At reps=3 there is
not a single pair where both sides ran free.

**1.17× could not be reproduced.** No natural pooling of this sweep yields it:
all-cells 1.033 / 1.000 / 0.998; by T, 0.887 / 0.921 / 0.918 / 1.405. The closest
is T=5 alone at 1.405. Treat 1.17× as unverified rather than as a bound to tighten.

---

## 3. Cap lift: paired, 5× budget, same cells

Pre-registered subset: seed 0, all T, all reps, 12 cells per arm, `maxiter`
200 → 1000 (cap 1000 → 5000).

### The α\* arm shows a clean dose-response

| α\* stratum | n | median \|Δ mass\| | max |
|---|---:|---:|---:|
| fully censored (all 5 restarts capped) | 5 | **100.0%** | 247.6% |
| partially censored (some restarts capped) | 3 | 5.1% | 10.8% |
| converged (used no extra budget) | 4 | **0.0%** | 0.0% |

Monotone in how budget-starved the cell was, with an exactly-zero floor. Four cells
consumed *identical* eval counts with the cap raised (362→362, 331→331, 391→391)
and returned bit-identical mass, so the pipeline is deterministic where it should
be and every non-zero move above is real, not restart noise.

The reps=3 cells, which is where the censoring lives:

| cell | evals | ideal mass |
|---|---|---|
| T=2 | 1000 → 4915 | 0.0909 → **0.1879** |
| T=3 | 1000 → 3300 | 0.006343 → 0.006333 |
| T=4 | 1000 → 4701 | 0.000436 → **0.001514** |
| T=5 | 1000 → 2465 | 1.7×10⁻⁵ → ~0 |

At T=2 the mass **doubled on budget alone**, with the encoding, the weight, and
the optimizer untouched.

### The verdict turns on a choice the pre-registration failed to pin

The registered classifier (`evals == 1000`) gives median 100% and fires.
Reclassifying on *"did the cell use more budget when offered"* pools the weakly
affected partial cells in and drops the median to **8.0% — below the 10%
threshold, flipping the verdict.**

This is the recurring defect from LESSONS §5, committed again: the threshold, the
subset, and the direction of risk were all pinned in advance, and the *classifier*
was left loose. It decided the outcome.

The registered verdict stands — the strata are ordered and the control is exactly
0.0%, so dilution by weakly-affected cells explains the 8.0% better than a null
does — but that is a judgment made after seeing the data and should be read as
one.

### The default arm cannot answer

Only **1 of 12** default cells genuinely converged, and it moved 88.1%. With n=1
there is no control, so the default arm cannot separate a budget effect from
optimizer stochasticity. **Not estimable** — not agreement, and not a null.

### A caveat on magnitude, not on validity

At T=5 the α\* masses are ~10⁻⁵ and one cell went 1.7×10⁻⁵ → 4×10⁻⁹ (the −100%).
These are exact statevector values with no sampling floor, so the changes are real
— but they are large *relative* changes on a quantity already far below anything
decision-relevant. LESSONS §3 applies to reading them, even though the metric
itself is no longer the thing that is broken.

---

## 4. What this changes

**Direction of the error is favorable, as pre-registered.** This experiment could
only reveal the α\* result to be understated. It did.

- The **440× mass shift** and the **0.0716–0.0750 vs 0.078125 bar** in
  `slack-free-encoding.md` are lower bounds. Qualified in place there.
- Re-running the 440× also showed it is **sensitive to α in the third decimal**:
  α=0.0209 → 0.08839 (465×), α=0.021 → 0.07265 (382×). A 0.5% change in the weight
  moves the mass 22%. The `0.00019` endpoint reproduces exactly; the `0.0832` one
  does not reproduce at any single stated α. The finding survives as
  "several-hundred-fold"; the three-significant-figure precision does not. This is
  independent of the budget question and was found only because the re-run happened.
- The **optimizer study** inherits this. Every COBYLA arm ran at ≥99% of its own
  cap (`cobyla-5` ~1,000 of 1,000; `cobyla-25` ~4,950 of 5,000; `cobyla-50` ~9,900
  of 10,000), and the ladder varied **`n_starts` only** — `maxiter` was fixed at
  200 throughout. So "the budget ladder saturates below the bar" is a statement
  about three points that were all budget-exhausted, and *iterations per restart
  was never a rung on the ladder*. It is the axis that moved mass by 100%+ here.
  The study's finding about **starts** ("more starts converge on one basin rather
  than finding better ones") is unaffected; ~~its implied conclusion about **budget
  in general** is not supported~~.

  > **Corrected 2026-08-05 — that last clause was too strong.** "Not supported"
  > overreached: it treated an untested axis as an untrue conclusion. The axis was
  > since tested directly
  > ([optimizer-budget-study.md](optimizer-budget-study.md), 120 runs,
  > pre-registered). Iterations-per-restart *is* a real axis — 25× the budget buys
  > a paired +0.0072 with a 95% CI excluding zero — and the conclusion **survives
  > it**: the gap is 0.0102, so the budget effect closes under a third of it, and
  > the best-funded arm then converges at 38% of its cap. The right statement is
  > that the study's conclusion held **for a reason it had not demonstrated**, and
  > now has. See the closing section of that document: a censored measurement
  > invalidates a claim's *precision*, not automatically its *direction*.

**What is not affected:** the a-priori derivation of α\* itself (a property of the
problem, computed with no reference to any optimizer), the exactness sweep over
200 instance seeds, the encoding comparison, and every hardware result.

---

## 5. What a fixed budget should have been

The cap was fixed at `maxiter=200` for reproducibility, which is right. The defect
is that a *fixed* budget was reported as if it were a *sufficient* one, with no
check that the optimizer had stopped wanting more.

The check costs nothing and belongs next to any recorded eval count:

> **Record the cap alongside the count, and flag equality.** `experiment_scaling.py`
> now writes `maxiter` and `evals_censored` per row and prints a warning naming how
> many rows are censored. A count that equals its cap is a bound, and a table of
> bounds should not be read as a table of measurements.

And, because the aggregate test is one-sided: **the check that discriminates is
whether the run consumes more when offered more.** That requires one re-run at a
raised cap, which is what settled this.
