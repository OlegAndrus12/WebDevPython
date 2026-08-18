"""Liskov Substitution — a signature violation: `ZipFileManager.read()` inserts a `delimiter`
parameter its base never declared, so the subclass is no longer a drop-in `FileManager`."""

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile


class FileManager:
    def __init__(self, filename):
        self.path = Path(filename)

    def read(self, encoding="utf-8"):
        return self.path.read_text(encoding)

    def write(self, data, encoding="utf-8"):
        self.path.write_text(data, encoding)

class ZipFileManager(FileManager):
    def __init__(self, filename):
        self.path = Path(filename)

    # signature is overriden
    def read(self, delimiter="|", encoding="utf-8"):
        return self.path.read_text(encoding)

    def compress(self):
        with ZipFile(self.path.with_suffix(".zip"), mode="w") as archive:
            archive.write(self.path)

    def decompress(self):
        with ZipFile(self.path.with_suffix(".zip"), mode="r") as archive:
            archive.extractall()

if __name__ == "__main__":
    with TemporaryDirectory() as tmp:
        sample = Path(tmp) / "test.txt"

        # 1 — the base class
        manager = FileManager(sample)
        manager.write("orders data")
        print(f"FileManager.read()    -> {manager.read()!r}")

        # 2 — the subclass, called exactly the same way: still fine, because
        #     both parameters are defaulted
        manager = ZipFileManager(sample)
        print(f"ZipFileManager.read() -> {manager.read()!r}")

        # 3 — the same call with one positional argument means two different
        #     things. The base reads UTF-16; the subclass takes it as a
        #     delimiter and silently ignores it.
        print(f"ZipFileManager.read('utf-16') -> {manager.read('utf-16')!r}")