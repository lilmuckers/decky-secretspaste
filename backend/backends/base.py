from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class VaultBackend(ABC):
    @abstractmethod
    async def add_secret(self, name: str, value: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def delete_secret(self, secret_id: str) -> bool:
        ...

    @abstractmethod
    async def list_secrets(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def get_secret(self, secret_id: str) -> Optional[Dict[str, str]]:
        ...

    def status(self) -> Dict[str, bool]:
        return {"password_required": False, "locked": False}
