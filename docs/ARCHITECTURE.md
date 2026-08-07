# Architecture and development notes

Orientation for working in this repository: how the pipeline fits together, the
non-obvious invariants, where the data comes from, and the conventions to keep.
The gotchas are the point — most of them were bugs first. `README.md` is the
project overview; this is the working detail behind it.

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
  builds reproducible day cycles (for real inputs, see `quantum_solar.data.load_nrel_instance`).
- `qubo.py` — `build_qubo` folds the linear cost objective and the constraint
  penalties into an upper-triangular `QUBO`. `default_weights` sizes the
  penalties to dominate the objective.
- `dynamic_programming.py` — `dp_solve`: exact, `O(T·K·3)` DP over the discrete
  SoC grid. The **scalable** ground truth; enforces SoC bounds structurally (no
  slack). Use it, not brute force, for any non-tiny `T`.
  `optima_census` runs the same recurrence forward *and* backward to answer "how
  much of that schedule is actually determined?" — because **`dp_solve`'s returned
  hours are largely arbitrary**. Every hour at the same price is interchangeable,
  so on the real Xcel RE-TOU weekday 2,448 minimal-cost plans tie and only the four
  peak discharge hours are forced. Report `forced()` and `n_minimal`, never the raw
  hour list, whenever the audience might read it as *the* answer. Note `n_optima`
  (all ties) is a much larger and near-useless number **at the lossless default**:
  a charge and discharge at one price then cancel, so it counts unbounded free
  cycling — on a flat-price day, every feasible schedule (~1.5e10). Set a round
  trip below 1 and that degeneracy vanishes (the pair now loses money), so
  `n_optima` becomes meaningful and small. Validated against exhaustive
  enumeration in `tests/test_optima_census.py`.
  The **sizing rule follows from that same fact**: if every optimum discharges
  across the whole peak window and nothing else is forced, the only energy that
  earns is what the rating can deliver inside it, so
  `saving = min(capacity, rate × peak_hours) × price_spread` — linear in capacity,
  then flat at the knee. `docs/results/capacity-rate-sensitivity.md`.
- `ising.py` — `qubo_to_ising` maps the QUBO to a `SparsePauliOp` via
  `x_i = (1 − z_i)/2`. Invariant: `⟨x|H|x⟩ + constant == qubo.energy(x)`.
- `qaoa.py` — `QAOASolver`, hand-rolled from `QAOAAnsatz` + Aer
  `EstimatorV2`/`SamplerV2` + multi-start COBYLA (not `qiskit_algorithms`).
- `brute_force.py` — exact `2^M` enumeration of the QUBO; validates the
  *encoding* on tiny instances. Refuses `> MAX_ENUMERATION_SITES` (20) vars.
- `statevector.py` — `qaoa_probabilities`: the exact QAOA output distribution in
  NumPy. **Use this, never `Statevector(QAOAAnsatz(...))`** — the latter
  matrix-exponentiates the undecomposed cost layer and raises `MemoryError` from
  `m=14` up, which silently capped `ideal_opt_mass` at `T=3` for a whole sweep.
  The cost Hamiltonian is diagonal, so no exponentiation is needed. A constant
  shift of the diagonal is a global phase, so raw QUBO energies work as the cost
  diagonal. Params are `[β_0..β_{p-1}, γ_0..γ_{p-1}]` — `QAOAAnsatz.parameters`
  order, all betas then all gammas, **not** interleaved. `assert_matches_qiskit`
  cross-checks it against Qiskit at a size where Qiskit still works; the scripts
  call it at startup and refuse to report if it drifts.
- All solvers return the shared `Solution` type (`x`, `qubo_energy`,
  `true_energy`, `feasible`).

**Qiskit is an optional dependency of the classical half.** `ising.py` and
`qaoa.py` are the only modules that import it, and `__init__.py` loads their three
exports (`qubo_to_ising`, `QAOASolver`, `QAOAResult`) lazily via PEP 562
`__getattr__`. So `import quantum_solar` pulls **numpy and the stdlib only** — not
qiskit, scipy or matplotlib — and `dp_solve`/`brute_force_solve`/`build_qubo`/
`annual_savings` all run without a quantum stack installed. Touching a quantum name
raises `ImportError` at the attribute, not at package import. Keep the deferral at
the package boundary: `ising`/`qaoa` should keep ordinary top-level imports so each
module still declares its real dependencies, and importing them directly is
eagerly-qiskit by design. `tests/test_optional_qiskit.py` enforces this by blocking
qiskit in `sys.meta_path`, so a stray top-level import fails the suite rather than
passing silently in an environment that happens to have qiskit.
- `annual.py` — `annual_savings` sweeps **all 365 days exactly** (PVWatts fetched
  once, URDB memoized per `(month, weekend)`; ~0.1 s, no extra API calls). Days are
  independent by the `S_T = S_0` constraint, so the annual optimum is the sum of
  per-day `dp_solve` optima. Reports the **three-way** counterfactual split (no
  system / solar only / solar + optimal battery) as `AnnualResult`/`DayResult`;
  `battery_savings` holds solar fixed, so it is the battery alone. `annual_from_inputs`
  is the I/O-free core shared by the live path and `scripts/annual_savings.py`, so
  the attribution is computed in exactly one place.

**Variable layout (important):** `x = [c_0..c_{T-1} | d_0..d_{T-1} | slack]`. The
first `2T` bits are the charge/discharge decisions; `BatteryProblem` reads only
those. Slack bits follow — see below.

Gotchas:
- **SoC inequality encoding.** `0 ≤ S_t ≤ Q` is encoded *exactly* for interior
  slots with a bounded binary slack `s_t ∈ [0,Q]` and penalty `(S_t − s_t)²`.
  Exact (preserves the brute-force contract) but adds `(T−1)·b` qubits — this is
  why brute force / QAOA stay small-`T` and `dp_solve` exists. The terminal
  `S_T = S_0` is a slack-free `(S_T − S_0)²` penalty.
- **v1 modeling assumptions:** `charge_energy == discharge_energy` (keeps SoC on a
  uniform grid, required by both the slack encoding and the DP grid). That is the
  only one left — round-trip losses and export-below-import are both modelled now.
- **Asymmetric pricing is modelled** via `sell_price` (default `None` = net
  metering). Exports credit at `export_price`, imports at `buy_price`, so the bill
  becomes **convex piecewise linear** with a kink at `net == 0`. Three consequences
  worth knowing before touching this: the DP is still valid (the household's net is
  exogenous, so cost stays per-`(slot, action)` — `problem.action_costs()` is the
  single source all four solvers use); the QUBO needs a `c_j*d_j` **correction
  term**, without which the surrogate is right on mutually-exclusive assignments
  and silently wrong on `c_j == d_j == 1`, breaking the brute-force contract where
  nothing looks; and the objective **stops separating**, so the plan finally
  depends on solar and load. `tests/test_export_pricing.py`.
- **Round-trip losses are modelled** (`charge_efficiency`, `discharge_efficiency`,
  both defaulting to `1.0` = the original lossless model). The design rule is
  **losses live in the price, not in the state of charge**: the two energy quanta
  stay store-side and equal so the SoC grid is untouched, and the efficiencies
  convert to grid-side energy inside the objective only — a charging slot imports
  `charge_energy / charge_efficiency`, a discharging slot offsets
  `discharge_energy * discharge_efficiency`. Every cost site must use
  `grid_charge_energy`/`grid_discharge_energy`; every SoC/penalty/encoding site
  must use the store-side quanta. `tests/test_efficiency.py` re-runs the
  DP-vs-brute-force-vs-QUBO cross-checks with losses on, which is what catches a
  coefficient applied in one place and not another.
- **Where the loss sits matters, not just the round trip.** Arbitrage buys cheap
  and sells dear, so energy lost on the charge leg is wasted at the off-peak price
  and energy lost on the discharge leg at the peak price. Same round trip, three
  different bills. Only `breakeven_price_ratio` depends on the product alone: a
  cycle pays iff `p_hi/p_lo > 1/round_trip`.
- **Consequence: the optimal battery plan ignores solar and load entirely.** With
  one buy=sell price the bill separates into `price @ (load − generation)` plus
  the battery's own term, and the battery appears only in the second — so the plan
  depends on the **price curve alone**. Verified: identical schedule under zero
  solar, 3× solar, flat load and random load; only the bill moves. **Never present
  it as real-world guidance**, and don't "fix" a caption by asserting the battery
  charges on surplus solar — it does not.
  This holds **only under net metering**. Set `sell_price` below `price` and the
  kink at `net == 0` couples the plan to the household, which is the regime where a
  battery earns self-consumption value rather than pure arbitrage.
  > *Corrected 2026-08-07.* This previously read "round-trip losses or export paid
  > below import both couple the plan back to solar and load". The losses half was
  > wrong, and is now testable rather than assumed: losses only rescale the battery
  > term's coefficients, leaving the split — and the schedule — intact. Re-verified
  > at a 0.90 round trip, identical plan under all four perturbations. **Only
  > asymmetric buy/sell prices break the separation**, because then which price
  > applies depends on the sign of `load − generation + battery` — now confirmed by
  > `test_export_below_import_couples_the_plan_to_solar`.
- `Solution.true_energy` is **cost** here (lower better) — the sign flips vs a
  yield-style objective.
- QAOA transpiles for an `AerSimulator` with **no coupling map** (trivial layout,
  plain little-endian counts; `_counts_key_to_x` handles endianness).
- `QAOAAnsatz` emits an `NLocal`/`BlueprintCircuit` `DeprecationWarning`
  (Qiskit 2.1, removal in 3.0). Functional; revisit before a Qiskit 3 upgrade.

## Data & secrets

- `synthetic_instance` is the built-in synthetic source. `quantum_solar.data.load_nrel_instance`
  builds a **fully real** instance (`num_slots=24` only): **generation** (NREL
  PVWatts v8), **price** (Xcel CO Residential RE-TOU via the OpenEI/URDB API at
  `api.openei.org`, keyed by the same NREL key), and **load** (NREL ResStock
  representative CO single-family-detached profile — packaged CSVs read with no
  network; provenance in `src/quantum_solar/data/profiles/SOURCE.md`).
- **Season/day-type coherence (do not regress).** `load_nrel_instance` derives the
  price month, the URDB weekday-vs-weekend schedule, **and** the load bucket all
  from `day` (the 0-based day-of-year), so the three inputs can never disagree on
  season or day type — the bug fixed here was `day` selecting the solar day while
  load/price silently stayed on July. The day→season/day-type map lives in
  `data/calendar.py`, pinned to **AMY 2018**: it is the year the ResStock CSVs were
  averaged under, and it is non-leap so `range(365)` aligns 1:1 with the 8760-hour
  PVWatts array — **do not make the year dynamic.** Helpers: `day_to_month`,
  `is_weekend`, `day_type`.
- **Load profiles are 4 committed buckets** (summer/winter × weekday/weekend),
  read via `load_profile(month, day_type)`. An internal month→season table folds
  the 12 months onto the 2 buckets (summer = Jun–Sep, pinned to the RE-TOU tariff
  season), so growing to 12 monthly buckets later is a data + table change with **no
  call-site churn**. Regenerate with `scripts/make_resstock_profiles.py` (downloads
  the ~45 MB ResStock aggregate to gitignored `data/cache/`). `co_summer_weekday_load()`
  is a back-compat alias for `load_profile(6, "weekday")`.
- **URDB weekend path.** `fetch_urdb_tou(..., weekend=True)` reads
  `energyweekendschedule` (flat off-peak in this tariff → $0 weekend arbitrage);
  `weekend=False` (default) reads the weekday schedule, on the same cached payload.
  US federal holidays have no URDB schedule and bill as weekdays on both the price
  and load sides — a known v1 limitation.
- **Energy vs intensive resampling:** generation and load are energy (kWh) →
  `to_slots` (SUM); price is intensive ($/kWh) → `price_to_slots` (AVERAGE). Never
  swap them. All three align on local clock hour 0-23 (DST ignored).
- API responses are cached under `data/cache/` (gitignored), and never when the
  response carries an error (`errors` for PVWatts, `error` for URDB). Loader
  parsing, resampling, and key-resolution are unit-tested offline (HTTP
  monkeypatched); `slow` live tests (`test_pvwatts_live`, `test_urdb_live`) hit
  the real APIs and self-skip when no key is configured.
- **NREL API key** lives in `NREL_API_KEY`. The repo-root `.env` holds it and is
  gitignored — never commit it. `config.nrel_api_key()` reads `os.environ` first,
  then falls back to parsing the repo-root `.env` (ignoring the `REPLACE_ME`
  placeholder).
- **NREL developer domain moved to `developer.nlr.gov`** (NREL → "National
  Laboratory of the Rockies"). The old `developer.nrel.gov` was retired
  2026-05-29 and no longer resolves — use `nlr.gov` in all API URLs and docs.
  Existing API keys still work; only the domain changed.

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

### GitHub CLI (`gh`)

`git push` over the SSH remote authenticates fine, but the GitHub **REST API does
not accept SSH keys** — so anything that *writes* to GitHub needs an API token or
the `gh` CLI. `gh` is not installed by default:

```bash
sudo apt install gh      # install
gh auth login            # authenticate (interactive; do this yourself)
```

This unblocks the GitHub write/query operations this environment otherwise can't
do:

- `gh workflow run tests.yml --ref main` — dispatch the full CI suite (the `full`
  job runs the slow QAOA tests via `workflow_dispatch`) instead of waiting for the
  Monday 06:00 UTC cron.
- `gh run list` / `gh run view` — check Actions status.
- `gh pr create` — open pull requests.

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
  Keep it that way; add a line when introducing a new direct dependency. It is the
  **single source of truth** for dependencies — `pyproject.toml` deliberately
  declares none, which is why the package installs with `pip install -e . --no-deps`.
  Each line is annotated with which half of the project needs it (only `numpy` is
  required by the classical path), but the file is still one full environment, not
  a set of installable tiers. **Do not split it into core/quantum files and do not
  mirror it into `pyproject.toml` extras**: either creates two declarations of the
  same dependency, and they drift. If a slim install is ever actually needed —
  publishing to PyPI, or someone asking for one — do it properly in one move:
  dependencies and `quantum`/`hardware`/`dev` extras into `pyproject.toml`, and
  delete `requirements.txt`. Maintaining both is the failure mode to avoid.
- `requirements-hardware.txt` holds hardware-only deps (`qiskit-ibm-runtime`),
  kept separate so simulator/test users (and CI) don't pull them. Code that needs
  it (`scripts/experiment_hardware.py` submit stage) imports `qiskit_ibm_runtime`
  **lazily** so stages (a)/(c) and the tests run without it installed. Hardware
  auth is a saved account (`~/.qiskit`) via a bare `QiskitRuntimeService()` — no
  legacy `channel="ibm_quantum"` (sunset in the 2025 migration).
- Commits carry no attribution or co-author trailers. Keep it that way.
- Editor and local tooling configuration stays out of the repository; add it to
  `.gitignore` rather than committing machine-local settings.
