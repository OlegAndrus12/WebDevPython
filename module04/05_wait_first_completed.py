"""3. Паралельне виконання: asyncio.wait і "перший, хто відповів".

`gather` waits for all of them. `wait` gives you control: return when the first
task finishes, when the first one fails, or when everything is done.

Real-life task: turn an address into coordinates. Three geocoding providers can
answer it. Ask all three, take whichever answers first, cancel the rest -- a
"hedged request". This is how CDNs and DNS resolvers cut tail latency.

    poetry run python 05_wait_first_completed.py
"""
import asyncio
import random

from libs import async_timed

PROVIDERS = {
    "nominatim": 1.2,
    "mapbox": 0.6,
    "here-maps": 2.0,
}


async def geocode_with(provider: str, base_latency: float) -> str:
    latency = base_latency * random.uniform(0.8, 1.2)
    try:
        await asyncio.sleep(latency)
    except asyncio.CancelledError:
        print(f"   [{provider}] cancelled -- connection closed")
        raise
    print(f"   [{provider}] answered in {latency:.2f}s")
    return f"50.4501, 30.5234 from {provider}"


@async_timed("hedged geocoding")
async def geocode_fastest() -> str:
    tasks = [
        asyncio.create_task(geocode_with(provider, latency), name=provider)
        for provider, latency in PROVIDERS.items()
    ]

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    print(f"   done: {len(done)}, still pending: {len(pending)}")

    for task in pending:
        task.cancel()
    # Give the cancelled tasks a chance to actually unwind before we return.
    await asyncio.gather(*pending, return_exceptions=True)

    return done.pop().result()


if __name__ == "__main__":
    print(asyncio.run(geocode_fastest()))
    print("\nTotal time = the fastest provider, not the average and not the slowest.")
