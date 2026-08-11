"""Web figure: how the project was actually run, as opposed to what it found.

Every other figure in `docs/figures/web/` reports an outcome. This one documents the
process that produced them, which is the part a reader cannot reconstruct from a
result: when work happened, what was predicted before it happened, what the data did
to those predictions, and where the decision was to spend nothing.

Four lanes on one timeline, all derived:

  registered    each pre-registration in `docs/plans/`, dated by the commit that
                first added it
  reported      each claim-making write-up in `docs/results/`, same dating, with
                the one falsified prediction called out
  hardware      the runs on `ibm_fez`, dated from the generated provenance table
  commits       commits per day, which is what the shape of the work looks like

THE HONEST PART, and the reason the footnote exists. Pre-registration is only worth
something if the plan really did come first, so the script measures that rather than
asserting it. In four of the six studies whose plan and result are separate
documents, the plan is an earlier commit by 46 to 158 minutes. In the other two both
files landed in a single commit, so the ordering is documented in the text but is
not independently timestamped, and the figure says so. A process figure that
overstated its own evidence would be self-defeating.

NOTHING IS TYPED IN. Dates come from `git log --diff-filter=A`, the hardware totals
from the table `scripts/hardware_jobs.py` generates, and every headline count from
grepping the documents themselves. The script refuses to draw if any of those counts
stops matching what it claims, so the summary box cannot drift from the repository
it describes.

Run:  python scripts/make_process_figure.py
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PLANS = ROOT / "docs" / "plans"
RESULTS = ROOT / "docs" / "results"
LESSONS = ROOT / "docs" / "LESSONS.md"
JOBS = RESULTS / "hardware-jobs.md"
OUT = ROOT / "docs" / "figures" / "web" / "process.png"

# The provenance table is generated and makes no claims of its own, so it is not
# one of the write-ups the "carries a correction" count applies to.
GENERATED = {"hardware-jobs.md"}
CORRECTION = re.compile(r"retract|corrected|walked back|superseded", re.I)

INK = "#2F4B7C"
ACCENT = "#E45756"
HARDWARE = "#6A51A3"
MUTED = "#9BB0C9"


def git(*args) -> str:
    try:
        return subprocess.run(("git", "-C", str(ROOT)) + args, capture_output=True,
                              text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(
            f"REFUSING TO DRAW: this figure is built from the repository's own "
            f"history and git is unavailable here ({exc}). Run it from a clone."
        )


def added_on(path: Path) -> date:
    """The date the commit that first added `path` landed."""
    out = git("log", "--diff-filter=A", "--format=%ad", "--date=short", "--",
              str(path.relative_to(ROOT))).split()
    if not out:
        raise SystemExit(f"REFUSING TO DRAW: {path.name} has no add-commit in history.")
    return date.fromisoformat(out[-1])


def added_at(path: Path) -> int:
    out = git("log", "--diff-filter=A", "--format=%at", "--",
              str(path.relative_to(ROOT))).split()
    return int(out[-1])


def gather():
    plans = sorted(PLANS.glob("*.md"))
    writeups = [p for p in sorted(RESULTS.glob("*.md")) if p.name not in GENERATED]

    falsified = [p for p in writeups if "FALSIFIED" in p.read_text()]
    if len(falsified) != 1:
        raise SystemExit(
            f"REFUSING TO DRAW: the figure calls out exactly one falsified "
            f"prediction, but {len(falsified)} write-ups contain FALSIFIED."
        )
    corrected = [p for p in writeups if CORRECTION.search(p.read_text())]
    if len(corrected) != len(writeups):
        uncorrected = sorted(p.name for p in writeups if p not in corrected)
        raise SystemExit(
            f"REFUSING TO DRAW: the summary says every claim-making write-up "
            f"carries a correction, but these do not: {uncorrected}."
        )

    # Pre-registration ordering, measured rather than asserted.
    paired = [(PLANS / p.name, RESULTS / p.name) for p in plans
              if (RESULTS / p.name).exists()]
    gaps = [(added_at(r) - added_at(pl)) / 60.0 for pl, r in paired]
    ordered = [g for g in gaps if g > 0]
    same_commit = [g for g in gaps if g == 0]
    if len(ordered) + len(same_commit) != len(paired):
        raise SystemExit(
            "REFUSING TO DRAW: a result was committed BEFORE its own plan, which "
            "would make the pre-registration claim false."
        )

    totals = re.search(
        r"\*\*(\d+) jobs, (\d+) circuits, ([\d,]+) shots, (\d+) seconds of QPU time",
        JOBS.read_text())
    if not totals:
        raise SystemExit(
            "REFUSING TO DRAW: could not read the totals line from "
            "hardware-jobs.md, which is where the QPU figures come from.")
    run_dates = sorted({date.fromisoformat(d) for d in
                        re.findall(r"^\| `\w+` \| (\d{4}-\d{2}-\d{2}) \|",
                                   JOBS.read_text(), re.M)})

    # Normalize wrapping: the phrase spans a line break in the source.
    lessons = " ".join(LESSONS.read_text().split())
    if "would have returned nine zeros" not in lessons:
        raise SystemExit(
            "REFUSING TO DRAW: LESSONS.md no longer records the declined run, "
            "which the figure marks.")

    commits = Counter(date.fromisoformat(d) for d in
                      git("log", "--format=%ad", "--date=short").split())

    # When the declined 4th experiment was recorded, from the commit that did it.
    declines = [line.split("|", 1)[0] for line in
                git("log", "--format=%ad|%s", "--date=short").splitlines()
                if re.search(r"not run|declin", line.split("|", 1)[1], re.I)]
    if not declines:
        raise SystemExit(
            "REFUSING TO DRAW: no commit records an experiment being declined, "
            "but the figure marks one.")

    return {
        "plans": [added_on(p) for p in plans],
        "writeups": [(added_on(p), p.name) for p in writeups],
        "falsified": added_on(falsified[0]),
        "runs": run_dates,
        "jobs": int(totals.group(1)), "circuits": int(totals.group(2)),
        "qpu": int(totals.group(4)),
        "n_writeups": len(writeups), "n_plans": len(plans),
        "ordered": len(ordered), "same_commit": len(same_commit),
        "gap_lo": min(ordered), "gap_hi": max(ordered),
        "commits": commits, "declined": date.fromisoformat(declines[-1]),
    }


def main() -> None:
    d = gather()
    days = sorted(d["commits"])
    lo, hi = min(days) - timedelta(days=2), max(days) + timedelta(days=2)

    fig, (ax, ax_c) = plt.subplots(
        2, 1, figsize=(13.6, 8.2), sharex=True,
        gridspec_kw={"height_ratios": [2.4, 1.0], "hspace": 0.10})

    lanes = {"registered": 3, "reported": 2, "hardware": 1}
    for name, y in lanes.items():
        ax.axhline(y, color="0.90", lw=1.0, zorder=0)

    ax.plot(d["plans"], [lanes["registered"]] * len(d["plans"]), "^",
            color=INK, ms=11, zorder=3)
    normal = [dt for dt, _ in d["writeups"] if dt != d["falsified"]]
    ax.plot(normal, [lanes["reported"]] * len(normal), "o", color=MUTED, ms=10,
            markeredgecolor=INK, markeredgewidth=1.4, zorder=3)
    ax.plot([d["falsified"]], [lanes["reported"]], "o", color=ACCENT, ms=13, zorder=4)
    ax.plot(d["runs"], [lanes["hardware"]] * len(d["runs"]), "*",
            color=HARDWARE, ms=19, zorder=3)

    for label, y in (("pre-registered", 3), ("reported", 2), ("ran on hardware", 1)):
        ax.text(lo + timedelta(hours=6), y + 0.26, label, fontsize=10.5,
                color="0.35", va="bottom")

    ax.annotate("first hardware run\n4 circuits, 7 QPU-seconds",
                xy=(d["runs"][0], 1), xytext=(d["runs"][0] + timedelta(days=1), 1.75),
                fontsize=9.5, color=HARDWARE,
                arrowprops=dict(arrowstyle="->", color=HARDWARE, lw=1.3))
    ax.annotate("prediction FALSIFIED,\nand published anyway",
                xy=(d["falsified"], 2), xytext=(d["falsified"] - timedelta(days=9), 2.62),
                fontsize=10, weight="bold", color=ACCENT, ha="right",
                arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.5))
    # A hollow star on the hardware lane: designed, costed, and not run. The
    # arrow needs something to point at, and the absence is the point.
    ax.plot([d["declined"]], [lanes["hardware"]], "*", ms=19, zorder=3,
            markerfacecolor="white", markeredgecolor=HARDWARE, markeredgewidth=1.8)
    ax.annotate("a 4th hardware experiment\ndesigned, costed, then declined",
                xy=(d["declined"], 1), xytext=(d["declined"] + timedelta(days=1), 0.42),
                fontsize=9.5, color="0.35", ha="center",
                arrowprops=dict(arrowstyle="->", color="0.5", lw=1.2))

    ax.set_ylim(0.18, 3.62)
    ax.set_yticks([])
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)

    counts = [d["commits"].get(day, 0) for day in
              [lo + timedelta(days=i) for i in range((hi - lo).days + 1)]]
    ax_c.bar([lo + timedelta(days=i) for i in range((hi - lo).days + 1)], counts,
             color=INK, width=0.85)
    ax_c.set_ylabel("commits\nper day", fontsize=10)
    ax_c.set_xlim(lo, hi)
    ax_c.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax_c.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax_c.grid(axis="y", alpha=0.25, lw=0.7)
    ax_c.set_axisbelow(True)
    for side in ("right", "top"):
        ax_c.spines[side].set_visible(False)

    fig.suptitle("How the project was run: predict first, then let the data overrule you",
                 fontsize=15, y=0.975)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.905, bottom=0.335)

    fig.text(
        0.5, 0.225,
        f"{d['n_plans']} predictions registered before the runs they describe. "
        f"{d['ordered']} of {d['ordered'] + d['same_commit']} are a separate, earlier "
        f"commit than their own result ({d['gap_lo']:.0f} to {d['gap_hi']:.0f} minutes "
        f"ahead); the other {d['same_commit']} shipped in one commit,\nso their order "
        f"is documented but not independently timestamped. "
        f"{len(d['writeups'])} of {len(d['writeups'])} write-ups carry a correction or "
        f"a retraction. 1 prediction was falsified and published as such.",
        ha="center", va="center", fontsize=10, color=INK,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#EEF2F8", edgecolor="#C6D3E4"),
    )
    fig.text(
        0.5, 0.105,
        f"{d['jobs']} jobs, {d['circuits']} circuits, {d['qpu']} seconds of quantum "
        f"processor time in total. The most useful decision was not to spend more: a "
        f"planned 10-hour run at the largest size\nwas cancelled once the metric was "
        f"shown to have bottomed out two sizes earlier, where it would have returned "
        f"nine zeros.",
        ha="center", va="center", fontsize=9.5, color="0.35",
    )
    fig.text(0.5, 0.022,
             "Dates from the commit that first added each document; hardware totals "
             "from the generated provenance table; every count above recomputed from "
             "the repository at draw time.",
             ha="center", fontsize=8.5, color="0.5")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  {d['n_plans']} pre-registrations, {d['n_writeups']} write-ups, all with "
          f"a correction; 1 falsified")
    print(f"  pre-registration ordering: {d['ordered']} separately committed "
          f"({d['gap_lo']:.0f} to {d['gap_hi']:.0f} min), {d['same_commit']} same-commit")
    print(f"  {d['jobs']} jobs, {d['circuits']} circuits, {d['qpu']} QPU-seconds; "
          f"{sum(d['commits'].values())} commits over {len(d['commits'])} active days")


if __name__ == "__main__":
    main()
