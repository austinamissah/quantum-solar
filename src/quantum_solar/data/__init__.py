"""Data loaders for real solar/pricing inputs (NREL; EIA planned)."""

from .config import NLR_BASE, nrel_api_key
from .nrel import fetch_pvwatts, load_nrel_instance, to_slots

__all__ = [
    "nrel_api_key",
    "NLR_BASE",
    "fetch_pvwatts",
    "to_slots",
    "load_nrel_instance",
]
