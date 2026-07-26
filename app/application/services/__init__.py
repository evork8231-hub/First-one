"""Use-case orchestration services.

Each service composes one or more repository/collector/verifier/engine
interfaces to implement a single stage of the
Public Data -> Signals -> Verification -> Storage -> Correlation ->
Leads -> Verification -> Scoring -> Export pipeline. Services never talk
to each other's storage directly; they pass domain objects.
"""
