# quantum-solar

[![tests](https://github.com/austinamissah/quantum-solar/actions/workflows/tests.yml/badge.svg)](https://github.com/austinamissah/quantum-solar/actions/workflows/tests.yml)

Quantum optimization of **residential battery charge/discharge scheduling under
time-of-use electricity pricing**.

Given a day split into `T` time slots — each with a solar generation, household
load, and electricity price — decide when a home battery should charge, discharge,
or idle to minimize the electricity bill, subject to the battery's capacity and a
return-to-initial state-of-charge constraint. The schedule is expressed as a QUBO
and solved with QAOA on the Qiskit Aer simulator, verified against exact classical
baselines.

## Example schedule

The optimizer charges when energy is cheap (overnight and midday, when solar is
abundant) and discharges into the morning and evening price peaks, while keeping
the state of charge within capacity and returning it to its starting level:

![Optimal battery schedule](docs/schedule.png)

*(Illustrative synthetic day; regenerate with `python scripts/make_preview.py`. See
[Real data](#real-data) for using real NREL solar generation.)*

## Pipeline

```
BatteryProblem ──build_qubo──▶ QUBO ──qubo_to_ising──▶ Ising H ──▶ QAOASolver ──▶ schedule
      │                          │                                                   ▲
      │                          └──▶ brute_force_solve (exact, tiny T) ─────────────┤ verify
      └──────────────────────────────▶ dp_solve (exact, polynomial, any T) ──────────┘
```

1. **`BatteryProblem`** owns the true objective (net-metered grid cost) and the
   hard constraints: no simultaneous charge/discharge, state of charge within
   `[0, Q]`, and `S_T = S_0`.
2. **`build_qubo`** folds the linear cost objective and the constraints into a
   QUBO. The state-of-charge inequality `0 ≤ S_t ≤ Q` is encoded **exactly** with
   a bounded binary *slack* variable per interior slot — `(S_t − s_t)²` is zero
   iff the SoC is in band. This is exact (so brute force stays a valid ground
   truth) at the cost of extra qubits.
3. **`qubo_to_ising`** maps the QUBO to a Qiskit `SparsePauliOp` cost Hamiltonian,
   with the invariant `⟨x|H|x⟩ + constant == qubo.energy(x)`.
4. **`QAOASolver`** runs QAOA on Aer (multi-start COBYLA over the variational
   parameters) and samples the best schedule.
5. **Verification.** `brute_force_solve` enumerates the QUBO exactly on tiny
   instances (validating the encoding); `dp_solve` is an exact `O(T·K·3)` dynamic
   program over the SoC grid that scales to a full day and serves as ground truth
   at larger `T`. Tests assert QAOA recovers the exact optimum.

v1 modeling assumptions: net metering (a single buy=sell price) and a lossless
battery with equal charge/discharge energy per slot. Asymmetric pricing and
round-trip losses are on the roadmap.

## Installation

```bash
git clone git@github.com:austinamissah/quantum-solar.git
cd quantum-solar
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # qiskit, qiskit-aer, numpy, scipy, matplotlib, jupyter, pytest
pip install -e . --no-deps        # install the quantum_solar package (src layout)
```

## Run the demo

```bash
jupyter lab notebooks/demo.ipynb
```

The notebook builds a small instance, solves it with brute force, DP, and QAOA
(showing they agree), then plots the optimal schedule for a full day.

## Hardware (IBM Quantum)

Running the tuned QAOA circuits on real hardware uses an extra dependency, kept
out of the main requirements:

```bash
pip install -r requirements-hardware.txt   # qiskit-ibm-runtime (hardware only)
```

`scripts/experiment_hardware.py` has three separated stages:

```bash
python scripts/experiment_hardware.py optimize   # (a) simulator: tune angles -> hardware_params.json
python scripts/experiment_hardware.py submit     # (b) DRY RUN: prints backend/circuits/shots/est. QPU s
python scripts/experiment_hardware.py submit --yes-spend-qpu   # actually samples (SamplerV2, 4096 shots)
```

Stage (b) only ever runs sampling (never optimization) on hardware, is a dry run
unless `--yes-spend-qpu` is given, and records the actual QPU seconds from job
metadata. Auth uses a saved account: run `QiskitRuntimeService.save_account(...)`
once (stored in `~/.qiskit`); the script uses a bare `QiskitRuntimeService()` —
**not** the legacy `channel="ibm_quantum"` (sunset in the 2025 migration).
`notebooks/experiment_hardware.ipynb` compares exact vs ideal-simulated vs
hardware distributions (TVD, optimal mass, feasibility).

## Tests

```bash
pytest -m "not slow"   # fast unit tests (model, QUBO, Ising, brute force, DP)
pytest                 # full suite, including the slow Aer-backed QAOA runs
```

CI runs the fast suite on every push and pull request; a weekly scheduled job
runs the full suite including the slow quantum tests.

## Real data

Solar generation can be pulled from the NREL PVWatts API instead of the synthetic
generator:

```python
from quantum_solar.data import load_nrel_instance

problem = load_nrel_instance(lat=39.74, lon=-105.18, day=172)  # 24 hourly slots
```

Set `NREL_API_KEY` in your environment or a repo-root `.env` (a free key comes
from developer.nlr.gov). Responses are cached under `data/cache/`. **All three
inputs are real and Colorado-coherent:** solar generation (NREL PVWatts),
time-of-use price (Xcel Energy CO *Residential Energy TOU*, Schedule RE-TOU, via
URDB), and household load (NREL ResStock representative Colorado
single-family-detached summer-weekday profile, a packaged reference file; see
`src/quantum_solar/data/profiles/SOURCE.md`). The demo notebook reports a
three-way dollar-savings comparison (no system / solar-only / solar + optimal
battery) for a typical summer weekday.

## Status

The pipeline runs end to end: problem model, exact QUBO encoding, Ising mapping,
QAOA on the Aer simulator, and both classical baselines, all covered by tests. It
is no longer simulation-only. The real-data path uses real inputs throughout (NREL
PVWatts generation, Xcel URDB price, NREL ResStock load, all Colorado-coherent),
and the tuned QAOA circuits have run on real IBM Quantum hardware.

### Results on hardware

On July 11, 2026 the four smallest tuned circuits (2 and 3 time slots, 1 and 2
QAOA layers) ran on `ibm_fez`, a 156-qubit processor, using 7 seconds of QPU time
with 4096 shots per circuit via SamplerV2. Noise grew steadily with circuit size:
the total-variation distance from the ideal simulation rose from 0.12 to 0.46 as
the transpiled two-qubit gate count grew from 37 to 290. Only the smallest circuit
kept a signal clearly above random guessing; the other three fell to the
measurement floor, where noise dominates. The pre-registered prediction that
shallower circuits would survive noise better did not cleanly hold: it flipped with
size, because near the floor the ordering reflected how well each circuit was tuned
rather than its depth. The full analysis is in
`notebooks/experiment_hardware.ipynb`, and the run was pre-registered in
`docs/plans/hardware-run.md`.

## Roadmap

- Representative days across seasons, for annualized rather than single-day savings.
- Relax the v1 modeling assumptions: asymmetric buy/sell prices and round-trip
  efficiency.
- Scaling study: slack-free approximate encodings vs. the exact one.
