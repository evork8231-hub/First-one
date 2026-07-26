"""Application layer: use-case orchestration.

Depends only on ``app.domain`` and on the interfaces declared in
``app.application.interfaces``. Never imports a concrete infrastructure
implementation (no SQLAlchemy sessions, no httpx clients) -- those are
injected via the interfaces at composition time by
``app.core.container``.
"""
