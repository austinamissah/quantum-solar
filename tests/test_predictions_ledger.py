"""Gates on `docs/PREDICTIONS.md` and `docs/DECISIONS.md`.

A ledger that can go stale is worth less than no ledger, so these checks are about
drift rather than about the contents being pleasant. Three things can rot here and
each has a check: a plan can be added and never scored, a linked write-up can be
renamed out from under a row, and the falsified count can drift from the prose that
states it -- which is what happened to the test count this repository already
records (`docs/LESSONS.md` section 7).

Two counts are pinned because they count different things and are easy to conflate.
Four *write-ups* headline a falsification in a verdict line, which is what
`docs/FINDINGS.md` and the README report.
Eight *predictions* are scored falsified in the ledger: `hardware-run-encoding.md`
carries two whose headings name the noise model rather than the prediction, and
`hardware-run.md`'s H1 met its own stated refutation condition. Asserting either
number alone would let the other drift.

Every count check is written as a function over text, and every one has a mutation
beside it that perturbs the document and requires the function to raise. A guard
that has never been broken has shown nothing, and one that silently matches nothing
looks identical to one that passes -- so each mutation asserts its target string is
present before changing it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from _markdown import flatten, markdown_table

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PLANS = DOCS / "plans"
RESULTS = DOCS / "results"

PREDICTIONS = DOCS / "PREDICTIONS.md"
DECISIONS = DOCS / "DECISIONS.md"
FINDINGS = DOCS / "FINDINGS.md"

PRED_TEXT = PREDICTIONS.read_text()
DEC_TEXT = DECISIONS.read_text()
FINDINGS_TEXT = FINDINGS.read_text()

#: `[label](target)` -- the ledgers carry every reference as a link so a rename
#: breaks a test rather than a reader.
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

VERDICTS = {"held", "falsified", "rule verdict", "not run"}
WORDS = {"four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "thirteen": 13, "fourteen": 14, "twenty-six": 26}
README_TEXT = (ROOT / "README.md").read_text()
README_SENTENCE = re.compile(
    r"(\w[\w-]*) predictions were registered across (\w+) pre-registrations before the "
    r"runs they describe; (\w+) were falsified and (\w+) resolved by a decision rule")


def parse_rows(text: str) -> list[dict]:
    """One dict per scored prediction: its plan, its verdict, its result link."""
    rows = []
    for cells in markdown_table(text, "what was predicted")[1]:
        plan, result = LINK.search(cells[0]), LINK.search(cells[4])
        assert plan and result, f"a row is missing a link: {cells[0]!r} / {cells[4]!r}"
        rows.append({"plan": plan.group(2), "predicted": cells[1],
                     "happened": cells[2], "verdict": cells[3].strip("*_ "),
                     "result": result.group(2)})
    return rows


def tally(rows: list[dict]) -> dict[str, int]:
    counts = {v: 0 for v in VERDICTS}
    for row in rows:
        counts[row["verdict"]] += 1
    return counts


ROWS = parse_rows(PRED_TEXT)


def writeups_headlining_a_falsification(results: Path = RESULTS) -> list[Path]:
    """Write-ups whose own text carries the verdict word, as the prose counts them.

    The literal uppercase token, which these documents use only in a verdict line;
    `scripts/make_process_figure.py` uses the same rule as a cross-check against the
    ledger. The generated provenance table makes no claims and is excluded there and
    here.
    """
    return [p for p in sorted(results.glob("*.md"))
            if p.name != "hardware-jobs.md" and "FALSIFIED" in p.read_text()]


# --- the three checks that carry the file, as functions over text -------------

def check_header_tally(pred_text: str) -> None:
    """The ledger's own summary line against the rows underneath it."""
    rows = parse_rows(pred_text)
    counts = tally(rows)
    stated = re.search(
        r"\*\*Counts: (\d+) predictions .*? (\d+) held, (\d+) falsified, "
        r"(\d+) rule verdicts, (\d+) not run\.\*\*", flatten(pred_text))
    assert stated, "the header no longer states its counts in the pinned form"
    assert int(stated.group(1)) == len(rows), "header total is not the row count"
    assert int(stated.group(2)) == counts["held"], "header 'held' is not the row count"
    assert int(stated.group(3)) == counts["falsified"], "header 'falsified' is not the row count"
    assert int(stated.group(4)) == counts["rule verdict"], "header 'rule verdict' is not the row count"
    assert int(stated.group(5)) == counts["not run"], "header 'not run' is not the row count"


def check_prose_agrees(pred_text: str, findings_text: str, results: Path = RESULTS) -> None:
    """The ledger against every count stated in prose elsewhere in the repository."""
    flat = flatten(findings_text)
    assert "Four write-ups report a registered prediction falsified" in flat, (
        "FINDINGS.md no longer states the write-up count in the pinned form")
    assert len(writeups_headlining_a_falsification(results)) == 4, (
        "the number of write-ups headlining a falsification is not four")

    stated = re.search(r"scores all \*\*(\d+)\*\* registered predictions, "
                       r"\*\*(\d+)\*\* of them falsified", flat)
    assert stated, "FINDINGS.md no longer states the per-prediction counts"
    rows = parse_rows(pred_text)
    assert int(stated.group(1)) == len(rows), "prose total is not the row count"
    assert int(stated.group(2)) == tally(rows)["falsified"], (
        "prose falsified count is not the row count")


def check_logbook_size(dec_text: str) -> None:
    rows = markdown_table(dec_text, "alternative rejected")[1]
    assert 0 < len(rows) <= 10, f"{len(rows)} rows; the cap is ten"
    header = re.search(r"\b(\w+) forks in this project's record", flatten(dec_text), re.I)
    assert header, "the header no longer states how many forks it lists"
    assert WORDS[header.group(1).lower()] == len(rows), "header count is not the row count"


# --- coverage, links, vocabulary ----------------------------------------------

def test_there_are_rows_to_check():
    """Guard the guard: a parser that matched nothing would pass every test below."""
    assert len(ROWS) >= 20, f"parsed only {len(ROWS)} rows; the table did not parse"
    assert len(list(PLANS.glob("*.md"))) == 14


def test_every_plan_file_is_scored():
    """No plan may be quietly left out, including one that was never run.

    At least one row rather than exactly one: eight of the plans register more than
    one prediction, and several split held from falsified within a single plan. One
    row per plan would force those to a single verdict, which is the softening this
    ledger exists to prevent.
    """
    scored = {Path(row["plan"]).name for row in ROWS}
    missing = {p.name for p in PLANS.glob("*.md")} - scored
    assert not missing, f"plans with no row in PREDICTIONS.md: {sorted(missing)}"


def test_every_row_names_a_real_plan_and_a_real_result():
    for row in ROWS:
        assert (DOCS / row["plan"]).is_file(), f"no such plan: {row['plan']}"
        assert (DOCS / row["result"]).resolve().is_file(), f"no such result: {row['result']}"


def test_every_verdict_is_one_of_the_four_values():
    for row in ROWS:
        assert row["verdict"] in VERDICTS, f"unknown verdict {row['verdict']!r}"


def test_the_softened_falsification_is_still_scored_as_one():
    """H1 is the row most likely to drift back to the wording its write-up uses.

    Its plan states the refutation condition, the run met it, and the notebook
    records it as "partially supported at best". The ledger scores it falsified and
    quotes the softer phrasing in the outcome column rather than in the verdict.
    """
    h1 = [r for r in ROWS if r["plan"].endswith("hardware-run.md")
          and "H1" in r["predicted"]]
    assert len(h1) == 1, "the H1 row is missing or duplicated"
    assert h1[0]["verdict"] == "falsified"
    assert "partially supported at best" in h1[0]["happened"]


# --- the counts, with mutations -----------------------------------------------

def test_the_header_tally_matches_the_rows():
    check_header_tally(PRED_TEXT)


def test_the_header_tally_guard_catches_a_perturbed_count():
    """Guard the guard: move one count in the header and the check must fail."""
    original = "8 falsified"
    assert original in PRED_TEXT, "the header phrasing moved; this mutation tests nothing"
    with pytest.raises(AssertionError, match="header 'falsified'"):
        check_header_tally(PRED_TEXT.replace(original, "7 falsified"))


def test_the_header_tally_guard_catches_a_flipped_verdict():
    """The nastier mutation: a verdict flips and the header is left alone."""
    original = "| **falsified** | [basin-structure.md](results/basin-structure.md) |"
    assert original in PRED_TEXT, "the basin row moved; this mutation tests nothing"
    flipped = PRED_TEXT.replace(
        original, "| **held** | [basin-structure.md](results/basin-structure.md) |", 1)
    with pytest.raises(AssertionError, match="header 'held'|header 'falsified'"):
        check_header_tally(flipped)


def test_findings_and_the_ledger_agree_on_both_counts():
    check_prose_agrees(PRED_TEXT, FINDINGS_TEXT)


def test_the_prose_guard_catches_a_perturbed_prediction_count():
    original = "registered predictions, **8** of"
    assert original in FINDINGS_TEXT, "the FINDINGS sentence moved; this tests nothing"
    with pytest.raises(AssertionError, match="prose falsified count"):
        check_prose_agrees(PRED_TEXT, FINDINGS_TEXT.replace(
            original, "registered predictions, **6** of"))


def check_readme_agrees(pred_text: str, readme_text: str) -> None:
    """The README sentence under the process figure, against the ledger rows.

    This sentence used to read "Fourteen predictions were registered", which counted
    plan files; it sits directly under a figure that now counts predictions, so it is
    the restatement most likely to drift back.
    """
    m = README_SENTENCE.search(flatten(readme_text))
    assert m, "README no longer states the prediction counts in the pinned form"
    rows = parse_rows(pred_text)
    counts = tally(rows)
    plans = {Path(r["plan"]).name for r in rows}
    assert WORDS[m.group(1).lower()] == len(rows), "README total is not the row count"
    assert WORDS[m.group(2).lower()] == len(plans), "README plan count is not the ledger's"
    assert WORDS[m.group(3).lower()] == counts["falsified"], "README falsified is not the row count"
    assert WORDS[m.group(4).lower()] == counts["rule verdict"], "README rule count is not the row count"


def test_the_readme_sentence_agrees_with_the_ledger():
    check_readme_agrees(PRED_TEXT, README_TEXT)


def test_the_readme_guard_catches_a_perturbed_count():
    original = "eight were falsified"
    assert original in README_TEXT, "the README sentence moved; this mutation tests nothing"
    with pytest.raises(AssertionError, match="README falsified"):
        check_readme_agrees(PRED_TEXT, README_TEXT.replace(original, "four were falsified"))


def test_the_prose_guard_catches_a_perturbed_writeup_count(tmp_path):
    """Add a write-up that headlines a falsification and the four must stop matching."""
    fake = tmp_path / "results"
    fake.mkdir()
    for src in RESULTS.glob("*.md"):
        (fake / src.name).write_text(src.read_text())
    assert len(writeups_headlining_a_falsification(fake)) == 4
    (fake / "invented-study.md").write_text("# Invented\n\nVerdict: FALSIFIED.\n")
    with pytest.raises(AssertionError, match="is not four"):
        check_prose_agrees(PRED_TEXT, FINDINGS_TEXT, fake)


def test_every_headlining_writeup_has_a_falsified_row():
    """The looser count cannot exceed the stricter one without the ledger noticing.

    A write-up that says FALSIFIED and has no falsified row in the ledger means the
    ledger missed a falsification, which is the one direction of drift that would
    make this file worse than nothing.
    """
    linked = {Path(row["result"]).name for row in ROWS if row["verdict"] == "falsified"}
    for writeup in writeups_headlining_a_falsification():
        assert writeup.name in linked, (
            f"{writeup.name} headlines a falsification with no falsified row")


def test_the_falsified_rows_land_where_their_writeups_report_them():
    """Which document each falsification belongs to, not just how many there are."""
    expected = {
        "basin-structure.md": 1,
        "basin-structure-reps2.md": 1,
        "hardware-run-depth.md": 2,
        "hardware-run-depth-replication.md": 1,
        "hardware-run-encoding.md": 2,
        "experiment_hardware.ipynb": 1,
    }
    actual: dict[str, int] = {}
    for row in ROWS:
        if row["verdict"] == "falsified":
            name = Path(row["result"]).name
            actual[name] = actual.get(name, 0) + 1
    assert actual == expected


def test_not_run_is_empty_and_says_why():
    """All fourteen plans ran; the declined experiment never reached a plan file."""
    assert tally(ROWS)["not run"] == 0
    assert "*not run* is empty: all fourteen plans ran" in flatten(PRED_TEXT)
    assert "DECISIONS.md" in PRED_TEXT


# --- the decisions logbook ----------------------------------------------------

DEC_ROWS = markdown_table(DEC_TEXT, "alternative rejected")[1]


def test_the_logbook_stays_selective_and_counts_itself():
    check_logbook_size(DEC_TEXT)


def test_the_logbook_guard_catches_a_perturbed_count():
    original = "Nine forks in this project's record"
    assert original in DEC_TEXT, "the header phrasing moved; this mutation tests nothing"
    with pytest.raises(AssertionError, match="header count"):
        check_logbook_size(DEC_TEXT.replace(original, "Eight forks in this project's record"))


def test_every_decision_row_is_complete():
    """The load-bearing columns are the alternative and the cost; neither may be thin."""
    for cells in DEC_ROWS:
        date, decision, alternative, cost, _ = cells
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date), f"bad date: {date!r}"
        assert len(decision) > 20, f"decision too thin to be checkable: {cells}"
        assert len(alternative) > 20, f"no real alternative recorded: {cells}"
        assert len(cost) > 20, f"cost too thin to be specific: {cells}"
        assert cost.strip().lower() not in {"time", "effort"}, f"unspecific cost: {cost!r}"


def test_every_decision_links_somewhere_real():
    for cells in DEC_ROWS:
        target = LINK.search(cells[4])
        assert target, f"a decision row has no link: {cells[4]!r}"
        assert (DOCS / target.group(2)).resolve().is_file(), target.group(2)


@pytest.mark.parametrize("path", [PREDICTIONS, DECISIONS], ids=lambda p: p.name)
def test_the_ledgers_are_notes_rather_than_instructions(path):
    """Public documentation here describes; standing instructions live elsewhere."""
    flat = flatten(path.read_text()).lower()
    for phrase in ("do not ", "always ", "keep it that way", "you should"):
        assert phrase not in flat, f"{path.name} reads as an instruction: {phrase!r}"
