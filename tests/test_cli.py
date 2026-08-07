"""The ``python -m quantum_solar`` demo.

Two things are worth testing here and one of them is not the formatting.

The first is that the CLI runs **offline** — no network, no API key, no warm
cache. That is the whole reason it exists: ``data/cache/`` is gitignored, so on a
fresh clone the real-data half of the notebook cannot run at all.

The second is that its numbers are the README's numbers. The CLI is a second
audience for figures the README quotes in prose, and two renderings of one
quantity drift. Pinning them here means a change to the model that moves the
annual split fails a test instead of silently disagreeing with the front page.
"""

from __future__ import annotations

import numpy as np
import pytest

from quantum_solar.__main__ import (
    WIDTH,
    _annual,
    _bar,
    _forced_runs,
    _load_snapshot,
    build_parser,
    main,
)


@pytest.fixture(scope="module")
def snapshot():
    return _load_snapshot()


# --- offline, and the README's numbers ---------------------------------------


def test_runs_without_network_or_api_key(monkeypatch, capsys):
    """No socket, no NREL_API_KEY, no cache. It must still produce the demo."""
    import socket

    def no_network(*args, **kwargs):
        raise AssertionError("the CLI made a network call")

    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.delenv("NREL_API_KEY", raising=False)

    assert main(["--day-only"]) == 0
    out = capsys.readouterr().out
    assert "no network, no API key" in out
    assert "ONE DAY" in out


@pytest.mark.parametrize("round_trip,export_ratio,expected", [
    # (no_system, solar_only, optimized, solar_savings, battery_savings)
    # Every figure below is measured, not derived. The README states the anchors
    # marked; the remaining components are pinned from the same run so the whole
    # split is locked rather than just the two numbers that got published.
    (1.00, 1.00, (1747.83, 777.22, 321.50, 970.61, 455.72)),    # README: the table
    (0.90, 1.00, (1747.83, 777.22, 372.94, 970.61, 404.28)),    # README: battery $404.28
    (0.90, 0.10, (1747.83, 1178.69, 691.75, 569.14, 486.94)),   # README: battery $486.94
    (1.00, 0.10, (1747.83, 1178.69, 670.06, 569.14, 508.62)),   # README: solar $569.14
])
def test_annual_split_matches_the_readme(snapshot, round_trip, export_ratio, expected):
    """The three-way split the README quotes, recomputed from committed data."""
    _snap, generation, price_for = snapshot
    result = _annual(generation, price_for, capacity=10.0, rate=2.0,
                     round_trip=round_trip, export_ratio=export_ratio)
    got = (result.no_system_cost, result.solar_only_cost, result.optimized_cost,
           result.solar_savings, result.battery_savings)
    assert got == pytest.approx(expected, abs=0.01)


def test_battery_and_solar_legs_move_in_opposite_directions(snapshot):
    """Why the CLI refuses to add them, asserted rather than only asserted in prose."""
    _snap, generation, price_for = snapshot
    kw = dict(capacity=10.0, rate=2.0, round_trip=0.90)
    retail = _annual(generation, price_for, export_ratio=1.0, **kw)
    poor = _annual(generation, price_for, export_ratio=0.10, **kw)

    assert poor.solar_savings < retail.solar_savings      # a poor credit hurts solar
    assert poor.battery_savings > retail.battery_savings  # and helps the battery


# --- the sizing rule, and the regime where it stops holding -------------------


def test_sizing_knee_is_unmoved_by_losses(snapshot):
    """Losses change the multiplier, not the knee: 8 kWh either way at 2 kW."""
    _snap, generation, price_for = snapshot

    def knee(round_trip):
        savings = {c: _annual(generation, price_for, capacity=c, rate=2.0,
                              round_trip=round_trip, export_ratio=1.0).battery_savings
                   for c in (2.0, 4.0, 6.0, 8.0, 10.0, 20.0)}
        ceiling = max(savings.values())
        return min(c for c, s in savings.items() if abs(s - ceiling) < 0.005)

    assert knee(1.0) == 8.0
    assert knee(0.90) == 8.0


@pytest.mark.parametrize("capacity,rate,useful", [
    (2.0, 2.0, 2.0), (4.0, 2.0, 4.0), (6.0, 2.0, 6.0), (8.0, 2.0, 8.0),
    (10.0, 2.0, 8.0),    # capacity-bound: the pack is bigger than the window allows
    (10.0, 0.5, 2.0), (10.0, 1.0, 4.0), (10.0, 2.5, 10.0),   # rate-bound
])
def test_annual_value_is_exactly_linear_in_peak_throughput(snapshot, capacity, rate, useful):
    """$56.9646/yr per kWh/day of peak-window throughput, on both sides of the knee.

    This constant is why $113.93 shows up twice in the docs for unrelated changes —
    a 2 → 2.5 kW inverter upgrade and the last four qubits of the `cp5band`
    encoding. Both move 2 kWh/day of peak throughput, so both come to 2 × 56.9646.
    It reads exactly like a copy-paste and is not one; pinning the constant here
    keeps it that way. See docs/results/capacity-rate-sensitivity.md.
    """
    _snap, generation, price_for = snapshot
    savings = _annual(generation, price_for, capacity=capacity, rate=rate,
                      round_trip=1.0, export_ratio=1.0).battery_savings
    assert savings / useful == pytest.approx(56.9646, abs=1e-4)


def test_the_repeated_113_93_is_two_kwh_per_day(snapshot):
    """The rate upgrade and the four-qubit encoding step are the same 2 kWh/day."""
    _snap, generation, price_for = snapshot

    def battery(capacity, rate):
        return _annual(generation, price_for, capacity=capacity, rate=rate,
                       round_trip=1.0, export_ratio=1.0).battery_savings

    # 2 -> 2.5 kW moves useful throughput 8 -> 10 kWh/day.
    assert battery(10.0, 2.5) - battery(10.0, 2.0) == pytest.approx(113.93, abs=0.01)
    # cp5 delivers 6 of 8 useful kWh/day; the shortfall is the same 2 kWh/day.
    # (The encoding arm itself is priced in scripts/annual_encoding_cost.py, which
    # runs qubo_min_exact over the year; here we pin only the throughput identity.)
    assert battery(8.0, 2.0) - battery(6.0, 2.0) == pytest.approx(113.93, abs=0.01)


def test_sizing_narrative_is_suppressed_when_the_rule_does_not_apply(capsys):
    """Below-retail export breaks the rule, so the CLI must not narrate it.

    Under net metering the capacity column flattens at the knee. Paying less for
    exports than imports couples the plan to solar and load, the knee stops
    existing, and printing "rate is the axis that pays" over those numbers would
    be a confidently wrong claim.
    """
    main(["--export-ratio", "0.25"])
    out = capsys.readouterr().out
    assert "does not apply" in out
    assert "Rate is the axis that pays" not in out

    main([])
    out = capsys.readouterr().out
    assert "Rate is the axis that pays" in out
    assert "flattens at 8 kWh" in out


# --- reporting obligations the repo cares about -------------------------------


def test_reports_forced_hours_and_the_tie_count(capsys):
    """Never present one tied optimum as the answer without saying so."""
    main(["--day", "192", "--day-only"])
    out = capsys.readouterr().out

    assert "17:00–20:00 discharge" in out   # the forced window, collapsed to a run
    assert "2,448 minimal-cost plans tie" in out
    assert "one arbitrary pick" in out
    # The net-metering separability caveat travels with the plan, not a footnote.
    assert "depends on the PRICE curve alone" in out


def test_a_flat_price_day_is_reported_as_unique_and_idle(capsys):
    """The weekend tariff is flat, so idling is optimal and it is the ONLY optimum."""
    main(["--day", "194", "--day-only"])
    out = capsys.readouterr().out

    assert "flat all day" in out
    assert "exactly one minimal-cost plan" in out
    assert "00:00–23:00 idle" in out
    assert "battery saves $0.00" in out


def test_forced_runs_collapses_consecutive_hours():
    assert _forced_runs({17: "discharge", 18: "discharge", 19: "discharge"}) \
        == ["17:00–19:00 discharge"]
    assert _forced_runs({0: "charge", 3: "charge"}) == ["00:00 charge", "03:00 charge"]
    # A run must not span an action change.
    assert _forced_runs({1: "charge", 2: "discharge"}) \
        == ["01:00 charge", "02:00 discharge"]


def test_flat_series_is_not_stretched_into_fake_structure():
    """A constant renders flat. Auto-scaling one onto its own noise once made a
    constant price look like a signal in a committed figure (LESSONS.md §6)."""
    assert len(set(_bar(np.full(24, 0.139), 0.139, 0.139))) == 1
    assert len(set(_bar(np.linspace(0, 1, 24), 0.0, 1.0))) > 1


# --- argument handling --------------------------------------------------------


@pytest.mark.parametrize("argv,message", [
    (["--day", "365"], "0..364"),
    (["--day", "-1"], "0..364"),
    (["--round-trip", "1.5"], "round-trip"),
    (["--round-trip", "0"], "round-trip"),
    (["--export-ratio", "2"], "export-ratio"),
])
def test_rejects_out_of_range_arguments(argv, message):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert message in str(exc.value)


def test_off_grid_capacity_is_refused_with_guidance():
    """`require_soc_on_grid` rejects a capacity the rate does not divide; the CLI
    must turn that into an instruction rather than a traceback."""
    with pytest.raises(SystemExit) as exc:
        main(["--capacity", "7", "--rate", "2", "--day-only"])
    assert "divides --capacity" in str(exc.value)


# --- the --quantum opt-in path ------------------------------------------------
#
# Opt-in paths rot silently: a flag the default run skips is untested by default,
# and "the suite is green" says nothing about it (LESSONS.md §7, checklist item 8).
# So both branches are covered, and the working one at the size it actually runs.


@pytest.mark.slow
def test_quantum_section_agrees_with_the_exact_solvers(capsys):
    """QAOA must recover the exact optimum, and alpha* must beat the default weight.

    Run at the real size the flag uses (a 2-slot instance at reps=2), not a
    smaller stand-in: a test that calls the right function at the wrong size is
    not coverage of the size that matters.
    """
    pytest.importorskip("qiskit_aer")

    main(["--day-only", "--quantum"])
    out = capsys.readouterr().out

    assert "QUANTUM" in out
    # All four solvers agree on the cost; the penalty weight moves the probability.
    costs = [line for line in out.splitlines()
             if line.strip().startswith(("exact DP", "brute force", "QAOA @"))]
    assert len(costs) == 4, out
    assert all("$0.22" in line for line in costs), costs

    masses = [float(line.split("P(optimal) = ")[1].split()[0])
              for line in costs if "P(optimal)" in line]
    default_mass, alphastar_mass = masses
    assert alphastar_mass > 50 * default_mass, (default_mass, alphastar_mass)
    # Below uniform at the default weight, well above it at alpha*.
    assert default_mass * 64 < 1.0 < alphastar_mass * 64


def test_quantum_section_degrades_gracefully_without_qiskit(monkeypatch, capsys):
    """A numpy-only user gets an instruction, not an ImportError traceback.

    Blocks qiskit at the import machinery, the same way
    ``tests/test_optional_qiskit.py`` does — checking this in an environment where
    qiskit happens to be installed would prove nothing.
    """
    import sys

    import quantum_solar.__main__ as cli

    blocked_roots = {"qiskit", "qiskit_aer", "qiskit_ibm_runtime"}

    class _BlockQiskit:
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked_roots:
                raise ImportError(f"blocked for test: {fullname}")
            return None  # defer to the rest of sys.meta_path

    for name in list(sys.modules):
        if name.split(".")[0] in blocked_roots or name in {"quantum_solar.ising",
                                                           "quantum_solar.qaoa"}:
            monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "meta_path", [_BlockQiskit(), *sys.meta_path])

    cli.show_quantum(seed=0)

    out = capsys.readouterr().out
    assert "pip install -r requirements.txt" in out
    assert "blocked for test" in out   # the real cause is shown, not swallowed


def test_lossless_payback_signposts_the_loss_adjusted_headline(capsys):
    """The default is lossless, but readers arrive holding the 0.90 figure.

    The demo's defaults give ~25 years and the README and write-ups lead with ~28,
    bracketed [23.6, 28.4]. Both are correct for their own regime, so the default
    run has to name the other one or the difference reads as a discrepancy. The
    flag it points at must actually produce the number it quotes.
    """
    main([])
    out = capsys.readouterr().out
    assert "= 25 years" in out
    assert "~28 years at a 0.90 round trip" in out
    assert "[23.6, 28.4]" in out
    assert "--round-trip 0.90" in out

    main(["--round-trip", "0.90"])
    out = capsys.readouterr().out
    assert "= 28 years" in out          # the signpost's promise, kept
    assert "Elsewhere the headline" not in out   # and withdrawn once it is moot


@pytest.mark.parametrize("argv", [
    [],                                                   # the full default run
    ["--round-trip", "0.90", "--export-ratio", "0.25"],   # the widest prose block
    ["--day", "194", "--day-only"],                       # the all-forced flat day
])
def test_output_fits_a_standard_terminal(argv, capsys):
    """No line wraps at WIDTH columns, in any section.

    The demo is meant to be read in a terminal and recorded, and one wrapped line
    ruins both. Two lines used to overflow: the header when the loss/export labels
    are spelled out, and the forced-hours list on a day where most hours are
    forced.
    """
    main(argv)
    too_wide = [line for line in capsys.readouterr().out.splitlines()
                if len(line) > WIDTH]
    assert not too_wide, too_wide


def test_parser_documents_every_knob():
    """Each flag the demo advertises has help text, so `--help` is the manual."""
    for action in build_parser()._actions:
        assert action.help, f"{action.dest} has no help text"
