"""The QUBO -> Ising bridge: ⟨x|H|x⟩ + constant must equal qubo.energy(x)."""

import itertools

import numpy as np
from qiskit.quantum_info import Statevector

from quantum_solar import build_qubo, qubo_to_ising


def _basis_label(x, m: int) -> str:
    """Qiskit label for |x⟩: leftmost char is the highest qubit."""
    return "".join(str(int(x[m - 1 - i])) for i in range(m))


def _roundtrip_exact(problem, weights):
    qubo = build_qubo(problem, weights)
    hamiltonian, constant = qubo_to_ising(qubo)
    m = qubo.num_vars

    for bits in itertools.product([0, 1], repeat=m):
        x = np.array(bits)
        state = Statevector.from_label(_basis_label(x, m))
        expectation = state.expectation_value(hamiltonian).real
        assert np.isclose(expectation + constant, qubo.energy(x))


def test_roundtrip_tiny(tiny_problem, tiny_weights):
    _roundtrip_exact(tiny_problem, tiny_weights)


def test_roundtrip_small_with_shading(small_problem, small_weights):
    _roundtrip_exact(small_problem, small_weights)
