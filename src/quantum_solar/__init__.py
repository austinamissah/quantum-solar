"""Quantum computing approach to residential battery scheduling optimization.

The classical half of this package — ``BatteryProblem``, ``build_qubo``,
``dp_solve``, ``brute_force_solve``, ``annual_savings`` — needs **only numpy and
the standard library**. Qiskit is required by exactly two modules, ``ising`` and
``qaoa``, so the three names they export are loaded lazily (PEP 562) rather than
at package import. ``import quantum_solar`` therefore works, and the exact
classical solvers run, in an environment with no quantum stack installed.

The deferral is here at the package boundary on purpose: ``ising`` and ``qaoa``
keep ordinary top-level imports, so each module still declares the dependencies it
genuinely has. Importing either directly (``from quantum_solar.qaoa import
QAOASolver``) imports qiskit eagerly, as it should — the requirement is real, it is
just not the whole package's.

Touching a quantum name without qiskit installed raises ``ImportError`` naming the
missing package, at the point of use rather than at ``import quantum_solar``.
"""

from importlib import import_module

from .annual import AnnualResult, DayResult, annual_savings
from .brute_force import brute_force_solve
from .dynamic_programming import dp_solve
from .encodings import Encoding, SoCEncoding, max_sound_spacing
from .problem import BatteryProblem, synthetic_instance
from .qubo import QUBO, PenaltyWeights, build_qubo, default_weights, num_vars
from .solution import Solution

# name -> submodule that defines it. These are the only qiskit-dependent exports.
_LAZY = {
    "qubo_to_ising": "ising",
    "QAOAResult": "qaoa",
    "QAOASolver": "qaoa",
}


def __getattr__(name: str):
    """Load the qiskit-backed exports on first use (PEP 562)."""
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{_LAZY[name]}", __name__), name)
    globals()[name] = value  # cache: __getattr__ is only consulted on a miss
    return value


def __dir__() -> list[str]:
    return sorted(__all__)

__all__ = [
    "BatteryProblem",
    "synthetic_instance",
    "QUBO",
    "PenaltyWeights",
    "build_qubo",
    "default_weights",
    "num_vars",
    "Encoding",
    "SoCEncoding",
    "max_sound_spacing",
    "qubo_to_ising",
    "brute_force_solve",
    "dp_solve",
    "QAOASolver",
    "QAOAResult",
    "Solution",
    "annual_savings",
    "AnnualResult",
    "DayResult",
]
