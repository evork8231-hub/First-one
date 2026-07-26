"""Rule engine implementation.

Evaluates data-driven ``app.domain.rule.Rule`` definitions against
``SignalCluster`` instances produced by the correlation engine. Rules
themselves are never hardcoded in Python; see ``app.rule_engine.loader``
for how they are read from YAML configuration.
"""
