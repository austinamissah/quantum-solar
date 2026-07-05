"""Map a QUBO to an Ising cost Hamiltonian for the quantum solver.

Substituting ``x_i = (1 − z_i) / 2`` (with ``z_i`` the eigenvalue of ``Z_i``)
into ``xᵀQx + offset`` yields a diagonal Hamiltonian

    H = Σ_i h_i Z_i + Σ_{i<j} J_ij Z_i Z_j

plus a scalar constant. The Hamiltonian is returned separately from the constant
so QAOA can add the constant back when reporting energies. By construction,
``⟨x|H|x⟩ + constant == qubo.energy(x)`` for every computational basis state.
"""

from __future__ import annotations

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from .qubo import QUBO


def qubo_to_ising(qubo: QUBO) -> tuple[SparsePauliOp, float]:
    """Return ``(H, constant)`` for the given QUBO."""
    Q = qubo.Q
    m = qubo.num_vars

    diag = np.diag(Q).astype(float)
    # Symmetric off-diagonal matrix A (A_ij = A_ji = Q_ij for i<j, zero diagonal).
    off = np.triu(Q, k=1)
    A = off + off.T

    constant = float(qubo.offset + 0.5 * diag.sum() + 0.25 * off.sum())
    h = -0.5 * diag - 0.25 * A.sum(axis=1)
    # J_ij = Q_ij / 4 for i < j.
    ii, jj = np.triu_indices(m, k=1)
    j_coeffs = off[ii, jj] / 4.0

    terms: list[tuple[str, list[int], float]] = []
    for i in range(m):
        if h[i] != 0.0:
            terms.append(("Z", [i], float(h[i])))
    for i, j, c in zip(ii, jj, j_coeffs):
        if c != 0.0:
            terms.append(("ZZ", [int(i), int(j)], float(c)))

    if not terms:
        # Degenerate all-zero Hamiltonian; represent as 0·I so the op is valid.
        return SparsePauliOp.from_list([("I" * m, 0.0)]), constant

    return SparsePauliOp.from_sparse_list(terms, num_qubits=m), constant
