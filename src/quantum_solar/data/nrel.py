"""NREL data loader (solar generation via PVWatts).

v1 scope: real solar generation from the PVWatts v8 API, mapped onto ``T`` slots.
Price and household load remain synthetic (see ``synthetic_instance``); a URDB
time-of-use price loader and an EIA load loader are on the roadmap.

API responses are cached to disk (keyed on the request minus the api_key) so runs
are reproducible and offline-friendly.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

from ..problem import BatteryProblem
from .config import NLR_BASE, nrel_api_key
from .load_profile import co_summer_weekday_load

PVWATTS_ENDPOINT = f"{NLR_BASE}/pvwatts/v8.json"

# Detailed URDB time-of-use rate structures come from the OpenEI Utility Rates
# API (host api.openei.org) — documented on the NLR developer network and keyed
# by the same NREL API key. developer.nlr.gov's own utility_rates endpoint
# returns only average rates (no TOU schedule).
URDB_ENDPOINT = "https://api.openei.org/utility_rates"

# Public Service Co of Colorado (Xcel Energy) — "Residential Energy Time Of Use
# (Schedule RE-TOU)", the active 2026 residential TOU tariff, aligned with the
# Golden, CO PVWatts location. Summer weekday: off-peak ~$0.139/kWh, on-peak
# ~$0.381/kWh (17:00-21:00). URDB rate:
#   https://apps.openei.org/USURDB/rate/view/69bd927af5cd25efec0e9aad
#
# The entry keeps the legacy "RE-TOU" name but reflects the post-Nov-2025
# two-period (on/off-peak) TOU structure. Tariff data is a snapshot — Xcel has a
# ~9.9% increase filed for Aug 2026 — so this label (and the committed test
# fixture) pin the specific version we test against.
XCEL_CO_RETOU_LABEL = "69bd927af5cd25efec0e9aad"

DEFAULT_CACHE = Path(__file__).resolve().parents[3] / "data" / "cache"


def _get_json(url: str, params: dict, cache_dir: Path | None) -> dict:
    """GET ``url?params`` as JSON, using an on-disk cache when ``cache_dir`` set."""
    cache_file: Path | None = None
    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_key = url + "?" + urllib.parse.urlencode(
            {k: v for k, v in sorted(params.items()) if k != "api_key"}
        )
        digest = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
        cache_file = cache_dir / f"{digest}.json"
        if cache_file.is_file():
            return json.loads(cache_file.read_text())

    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(full_url, headers={"User-Agent": "quantum-solar"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)

    # Only cache successful responses — caching an error payload would serve a
    # transient failure from disk forever. PVWatts reports errors under "errors",
    # the OpenEI/URDB API under "error"; treat either as a failure.
    if cache_file is not None and not (data.get("errors") or data.get("error")):
        cache_file.write_text(json.dumps(data))
    return data


def fetch_pvwatts(
    lat: float,
    lon: float,
    system_kw: float,
    *,
    tilt: float = 20.0,
    azimuth: float = 180.0,
    array_type: int = 1,
    module_type: int = 0,
    losses: float = 14.0,
    cache_dir: Path | None = DEFAULT_CACHE,
    api_key: str | None = None,
) -> np.ndarray:
    """Return 8760 hourly AC energy values (kWh) for a PV system at ``lat/lon``."""
    params = {
        "api_key": api_key or nrel_api_key(),
        "lat": lat,
        "lon": lon,
        "system_capacity": system_kw,
        "azimuth": azimuth,
        "tilt": tilt,
        "array_type": array_type,
        "module_type": module_type,
        "losses": losses,
        "timeframe": "hourly",
    }
    data = _get_json(PVWATTS_ENDPOINT, params, cache_dir)
    errors = data.get("errors") or []
    if errors:
        raise RuntimeError(f"PVWatts API error: {errors}")
    ac_wh = np.asarray(data["outputs"]["ac"], dtype=float)  # hourly AC energy (Wh)
    return ac_wh / 1000.0  # -> kWh per hour


def to_slots(hourly: np.ndarray, day: int, num_slots: int) -> np.ndarray:
    """Aggregate one day's 24 hourly energy values into ``num_slots`` slots (kWh).

    Energy quantities ONLY: values are *summed* within each slot, so a wider slot
    holds proportionally more energy. Intensive per-unit series — a future price
    or rate curve ($/kWh) — must be *averaged* per slot, not summed; do not reuse
    this helper for them.
    """
    if 24 % num_slots != 0:
        raise ValueError(f"num_slots must divide 24, got {num_slots}")
    hourly = np.asarray(hourly, dtype=float)
    day_hours = hourly[day * 24 : (day + 1) * 24]
    if day_hours.shape[0] < 24:
        raise ValueError(f"not enough hourly data for day {day}")
    return day_hours.reshape(num_slots, 24 // num_slots).sum(axis=1)


def fetch_urdb_tou(
    label: str,
    *,
    month: int = 6,
    cache_dir: Path | None = DEFAULT_CACHE,
    api_key: str | None = None,
) -> np.ndarray:
    """Return the 24-hour weekday $/kWh price vector for a URDB rate.

    Extracts the ``energyweekdayschedule`` for ``month`` (0-based; default July =
    summer) and maps each hour's period to its first-tier energy rate. Prices are
    intensive per-kWh values — resample with :func:`price_to_slots`, never
    :func:`to_slots`.

    Weekday only. In this tariff the ``energyweekendschedule`` (already present in
    the response) is flat off-peak all day, so weekends offer no arbitrage. A
    future ``weekend=True`` parameter could expose that schedule; not built here.

    URDB rates are *all-in* per-kWh prices (energy plus delivery, riders, and
    adjustments), so they exceed a utility's published energy-only charge — e.g.
    the Xcel RE-TOU rate returns ~$0.381/kWh on-peak summer 2026 vs Xcel's
    published ~$0.21 energy-only, while matching the PUC-approved structure
    exactly (5-9pm weekday peak, ~2.7x on/off-peak ratio). All-in is the correct
    price for battery arbitrage, which pays or avoids the full retail rate.
    """
    params = {
        "version": "latest",
        "format": "json",
        "detail": "full",
        "api_key": api_key or nrel_api_key(),
        "getpage": label,
    }
    data = _get_json(URDB_ENDPOINT, params, cache_dir)
    if data.get("errors") or data.get("error"):
        raise RuntimeError(f"URDB API error: {data.get('errors') or data.get('error')}")
    items = data.get("items") or []
    if not items:
        raise RuntimeError(f"URDB returned no rate for label {label!r}")

    rate = items[0]
    structure = rate["energyratestructure"]
    schedule = rate["energyweekdayschedule"][month]  # 24 period indices, local hour
    tier0 = lambda period: structure[period][0]
    return np.array(
        [tier0(p)["rate"] + (tier0(p).get("adj") or 0.0) for p in schedule],
        dtype=float,
    )


def price_to_slots(hourly_price: np.ndarray, num_slots: int) -> np.ndarray:
    """Resample a 24-hour price vector to ``num_slots`` by AVERAGING (kWh price).

    Prices are intensive (per-kWh): a wider slot's price is the mean of its hours,
    not their sum. This is deliberately distinct from :func:`to_slots`, which sums
    energy — do not swap them.
    """
    if 24 % num_slots != 0:
        raise ValueError(f"num_slots must divide 24, got {num_slots}")
    hourly = np.asarray(hourly_price, dtype=float)
    if hourly.shape[0] != 24:
        raise ValueError(f"expected 24 hourly prices, got {hourly.shape[0]}")
    return hourly.reshape(num_slots, 24 // num_slots).mean(axis=1)


def load_nrel_instance(
    lat: float,
    lon: float,
    *,
    day: int = 172,
    num_slots: int = 24,
    capacity: float = 10.0,
    charge_energy: float = 2.0,
    discharge_energy: float | None = None,
    initial_soc: float | None = None,
    system_kw: float = 5.0,
    rate_label: str = XCEL_CO_RETOU_LABEL,
    price_month: int = 6,
    cache_dir: Path | None = DEFAULT_CACHE,
    api_key: str | None = None,
) -> BatteryProblem:
    """Build a :class:`BatteryProblem` from real data (``num_slots=24`` only).

    All three inputs are real:
      * ``generation`` — NREL PVWatts for ``lat``/``lon`` (``day`` is a 0-based
        day-of-year index, default ~summer solstice). Energy: summed via to_slots.
      * ``price`` — Xcel Energy CO "Residential Energy TOU (RE-TOU)" weekday
        schedule for ``price_month`` from URDB (``rate_label``). Intensive
        $/kWh: averaged via price_to_slots.
      * ``load`` — NREL ResStock representative Colorado single-family-detached
        summer-weekday profile (``co_summer_weekday_load``). Energy: summed via
        to_slots.
    """
    # v1 restriction: generation and load are aggregated as ENERGY per slot (they
    # scale with slot width via to_slots), while price is a duration-independent
    # per-slot value. Combining them at any resolution other than hourly would mix
    # inconsistent units, so only 24 one-hour slots are allowed.
    if num_slots != 24:
        raise ValueError(
            "load_nrel_instance supports only num_slots=24 in v1 (hourly): real "
            "PVWatts generation and load are summed as energy per slot while price "
            "is duration-independent, so other resolutions would be "
            "energy-inconsistent."
        )

    discharge_energy = charge_energy if discharge_energy is None else discharge_energy
    # Default to ~half full, snapped onto the charge-energy SoC grid so the DP's
    # grid does not round it off (an off-grid initial SoC yields infeasible,
    # capacity-exceeding schedules; see require_soc_on_grid).
    if initial_soc is None:
        initial_soc = round((capacity / 2.0) / charge_energy) * charge_energy

    hourly = fetch_pvwatts(lat, lon, system_kw, cache_dir=cache_dir, api_key=api_key)
    generation = to_slots(hourly, day, num_slots)

    hourly_price = fetch_urdb_tou(rate_label, month=price_month, cache_dir=cache_dir, api_key=api_key)
    price = price_to_slots(hourly_price, num_slots)

    # TIME ALIGNMENT: PVWatts output, the URDB weekday schedule, and the load
    # profile are all indexed by local clock hour 0..23 (local standard time; DST
    # ignored), so generation[i], price[i], load[i] refer to the same hour. At
    # num_slots=24 every resample is the identity.
    load = to_slots(co_summer_weekday_load(), day=0, num_slots=num_slots)
    return BatteryProblem(
        generation=generation,
        load=load,
        price=price,
        capacity=capacity,
        charge_energy=charge_energy,
        discharge_energy=discharge_energy,
        initial_soc=initial_soc,
    )
