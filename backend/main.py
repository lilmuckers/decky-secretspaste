import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import decky_plugin
from backends import GopassBackend, LocalVaultBackend, VaultBackend


class SecretStore:
    def __init__(self) -> None:
        self.data_dir = Path(decky_plugin.DECKY_PLUGIN_SETTINGS_DIR)
        self.config_file = self.data_dir / "config.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.clipboard_timeout = self._load_clipboard_timeout()
        self.vault_backend = "gopass"
        self._load_backend_choice()
        self.backends: Dict[str, VaultBackend] = {
            "gopass": GopassBackend(self.data_dir),
            "local": LocalVaultBackend(self.data_dir),
        }
        self.lock = asyncio.Lock()

    def _load_backend_choice(self) -> None:
        if not self.config_file.exists():
            return
        try:
            data = json.loads(self.config_file.read_text(encoding="utf-8"))
            self.vault_backend = data.get("vault_backend", "gopass")
        except Exception as err:  # noqa: BLE001
            decky_plugin.logger.error(f"Failed to read config: {err}")

    def _persist_config(self) -> None:
        payload = {
            "clipboard_timeout": self.clipboard_timeout,
            "vault_backend": self.vault_backend,
        }
        self.config_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_clipboard_timeout(self) -> int:
        default_timeout = 20
        if not self.config_file.exists():
            return default_timeout
        try:
            data = json.loads(self.config_file.read_text(encoding="utf-8"))
            return int(data.get("clipboard_timeout", default_timeout))
        except Exception as err:  # noqa: BLE001
            decky_plugin.logger.error(f"Failed to read config: {err}")
            return default_timeout

    def _backend(self) -> VaultBackend:
        return self.backends.get(self.vault_backend, self.backends["gopass"])

    async def add_secret(self, name: str, value: str) -> Dict[str, Any]:
        async with self.lock:
            return await self._backend().add_secret(name, value)

    async def delete_secret(self, secret_id: str) -> bool:
        async with self.lock:
            return await self._backend().delete_secret(secret_id)

    async def list_secrets(self) -> List[Dict[str, Any]]:
        async with self.lock:
            return await self._backend().list_secrets()

    async def get_secret(self, secret_id: str) -> Optional[Dict[str, str]]:
        async with self.lock:
            return await self._backend().get_secret(secret_id)

    async def set_clipboard_timeout(self, seconds: int) -> int:
        async with self.lock:
            seconds = max(1, min(int(seconds), 300))
            self.clipboard_timeout = seconds
            self._persist_config()
            return self.clipboard_timeout

    async def get_clipboard_timeout(self) -> int:
        async with self.lock:
            return self.clipboard_timeout

    async def set_vault_backend(self, backend: str) -> Dict[str, Any]:
        async with self.lock:
            if backend not in self.backends:
                raise ValueError("Invalid backend")
            self.vault_backend = backend
            self._persist_config()
            return await self.status()

    async def configure_local_vault(self, password: str) -> Dict[str, Any]:
        async with self.lock:
            local_backend = self.backends["local"]
            if not hasattr(local_backend, "configure_password"):
                return await self.status()
            result = local_backend.configure_password(password)  # type: ignore[attr-defined]
            return await self.status(extra=result)

    async def unlock_local_vault(self, password: str) -> Dict[str, Any]:
        async with self.lock:
            local_backend = self.backends["local"]
            if not hasattr(local_backend, "unlock"):
                return await self.status()
            unlocked = local_backend.unlock(password)  # type: ignore[attr-defined]
            status = local_backend.status()
            status["unlocked"] = unlocked and not status.get("locked", False)
            return await self.status(extra=status)

    async def status(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        base = {
            "vault_backend": self.vault_backend,
            "clipboard_timeout": self.clipboard_timeout,
            "local_status": self.backends["local"].status(),
        }
        if extra:
            base.update(extra)
        return base


class Plugin:
    def __init__(self) -> None:
        self.store = SecretStore()

    async def _main(self) -> None:
        decky_plugin.logger.info("SecretsPaste backend ready")

    async def _unload(self) -> None:
        decky_plugin.logger.info("SecretsPaste backend unloaded")

    async def add_secret(self, name: str, value: str) -> Dict[str, Any]:
        return await self.store.add_secret(name, value)

    async def delete_secret(self, secret_id: str) -> bool:
        return await self.store.delete_secret(secret_id)

    async def list_secrets(self) -> List[Dict[str, Any]]:
        return await self.store.list_secrets()

    async def get_secret(self, secret_id: str) -> Optional[Dict[str, str]]:
        return await self.store.get_secret(secret_id)

    async def set_clipboard_timeout(self, seconds: int) -> int:
        return await self.store.set_clipboard_timeout(seconds)

    async def get_clipboard_timeout(self) -> int:
        return await self.store.get_clipboard_timeout()

    async def set_vault_backend(self, backend: str) -> Dict[str, Any]:
        return await self.store.set_vault_backend(backend)

    async def configure_local_vault(self, password: str) -> Dict[str, Any]:
        return await self.store.configure_local_vault(password)

    async def unlock_local_vault(self, password: str) -> Dict[str, Any]:
        return await self.store.unlock_local_vault(password)

    async def get_status(self) -> Dict[str, Any]:
        return await self.store.status()
