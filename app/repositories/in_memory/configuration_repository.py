"""In-memory ConfigurationRepository implementation, used primarily in tests."""

from __future__ import annotations

from app.application.interfaces.repositories import ConfigurationRepository
from app.domain.configuration import ConfigurationEntry


class InMemoryConfigurationRepository(ConfigurationRepository):
    """Stores ConfigurationEntry records in a process-local dict. Not safe across processes."""

    def __init__(self) -> None:
        self._entries: dict[str, ConfigurationEntry] = {}

    def get(self, key: str) -> ConfigurationEntry | None:
        return self._entries.get(key)

    def set(self, entry: ConfigurationEntry) -> ConfigurationEntry:
        self._entries[entry.key] = entry
        return entry

    def list_all(self) -> list[ConfigurationEntry]:
        return sorted(self._entries.values(), key=lambda entry: entry.key)
