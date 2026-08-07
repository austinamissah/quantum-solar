# Does α\* buy reproducibility? — results

**Pre-registered:** [`../plans/basin-structure.md`](../plans/basin-structure.md).
Every definition below (τ, the clustering rule, the seed budget, the α ladder, the
falsification criteria) was fixed before the sweep ran. Simulator and exact
computation only — **no QPU was spent**.

**Run:** `python scripts/basin_study.py` → `basin_study.csv`, `basin_study.json`,
`basin_distributions.npz`. 1,200 tunings (10 α × 40 seeds × 3 instances),
`qiskit` 2.5.0, `qiskit-aer` 0.17.2, `scipy` 1.18.0, `numpy` 2.5.1.
**τ = 0.043286** (sd 0.004802), recomputed at run time from 400 resamples and
matching the registered value.

## Verdict: the registered prediction is FALSIFIED

The prediction was a **U-shape with a strict minimum at α\***. The falsification
criterion was "basin count at α\* is not a **strict** minimum over the ladder".

It is not strict. Basin count is **1 at α\* and 1 at every α below it**, then rises
monotonically above. There is no lower branch.

| α | basins @τ | @τ/2 | @2τ | single-linkage | max pairwise TVD | `<H>` spread |
|---:|---:|---:|---:|---:|---:|---:|
| 0.003 | 1 | 1 | 1 | 1 | 0.0060 | 0.0000 |
| 0.006 | 1 | 1 | 1 | 1 | 0.0109 | 0.0001 |
| 0.010 | 1 | 1 | 1 | 1 | 0.0039 | 0.0000 |
| 0.0209 | 1 | 1 | 1 | 1 | 0.0008 | 0.0000 |
| **0.021 (α\*)** | **1** | 1 | 1 | 1 | 0.0011 | 0.0000 |
| 0.030 | 2 | 2 | 2 | 2 | 0.2590 | 0.1495 |
| 0.060 | 3 | 3 | 3 | 3 | 0.5842 | 0.5284 |
| 0.100 | 3 | 4 | 3 | 3 | 0.6313 | 0.7478 |
| 0.300 | 9 | 9 | 9 | 9 | 0.7820 | 1.8497 |
| 1.000 | **19** | 22 | 13 | 16 | 0.8079 | 6.3374 |

Primary instance (T=3, seed 0, checkpoint(3), reps=1), N=40. Both robustness
instances reproduce the pattern exactly — 1 through α\*, then 2, 3, 3, 9–10, 17–19
— and are reported, not used to decide.

**What was right and what was wrong.** The upper branch is confirmed and is
stronger than predicted. The lower branch does not exist *in this metric*. The
mechanism posited for it — weak penalties leaving many competitive infeasible
assignments — is real, but it does not show up as basin multiplicity: the search
converges just as reproducibly to a single **wrong** basin. The prediction was
wrong about the shape, not about the physics below α\*.

## The result that replaces it: α\* is a boundary, not a midpoint

Basin count alone is the wrong lens, because a single basin can be the wrong
basin. Crossing it with the exactness of the encoding gives the actual structure:

| α | QUBO minimizer is the true optimum? | basins | regime |
|---:|:--:|---:|---|
| 0.003 | **no — infeasible** | 1 | reproducible and **wrong** |
| 0.006 | **no — infeasible** | 1 | reproducible and **wrong** |
| 0.010 | yes | 1 | **usable** |
| 0.0209 | yes | 1 | **usable** |
| 0.021 | yes | 1 | **usable** |
| 0.030 | yes | 2 | exact, reproducibility going |
| 1.000 | yes | 19 | exact, irreproducible |

> **The usable window on this instance is 0.010 ≤ α ≤ 0.021, and α\* = 0.0209 sits
> at its upper edge.**

That is the operationally useful finding, and it is a **warning the project did not
have**: α\* is not a safe midpoint with margin on both sides. Going 1.4× above it,
to α = 0.030, already doubles the basin count. The α\* rule buys the largest penalty
margin that is still inside the single-basin regime — and nothing more. Below 0.010
the encoding breaks; above 0.021 reproducibility does, immediately.

This also sharpens `LESSONS` §1. The 48× overshoot was known to cost *solution
quality*; it also costs **reproducibility**, and by a lot — 19 distinct basins out
of 40 tunings at the default weight, against 1 at α\*.

### Reproducible is not good — the registered limitation earning its place

At α = 0.003 the tuned circuit puts **0.0567** mass on the QUBO's minimizer, higher
than α\*'s 0.0448. That number is worthless: the minimizer there is **infeasible**,
so the mass sits on a state that is not a schedule. Anyone reading basin count or
mass without the exactness column would conclude the low-α end looks fine. It does
not. This was pre-registered as a limitation and it is the main way this result
could be misread.

## Sensitivities, all pre-committed

- **Cutoff.** The *count* at high α is cutoff-dependent (α=1.0: 22 / 19 / 13 at
  τ/2 / τ / 2τ). The *conclusion* is not — every α ≤ α\* gives exactly 1 basin at
  every cutoff and on every instance. Report the count at high α as "many, order
  10–20", not as a precise integer.
- **Linkage.** Complete and single linkage agree everywhere except α = 1.0, where
  single linkage chains basins together (instance 2: **17 complete vs 7 single**).
  Flagged as registered; the headline uses complete linkage, which is why it was
  chosen in advance.
- **Seed budget.** Basin count grows with N at high α, as expected — more tunings
  find more basins. The window's single-basin result is stable from N=5.

## Selection stability — and a correction it forces

The lowest-`<H>` rule was expected to be unstable in N. **It is not**, at N ≥ 10:

| α | N=5 | N=10 | N=20 | N=40 |
|---:|---:|---:|---:|---:|
| 0.021 (α\*) | 0.000 | 0.000 | 0.000 | 0.000 |
| 0.300 | 0.141 | 0.141 | 0.141 | 0.141 |
| 1.000 | 0.147 | 0.148 | 0.149 | 0.149 |

(TVD of the selected circuit to the α\* reference. The winning *seed* changes; the
selected *basin* does not.)

> **Correction to `slack-free-encoding.md`, 2026-08-07.** Declining the encoding ×
> weight 2×2 rested partly on the claim that `cp3 @ default` is "ill-defined"
> because tuning is irreproducible. **That is too strong.** The landscape is
> irreproducible — 19 basins — but the *selection rule* is stable: lowest-`<H>`
> converges to TVD 0.1488 and stays there from N=10 to N=40. The cell is definable
> by pinning N ≥ 10 and the rule. The remaining objection to the 2×2 is only that
> the weight moves `cp3`'s circuit 4× less than `exact`'s, which is a weaker
> argument than the one originally given. This is the second part of that rationale
> to be walked back after measuring it, and both walk-backs went the same way:
> the argument was worse than the measurement.

## Limitations

Recorded in advance and all still binding: one instance family (T=3,
checkpoint(3), **reps=1** — nothing here transfers to reps=2, where the optimizer
study's open question lives); basin count is a property of *the pinned search*
(`n_starts=5`) and not of the true stationary-point structure; τ is tied to a
4,096-shot budget; and reproducibility is not quality.

**Not addressed by this study:** whether any of these basins clears the 0.078125
bar. That is the optimizer study's question and it stays **CONFIRMED-CLOSED**.
The best mass seen anywhere here is 0.0643, at an α where the encoding is broken.
