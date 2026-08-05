"""Exact QAOA output distribution, computed directly in NumPy.

Qiskit can produce this via ``Statevector(QAOAAnsatz(...).assign_parameters(...))``,
but that path asks Qiskit to turn the cost layer into a matrix: ``QAOAAnsatz``
holds the phase separator as a single :class:`~qiskit.circuit.library.PauliEvolutionGate`,
and an un-decomposed evolution gate is realized by **exponentiating a 2^m x 2^m
operator**. That is fine at m=6 and dies with ``MemoryError`` inside SciPy's sparse
``expm`` by m=14 -- long before the statevector itself (a 2^m vector, 4 MB at m=18)
is anywhere near large.

The cost Hamiltonian here is diagonal (``qubo_to_ising`` emits only I and Z terms),
so no exponentiation is needed at all: the cost layer is an elementwise phase and
the mixer is a single-qubit rotation applied qubit by qubit. That makes the exact
distribution available at every size the sweep runs, for the cost of a handful of
vector operations.

Verified against the Qiskit path by :func:`assert_matches_qiskit` and by
``tests/test_statevector.py``, in the repo's established
"check the fast implementation against the slow one" pattern.
"""

from __future__ import annotations

import numpy as np

__all__ = ["qaoa_probabilities", "assert_matches_qiskit"]


def qaoa_probabilities(cost_diagonal: np.ndarray, params, reps: int) -> np.ndarray:
    """Exact QAOA measurement distribution over the ``2^m`` basis states.

    Parameters
    ----------
    cost_diagonal:
        ``(2^m,)`` array of cost-Hamiltonian diagonal entries, indexed by basis
        integer with **bit j = qubit j** (little-endian, matching Qiskit's
        ``Statevector`` index convention and :func:`enumerate_bitstrings` row
        order). Any constant offset only contributes a global phase, so passing
        raw QUBO energies in place of Ising energies is exact for probabilities.
    params:
        The ``2*reps`` variational parameters **in ``QAOAAnsatz.parameters``
        order**, which is all betas then all gammas -- ``[β_0..β_{p-1},
        γ_0..γ_{p-1}]`` -- not interleaved. (Qiskit sorts a ParameterView by
        name and 'β' < 'γ'.) This is the order ``QAOASolver`` optimizes in, so a
        recorded ``optimal_params`` can be passed straight through.
    reps:
        Number of QAOA layers.

    Returns
    -------
    ``(2^m,)`` array of probabilities summing to 1.
    """
    cost_diagonal = np.asarray(cost_diagonal, dtype=float)
    n = cost_diagonal.size
    m = int(round(np.log2(n)))
    if 2 ** m != n:
        raise ValueError(f"cost_diagonal length {n} is not a power of two")
    params = np.asarray(params, dtype=float)
    if params.size != 2 * reps:
        raise ValueError(f"expected {2 * reps} params for reps={reps}, got {params.size}")
    betas, gammas = params[:reps], params[reps:]

    # |+>^m
    psi = np.full(n, 2.0 ** (-m / 2), dtype=complex)
    for beta, gamma in zip(betas, gammas):
        # Phase separator exp(-i gamma H_C): diagonal, so elementwise.
        psi *= np.exp(-1j * gamma * cost_diagonal)
        # Mixer exp(-i beta sum_j X_j) = prod_j RX(2 beta)_j, applied qubit by
        # qubit. For qubit j the amplitude pairs differing only in bit j are the
        # two halves of axis 1 after reshaping to (high, 2, low).
        c, s = np.cos(beta), -1j * np.sin(beta)
        for j in range(m):
            low, high = 2 ** j, 2 ** (m - 1 - j)
            v = psi.reshape(high, 2, low)
            a, b = v[:, 0, :].copy(), v[:, 1, :].copy()
            v[:, 0, :] = c * a + s * b
            v[:, 1, :] = c * b + s * a
    return np.abs(psi) ** 2


def assert_matches_qiskit(cost_operator, params, reps, *, atol=1e-10) -> float:
    """Check :func:`qaoa_probabilities` against Qiskit's own statevector.

    Builds the reference with ``Statevector(QAOAAnsatz(...))``, which is only
    tractable at small ``m`` -- that is the whole reason the NumPy path exists.
    Returns the max absolute probability difference and raises if it exceeds
    ``atol``, so a caller can refuse to report numbers from an unvalidated path.
    """
    from qiskit.circuit.library import QAOAAnsatz
    from qiskit.quantum_info import Statevector

    ansatz = QAOAAnsatz(cost_operator=cost_operator, reps=reps)
    reference = Statevector(ansatz.assign_parameters(list(params))).probabilities()
    diagonal = np.real(np.diag(cost_operator.to_matrix()))
    mine = qaoa_probabilities(diagonal, params, reps)
    delta = float(np.max(np.abs(reference - mine)))
    if delta > atol:
        raise AssertionError(
            f"NumPy QAOA statevector disagrees with Qiskit by {delta:.3e} "
            f"(atol={atol:.1e}) at reps={reps}"
        )
    return delta
