# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Quantum computing approach to **residential battery charge/discharge scheduling
under time-of-use pricing**. A day is split into `T` slots; in each slot the
battery may charge, discharge, or idle. The goal is to minimize electricity cost
by formulating the schedule as a QUBO and solving it with QAOA (Qiskit/Aer),
validated against exact classical baselines.

## Architecture

The package lives in `src/quantum_solar/` (src layout — importable after
`pip install -e . --no-deps`). The pipeline is:

```
BatteryProblem --build_qubo--> QUBO --+--> brute_force_solve ------> Solution
       |                              |
       |                              +--qubo_to_ising--> QAOASolver.solve --> QAOAResult
       +--(exact, polynomial)--> dp_solve --------------> Solution
```

Core design principle: the **true objective (grid cost) is kept separate from the
QUBO surrogate**. `ising.py`, `qaoa.py`, `brute_force.py`, `solution.py` are
domain-agnostic over "a QUBO + a problem exposing `energy(x)`/`is_feasible(x)`".

- `problem.py` — `BatteryProblem` owns the physics: `energy(x)` (net-metered grid
  cost, **lower is better**) and `is_feasible(x)` (mutual exclusion, SoC bounds
  `0 ≤ S_t ≤ Q`, and return-to-initial `S_T = S_0`). `synthetic_instance(...)`
  builds reproducible day cycles (NREL/EIA loaders are a future addition).
- `qubo.py` — `build_qubo` folds the linear cost objective and the constraint
  penalties into an upper-triangular `QUBO`. `default_weights` sizes the
  penalties to dominate the objective.
- `dynamic_programming.py` — `dp_solve`: exact, `O(T·K·3)` DP over the discrete
  SoC grid. The **scalable** ground truth; enforces SoC bounds structurally (no
  slack). Use it, not brute force, for any non-tiny `T`.
- `ising.py` — `qubo_to_ising` maps the QUBO to a `SparsePauliOp` via
  `x_i = (1 − z_i)/2`. Invariant: `⟨x|H|x⟩ + constant == qubo.energy(x)`.
- `qaoa.py` — `QAOASolver`, hand-rolled from `QAOAAnsatz` + Aer
  `EstimatorV2`/`SamplerV2` + multi-start COBYLA (not `qiskit_algorithms`).
- `brute_force.py` — exact `2^M` enumeration of the QUBO; validates the
  *encoding* on tiny instances. Refuses `> MAX_ENUMERATION_SITES` (20) vars.
- All solvers return the shared `Solution` type (`x`, `qubo_energy`,
  `true_energy`, `feasible`).

**Variable layout (important):** `x = [c_0..c_{T-1} | d_0..d_{T-1} | slack]`. The
first `2T` bits are the charge/discharge decisions; `BatteryProblem` reads only
those. Slack bits follow — see below.

Gotchas:
- **SoC inequality encoding.** `0 ≤ S_t ≤ Q` is encoded *exactly* for interior
  slots with a bounded binary slack `s_t ∈ [0,Q]` and penalty `(S_t − s_t)²`.
  Exact (preserves the brute-force contract) but adds `(T−1)·b` qubits — this is
  why brute force / QAOA stay small-`T` and `dp_solve` exists. The terminal
  `S_T = S_0` is a slack-free `(S_T − S_0)²` penalty.
- **v1 modeling assumptions:** net metering (single buy=sell price, keeps the
  objective linear) and a lossless battery with `charge_energy == discharge_energy`
  (keeps SoC on a uniform grid, required by both the slack encoding and the DP
  grid). Asymmetric prices / losses are deferred.
- `Solution.true_energy` is **cost** here (lower better) — the sign flips vs a
  yield-style objective.
- QAOA transpiles for an `AerSimulator` with **no coupling map** (trivial layout,
  plain little-endian counts; `_counts_key_to_x` handles endianness).
- `QAOAAnsatz` emits an `NLocal`/`BlueprintCircuit` `DeprecationWarning`
  (Qiskit 2.1, removal in 3.0). Functional; revisit before a Qiskit 3 upgrade.

## Environment & Commands

A virtualenv already exists at `.venv` (Python 3.12).

```bash
source .venv/bin/activate         # activate the environment
pip install -r requirements.txt   # sync deps (already installed in .venv)
pip install -e . --no-deps        # make `import quantum_solar` work (src layout)

python -m pytest                  # full suite (~10s; includes slow QAOA runs)
python -m pytest -m "not slow"    # fast unit tests only, skip Aer end-to-end
python -m pytest tests/test_ising.py::test_roundtrip_tiny_exhaustive   # single test
python -m pytest -m slow          # only the end-to-end QAOA vs brute-force tests

jupyter lab                       # interactive/quantum work in notebooks/
```

No linter is configured. The slow marker gates the Aer-backed QAOA tests
(defined in `pyproject.toml`).

## Stack

- **Qiskit 2.x** (`qiskit`) — quantum circuit construction and algorithms.
- **qiskit-aer** — local high-performance simulator; the default backend for
  running/optimizing circuits without real quantum hardware.
- **numpy / scipy** — numerical work and classical optimizers (e.g. for the
  variational parameter loop in QAOA/VQE-style algorithms).
- **matplotlib** — visualization of schedules, price/SoC curves, and circuits.
- **Jupyter / JupyterLab** — primary interactive development surface.

## Testing

- Use **pytest**. Write unit tests for the physics model and the optimization
  code.
- Validate against exact classical baselines: **brute-force enumeration** of the
  QUBO on tiny instances (validates the encoding), and the **DP solver** as the
  scalable ground truth (`test_dynamic_programming` checks DP == brute force on
  tiny instances, then DP scales to a full `T=24` day). QAOA results are asserted
  to recover the brute-force/DP optimum before being trusted at larger sizes.

## Code quality

- Prioritize correctness and efficiency.
- Prefer vectorized NumPy over Python loops for numerical work.

## Conventions

- `requirements.txt` lists only direct dependencies with `~=` major.minor bounds.
  Keep it that way; add a line when introducing a new direct dependency.
- Commit attribution is intentionally disabled in `.claude/settings.json`
  (empty `commit`/`pr` trailers) — do not add co-author/attribution trailers.
