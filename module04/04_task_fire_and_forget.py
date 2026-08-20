"""3. asyncio.Task: не змушуй клієнта чекати на побічний ефект.

POST /register does two things: write the row, send the welcome email. Only the
first one is worth making the client wait for.

    poetry run python 04_task_fire_and_forget.py
"""
import asyncio

from libs import async_timed

DB_WRITE = 0.05   # a real INSERT is fast
SMTP_SEND = 1.2   # a real SMTP conversation is not


async def create_user(name: str) -> dict:
    await asyncio.sleep(DB_WRITE)
    return {"id": 1, "name": name}


async def send_welcome_email(user: dict) -> None:
    await asyncio.sleep(SMTP_SEND)
    print(f"   [email] sent to {user['name']}")


@async_timed("POST /register  -- await the email")
async def register_awaiting(name: str) -> dict:
    user = await create_user(name)
    await send_welcome_email(user)          # the client sits through SMTP
    return {"status": "created", "id": user["id"]}


@async_timed("POST /register  -- create_task the email")
async def register_fire_and_forget(name: str) -> dict:
    user = await create_user(name)
    # create_task() hands the coroutine to the event loop and returns *now*.
    # Calling send_welcome_email(user) without create_task and without await
    # would do nothing at all -- a coroutine that is never scheduled never runs.
    asyncio.create_task(send_welcome_email(user))
    return {"status": "created", "id": user["id"]}


async def main() -> None:
    print(f"-> 200 {await register_awaiting('olena')}\n")
    print(f"-> 200 {await register_fire_and_forget('petro')}")

    # The response above is already out, but the email is still in flight. If main()
    # returned now, asyncio.run() would cancel it -- a Task lives only as long as
    # the loop that runs it. In a web app the loop outlives the request; here we
    # have to wait for it on purpose.
    await asyncio.sleep(SMTP_SEND)


if __name__ == "__main__":
    asyncio.run(main())
    print(f"\n{DB_WRITE + SMTP_SEND:.2f}s vs {DB_WRITE:.2f}s for the same work.")
    print("The email still gets sent -- just not on the client's clock.")
