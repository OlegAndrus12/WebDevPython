"""6. Асинхронні HTTP-запити: завантаження файлів потоком (aiohttp + aiofiles).

Real-life task: download a set of documents and save them to disk. This is where
the two previous sections meet -- the network part is async, the disk part is
async, and neither blocks the loop.

The important detail is `iter_chunked`: we never call `await response.read()`,
so a 2 GB file uses 64 KB of memory instead of 2 GB.

    poetry run python 18_download_files.py
"""
import asyncio
from pathlib import Path

import aiohttp
import aiofiles

DOWNLOADS = Path("downloads")
CHUNK = 64 * 1024 # 64 KB

# The PEPs that introduced async/await and asyncio -- worth reading anyway.
FILES = {
    "pep-0492-async-await.rst": "https://raw.githubusercontent.com/python/peps/main/peps/pep-0492.rst",
    "pep-3156-asyncio.rst": "https://raw.githubusercontent.com/python/peps/main/peps/pep-3156.rst",
    "pep-0525-async-generators.rst": "https://raw.githubusercontent.com/python/peps/main/peps/pep-0525.rst",
    "pep-0530-async-comprehensions.rst": "https://raw.githubusercontent.com/python/peps/main/peps/pep-0530.rst",
    "asyncio-tasks.py": "https://raw.githubusercontent.com/python/cpython/main/Lib/asyncio/taskgroups.py",
    "python-logo.png": "https://www.python.org/static/community_logos/python-logo-master-v3-TM.png",
}


async def download(session: aiohttp.ClientSession, name: str, url: str) -> tuple[str, int]:
    target = DOWNLOADS / name
    try:
        async with session.get(url) as response:
            #raise_for_status() turns a 404/500 into a ClientResponseError
            response.raise_for_status()

            written = 0
            async with aiofiles.open(target, "wb") as fd:
                # Stream it: read a chunk, write a chunk, yield to the loop.
                async for chunk in response.content.iter_chunked(CHUNK):
                    await fd.write(chunk)
                    written += len(chunk)

        print(f"   done: {name} ({written / 1024:.1f} KiB)")
        return name, written
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        print(f"   failed: {name} -- {type(err).__name__}: {err}")
        # Do not leave a truncated file behind.
        target.unlink(missing_ok=True)
        return name, 0


async def download_all() -> list[tuple[str, int]]:
    DOWNLOADS.mkdir(exist_ok=True)
    timeout = aiohttp.ClientTimeout(total=60, connect=5)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        return await asyncio.gather(*(download(session, name, url) for name, url in FILES.items()))


if __name__ == "__main__":
    results = asyncio.run(download_all())
    total = sum(size for _, size in results)
    ok = sum(1 for _, size in results if size)
    print(f"\n{ok}/{len(results)} files, {total / 1024:.1f} KiB into {DOWNLOADS}/")
