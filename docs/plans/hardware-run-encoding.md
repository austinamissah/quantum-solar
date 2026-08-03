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

## Pre-registered directional prediction

> **TVD(sim, hw) will be lower for `T3/cp3` than for `T3/exact`, by roughly a
> factor of two: ≈0.19 versus ≈0.35.**

Reasoning: the fitted depolarizing model from July's one usable row gives ~1.32%
effective error per 2-qubit gate, which predicts held-out TVD at 77 and 290 gates
to within 3.5% and 1%. It gives ε(50) = 0.486 and ε(109) = 0.765. Under a
mixture model TVD(sim,hw) ≈ ε · TVD(sim, uniform), and the tuned circuits have
TVD(sim,uniform) = 0.3817 and 0.4531. Hence 0.486 × 0.3817 = **0.185** and
0.765 × 0.4531 = **0.347**.

**Secondary prediction:** feasible mass degrades less for `cp3`. Ideal values are
0.2785 (`cp3`) and 0.1895 (`exact`); the prediction is that `cp3` retains a larger
*fraction* of its ideal value.

**Stated confound.** The two circuits do not have equal TVD(sim,uniform) (0.3817
vs 0.4531), so part of any raw gap is the ideal distributions' differing
peakedness rather than device degradation. Both scales are computed by simulation
before submission (above) and are reported, so the normalized quantity
`TVD(sim,hw) / TVD(sim,uniform)` — predicted 0.486 vs 0.765 — is available as the
confound-corrected comparison. **The normalized comparison is the one that
adjudicates the claim**; the raw one is reported for continuity with July.

## What would falsify the encoding claim

The claim under test is that the slack-free encoding buys *real device* margin,
not just a smaller number in a transpiler report. It is **falsified** if:

- **`cp3`'s normalized TVD is not lower than `exact`'s** — i.e.
  `TVD(sim,hw)/TVD(sim,uniform)` for `cp3` ≥ that for `exact`. A 2.2× predicted
  separation (0.486 vs 0.765) against a ≈0.042 shot floor is far outside noise,
  so this is a real test rather than a formality.
- **Or the raw gap is entirely explained by the floor**, i.e. both circuits'
  TVD(sim,hw) lie within their floors of each other.

A confirmed but much smaller separation than predicted (say <20% rather than
~2×) does **not** falsify the encoding claim, but does falsify the *quantitative*
noise model, and must be reported as such rather than folded into a pass.

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

- The primary comparison is the **normalized** TVD on the **unmitigated** pair.
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
