# Pre-registration: hardware run — does the slack-free encoding reduce *device* degradation?

**Date:** 2026-08-03 — written **before** any circuit is submitted. Nothing has
been run on hardware for this plan.

## This is not a retry of H1

**H1 is closed and is not revisited here.** H1 asked whether extra QAOA depth
helps or hurts once device noise is included — depth vs noise, judged on
optimal-state mass. It was closed without an answer because no circuit ever
cleared the pre-registered ideal-mass gate on the instance designated in advance:
at the a-priori penalty weight, reps=2 ideal mass saturated at ~0.075 against a
required 0.078125, and all twelve pre-registered optimizer arms failed to close
it. On that instance the refined `<H>` argmin carries mass 0.0657, below the bar.

Two qualifications that must travel with that statement (both established in
`docs/results/slack-free-encoding.md`, and neither of which reopens H1):

- The failure is **instance-dependent, not a property of the method**. The same
  arms pass reliably on both robustness instances, up to 10/10 at 0.106. Instance
  seed 1 is simply the hardest of the three tested.
- "No `<H>`-minimizing procedure can clear the bar" is **too strong** even on that
  instance: the best-0.01% `<H>` band's *maximum* is 0.0788, marginally above the
  bar. What holds is that the argmin does not clear it and the typical
  near-minimum point does not either.

**The question here is different in kind.** It is not about depth, not about
optimal mass, and not about solution quality. It asks whether the slack-free
encoding's advantage — established so far only in *simulated* gate counts —
actually survives contact with a device:

> **Does the slack-free encoding reduce hardware degradation, or only simulated
> gate count?**

That is answerable with metrics July already measured successfully, at a shot
budget July already showed to be adequate for them.

## Circuits

Same instance, same physical optimum, same depth. **The encoding is the only
variable.**

| circuit | encoding | qubits | 2Q (o1) | 2Q (o3) | depth (o3) | ideal feasible mass | TVD(sim, uniform) |
|---|---|---:|---:|---:|---:|---:|---:|
| `T3/exact` | `Encoding.EXACT` | 10 | 139 | **109** | 228 | 0.1895 | 0.4531 |
| `T3/cp3` | `Encoding.checkpoint(3)` | 6 | 57 | **50** | 137 | 0.2785 | 0.3817 |

- **Instance:** `synthetic_instance(T=3, seed=0, capacity=3.0, charge_energy=1.0,
  discharge_energy=1.0, initial_soc=1.0)` — deliberately the *same instance July
  ran*, so July's recorded `T3/exact` hardware result is a partial external
  baseline rather than something we must reproduce from scratch.
- **Depth:** `reps=1` for both. Adding depth would reintroduce exactly the
  confound H1 was about.
- **Penalty weight: α = 0.021 for both**, not just for `cp3`. α\* =
  (objective span 0.3095) / (default penalty 14.81) = **0.0209** is a property of
  the *problem*, not of the encoding, so the same threshold applies to both and
  0.021 clears it for both — verified exact on 100% of 200 instance seeds for each
  encoding. Using one weight for both is what makes the encoding the only variable.
- **Transpilation:** `optimization_level=3` (the current submission path).
- **Parameters:** re-optimized on the simulator with the existing settings
  (COBYLA, `n_starts=5`, `maxiter=200`, seed 1234), no optimization on hardware.

Note the gate counts differ slightly from the figures quoted when this run was
proposed (133 / 54): those were measured at the *default* penalty weight. At the
α = 0.021 weight actually being submitted they are 109 / 50 at o3. The ~2:1 ratio
— the thing under test — is unchanged.

## Metrics

**Primary: TVD(ideal-sim, hardware).** A full-distribution measure, robust to
single-bitstring shot noise, and the metric on which July's Prediction 1 held
monotonically (37/77/124/290 gates → 0.119/0.203/0.383/0.459).

**Secondary: feasible mass** — the probability the device puts on schedules
satisfying the physical constraints. Measurable at 4096 shots in July (0.209,
0.189, 0.084, 0.128) and directly meaningful: it is the fraction of samples a
user could act on.

**Optimal-state mass is explicitly NOT a metric here.** It was unmeasurable in
July at 4096 shots (1–97 counts, three of four circuits at the floor), and it is
the quantity whose gate H1 failed. Reporting it would invite reading this run as
an H1 retry. It may be recorded as a diagnostic; **no conclusion of this run may
rest on it.**

### Shots: equalized shot-noise floor, not equal shot count

TVD's shot-noise floor grows with Hilbert-space dimension (≈ `sqrt(2^m / 2πN)`),
so comparing a 6-qubit and a 10-qubit circuit at equal shots would hand the
smaller circuit an artificial advantage on the primary metric. Measured floors
(30 multinomial resamples of each tuned ideal distribution):

| circuit | N=4,096 | N=16,384 | N=65,536 |
|---|---:|---:|---:|
| `T3/exact` (m=10) | 0.1672 | 0.0844 | **0.0421** |
| `T3/cp3` (m=6) | **0.0430** | 0.0214 | 0.0110 |

So: **`cp3` at 4,096 shots and `exact` at 65,536 shots**, which equalizes the
floor at ≈0.042 for both. Any measured difference is then device degradation, not
dimension. Both floors are reported alongside the results.

## Validation of the normalized metric on July's data

Requested before approval, and it changed the predicted values. Computing
`TVD(sim,hw) / TVD(sim,uniform)` for all four July circuits:

| circuit | 2Q | TVD(sim,hw) | TVD(sim,uniform) | **normalized** | TVD(hw,uniform) | max bitstring / uniform |
|---|---:|---:|---:|---:|---:|---:|
| T2/reps1 | 37 | 0.1189 | 0.4075 | **0.2918** | 0.3848 | 4.25x |
| T2/reps2 | 77 | 0.2031 | 0.5588 | **0.3635** | 0.4167 | 5.05x |
| T3/reps1 | 124 | 0.3828 | 0.6448 | **0.5937** | 0.4038 | 8.25x |
| T3/reps2 | 290 | 0.4590 | 0.4988 | **0.9202** | 0.2883 | 5.00x |

**The normalized ratio is monotonic in gate count** (0.292 → 0.364 → 0.594 →
0.920), so it is validated as the adjudicating metric. Three caveats travel with
that, and none of them is dispensable:

1. **This validates the ratio as an *ordering statistic*, not as a physical
   fraction.** The device asymptote is biased, not flat: `TVD(hw,uniform)` never
   approaches 0 (it bottoms out at 0.288) and individual bitstrings reach 8.25x
   uniform. So the ratio must not be read as "fraction of the way to uniform" —
   at 290 gates it is 0.92 while the hardware distribution is still 0.288 away
   from uniform, i.e. displaced off the sim-uniform line toward a biased limit.
2. **n = 4, and raw TVD is monotonic on the same data.** July therefore shows the
   normalized ratio is *not worse* than raw; it cannot show it is better. The
   reason to prefer it here is specific to this run's design — the two circuits
   differ in peakedness (0.3817 vs 0.4531) by construction, and the ratio divides
   that out. Raw TVD is reported alongside, and if the two disagree, that
   disagreement is the result and gets reported as such.
3. **`TVD(sim,uniform)` is not monotonic in gate count** across July's circuits
   (0.408, 0.559, 0.645, 0.499). Raw TVD stayed monotonic anyway, which is mild
   evidence that peakedness variation of that size does not by itself reorder raw
   TVD.

## Pre-registered directional prediction

> **`T3/cp3` normalized TVD ≈ 0.32, `T3/exact` ≈ 0.57 — cp3 lower, with
> non-overlapping uncertainty bands.**

**These numbers are a correction.** The first draft predicted 0.486 vs 0.765,
from the depolarizing model fitted to July's *optimal mass* (1.32%/gate). Checked
against the normalized TVD it is now being asked to predict, that model
**overpredicts systematically — by +33%, +76%, +36%, and +6%** across the four
circuits. It was fitted to a different observable and must not be used here.

### Estimator and uncertainty: out-of-sample, not in-sample

Backing an implied decay rate `k = −ln(1 − normalized) / gates` out of each July
circuit separately:

| circuit | 2Q | normalized | implied `k` |
|---|---:|---:|---:|
| T2/reps1 | 37 | 0.2918 | 0.00933 |
| T2/reps2 | 77 | 0.3635 | 0.00587 |
| T3/reps1 | 124 | 0.5937 | 0.00726 |
| T3/reps2 | 290 | 0.9202 | 0.00872 |

Mean **0.00779**, range 0.00587–0.00933 — a half-range of **±22%** of the mean,
with **no trend in gate count** (pearson r = +0.21, p = 0.79), so the scatter is
circuit-to-circuit variation rather than a missing gate-count term.

Propagating that observed spread through `1 − exp(−k·g)`:

| circuit | 2Q (o3) | low `k` | **central** | high `k` | raw TVD range |
|---|---:|---:|---:|---:|---|
| `T3/cp3` | 50 | 0.254 | **0.323** | 0.373 | 0.097 – 0.142 |
| `T3/exact` | 109 | 0.472 | **0.572** | 0.638 | 0.214 – 0.289 |

The bands do not overlap, with a **0.100 gap** between cp3's upper bound and
exact's lower bound.

This replaces the earlier ±0.05 RMS-residual band deliberately. An RMS residual
is an **in-sample** goodness-of-fit statistic for a one-parameter curve fit on
four points; it describes how well the curve was drawn, not how far a *new*
circuit may fall from it. The per-circuit `k` spread is an **out-of-sample**
estimate of exactly that — how much circuits of this family actually vary around
the shared law — and is the more defensible basis for a falsification threshold.
As a consistency check, the least-squares fit's values (0.306, 0.548) fall inside
both bands.

**Secondary prediction:** feasible mass degrades less for `cp3`. Ideal values are
0.2785 (`cp3`) and 0.1895 (`exact`); the prediction is that `cp3` retains a larger
*fraction* of its ideal value.

## What would falsify the encoding claim

**Two claims are on trial here, and they are not equally strong. Do not conflate
them.**

### Primary — an ORDERING test (the encoding claim)

> **`T3/cp3`'s normalized TVD is lower than `T3/exact`'s.**

This is the encoding claim, and it is a **pure ordering test: magnitude is
irrelevant to it.** If cp3's normalized TVD is not lower than exact's, the
encoding claim **fails regardless of how large or small the numbers are**. If it
is lower, the encoding claim **holds**, even if the separation is a fraction of
what was predicted.

It is also falsified if the raw gap is entirely explained by shot noise — both
circuits' TVD(sim,hw) lying within their ≈0.042 floors of each other — since
that is a measurement failure rather than a result in either direction.

### Secondary — a MAGNITUDE test (the noise model)

> **cp3 lands in [0.254, 0.373] and exact in [0.472, 0.638].**

This tests the *quantitative noise model*, which is a **separate and weaker
claim** than the encoding result. It rests on four circuits, one free parameter,
and an uncertainty taken from their scatter.

**A magnitude miss must be reported as a failure of the noise model, not of the
encoding result.** Concretely: if cp3 comes in below exact but either value falls
outside its band, the correct report is "the encoding claim holds; the noise model
does not predict the magnitude" — not a hedged or negative headline. That would be
the noise model's second falsification, the mass-fitted version having already
failed against July's normalized TVD above.

The converse also holds: values landing inside the bands while the *ordering*
fails would refute the encoding claim outright, and no agreement of magnitudes
could rescue it.

## Error-mitigation arm — EXPLORATORY, not gating

Dynamical decoupling plus readout (measure) twirling, via `SamplerV2` options, on
both circuits: a 2×2 design (encoding × mitigation).

**This arm is exploratory and does not gate any conclusion.** The primary
encoding comparison is decided on the **unmitigated** pair, which is what keeps it
comparable to July's unmitigated data. Mitigation is a second factor; letting it
into the primary comparison would confound the one variable this run exists to
isolate. Its purpose is to record whether mitigation changes the *ordering* — if
it did, that would itself be a finding worth a separate plan.

Both techniques are close to free in shots: DD fills idle time and adds no
samples, and measure twirling redistributes existing shots across randomizations.

## Budget

Using the repo's deliberately coarse estimator (`2.0 + shots × depth × 2e-6` per
circuit — an order-of-magnitude figure, not a quote):

| arm | circuits | est. QPU seconds |
|---|---|---:|
| primary (unmitigated) | `cp3` @ 4,096 + `exact` @ 65,536 | ~35 |
| mitigation (exploratory) | same two, DD + twirling | ~35 |
| **total** | 4 executions | **~70** |

For reference July spent 7.0 actual QPU-seconds on four circuits at 4,096 shots.
The increase is almost entirely the 16× shots on the 10-qubit circuit, bought
deliberately to equalize the TVD floor. Actual seconds are recorded post-run from
job metadata. If the mitigation arm does not fit the allocation, **it is dropped
first** — it is exploratory by construction.

## Fixed interpretation rules

- The primary comparison is the **normalized** TVD on the **unmitigated** pair,
  and it is an **ordering** test. Magnitude does not enter it.
- The magnitude bands test the noise model only. **A magnitude miss is reported
  as a noise-model failure, never as a failure of the encoding result**, and the
  headline follows the ordering.
- No conclusion rests on optimal-state mass, at any point, for any arm.
- The prediction above is directional and was fixed before submission; a null or
  reversed result is reported as such and not reframed.
- This run says nothing about H1, about solution quality, or about whether QAOA
  is useful for this problem. It tests one thing: whether fewer qubits and gates
  from a slack-free encoding show up as less degradation on real hardware.

## Scope limits

- One instance, one size (T=3), one depth (`reps=1`), one backend family (Heron).
- The device is not fixed here; backend selection follows
  `scripts/experiment_hardware.py` (least-busy operational Heron with enough
  qubits). Calibration drift between July's run and this one is uncontrolled, so
  July's numbers are context, not a control.
- The ~1.32%/gate model is fitted from a **single** usable July row; it predicts
  full-distribution TVD well but is known **not** to predict single-bitstring
  optimal mass, which is a further reason optimal mass is excluded here.
