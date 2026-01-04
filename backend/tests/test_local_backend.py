import pytest
from pathlib import Path

from backends.local_backend import LocalVaultBackend


@pytest.mark.asyncio
async def test_local_backend_add_list_get_delete(tmp_path: Path):
    backend = LocalVaultBackend(tmp_path)

    added = await backend.add_secret("api-key", "supersecret")
    assert added["name"] == "api-key"

    listed = await backend.list_secrets()
    assert len(listed) == 1
    assert listed[0]["name"] == "api-key"

    fetched = await backend.get_secret(added["id"])
    assert fetched and fetched["value"] == "supersecret"

    deleted = await backend.delete_secret(added["id"])
    assert deleted is True
    assert await backend.list_secrets() == []


@pytest.mark.asyncio
async def test_local_backend_password_flow(tmp_path: Path):
    backend = LocalVaultBackend(tmp_path)

    # Set a password
    status = backend.configure_password("pw123")
    assert status["password_required"] is True
    assert status["locked"] is False

    # Unlock with wrong password should fail
    assert backend.unlock("wrong") is False
    assert backend.status()["locked"] is True

    # Unlock with correct password should succeed
    assert backend.unlock("pw123") is True
    assert backend.status()["locked"] is False

    # Add works while unlocked
    added = await backend.add_secret("token", "abc")
    assert added["name"] == "token"

    # Simulate reload: new instance should be locked until unlocked
    reloaded = LocalVaultBackend(tmp_path)
    assert reloaded.status()["locked"] is True
    with pytest.raises(RuntimeError):
        await reloaded.list_secrets()
    assert reloaded.unlock("pw123") is True
    assert reloaded.status()["locked"] is False


@pytest.mark.asyncio
async def test_local_backend_remove_password(tmp_path: Path):
    backend = LocalVaultBackend(tmp_path)
    backend.configure_password("pw123")
    backend.unlock("pw123")
    status = backend.configure_password("")
    assert status["password_required"] is False
    assert backend.status()["locked"] is False

    added = await backend.add_secret("note", "value")
    assert added["name"] == "note"
