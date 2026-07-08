"""Data loaders for real solar/pricing inputs (NREL; EIA planned)."""

from .config import NLR_BASE, nrel_api_key
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
    "load_nrel_instance",
    "XCEL_CO_RETOU_LABEL",
]
