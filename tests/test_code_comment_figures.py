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
ARCHITECTURE = (ROOT / "docs" / "ARCHITECTURE.md").read_text()
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


# --- executable constants: the code is the enforcement point ---------------------
#
# The checks above cover figures a comment *describes*. These cover values the code
# *acts on* -- a threshold, a seed budget, a warranty term -- where a write-up states
# the same number as pinned or registered. Drift matters in both directions here: a
# study whose script no longer uses the weight its write-up names is not the study
# that was published, and a document naming a threshold the code has moved past is
# describing something that no longer runs.
#
# Ordinary parameters are deliberately out of scope. Most numeric defaults in this
# repo (``capacity=10.0``, ``charge_energy=2.0``) appear in the write-ups only because
# the write-ups describe the instance; the code is their source, so there is nothing
# for them to drift from.


def module_constants(relative: str) -> dict:
    """Module-level literal assignments, without importing the module."""
    found = {}
    for node in ast.parse(source(relative)).body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = ast.literal_eval(node.value)
        except Exception:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                found[target.id] = value
            elif isinstance(target, ast.Tuple) and isinstance(value, tuple):
                for element, item in zip(target.elts, value):
                    if isinstance(element, ast.Name):
                        found[element.id] = item
    return found


BASIN_JSON = json.loads((ROOT / "docs" / "results" / "basin_study.json").read_text())


def test_the_two_alpha_star_constants_are_different_on_purpose():
    """`basin_study.ALPHA_STAR` is 0.021; `make_basin_figure.ALPHA_STAR` is 0.0209.

    They are not the same quantity and must not be reconciled. 0.0209 is the a-priori
    rule, span/penalty; 0.021 is the ladder rung the hardware runs actually used and
    the study anchors on. Both appear in the write-ups, one line apart in places, so
    a well-meaning "fix" that harmonizes them is a real risk -- and it would silently
    re-anchor either the study or the figure.
    """
    study = module_constants("scripts/basin_study.py")["ALPHA_STAR"]
    figure = module_constants("scripts/make_basin_figure.py")["ALPHA_STAR"]

    assert study == BASIN_JSON["alpha_star"], "the study must use its artifact's anchor"
    document = float(
        re.search(r"\(objective span\) / \(default penalty\) = ([\d.]+)", ENCODING).group(1)
    )
    assert figure == document, "the figure must use the a-priori threshold"
    assert study != figure, "these are different quantities; harmonizing them is the bug"


def test_the_basin_study_constants_match_its_own_artifact():
    """Seed budgets, resamples and solver settings, against `basin_study.json`.

    The JSON is what the write-up reports; these constants are what would produce it
    on a re-run. If they part company the study is no longer reproducible from its
    own script, which is the one property a pre-registered sweep has to keep.
    """
    constants = module_constants("scripts/basin_study.py")
    assert constants["HEADLINE_N"] == BASIN_JSON["headline_N"]
    assert list(constants["REPORT_N"]) == BASIN_JSON["report_N"]
    assert constants["TAU_RESAMPLES"] == BASIN_JSON["tau_resamples"]

    solver = BASIN_JSON["solver"]
    assert constants["SHOTS"] == solver["shots"]
    assert constants["N_STARTS"] == solver["n_starts"]
    assert constants["MAXITER"] == solver["maxiter"]
    assert constants["REPS"] == solver["reps"]


def test_the_warranty_term_is_one_number_in_three_places():
    """The 10-year warranty is the bar the whole payback conclusion is measured against.

    It is stated in the sizing study, in the CLI that prints a payback verdict, and in
    the committed JSON. A drift in the CLI alone would have it telling a user a
    different story than the write-up.
    """
    study = module_constants("scripts/battery_sizing_study.py")["WARRANTY_YEARS"]
    cli = module_constants("src/quantum_solar/__main__.py")["WARRANTY_YEARS"]
    committed = STUDY_JSON["annual"]["warranty_years"]

    assert study == cli == committed
    assert f"**{committed} years**" in SIZING


def test_the_headline_round_trip_is_one_number():
    """0.90 is the regime every current dollar figure is quoted in.

    Two scripts name it and the JSON records it. The figure script's copy is the one
    that decides which regime gets drawn, so it drifting would mislabel a chart rather
    than fail loudly.
    """
    study = module_constants("scripts/battery_sizing_study.py")["HEADLINE_ROUND_TRIP"]
    figure = module_constants("scripts/make_payback_figure.py")["EXPECTED_ROUND_TRIP"]
    assert study == figure == STUDY_JSON["annual"]["round_trip_efficiency"]


def test_the_cheapest_install_the_figure_calls_out():
    """`make_payback_figure.CHEAPEST` must be the cheapest install the study prices."""
    cheapest = module_constants("scripts/make_payback_figure.py")["CHEAPEST"]
    assert cheapest == min(p["installed_cost"] for p in STUDY_JSON["annual"]["payback"])


def test_the_peak_window_end_hour_matches_the_construction_note():
    """The sweep grows the window backward from a fixed end hour; both name hour 20.

    The write-up explains that growing it forward would eat the refill hours and bind
    instead of the rule under test, so this constant is load-bearing for the result.
    """
    end = module_constants("scripts/battery_sizing_study.py")["PEAK_END"]
    assert f"window *ends* at hour {end}" in SIZING


def test_the_reliability_rule_is_the_scripts_own():
    """PASS+RELIABLE is `RELIABLE_FRACTION` of the seeds, not a threshold read off.

    The code says 0.8, i.e. >= 8/10. The published table happens to show 9, 9, 10 and
    7, which is equally consistent with a >= 9 rule -- so reading the rule off the
    table gives a plausible wrong answer. Taken from the script instead.
    """
    constants = module_constants("scripts/optimizer_study.py")
    fraction = constants["RELIABLE_FRACTION"]

    _, rows = markdown_table(ENCODING, "| instance | α | best arm |")
    for row in rows:
        clears, total = (int(n) for n in numbers(row[4])[:2])
        verdict = row[5].strip("*")
        assert ("RELIABLE" in verdict) == (clears >= fraction * total), row[0]


def test_the_spsa_budget_matches_its_published_eval_count():
    """SPSA evaluates twice per iteration, so its arm-table cost is 2 x SPSA_ITERS."""
    iterations = module_constants("scripts/optimizer_study.py")["SPSA_ITERS"]
    _, rows = markdown_table(ENCODING, "| arm | mean (α=0.021) |")
    published = next(numbers(row[3])[0] for row in rows if row[0].strip("`") == "spsa")
    assert published == 2 * iterations


def test_the_committed_instance_day_matches_the_write_up():
    """"AMY-2018 day 192" must be the day the committed schedule actually holds.

    The loader's ``day=172`` default is not this number and is not meant to be -- the
    committed instance passes its day explicitly -- so the check is against the
    artifact, not the default.
    """
    snapshot = json.loads((ROOT / "docs" / "figures" / "web" / "schedule_real_day.json").read_text())
    day = snapshot["buckets"]["summer_weekday"]["day"]
    year = module_constants("src/quantum_solar/data/calendar.py")["AMY_YEAR"]
    assert f"AMY-{year} day {day}" in SIZING


@pytest.mark.parametrize(
    "relative,name",
    [
        ("src/quantum_solar/brute_force.py", "MAX_ENUMERATION_SITES"),
        ("src/quantum_solar/problem.py", "MAX_SOC_LEVELS"),
    ],
    ids=["enumeration-sites", "soc-levels"],
)
def test_the_refusal_ceilings_architecture_quotes(relative, name):
    """`ARCHITECTURE.md` names both refusal ceilings with their values in brackets.

    These are guards, not preferences: one keeps brute force from being asked for an
    intractable enumeration, the other rejects an off-grid rate rather than silently
    rounding it -- a defect this repo actually shipped once, a 10 kWh battery quietly
    becoming 12. A document quoting a ceiling the code has moved past would send a
    reader looking for the wrong failure.
    """
    value = module_constants(relative)[name]
    # The opening backtick is dropped from the match: one of the two is written
    # ``> MAX_ENUMERATION_SITES`` inside the quoted span, the other bare.
    assert f"{name}` ({value})" in ARCHITECTURE


def test_the_pre_registered_mass_move_threshold():
    """`eval_censoring.MASS_MOVE_THRESHOLD` is a threshold fixed before the data.

    Its comment names the plan it comes from, and the plan states it as a percentage
    while the code holds a fraction. That mismatch is why an earlier sweep of this
    repo recorded it as "nothing to check against": string-matching 0.10 never finds
    "10%". It is checkable, and being pre-registered it is one of the values that most
    needs to be -- a threshold that drifts after the fact is the failure the whole
    pre-registration discipline exists to prevent.
    """
    text = source("scripts/eval_censoring.py")
    fraction = module_constants("scripts/eval_censoring.py")["MASS_MOVE_THRESHOLD"]

    plan_path = re.search(r"Pre-registered threshold \((docs/plans/[\w-]+\.md)\)", text).group(1)
    plan = (ROOT / plan_path).read_text()
    assert plan, f"{plan_path} is named by the script but is empty or missing"

    # The plan writes the pipes escaped, inside a markdown table cell.
    stated = {int(p) for p in re.findall(r"Δideal_opt_mass\\?\| [≤>] (\d+)% relative", plan)}
    assert stated, "the plan no longer states the threshold as a percentage"
    assert stated == {round(fraction * 100)}, (
        f"code holds {fraction} ({fraction * 100:g}%); the plan registers {stated}"
    )
