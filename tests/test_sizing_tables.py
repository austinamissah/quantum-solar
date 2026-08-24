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

The payback and export-credit tables are covered too. Those carry the document's
actual conclusion, and two of their claims have already been retracted once -- the
lossless figures, and the *direction* in which a poor export credit moves the battery
leg. So the direction is pinned as a direction, not merely as digits: a retracted
claim quietly drifting back is the failure this half exists to catch.

Nothing is retyped into this file. Every quantity comes from the document's own prose
or from the generated JSON, because retyping a number is the defect being guarded
against and a test that retypes it can agree with a wrong table.

Two figures live in the prose alone and have no counterpart in the JSON: the lossless
2.5 kW saving, and the $56.9646/yr per kWh/day constant. Those are checked against the
document's own decomposition of them -- the only independent statement of either that
exists -- so that a figure and its derivation cannot drift apart unnoticed.
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

#: The document sets these properly; matching a plain hyphen would silently fail.
MINUS = "−"
EN_DASH = "–"
TIMES = "×"

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
    """Every number in a cell, with thousands separators removed first.

    The separator is stripped only between a digit and three following digits, so
    ``$11,500`` reads as one number while a comma-separated list of capacities
    (``10, 12, 16, 20``) still reads as four.
    """
    return [float(n) for n in NUMBER.findall(re.sub(r"(?<=\d),(?=\d{3}\b)", "", cell))]


def signed_money(cell: str) -> float | None:
    """A dollar amount carrying its sign, e.g. ``**−$113.93**`` or ``+$0.00/yr``.

    ``None`` where the document prints an em-dash, which it uses for "nothing to
    compare against" rather than for zero -- the two are different claims and the
    distinction is checked by the callers.
    """
    match = re.search(r"([-+]?)\$(\d+\.\d{2})", cell.replace(MINUS, "-"))
    return None if match is None else float(match.group(2)) * (
        -1 if match.group(1) == "-" else 1
    )


def signed_int(cell: str) -> int:
    return int(re.search(r"([-+]?\d+)", cell.replace(MINUS, "-")).group(1))


def signed_percent(cell: str) -> float | None:
    """A percentage as printed, or ``None`` where the document prints an em-dash.

    The document uses a real minus sign (U+2212), not a hyphen, so the sign is
    normalized before parsing rather than assumed.
    """
    match = re.search(r"(-?\d+(?:\.\d+)?)%", cell.replace(MINUS, "-"))
    return None if match is None else float(match.group(1))


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


# --- payback and the export credit ----------------------------------------------
#
# These tables carry the document's actual conclusion, and two of its claims have
# already been retracted once (see the retraction block in the document itself): the
# lossless figures, and the *direction* in which a poor export credit moves the
# battery leg. A retracted claim that drifts back is the failure mode worth gating,
# so the direction is pinned here and not merely the digits.

ANNUAL = STUDY["annual"]
WARRANTY = ANNUAL["warranty_years"]


def to_the_tenth(value: float) -> str:
    return f"{value:.1f}"


def payback_years(cost: float, savings: float) -> float:
    """Payback as the study computes it: cost over the annual saving, nothing else."""
    return cost / savings


def headline_cost(header_cell: str) -> float:
    """The install cost a "payback @ $11,500" column header names."""
    return numbers(header_cell)[-1]


def round_trip_rows() -> list[tuple[float, list[str], float]]:
    header, rows = markdown_table("| round trip |")
    return [(numbers(r[0])[0], r, headline_cost(header[3])) for r in rows]


ROUND_TRIP_ROWS = round_trip_rows()


@pytest.mark.parametrize(
    "round_trip,row,cost",
    ROUND_TRIP_ROWS,
    ids=[f"rt{rt:g}" for rt, _, _ in ROUND_TRIP_ROWS],
)
def test_round_trip_table_row(round_trip, row, cost):
    """Every column of the round-trip table, against the study and its own formula.

    The "vs lossless" column is recomputed rather than compared, because it is the
    one column with no counterpart in the JSON -- it is arithmetic the author did by
    hand, which is exactly where the sweep table went wrong.
    """
    point = next(p for p in ANNUAL["by_round_trip"] if p["round_trip"] == round_trip)
    savings = point["battery_savings"]

    assert money(row[1]) == to_the_cent(savings)

    lossless = ANNUAL["battery_savings_lossless"]
    printed_delta = signed_percent(row[2])
    if printed_delta is None:
        # The em-dash row is the lossless baseline, which has nothing to compare to.
        assert savings == lossless, "only the lossless row may print a dash"
    else:
        expected = (savings - lossless) / lossless * 100
        assert to_the_tenth(printed_delta) == to_the_tenth(expected)

    printed_payback = numbers(row[3])[0]
    assert to_the_tenth(printed_payback) == to_the_tenth(point["payback_years"][str(int(cost))])
    assert to_the_tenth(printed_payback) == to_the_tenth(payback_years(cost, savings))


def test_the_bolded_round_trip_row_is_the_headline():
    """The bolded row is the one the rest of the document quotes, not a stray."""
    bolded = [rt for rt, row, _ in ROUND_TRIP_ROWS if "**" in row[0]]
    assert bolded == [ANNUAL["round_trip_efficiency"]]
    assert f"**{WARRANTY} years**" in FLAT


def installed_cost_rows() -> list[tuple[float, list[str]]]:
    _, rows = markdown_table("| installed cost |")
    return [(numbers(r[0])[0], r) for r in rows]


INSTALLED_COST_ROWS = installed_cost_rows()


@pytest.mark.parametrize(
    "cost,row",
    INSTALLED_COST_ROWS,
    ids=[f"${c:g}" for c, _ in INSTALLED_COST_ROWS],
)
def test_installed_cost_table_row(cost, row):
    """Both payback columns, against the study and recomputed from the two savings.

    The 2 kW and 2.5 kW columns come from different annual savings, so recomputing
    them separately catches a column swap that matching the JSON alone would not.
    """
    point = next(p for p in ANNUAL["payback"] if p["installed_cost"] == cost)

    at_2kw, at_2p5kw = numbers(row[1])[0], numbers(row[2])[0]
    assert to_the_tenth(at_2kw) == to_the_tenth(point["years_at_2kw"])
    assert to_the_tenth(at_2p5kw) == to_the_tenth(point["years_at_2p5kw"])
    assert to_the_tenth(at_2kw) == to_the_tenth(
        payback_years(cost, ANNUAL["battery_savings_2kw"])
    )
    assert to_the_tenth(at_2p5kw) == to_the_tenth(
        payback_years(cost, ANNUAL["battery_savings_2p5kw"])
    )

    # The JSON's own within_warranty flag is about the 2 kW baseline; the table's
    # column is about either rating. Both are pinned, since the $5,000 row differs
    # between them and that row is the document's one interesting case.
    assert point["within_warranty"] == (point["years_at_2kw"] <= WARRANTY)
    either_clears = at_2kw <= WARRANTY or at_2p5kw <= WARRANTY
    assert either_clears == (row[3].strip().lower() != "no")


def test_only_one_install_clears_the_warranty():
    """"the single case that does" -- checked, not asserted."""
    clears = [
        (c, row)
        for c, row in INSTALLED_COST_ROWS
        if numbers(row[1])[0] <= WARRANTY or numbers(row[2])[0] <= WARRANTY
    ]
    assert len(clears) == 1, "the document claims exactly one install clears warranty"
    assert "the single case that does" in FLAT
    assert f"**{to_the_tenth(numbers(clears[0][1][2])[0])} years**" in FLAT


def export_rows() -> list[tuple[float, list[str], float]]:
    header, rows = markdown_table("| export credit |")
    return [(numbers(r[0])[0], r, headline_cost(header[3])) for r in rows]


EXPORT_ROWS = export_rows()


@pytest.mark.parametrize(
    "ratio,row,cost",
    EXPORT_ROWS,
    ids=[f"x{r:g}" for r, _, _ in EXPORT_ROWS],
)
def test_export_credit_table_row(ratio, row, cost):
    """Both legs and the payback, against the study and its own formula.

    Both legs are reported because they move in opposite directions and must never be
    summed; pinning them together keeps that pairing honest.
    """
    point = next(p for p in ANNUAL["by_export_ratio"] if p["export_ratio"] == ratio)

    assert money(row[1]) == to_the_cent(point["solar_savings"])
    assert money(row[2]) == to_the_cent(point["battery_savings"])

    printed_payback = numbers(row[3])[0]
    assert to_the_tenth(printed_payback) == to_the_tenth(point["payback_years"][str(int(cost))])
    assert to_the_tenth(printed_payback) == to_the_tenth(
        payback_years(cost, point["battery_savings"])
    )


def test_the_two_legs_move_in_opposite_directions():
    """The retracted claim, pinned as a direction rather than as digits.

    The document originally asserted that a worse export credit lengthens payback. It
    shortens it: a poor credit creates self-consumption value for the battery. That
    correction is the reason this section exists, so it is worth a gate that fails if
    the numbers ever drift back to telling the original story.
    """
    by_credit = sorted(ANNUAL["by_export_ratio"], key=lambda p: -p["export_ratio"])
    battery = [p["battery_savings"] for p in by_credit]
    solar = [p["solar_savings"] for p in by_credit]

    assert battery == sorted(battery), "a worse export credit must raise the battery leg"
    assert solar == sorted(solar, reverse=True), "and must lower the solar leg"


def test_the_payback_bracket_matches_the_export_sweep():
    """"[23.6, 28.4] years" is the range the sweep actually spans."""
    cost = EXPORT_ROWS[0][2]
    spans = [p["payback_years"][str(int(cost))] for p in ANNUAL["by_export_ratio"]]
    low, high = to_the_tenth(min(spans)), to_the_tenth(max(spans))

    assert f"**[{low}, {high}] years**" in FLAT
    assert f"**{low}{EN_DASH}{high} years**" in FLAT


def test_nothing_in_either_sweep_clears_the_warranty():
    """"none of it reaches the bar", cross-checked against the study's own flag."""
    for key in ("by_round_trip", "by_export_ratio"):
        for point in ANNUAL[key]:
            reached = [c for c, y in point["payback_years"].items() if y <= WARRANTY]
            assert not reached, f"{key} at {point} clears the warranty at {reached}"
            assert point["cheapest_within_warranty"] is None


# --- the annual upgrade table and the constant behind it -------------------------
#
# These two tables are the document's buying advice, and they are the one place where
# the numbers are not all in the JSON: the lossless 2.5 kW figure and the per-kWh/day
# constant appear in the prose alone. So they are checked against the decomposition
# the document itself gives, which is the only independent statement of them there is.

#: ``$56.9646 /yr per kWh/day``, the constant the document says generates the rest.
CONSTANT = float(re.search(r"\$(\d+\.\d{4}) /yr per kWh/day", FLAT).group(1))


def upgrade_rows() -> list[tuple[str, list[str]]]:
    _, rows = markdown_table("| upgrade from")
    return [(r[0], r) for r in rows]


UPGRADE_ROWS = upgrade_rows()

#: Which study field each row of the upgrade table reports. Structure, not data --
#: a renamed row fails here rather than being silently skipped.
UPGRADE_FIELDS = {
    "baseline": ("battery_savings_2kw", None),
    "rating": ("battery_savings_2p5kw", "rate_upgrade_gain"),
    "capacity": ("battery_savings_2kw", "capacity_upgrade_gain"),
}


@pytest.mark.parametrize(
    "label,row", UPGRADE_ROWS, ids=[l.split()[0] for l, _ in UPGRADE_ROWS]
)
def test_annual_upgrade_table_row(label, row):
    """Each row reports the study field it claims to, and its gain is that gain."""
    key = next((k for k in UPGRADE_FIELDS if label.lower().startswith(k)), None)
    assert key is not None, f"unrecognized upgrade row {label!r}"
    savings_field, gain_field = UPGRADE_FIELDS[key]

    assert money(row[1]) == to_the_cent(ANNUAL[savings_field])

    gain = signed_money(row[2])
    if gain_field is None:
        assert gain is None, "the baseline row has no gain to report"
    else:
        assert gain is not None and to_the_cent(gain) == to_the_cent(ANNUAL[gain_field])


def test_the_upgrade_gains_are_differences_from_the_baseline():
    """A gain column that does not equal its own row minus the baseline is wrong.

    Independent of the JSON's ``*_gain`` fields: this catches a gain that matches a
    stale field while disagreeing with the savings printed beside it.
    """
    baseline = money(UPGRADE_ROWS[0][1][1])
    for label, row in UPGRADE_ROWS[1:]:
        gain = signed_money(row[2])
        assert gain is not None, f"{label!r} should report a gain"
        expected = float(money(row[1])) - float(baseline)
        assert to_the_cent(gain) == to_the_cent(expected), label


def test_the_lossless_aside_is_consistent_with_the_table():
    """"Losslessly these were $455.72, $569.65 and +$113.93" -- all three checked.

    Only the first is in the JSON. The second is pinned as the first plus the third,
    and the third as two kWh/day of the constant, which is what makes the aside more
    than three numbers typed from memory.
    """
    aside = re.search(
        r"At the ([\d.]+) round trip\. Losslessly these were "
        r"\$([\d.]+), \$([\d.]+) and \+\$([\d.]+);",
        FLAT,
    )
    assert aside is not None, "the lossless aside has been reworded"
    round_trip, baseline, upgraded, gain = (float(g) for g in aside.groups())

    assert round_trip == ANNUAL["round_trip_efficiency"]
    assert to_the_cent(baseline) == to_the_cent(ANNUAL["battery_savings_lossless"])
    assert to_the_cent(upgraded) == to_the_cent(baseline + gain)
    assert to_the_cent(gain) == to_the_cent(2 * CONSTANT)


def test_the_asymmetry_is_unchanged_only_scaled():
    """The aside's own claim: losses scale both legs by the same factor.

    Compared at a tolerance rather than exactly, because every figure involved is
    already rounded to the cent; the point is that one ratio is the other, not that
    two rounded quotients agree to full precision.
    """
    lossless_gain = 2 * CONSTANT
    assert ANNUAL["rate_upgrade_gain"] / lossless_gain == pytest.approx(
        ANNUAL["battery_savings_2kw"] / ANNUAL["battery_savings_lossless"], rel=1e-3
    )


def test_the_constant_is_the_years_spreads_summed():
    """The constant is checked against the document's own decomposition of it.

    Nothing else states it: the JSON carries the summer spread, and the rest of the
    arithmetic lives only in this sentence. Checking it here is what stops the
    constant and its derivation from drifting apart.
    """
    parts = re.search(
        rf"(\d+) summer weekdays {TIMES} \$([\d.]+) \+ "
        rf"(\d+) winter weekdays {TIMES} \$([\d.]+) \+ "
        rf"(\d+) weekends {TIMES} \$(\d+)",
        FLAT,
    )
    assert parts is not None, "the decomposition sentence has been reworded"
    summer, summer_spread, winter, winter_spread, weekend, weekend_spread = (
        float(g) for g in parts.groups()
    )

    assert summer_spread == SPREAD, "the summer spread is the study's price_spread"
    assert summer + winter + weekend == 365, "the day counts must cover the year"
    total = summer * summer_spread + winter * winter_spread + weekend * weekend_spread
    assert f"{total:.4f}" == f"{CONSTANT:.4f}"


def multiplier_rows() -> list[tuple[str, int, float]]:
    _, rows = markdown_table("| change |")
    return [(r[0], signed_int(r[1]), signed_money(r[2])) for r in rows]


MULTIPLIER_ROWS = multiplier_rows()


@pytest.mark.parametrize(
    "label,delta,annual",
    MULTIPLIER_ROWS,
    ids=[f"delta{d:+d}" for _, d, _ in MULTIPLIER_ROWS],
)
def test_multiplier_table_row(label, delta, annual):
    """Each row is its own Δ times the constant, and its Δ is its own useful pair.

    The second half matters: a row can multiply correctly and still state a throughput
    change that its label contradicts, and the label is what a reader reasons from.
    """
    assert to_the_cent(annual) == to_the_cent(delta * CONSTANT)

    pair = re.search(r"useful (\d+) → (\d+)", label)
    if pair:
        before, after = (int(g) for g in pair.groups())
        assert delta == after - before, f"{label!r} contradicts its own Δ"
    elif "useful stays" in label:
        assert delta == 0, f"{label!r} says useful is unchanged but Δ is not zero"


def test_the_repeated_figure_is_flagged_as_an_identity():
    """The two rows sharing $113.93 are opposite moves of the same size.

    The document goes out of its way to say this is not a copy-paste, so the property
    that makes it not one is worth pinning: a future reader "fixing" one of the two is
    exactly the edit this catches.
    """
    magnitudes = [abs(a) for _, _, a in MULTIPLIER_ROWS]
    repeated = {m for m in magnitudes if magnitudes.count(m) > 1}
    assert len(repeated) == 1, "expected exactly one repeated figure in the table"

    figure = repeated.pop()
    sharing = [(d, a) for _, d, a in MULTIPLIER_ROWS if abs(a) == figure]
    assert {a > 0 for _, a in sharing} == {True, False}, "the two must have opposite signs"
    assert len({abs(d) for d, _ in sharing}) == 1, "and must move the same throughput"
    assert f"The repeated ${to_the_cent(figure)} is a real identity" in FLAT
