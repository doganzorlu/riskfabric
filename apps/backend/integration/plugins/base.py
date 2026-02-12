from abc import ABC, abstractmethod
from typing import Any


class EamIntegrationPlugin(ABC):
    plugin_name: str
    plugin_version: str

    @abstractmethod
    def run(self, *, direction: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError
