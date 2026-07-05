# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Quantum computing approach to solar panel placement optimization. The goal is to
formulate solar-panel siting/layout as an optimization problem and solve it with
quantum algorithms (via Qiskit), likely as a QUBO/Ising model attacked with QAOA
or similar variational methods on the Aer simulator.

## Status

Pre-implementation. As of this writing the repo contains only project metadata
(`README.md`, `LICENSE`), the Python dependency set (`requirements.txt`), and
Claude settings — no source code, tests, or notebooks exist yet. When adding the
first modules, establish the package layout and testing approach, then record
them here.

## Environment & Commands

A virtualenv already exists at `.venv` (Python 3.12).

```bash
source .venv/bin/activate     # activate the environment
pip install -r requirements.txt   # sync dependencies (already installed in .venv)
jupyter lab                   # launch JupyterLab for interactive/quantum work
python path/to/script.py      # run a script
```

No test runner, linter, or build is configured yet. `pytest` is not currently a
dependency — add it (and pin it in `requirements.txt`) before writing tests.

## Stack

- **Qiskit 2.x** (`qiskit`) — quantum circuit construction and algorithms.
- **qiskit-aer** — local high-performance simulator; the default backend for
  running/optimizing circuits without real quantum hardware.
- **numpy / scipy** — numerical work and classical optimizers (e.g. for the
  variational parameter loop in QAOA/VQE-style algorithms).
- **matplotlib** — visualization of layouts, results, and circuits.
- **Jupyter / JupyterLab** — primary interactive development surface.

## Testing

- Use **pytest**. Write unit tests for the physics model and the optimization
  code.
- Validate QAOA output against **classical brute-force enumeration** on small
  problem instances. Small placement problems can be enumerated exactly, so the
  brute-force optimum is ground truth — assert the quantum result matches (or is
  within tolerance of) it before trusting the algorithm on larger instances.

## Code quality

- Prioritize correctness and efficiency.
- Prefer vectorized NumPy over Python loops for numerical work.

## Conventions

- `requirements.txt` is fully pinned (exact versions). Keep it that way and
  update it whenever adding a dependency.
- Commit attribution is intentionally disabled in `.claude/settings.json`
  (empty `commit`/`pr` trailers) — do not add co-author/attribution trailers.
