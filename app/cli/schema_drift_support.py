"""Shared, exception-safe wrapper around ``SchemaDriftDetector.check()`` for the CLI layer.

Both ``collect_cmd.py`` and ``pipeline_cmd.py`` need to run the same
schema-drift check after ingestion and must both honor the same
guarantee: a drift-check failure must never surface as a command
failure, since ingestion has already completed and been persisted by
the time this runs. Kept as one shared function (rather than a
try/except duplicated in both command modules) so there is exactly one
place in the codebase that catches this specific infrastructure
exception.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from app.core.container import Container
from app.verification.schema_drift import SchemaDriftResult


def check_schema_drift_safely(
    container: Container, collector_name: str, raw_payloads: Sequence[Mapping[str, Any]]
) -> SchemaDriftResult | None:
    """Run the schema-drift check, downgrading an infrastructure failure to a warning.

    Returns ``None`` (already logged) if the check itself could not run
    -- e.g. a database error reading/writing the stored fingerprint or
    the drift audit entry. Only ``SQLAlchemyError`` (the real
    infrastructure boundary this call crosses) is caught; a bug in the
    detector's own logic still surfaces normally rather than being
    silently absorbed.
    """
    try:
        return container.schema_drift_detector().check(collector_name, raw_payloads)
    except SQLAlchemyError as exc:
        logger.warning(
            "Schema-drift check for {} could not run due to an infrastructure error "
            "(ingestion already succeeded and is unaffected): {}",
            collector_name,
            exc,
        )
        return None
