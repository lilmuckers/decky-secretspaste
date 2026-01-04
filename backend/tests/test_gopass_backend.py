import pytest
from pathlib import Path

from backends.gopass_backend import GopassBackend


def _fake_runner(store):
    def _run(args, stdin=None):
        cmd = args[0]
        target = args[-1]
        if cmd == "insert":
            store[target] = (stdin or "").strip()
            return ""
        if cmd == "show":
            return store.get(target, "")
        if cmd == "rm":
            store.pop(target, None)
            return ""
        return ""

    return _run


@pytest.mark.asyncio
async def test_gopass_backend_add_list_get_delete(tmp_path: Path):
    backend = GopassBackend(tmp_path)
    backend.gopass_bin = "dummy"
    secret_store = {}
    backend._run_gopass = _fake_runner(secret_store)  # type: ignore[assignment]

    added = await backend.add_secret("db", "pw1")
    assert added["name"] == "db"
    assert backend.secrets_file.exists()

    listed = await backend.list_secrets()
    assert len(listed) == 1
    assert listed[0]["name"] == "db"

    fetched = await backend.get_secret(added["id"])
    assert fetched and fetched["value"] == "pw1"

    removed = await backend.delete_secret(added["id"])
    assert removed is True
    assert await backend.list_secrets() == []
