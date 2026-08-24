"""The sizing tables in ``docs/results/capacity-rate-sensitivity.md``, pinned.

That document is hand-written: no script emits it, and the two scripts that mention
its path (``battery_sizing_study.py``, ``make_payback_figure.py``) only name it in
comments. So its tables are transcriptions of
``docs/results/capacity_rate_sensitivity.json``, and nothing was checking them --
three cells of the opening sweep table printed ``$1.94`` for a quantity the JSON
carries as ``1.9346`` and the document itself computes four lines below the table.
Fixed on 2026-08-23; this is the gate that keeps it fixed.

The sentence under that table claims the rule "reproduces all thirteen solved points
to the cent", which is exactly the property tested here, so a failure here means the
document is contradicting itself.

Nothing is retyped into this file. Every quantity comes from the document's own prose
or from the generated JSON, because retyping a number is the defect being guarded
against and a test that retypes it can agree with a wrong table.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "results" / "capacity-rate-sensitivity.md"
DATA = ROOT / "docs" / "results" / "capacity_rate_sensitivity.json"

TEXT = DOC.read_text()
STUDY = json.loads(DATA.read_text())

#: Prose claims are matched against this, not ``TEXT``: a sentence that reads as one
#: phrase in the rendered document can be split across a source line, and "all **56**
#: swept points" is in fact wrapped after "swept". Tables are matched line by line
#: against ``TEXT``, since a markdown row cannot wrap.
FLAT = " ".join(TEXT.split())

#: A dollar amount as the document prints it, e.g. ``**$1.93**`` or ``$2.42 (flat)``.
MONEY = re.compile(r"\$(\d+\.\d{2})\b")
NUMBER = re.compile(r"\d+(?:\.\d+)?")

#: Counts the document spells out in words rather than digits.
NUMBER_WORDS = {13: "thirteen"}


def markdown_table(header_contains: str) -> tuple[list[str], list[list[str]]]:
    """The header cells and body rows of the first table whose header matches.

    Cells are returned raw, still carrying ``**bold**`` and parentheticals like
    ``(flat)``; callers pull out the part they mean. The alignment row is skipped
    and the table ends at the first line that is not a row.
    """
    lines = TEXT.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and header_contains in line:
            header = [c.strip() for c in line.strip("|").split("|")]
            rows = []
            for row in lines[i + 2 :]:
                if not row.startswith("|"):
                    break
                rows.append([c.strip() for c in row.strip("|").split("|")])
            return header, rows
    raise AssertionError(f"no table whose header contains {header_contains!r} in {DOC}")


def numbers(cell: str) -> list[float]:
    return [float(n) for n in NUMBER.findall(cell)]


def money(cell: str) -> str:
    """The dollar figure in a cell, as printed, without the ``$``."""
    found = MONEY.findall(cell)
    assert len(found) == 1, f"expected exactly one dollar figure in {cell!r}"
    return found[0]


def to_the_cent(value: float) -> str:
    return f"{value:.2f}"


# --- constants, taken from the document and the study rather than retyped --------

#: The real tariff's peak window. The opening table is this window; the peak-window
#: sweep below varies it. Read from the document's own sentence so that changing the
#: claim without changing the tables fails here.
PEAK_HOURS = int(re.search(r"Colorado's (\d+)-hour block", FLAT).group(1))

SPREAD = STUDY["price_spread"]
SWEPT_RATE = STUDY["swept_at_rate_kw"]
SWEPT_CAPACITY = STUDY["swept_at_capacity_kwh"]

WINDOW = next(w for w in STUDY["windows"] if w["peak_hours"] == PEAK_HOURS)


def predicted(capacity: float, rate: float, peak_hours: int = PEAK_HOURS) -> float:
    """The rule the document states, in the document's own form.

    ``saving = min(capacity_kWh, rate_kW * peak_hours) * price_spread``
    """
    return min(capacity, rate * peak_hours) * SPREAD


def sweep_cells() -> list[tuple[str, float, float, str]]:
    """Every ``(half, capacity, rate, printed)`` cell of the opening sweep table.

    The table is two sweeps side by side with a spacer column: capacity at a fixed
    rating on the left, rating at a fixed capacity on the right. The fixed values are
    stated in the header ("@ 2 kW", "@ 10 kWh") and are checked against the study
    rather than assumed, since a re-run at a different fixed point would leave the
    header describing a sweep that no longer exists.
    """
    header, rows = markdown_table("capacity (kWh) @")
    fixed_rate = numbers(header[0])[-1]
    fixed_capacity = numbers(header[3])[-1]
    assert fixed_rate == SWEPT_RATE, "table header disagrees with swept_at_rate_kw"
    assert fixed_capacity == SWEPT_CAPACITY, (
        "table header disagrees with swept_at_capacity_kwh"
    )

    cells = []
    for row in rows:
        # One row can list several capacities sharing a saving ("10, 12, 16, 20").
        for capacity in numbers(row[0]):
            cells.append(("capacity", capacity, fixed_rate, money(row[1])))
        for rate in numbers(row[3]):
            cells.append(("rate", fixed_capacity, rate, money(row[4])))
    return cells


SWEEP_CELLS = sweep_cells()
SWEEP_IDS = [f"{half}-{cap:g}kWh-{rate:g}kW" for half, cap, rate, _ in SWEEP_CELLS]


@pytest.mark.parametrize("half,capacity,rate,printed", SWEEP_CELLS, ids=SWEEP_IDS)
def test_sweep_table_cell_matches_the_rule(half, capacity, rate, printed):
    """Each printed cell is the rule's value, rounded to the cent.

    This is the check that was missing: ``min(10, 2x4) * $0.24183 = $1.9346`` is
    ``$1.93``, and three cells printed ``$1.94``.
    """
    assert printed == to_the_cent(predicted(capacity, rate))


@pytest.mark.parametrize("half,capacity,rate,printed", SWEEP_CELLS, ids=SWEEP_IDS)
def test_sweep_table_cell_matches_the_solved_point(half, capacity, rate, printed):
    """Each printed cell is also the solved saving, not merely the rule's value.

    The rule and the solver agreeing is the document's claim; a table can satisfy the
    rule and still misreport what was solved, so both are pinned.
    """
    points = WINDOW["by_capacity" if half == "capacity" else "by_rate"]
    solved = [p for p in points if p["capacity"] == capacity and p["rate"] == rate]
    assert solved, f"no solved point at {capacity} kWh / {rate} kW in the study"
    assert printed == to_the_cent(solved[0]["saving"])


def test_the_solved_point_count_matches_the_claim():
    """"reproduces all thirteen solved points" counts the points actually tabled."""
    count = len(SWEEP_CELLS)
    word = NUMBER_WORDS.get(count, str(count))
    assert f"all {word} solved points" in FLAT, (
        f"the table lists {count} points; the sentence under it says otherwise"
    )


def window_ceiling_rows() -> list[tuple[int, float, float, str]]:
    """``(peak_hours, rate x hours, measured knee, printed ceiling)`` per window."""
    _, rows = markdown_table("| peak hours |")
    return [
        (int(numbers(row[0])[0]), numbers(row[2])[0], numbers(row[3])[0], money(row[4]))
        for row in rows
    ]


WINDOW_ROWS = window_ceiling_rows()


@pytest.mark.parametrize(
    "peak_hours,rate_times_hours,knee,printed",
    WINDOW_ROWS,
    ids=[f"{h}h" for h, _, _, _ in WINDOW_ROWS],
)
def test_peak_window_table_matches_the_rule(peak_hours, rate_times_hours, knee, printed):
    """The peak-window sweep's ceiling column is the same formula at another window.

    It carries the same $1.93 the opening table got wrong, so it is worth the same
    gate. The ceiling is the saving at saturation, where capacity no longer binds.
    """
    window = next(w for w in STUDY["windows"] if w["peak_hours"] == peak_hours)
    assert rate_times_hours == SWEPT_RATE * peak_hours
    assert knee == window["saturation_capacity_kwh"]
    assert printed == to_the_cent(predicted(rate_times_hours, SWEPT_RATE, peak_hours))
    assert printed == to_the_cent(window["daily_ceiling"])


def test_the_swept_point_count_matches_the_claim():
    """"all **56** swept points" is the study's own point count."""
    swept = sum(len(w["by_capacity"]) + len(w["by_rate"]) for w in STUDY["windows"])
    assert f"**{swept}** swept points" in FLAT
