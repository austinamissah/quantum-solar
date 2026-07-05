"""The QUBO -> Ising bridge: ⟨x|H|x⟩ + constant must equal qubo.energy(x)."""

import itertools

import numpy as np
from qiskit.quantum_info import Statevector

from quantum_solar import build_qubo, qubo_to_ising


def _basis_label(x, m: int) -> str:
    """Qiskit label for |x⟩: leftmost char is the highest qubit."""
    return "".join(str(int(x[m - 1 - i])) for i in range(m))


def _assert_matches(qubo, xs):
    hamiltonian, constant = qubo_to_ising(qubo)
    m = qubo.num_vars
    for x in xs:
        state = Statevector.from_label(_basis_label(x, m))
        expectation = state.expectation_value(hamiltonian).real
        assert np.isclose(expectation + constant, qubo.energy(x))


def test_roundtrip_tiny_exhaustive(tiny_problem, tiny_weights):
    qubo = build_qubo(tiny_problem, tiny_weights)
    xs = [np.array(bits) for bits in itertools.product([0, 1], repeat=qubo.num_vars)]
    _assert_matches(qubo, xs)


def test_roundtrip_small_sampled(small_problem, small_weights):
    qubo = build_qubo(small_problem, small_weights)
    rng = np.random.default_rng(0)
    xs = rng.integers(0, 2, size=(200, qubo.num_vars))
    _assert_matches(qubo, xs)
