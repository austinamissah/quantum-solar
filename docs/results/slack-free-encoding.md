# Slack-free SoC encodings: results

**Status:** all measurements complete.

The strongest results here are **classical and depend on no hardware measurement
at all** (Part 1). The hardware work (Part 2) asked **two distinct questions with
different outcomes** — one was never submitted, the other ran three times — and
they must not be conflated.

## Headline

The exact SoC encoding spends `(T−1)·b` qubits on slack. Replacing it with a
**sound** checkpoint encoding — one whose zero-penalty assignments are provably
feasible — removes most of that, and the removal is close to free:

- **`cp5band` captures the entire $455.72/yr battery value at 52 qubits against
  the exact encoding's 117.** Halving the qubit count costs nothing; going fully
  slack-free (48 qubits) costs $113.93/yr, so the last four qubits are the
  expensive ones.
- **At T=3, like-for-like: ideal optimal mass 0.00013 → 0.0453 (349×), and 133 →
  54 transpiled two-qubit gates**, at 6 qubits instead of 10.
- **`α\* = span/penalty = 0.0209`** — an a-priori penalty weight that predicts the
  exactness cliff, and supersedes `default_weights`' 10× margin.
- On hardware, across three runs: a **consistently positive but small** reduction
  in device degradation, pooled **[+0.0075, +0.1285]**, with run-to-run variation
  of the same order as the effect.

---

# Part 1 — Classical results

Everything in this part is simulator or exact computation. None of it depends on
a hardware measurement.

## The encoding

`Checkpoint` is **sound**: pinning SoC every `k` slots bounds the
between-checkpoint excursion by `⌊k/2⌋`, so every zero-penalty assignment is
genuinely feasible when `⌊k/2⌋ ≤ min(k₀, n_max − k₀)`. Verified exhaustively at
small `T` and by `qubo_min_exact` through T=24. Spacing is pinned and validated,
never derived.

> **Asymmetric hardware widens this gap (2026-08-07).** Once `charge_energy` and
> `discharge_energy` may differ, the SoC grid refines to their GCD, and the slack
> register — which must represent every level — widens with it. At T=6/Q=10 the
> `EXACT` encoding goes **27 → 37** qubits for a 2.0-in/1.5-out battery and **42**
> for 2.0/1.25, while `Checkpoint(3)` stays at **12 regardless**, having no slack
> register to widen. The slack-free encoding's advantage is therefore *understated*
> by the symmetric-rate comparison below: real inverters commonly charge and
> discharge at different rates, and every such split costs the exact encoding
> qubits and costs the slack-free one nothing. See `docs/ARCHITECTURE.md` on
> `soc_quantum`.

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

That $113.93 is the same figure the rate upgrade earns in
[`capacity-rate-sensitivity.md`](capacity-rate-sensitivity.md), to the cent, and it
is **not** a transcription between the two documents. Annual value is exactly
linear in delivered peak energy below the knee, at $56.9646/yr per kWh/day, so any
change worth 2 kWh/day of peak throughput comes to $113.93 — and both of these are.
`cp5` delivers 6 of the instance's 8 useful kWh/day; a 2 → 2.5 kW inverter takes it
from 8 to 10. Same constant, opposite signs, different code paths.

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

## Penalty scaling: the reusable rule

`default_weights` sizes penalties at ~10× the objective scale. At T=3 that is a
penalty scale of 14.81 against an objective span of **0.3095** across the feasible
set — a **48×** overshoot. QAOA minimizes `<H>`, so cost is nearly invisible to
it: at the default weight, reps=2 reached `<H>` = 1.14 (96.6% of the way from the
uniform-superposition value of 33.47 to the QUBO minimum of 0.0042) while putting
**93.6%** of its mass on the feasible subspace and 0.019% on the optimum.
Rescaling the weight moved reps=2 ideal mass **440×** (0.00019 → 0.0832) with the
encoding and the optimizer untouched.

> **Qualified 2026-08-04 — this is a lower bound, and its last digit is not
> stable.** Both numbers were produced at `n_starts=5, maxiter=200`, i.e. a hard
> cap of 1000 COBYLA evaluations, and the runs sat *on* that cap. Given 5× the
> budget, α\* cells that were at the cap moved their ideal mass by a median of
> **100%** (one reps=3 cell doubled, 0.0909 → 0.1879) while cells that had
> genuinely converged moved by **0.0%**. The rescaling effect is therefore at least
> this large; how much larger is unmeasured.
>
> Separately, on re-running: the `0.00019` endpoint reproduces exactly, but
> `0.0832` does not reproduce at any single stated α. The result is **sensitive to
> α in its third decimal** — α=0.0209 gives 0.08839 (465×), α=0.021 gives 0.07265
> (382×). A 0.5% change in the weight swings the mass 22%. **Read this as
> "several-hundred-fold", not as "440×"**; the precision implied by three
> significant figures is not there, and the direction of the sensitivity is the
> same direction as the budget effect. See [eval-censoring.md](eval-censoring.md).

The correct weight is derivable a priori, with no reference to any mass:

> **α\* = (objective span) / (default penalty) = 0.0209**

verified at 100% optimal over 200 instance seeds at and above it, collapsing
below (61% at 0.010, 6% at 0.005, 1.5% at 0.003). This is the reusable result and
it supersedes the current 10× margin.

## What limits QAOA concentration

After the weight was corrected, reps=2 ideal mass reached **0.0716–0.0750**
against a required **0.078125** (5 × uniform at m=6) on the pre-designated
instance. Pre-registered optimizer study (`docs/plans/optimizer-study.md`): **all
12 arm × α combinations fail on the primary instance** — but see the
instance-dependence result immediately below, which qualifies that.

> **Qualified 2026-08-04, resolved 2026-08-05 — the arms were budget-limited, and
> the conclusion survives it.** Every COBYLA arm ran at ≥99% of its own evaluation
> cap (`cobyla-5` ~1,000 of 5×200; `cobyla-25` ~4,950 of 25×200; `cobyla-50`
> ~9,900 of 50×200), so the masses below are lower bounds and the gap to the
> 0.078125 bar is an upper bound on the true shortfall. The ladder also varied
> **`n_starts` only** — `maxiter` was pinned at 200 across every rung.
>
> That axis has since been tested directly
> ([optimizer-budget-study.md](optimizer-budget-study.md), 120 runs,
> pre-registered). Raising `maxiter` 25× buys a paired **+0.0072** (95% CI
> excluding zero) and leaves **0.0102** still to find; the best-funded arm then
> spends only 38% of its cap, converging rather than being cut off. At a *fixed*
> 10,000-evaluation budget, allocation dominates: 50 shallow restarts beat 2 deep
> ones by **40%**. So "the budget ladder saturates below the bar" is confirmed —
> and the reason is now demonstrated rather than assumed. The bar is not reached
> by any arm at any budget tested.

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
ones. (The `evals` column above is each arm's *cap*, not a converged count — see
the qualification opening this section.) The only clearing run in the entire study came from `cobyla-5`, the
*weakest* arm — so the clearing run had a **worse** `<H>` than runs that did not
clear. `transfer` is near-deterministic (sd 0.00014) and lands at 0.065: a free,
perfectly repeatable warm start, below the bar.

> **`lbfgs-sv` is basin-stable under a roundoff-scale objective perturbation
> (measured 2026-08-06).** `lbfgs-sv` is the only arm that *optimizes* against the
> exact statevector rather than the shot estimator, so it is the only one whose
> search path can be moved by a change below reporting precision. Recomputing that
> objective on the NumPy statevector instead of Qiskit's perturbs it by ≤1.3e-15
> on `<H>` (≤1e-16 on mass) — and that is enough to move the L-BFGS-B trajectory
> in **16 of 20 (α, tuning-seed) cells**, which change evaluation count by up to
> 80 (e.g. 755 → 835).
>
> Every one of the 20 cells still converged to the same basin, and both α means
> reproduce the table above to the 5 d.p. it is published at (0.06751 / 0.06307).
> So the arm's landscape has **wide basins with unstable paths through them**: the
> reported means do not depend on the exact arithmetic route, but the `evals`
> column for this arm is only reproducible to ~±10%. Read that column as a scale,
> not a fixed cost. This is a property of the arm, not of the refactor that
> exposed it.
>
> *Resolution caveat: agreement was checked at 1e-5 logging resolution against a
> harness tolerance of 5e-4 — 50× inside the gate, but not a bitwise claim.*

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
effect — is the hardest of the three.

Arm ranking across all six cells: `cobyla-50` and `cobyla-25` pass in 4, and
`transfer` passes in 1 but does so at **949 evaluations against cobyla-50's
9,977** — 10× cheaper, sd 0.00102, 10/10. `cobyla-5` and `spsa` never pass.

Formally the study **fails on the primary instance**, and the bar is not moved
and the primary is not reselected. The supported reading is that a hardware
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

Asymmetry, deliberately handled: a sampled mass *maximum* is a valid lower bound
on what is achievable, but a sampled `<H>` *minimum* bounds nothing, so the `<H>`
side is refined by L-BFGS restarts rather than read off the sample.

## Encodings and levers that did not work

**Soft encodings.** At the default `weight_scale=1`, `CenterAnchor` loses 100% of
battery value. At **`scale=0.001` it loses 28.79% with 0% infeasible** (T=24) — so
"catastrophic" was an artifact of the weight, the same mistake the penalty-scaling
finding identifies elsewhere. It is still not competitive (`cp5band` is 0%), but
it is not useless. `WindowDrift` does not recover at any scale: `wd2`/`wd3` are
sound but ~78-80% regret, `wd4`/`wd6` are 25-35% infeasible, and scales 0.1/1/10
are bit-identical, since once the penalty dominates the argmin stops moving.

**A lever that turned out not to be one.** Dropping the mutual-exclusion penalty
doubles the QUBO ground-state manifold (`c_t = d_t = 1` is physically idle when
`e_c == e_d`). But the bar is `5·n_opt/2^m`, and the physical optimum has 2
bitstring representations either way, so uniform doubles in lockstep and the
beats-random ratio is **unchanged by construction**. It helps absolute shot
counts, not the relative gate. An earlier claim that this was worth a large factor
conflated those two axes.

---

# Part 2 — Hardware results

## Two questions, separated

| question | metric | outcome |
|---|---|---|
| **H1** — does depth help, net of noise? | ideal optimal mass, gate 5× uniform | **not submitted under this plan** — gate not met on the pre-designated instance. Answered later, on 2026-08-25, by [hardware-run-depth.md](hardware-run-depth.md) |
| **Encoding vs device degradation** | TVD(ideal, hardware) | **three runs on `ibm_fez`, 146 QPU-seconds** |

These are different metrics answering different questions. H1's failure says
nothing about the device-degradation result, and vice versa.

Two independent limits stalled the H1 line, and they must not be collapsed into
one cause: **penalty scaling** (Part 1, the dominant term) and **transpiled gate
count** (below, a separate limit that would have degraded T3/exact at 133 gates
whatever the weights were).

## Circuit cost

Fitting a depolarizing model to July's one usable row gives ~1.32% effective error
per 2-qubit gate; it predicts held-out TVD at 77 and 290 gates to within 3.5% and
1%. **That in-sample accuracy has not survived contact with later runs**: the model
has since been falsified three times, always by predicting more degradation than
occurred, most recently at 112 gates in
[`hardware-run-depth.md`](hardware-run-depth.md). It is used below to price
candidate circuits, which is what it is fit for; it should not be relied on for a
forward prediction. It does **not** predict single-bitstring optimal mass for collapsed circuits —
device noise has structure and does not take the state to exactly uniform — which
is why H1's gate is on *ideal* mass, which can be computed exactly.

| circuit | qubits | 2Q (o1) | 2Q (o3) | ε |
|---|---:|---:|---:|---:|
| T3/exact (July, 1 count) | 10 | 133 | 111 | 0.77 |
| **T3/cp3** | **6** | **54** | **50** | **0.49** |
| T4/cp3band | 9 | 149 | 125 | 0.81 |
| T6/cp3band | 13 | 348 | 269 | 0.97 |

Like-for-like at T=3, the encoding took ideal mass from 0.00013 to **0.0453
(349×)** at 54 gates instead of 133. T=6 and T=4 are ruled out: their reps=2
circuits (**~590** and **267** gates at level 3) are past the coherence limit, and
a candidate that can only run one depth cannot answer a question about depth.

> **Correction, 2026-08-25.** The T=6 figure read **269** until now, which is that
> circuit's **reps=1** count at level 3 — the value in the table directly above,
> not its reps=2 count. Re-transpiling against `FakeFez` puts the T=6 reps=2
> circuit at **581–600** two-qubit gates over five draws, against **263–284** for
> T=4, which is where the quoted 267 sits. The same re-measure returns the table's
> own rows at 276–301 (T=6) and 120–134 (T=4), so the table is reps=1 throughout
> and is unchanged; only this sentence mixed the two depths. The ruling-out stands
> and is strengthened, the real reps=2 circuit being about twice as far past the
> coherence limit as the wrong number suggested. This is `docs/LESSONS.md` §6
> ("make comparisons differ in exactly one thing") failing on the same number that
> file already records for the 348/269 pairing: mixed there on transpiler level,
> here on depth.

A structural result at T=3: with spacing 3 there are **no interior checkpoints**,
so the encoding reduces to objective + mutual exclusion + terminal. Soundness
still covers it (the single gap of 3 ≤ k bounds the excursion to 1 step), so no
interior SoC penalty is needed at T=3 at all.

### Transpiler optimization level: a free 8-18% gate reduction

Independent of any encoding question. The submission path transpiled at
`optimization_level=1`. Re-transpiling **the same
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

> **Correction, 2026-08-23.** This heading read **12-18%** until now, which is the
> range over the two T=3 circuits rather than over the four this section actually
> reports: the T=2 pair reduces by 11% and 8%. The measurements are unchanged and
> were always tabled above; only the summary range was wrong, understating how much
> the smallest circuits vary. The same range appeared in a comment in
> `scripts/experiment_hardware.py` and is corrected there too.

## Device degradation: three runs

`cp3` (6 qubits, 46 gates) against `exact` (10 qubits, 106 gates) — same instance,
same optimum, same depth, same weight, shot-noise floors equalized.

> **"Same weight" — is the encoding result conditional on it? Partly answered on
> the simulator, 2026-08-07 (corrected same day, see below).** Every hardware run
> compared the encodings at `α* = 0.021`, so the obvious 2×2 is missing its fourth
> cell: `cp3 @ default`. Before spending QPU, we measured how far the *weight*
> moves each encoding's optimal circuit:
>
> | encoding | TVD(ideal @default, ideal @α=0.021) | vs expected shot floor |
> |---|---:|---:|
> | `exact` | 0.6078 | 14.4× |
> | `cp3` | 0.1488 | **3.4×** |
>
> The denominator is the **expected** shot-noise floor — `E[TVD(ideal, sampled)]` =
> 0.0421 (exact @65,536) and 0.0433 (cp3 @4,096), computed by resampling. It is
> *not* the 0.0426/0.0497 "floor" column in the result table above: those are single
> realized Aer draws, and 0.0497 sits 1.3 sd above its own mean, so using it as a
> denominator imports one draw's noise (±11%).
>
> `cp3`'s circuit moves about **4× less** than `exact`'s with the weight, and the
> transpiled gate count does not move at all (46 and 106 at both weights; couplings
> 15 and 29). So an encoding-by-weight interaction would be driven mostly by the
> `exact` arm. This is an argument from ideal distributions, **not a hardware
> measurement**, and it does not license dropping the "at α=0.021" qualifier.
>
> **The hardware 2×2 was designed and not run, because the `cp3 @ default` cell is
> not well defined.** Its tuning is not reproducible: over 20 seeds the ideal
> distribution's TVD to `cp3 @ α=0.021` spans **0.015–0.755**, and the principled
> selection rule (lowest achieved `<H>`, what `QAOASolver` already applies) is
> itself unstable in the seed budget — it picks TVD 0.1466 at N=8 and 0.1488 at
> N=20, on an `<H>` difference of **0.14%**. Pinning a seed makes the cell
> reproducible without making it well defined: you would be measuring one
> arbitrarily-selected basin and generalizing to "cp3 at default weight". Resolving
> it needs an instance where `cp3`'s optimum moves with the weight, checked on the
> simulator first — that check costs two minutes.
>
> > **Correction, same day.** This note first reported `cp3` at TVD **0.1035** and
> > **2.1×** the floor, and argued the two `cp3` cells were near-identical so a null
> > interaction would be near-trivial. Both figures were wrong in the same
> > direction. 0.1035 came from an 8-seed search over one arbitrary seed set, and
> > the 2.1× divided it by a single realized draw (0.0497) rather than the expected
> > floor. Corrected, `cp3` moves 3.4× its floor — a real difference, not a
> > near-trivial one — so the "uninformative null" argument does **not** hold up.
> > The decision not to run stands, but on the second reason only: the cell is
> > ill-defined, not the contrast trivial. The seed-budget dependence this exposed
> > is what `docs/plans/basin-structure.md` was written to characterize.
> >
> > **Second correction, after that study ran
> > ([basin-structure.md](basin-structure.md)).** The "ill-defined cell" argument is
> > also too strong. The *landscape* at default weight is irreproducible — 19
> > distinct basins over 40 tunings — but the *selection rule* is stable: lowest
> > `<H>` converges to TVD 0.1488 and holds there from N=20 through N=40. Pinning
> > N ≥ 20 and the rule defines the cell. What remains against the 2×2 is only that
> > the weight moves `cp3`'s circuit ~4× less than `exact`'s — a weaker argument
> > than either originally given. Recorded rather than quietly dropped: both halves
> > of the original rationale were worse than the measurements that replaced them.

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

A separate decomposition, using a circuit bit-identical to the one July ran, found
the `k` asymmetry is **43% device drift, 57% penalty weight**.

Full detail per run: `hardware-run-encoding.md` (run 1),
`hardware-run-encoding-replication.md` (run 2 + the drift/weight decomposition),
`hardware-run-spread.md` (run 3 + the variance measurement).

---

# Our own predictions that were wrong

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
  best-0.01% band's *maximum* (0.07880 at α=0.021, 0.07947 at α=0.030) grazes just
  above the 0.078125 bar. The argmin does not clear it, and the typical
  near-minimum point does not.
- **"Drift is ruled out."** Invalid: `cp3` had no July baseline, so "it failed to
  move" was never observable. Drift was later measured directly at 43% of the
  shift.
- **"Run-to-run variation exceeds within-job device variance."** A bare point
  comparison (0.02437 vs 0.01743). On 2 df the between-run interval is
  [0.0127, 0.1532] and σ_device falls inside it — statistically indistinguishable.

A recurring pattern worth naming: **every one of these was a point estimate
compared without its interval, or a threshold stated without pinning the
quantities entering it.** Three pre-registrations in this program each left an
analysis choice unspecified that could have decided an outcome.

# Scope limits

- All concentration results are **ideal (noiseless) simulator**. The observed
  reps=2 > reps=1 ordering at correctly-scaled weights speaks to the **landscape**,
  not to H1's net-of-noise question. Any future hardware pre-registration must
  re-derive its reps prediction from gate counts and the noise model rather than
  inherit it from here.
- Concentration results are T=3 / `checkpoint(3)` / m=6 only.
- The annual dollar figures are one location, one tariff, one year (AMY 2018).
- Hardware results are one device (`ibm_fez`), one instance, one depth, n = 3
  runs. `exact`-arm device variance remains unbounded at n = 2.
