"""The NumPy QAOA statevector must agree with Qiskit's, and must scale past it.

The second test is the regression guard: the sweep's ``ideal_opt_mass`` column was
originally computed with ``Statevector(QAOAAnsatz(...))``, which raises
``MemoryError`` from m=14 upward because it matrix-exponentiates the undecomposed
cost layer. That failure only appeared hours into a sweep.
"""

from __future__ import annotations

import numpy as np
import pytest

from quantum_solar import build_qubo, default_weights, qubo_to_ising, synthetic_instance
from quantum_solar.brute_force import enumerate_bitstrings
from quantum_solar.statevector import assert_matches_qiskit, qaoa_probabilities


def _hamiltonian(t, seed=0):
    problem = synthetic_instance(t, seed=seed, capacity=3.0, charge_energy=1.0,
                                 initial_soc=1.0)
    qubo = build_qubo(problem, default_weights(problem))
    return qubo, qubo_to_ising(qubo)[0]


@pytest.mark.parametrize("t", [2, 3])
@pytest.mark.parametrize("reps", [1, 2, 3])
def test_matches_qiskit_statevector(t, reps):
    """Fast path == slow path, at every size where the slow path is tractable."""
    _, hamiltonian = _hamiltonian(t)
    params = np.random.default_rng(reps).uniform(0.0, np.pi, 2 * reps)
    assert assert_matches_qiskit(hamiltonian, params, reps, atol=1e-10) < 1e-10


def test_constant_offset_is_a_global_phase():
    """Shifting the cost diagonal must not change probabilities.

    This is what licenses passing raw QUBO energies where the Ising diagonal is
    expected -- the two differ by ``qubo_to_ising``'s constant.
    """
    qubo, hamiltonian = _hamiltonian(3)
    m = qubo.num_vars
    X = enumerate_bitstrings(m).astype(float)
    energies = np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset
    ising_diagonal = np.real(np.diag(hamiltonian.to_matrix()))
    params = np.random.default_rng(7).uniform(0.0, np.pi, 4)
    a = qaoa_probabilities(energies, params, 2)
    b = qaoa_probabilities(ising_diagonal, params, 2)
    assert np.allclose(a, b, atol=1e-12)


def test_scales_past_the_qiskit_matrix_path():
    """m=18 (T=5) must work -- this is exactly where the original code died."""
    qubo, _ = _hamiltonian(5)
    assert qubo.num_vars == 18
    X = enumerate_bitstrings(18).astype(float)
    energies = np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset
    probs = qaoa_probabilities(energies, np.linspace(0.1, 1.0, 4), 2)
    assert probs.shape == (2 ** 18,)
    assert probs.sum() == pytest.approx(1.0)


def test_normalized_and_rejects_bad_shapes():
    qubo, _ = _hamiltonian(2)
    X = enumerate_bitstrings(qubo.num_vars).astype(float)
    energies = np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset
    assert qaoa_probabilities(energies, [0.3, 0.7], 1).sum() == pytest.approx(1.0)
    with pytest.raises(ValueError):
        qaoa_probabilities(energies, [0.3, 0.7], 2)      # wrong param count
    with pytest.raises(ValueError):
        qaoa_probabilities(energies[:-1], [0.3, 0.7], 1)  # not a power of two
