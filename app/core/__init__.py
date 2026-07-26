"""Cross-cutting, dependency-free primitives shared by every layer.

Nothing in ``app.core`` may import from ``app.domain``, ``app.application``,
or any infrastructure package. This keeps it safe to import from anywhere
without creating cycles or violating Clean Architecture's inward-pointing
dependency rule.
"""
