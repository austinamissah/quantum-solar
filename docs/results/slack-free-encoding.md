# Slack-free SoC encodings: results

**Status:** all measurements complete. **Two distinct hardware questions were
asked, and they had different outcomes — do not conflate them.**

- **H1 (does depth help, net of noise?)** — judged on *ideal optimal mass*, gate
  5x uniform. **Never submitted.** The gate was not met on the instance
  designated in advance, though it *was* met on both robustness instances, so
  that failure is instance-dependent rather than a verdict on the method. See
  `docs/plans/optimizer-study.md`.
- **Does the slack-free encoding reduce *device degradation*?** — judged on
  TVD(ideal, hardware), a different metric entirely. **Three runs submitted on
  `ibm_fez`, 146 QPU-seconds total.** Result below.

## Summary

The exact SoC encoding spends `(T−1)·b` qubits on slack. Replacing it with a
**sound** checkpoint encoding — one whose zero-penalty assignments are provably
feasible — removes most of that, and the removal is close to free:

- **`cp5band` captures the entire $455.72/yr battery value at 52 qubits against
  the exact encoding's 117.** Halving the qubit count costs nothing; going fully
  slack-free (48 qubits) costs $113.93/yr, so the last four qubits are the
  expensive ones.
- **At T=3, like-for-like: ideal optimal mass 0.00013 → 0.0453 (349×), and 133 →
  54 transpiled two-qubit gates**, at 6 qubits instead of 10.

### Hardware: three runs, pooled

`cp3` (6 qubits, 46 gates) against `exact` (10 qubits, 106 gates) — same instance,
same optimum, same depth, same weight, shot-noise floors equalized.

| run | normalized gap | job |
|---|---:|---|
| 1 | 0.0658 | `d9of01va5u8s73e2ljhg` |
| 2 | 0.0934 | `d9og4hna5u8s73e2n26g` |
| 3 | 0.0448 | `d9ojlotoh1qc73bc2b8g` |

> **Pooled: mean 0.0680, t(2) 95% CI [+0.0075, +0.1285], all three positive.**
> Across three runs the slack-free encoding shows a consistently positive but
> **small** reduction in device degradation, with run-to-run variation of the same
> order as the effect.

Three qualifications, all load-bearing:

- **The single-run intervals originally published were too narrow.** They captured
  shot noise only. The third run measured the device term directly
  (σ_device = 0.01743, **70% of the replicate spread**); including it, run 3 alone
  no longer excludes zero. The pooled interval above needs no such correction —
  between-run scatter already subsumes every variance component.
- **The pre-registered variance gate returned INDETERMINATE**, and awkwardly: the
  point estimate σ_device/gap = 0.389 *fails* the 0.361 threshold, and only the
  width of the χ² interval keeps that from being the verdict.
- **Between-run variance is unbounded at n = 3** (95% interval [0.0127, 0.1532])
  and is *not* distinguishable from σ_device. No claim about their relative size
  is supported.

A separate decomposition, using a circuit bit-identical to the one July ran,
found the `k` asymmetry is **43% device drift, 57% penalty weight**.

Full detail per run: `hardware-run-encoding.md` (run 1),
`hardware-run-encoding-replication.md` (run 2 + the drift/weight decomposition),
`hardware-run-spread.md` (run 3 + the variance measurement).

Every claim made for the encoding held. What stopped the **H1** run — a separate
question from the device-degradation result above — was elsewhere, and it took
three corrections to locate:

1. **The dominant limit on ideal concentration was penalty scaling, not the
   encoding.** `default_weights` overshoots the objective span by **48×**, making
   cost nearly invisible in `<H>`. Rescaling moved reps=2 mass **440×** with
   nothing else changed. The fix is a priori: **α\* = span/penalty = 0.0209**,
   which predicts the exactness cliff exactly.
2. **Transpiled gate count was a second, independent limit** — T3/exact at 133
   gates would have degraded on hardware whatever the weights were. These two are
   separate causes and are not collapsed here.
3. **After both were addressed, reps=2 mass reached 0.0716-0.0750 against a
   required 0.078125** on the primary instance, and all 12 pre-registered
   optimizer arms failed to close it — but the same arms **pass reliably on both
   robustness instances** (up to 10/10 at 0.106). The primary instance is simply
   the hardest of the three.

The mechanism behind the shortfall is now precise: **`<H>` tracks optimal-state
mass through the bulk of the low-energy region and decouples in the final
approach to the minimum.** Correlation weakens ~40% from the best-5% to the
best-0.01% `<H>` band, and the refined argmin carries *less* mass than the mean
of the best-0.01% band — which is why partially-converged optimizers scored 14%
better than fully-converged ones.

A hardware candidate at this size now looks plausible, but it requires a fresh
pre-registration naming its instance in advance; selecting one that has already
been seen to clear is the error this discipline exists to prevent.

### Our own predictions that were wrong

Recorded with their reasoning rather than quietly replaced:

- **"$0 weekend days dilute annual regret."** They cannot — a $0 day contributes
  to neither numerator nor denominator. Regret went the *other* way (75% annual
  vs 32.5% synthetic) because tariff value concentrates into high-spread days.
- **"Dropping mutual exclusion is a lever on the gate."** It doubles the ground
  state manifold *and* `n_opt`, so the beats-random bar doubles in lockstep.
  Neutral by construction; it helps absolute counts only.
- **"reps=2 optimization is failing outright."** It achieved `<H>` = 1.14 vs
  reps=1's 16.08. Containment bounds `<H>`, not mass; inferring one from the
  other was the error.
- **"No `<H>`-minimizing procedure can clear the bar."** Too strong — the
  best-0.01% band's *maximum* grazes just above it. The argmin does not clear it,
  and the typical near-minimum point does not.

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

### Transpiler optimization level: a free 12-18% gate reduction

Independent of any encoding question, and worth recording on its own. The
submission path transpiled at `optimization_level=1`. Re-transpiling **the same
four July circuits** at level 3 gives:

| circuit | 2Q at o1 (July) | 2Q at o3 | reduction |
|---|---:|---:|---:|
| T2/reps1 | 37 | 33 | 11% |
| T2/reps2 | 77 | 71 | 8% |
| T3/reps1 | 124 | 109 | 12% |
| T3/reps2 | 290 | 237 | 18% |

Since device-noise TVD tracks two-qubit gate count monotonically on exactly these
circuits, this is a strict improvement at no cost — no change to the problem, the
encoding, the parameters, or the shot budget. It is now the default in
`scripts/experiment_hardware.py`.

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
(`docs/plans/optimizer-study.md`): **all 12 arm × α combinations fail on the
primary instance.** (They do *not* fail on the robustness instances — see
"INSTANCE-DEPENDENT" below, which qualifies everything in this subsection.)

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

### Landscape: `<H>` tracks mass through the bulk, and decouples near the minimum

Correlation at tightening low-`<H>` bands (n = 500,000 random parameter vectors
per α; the QAOA statevector is evaluated directly in numpy, verified against
qiskit to 4e-15):

| band | n | `<H>` range (α=0.021) | pearson | mean mass | max mass |
|---|---:|---|---:|---:|---:|
| global | 500,000 | [0.2636, 2.5630] | −0.396 | 0.01057 | 0.10696 |
| best 5% | 25,000 | [0.2636, 0.6548] | **−0.576** | 0.02894 | 0.10696 |
| best 1% | 5,000 | [0.2636, 0.4961] | −0.448 | 0.04374 | 0.08318 |
| best 0.1% | 500 | [0.2636, 0.3741] | −0.488 | 0.05722 | 0.08252 |
| best 0.01% | 50 | [0.2636, 0.3047] | **−0.328** | 0.06680 | 0.07880 |
| refined argmin | 1 | 0.2672 | — | **0.06570** | — |

α=0.030 behaves the same way: −0.617 (5%) → −0.544 (1%) → −0.650 (0.1%) →
**−0.371** (0.01%), mean mass 0.02334 → 0.03840 → 0.05272 → **0.06561**, refined
argmin **0.06361**.

The precise statement is neither "misaligned" nor "aligned":

> **`<H>` tracks mass through the bulk of the low-energy region and decouples in
> the final approach to the minimum.**

Three pieces of evidence, consistent across both α:

1. **Correlation weakens toward the minimum** — |r| falls ~40% from the best-5%
   band to the best-0.01% band (0.576 → 0.328, and 0.617 → 0.371). The decline is
   not gradual: it is concentrated in the last band, with 0.1% still strong.
2. **Mean mass rises monotonically as `<H>` tightens, then reverses at the
   argmin.** In both α the refined argmin carries *less* mass (0.06570, 0.06361)
   than the mean of the best-0.01% band (0.06680, 0.06561). Mass improves with
   `<H>` right up to the vicinity of the minimum, then falls in the final approach.
3. **The ceiling collapses** — max mass in band drops 0.10696 → 0.07880 as the
   band tightens, so the high-mass points live at moderately good `<H>`, not the
   best.

This explains why stopping short scored better: `cobyla-50` reached 0.0749, **14%
more mass than the refined argmin's 0.06570**, because incomplete convergence
leaves it in the region where the two objectives still agree.

It also corrects an over-strong claim of ours. "No `<H>`-minimizing procedure can
clear the bar" is not right even on this instance: max mass within the best-0.01%
band is 0.07880 (α=0.021) and 0.07947 (α=0.030), both marginally *above* the
0.078125 bar. What holds is that the argmin does not clear it and the typical
near-minimum point does not either — the band only grazes the bar at its top.

Asymmetry, deliberately handled: a sampled mass *maximum* is a valid lower bound
on what is achievable, but a sampled `<H>` *minimum* bounds nothing, so the `<H>`
side is refined by L-BFGS restarts rather than read off the sample.

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
