"""5. Асинхронна робота з файлами: сортування теки (асинхронна версія).

Same job as sync.py -- walk a folder, copy every file into output/<EXT>/ -- but
with aiopath (async Path) and aioshutil (async shutil).

Read the timings honestly: on a local SSD this is *not* dramatically faster than
sync.py. Copying files is syscall-bound, not latency-bound, and under the hood
aiopath/aioshutil hand the work to a thread pool anyway. What you gain is that a
web server doing this in the background keeps answering requests.

    poetry run python async_ex.py
"""
import asyncio
from pathlib import Path

from aiopath import AsyncPath
from aioshutil import copyfile

# Anchored to this file, not the working directory, so the script runs from anywhere.
BASE_DIR = Path(__file__).parent
SOURCE = AsyncPath(BASE_DIR / "picture")
OUTPUT = AsyncPath(BASE_DIR / "Backup-async")


async def read_folder(path: AsyncPath, output: AsyncPath) -> int:
    """Collect the whole tree into coroutines, then run them together."""
    tasks = []
    async for element in path.iterdir():
        if await element.is_dir():
            tasks.append(read_folder(element, output))
        else:
            tasks.append(copy_file(element, output))

    await asyncio.gather(*tasks)


async def copy_file(file: AsyncPath, output: AsyncPath) -> int:
    extension = file.suffix.lstrip(".").lower() or "other"
    target_dir = output / extension
    await target_dir.mkdir(parents=True, exist_ok=True)
    await copyfile(file, target_dir / file.name)


if __name__ == "__main__":
    asyncio.run(read_folder(SOURCE, OUTPUT))
