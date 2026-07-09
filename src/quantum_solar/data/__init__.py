"""Data loaders for real solar/pricing inputs (NREL; EIA planned)."""

from .config import NLR_BASE, nrel_api_key
from .load_profile import co_summer_weekday_load
from .nrel import (
    XCEL_CO_RETOU_LABEL,
    fetch_pvwatts,
    fetch_urdb_tou,
    load_nrel_instance,
    price_to_slots,
    to_slots,
)

__all__ = [
    "nrel_api_key",
    "NLR_BASE",
    "fetch_pvwatts",
    "fetch_urdb_tou",
    "to_slots",
    "price_to_slots",
    "co_summer_weekday_load",
    "load_nrel_instance",
    "XCEL_CO_RETOU_LABEL",
]
