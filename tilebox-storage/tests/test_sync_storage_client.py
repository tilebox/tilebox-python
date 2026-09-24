import asyncio
from contextvars import ContextVar
from pathlib import Path
from threading import get_ident
from unittest.mock import patch

import pytest

from tilebox import storage
from tilebox.storage._sync import _run
from tilebox.storage.granule import LocationStorageGranule


def test_local_sync_client(tmp_path: Path) -> None:
    folder = tmp_path / "scene"
    folder.mkdir()
    (folder / "data.tif").write_bytes(b"raster")
    (tmp_path / "preview.jpg").write_bytes(b"preview")
    granule = LocationStorageGranule("scene", "preview.jpg")
    client = storage.LocalFileSystemStorageClient(tmp_path)

    # Reuse the same client across separate asyncio.run() event loops.
    assert client.list_objects(granule) == ["data.tif"]
    assert client.download(granule) == folder
    assert client.download_quicklook(granule) == tmp_path / "preview.jpg"
    with patch("tilebox.storage.aio._display_quicklook") as display:
        client.quicklook(granule, width=321, height=123)
        display.assert_called_once_with(tmp_path / "preview.jpg", 321, 123, None)

    with pytest.raises(ValueError, match="Data not found"):
        client.download(LocationStorageGranule("missing"))


@pytest.mark.asyncio
async def test_local_sync_client_in_running_loop(tmp_path: Path) -> None:
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    test_local_sync_client(tmp_path)
    assert asyncio.get_running_loop() is loop
    assert asyncio.current_task() is task
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_run_preserves_context_in_worker_thread() -> None:
    context = ContextVar("storage_test_context", default="unset")
    token = context.set("caller")
    caller_thread = get_ident()
    caller_loop = asyncio.get_running_loop()

    async def operation() -> str:
        assert get_ident() != caller_thread
        assert asyncio.get_running_loop() is not caller_loop
        await asyncio.sleep(0)
        value = context.get()
        context.set("worker")
        return value

    try:
        assert _run(operation()) == "caller"
        assert context.get() == "caller"
    finally:
        context.reset(token)
