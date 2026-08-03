# Pre-registration: replication + weight/drift decomposition

**Date:** 2026-08-03 — written **before** submission. Nothing has been run for
this plan. Gate counts, depths and floors below are from a real `ibm_fez` dry run,
so no post-hoc amendment should be needed.

Follows `docs/plans/hardware-run-encoding.md` and its result in
`docs/results/hardware-run-encoding.md`.

## Two purposes

**Primary — replication.** The encoding result is **n = 1**. One run showed
`cp3`'s normalized TVD below `exact`'s, and the whole headline rests on it.

**Secondary — decompose the k asymmetry.** That run left `cp3`'s implied
`k = 0.00789` inside July's range while `exact`'s `0.00437` sat below all four
July circuits. Only one arm moved, which ruled out drift (it would move both) and
qubit count (July shows none: m=6 mean 0.00760 vs m=10 mean 0.00799). The
surviving hypothesis was the penalty weight. This run tests it directly.

### The replication baseline is the CORRECTED interval

The prior run's normalized gap CI is **[0.0291, 0.1013]** (median 0.0658), from a
bootstrap resampling **only** the hardware counts against an exactly-known
statevector reference.

An earlier, superseded figure of **[0.0038, 0.0977]** is **not** the baseline.
That came from resampling the ideal-sim reference as well, injecting noise the
estimand does not contain; it was retracted in the results document. Using it
here would set a replication bar roughly 8x looser than the actual result. On the
pre-registered *sampled*-reference form the corrected interval is
**[0.0220, 0.0942]**, and that is the one comparable to the July-calibrated bands.

## Circuits — one job, three circuits

One job so all three share a single calibration snapshot; per-PUB shots carry the
floor equalization.

| circuit | encoding | α | m | 2Q | depth | shots | floor | TVD-uniform | PR/D | peak/unif |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `cp3 @ α=0.021` | checkpoint(3) | 0.021 | 6 | 46 | 120 | 4,096 | 0.0430 | 0.3817 | 0.572 | 2.87x |
| `exact @ α=0.021` | EXACT | 0.021 | 10 | 106 | 182 | 65,536 | 0.0419 | 0.4531 | 0.458 | 5.30x |
| `exact @ default` | EXACT | 1.0 | 10 | 106 | 183 | 65,536 | 0.0349 | 0.6401 | 0.186 | 16.84x |

Rows 1–2 replicate the primary comparison. Rows 2–3 isolate the weight.

**Two properties this design has that the last one did not:**

1. **The weight contrast is at matched circuit size.** Both `exact` arms
   transpile to **106 two-qubit gates** — scaling penalties changes rotation
   angles, not gate structure. Any `k` difference between them cannot be a
   circuit-size effect.
2. **`exact @ default` is bit-identical to the circuit July ran.** Re-tuning
   reproduced July's angles exactly (`[2.394457, 2.340887]`), same instance, same
   seed, same device. So it is simultaneously the weight contrast *and* a direct
   **drift probe** against July's measured `k = 0.00726`.

Together these decompose the asymmetry cleanly:

- `exact@default` **now vs July** → drift (same circuit, 3½ weeks apart)
- `exact@default` **vs** `exact@α=0.021` **now** → weight (same day, same size)

Backend pinned to `ibm_fez`; `optimization_level=3`; `seed_transpiler` pinned;
params and counts files both guarded against overwrite. Estimated **~54.8 QPU
seconds**.

## Pre-committed outcome rules — replication

Adjudicated on the **normalized** gap, `exact@α=0.021` − `cp3@α=0.021`, with a
hardware-only bootstrap against an exact statevector reference (B = 10,000),
identical to the corrected analysis of the first run.

**Every case below is written now. None may be renegotiated after seeing data.**

### A. Gap reproduces within the prior CI — `[0.0291, 0.1013]`

The encoding result is **replicated**. Headline stands as written. Report the
pooled estimate across both runs and note that n = 2 on one device and one
instance still does not establish generality.

### B. Gap positive, CI excludes zero, but below the prior interval

The encoding result **holds; the effect size does not replicate**. The writeup
says the direction is confirmed twice and the magnitude is unstable, reports both
intervals side by side, and drops any quantitative effect-size claim. This is the
outcome that most likely reflects the truth if run-to-run variation is larger
than either run's internal CI suggests.

### C. Gap indistinguishable from zero — CI includes zero

The encoding result is **not replicated**. The correct writeup is: *one run showed
a positive gap with an interval excluding zero; a second, identically-designed run
did not. On the evidence, a device-level advantage from the slack-free encoding is
not established.* The first run is **not** reinterpreted as a fluke *or* defended
as the real one — both are reported, and the headline in
`docs/results/slack-free-encoding.md` is downgraded from "shows up as measurably
less degradation on real hardware" to "not established on hardware; the simulated
gate-count and annual-dollar results are unaffected."

### D. Gap reverses — `cp3` degrades MORE than `exact`

Written now, before it can be argued away:

> **The encoding claim fails.** Two identically-designed runs on the same device
> and instance produced opposite orderings. That is not a small effect measured
> imprecisely; it is an effect whose sign is not stable under replication, and the
> first run's interval excluding zero was therefore misleading — most likely
> because run-to-run device variation exceeds within-run sampling variation, which
> neither run's bootstrap can see.
>
> The writeup states plainly that the hardware claim is **withdrawn**. It does
> not average the two runs into a smaller positive effect, does not appeal to
> calibration differences to discount the reversing run, and does not seek a third
> run to break the tie — a best-of-three chosen after seeing two disagreeing
> results is not a test. Any further hardware work on this question requires a new
> pre-registration with a design that can measure run-to-run variance directly
> (repeated jobs within one calibration window), because that is the term this
> design omits.

The classical results — 52 qubits for $0.00/yr, 349x ideal mass, the α\* rule —
**do not depend on any of this** and are unaffected in every case above.

## Pre-committed prediction — the weight arm

> **`exact @ default` will show a HIGHER implied `k` than `exact @ α=0.021`, and
> will land near July's 0.00726 — normalized ≈ 0.54, versus 0.37 measured for
> `exact @ α=0.021`.**

Reasoning: the hypothesis is that a flatter ideal distribution has less structure
to lose, so it degrades less than a model calibrated on peaked circuits predicts.
The default-weight distribution is far peakier on every shape statistic —
**PR/D 0.186 vs 0.458**, **peak 16.84x vs 5.30x uniform**, TVD-to-uniform 0.6401
vs 0.4531 — so it should degrade *more*, at identical gate count. July measured
exactly this circuit at `k = 0.00726`, which at 106 gates predicts normalized
**0.537**.

### Decision table

| outcome for `exact@default` | reading |
|---|---|
| `k` ≈ 0.0073, near July | **Weight confirmed.** No drift, and the gap to `exact@α=0.021`'s 0.00437 is the weight effect. |
| `k` ≈ 0.0044, matching `exact@α=0.021` | **Weight FALSIFIED.** Weight makes no difference at matched gate count. Since this is July's exact circuit, the drop from 0.00726 is then drift — which leaves `cp3` sitting on July's mean unexplained and needing its own investigation. |
| `k` between ≈0.0044 and ≈0.0073 | Partial: both drift and weight contribute. Report the split, claim neither alone. |
| `k` > 0.00933, above July's range | Neither hypothesis. Something outside this model; report as unexplained. |

**What falsifies the weight hypothesis** (as opposed to merely failing to support
it): row 2 — `exact@default`'s `k` statistically indistinguishable from
`exact@α=0.021`'s, with overlapping bootstrap intervals. Weight would then be
excluded as the cause at matched gate count, not left open.

## Scope limits

- **Same device, same instance, same tuning seed, same day.** This measures
  run-to-run and drift. It does **not** test instance generality or device
  generality, and a successful replication must not be reported as though it did.
- The design still cannot separate run-to-run variance from within-run sampling
  variance; that needs repeated jobs in one calibration window, which is not run
  here and is named as the fix if outcome D occurs.
- Optimal-state mass remains excluded from every conclusion.
