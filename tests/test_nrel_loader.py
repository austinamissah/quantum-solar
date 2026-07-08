"""NREL loader: offline parsing/resampling/config tests + a gated live test."""

import io
import json
import os
import urllib.request
from pathlib import Path

import numpy as np
import pytest

from quantum_solar.data import config, nrel

FIXTURES = Path(__file__).parent / "fixtures"


# --- to_slots resampling -----------------------------------------------------

def test_to_slots_hourly_identity():
    hourly = np.arange(48, dtype=float)  # two days
    day1 = nrel.to_slots(hourly, day=1, num_slots=24)
    assert np.array_equal(day1, np.arange(24, 48))


def test_to_slots_aggregates_into_blocks():
    hourly = np.ones(24)  # 1 kWh each hour, one day
    slots = nrel.to_slots(hourly, day=0, num_slots=6)
    assert slots.shape == (6,)
    assert np.allclose(slots, 4.0)  # each 4-hour slot sums to 4 kWh


def test_to_slots_rejects_indivisible_and_short():
    with pytest.raises(ValueError, match="divide 24"):
        nrel.to_slots(np.ones(24), day=0, num_slots=5)
    with pytest.raises(ValueError, match="not enough hourly data"):
        nrel.to_slots(np.ones(24), day=1, num_slots=24)


# --- fetch_pvwatts parsing (no network) --------------------------------------

def test_fetch_pvwatts_converts_watts_to_kwh(monkeypatch):
    fake = {"errors": [], "outputs": {"ac": [2000.0] * 8760}}  # 2000 W -> 2 kWh
    monkeypatch.setattr(nrel, "_get_json", lambda *a, **k: fake)

    ac = nrel.fetch_pvwatts(39.7, -105.2, 4.0, api_key="x", cache_dir=None)
    assert ac.shape == (8760,)
    assert np.allclose(ac, 2.0)


def test_fetch_pvwatts_raises_on_api_error(monkeypatch):
    monkeypatch.setattr(nrel, "_get_json", lambda *a, **k: {"errors": ["bad key"]})
    with pytest.raises(RuntimeError, match="PVWatts API error"):
        nrel.fetch_pvwatts(0, 0, 1.0, api_key="x", cache_dir=None)


def test_get_json_uses_cache_without_network(tmp_path):
    # Pre-seed the cache; _get_json must return it without any HTTP call.
    params = {"api_key": "secret", "lat": 1, "lon": 2, "timeframe": "hourly"}
    import hashlib
    import urllib.parse

    cache_key = nrel.PVWATTS_ENDPOINT + "?" + urllib.parse.urlencode(
        {k: v for k, v in sorted(params.items()) if k != "api_key"}
    )
    digest = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
    (tmp_path / f"{digest}.json").write_text(json.dumps({"cached": True}))

    result = nrel._get_json(nrel.PVWATTS_ENDPOINT, params, cache_dir=tmp_path)
    assert result == {"cached": True}


def test_error_response_not_cached_then_success_cached(monkeypatch, tmp_path):
    payloads = [
        {"errors": ["bad key"], "outputs": {}},              # first call fails
        {"errors": [], "outputs": {"ac": [1000.0] * 8760}},  # second call succeeds
    ]

    def fake_urlopen(request, timeout=None):
        return io.BytesIO(json.dumps(payloads.pop(0)).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    params = {"api_key": "secret", "lat": 1, "lon": 2, "timeframe": "hourly"}

    first = nrel._get_json(nrel.PVWATTS_ENDPOINT, params, cache_dir=tmp_path)
    assert first.get("errors")                        # error is surfaced...
    assert list(tmp_path.glob("*.json")) == []        # ...but never cached

    second = nrel._get_json(nrel.PVWATTS_ENDPOINT, params, cache_dir=tmp_path)
    assert not second.get("errors")                   # a later success...
    assert len(list(tmp_path.glob("*.json"))) == 1    # ...is cached


# --- load_nrel_instance (no network) -----------------------------------------

def test_load_nrel_instance_real_generation_and_price(monkeypatch):
    hourly = np.tile(np.linspace(0.0, 3.0, 24), 366)  # deterministic daily curve
    price24 = np.full(24, 0.2)
    price24[17:21] = 0.4  # on-peak block
    monkeypatch.setattr(nrel, "fetch_pvwatts", lambda *a, **k: hourly)
    monkeypatch.setattr(nrel, "fetch_urdb_tou", lambda *a, **k: price24)

    problem = nrel.load_nrel_instance(39.7, -105.2, day=10, num_slots=24, capacity=8.0)
    assert problem.num_slots == 24
    assert problem.capacity == 8.0
    assert np.allclose(problem.generation, nrel.to_slots(hourly, 10, 24))  # real solar
    assert np.allclose(problem.price, price24)                              # real price (identity @24)
    assert problem.load.shape == (24,)                                      # synthetic load


def test_load_nrel_instance_rejects_non_hourly(monkeypatch):
    monkeypatch.setattr(nrel, "fetch_pvwatts", lambda *a, **k: np.zeros(8760))
    with pytest.raises(ValueError, match="only num_slots=24"):
        nrel.load_nrel_instance(39.7, -105.2, num_slots=12)


# --- API key resolution ------------------------------------------------------

def test_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("NREL_API_KEY", "env-key-123")
    assert config.nrel_api_key() == "env-key-123"


def test_api_key_falls_back_to_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("NREL_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('NREL_API_KEY="file-key-456"\n# comment\n')
    monkeypatch.setattr(config, "_REPO_ROOT", tmp_path)
    assert config.nrel_api_key() == "file-key-456"


def test_api_key_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("NREL_API_KEY", raising=False)
    monkeypatch.setattr(config, "_REPO_ROOT", tmp_path)  # no .env here
    with pytest.raises(RuntimeError, match="NREL_API_KEY is not set"):
        config.nrel_api_key()


def test_api_key_ignores_placeholder(monkeypatch, tmp_path):
    monkeypatch.setenv("NREL_API_KEY", "REPLACE_ME")
    monkeypatch.setattr(config, "_REPO_ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="NREL_API_KEY is not set"):
        config.nrel_api_key()


# --- price_to_slots (intensive resampling: average, never sum) ---------------

def test_price_to_slots_constant_survives():
    prices = np.full(24, 0.15)
    for num_slots in (1, 2, 3, 4, 6, 8, 12, 24):
        assert np.allclose(nrel.price_to_slots(prices, num_slots), 0.15)


def test_price_to_slots_preserves_average():
    prices = np.arange(24, dtype=float)
    for num_slots in (1, 2, 3, 4, 6, 8, 12, 24):
        resampled = nrel.price_to_slots(prices, num_slots)
        assert resampled.shape == (num_slots,)
        assert np.isclose(resampled.mean(), prices.mean())


def test_price_to_slots_validation():
    with pytest.raises(ValueError, match="divide 24"):
        nrel.price_to_slots(np.ones(24), 5)
    with pytest.raises(ValueError, match="24 hourly prices"):
        nrel.price_to_slots(np.ones(12), 6)


# --- URDB TOU parsing against a committed real fixture (no network) -----------

def _load_urdb_fixture():
    return json.loads((FIXTURES / "urdb_xcel_co_retou.json").read_text())


def test_fetch_urdb_tou_parses_summer_weekday(monkeypatch):
    monkeypatch.setattr(nrel, "_get_json", lambda *a, **k: _load_urdb_fixture())
    prices = nrel.fetch_urdb_tou("label", month=6, cache_dir=None, api_key="x")

    assert prices.shape == (24,)
    # Xcel RE-TOU summer weekday: on-peak block at hours 17-20, off-peak elsewhere.
    assert np.allclose(prices[17:21], prices[17])
    assert np.isclose(prices[0], 0.13926)   # off-peak
    assert np.isclose(prices[18], 0.38109)  # on-peak


def test_urdb_tariff_is_valid_tou(monkeypatch):
    monkeypatch.setattr(nrel, "_get_json", lambda *a, **k: _load_urdb_fixture())
    prices = nrel.fetch_urdb_tou("label", month=6, cache_dir=None, api_key="x")

    assert (prices > 0).all()                 # all prices positive
    assert prices.max() > prices.min()        # peak strictly above off-peak
    assert len(np.unique(prices)) >= 2        # flat vector => TOU extraction failed


# --- live integration (network + real key; skipped otherwise) ----------------

@pytest.mark.slow
def test_pvwatts_live():
    try:
        key = config.nrel_api_key()
    except RuntimeError:
        pytest.skip("no NREL_API_KEY configured")
    if os.environ.get("QS_SKIP_NETWORK"):
        pytest.skip("network disabled")

    system_kw = 4.0
    ac = nrel.fetch_pvwatts(39.74, -105.18, system_kw, cache_dir=None, api_key=key)
    assert ac.shape == (8760,)
    assert ac.min() >= 0.0 and ac.max() > 0.0
    # Physical plausibility: annual yield per installed kW. A unit error (e.g.
    # W vs kW, or summing vs averaging) would blow through this band.
    annual_per_kw = float(ac.sum()) / system_kw
    assert 700.0 <= annual_per_kw <= 2200.0


@pytest.mark.slow
def test_urdb_live():
    try:
        key = config.nrel_api_key()
    except RuntimeError:
        pytest.skip("no NREL_API_KEY configured")
    if os.environ.get("QS_SKIP_NETWORK"):
        pytest.skip("network disabled")

    prices = nrel.fetch_urdb_tou(nrel.XCEL_CO_RETOU_LABEL, month=6, cache_dir=None, api_key=key)
    assert prices.shape == (24,)
    assert (prices > 0).all()
    assert prices.max() > prices.min()      # real TOU spread
    assert len(np.unique(prices)) >= 2
