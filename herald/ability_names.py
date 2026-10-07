"""Pinned English ability labels, loaded offline with no runtime dependencies.

The asset records its OpenDota source commit, version and license. This is a
presentation-only snapshot, not a patch-aware ability registry. Missing labels
return None so callers can keep their existing internal-name or numeric fallback.
"""

import json
from pathlib import Path


_NAMES = json.loads(
    (Path(__file__).parent / "assets" / "ability_names.json").read_text(encoding="utf-8")
)["names"]


def localized_name(internal_name: str | None) -> str | None:
    """Return the source's literal English label, or None when unverified."""
    return _NAMES.get(internal_name)
