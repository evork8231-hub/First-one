"""Application-wide constants that are not user-configurable.

Values that a deployer or operator might reasonably want to change belong in
``app.config``, not here. This module only holds constants that define the
platform's identity (e.g. the country it targets) or Python-level limits.
"""

from __future__ import annotations

from typing import Final

#: This foundation targets Estonia exclusively. Multi-country support would
#: require extending app.domain.enums.Country and is out of scope for the
#: foundation phase.
PRIMARY_COUNTRY_CODE: Final[str] = "EE"

#: ISO 3166-1 alpha-2 codes this deployment is permitted to operate in.
SUPPORTED_COUNTRY_CODES: Final[frozenset[str]] = frozenset({PRIMARY_COUNTRY_CODE})

#: Confidence and score values are normalized floats in [0.0, 1.0].
MIN_SCORE: Final[float] = 0.0
MAX_SCORE: Final[float] = 1.0

#: Default application-level timezone name used for timestamp normalization.
DEFAULT_TIMEZONE: Final[str] = "Europe/Tallinn"
