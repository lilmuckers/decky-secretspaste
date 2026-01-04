import json
from pathlib import Path

import pytest

import decky_plugin
from main import SecretStore


@pytest.mark.asyncio
async def test_secret_store_switch_backends(tmp_path: Path):
    decky_plugin.DECKY_PLUGIN_SETTINGS_DIR = str(tmp_path)
    store = SecretStore()

    # Stub gopass backend runner to avoid external dependency
    gp_backend = store.backends["gopass"]
    gp_backend.gopass_bin = "dummy"
    memory = {}

    def _run(args, stdin=None):
        cmd = args[0]
        target = args[-1]
        if cmd == "insert":
            memory[target] = (stdin or "").strip()
            return ""
        if cmd == "show":
            return memory.get(target, "")
        if cmd == "rm":
            memory.pop(target, None)
            return ""
        return ""

    gp_backend._run_gopass = _run  # type: ignore[assignment]

    added = await store.add_secret("gp", "secret1")
    assert added["name"] == "gp"
    listed_gp = await store.list_secrets()
    assert len(listed_gp) == 1

    # Switch to local backend
    status = await store.set_vault_backend("local")
    assert status["vault_backend"] == "local"

    # Set and unlock local password
    local_status = await store.configure_local_vault("pw123")
    assert local_status["local_status"]["password_required"] is True
    unlocked = await store.unlock_local_vault("pw123")
    assert unlocked["local_status"]["locked"] is False

    added_local = await store.add_secret("local", "value2")
    assert added_local["name"] == "local"
    listed_local = await store.list_secrets()
    assert len(listed_local) == 1

    # Ensure config persisted
    cfg = json.loads(Path(tmp_path / "config.json").read_text())
    assert cfg["vault_backend"] == "local"
