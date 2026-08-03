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

#### Bootstrap confidence intervals

"Clears by 0.0025 against a 0.0497 floor" is a margin, not an inference. A
nonparametric bootstrap (B = 10,000) resampling **both** finite samples on both
arms — the ideal-sim reference carries its own shot noise, so resampling only the
hardware side would understate the variance:

| quantity | point | 95% CI | excludes 0? |
|---|---:|---|---|
| raw TVD gap (exact − cp3) | 0.0522 | **[0.0293, 0.0662]** | **yes** |
| normalized gap (exact − cp3) | 0.0665 | **[0.0038, 0.0977]** | **yes, marginally** |

Both exclude zero, so the ordering is a real effect rather than a coincidence of
sampling. **But the normalized interval — the adjudicating metric — has a lower
bound of 0.0038.** It clears zero by a hair. The raw ordering is solid; the
normalized ordering is real but thin, and the honest reading is that this run
establishes the direction, not a well-resolved effect size.

Two methodological notes, both checked rather than assumed:

- **The individual bootstrap CIs are biased upward and must not be read as CIs on
  the true TVD** — resampling two samples adds noise the originals did not carry,
  so e.g. `exact`'s raw CI [0.1745, 0.1839] sits entirely above its 0.1682 point
  estimate. The inflation is larger for `cp3` (≈0.014) than for `exact` (≈0.011),
  so it works *against* the gap: the interval above is conservative.
- **The residual floor mismatch also cuts the conservative way.** `cp3`'s floor
  (0.0497) exceeds `exact`'s (0.0426), so `cp3`'s TVD carries the larger
  finite-sample bias; correcting it would push `cp3` down and widen the gap.
- The normalization denominator is not the noise source. Re-running with the
  exactly-known `TVD(statevector, uniform)` instead of the sampled one gives
  [0.0031, 0.0991] — essentially unchanged, so the width is genuine numerator
  variability.

### Secondary — magnitude test: **the noise model FAILS**

| circuit | measured | pre-registered band | |
|---|---:|---|---|
| `cp3` | 0.3043 | [0.237, 0.349] | INSIDE |
| `exact` | 0.3708 | [0.463, 0.628] | **OUTSIDE (below)** |

`exact` degraded substantially *less* than predicted. Per the pre-registered
interpretation rule this is reported as a **failure of the noise model, not of
the encoding result** — the second time that model has been falsified, the
mass-fitted version having already failed against July's normalized TVD.

#### The failure is asymmetric, and that rules out two explanations

Backing an implied `k = −ln(1−normalized)/gates` out of each circuit:

| circuit | implied `k` | vs July's [0.00587, 0.00933] |
|---|---:|---|
| `cp3` | 0.00789 | **inside** (July's mean is 0.00779) |
| `exact` | 0.00437 | **below all four** July circuits |

Only one arm moved. That kills the two obvious explanations:

- **Not device drift.** Drift would have shifted both arms together. `cp3` lands
  almost exactly on July's mean.
- **Not a qubit-count dependence.** An earlier draft of this document claimed the
  single-rate model was failing across qubit counts. **That claim was wrong and is
  retracted**: July's own data shows no such dependence — m=6 mean 0.00760 against
  m=10 mean 0.00799, a 5% difference against a 22% circuit-to-circuit spread. The
  baseline does not support qubit count as the cause.

#### Hypothesis: the penalty weight, via ideal-distribution flatness

The one thing that differs asymmetrically is the **weight**. These angles are
tuned at α = 0.021; July's were tuned at the default. `cp3` has no July baseline
at default weight, so only `exact` can show the effect — which is exactly the arm
that moved. Simulated ideal-distribution properties for `T3/exact` reps=1:

| property | α = 0.021 | default |
|---|---:|---:|
| entropy (nats, max 6.93) | 6.3797 | 5.7086 |
| participation ratio (of 1024) | **469.3** | **190.7** |
| TVD to uniform | 0.4531 | 0.6401 |
| max bitstring / uniform | **5.30x** | **16.84x** |

The correctly-scaled Hamiltonian yields a far flatter ideal distribution —
spread over 2.5x as many states, with a peak a third as tall. A distribution
already close to the device's degraded limit has less structure to lose, so it
degrades less in TVD terms than a model calibrated on peaked, default-weight
circuits predicts. Normalizing by `TVD(sim, uniform)` corrects for this only if
the degradation path runs toward uniform, and July's data already showed the
device asymptote is biased rather than flat.

**This is a hypothesis, not a result.** The simulation establishes that the
distributions differ substantially; it does not establish that the difference
*caused* the k asymmetry, and n = 1 on the arm in question. The decisive test is
a hardware comparison of `exact` at α = 0.021 versus default weight — same
circuit, same device, weight as the only variable — which would show whether the
implied `k` returns to July's range at the default weight. That costs QPU and is
not run here.

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
