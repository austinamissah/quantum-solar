# Hardware run: does the slack-free encoding reduce device degradation?

**Run date:** 2026-08-03 · **Backend:** `ibm_fez` (pinned) · **42.0 QPU-seconds**
(estimated ~57.4) · Jobs `d9of01va5u8s73e2ljhg` (unmitigated),
`d9of08bvt76s73cq0rr0` (mitigated)

Pre-registered in `docs/plans/hardware-run-encoding.md`, amended to real-backend
gate counts before submission. Nothing below was chosen after seeing data.

## Result

| circuit | m | 2Q | shots | floor | TVD(sim,hw) | TVD(sim,unif) | **normalized** |
|---|---:|---:|---:|---:|---:|---:|---:|
| `T3/exact` | 10 | 106 | 65,536 | 0.0426 | 0.1682 | 0.4535 | **0.3708** |
| `T3/cp3` | 6 | 46 | 4,096 | 0.0497 | 0.1160 | 0.3811 | **0.3043** |
| `T3/exact` +mitigation | 10 | 106 | 65,536 | 0.0426 | 0.1721 | 0.4535 | 0.3796 |
| `T3/cp3` +mitigation | 6 | 46 | 4,096 | 0.0497 | 0.1221 | 0.3811 | 0.3203 |

The floor-equalisation worked as designed: 0.0426 and 0.0497 against the planned
≈0.042 / ≈0.043, so the two circuits are compared on even footing.

### Primary — ordering test: **the encoding claim HOLDS**

`cp3` normalized TVD **0.3043** < `exact` **0.3708**. The slack-free encoding's
advantage is not confined to a transpiler report; it shows up as measurably less
degradation on a real device, at matched shot-noise floors, same instance, same
optimum, same depth.

The raw-gap check passes, **but narrowly**: the raw TVD gap is 0.0522 against a
larger floor of 0.0497. It clears by 0.0025. Had it not, the pre-registration
would have called this a measurement failure rather than a result, and that
margin is thin enough to state plainly rather than round away.

### Secondary — magnitude test: **the noise model FAILS**

| circuit | measured | pre-registered band | |
|---|---:|---|---|
| `cp3` | 0.3043 | [0.237, 0.349] | INSIDE |
| `exact` | 0.3708 | [0.463, 0.628] | **OUTSIDE (below)** |

`exact` degraded substantially *less* than predicted. Per the pre-registered
interpretation rule this is reported as a **failure of the noise model, not of
the encoding result** — the second time that model has been falsified, the
mass-fitted version having already failed against July's normalized TVD.

Two things are visible in why it failed, and they point in different directions:

1. **Calibration drift, as the plan anticipated.** `ibm_fez`'s median 2-qubit
   gate error at submission was **0.27%** (snapshot recorded in the counts file).
   The bands were calibrated on July's fez circuits, and the device has evidently
   improved since. This is exactly the residual risk the pin was documented as
   *not* removing — and it is why the calibration snapshot now exists. July's
   calibration was never recorded, so the comparison can only be made forward.
2. **The single-rate model itself is suspect.** Backing an implied `k` out of
   each circuit here gives **0.00789** (`cp3`) and **0.00437** (`exact`) — a 1.8x
   spread *within one run on one device on one day*, against the ±22% spread July
   showed across four circuits. `cp3`'s value sits almost exactly on July's mean
   (0.00779); `exact`'s is far below July's minimum (0.00587). If this were pure
   drift both would have moved together. A single decay rate shared across
   circuits of different qubit counts is doing worse than its own uncertainty
   band admits.

### Secondary metric — feasible mass

| circuit | hardware | ideal | retained |
|---|---:|---:|---:|
| `T3/exact` | 0.1665 | 0.1895 | 87.9% |
| `T3/cp3` | 0.2358 | 0.2785 | 84.7% |

**The secondary prediction is not confirmed.** It predicted `cp3` would retain a
larger *fraction* of its ideal feasible mass; it retained slightly less (84.7% vs
87.9%). In absolute terms `cp3` still delivers far more usable output — 23.6% of
samples versus 16.7% — but the predicted direction on the retention *fraction* is
wrong, and is reported as such.

### Exploratory — error mitigation (gates nothing)

| circuit | unmitigated | mitigated | |
|---|---:|---:|---|
| `T3/cp3` | 0.3043 | 0.3203 | worse |
| `T3/exact` | 0.3708 | 0.3796 | worse |

Dynamical decoupling plus readout twirling made **both** circuits slightly worse.
The ordering is preserved under mitigation, so the primary conclusion is
unaffected either way. This arm was declared exploratory and non-gating in
advance; nothing here changes any conclusion, and the effect is small enough to
be within run-to-run variation that this design cannot resolve.

## An analysis defect worth recording

The first pass at this analysis compared a 65,536-shot hardware distribution
against a **4,096-shot** simulated reference, because `ideal_sim_counts` defaults
to the module-level `SHOTS`. That silently defeated the entire
floor-equalisation design *in the analysis* — it put `exact`'s floor at 0.164
instead of 0.043 and inflated its TVD by 35%, which would have made the raw-gap
check appear to fail. The run itself was correct; only the reference was
mis-sampled.

`ideal_sim_for_record` now exists so a plan with unequal shots samples its
reference at the matching count, and the failure mode is documented at the call
site rather than left as a trap.

## Scope

One instance, one size (T=3), one depth (reps=1), one device, one day. The
encoding result is a single ordering comparison at matched floors — it does not
establish how the advantage scales, and the noise-model failure above shows the
quantitative extrapolation is not yet trustworthy.
