from __future__ import annotations

import shutil
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from ddm_engine.config import Settings


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int


class ObjectStore(Protocol):
    def open_writer(self, key: str) -> AbstractContextManager[BinaryIO]:
        raise NotImplementedError

    def read_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    @contextmanager
    def open_writer(self, key: str) -> BinaryIO:
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as output:
            yield output

    def read_bytes(self, key: str) -> bytes:
        return self._path_for_key(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path_for_key(key)
        path.unlink(missing_ok=True)
        self._remove_empty_parents(path.parent)

    def exists(self, key: str) -> bool:
        return self._path_for_key(key).exists()

    def _path_for_key(self, key: str) -> Path:
        relative_path = Path(key)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Unsafe object key: {key}")
        return self.root / relative_path

    def _remove_empty_parents(self, path: Path) -> None:
        while path != self.root and path.exists():
            try:
                path.rmdir()
            except OSError:
                break
            path = path.parent


def create_object_store(settings: Settings) -> ObjectStore:
    if settings.object_store_backend == "local":
        return LocalObjectStore(settings.resolved_object_store_root)
    raise ValueError(f"Unsupported object store backend: {settings.object_store_backend}")


def remove_object_prefix(store_root: Path, prefix: str) -> None:
    relative_path = Path(prefix)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"Unsafe object prefix: {prefix}")
    shutil.rmtree(store_root / relative_path, ignore_errors=True)
