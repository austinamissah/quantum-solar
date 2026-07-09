# Pre-registration: IBM Quantum hardware run

**Date:** 2026-07-09 — written **before** any hardware results exist.

This fixes the plan, metrics, hypothesis, and interpretation rules ahead of
spending QPU, the same pre-registration discipline used for the QAOA-vs-exact
scaling sweep. The point is that no choice below can be made *after* seeing
hardware data.

## Circuits (primary)

Four tuned QAOA circuits, all seed 0, parameters re-optimized on the simulator in
stage (a) (`docs/results/hardware_params.json`):

| circuit | T | reps | qubits (m) | ideal optimal mass | shot-noise floor TVD(exact, ideal-sim) |
|---|---|---|---|---|---|
| T2/reps1 | 2 | 1 | 6  | 0.0288 | 0.0422 |
| T2/reps2 | 2 | 2 | 6  | 0.0011 | 0.0400 |
| T3/reps1 | 3 | 1 | 10 | 0.0001 | 0.1407 |
| T3/reps2 | 3 | 2 | 10 | 0.0009 | 0.1594 |

- **Shots:** 4096 per circuit.
- **Jobs:** a single `SamplerV2` job containing all four circuits.
- **No optimization on hardware** — only sampling of the pre-tuned circuits.

These sizes are chosen because the scaling sweep showed *measurable* ideal
probability concentration here (largest at T2/reps1); larger sizes have no ideal
signal to compare against.

## Backend selection

Least-busy **operational IBM Heron-family** device with at least `m` qubits,
unless `--backend NAME` overrides it. If no Heron device is available the code
falls back to the least-busy operational (non-simulator) backend with enough
qubits, so selection never hard-fails.

## Metrics (per circuit)

Reference distribution is the **tuned-circuit statevector** ("exact"), not the
brute-force optimum; the brute-force optimum only defines the optimal-bitstring
set for the scalar metrics.

1. **Total-variation distance** to the exact reference, for both the ideal-sim
   (4096 shots) and the hardware distribution. TVD(exact, ideal-sim) is the
   irreducible shot-noise floor; TVD(ideal-sim, hardware) is the device-noise
   contribution.
2. **Optimal-state mass** — probability on the brute-force-optimal bitstring(s).
3. **Feasibility rate** — probability on schedules satisfying the hard
   constraints.
4. **Ideal-vs-hardware comparison** — the above reported side by side (exact /
   ideal-sim / hardware) per circuit, in `notebooks/experiment_hardware.ipynb`.

## Named hypothesis

**H1 (depth vs noise).** Ideally, deeper QAOA (reps=2) concentrates at least as
much probability on the optimum as reps=1, but reps=2 has more two-qubit gates and
therefore more device noise. We predict that **on hardware the reps=1 circuit's
optimal mass will be greater than or equal to the reps=2 circuit's at the same
T** — i.e. the deeper circuit's extra device noise outweighs any concentration
gain. This is falsifiable: reps=2 hardware mass exceeding reps=1 refutes H1.

## Stretch sample (optional, explicitly non-primary)

A single 22-qubit T=6/reps1 circuit may be run behind `--include-stretch`. It is
**not a primary result and carries no success signal even ideally** (ideal QAOA
already fails at 22 qubits), so any hardware distribution there is a
device-behavior curiosity, not evidence about QAOA. It is excluded from H1 and
from all conclusions.

## Interpretation rules (one sentence per outcome class)

- **Matches ideal:** hardware optimal mass and feasibility track the ideal-sim
  within roughly the shot-noise floor — the device preserves the (thin) QAOA
  structure at this size.
- **Partially degraded:** hardware optimal mass is reduced and TVD(ideal-sim,
  hardware) is comparable to or larger than the shot-noise floor, but the optimum
  still sits measurably above the 1/4096 floor — device noise erodes the signal
  without erasing it.
- **Washed out:** hardware optimal mass falls to the 1/4096 floor and the
  distribution is effectively structureless (feasibility collapses toward random)
  — device noise destroys the signal at this depth/width.

## Reporting

Every configured circuit is reported regardless of outcome; H1 is evaluated
exactly as stated above; the stretch sample, if run, is labeled non-primary. The
actual QPU seconds are recorded from job metadata into
`docs/results/hardware_counts.json`.
