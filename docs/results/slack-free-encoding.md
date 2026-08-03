# Slack-free SoC encodings: results

**Status:** all measurements complete. **No hardware run** — the pre-registered
gate was not met on the primary instance, though it was met on both robustness instances (see below).

## Summary

The exact SoC encoding spends `(T−1)·b` qubits on slack. Replacing it with a
*sound* checkpoint encoding removes most of that at no cost in dollars, and cuts
transpiled two-qubit gates by more than half. It did not, however, produce a
submittable circuit — for a reason that turned out to have nothing to do with the
encoding.

## Two independent limits, in order

These must not be collapsed into one cause.

**1. Penalty scaling bound ideal concentration.** `default_weights` sizes
penalties at ~10× the objective scale. At T=3 that is a penalty scale of 14.81
against an objective span of **0.3095** across the feasible set — a **48×**
overshoot. QAOA minimizes `<H>`, so cost is nearly invisible to it: at the
default weight, reps=2 reached `<H>` = 1.14 (96.6% of the way from the
uniform-superposition value of 33.47 to the QUBO minimum of 0.0042) while putting
**93.6%** of its mass on the feasible subspace and 0.019% on the optimum.
Rescaling the weight moved reps=2 ideal mass **440×** (0.00019 → 0.0832) with the
encoding and the optimizer untouched.

The correct weight is derivable a priori, with no reference to any mass:

> **α\* = (objective span) / (default penalty) = 0.0209**

verified at 100% optimal over 200 instance seeds at and above it, collapsing
below (61% at 0.010, 6% at 0.005, 1.5% at 0.003). This is the reusable result and
it supersedes the current 10× margin.

**2. Transpiled gate count was a separate, independent limit.** T3/exact at 133
two-qubit gates would have degraded on hardware *regardless of weights*. Fitting
a depolarizing model to July's one usable row gives ~1.32% effective error per
2-qubit gate; it predicts held-out TVD at 77 and 290 gates to within 3.5% and 1%.
It does **not** predict single-bitstring optimal mass for collapsed circuits —
device noise has structure and does not take the state to exactly uniform — which
is why the gate is on *ideal* mass, which can be computed exactly.

## Encoding results

`Checkpoint` is **sound**: pinning SoC every `k` slots bounds the between-checkpoint
excursion by `⌊k/2⌋`, so every zero-penalty assignment is genuinely feasible when
`⌊k/2⌋ ≤ min(k₀, n_max − k₀)`. Verified exhaustively at small `T` and by
`qubo_min_exact` through T=24. Spacing is pinned and validated, never derived.

### Annual dollars (Golden CO, real 365-day instance, battery worth $455.72/yr)

| encoding | qubits | lost $/yr | lost % | infeasible days |
|---|---:|---:|---:|---:|
| exact | 117 | 0.00 | 0.00 | 0 |
| **cp5band** | **52** | **0.00** | **0.00** | 0 |
| cp5 | 48 | 113.93 | 25.00 | 0 |
| cp3band | 62 | 0.00 | 0.00 | 0 |
| cp3 | 48 | 341.79 | 75.00 | 0 |
| none | 48 | — | — | **329** (bill invalid) |

**Halving the qubit count is free; the last four qubits cost $113.93/yr.**

Two things the synthetic study could not have shown:

- The real battery (10 kWh @ 2 kWh/slot) has a looser sound ceiling than the
  synthetic Q=3 family (k ≤ 5 vs 3), worth **$228/yr**. Capacity makes
  `Checkpoint` *less* conservative for free — the opposite of how the exact
  encoding scales.
- **A prediction we got wrong.** We expected the 104 flat-tariff weekend days,
  which earn exactly $0, to *dilute* annual regret below the per-day figure. They
  cannot: a $0 day contributes to neither numerator nor denominator, so it drops
  out of the ratio rather than pulling it toward zero. Measured regret went the
  other way — `cp3` loses **75%** annually against 32.5% on the synthetic day —
  because the tariff concentrates battery value into a minority of high-spread
  days needing deep cycles held across many slots, exactly the shape checkpointing
  forbids. Scaling a synthetic day would have understated the cost by >2×.

### Circuit cost (FakeFez; o1 reproduces July's 37/77/290 exactly)

| circuit | qubits | 2Q (o1) | 2Q (o3) | ε |
|---|---:|---:|---:|---:|
| T3/exact (July, 1 count) | 10 | 133 | 111 | 0.77 |
| **T3/cp3** | **6** | **54** | **50** | **0.49** |
| T4/cp3band | 9 | 149 | 125 | 0.81 |
| T6/cp3band | 13 | 348 | 269 | 0.97 |

Like-for-like at T=3, the encoding took ideal mass from 0.00013 to **0.0453
(349×)** at 54 gates instead of 133. T=6 and T=4 are ruled out: their reps=2
circuits (269 and 267 gates) are past the coherence limit, and a candidate that
can only run one depth cannot answer a question about depth.

A structural result at T=3: with spacing 3 there are **no interior checkpoints**,
so the encoding reduces to objective + mutual exclusion + terminal. Soundness
still covers it (the single gap of 3 ≤ k bounds the excursion to 1 step), so no
interior SoC penalty is needed at T=3 at all.

## Why there is no hardware run

At the a-priori weight, reps=2 ideal mass is **0.0716–0.0750** against a required
**0.078125** (5 × uniform at m=6). Pre-registered optimizer study
(`docs/plans/optimizer-study.md`): **all 12 arm × α combinations fail.**

| arm | mean (α=0.021) | mean (α=0.030) | evals |
|---|---:|---:|---:|
| cobyla-5 | 0.06071 | 0.05895 | ~1,000 |
| cobyla-25 | 0.07348 | 0.07368 | ~4,950 |
| cobyla-50 | 0.07488 | 0.07500 | ~9,900 |
| spsa | 0.03691 | 0.03145 | 600 |
| lbfgs-sv | 0.06751 | 0.06307 | ~800 |
| transfer | 0.06502 | 0.06849 | ~740 |

The budget ladder **saturates below the bar** while variance collapses (sd 0.0101
→ 0.0032 → 0.0018). More starts converge on one basin rather than finding better
ones. The only clearing run in the entire study came from `cobyla-5`, the
*weakest* arm — so the clearing run had a **worse** `<H>` than runs that did not
clear. `transfer` is near-deterministic (sd 0.00014) and lands at 0.065: a free,
perfectly repeatable warm start, below the bar.

### The result is INSTANCE-DEPENDENT

The pre-registration's second interpretation rule fired. On the **robustness**
instances, arms pass — reliably:

| instance | α | best arm | mean | clears | verdict |
|---|---:|---|---:|---:|---|
| 1 (primary) | 0.021 | cobyla-50 | 0.07488 | 0/10 | fail |
| 1 (primary) | 0.030 | cobyla-50 | 0.07500 | 0/10 | fail |
| 2 | 0.021 | cobyla-50 | 0.08099 | 9/10 | **PASS+RELIABLE** |
| 2 | 0.030 | cobyla-50 | 0.07904 | 9/10 | **PASS+RELIABLE** |
| 3 | 0.021 | transfer | 0.10587 | 10/10 | **PASS+RELIABLE** |
| 3 | 0.030 | cobyla-25 | 0.09057 | 7/10 | PASS (unreliable) |

So **"QAOA's concentration on this problem is the limiting factor" is not
supported.** Four of six instance×α cells have at least one passing arm, and on
instance 3 four arms clear 10/10. Instance seed 1 — designated primary *in
advance*, which is the only reason this is a finding rather than a selection
effect — is simply the hardest of the three.

Arm ranking across all six cells: `cobyla-50` and `cobyla-25` pass in 4, and
`transfer` passes in 1 but does so at **949 evaluations against cobyla-50's
9,977** — 10× cheaper, sd 0.00102, 10/10. `cobyla-5` and `spsa` never pass.

Formally the study **fails on the primary instance**, and the bar is not moved
and the primary is not reselected. The honest reading is that a hardware
candidate at this size is plausible but must be established by a *fresh*
pre-registration designating its instance in advance — picking instance 3 now,
having seen that it clears, is precisely the error this discipline exists to
prevent.

### Landscape: `<H>` and mass are aligned in direction, but their optima are not

| α | pearson (best 5%) | mass at refined `<H>` min | achievable mass max |
|---:|---:|---:|---:|
| 0.021 | −0.574 | 0.06570 (below bar) | 0.24565 (3.1× bar) |
| 0.030 | −0.614 | 0.05398 (below bar) | 0.10858 (clears) |

The correlation is **negative** — lower `<H>` goes with *higher* mass — so by the
stated test `<H>` is **not** misaligned with the metric, and an earlier
"misaligned objective" framing of ours fails it. What is true is narrower: the
two argmins are far apart. On the primary instance the refined `<H>` optimum
captures only **26.7%** (α=0.021) and **49.7%** (α=0.030) of achievable mass, and
sits below the bar — so on *that instance* no `<H>`-minimizing procedure clears
it, while mass over 3× the bar exists at a worse `<H>`. Expressivity is ample;
the objective does not reach it. **This analysis is instance-1 only** and does not
generalize — the robustness results above show other instances clearing.

Asymmetry, deliberately handled: a sampled mass *maximum* is a valid lower bound
on what is achievable, but a sampled `<H>` *minimum* bounds nothing, so the `<H>`
side is refined by L-BFGS seeded from the 25 best sampled points plus 25 random
restarts.

### Soft encodings: `center` was mis-weighted, `wd` is genuinely bad

At the default `weight_scale=1`, `CenterAnchor` loses 100% of battery value. At
**`scale=0.001` it loses 28.79% with 0% infeasible** (T=24) — so "catastrophic"
was an artifact of the weight, the same mistake the penalty-scaling finding
identifies elsewhere. It is still not competitive (`cp5band` is 0%), but it is
not useless. `WindowDrift` does not recover at any scale: `wd2`/`wd3` are sound
but ~78-80% regret, `wd4`/`wd6` are 25-35% infeasible, and scales 0.1/1/10 are
bit-identical, since once the penalty dominates the argmin stops moving.

### A lever that turned out not to be one

Dropping the mutual-exclusion penalty doubles the QUBO ground-state manifold
(`c_t = d_t = 1` is physically idle when `e_c == e_d`). But the bar is
`5·n_opt/2^m`, and the physical optimum has 2 bitstring representations either
way, so uniform doubles in lockstep and the beats-random ratio is **unchanged by
construction**. It helps absolute shot counts, not the relative gate. An earlier
claim that this was worth a large factor conflated those two axes.

## Scope limits

- All concentration results are **ideal (noiseless) simulator**. The observed
  reps=2 > reps=1 ordering at correctly-scaled weights speaks to the **landscape**,
  not to H1's net-of-noise question. Any future hardware pre-registration must
  re-derive its reps prediction from gate counts and the noise model rather than
  inherit it from here.
- Concentration results are T=3 / `checkpoint(3)` / m=6 only.
- The annual dollar figures are one location, one tariff, one year (AMY 2018).
