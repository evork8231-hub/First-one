"""A disabled, credential-gated adapter for Ehitisregister's X-tee access path.

X-tee (Estonia's secure inter-organizational data-exchange layer, part of
the X-Road architecture) is a real, government-documented access method
for Ehitisregister -- confirmed via a RIHA (State Information System's
registry) document describing X-tee query services implemented by the
Building Register, including lookups by building code (``EHR_KOOD``),
cadastral/address identifier (``ADS_OID``), and internal technical key
(``EHIT_ID``). See ``docs/COLLECTORS.md#ehitisregister`` for the research
that established this.

Unlike the public Open Data portal collector
(``app.collectors.ehitisregister_collector.EhitisregisterCollector``),
X-tee access requires the calling party to be a **registered X-tee
member** operating a security server with member certificates -- this
platform cannot obtain or provision that on an operator's behalf, and
this collector never pretends otherwise.

This class exists to be a correctly-scoped scaffold, not a working
integration:

- The generic X-Road client/service identity model (member class/code,
  subsystem, security server, certificates) is a stable, publicly
  standardized concept independent of Ehitisregister specifically, so the
  configuration surface for it is real and complete
  (``app.config.settings.EhitisregisterXTeeConfig``).
- The *operation-specific* request/response schema for Ehitisregister's
  X-tee service (the actual SOAP body an operator's confirmed WSDL would
  define) was never verified against a live or documented source in this
  environment. Fabricating it would violate this platform's core rule
  against inventing API behavior, so ``collect()`` never attempts a
  request -- it validates configuration completeness and then explains,
  precisely, what is still missing before this adapter could become real.

An operator who has completed X-tee member registration and obtained
Ehitisregister's actual WSDL/service catalog is the only party who can
finish this integration; this file marks exactly where that work begins.
"""

from __future__ import annotations

from app.collectors.base import BaseCollector
from app.config.settings import EhitisregisterXTeeConfig
from app.core.exceptions import CollectorError
from app.core.retry import RetryPolicy
from app.domain.enums import SignalType
from app.domain.signal import Signal

#: Fields an operator must supply, purely to establish X-tee connectivity,
#: before this adapter will even attempt to describe what else is missing.
_REQUIRED_IDENTITY_FIELDS: tuple[str, ...] = (
    "security_server_url",
    "xroad_instance",
    "member_class",
    "member_code",
    "client_cert_path",
    "client_key_path",
)

#: Fields identifying the target service -- these can only come from an
#: operator's own confirmed X-tee/WSDL access, never guessed here.
_REQUIRED_SERVICE_FIELDS: tuple[str, ...] = (
    "service_member_class",
    "service_member_code",
    "service_code",
    "service_version",
)


class EhitisregisterXTeeCollector(BaseCollector):
    """A structurally disabled adapter for Ehitisregister's X-tee access path.

    ``collect()`` never returns data. It always raises ``CollectorError``,
    with a message that depends on how far the configuration has
    progressed, so an operator working through enablement gets an
    accurate next step rather than one generic failure.
    """

    def __init__(
        self, config: EhitisregisterXTeeConfig, *, retry_policy: RetryPolicy | None = None
    ) -> None:
        super().__init__(
            name="ehitisregister_xtee",
            source="Ehitisregister (Estonian Building Registry) via X-tee",
            supported_signal_types=frozenset(
                {SignalType.BUILDING_RECORD, SignalType.ENERGY_CERTIFICATE}
            ),
            retry_policy=retry_policy or RetryPolicy(max_retries=0),
        )
        self._config = config

    async def collect(self) -> list[Signal]:
        if not self._config.enabled:
            raise CollectorError(
                "ehitisregister_xtee is disabled. This adapter requires a real X-tee member "
                "agreement, a security server, and member certificates that this platform "
                "cannot provision -- set 'collectors.ehitisregister_xtee.enabled: true' (in "
                "addition to listing 'ehitisregister_xtee' in collectors.enabled) only after "
                "you have arranged those, then see the next error for what else is required."
            )

        missing_identity = [
            field for field in _REQUIRED_IDENTITY_FIELDS if getattr(self._config, field) is None
        ]
        if missing_identity:
            raise CollectorError(
                "ehitisregister_xtee is enabled but missing required X-tee client identity/"
                f"connectivity configuration: {', '.join(missing_identity)}. These come from "
                "your organization's own X-tee member registration and security server setup "
                "(see docs/COLLECTORS.md#ehitisregister), not from this platform."
            )

        missing_service = [
            field for field in _REQUIRED_SERVICE_FIELDS if getattr(self._config, field) is None
        ]
        if missing_service:
            raise CollectorError(
                "ehitisregister_xtee is enabled with valid client identity, but missing the "
                f"target service identifiers: {', '.join(missing_service)}. These identify "
                "Ehitisregister's own X-tee service and must come from your organization's "
                "confirmed WSDL/service catalog access -- see the RIHA X-tee services document "
                "referenced in docs/COLLECTORS.md#ehitisregister; this platform has not "
                "verified them and will not guess them."
            )

        raise CollectorError(
            "ehitisregister_xtee is fully configured, but the operation-specific X-tee request "
            "and response schema for Ehitisregister was never verified against a live or "
            "documented source in this environment -- only the generic X-Road envelope shape "
            "is standardized, not Ehitisregister's own service body. Fabricating it would "
            "violate this platform's rule against inventing undocumented API behavior. "
            "Extend this collector's collect() method with your organization's confirmed "
            "request/response mapping to complete this integration; until then it remains "
            "disabled by design. Prefer the 'ehitisregister' (Open Data portal) collector, "
            "which requires no credentials, if it covers the fields you need."
        )
