"""Encodings of the state-of-charge bounds ``0 ≤ S_t ≤ Q`` as QUBO penalties.

A QUBO is a quadratic polynomial in binary variables, so it expresses *equality*
constraints natively but not inequalities. The exact treatment (:class:`ExactSoC`,
the v1 default) buys the inequality with a bounded binary slack per interior slot,
at ``(T−1)·b`` auxiliary qubits — which is most of the register: at ``T=6`` with
``Q=3, e=1`` it is 10 of 22 qubits, and it grows with capacity as well as with
``T``. It also dilutes the QAOA ground-state mass by ``2^{(T−1)b}``, since exactly
one of the ``2^{10}`` slack patterns pairs with the optimal decision bits.

This module makes that choice pluggable. Every encoding here supplies **only** the
interior-slot SoC-bound penalty; the objective, the mutual-exclusion penalty, and
the terminal ``S_T = S_0`` constraint are shared and stay in
:mod:`quantum_solar.qubo`. The alternatives all use ``0`` auxiliary qubits, so
they cost ``2T`` regardless of capacity:

=====================  ========================  =========  ================
encoding               aux qubits                sound?     tunable weight?
=====================  ========================  =========  ================
:class:`ExactSoC`      ``(T−1)·b``               exact      no
:class:`Checkpoint`    ``0``, or ``n_cp·b_k``    **yes**    no
:class:`WindowDrift`   ``0``                     no         yes
:class:`CenterAnchor`  ``0``                     no         yes
:class:`NoSoCBounds`   ``0``                     no         no
=====================  ========================  =========  ================

"Sound" means every zero-penalty assignment is genuinely SoC-feasible, so the
QUBO's optimum can be suboptimal but never *infeasible*. Only
:class:`Checkpoint` has that property; it is an inner approximation. The others
are outer approximations whose argmin may violate the bounds — which is the point
of the study: ``dp_solve`` is exact and independent of the QUBO, so the rate at
which each encoding's optimum departs from the true optimum is measurable at
every ``T``.

Soundness of :class:`Checkpoint`: between two slots pinned to the same SoC level
and ``k`` apart, the trajectory rises at most ``j`` steps and must fall within the
remaining ``k−j``, so its excursion is bounded by ``max_j min(j, k−j) = ⌊k/2⌋``.
Pinning every ``k``-th slot therefore keeps the whole path in band provided
``⌊k/2⌋`` steps of headroom exist on both sides — see :func:`max_sound_spacing`.
Spacing is always an explicit, validated argument; it is deliberately *not*
derived from the instance, because the sound ceiling depends on ``initial_soc``
and silently inheriting it hides the constraint that matters most.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Protocol, runtime_checkable

import numpy as np

from .problem import BatteryProblem


def bounded_int_weights(n_max: int) -> list[int]:
    """Binary weights that represent every integer in ``[0, n_max]`` exactly.

    Uses powers of two with an adjusted final coefficient so the maximum is
    exactly ``n_max`` (the standard bounded-integer encoding).
    """
    if n_max <= 0:
        return []
    m = int(np.floor(np.log2(n_max)))
    weights = [1 << i for i in range(m)]
    weights.append(n_max - (2**m - 1))
    return weights


def add_squared(
    Q: np.ndarray, terms: list[tuple[int, float]], const: float, weight: float
) -> float:
    """Accumulate ``weight·(Σ α_i x_i + const)²`` into upper-triangular ``Q``.

    Returns the scalar contribution to the QUBO offset.
    """
    for i, ai in terms:
        Q[i, i] += weight * (ai * ai + 2.0 * const * ai)
    for a in range(len(terms)):
        i, ai = terms[a]
        for b in range(a + 1, len(terms)):
            j, aj = terms[b]
            lo, hi = (i, j) if i < j else (j, i)
            Q[lo, hi] += weight * 2.0 * ai * aj
    return weight * const * const


def encode_bounded(value: int, weights: list[int]) -> list[int]:
    """Bits selecting ``weights`` that sum to ``value``.

    Greedy largest-first, which is exact for :func:`bounded_int_weights` (every
    integer in ``[0, n_max]`` is representable). Used to rebuild the auxiliary
    block once a DP has chosen the SoC path.
    """
    bits = [0] * len(weights)
    rem = int(value)
    for i in sorted(range(len(weights)), key=lambda i: -weights[i]):
        if weights[i] <= rem:
            bits[i] = 1
            rem -= weights[i]
    if rem != 0:
        raise ValueError(f"{value} is not representable by weights {weights}")
    return bits


def clamp_dist(k: np.ndarray, lo: int, hi: int) -> np.ndarray:
    """Distance from each ``k`` to the interval ``[lo, hi]`` (``0`` when inside)."""
    return np.maximum(np.maximum(lo - k, k - hi), 0)


def soc_grid(problem: BatteryProblem) -> tuple[float, int, int]:
    """``(e, n_max, k_0)``: the SoC quantum, the top grid level, and ``S_0``'s level."""
    e = problem.charge_energy
    return e, int(round(problem.capacity / e)), int(round(problem.initial_soc / e))


def soc_terms(problem: BatteryProblem, upto: int) -> list[tuple[int, float]]:
    """``S_{upto+1} − S_0`` as a linear form in the decision bits."""
    t = problem.num_slots
    return [(i, problem.charge_energy) for i in range(upto + 1)] + [
        (t + i, -problem.discharge_energy) for i in range(upto + 1)
    ]


def max_sound_spacing(problem: BatteryProblem) -> int:
    """Largest :class:`Checkpoint` spacing that stays sound on this instance.

    A checkpoint gap of ``k`` admits excursions of ``⌊k/2⌋`` grid steps either
    way, so the headroom ``h = min(k_0, n_max − k_0)`` caps it at ``2h + 1``.
    Returns ``1`` when ``S_0`` sits on a boundary (``h = 0``), where every slot
    must be pinned and the encoding degenerates to "never move".
    """
    _, n_max, k0 = soc_grid(problem)
    return 2 * min(k0, n_max - k0) + 1


@runtime_checkable
class SoCEncoding(Protocol):
    """How the interior-slot bounds ``0 ≤ S_t ≤ Q`` enter the QUBO."""

    def validate(self, problem: BatteryProblem) -> None:
        """Raise :class:`ValueError` if this encoding cannot be applied."""

    def aux_bits(self, problem: BatteryProblem) -> int:
        """Auxiliary qubits required beyond the ``2T`` decision bits."""

    def add_penalty(
        self, Q: np.ndarray, problem: BatteryProblem, weight: float, aux_base: int
    ) -> float:
        """Accumulate the penalty into ``Q``; return the QUBO offset contribution."""

    # --- DP-side view of the same penalty (see quantum_solar.qubo_search) ---
    # These express the penalty as a function of the SoC path so it can be
    # minimized exactly at any T. They must agree with add_penalty; the
    # brute-force equivalence test in tests/test_qubo_search.py is what enforces
    # that, and it is the reason both live in this file rather than apart.

    def slot_penalty(
        self, problem: BatteryProblem, weight: float, levels: np.ndarray
    ) -> np.ndarray:
        """Penalty at each interior slot for each SoC level, shape ``(T−1, len(levels))``.

        Auxiliary variables are minimized out analytically (they are free), so
        this is the penalty the QUBO's optimum actually pays.
        """

    def drift_spec(
        self, problem: BatteryProblem, weight: float
    ) -> tuple[int, float] | None:
        """``(window, coefficient)`` for cross-slot drift penalties, else ``None``."""

    def aux_assignment(self, problem: BatteryProblem, levels: np.ndarray) -> np.ndarray:
        """Optimal auxiliary bits for an SoC path ``levels = [k_1 … k_T]``."""


class _NoAuxDefaults:
    """Defaults for encodings with no auxiliary block and no cross-slot coupling."""

    def validate(self, problem: BatteryProblem) -> None:
        return None

    def aux_bits(self, problem: BatteryProblem) -> int:
        return 0

    def drift_spec(
        self, problem: BatteryProblem, weight: float
    ) -> tuple[int, float] | None:
        return None

    def aux_assignment(self, problem: BatteryProblem, levels: np.ndarray) -> np.ndarray:
        return np.zeros(0, dtype=np.int8)


@dataclass(frozen=True)
class ExactSoC:
    """Bounded binary slack per interior slot — exact, ``(T−1)·b`` aux qubits.

    ``S_t`` is linear in the bits, so ``(S_t − s_t)²`` with ``s_t ∈ [0, Q]``
    representable is zero iff ``S_t`` is in band. Preserves the brute-force
    verification contract; this is the v1 default.
    """

    def validate(self, problem: BatteryProblem) -> None:
        return None

    def aux_bits(self, problem: BatteryProblem) -> int:
        _, n_max, _ = soc_grid(problem)
        return (problem.num_slots - 1) * len(bounded_int_weights(n_max))

    def add_penalty(
        self, Q: np.ndarray, problem: BatteryProblem, weight: float, aux_base: int
    ) -> float:
        e, n_max, _ = soc_grid(problem)
        slot_weights = bounded_int_weights(n_max)
        b = len(slot_weights)
        offset = 0.0
        for j in range(problem.num_slots - 1):
            terms = soc_terms(problem, j)
            terms += [(aux_base + j * b + k, -e * w) for k, w in enumerate(slot_weights)]
            offset += add_squared(Q, terms, problem.initial_soc, weight)
        return offset

    def slot_penalty(
        self, problem: BatteryProblem, weight: float, levels: np.ndarray
    ) -> np.ndarray:
        # Slack is free, so it takes the representable value nearest S_t: the
        # residual is the distance from S_t to the band [0, n_max]·e.
        e, n_max, _ = soc_grid(problem)
        row = weight * (e * clamp_dist(levels, 0, n_max)) ** 2
        return np.tile(row, (problem.num_slots - 1, 1))

    def drift_spec(
        self, problem: BatteryProblem, weight: float
    ) -> tuple[int, float] | None:
        return None

    def aux_assignment(self, problem: BatteryProblem, levels: np.ndarray) -> np.ndarray:
        _, n_max, _ = soc_grid(problem)
        w = bounded_int_weights(n_max)
        bits: list[int] = []
        for j in range(problem.num_slots - 1):
            bits += encode_bounded(int(np.clip(levels[j], 0, n_max)), w)
        return np.array(bits, dtype=np.int8)


@dataclass(frozen=True)
class Checkpoint:
    """Pin the SoC every ``spacing`` slots — sound, and slack-free by default.

    With ``banded=False`` the pinned slots are held at exactly ``S_0``, an
    equality penalty on the decision bits alone: ``0`` aux qubits. With
    ``banded=True`` they may instead land anywhere in the *tightened* band
    ``[⌊k/2⌋·e, Q − ⌊k/2⌋·e]``, encoded with a small slack register per
    checkpoint — still sound (the tightening absorbs the worst-case excursion),
    much less rigid, and far cheaper than :class:`ExactSoC` because there are
    ``⌈T/k⌉−1`` checkpoints rather than ``T−1`` slots.

    What is lost either way: schedules that hold charge *across* a checkpoint,
    including the canonical "charge at the midday trough, hold, discharge into
    the evening peak". That cost is the thing the encoding study measures.

    The penalty is an equality of the same form as the terminal constraint, so
    ``default_weights`` sizes it correctly with no extra tuning.
    """

    spacing: int
    banded: bool = False

    def _slots(self, problem: BatteryProblem) -> list[int]:
        """Interior slots ``t = k, 2k, … < T`` (``t = T`` is the terminal penalty)."""
        return list(range(self.spacing, problem.num_slots, self.spacing))

    def _band_weights(self, problem: BatteryProblem) -> list[int]:
        _, n_max, _ = soc_grid(problem)
        return bounded_int_weights(n_max - 2 * (self.spacing // 2))

    def validate(self, problem: BatteryProblem) -> None:
        if self.spacing < 1:
            raise ValueError(f"Checkpoint spacing must be >= 1, got {self.spacing}")
        _, n_max, k0 = soc_grid(problem)
        half = self.spacing // 2
        headroom = min(k0, n_max - k0)
        if half > headroom:
            raise ValueError(
                f"Checkpoint(spacing={self.spacing}) is unsound on this instance: "
                f"a gap of {self.spacing} slots admits excursions of {half} grid "
                f"steps, but S_0 (level {k0} of {n_max}) has only {headroom} steps "
                f"of headroom. Use spacing <= {max_sound_spacing(problem)}."
            )

    def aux_bits(self, problem: BatteryProblem) -> int:
        if not self.banded:
            return 0
        return len(self._slots(problem)) * len(self._band_weights(problem))

    def add_penalty(
        self, Q: np.ndarray, problem: BatteryProblem, weight: float, aux_base: int
    ) -> float:
        e, _, _ = soc_grid(problem)
        slots = self._slots(problem)
        offset = 0.0
        if not self.banded:
            # (S_t − S_0)²: the S_0 cancels out of the linear form, so const = 0.
            for t in slots:
                offset += add_squared(Q, soc_terms(problem, t - 1), 0.0, weight)
            return offset

        band_weights = self._band_weights(problem)
        b = len(band_weights)
        floor_level = e * (self.spacing // 2)
        for m, t in enumerate(slots):
            terms = soc_terms(problem, t - 1)
            terms += [(aux_base + m * b + k, -e * w) for k, w in enumerate(band_weights)]
            offset += add_squared(Q, terms, problem.initial_soc - floor_level, weight)
        return offset

    def slot_penalty(
        self, problem: BatteryProblem, weight: float, levels: np.ndarray
    ) -> np.ndarray:
        e, n_max, k0 = soc_grid(problem)
        pen = np.zeros((problem.num_slots - 1, len(levels)))
        half = self.spacing // 2
        width = n_max - 2 * half  # validate() guarantees this is >= 0
        for t in self._slots(problem):
            if self.banded:
                resid = clamp_dist(levels - half, 0, width)
            else:
                resid = levels - k0
            pen[t - 1] = weight * (e * resid) ** 2
        return pen

    def drift_spec(
        self, problem: BatteryProblem, weight: float
    ) -> tuple[int, float] | None:
        return None

    def aux_assignment(self, problem: BatteryProblem, levels: np.ndarray) -> np.ndarray:
        if not self.banded:
            return np.zeros(0, dtype=np.int8)
        _, n_max, _ = soc_grid(problem)
        w = self._band_weights(problem)
        half = self.spacing // 2
        width = n_max - 2 * half
        bits: list[int] = []
        for t in self._slots(problem):
            bits += encode_bounded(int(np.clip(levels[t - 1] - half, 0, width)), w)
        return np.array(bits, dtype=np.int8)


@dataclass(frozen=True)
class WindowDrift(_NoAuxDefaults):
    """Penalize net SoC drift within every window of ``window`` slots — ``0`` aux.

    ``μ · Σ_i (Σ_{t∈w_i} (c_t − d_t))²`` is the soft counterpart of
    :class:`Checkpoint`: ``μ → ∞`` approaches hard windowed pinning, ``μ → 0``
    approaches :class:`NoSoCBounds`. Unlike :class:`CenterAnchor` it is
    *duration-insensitive* — a long hold has zero drift in every interior window,
    so holding charge is free. Its cost is per action instead: an isolated charge
    appears in ``W`` windows and is tolled ``≈ μW``, while a bound-violating run
    of ``W`` same-direction actions is tolled ``≈ μW²``.

    Not sound: the argmin may be infeasible, and the toll can suppress marginal
    but profitable arbitrage. ``weight_scale`` multiplies ``weights.soc_bounds``
    and is the sweep knob; anchor the sweep where the toll first matches the best
    available arbitrage margin, ``μ ≈ (p_max − p_min)·e / W``.
    """

    window: int
    weight_scale: float = 1.0

    def validate(self, problem: BatteryProblem) -> None:  # noqa: D102 - overrides default
        if not 1 <= self.window <= problem.num_slots:
            raise ValueError(
                f"WindowDrift window must be in [1, T={problem.num_slots}], "
                f"got {self.window}"
            )

    def add_penalty(
        self, Q: np.ndarray, problem: BatteryProblem, weight: float, aux_base: int
    ) -> float:
        t = problem.num_slots
        e_c, e_d = problem.charge_energy, problem.discharge_energy
        w = weight * self.weight_scale
        offset = 0.0
        for i in range(t - self.window + 1):
            span = range(i, i + self.window)
            terms = [(j, e_c) for j in span] + [(t + j, -e_d) for j in span]
            offset += add_squared(Q, terms, 0.0, w)
        return offset

    def slot_penalty(
        self, problem: BatteryProblem, weight: float, levels: np.ndarray
    ) -> np.ndarray:
        return np.zeros((problem.num_slots - 1, len(levels)))

    def drift_spec(
        self, problem: BatteryProblem, weight: float
    ) -> tuple[int, float] | None:
        # penalty = w·(S_{i+W} − S_i)² = w·e²·(Δk)², so the DP scales (Δk)² by w·e².
        e, _, _ = soc_grid(problem)
        return self.window, weight * self.weight_scale * e * e


@dataclass(frozen=True)
class CenterAnchor(_NoAuxDefaults):
    """Pull every interior ``S_t`` toward the middle of the band — ``0`` aux.

    :class:`ExactSoC` with the slack *variable* replaced by a fixed target
    ``S_c = ⌊n_max/2⌋·e`` (floor, not :func:`round` — Python rounds halves to
    even, which is exactly the trap that put ``load_nrel_instance`` at 40% rather
    than 50% of capacity).

    Included as the obvious baseline, but expected to lose. Adding a charge at
    ``i`` and a discharge at ``j > i`` lifts ``S_t`` for all ``t ∈ [i, j)``, so
    the penalty grows with the *duration of the hold* — it taxes precisely the
    schedules that make money. Worse, the marginal penalty for stepping outward
    at offset ``δ`` is ``λe²(2δ+1)``, monotone in ``δ``, so any ``λ`` big enough
    to defend the band edge already distorts interior decisions: no separating
    weight exists. ``weight_scale`` is the sweep knob.
    """

    weight_scale: float = 1.0

    def add_penalty(
        self, Q: np.ndarray, problem: BatteryProblem, weight: float, aux_base: int
    ) -> float:
        e, n_max, _ = soc_grid(problem)
        center = e * (n_max // 2)
        w = weight * self.weight_scale
        offset = 0.0
        for j in range(problem.num_slots - 1):
            offset += add_squared(
                Q, soc_terms(problem, j), problem.initial_soc - center, w
            )
        return offset

    def slot_penalty(
        self, problem: BatteryProblem, weight: float, levels: np.ndarray
    ) -> np.ndarray:
        e, n_max, _ = soc_grid(problem)
        w = weight * self.weight_scale
        row = w * (e * (levels - n_max // 2)) ** 2
        return np.tile(row, (problem.num_slots - 1, 1))


@dataclass(frozen=True)
class NoSoCBounds(_NoAuxDefaults):
    """Drop the interior bounds entirely — ``0`` aux. The control arm.

    Objective, mutual exclusion, and the terminal constraint only. Expected to be
    near-uniformly infeasible: with nothing capping the excursion, the argmin
    charges in every cheap slot and discharges in every expensive one, limited
    only by ``Σc = Σd``. Its job is to fix the 0% end of the exactness axis and
    show the measurement has resolution.
    """

    def add_penalty(
        self, Q: np.ndarray, problem: BatteryProblem, weight: float, aux_base: int
    ) -> float:
        return 0.0

    def slot_penalty(
        self, problem: BatteryProblem, weight: float, levels: np.ndarray
    ) -> np.ndarray:
        return np.zeros((problem.num_slots - 1, len(levels)))


class Encoding:
    """Canonical SoC-bound encodings; see the module docstring for trade-offs."""

    EXACT: ClassVar[ExactSoC] = ExactSoC()
    NONE: ClassVar[NoSoCBounds] = NoSoCBounds()

    @staticmethod
    def checkpoint(spacing: int, *, banded: bool = False) -> Checkpoint:
        """Pin the SoC every ``spacing`` slots (see :func:`max_sound_spacing`)."""
        return Checkpoint(spacing=spacing, banded=banded)

    @staticmethod
    def window_drift(window: int, *, weight_scale: float = 1.0) -> WindowDrift:
        """Penalize net drift over every ``window``-slot span."""
        return WindowDrift(window=window, weight_scale=weight_scale)

    @staticmethod
    def center_anchor(*, weight_scale: float = 1.0) -> CenterAnchor:
        """Pull every interior ``S_t`` toward mid-band."""
        return CenterAnchor(weight_scale=weight_scale)
