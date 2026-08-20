"""2. Основи asyncio: корутина -- це ще не виконання.

Calling an `async def` function does not run it. It builds a *coroutine object*:
a description of work that somebody (the event loop) still has to execute.

This is the single most common beginner bug: forgetting `await` and wondering why
"nothing happened" -- so we reproduce it on purpose below.

    poetry run python 03_coroutine_object.py
"""
import asyncio

from faker import Faker

fake = Faker("uk-UA")


async def fetch_user(user_id: int) -> dict:
    """Pretend this talks to Postgres over the network (0.5s round trip)."""
    await asyncio.sleep(0.5)
    return {"id": user_id, "name": fake.name(), "email": fake.email()}


async def main() -> None:
    # 1. Calling the coroutine function returns an object. No query has been sent.
    coro = fetch_user(1)
    print("what we got back:", coro)
    print("type:            ", type(coro))

    # 2. `await` hands it to the event loop and waits for the result.
    user = await coro
    print("after await:     ", user)

    # 3. A coroutine can only be awaited once -- it is not a reusable recipe.
    try:
        await coro
    except RuntimeError as err:
        print("awaiting twice:   RuntimeError:", err)

    # 4. And this is the classic mistake: the coroutine is created and dropped.
    #    Python warns "coroutine ... was never awaited" -- the DB was never queried.
    fetch_user(2)


if __name__ == "__main__":
    asyncio.run(main())



import asyncio


async def send_sms(phone: str, code: str) -> str:
    """One async function doing one thing: hand an SMS to the operator.

    `asyncio.sleep` stands in for the operator's API here. It is the async twin
    of `time.sleep`: it waits without blocking anyone else.
    """
    print(f"sending {code} to {phone} ...")
    await asyncio.sleep(1)
    return "delivery-id-8f21c"


if __name__ == "__main__":
    # asyncio.run() creates the event loop, runs the coroutine to completion,
    # closes the loop, and gives you back the return value. That is all.
    receipt = asyncio.run(send_sms("+380671234567", "4821"))
    print(receipt)

    # It works with anything awaitable, not only your own functions:
    asyncio.run(asyncio.sleep(0.1))
