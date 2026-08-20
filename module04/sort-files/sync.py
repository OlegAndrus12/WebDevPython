"""5. Асинхронна робота з файлами: сортування теки (синхронна версія).

Real-life task: the Downloads folder. Walk it recursively and copy every file
into output/<EXT>/, so images end up together, documents together, and so on.

This is the baseline. Compare with async_ex.py in the same folder.

    poetry run python sync.py
"""
import shutil
from pathlib import Path
from time import perf_counter

# Anchored to this file, not the working directory, so the script runs from anywhere.
BASE_DIR = Path(__file__).parent
SOURCE = BASE_DIR / "picture"
OUTPUT = BASE_DIR / "Backup"


def read_folder(path: Path, output: Path) -> int:
    copied = 0
    for element in path.iterdir():
        if element.is_dir():
            copied += read_folder(element, output)
        else:
            copy_file(element, output)
            copied += 1
    return copied


def copy_file(file: Path, output: Path) -> None:
    # ".JPG" and ".jpg" are the same folder; files without a suffix go to "other"
    extension = file.suffix.lstrip(".").lower() or "other"
    target_dir = output / extension
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(file, target_dir / file.name)


if __name__ == "__main__":
    if not SOURCE.is_dir():
        raise SystemExit(f"source folder not found: {SOURCE.resolve()}")

    total = read_folder(SOURCE, OUTPUT)
