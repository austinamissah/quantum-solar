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

from ..problem import BatteryProblem, synthetic_instance
from .config import NLR_BASE, nrel_api_key

PVWATTS_ENDPOINT = f"{NLR_BASE}/pvwatts/v8.json"
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

    if cache_file is not None:
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
    ac_watts = np.asarray(data["outputs"]["ac"], dtype=float)  # hourly average W
    return ac_watts / 1000.0  # -> kWh per hour


def to_slots(hourly: np.ndarray, day: int, num_slots: int) -> np.ndarray:
    """Aggregate one day's 24 hourly energy values into ``num_slots`` slots (kWh)."""
    if 24 % num_slots != 0:
        raise ValueError(f"num_slots must divide 24, got {num_slots}")
    hourly = np.asarray(hourly, dtype=float)
    day_hours = hourly[day * 24 : (day + 1) * 24]
    if day_hours.shape[0] < 24:
        raise ValueError(f"not enough hourly data for day {day}")
    return day_hours.reshape(num_slots, 24 // num_slots).sum(axis=1)


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
    price_seed: int = 0,
    cache_dir: Path | None = DEFAULT_CACHE,
    api_key: str | None = None,
) -> BatteryProblem:
    """Build a :class:`BatteryProblem` with real PVWatts solar generation.

    Price and load are synthetic for now (v1). ``day`` is a 0-based day-of-year
    index (default ~summer solstice).
    """
    discharge_energy = charge_energy if discharge_energy is None else discharge_energy
    initial_soc = capacity / 2.0 if initial_soc is None else initial_soc

    hourly = fetch_pvwatts(lat, lon, system_kw, cache_dir=cache_dir, api_key=api_key)
    generation = to_slots(hourly, day, num_slots)

    synthetic = synthetic_instance(num_slots, seed=price_seed)  # price + load shapes
    return BatteryProblem(
        generation=generation,
        load=synthetic.load,
        price=synthetic.price,
        capacity=capacity,
        charge_energy=charge_energy,
        discharge_energy=discharge_energy,
        initial_soc=initial_soc,
    )
