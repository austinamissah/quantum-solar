"""Published figures restated in code, pinned to the write-ups they came from.

The table gates over `docs/results/` catch a write-up disagreeing with its own data.
They do not catch the other direction: a measurement quoted in a comment, a docstring
or a module constant, drifting from the document it was copied out of. Nothing read
both, which is exactly how ``experiment_hardware.py`` came to justify its transpiler
default with a range its own write-up contradicts (fixed 2026-08-23).

Found by sweeping every comment and docstring under `scripts/` and `src/` for figures
that also appear in a write-up, then keeping the ones that are genuine restatements of
a measurement rather than incidental (day counts, seeds, shot budgets).

**Source files are parsed, never imported.** Several need qiskit, several run a sweep
on import, and the point is to read what the comment says, not what the module does.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from _markdown import markdown_table, numbers, rounding_interval, to_the_cent

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "quantum_solar" if (ROOT / "quantum_solar").is_dir() else ROOT / "src" / "quantum_solar"

LESSONS = (ROOT / "docs" / "LESSONS.md").read_text()
SIZING = (ROOT / "docs" / "results" / "capacity-rate-sensitivity.md").read_text()
BASIN = (ROOT / "docs" / "results" / "basin-structure.md").read_text()
ENCODING = (ROOT / "docs" / "results" / "slack-free-encoding.md").read_text()
STUDY_JSON = json.loads((ROOT / "docs" / "results" / "capacity_rate_sensitivity.json").read_text())


def source(relative: str) -> str:
    return (ROOT / relative).read_text()


# --- the July hardware circuits, quoted in three files ---------------------------


def lessons_degradation_table() -> list[tuple[int, int, float]]:
    """LESSONS §2's own table: (qubits, 2-qubit gates, TVD). The authority here."""
    _, rows = markdown_table(LESSONS, "| circuit | qubits | 2-qubit gates |")
    return [
        (int(numbers(row[1])[0]), int(numbers(row[2])[0]), numbers(row[3])[0])
        for row in rows
    ]


LESSONS_ROWS = lessons_degradation_table()
JULY_GATES = [g for _, g, _ in LESSONS_ROWS]
JULY_TVDS = [t for _, _, t in LESSONS_ROWS]


def test_the_lessons_table_was_parsed_as_expected():
    """Guard the guard: a mis-parsed source table would make every check below vacuous."""
    assert len(LESSONS_ROWS) == 4
    assert JULY_GATES == sorted(JULY_GATES), "the table is ordered by gate count"
    assert JULY_TVDS == sorted(JULY_TVDS), "and degradation rises with it, which is §2"


@pytest.mark.parametrize(
    "relative",
    ["scripts/encoding_study.py", "scripts/experiment_hardware.py"],
    ids=["encoding_study", "experiment_hardware"],
)
def test_the_july_gate_counts_quoted_in_code(relative):
    """"37/77/124/290" in a comment must be LESSONS §2's gate column."""
    quoted = re.search(r"(\d+(?:/\d+){3}) gates|circuits: (\d+(?:/\d+){3})", source(relative))
    assert quoted, f"{relative} no longer quotes the July gate counts"
    counts = [int(n) for n in (quoted.group(1) or quoted.group(2)).split("/")]
    assert counts == JULY_GATES


@pytest.mark.parametrize(
    "relative",
    ["scripts/encoding_study.py", "scripts/experiment_hardware.py"],
    ids=["encoding_study", "experiment_hardware"],
)
def test_the_july_degradation_quoted_in_code(relative):
    """"0.119/0.203/0.383/0.459" in a comment must be LESSONS §2's TVD column.

    Both files use it for the same argument -- that device-noise TVD tracks gate
    count monotonically -- so a drift here would leave a live justification resting
    on numbers the write-up no longer reports.
    """
    quoted = re.search(r"(0\.\d+(?:/0\.\d+){3})", source(relative))
    assert quoted, f"{relative} no longer quotes the July degradation figures"
    values = [float(n) for n in quoted.group(1).split("/")]
    assert [f"{v:.3f}" for v in values] == [f"{t:.3f}" for t in JULY_TVDS]


def test_the_figure_scripts_circuit_table_matches_lessons():
    """`make_gates_vs_qubits_figure.CIRCUITS` restates LESSONS §2 as a constant.

    The script refuses to draw if it cannot reproduce these, which is a good gate --
    but it only runs when the figure is regenerated. This puts the same comparison in
    the suite, where a LESSONS edit is caught the same day rather than at the next
    redraw.

    Its ``gates`` column is also the write-up's level-1 transpiler column, so this
    ties three files to one set of numbers.
    """
    tree = ast.parse(source("scripts/make_gates_vs_qubits_figure.py"))
    circuits = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", None) == "CIRCUITS" for t in node.targets)
    )
    records = ast.literal_eval(circuits)

    assert [r["gates"] for r in records] == JULY_GATES
    assert [f"{r['published']:.3f}" for r in records] == [f"{t:.3f}" for t in JULY_TVDS]
    assert [r["qubits"] for r in records] == [q for q, _, _ in LESSONS_ROWS]

    _, transpiler = markdown_table(ENCODING, "| 2Q at o1 (July) |")
    assert [int(numbers(row[1])[0]) for row in transpiler] == JULY_GATES


def test_the_derived_depth_gap_in_the_encoding_study_docstring():
    """"the two 6-qubit circuits differ by 0.084 TVD from depth alone" -- recomputed."""
    stated = float(re.search(r"differ by ([\d.]+) TVD from depth alone", source("scripts/encoding_study.py")).group(1))
    six_qubit = sorted(t for q, _, t in LESSONS_ROWS if q == 6)
    assert len(six_qubit) == 2, "the claim is about exactly the two 6-qubit circuits"
    assert f"{six_qubit[1] - six_qubit[0]:.3f}" == f"{stated:.3f}"


# --- the tariff, quoted in the loader --------------------------------------------


def test_the_tariff_prices_in_the_loader_match_the_committed_study():
    """`nrel.py` documents the Golden CO rate; the sizing study computes on it.

    The loader's comment is what a reader checks a suspicious bill against, and the
    study's spread is what every dollar figure in the repo is built from. They are the
    same tariff and are quoted to different precision, so each is checked against the
    other's rounding interval rather than for equality.
    """
    text = source("src/quantum_solar/data/nrel.py")
    off_peak = re.search(r"off-peak ~\$([\d.]+)/kWh", text).group(1)
    on_peak = re.search(r"~\$([\d.]+)/kWh \(", text).group(1)

    committed_off = STUDY_JSON["off_peak_price"]
    committed_on = committed_off + STUDY_JSON["price_spread"]

    for quoted, committed, label in [
        (off_peak, committed_off, "off-peak"),
        (on_peak, committed_on, "on-peak"),
    ]:
        low, high = rounding_interval(quoted)
        assert low <= committed <= high, f"{label}: {quoted} vs committed {committed}"


def test_the_peak_window_in_the_loader_matches_the_study():
    """The comment's 17:00-21:00 must be the four-hour window the rule is built on."""
    start, end = (
        int(g) for g in re.search(r"\((\d+):00-(\d+):00\)", source("src/quantum_solar/data/nrel.py")).groups()
    )
    hours = int(re.search(r"Colorado's (\d+)-hour block", SIZING).group(1))
    assert end - start == hours


# --- the constant, quoted in the sizing figure -----------------------------------


def test_the_sizing_figure_docstring_restates_the_multiplier_table():
    """The docstring lists four headline figures as multiples of one constant.

    Those four are the sibling document's multiplier table. The docstring is where a
    maintainer learns why the figure is drawn lossless, so it carrying a stale
    multiplier would mislead exactly the person about to change the figure.
    """
    text = source("scripts/make_sizing_figure.py")
    constant = float(re.search(r"\$(\d+\.\d{4})/yr per kWh/day", text).group(1))

    document_constant = float(re.search(r"\$(\d+\.\d{4}) /yr per kWh/day", SIZING).group(1))
    assert f"{constant:.4f}" == f"{document_constant:.4f}"

    quoted = {m for m in re.findall(r"[-+]?\$\d+\.\d{2}(?![\d])", text)}
    _, rows = markdown_table(SIZING, "| change | Δ useful kWh/day |")
    tabled = set()
    for row in rows:
        value = re.search(r"([-+]?)\$(\d+\.\d{2})", row[2].replace("−", "-"))
        sign = "-" if value.group(1) == "-" else ("+" if float(value.group(2)) else "")
        tabled.add(f"{sign}${value.group(2)}")

    # Every signed figure the docstring quotes must be one the table reports.
    signed = {q for q in quoted if q[0] in "+-"}
    assert signed, "the docstring is supposed to quote the signed multiplier figures"
    assert signed <= tabled, f"{signed - tabled} is not in the multiplier table"


def test_the_lossless_to_round_trip_multiplier_in_the_sizing_figure():
    """"At the 0.90 round trip the multiplier scales down (to $50.5346)" -- recomputed.

    This figure appears nowhere else in the repo, so it has no document to drift from
    and is instead checked against the annual savings it is derived from.
    """
    text = source("scripts/make_sizing_figure.py")
    constant = float(re.search(r"\$(\d+\.\d{4})/yr per kWh/day", text).group(1))
    scaled = float(re.search(r"scales down\s*#?\s*\n?.*?\(to \$(\d+\.\d{4})\)", text, re.S).group(1))

    annual = STUDY_JSON["annual"]
    expected = constant * annual["battery_savings_2kw"] / annual["battery_savings_lossless"]
    assert f"{expected:.4f}" == f"{scaled:.4f}"

    knee = int(re.search(r"it is (\d+) kWh either way", text).group(1))
    window = next(w for w in STUDY_JSON["windows"] if w["peak_hours"] == 4)
    assert knee == window["saturation_capacity_kwh"]


# --- the pre-registered bar and the basin window ---------------------------------


def test_the_bar_quoted_in_the_optimizer_scripts():
    """`5 x uniform at m=6 = 0.078125` in code must be that, exactly.

    The bar is pre-registered. A drifted copy in a script is how a study silently
    starts measuring against a different threshold than the one it committed to.
    """
    text = source("scripts/optimizer_study.py")
    factor, qubits, bar = (
        re.search(r"(\d+) x uniform at m=(\d+) = ([\d.]+)", text).groups()
    )
    assert float(bar) == int(factor) / 2 ** int(qubits)
    assert f"required {bar}" in ENCODING.replace("**", "") or bar in ENCODING


def test_the_basin_window_quoted_in_its_figure_script():
    """`make_basin_figure.py` states the usable window; the study defines it."""
    text = source("scripts/make_basin_figure.py")
    low, high = (
        float(g)
        for g in re.search(
            r"encoding breaks below ([\d.]+), reproducibility breaks above ([\d.]+)", text
        ).groups()
    )
    document_low, document_high = (
        float(g)
        for g in re.search(r"usable window on this instance is ([\d.]+) ≤ α ≤ ([\d.]+)", BASIN).groups()
    )
    assert (low, high) == (document_low, document_high)
