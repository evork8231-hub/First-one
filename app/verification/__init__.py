"""Verification implementations.

Verification is pluggable: any number of ``SignalVerifier`` or
``LeadVerifier`` implementations can be registered with
``app.application.services.verification_service.VerificationService``. The
foundation ships structural verifiers only -- they check internal
consistency of already-collected data. Verifiers that cross-reference an
external public registry are a future phase.
"""
