"""Quantum computing approach to solar panel placement optimization."""

from .brute_force import brute_force_solve
from .ising import qubo_to_ising
from .problem import SolarProblem, random_instance
from .qaoa import QAOAResult, QAOASolver
from .qubo import QUBO, PenaltyWeights, build_qubo
from .solution import Solution

__all__ = [
    "SolarProblem",
    "random_instance",
    "QUBO",
    "PenaltyWeights",
    "build_qubo",
    "qubo_to_ising",
    "brute_force_solve",
    "QAOASolver",
    "QAOAResult",
    "Solution",
]
