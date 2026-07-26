"""Collector implementations.

This package holds infrastructure that reads publicly available sources
and translates them into ``app.domain.signal.Signal`` objects. It depends
on ``app.application.interfaces.collector.CollectorInterface`` (dependency
inversion) but never the reverse.

The foundation intentionally ships no concrete, source-specific collector
(no scraper, no API client) -- only the shared abstract scaffolding and a
registry. Building the first real collector is explicitly out of scope
for this phase; see the STOP CONDITION in the project brief.
"""
