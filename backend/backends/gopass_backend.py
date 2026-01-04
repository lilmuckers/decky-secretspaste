import asyncio
import json
import secrets
import subprocess
import time
from pathlib import Path
from shutil import which
from typing import Any, Dict, List, Optional

import decky_plugin

from .base import VaultBackend


class GopassError(RuntimeError):
    pass


class GopassBackend(VaultBackend):
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.secrets_file = self.data_dir / "secrets.json"
        self.gopass_prefix = "secretspaste"
        self.gopass_bin = which("gopass")
        self.lock = asyncio.Lock()
        self.secrets: List[Dict[str, Any]] = self._load_secrets()

    def _ensure_gopass(self) -> None:
        if not self.gopass_bin:
            raise GopassError("gopass is not installed or not on PATH.")

    def _secret_path(self, secret_id: str) -> str:
        return f"{self.gopass_prefix}/{secret_id}"

    def _run_gopass(self, args: List[str], stdin: Optional[str] = None) -> str:
        self._ensure_gopass()
        cmd = [self.gopass_bin, *args]
        result = subprocess.run(
            cmd,
            input=stdin.encode("utf-8") if stdin is not None else None,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="ignore").strip()
            stdout = result.stdout.decode("utf-8", errors="ignore").strip()
            message = stderr or stdout or "gopass command failed"
            raise GopassError(message)
        return result.stdout.decode("utf-8", errors="ignore")

    def _load_secrets(self) -> List[Dict[str, Any]]:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.secrets_file.exists():
            return []
        try:
            data = json.loads(self.secrets_file.read_text(encoding="utf-8"))
            return data.get("secrets", [])
        except Exception as err:  # noqa: BLE001
            decky_plugin.logger.error(f"Failed to read secrets metadata: {err}")
            return []

    def _persist_secrets(self) -> None:
        payload = {"secrets": self.secrets}
        self.secrets_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    async def add_secret(self, name: str, value: str) -> Dict[str, Any]:
        async with self.lock:
            secret_id = secrets.token_hex(8)
            path = self._secret_path(secret_id)
            created_at = int(time.time())
            try:
                self._run_gopass(["insert", "-f", "-n", path], stdin=value + "\n")
            except Exception as err:  # noqa: BLE001
                decky_plugin.logger.error(f"Failed to insert secret into gopass: {err}")
                raise
            record = {"id": secret_id, "name": name, "created_at": created_at}
            self.secrets.append(record)
            self._persist_secrets()
            return record

    async def delete_secret(self, secret_id: str) -> bool:
        async with self.lock:
            target = next((s for s in self.secrets if s.get("id") == secret_id), None)
            if not target:
                return False
            path = self._secret_path(secret_id)
            try:
                self._run_gopass(["rm", "-f", path])
            except Exception as err:  # noqa: BLE001
                decky_plugin.logger.error(f"Failed to remove secret from gopass: {err}")
                return False
            self.secrets = [s for s in self.secrets if s.get("id") != secret_id]
            self._persist_secrets()
            return True

    async def list_secrets(self) -> List[Dict[str, Any]]:
        async with self.lock:
            return [
                {"id": s["id"], "name": s["name"], "created_at": s.get("created_at", 0)}
                for s in sorted(self.secrets, key=lambda item: item.get("created_at", 0), reverse=True)
            ]

    async def get_secret(self, secret_id: str) -> Optional[Dict[str, str]]:
        async with self.lock:
            found = next((s for s in self.secrets if s.get("id") == secret_id), None)
            if not found:
                return None
            path = self._secret_path(secret_id)
            try:
                value = self._run_gopass(["show", "-o", path]).strip()
            except Exception as err:  # noqa: BLE001
                decky_plugin.logger.error(f"Failed to read secret from gopass: {err}")
                return None
            return {"id": found["id"], "name": found["name"], "value": value}
