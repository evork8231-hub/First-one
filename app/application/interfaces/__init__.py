"""Abstract interfaces the application layer depends on.

Every class in this package is an ``abc.ABC``. Infrastructure packages
(``app.repositories``, ``app.collectors``, ``app.verification``,
``app.correlation``, ``app.rule_engine``) provide concrete implementations
and are wired together at composition time in ``app.core.container`` --
the application and domain layers never import those infrastructure
packages directly.
"""
