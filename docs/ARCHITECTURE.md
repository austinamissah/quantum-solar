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
  slack). It replaces brute force for any non-tiny `T`.
  **`dp_solve`'s tie-break is specified rather than incidental.** Selection is
  lexicographic: minimum cost (within `TIE_ATOL`), then **fewest battery actions**,
  then a fixed action preference (idle < charge < discharge). The comparison is
  tolerance-based *on purpose* — an exact `<` is what let the `action_costs()`
  refactor move costs by ~1e-16, reorder the ties, and silently rewrite all four
  committed schedule figures (the summer weekday went 8 actions → 10; the
  flat-price weekends went from an idle line to cost-free churn). No cost moved, so
  nothing caught it. The minimal-action step also guarantees the returned plan uses
  exactly `optima_census(...).min_actions`, i.e. it is always a member of the
  population the census counts — otherwise pairing `dp_solve`'s hours with
  `forced()` in one figure is incoherent. Pinned by
  `tests/test_dynamic_programming.py` (minimal-action invariant over a 36-cell
  sweep, `true_energy == energy(x)`, and a flat-price day returning idle).
  `optima_census` runs the same recurrence forward *and* backward to answer "how
  much of that schedule is actually determined?" — because **the returned hours are
  still only one of many tied optima**. Every hour at the same price is
  interchangeable, so on the real Xcel RE-TOU weekday 2,448 minimal-cost plans tie
  and only the four peak discharge hours are forced. Report `forced()` and
  `n_minimal` rather than the raw hour list, wherever the audience might read it as *the*
  answer — the tie-break makes the plan reproducible, not canonical. Note `n_optima`
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
  NumPy. **This replaces `Statevector(QAOAAnsatz(...))`** — the latter
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
- `__main__.py` — `python -m quantum_solar`, the one-command demo. **Runs entirely
  offline**: the annual snapshot (`docs/figures/annual_golden_co.json`) plus the
  packaged ResStock profiles, so a fresh clone needs no `NREL_API_KEY` and no warm
  `data/cache/` — which the notebook's real-data cells do. Numpy-only (text
  rendering, no matplotlib); `--quantum` is the sole path that imports qiskit, and
  it degrades to an install hint rather than a traceback. Every dollar figure goes
  through `annual_from_inputs`, and `tests/test_cli.py` pins the three-way split
  against the README's table so the two cannot drift. Two rules are enforced in the
  output rather than left to the reader: the solar and battery legs are never
  summed, and **the sizing-rule narrative is suppressed unless `export_ratio == 1`**
  — below-retail export couples the plan to solar and load, the knee stops existing
  and the rate column stops being monotonic, so narrating the rule there would be a
  confidently wrong claim.

**Qiskit is an optional dependency of the classical half.** `ising.py` and
`qaoa.py` are the only modules that import it, and `__init__.py` loads their three
exports (`qubo_to_ising`, `QAOASolver`, `QAOAResult`) lazily via PEP 562
`__getattr__`. So `import quantum_solar` pulls **numpy and the stdlib only** — not
qiskit, scipy or matplotlib — and `dp_solve`/`brute_force_solve`/`build_qubo`/
`annual_savings` all run without a quantum stack installed. Touching a quantum name
raises `ImportError` at the attribute, not at package import. The deferral sits at
the package boundary: `ising`/`qaoa` keep ordinary top-level imports so each module
still declares its real dependencies, and importing them directly is eagerly-qiskit
by design. `tests/test_optional_qiskit.py` enforces this by blocking
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
- **No v1 modeling assumptions remain.** Round-trip losses, export credited below
  import, and asymmetric charge/discharge rates are all modeled, and every one
  defaults to the original behavior.
- **Asymmetric charge/discharge energy** is supported. The SoC grid step is
  `soc_quantum(problem)` — the **GCD** of the two quanta, not either one — because
  reachable states `S_0 + n_c·e_c − n_d·e_d` form a uniform grid iff the quanta are
  commensurate. A charge then spans `charge_energy/g` levels and a discharge
  `discharge_energy/g`; with equal rates `g` *is* that rate and nothing changes.
  `encodings.soc_grid` is the **single place** this lands — slack width, penalty
  scaling and the search state space all derive from it, so nothing reintroduces
  `problem.charge_energy` as a grid step anywhere. Three consequences:
  - **Incommensurate rates are rejected, not approximated.** 2.0 against 2.0√2
    needs ~9M levels, so `require_soc_on_grid` fails on `MAX_SOC_LEVELS` (4096).
  - **Asymmetry costs qubits, and only in the slack encoding.** A finer grid needs
    a wider slack register: at T=6/Q=10, `EXACT` goes 27 → **37** qubits for
    2.0-in/1.5-out and 42 for 2.0/1.25, while slack-free `checkpoint(3)` stays at
    **12 regardless**. So asymmetric hardware *widens* the encoding gap that
    `docs/results/slack-free-encoding.md` measured, in the slack-free encoding's
    favor.
  - **`qubo_min_exact` rejects `WindowDrift` + asymmetric rates.** That search packs
    each SoC step into one base-3 digit (−1/0/+1), which cannot hold the four
    distinct steps asymmetry produces. Every other encoding has no drift term, so
    only this combination is affected; it raises rather than returning a quietly
    wrong optimum.
- **Asymmetric pricing is modeled** via `sell_price` (default `None` = net
  metering). Exports credit at `export_price`, imports at `buy_price`, so the bill
  becomes **convex piecewise linear** with a kink at `net == 0`. Three consequences
  worth knowing before touching this: the DP is still valid (the household's net is
  exogenous, so cost stays per-`(slot, action)` — `problem.action_costs()` is the
  single source all four solvers use); the QUBO needs a `c_j*d_j` **correction
  term**, without which the surrogate is right on mutually-exclusive assignments
  and silently wrong on `c_j == d_j == 1`, breaking the brute-force contract where
  nothing looks; and the objective **stops separating**, so the plan finally
  depends on solar and load. `tests/test_export_pricing.py`.
- **Round-trip losses are modeled** (`charge_efficiency`, `discharge_efficiency`,
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
  solar, 3× solar, flat load and random load; only the bill moves. **It is a
  modeling artifact rather than real-world guidance**, and a caption asserting the
  battery charges on surplus solar would be wrong: it does not.
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
- **Season/day-type coherence.** `load_nrel_instance` derives the
  price month, the URDB weekday-vs-weekend schedule, **and** the load bucket all
  from `day` (the 0-based day-of-year), so the three inputs can never disagree on
  season or day type — the bug fixed here was `day` selecting the solar day while
  load/price silently stayed on July. The day→season/day-type map lives in
  `data/calendar.py`, pinned to **AMY 2018**: it is the year the ResStock CSVs were
  averaged under, and it is non-leap so `range(365)` aligns 1:1 with the 8760-hour
  PVWatts array, so the year is fixed rather than dynamic. Helpers: `day_to_month`,
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
  gitignored and uncommitted. `config.nrel_api_key()` reads `os.environ` first,
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

python -m quantum_solar           # the demo: one day, the year, sizing, payback
python -m quantum_solar --help    # the knobs (capacity/rate/round-trip/export/day)

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
- Numerical work is vectorized NumPy rather than Python loops.

## Conventions

- `requirements.txt` lists only direct dependencies with `~=` major.minor bounds.
  A line is added there when a new direct dependency appears. It is the
  **single source of truth** for dependencies — `pyproject.toml` deliberately
  declares none, which is why the package installs with `pip install -e . --no-deps`.
  Each line is annotated with which half of the project needs it (only `numpy` is
  required by the classical path), but the file is still one full environment, not
  a set of installable tiers. It is deliberately **not** split into core/quantum
  files and **not** mirrored into `pyproject.toml` extras: either creates two
  declarations of the same dependency, and they drift. If a slim install is ever actually needed —
  publishing to PyPI, or someone asking for one — do it properly in one move:
  dependencies and `quantum`/`hardware`/`dev` extras into `pyproject.toml`, and
  delete `requirements.txt`. Maintaining both is the failure mode to avoid.
- `requirements-hardware.txt` holds hardware-only deps (`qiskit-ibm-runtime`),
  kept separate so simulator/test users (and CI) don't pull them. Code that needs
  it (`scripts/experiment_hardware.py` submit stage) imports `qiskit_ibm_runtime`
  **lazily** so stages (a)/(c) and the tests run without it installed. Hardware
  auth is a saved account (`~/.qiskit`) via a bare `QiskitRuntimeService()` — no
  legacy `channel="ibm_quantum"` (sunset in the 2025 migration).
- **A published number lives in exactly one place; everywhere else derives it.**
  Every figure a write-up in `docs/results/` states is checked against the artifact
  that produced it, and every restatement of one in a comment, a docstring, or a
  module constant is checked against the document it came from. Enforced by
  `tests/_markdown.py` (shared parsing) plus the `tests/test_*_tables.py` modules,
  which between them cover every write-up, and by
  `tests/test_code_comment_figures.py` for the restatements. A number added to a write-up gets its check
  with it: the write-ups are hand-written, no script emits them, and an unchecked
  figure has drifted from its own data more than once. Three things separate a gate
  from a rubber stamp:
  - **Recomputation, not comparison.** A column with no counterpart in an artifact — a
    percentage, a gain, a ratio — is hand arithmetic, and hand arithmetic is where
    every wrong number found so far has been.
  - **A check that infers its rule from the data it checks proves nothing.** It
    agrees with that data whatever the rule really is. Where the code already derives
    a value (an evaluation cap, a reliability threshold), the test derives it the same
    way rather than restating the answer.
  - **A ratio of rounded figures needs an interval, not equality.** These documents
    divide unrounded quantities and print the rounded ones, so `0.00013 → 0.0453` is
    published as 349× while the printed pair divides to 348. `rounding_interval` and
    `assert_quotient` cover this; equality fails on correct arithmetic.
- **Those checks are found by text-matching, so they are blind to a change of
  units.** A threshold registered as `10%` in a plan and held as `0.10` in code does
  not match, and was missed for exactly that reason. Fraction against percent is the
  common case; seconds against minutes and kWh against Wh have the same shape. A
  number appearing in a unit its document does not use has to be paired up by hand,
  since no sweep finds it.
- **Guards here are mutation-tested, not just the findings.** A check that passes on
  correct data has shown nothing; breaking what it claims to protect is what shows it
  works. On
  2026-08-24 five separate guards in this repository turned out to be weaker than they
  read, and every one was found this way and none any other way:
  - a rule inferred from the very table it was checking, so it would have agreed with
    that table whichever rule was real;
  - an evaluation cap hardcoded where the script derives it;
  - a caveat guard that checked the sentences either side of the one it protected;
  - a verdict table whose **outcome** column was never checked, so "held" could flip
    to "FALSIFIED" with every figure intact;
  - three guards that silently matched nothing because the sentence they quoted
    **wraps across source lines**.

  The last is the subtlest: a pattern that matches nothing passes forever and looks
  identical to a pattern that matches. Mutations here assert the pattern is present
  before changing it, because otherwise the mutation test reports success while
  exercising nothing — which happened here first and hid two of the five.
- **Where a write-up's caveats do work, gate the caveats too.** These documents earn
  their conclusions by bounding them, so a later edit that keeps "picks the argmax in
  9 of 9" while dropping "and the held-out instances are easy" leaves every number
  correct and the paper wrong. The `test_selection_*_tables.py` modules assert the
  limiting sentences alongside the findings, and mutation-test both.
- Commits carry no attribution or co-author trailers.
- Editor and local tooling configuration stays out of the repository, in
  `.gitignore` rather than committed.
