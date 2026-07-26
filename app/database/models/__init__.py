"""ORM model registry.

Importing this package registers every table on ``Base.metadata`` --
Alembic's ``env.py`` imports it for autogeneration, and
``app.database.session.create_all_tables`` (test/dev convenience only;
production schema changes go through Alembic) relies on it too.
"""

from app.database.base import Base
from app.database.models.audit_log_model import AuditLogModel
from app.database.models.configuration_model import ConfigurationModel
from app.database.models.lead_model import LeadModel
from app.database.models.signal_model import SignalModel
from app.database.models.weather_model import WeatherEventModel

__all__ = [
    "AuditLogModel",
    "Base",
    "ConfigurationModel",
    "LeadModel",
    "SignalModel",
    "WeatherEventModel",
]
