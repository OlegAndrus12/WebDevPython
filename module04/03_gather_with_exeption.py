"""3. Паралельне виконання: asyncio.gather.

Same profile page as 04_await_is_sequential.py, but the three calls are handed to
the loop together. Total time = the slowest one, not the sum.

Also shows the two things people trip over with gather:
  * results come back in the order you passed them in, not the order they finished;
  * by default one exception kills the whole gather -- `return_exceptions=True`
    turns failures into values instead, which is usually what a web page wants.

    poetry run python 05_gather.py
"""
import asyncio

from libs import async_timed


async def fetch_user(user_id: int) -> dict:
    await asyncio.sleep(5)
    return {"id": user_id, "name": "Олена Ковальчук"}


async def fetch_orders(user_id: int) -> list[dict]:
    await asyncio.sleep(5)
    return [{"id": 101, "total": 1250}, {"id": 102, "total": 480}]


async def fetch_recommendations(user_id: int) -> list[str]:
    await asyncio.sleep(5)
    raise ConnectionError("recommendation service is down")


@async_timed("profile page, gather without return_exceptions")
async def build_profile_strict(user_id: int) -> dict:
    # Without the flag the first exception propagates immediately and the
    # remaining results are lost, even though those calls already succeeded.
    #gather() = "start these together and wait for all of them"
    user, orders, recommendations = await asyncio.gather(
        fetch_user(user_id),
        fetch_orders(user_id),
        fetch_recommendations(user_id),
    )
    return {"user": user, "orders": orders, "recommendations": recommendations}

@async_timed("profile page, gather")
async def build_profile(user_id: int) -> dict:
    user, orders, recommendations = await asyncio.gather(
        fetch_user(user_id),
        fetch_orders(user_id),
        fetch_recommendations(user_id),
        return_exceptions=True,
    )

    # With return_exceptions=True the "result" may be an exception object.
    # A recommendation outage should not take the whole page down.
    if isinstance(recommendations, Exception):
        print(f"   degraded: {recommendations!r}")
        recommendations = []

    return {"user": user, "orders": orders, "recommendations": recommendations}


async def main() -> None:
    print(await build_profile(1))
    print()
    try:
        await build_profile_strict(1)
    except ConnectionError as err:
        print(f"   whole page failed: {err}")


if __name__ == "__main__":
    asyncio.run(main())
    print("\n0.6s instead of 1.5s -- the three calls waited on the network together.")
