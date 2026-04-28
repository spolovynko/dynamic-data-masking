from pathlib import Path

import pytest

from ddm_engine.storage.object_store import LocalObjectStore


def test_local_object_store_writes_reads_and_deletes_object(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)

    with store.open_writer("originals/job-1/original.txt") as output:
        output.write(b"private text")

    assert store.exists("originals/job-1/original.txt")
    assert store.read_bytes("originals/job-1/original.txt") == b"private text"

    store.delete("originals/job-1/original.txt")

    assert not store.exists("originals/job-1/original.txt")


def test_local_object_store_rejects_path_traversal(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)

    with pytest.raises(ValueError, match="Unsafe object key"):
        with store.open_writer("../outside.txt"):
            pass
