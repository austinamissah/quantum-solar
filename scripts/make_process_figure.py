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

Every process number in the summary is recomputed at draw time: pre-registrations
counted from `docs/plans/`, corrections from the write-ups themselves, hardware
totals parsed from the generated provenance table. The script refuses to draw if any
of them stops holding.

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
OUT = ROOT / "docs" / "figures" / "web" / "process.png"

GENERATED = {"hardware-jobs.md"}          # provenance table, makes no claims
CORRECTION = re.compile(r"retract|corrected|walked back|superseded", re.I)

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


def gather():
    plans = sorted(PLANS.glob("*.md"))
    writeups = [p for p in sorted(RESULTS.glob("*.md")) if p.name not in GENERATED]

    falsified = [p for p in writeups if "FALSIFIED" in p.read_text()]
    if len(falsified) != 1:
        raise SystemExit(
            f"REFUSING TO DRAW: the summary claims one falsified prediction, but "
            f"{len(falsified)} write-ups contain FALSIFIED.")
    corrected = [p for p in writeups if CORRECTION.search(p.read_text())]
    if len(corrected) != len(writeups):
        missing = sorted(p.name for p in writeups if p not in corrected)
        raise SystemExit(
            f"REFUSING TO DRAW: the summary says every claim-making write-up carries "
            f"a correction, but these do not: {missing}.")

    totals = re.search(
        r"\*\*(\d+) jobs, (\d+) circuits, ([\d,]+) shots, (\d+) seconds of QPU time",
        JOBS.read_text())
    if not totals:
        raise SystemExit(
            "REFUSING TO DRAW: could not read the totals line from hardware-jobs.md.")

    if "would have returned nine zeros" not in " ".join(LESSONS.read_text().split()):
        raise SystemExit(
            "REFUSING TO DRAW: LESSONS.md no longer records the declined run.")

    return {"plans": len(plans), "writeups": len(writeups),
            "jobs": int(totals.group(1)), "circuits": int(totals.group(2)),
            "qpu": int(totals.group(4))}


def main() -> None:
    starts = check_order()
    d = gather()
    n = len(STAGES)

    fig, ax = plt.subplots(figsize=(15.2, 7.6))
    ax.set_xlim(-1.5, n - 0.22)
    ax.set_ylim(-1.75, 1.75)
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

    # The two decisions worth attaching to a stage rather than to a date.
    ax.text(3, -1.16, f"{d['jobs']} jobs, {d['circuits']} circuits, {d['qpu']} "
            f"seconds\nof quantum processor time in all.\nA 4th experiment was "
            f"designed,\ncosted, and then not run.",
            ha="center", va="top", fontsize=9.3, color=HARDWARE)
    ax.text(7, -1.16, "The prediction here was\nFALSIFIED, and published\nas such.",
            ha="center", va="top", fontsize=9.3, color=ACCENT, weight="bold")

    fig.suptitle("What I built, in the order I built it, and what checked each step",
                 fontsize=15.5, y=0.955)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.22)

    fig.text(
        0.5, 0.125,
        f"Each stage rests on the one before it, and none was trusted on its own. "
        f"{d['plans']} predictions were registered before the runs they describe, and "
        f"{d['writeups']} of {d['writeups']} write-ups carry a correction or a "
        f"retraction:\nbeing wrong was the normal case, not the exception.",
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
    print(f"  order check passed; {d['plans']} pre-registrations, "
          f"{d['writeups']}/{d['writeups']} write-ups corrected, "
          f"{d['qpu']} QPU-seconds")


if __name__ == "__main__":
    main()
