"""Representative Colorado residential load profile (packaged reference data).

Unlike the PVWatts and URDB loaders, this is a *static* reference profile (not a
per-request API query), so it is packaged as a committed CSV and read with no
network. Provenance and derivation are documented in profiles/SOURCE.md.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

_PROFILE_PATH = Path(__file__).resolve().parent / "profiles" / "co_residential_summer_weekday.csv"


def co_summer_weekday_load() -> np.ndarray:
    """Representative CO residential load: 24 hourly kWh for a typical summer weekday.

    ENERGY quantity (kWh): aggregate to slots with ``to_slots`` (which SUMS), never
    ``price_to_slots`` (which averages). Static reference profile — not indexed by
    day-of-year.

    Source: NREL End-Use Load Profiles / ResStock (``resstock_amy2018_release_2``),
    Colorado single-family-detached aggregate, per-dwelling July-weekday average.
    See ``profiles/SOURCE.md``.
    """
    with open(_PROFILE_PATH, newline="") as f:
        reader = csv.DictReader(f)
        return np.array([float(row["load_kwh"]) for row in reader], dtype=float)
