"""Regenerate the packaged CO residential load profiles from NREL ResStock.

One-off data-prep script (not imported at runtime). Downloads the ~45 MB NREL
ResStock AMY-2018 aggregate for Colorado single-family-detached homes and derives
the committed per-dwelling load profiles, bucketed by (season, day type):

    co_residential_{summer,winter}_{weekday,weekend}.csv   (4 files, 24 hourly kWh)

Derivation (matches profiles/SOURCE.md):
  1. per-dwelling load = out.electricity.total.energy_consumption.kwh
                         / units_represented   (~1.49M CO SFD homes)
  2. each 15-min timestamp is interval-ENDING; shift back 15 min to the
     interval-start local hour (so 00:15..01:00 -> hour 0).
  3. sum the four 15-min intervals into hourly kWh.
  4. average over every matching day in the bucket.

Seasons are pinned to the Xcel RE-TOU tariff's own split (summer = Jun-Sep,
periods with the higher on-peak rate; winter = Oct-May) so load and price seasons
never disagree. Day type (weekday/weekend) uses the row's real 2018 calendar
date — the same AMY-2018 year the annual loop classifies days under
(quantum_solar.data.calendar); holidays are billed as weekdays (v1 limitation).

The committed CSVs supersede the previous July-only summer-weekday profile: the
summer bucket now averages all Jun-Sep weekdays, consistent with the tariff.

Usage:
    python scripts/make_resstock_profiles.py           # download (cached) + write CSVs
    python scripts/make_resstock_profiles.py --dry-run # compute + print, do not write
"""

from __future__ import annotations

import argparse
import csv
import datetime
import urllib.request
from pathlib import Path

import numpy as np

AGGREGATE_URL = (
    "https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/"
    "end-use-load-profiles-for-us-building-stock/2024/resstock_amy2018_release_2/"
    "timeseries_aggregates/by_state/upgrade=0/state=CO/"
    "up00-co-single-family_detached.csv"
)

PROFILES_DIR = Path(__file__).resolve().parents[1] / "src" / "quantum_solar" / "data" / "profiles"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"
LOCAL_AGGREGATE = CACHE_DIR / "resstock_up00_co_single_family_detached.csv"

# Tariff-native season split (see module docstring): 0-based months Jun..Sep.
SUMMER_MONTHS0 = {5, 6, 7, 8}
_INTERVAL = datetime.timedelta(minutes=15)


def _season(month0: int) -> str:
    return "summer" if month0 in SUMMER_MONTHS0 else "winter"


def download(dest: Path = LOCAL_AGGREGATE) -> Path:
    """Fetch the aggregate CSV to ``dest`` (cached; skipped if already present)."""
    if dest.is_file():
        print(f"using cached aggregate: {dest} ({dest.stat().st_size/1e6:.1f} MB)")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {AGGREGATE_URL}\n       -> {dest}")
    req = urllib.request.Request(AGGREGATE_URL, headers={"User-Agent": "quantum-solar"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
        fh.write(resp.read())
    print(f"  saved {dest.stat().st_size/1e6:.1f} MB")
    return dest


def derive(aggregate: Path) -> dict[tuple[str, str], np.ndarray]:
    """Return {(season, day_type): 24 hourly per-dwelling kWh} from the aggregate."""
    # sum of per-dwelling kWh per (bucket, hour), and the set of dates per bucket
    # so we can average over the actual number of days in each bucket.
    totals: dict[tuple[str, str], np.ndarray] = {}
    dates: dict[tuple[str, str], set] = {}

    with open(aggregate, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            end = datetime.datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
            start = end - _INTERVAL  # interval-ending -> interval-start
            units = float(row["units_represented"])
            per_dwelling = float(row["out.electricity.total.energy_consumption.kwh"]) / units

            season = _season(start.month - 1)
            day_type = "weekend" if start.weekday() >= 5 else "weekday"
            bucket = (season, day_type)

            totals.setdefault(bucket, np.zeros(24))[start.hour] += per_dwelling
            dates.setdefault(bucket, set()).add(start.date())

    return {b: totals[b] / len(dates[b]) for b in totals}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="compute and print, do not write CSVs")
    args = ap.parse_args()

    profiles = derive(download())

    for (season, day_type), hourly in sorted(profiles.items()):
        assert hourly.shape == (24,)
        total = hourly.sum()
        path = PROFILES_DIR / f"co_residential_{season}_{day_type}.csv"
        print(f"{season:6} {day_type:7}  total={total:5.1f} kWh/day  peak={hourly.max():.2f}  -> {path.name}")
        if args.dry_run:
            continue
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["hour", "load_kwh"])
            for h in range(24):
                w.writerow([h, f"{hourly[h]:.3f}"])

    if args.dry_run:
        print("\n(dry run — no files written)")


if __name__ == "__main__":
    main()
