#!/usr/bin/env python3
import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path
from typing import Any


def _ensure_decky_plugin(settings_dir: Path) -> None:
    try:
        import decky_plugin  # type: ignore # noqa: F401
    except ImportError:
        stub_logger = type(
            "Logger",
            (),
            {
                "info": lambda *args, **kwargs: None,
                "error": lambda *args, **kwargs: None,
                "debug": lambda *args, **kwargs: None,
                "warn": lambda *args, **kwargs: None,
                "warning": lambda *args, **kwargs: None,
            },
        )()
        sys.modules["decky_plugin"] = type(
            "DeckyPlugin", (), {"logger": stub_logger, "DECKY_PLUGIN_SETTINGS_DIR": str(settings_dir)}
        )()
    else:
        import decky_plugin  # type: ignore

        decky_plugin.DECKY_PLUGIN_SETTINGS_DIR = str(settings_dir)


def _prompt_nonempty(prompt: str) -> str:
    while True:
        val = input(prompt).strip()
        if val:
            return val
        print("Value cannot be empty. Try again.")


def _prompt_secret(prompt: str) -> str:
    while True:
        first = getpass.getpass(prompt)
        confirm = getpass.getpass("Confirm secret: ")
        if first == confirm and first:
            return first
        print("Secrets did not match or were empty. Try again.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Add a secret to SecretsPaste via CLI.")
    parser.add_argument("--settings-dir", type=Path, help="Plugin settings directory (defaults to Decky location).")
    parser.add_argument("--backend", choices=["gopass", "local"], help="Override backend (default: current config).")
    parser.add_argument("--unlock", help="Local vault password, if required.")
    args = parser.parse_args()

    settings_dir = (
        args.settings_dir
        or Path(os.environ.get("DECKY_PLUGIN_SETTINGS_DIR", "~/.local/share/Steam/steamui/plugins/secretspaste")).expanduser()
    )
    settings_dir.mkdir(parents=True, exist_ok=True)

    _ensure_decky_plugin(settings_dir)

    from main import SecretStore  # noqa: WPS433 (import after stubbing decky_plugin)

    store = SecretStore()

    if args.backend:
        await store.set_vault_backend(args.backend)

    status: dict[str, Any] = await store.status()

    if status["vault_backend"] == "local" and status["local_status"].get("password_required", False):
        pwd = args.unlock or getpass.getpass("Local vault password: ")
        unlock_status = await store.unlock_local_vault(pwd)
        if unlock_status["local_status"].get("locked", False):
            print("Failed to unlock local vault. Aborting.")
            sys.exit(1)

    name = _prompt_nonempty("Secret name: ")
    secret_value = _prompt_secret("Secret value: ")

    added = await store.add_secret(name, secret_value)
    print(f"Added secret '{added['name']}' ({added['id']}) to backend '{status['vault_backend']}'.")


if __name__ == "__main__":
    asyncio.run(main())
