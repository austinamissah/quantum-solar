# Pre-registration: QAOA optimizer study (reps=2 concentration)

**Date:** 2026-08-02 — written **before** any arm is measured.

Same discipline as `hardware-run.md`: every choice below is fixed now, so none of
it can be made after seeing results. In particular the success threshold is
inherited unchanged from the hardware-run gate and is **not** revisited here.

## Why this study exists

The slack-free encoding study established, in order:

1. **Penalty scaling was the binding constraint on ideal concentration.** At
   `default_weights` (α=1) the penalty scale is 14.81 against an objective span
   of 0.3095 across the feasible set — a 48× overshoot that makes cost nearly
   invisible in `<H>`. Rescaling moved reps=2 ideal mass by 440× (0.00019 →
   0.0832) with the encoding and optimizer untouched.
   *(Qualified 2026-08-04: a lower bound — the runs sat on a 1000-evaluation cap,
   and the endpoint is sensitive to α in its third decimal, 465× at 0.0209 vs
   382× at 0.021. Read as "several-hundred-fold". See
   [eval-censoring.md](../results/eval-censoring.md).)*
2. **Transpiled gate count was a second, independent limit.** T3/exact at 133
   two-qubit gates (ε≈0.77 under the fitted per-gate model) would have degraded
   on hardware *regardless* of penalty weights. The encoding fixed this axis —
   133 → 54 gates, 10 → 6 qubits — and it is not the same cause as (1). These
   two must not be collapsed into a single explanation.

After fixing the weight by an a-priori rule (below), reps=2 ideal mass at the
designated size reached mean 0.0716 (sd 0.0116, 2/6 tuning seeds clearing)
against a required 0.0781. The residual gap is ~8% and the failure mode is
**variance, not absence of good parameters**: the observed maximum (0.0879)
clears the bar, so parameters that pass demonstrably exist in the reps=2
landscape and COBYLA×5-starts reaches that basin about a third of the time.

This study asks one question: **can a better parameter-optimization procedure
reach that basin reliably?**

## Fixed configuration

- **Problem:** `synthetic_instance(T=3, capacity=3.0, charge_energy=1.0,
  discharge_energy=1.0, initial_soc=1.0)`, encoding `Encoding.checkpoint(3)`,
  m = 6 qubits.
- **Penalty weight:** α ∈ {0.021, 0.030}, both reported. α is **not** a free
  knob: α\* = (objective span)/(default penalty) = 0.0209 is the a-priori
  exactness threshold, verified at 100% optimal over 200 instance seeds at and
  above it and collapsing below (61% at 0.010, 6% at 0.005, 1.5% at 0.003).
  Values below α\* are excluded regardless of the mass they produce.
- **Depth:** reps = 2 (the failing case). reps = 1 reported for reference only.
- **Primary instance seed: 1** — held out; the sweep and repeats used seed 0.
- **Robustness instance seeds: 2, 3** — reported, **not** gating.
- **Tuning seeds: 101–110 (N = 10)** — fresh; earlier runs used 1234 and 1–5.
  N = 10 is chosen against the measured reps=2 sd ≈ 15% of mean, giving a
  standard error on the mean of ≈ 5%, comfortably below the 8% gap being tested.

## Success criterion (fixed)

Uniform at m=6 is 1/64 = 0.015625; the bar is **5 × uniform = 0.078125**,
inherited from `hardware-run.md` and unchanged.

An arm **PASSES** if its **mean ideal optimal mass over the 10 tuning seeds is
≥ 0.078125 on the primary instance (seed 1)**, at either α. Pass/fail is on the
mean alone.

Independently, and reported alongside, an arm is labelled **RELIABLE** if it
clears the bar on ≥ 8 of 10 tuning seeds. An arm that passes on the mean but is
not reliable is a materially weaker result than one that is both, because
variance is precisely what failed at the baseline — so all three of **mean, sd,
and fraction-clearing** are reported for every arm, and no arm is summarized by
its mean alone.

## Arms

| arm | procedure | objective |
|---|---|---|
| `cobyla-5` | COBYLA, 5 random starts, maxiter 200 (**baseline / control**) | shot-based estimator |
| `cobyla-25` | COBYLA, 25 random starts, maxiter 200 | shot-based estimator |
| `cobyla-50` | COBYLA, 50 random starts, maxiter 200 | shot-based estimator |
| `spsa` | SPSA, 300 iterations (600 evaluations), standard gain schedule | shot-based estimator |
| `lbfgs-sv` | L-BFGS-B, 5 random starts, maxiter 200 | **exact statevector `<H>`** |
| `transfer` | single COBYLA run initialized at the reps=1 optimum, duplicated across both layers | shot-based estimator |

`cobyla-25` / `cobyla-50` isolate whether this is purely a basin-hitting-rate
problem. `lbfgs-sv` uses a noiseless objective and is therefore **not** a
like-for-like optimizer comparison — it is an upper bound on what any parameter
search can achieve when the objective itself is exact, and is reported as such.
`transfer` exploits the finding that reps=1 converges to the same point from
every start (sd ≈ 1e-5), making the warm start free and deterministic; the reps=1
parameters are duplicated across both reps=2 layers, mapped through
`QAOAAnsatz`'s parameter ordering read programmatically from parameter names.
That duplication scheme is fixed now and will not be re-chosen after seeing
results.

Evaluation budgets differ across arms by construction (that is the point of the
`cobyla-25`/`cobyla-50` arms); budget is reported per arm so cost is visible and
no arm is credited with a win that is purely bought.

## Interpretation rules (fixed)

- **If one or more arms pass:** the residual gap was optimizer reliability. The
  passing arm with the smallest evaluation budget becomes the candidate
  configuration, and the next step is held-out *instance* validation — not a
  hardware run, which requires its own pre-registration.
- **If no arm passes but robustness instances (seeds 2, 3) show arms clearing:**
  the result is **instance-dependent**, not "optimizers do not help", and must be
  reported that way.
- **If no arm passes anywhere:** QAOA's concentration on this problem is the
  limiting factor at reps=2, and the honest finding is that the encoding and the
  weight rule both work while the variational method does not reach the required
  concentration. No hardware run.
- The bar is **not** lowered, and no tuning seed, α below α\*, or arm variant is
  introduced after seeing results in order to clear it.

## Scope limits (fixed)

- Everything here is measured on an **ideal (noiseless) simulator**. The
  reps=2 > reps=1 ordering observed at correctly-scaled weights speaks to the
  **landscape**, not to H1, which asks a net-of-noise question. If a hardware run
  is ever pre-registered, its reps prediction must be re-derived there from
  gate counts and the device-noise model — **not** inherited from this document.
- Results are for T=3 / `checkpoint(3)` / m=6 only. Nothing here generalizes to
  other sizes without measurement.
