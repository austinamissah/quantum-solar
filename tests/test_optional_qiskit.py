"""The classical solvers must import and run without qiskit installed.

`ising` and `qaoa` are the only modules that need qiskit, and their exports are
loaded lazily from `quantum_solar/__init__.py`, so someone with numpy alone can
still use `dp_solve`/`brute_force_solve`. That is only true if it is tested with
qiskit genuinely unimportable — checking it in an environment where qiskit happens
to be installed proves nothing, since a stray top-level import would silently
succeed.

These tests simulate the missing dependency by evicting qiskit from the module
cache and blocking re-import, which is what a numpy-only environment looks like
from the importer's point of view.
"""

from __future__ import annotations

import importlib
import sys

import numpy as np
import pytest

QUANTUM_PACKAGES = {"qiskit", "qiskit_aer", "qiskit_ibm_runtime"}


class _BlockQiskit:
    """A meta-path finder that makes any qiskit import fail."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in QUANTUM_PACKAGES:
            raise ImportError(f"blocked for test: {fullname}")
        return None  # defer to the rest of sys.meta_path


@pytest.fixture
def no_qiskit(monkeypatch):
    """Import machinery in which qiskit does not exist. Restored on teardown."""
    for name in list(sys.modules):
        root = name.split(".")[0]
        if root in QUANTUM_PACKAGES or root == "quantum_solar":
            monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "meta_path", [_BlockQiskit(), *sys.meta_path])
    return importlib.import_module("quantum_solar")


def test_package_imports_without_qiskit(no_qiskit):
    assert no_qiskit.__name__ == "quantum_solar"
    assert not any(m.split(".")[0] in QUANTUM_PACKAGES for m in sys.modules), \
        "importing quantum_solar pulled in a quantum package"


def test_dp_solve_runs_without_qiskit(no_qiskit):
    problem = no_qiskit.synthetic_instance(4, seed=0)
    solution = no_qiskit.dp_solve(problem)
    assert solution.feasible
    assert np.isfinite(solution.true_energy)


def test_brute_force_and_qubo_run_without_qiskit(no_qiskit):
    """The QUBO build and its exact enumeration are classical too."""
    problem = no_qiskit.synthetic_instance(2, seed=0)
    qubo = no_qiskit.build_qubo(problem, no_qiskit.default_weights(problem))
    brute = no_qiskit.brute_force_solve(problem, qubo)
    dp = no_qiskit.dp_solve(problem)
    assert brute.true_energy == pytest.approx(dp.true_energy, abs=1e-9)


def test_quantum_names_raise_at_use_not_at_import(no_qiskit):
    """The failure must be deferred to the attribute, and must name the cause."""
    with pytest.raises(ImportError, match="qiskit"):
        _ = no_qiskit.QAOASolver
    with pytest.raises(ImportError, match="qiskit"):
        _ = no_qiskit.qubo_to_ising


def test_unknown_attribute_still_raises_attribute_error(no_qiskit):
    """__getattr__ must not turn every typo into an ImportError."""
    with pytest.raises(AttributeError, match="no attribute"):
        _ = no_qiskit.does_not_exist


def test_quantum_names_work_when_qiskit_is_present():
    """The lazy path must resolve to the real objects in a normal environment."""
    import quantum_solar

    assert quantum_solar.QAOASolver.__name__ == "QAOASolver"
    assert quantum_solar.qubo_to_ising.__module__ == "quantum_solar.ising"
    # Everything advertised in __all__ must actually be reachable.
    for name in quantum_solar.__all__:
        assert hasattr(quantum_solar, name), f"{name} in __all__ but not gettable"
