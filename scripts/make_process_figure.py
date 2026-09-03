"""Web figure: the order the project was built in, and what checked each step.

Every other figure here reports an outcome. This one documents the build, which is
the part a reader cannot reconstruct from a result: what was made first, what each
stage added, and what was put in place to catch it being wrong.

It is a sequence rather than a calendar on purpose. A date axis records when commits
landed, which is a fact about version control rather than about the work, and it
buries the thing worth showing: each stage rests on the one before it, and each one
has something independent checking it.

THE ORDER IS NOT ASSERTED, IT IS CHECKED. Each stage names the modules that
implement it, and the script refuses to draw unless the stages run in non-decreasing
order of when those modules first entered the repository. A stage list rearranged
into a tidier story than the one that actually happened will fail rather than print.
Within a stage the order is dependency order, which is not recoverable from
timestamps and is not claimed to be.

The "checked by" row is the point of the figure, not decoration. Those checks are
why the results in the rest of `docs/figures/web/` can be trusted, and several of
them caught something real: the dry run caught a submit script rebuilding the
previous experiment's circuits, and the brute-force equivalence is what keeps an
approximate encoding from quietly returning an infeasible schedule.

Every process number in the summary is recomputed at draw time: predictions and
their verdicts tallied from the rows of `docs/PREDICTIONS.md`, pre-registrations
counted from `docs/plans/`, corrections from the write-ups themselves, hardware
totals parsed from the generated provenance table. The script refuses to draw if any
of them stops holding, or if the ledger's own header disagrees with its rows.

The prediction counts name their quantity. An earlier caption read "14 predictions
were registered, 4 write-ups report one of them falsified", which counted plan files
and write-ups carrying a verdict token; the ledger counts predictions, of which eight
plans register more than one, so the two framings give different numbers for what
sounds like the same thing.

A correction counts only where a write-up corrects one of its own claims. Crediting
a correction made in another document is not the same act, and counting it inflated
this number by one for as long as the rule was a bare keyword search.

Run:  python scripts/make_process_figure.py
"""

from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PLANS = ROOT / "docs" / "plans"
RESULTS = ROOT / "docs" / "results"
LESSONS = ROOT / "docs" / "LESSONS.md"
JOBS = RESULTS / "hardware-jobs.md"
LEDGER = ROOT / "docs" / "PREDICTIONS.md"
DECISIONS = ROOT / "docs" / "DECISIONS.md"
OUT = ROOT / "docs" / "figures" / "web" / "process.png"

GENERATED = {"hardware-jobs.md"}          # provenance table, makes no claims
CORRECTION = re.compile(r"retract|corrected|walked back|superseded", re.I)
# A write-up counts only where it corrects or retracts one of ITS OWN claims. The
# keyword alone also fires on a sentence crediting a correction made somewhere
# else: optimizer-budget-study.md matched solely on "an overstatement is
# corrected there", which is about eval-censoring.md rather than about anything
# this document claimed. A sentence that names another file, or defers to
# "there", points away from the write-up it sits in, so it does not count.
ELSEWHERE = re.compile(r"\.md\b|\bthere\b", re.I)

# Which write-ups those two rules select, pinned by name. The count itself is
# still derived rather than hardcoded (docs/LESSONS.md section 7 is about the
# version that hardcoded it); what is pinned is the membership, so a rule that
# quietly starts matching more or fewer documents refuses to draw instead of
# restating whatever it happened to find. A new write-up that genuinely corrects
# its own claim belongs here: read the sentence that matched, then add it.
SELF_CORRECTING = [
    "basin-structure",
    "capacity-rate-sensitivity",
    "eval-censoring",
    "hardware-run-depth",
    "hardware-run-encoding",
    "hardware-run-encoding-replication",
    "hardware-run-spread",
    "slack-free-encoding",
]

INK = "#2F4B7C"
ACCENT = "#E45756"
HARDWARE = "#6A51A3"
CHECK = "#2F6B43"
BOX = "#EEF2F8"

# Build order. `files` are the modules implementing each stage and are what the
# ordering check runs on.
STAGES = [
    ("Model one day\nexactly",
     "cost, feasibility, and\nan exact classical solver",
     "matches brute-force\nenumeration",
     ["src/quantum_solar/problem.py", "src/quantum_solar/dynamic_programming.py"]),
    ("Make it\nquantum",
     "QUBO, Ising mapping,\nQAOA on a simulator",
     "must recover the\nexact optimum",
     ["src/quantum_solar/qubo.py", "src/quantum_solar/qaoa.py"]),
    ("Swap in\nreal inputs",
     "NREL solar, Xcel tariff,\nNREL household load",
     "season and day type\nfrom one index",
     ["src/quantum_solar/data/nrel.py"]),
    ("Sweep sizes,\nthen hardware",
     "tuned circuits on\nIBM's ibm_fez",
     "dry run before\nevery spend",
     ["scripts/experiment_scaling.py", "scripts/experiment_hardware.py"]),
    ("Cut the\nqubit cost",
     "checkpoint encodings,\nand a full year priced",
     "brute-force equivalence;\none attribution path",
     ["src/quantum_solar/encodings.py", "src/quantum_solar/annual.py"]),
    ("Fix the\nmeasurement",
     "exact statevector\ninstead of sampling",
     "agrees with Qiskit\nto 4e-17",
     ["src/quantum_solar/statevector.py"]),
    ("Price it\nfor a buyer",
     "sizing rule and\npayback arithmetic",
     "rule holds at all\n56 swept points",
     ["scripts/battery_sizing_study.py"]),
    ("Map the\nlandscape",
     "basin structure, and\na one-command demo",
     "prediction registered\nin advance",
     ["scripts/basin_study.py", "src/quantum_solar/__main__.py"]),
]


def git(*args) -> str:
    try:
        return subprocess.run(("git", "-C", str(ROOT)) + args, capture_output=True,
                              text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(
            f"REFUSING TO DRAW: this figure is built from the repository's own "
            f"history and git is unavailable here ({exc}). Run it from a clone."
        )


def added_on(rel: str) -> date:
    out = git("log", "--diff-filter=A", "--format=%ad", "--date=short", "--", rel).split()
    if not out:
        raise SystemExit(f"REFUSING TO DRAW: {rel} has no add-commit in history.")
    return date.fromisoformat(out[-1])


# A sentence ends at ".", "!" or "?", possibly behind the markdown emphasis that
# closes a bolded lead-in ("**...corrected.**"). Blocks are split first so a
# heading, which carries no terminator, cannot run into the sentence beneath it.
SENTENCE_END = re.compile(r"""(?<=[.!?])[*_`"')\]]*\s+""")
QUOTE_MARK = re.compile(r"^\s*>+\s?")


def sentences(text: str) -> list[str]:
    """Sentences, with markdown wrapping and blockquote markers flattened away."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        flat = " ".join(QUOTE_MARK.sub("", line) for line in block.splitlines())
        flat = " ".join(flat.split())
        if flat:
            out.extend(SENTENCE_END.split(flat))
    return out


def corrects_itself(path: Path) -> bool:
    """True where a correction sentence is about this write-up's own claims."""
    return any(CORRECTION.search(s) and not ELSEWHERE.search(s)
               for s in sentences(path.read_text()))


def check_order() -> list[date]:
    """Stages must run in non-decreasing order of when their modules first landed."""
    starts = [min(added_on(f) for f in files) for *_, files in STAGES]
    for i in range(1, len(starts)):
        if starts[i] < starts[i - 1]:
            raise SystemExit(
                f"REFUSING TO DRAW: stage {i + 1} "
                f"({STAGES[i][0].splitlines()[0]}) has modules dating from "
                f"{starts[i]}, earlier than stage {i} "
                f"({STAGES[i - 1][0].splitlines()[0]}) at {starts[i - 1]}. The stage "
                f"list tells a tidier story than the history does; fix the list."
            )
    return starts


LEDGER_HEADER = re.compile(
    r"\*\*Counts: (\d+) predictions .*? (\d+) held, (\d+) falsified, "
    r"(\d+) rule verdicts, (\d+) not run\.\*\*")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def ledger() -> dict:
    """Verdict tallies from the rows of PREDICTIONS.md, checked against its header.

    The rows are the record; the header is a restatement of them. Both are read so
    that a row edited without its header, or the reverse, refuses here instead of
    drawing whichever one happened to be parsed.
    """
    text = LEDGER.read_text()
    rows = []
    for line in text.splitlines():
        if line.startswith("| [") and "plans/" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows.append((LINK.search(cells[0]).group(2), cells[3].strip("*_ ")))
    counts = {"held": 0, "falsified": 0, "rule verdict": 0, "not run": 0}
    for _plan, verdict in rows:
        if verdict not in counts:
            raise SystemExit(f"REFUSING TO DRAW: unknown verdict {verdict!r} in the ledger.")
        counts[verdict] += 1
    header = LEDGER_HEADER.search(" ".join(text.split()))
    if not header:
        raise SystemExit("REFUSING TO DRAW: PREDICTIONS.md no longer states its counts.")
    stated = dict(zip(("total", "held", "falsified", "rule verdict", "not run"),
                      map(int, header.groups())))
    if stated != {"total": len(rows), **counts}:
        raise SystemExit(
            f"REFUSING TO DRAW: PREDICTIONS.md's header says {stated} but its rows "
            f"tally to {{'total': {len(rows)}, **{counts}}}. Fix the ledger first.")
    return {"total": len(rows), "plans": {Path(p).name for p, _ in rows}, **counts}


def gather():
    plans = sorted(PLANS.glob("*.md"))
    writeups = [p for p in sorted(RESULTS.glob("*.md")) if p.name not in GENERATED]

    # Every count is DERIVED and drawn, never asserted. An earlier version fixed
    # the falsified count at one and required every write-up to carry a correction,
    # so each new result made the figure unregenerable and the caption beside it
    # drifted instead (docs/LESSONS.md section 7, on the figure about the process).
    # The guards below check the claims are non-vacuous and agree with each other,
    # not that they are a fixed size.
    led = ledger()
    if led["plans"] != {p.name for p in plans}:
        raise SystemExit(
            "REFUSING TO DRAW: the plans scored in PREDICTIONS.md are not the files "
            f"in docs/plans/: {sorted(led['plans'] ^ {p.name for p in plans})}.")
    if not led["falsified"]:
        raise SystemExit(
            "REFUSING TO DRAW: the summary says predictions were falsified and "
            "published as such, but the ledger scores none.")
    # The verdict token is a looser count than the ledger's (a write-up can carry
    # two falsified predictions, or one under a heading that names the noise model
    # instead), so it is not drawn; but every write-up carrying it must be scored.
    headlining = [p for p in writeups if "FALSIFIED" in p.read_text()]
    if len(headlining) > led["falsified"]:
        raise SystemExit(
            f"REFUSING TO DRAW: {len(headlining)} write-ups carry FALSIFIED but the "
            f"ledger scores only {led['falsified']} predictions falsified.")
    corrected = [p for p in writeups if corrects_itself(p)]
    if sorted(p.stem for p in corrected) != sorted(SELF_CORRECTING):
        raise SystemExit(
            "REFUSING TO DRAW: the write-ups correcting a claim of their own are "
            f"{sorted(p.stem for p in corrected)}, not the pinned "
            f"{sorted(SELF_CORRECTING)}. Read the sentence that moved the verdict "
            "before editing the list: a write-up counts where it corrects itself, "
            "not where it reports a correction made in another document.")

    totals = re.search(
        r"\*\*(\d+) jobs, (\d+) circuits, ([\d,]+) shots, (\d+) seconds of QPU time",
        JOBS.read_text())
    if not totals:
        raise SystemExit(
            "REFUSING TO DRAW: could not read the totals line from hardware-jobs.md.")

    if "would have returned nine zeros" not in " ".join(LESSONS.read_text().split()):
        raise SystemExit(
            "REFUSING TO DRAW: LESSONS.md no longer records the declined run.")
    if "Declined the hardware encoding × weight 2×2" not in DECISIONS.read_text():
        raise SystemExit(
            "REFUSING TO DRAW: DECISIONS.md no longer records the experiment that "
            "was designed, costed and not run, which the figure points a reader to.")

    basin = " ".join((RESULTS / "basin-structure.md").read_text().split())
    if "U-shape with a strict minimum" not in basin:
        raise SystemExit(
            "REFUSING TO DRAW: basin-structure.md no longer states the registered "
            "prediction as a U-shape with a strict minimum, which is what this "
            "figure paraphrases.")

    return {"plans": len(plans), "writeups": len(writeups),
            "predictions": led["total"], "held": led["held"],
            "falsified": led["falsified"], "rules": led["rule verdict"],
            "corrected": len(corrected),
            "jobs": int(totals.group(1)), "circuits": int(totals.group(2)),
            "qpu": int(totals.group(4))}


def main() -> None:
    starts = check_order()
    d = gather()
    n = len(STAGES)

    fig, ax = plt.subplots(figsize=(15.2, 7.6))
    ax.set_xlim(-1.5, n - 0.22)
    ax.set_ylim(-2.15, 1.75)
    ax.axis("off")

    ax.add_patch(FancyArrowPatch((-0.5, 0), (n - 0.34, 0), arrowstyle="-|>",
                                 mutation_scale=22, color="0.72", lw=2.4, zorder=1))

    for i, (title, adds, checked, _files) in enumerate(STAGES):
        ax.add_patch(plt.Circle((i, 0), 0.12, color=INK, zorder=3))
        ax.text(i, 0, str(i + 1), ha="center", va="center", color="white",
                fontsize=11, weight="bold", zorder=4)
        ax.text(i, 0.31, title, ha="center", va="bottom", fontsize=11,
                weight="bold", color=INK)
        ax.text(i, 1.06, adds, ha="center", va="bottom", fontsize=9.3, color="0.38")
        ax.text(i, -0.32, checked, ha="center", va="top", fontsize=9.3, color=CHECK)

    ax.text(-1.45, 1.40, "what it added", fontsize=9.5, color="0.5", style="italic")
    ax.text(-1.45, -0.32, "checked by", fontsize=9.5, color=CHECK, style="italic",
            va="top")

    # The two decisions worth attaching to a stage rather than to a date. Naming
    # the prediction matters: "a prediction was falsified" is a claim about
    # temperament, and only the actual prediction makes it checkable.
    ax.text(3, -1.14, f"{d['jobs']} jobs, {d['circuits']} circuits, {d['qpu']} "
            f"seconds\nof quantum processor time in all.\nAn experiment was "
            f"designed,\ncosted, and then not run: it has no\nplan file, so it is "
            f"in DECISIONS.md.",
            ha="center", va="top", fontsize=10.5, color=HARDWARE)
    ax.text(7, -1.14, "Predicted: the tuner would converge\nless reliably at penalty "
            "weights on\nBOTH sides of the derived one.\nBelow it, reliability never "
            "drops.\nFALSIFIED, and published as such.",
            ha="center", va="top", fontsize=10.5, color=ACCENT, weight="bold")

    fig.suptitle("What I built, in the order I built it, and what checked each step",
                 fontsize=15.5, y=0.955)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.20)

    fig.text(
        0.5, 0.125,
        f"Each stage rests on the one before it, and none was trusted on its own. "
        f"{d['predictions']} registered predictions across {d['plans']} "
        f"pre-registrations: {d['held']} held, {d['falsified']} falsified, "
        f"{d['rules']} resolved by a decision rule rather than a directional claim.\n"
        f"{d['corrected']} of {d['writeups']} write-ups carry a correction or a "
        f"retraction. Being wrong was the normal case, not the exception.",
        ha="center", va="center", fontsize=10.5, color=INK,
        bbox=dict(boxstyle="round,pad=0.5", facecolor=BOX, edgecolor="#C6D3E4"))
    fig.text(0.5, 0.032,
             "The stage order is checked against the repository: the script refuses "
             "to draw unless each stage's modules first appear no earlier than the "
             "previous stage's. Within a stage, the order is dependency order.",
             ha="center", fontsize=10, color="0.35")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    for i, ((title, *_), start) in enumerate(zip(STAGES, starts), 1):
        print(f"  {i}. {title.replace(chr(10), ' '):<40} earliest module {start}")
    print(f"  order check passed; {d['predictions']} predictions in "
          f"{d['plans']} pre-registrations: {d['held']} held, {d['falsified']} "
          f"falsified, {d['rules']} rule verdicts; {d['corrected']}/{d['writeups']} "
          f"write-ups corrected; {d['qpu']} QPU-seconds")


if __name__ == "__main__":
    main()
