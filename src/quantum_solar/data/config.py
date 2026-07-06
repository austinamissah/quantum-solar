"""Configuration and secrets for the data loaders.

The NREL API key is resolved from the environment first, then from the repo-root
``.env`` file (which is gitignored). NREL's developer platform moved to
``developer.nlr.gov`` in May 2026 — the old ``developer.nrel.gov`` is retired.
"""

from __future__ import annotations

import os
from pathlib import Path

NLR_BASE = "https://developer.nlr.gov/api"
_ENV_VAR = "NREL_API_KEY"
_PLACEHOLDER = "REPLACE_ME"

# Repo root, relative to this module: src/quantum_solar/data/config.py
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def nrel_api_key() -> str:
    """Return the NREL API key from ``os.environ`` or the repo-root ``.env``.

    Raises ``RuntimeError`` with actionable guidance if it is unset or still the
    placeholder.
    """
    key = os.environ.get(_ENV_VAR)
    if key and key != _PLACEHOLDER:
        return key

    env_file = _REPO_ROOT / ".env"
    if env_file.is_file():
        key = _parse_env_file(env_file).get(_ENV_VAR)
        if key and key != _PLACEHOLDER:
            return key

    raise RuntimeError(
        f"{_ENV_VAR} is not set. Export it, or set it in the repo-root .env "
        f"(get a free key at https://developer.nlr.gov/signup/)."
    )
