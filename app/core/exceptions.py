"""Shared exception hierarchy for the Signal Intelligence Platform.

Every layer raises subclasses of :class:`AppError` so callers can catch
failures at the granularity they care about (e.g. ``except RepositoryError``)
without needing to know which concrete implementation raised them.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for every exception raised by this application."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, object] = details or {}


class ConfigurationError(AppError):
    """Raised when configuration is missing, malformed, or invalid."""


class ValidationError(AppError):
    """Raised when a domain model fails validation beyond what Pydantic enforces."""


class DomainError(AppError):
    """Base class for errors raised by domain logic."""


class InvalidSignalError(DomainError):
    """Raised when a Signal cannot be constructed or is internally inconsistent."""


class InvalidLeadError(DomainError):
    """Raised when a Lead cannot be constructed or is internally inconsistent."""


class InvalidRuleError(DomainError):
    """Raised when a Rule definition is malformed."""


class RepositoryError(AppError):
    """Base class for persistence-layer failures."""


class EntityNotFoundError(RepositoryError):
    """Raised when a requested entity does not exist in the repository."""


class DuplicateEntityError(RepositoryError):
    """Raised when attempting to persist an entity that already exists."""


class CollectorError(AppError):
    """Base class for errors raised while collecting signals from a source."""


class CollectorUnavailableError(CollectorError):
    """Raised when a collector's upstream source cannot be reached."""


class VerificationError(AppError):
    """Base class for errors raised during signal or lead verification."""


class CorrelationError(AppError):
    """Base class for errors raised by the correlation engine."""


class RuleEngineError(AppError):
    """Base class for errors raised by the rule engine."""


class RuleEvaluationError(RuleEngineError):
    """Raised when a rule cannot be evaluated against a signal cluster."""


class LeadGenerationError(AppError):
    """Base class for errors raised while generating leads from rule matches."""


class RetryExhaustedError(AppError):
    """Raised when an operation exhausts its configured retry budget."""

    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        last_exception: BaseException | None = None,
    ) -> None:
        super().__init__(message, details={"attempts": attempts})
        self.attempts = attempts
        self.last_exception = last_exception


class ExportError(AppError):
    """Raised when exporting leads or signals to an external format fails."""


class RollbackError(AppError):
    """Base class for errors that prevent a collector-run rollback from proceeding safely."""


class CorruptedRollbackMetadataError(RollbackError):
    """Raised when an audit entry's rollback metadata cannot be trusted.

    Covers a malformed ``execution_id``, a non-list ``inserted_signal_ids``/
    ``inserted_event_ids``, or an entry containing a value that does not
    parse as a UUID. Rollback must never guess or coerce this data -- if it
    cannot be parsed exactly as written, deletion must not proceed.
    """


class RollbackBlockedByDependentDataError(RollbackError):
    """Raised when rollback would delete Signals still cited by an existing Lead.

    Deleting a Signal that a Lead's ``supporting_signal_ids`` still
    references would leave that Lead pointing at a record that no longer
    exists. Rollback refuses rather than silently deleting the Signal or
    silently rewriting the Lead -- see
    ``app.application.services.rollback_service.RollbackService`` for the
    full rationale.
    """


class RollbackConflictError(RollbackError):
    """Raised when another process already rolled back this exact run.

    Detected by a second, authoritative check made *after* this
    transaction has taken SQLite's write lock (see
    ``app.repositories.sqlite.rollback_unit_of_work.SQLiteRollbackUnitOfWork``),
    so this can only fire on a genuine race between two concurrent
    ``sigint rollback`` invocations -- never on an ordinary second run,
    which is instead reported as ``EntityNotFoundError`` by
    ``RollbackService`` before any transaction is opened.
    """
