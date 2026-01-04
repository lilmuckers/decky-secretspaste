import base64
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import decky_plugin
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .base import VaultBackend


class LocalVaultBackend(VaultBackend):
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.vault_file = self.data_dir / "local_vault.json"
        self.master_info_file = self.data_dir / "local_vault_master.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._fernet: Optional[Fernet] = None
        self._master_key: Optional[bytes] = None
        self._password_required = False
        self._load_master_info()

    def _load_master_info(self) -> None:
        if not self.master_info_file.exists():
            return
        try:
            info = json.loads(self.master_info_file.read_text(encoding="utf-8"))
            self._password_required = bool(info.get("password_required", False))
        except Exception as err:  # noqa: BLE001
            decky_plugin.logger.error(f"Failed to read local master info: {err}")

    def _derive_wrap_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=200_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    def _save_master(self, wrapped_key: str, salt: str, password_required: bool) -> None:
        payload = {
            "wrapped_key": wrapped_key,
            "salt": salt,
            "password_required": password_required,
        }
        self.master_info_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._password_required = password_required

    def _load_wrapped(self) -> Optional[Dict[str, str]]:
        if not self.master_info_file.exists():
            return None
        try:
            info = json.loads(self.master_info_file.read_text(encoding="utf-8"))
            if "wrapped_key" not in info or "salt" not in info:
                return None
            return {
                "wrapped_key": info["wrapped_key"],
                "salt": info["salt"],
                "password_required": bool(info.get("password_required", False)),
            }
        except Exception as err:  # noqa: BLE001
            decky_plugin.logger.error(f"Failed to load wrapped key: {err}")
            return None

    def _ensure_master(self) -> None:
        if self._fernet is not None:
            return
        wrapped = self._load_wrapped()
        if wrapped is None:
            master_key = Fernet.generate_key()
            self._fernet = Fernet(master_key)
            self._master_key = master_key
            self._save_master(
                master_key.decode("utf-8"),
                base64.urlsafe_b64encode(os.urandom(16)).decode("utf-8"),
                False,
            )
            return
        if not wrapped["password_required"]:
            try:
                master_key = wrapped["wrapped_key"].encode("utf-8")
                self._fernet = Fernet(master_key)
                self._master_key = master_key
            except Exception as err:  # noqa: BLE001
                decky_plugin.logger.error(f"Failed to load local master key: {err}")
                raise
        else:
            # Locked until unlocked explicitly
            self._fernet = None
            self._master_key = None

    def unlock(self, password: str) -> bool:
        wrapped = self._load_wrapped()
        if not wrapped or not wrapped["password_required"]:
            self._ensure_master()
            return True
        try:
            salt = base64.urlsafe_b64decode(wrapped["salt"])
            wrap_key = self._derive_wrap_key(password, salt)
            wrapper = Fernet(wrap_key)
            master_key = wrapper.decrypt(wrapped["wrapped_key"].encode("utf-8"))
            self._fernet = Fernet(master_key)
            self._master_key = master_key
            return True
        except Exception as err:  # noqa: BLE001
            decky_plugin.logger.error(f"Unlock failed: {err}")
            self._fernet = None
            self._master_key = None
            return False

    def configure_password(self, password: str) -> Dict[str, bool]:
        self._ensure_master()
        if self._fernet is None:
            return {"password_required": True, "locked": True}
        if not password:
            if not self._master_key:
                return {"password_required": True, "locked": True}
            master_key_b64 = self._master_key.decode("utf-8")
            salt = base64.urlsafe_b64encode(os.urandom(16)).decode("utf-8")
            self._save_master(master_key_b64, salt, False)
            return {"password_required": False, "locked": False}
        salt_bytes = os.urandom(16)
        wrap_key = self._derive_wrap_key(password, salt_bytes)
        wrapper = Fernet(wrap_key)
        if not self._master_key:
            return {"password_required": True, "locked": True}
        wrapped_key = wrapper.encrypt(self._master_key)
        self._save_master(
            wrapped_key.decode("utf-8"),
            base64.urlsafe_b64encode(salt_bytes).decode("utf-8"),
            True,
        )
        return {"password_required": True, "locked": False}

    def _read_data(self) -> Dict[str, Any]:
        if not self.vault_file.exists():
            return {"secrets": []}
        try:
            return json.loads(self.vault_file.read_text(encoding="utf-8"))
        except Exception as err:  # noqa: BLE001
            decky_plugin.logger.error(f"Failed to read local vault: {err}")
            return {"secrets": []}

    def _write_data(self, data: Dict[str, Any]) -> None:
        self.vault_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _require_unlocked(self) -> None:
        self._ensure_master()
        if self._fernet is None:
            raise RuntimeError("Local vault locked")

    async def add_secret(self, name: str, value: str) -> Dict[str, Any]:
        self._require_unlocked()
        data = self._read_data()
        secret_id = secrets.token_hex(8)
        created_at = int(time.time())
        ciphertext = self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        record = {"id": secret_id, "name": name, "created_at": created_at, "ciphertext": ciphertext}
        data.setdefault("secrets", []).append(record)
        self._write_data(data)
        return {"id": secret_id, "name": name, "created_at": created_at}

    async def delete_secret(self, secret_id: str) -> bool:
        self._require_unlocked()
        data = self._read_data()
        secrets_list = data.get("secrets", [])
        before = len(secrets_list)
        data["secrets"] = [s for s in secrets_list if s.get("id") != secret_id]
        self._write_data(data)
        return len(data["secrets"]) != before

    async def list_secrets(self) -> List[Dict[str, Any]]:
        self._require_unlocked()
        data = self._read_data()
        secrets_list = data.get("secrets", [])
        return [
            {"id": s["id"], "name": s["name"], "created_at": s.get("created_at", 0)}
            for s in sorted(secrets_list, key=lambda item: item.get("created_at", 0), reverse=True)
        ]

    async def get_secret(self, secret_id: str) -> Optional[Dict[str, str]]:
        self._require_unlocked()
        data = self._read_data()
        found = next((s for s in data.get("secrets", []) if s.get("id") == secret_id), None)
        if not found:
            return None
        try:
            plaintext = self._fernet.decrypt(found["ciphertext"].encode("utf-8")).decode("utf-8")
            return {"id": found["id"], "name": found["name"], "value": plaintext}
        except Exception as err:  # noqa: BLE001
            decky_plugin.logger.error(f"Failed to decrypt local secret: {err}")
            return None

    def status(self) -> Dict[str, bool]:
        wrapped = self._load_wrapped()
        password_required = bool(wrapped.get("password_required")) if wrapped else False
        locked = password_required and self._fernet is None
        return {"password_required": password_required, "locked": locked}
