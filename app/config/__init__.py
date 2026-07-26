"""Configuration system.

Everything an operator might reasonably want to change without a code
change lives here: signal weights, confidence thresholds, lead
thresholds, enabled collectors, retry limits, timeouts, export settings,
database settings, and logging settings. Structured defaults live in
``config/default.yaml`` at the repository root; secrets are read from
environment variables only (see ``docs/CONFIGURATION.md``).
"""
