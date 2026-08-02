"""Data loaders for real solar/pricing inputs (NREL; EIA planned)."""

from .calendar import day_to_month, day_type, is_weekend
from .config import NLR_BASE, nrel_api_key
from .load_profile import co_summer_weekday_load, load_profile
from .nrel import (
    XCEL_CO_RETOU_LABEL,
    build_instance,
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
    "load_profile",
    "build_instance",
    "load_nrel_instance",
    "XCEL_CO_RETOU_LABEL",
    "day_to_month",
    "is_weekend",
    "day_type",
]
