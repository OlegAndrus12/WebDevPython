"""2. Основи asyncio: `await` сам по собі НЕ дає паралельності.

Real-life task: render a user profile page. It needs three independent things:
the user record, their orders, and recommendations. Three different services,
none of them depends on the others.

Written the way most people write it first -- three `await`s in a row -- the page
takes the *sum* of the three latencies. `async def` alone bought us nothing.
Compare with 05_gather.py, which fixes exactly this.

    poetry run python 04_await_is_sequential.py
"""
import asyncio

from libs import async_timed


async def fetch_user(user_id: int) -> dict:
    await asyncio.sleep(0.4)  # Postgres
    return {"id": user_id, "name": "Олена Ковальчук"}


async def fetch_orders(user_id: int) -> list[dict]:
    await asyncio.sleep(0.6)  # another service
    return [{"id": 101, "total": 1250}, {"id": 102, "total": 480}]


async def fetch_recommendations(user_id: int) -> list[str]:
    await asyncio.sleep(0.5)  # ML service
    return ["Клавіатура", "Монітор 27\"", "USB-C хаб"]


@async_timed("profile page, three awaits in a row")
async def build_profile_sequential(user_id: int) -> dict:
    user = await fetch_user(user_id)
    orders = await fetch_orders(user_id)
    recommendations = await fetch_recommendations(user_id)
    return {"user": user, "orders": orders, "recommendations": recommendations}


if __name__ == "__main__":
    profile = asyncio.run(build_profile_sequential(1))
    print(profile)
    print("\n0.4 + 0.6 + 0.5 = 1.5s. Nothing here ran at the same time:")
    print("each `await` stops *this* coroutine until that one call is done.")
