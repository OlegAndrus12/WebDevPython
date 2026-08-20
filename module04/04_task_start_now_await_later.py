"""3. asyncio.Task: почати зараз, вирішити потім, чи чекати результат.

create_task() returns a handle, and the handle is the point: the line that STARTS
the work and the line that AWAITS it can be different lines -- with anything you
like in between, including an `if` that decides not to await it at all.

That is the one thing gather cannot do. `gather(a(), b())` starts and awaits in a
single expression, so if you always want both results, gather is simpler and you
should use it. Use a handle when "do I need this result?" is answered later.

Here: POST /register sends the welcome email either way. An admin-created account
reports the message id back in the response, so it waits for it. A self-signup
does not.

    poetry run python 04_task_start_now_await_later.py
"""
import asyncio

from libs import async_timed

DB_WRITE = 0.05
SMTP_SEND = 1.2
AUDIT_LOG = 0.3


async def create_user(name: str) -> dict:
    await asyncio.sleep(DB_WRITE)
    return {"id": 1, "name": name}


async def send_welcome_email(user: dict) -> str:
    await asyncio.sleep(SMTP_SEND)
    return f"msg-{user['id']}@smtp"


async def write_audit_log(user: dict) -> None:
    await asyncio.sleep(AUDIT_LOG)


@async_timed("POST /register")
async def register(name: str, report_email: bool) -> dict:
    user = await create_user(name)

    # In flight from here on.
    task = asyncio.create_task(send_welcome_email(user), name="welcome-email")

    # Runs while SMTP is talking -- 0.3s that costs nothing extra.
    await write_audit_log(user)
    print(f"   audit written; email done={task.done()}")

    response = {"status": "created", "id": user["id"]}
    if report_email:
        # Awaiting the handle here, 0.35s after it started, so 0.35s of the wait
        # is already behind us. Awaiting a Task twice is fine: the result is cached.
        response["email"] = await task
    return response


async def main() -> None:
    print(f"-> 200 {await register('olena', report_email=True)}\n")
    print(f"-> 200 {await register('petro', report_email=False)}")
    await asyncio.sleep(SMTP_SEND)  # let petro's email finish before the loop closes


if __name__ == "__main__":
    asyncio.run(main())
    print(f"\nSame create_task line, two different endings: {DB_WRITE + SMTP_SEND:.2f}s "
          f"when the response needs the result,")
    print(f"{DB_WRITE + AUDIT_LOG:.2f}s when it does not. The `if` sits between "
          f"starting the work and awaiting it,")
    print("which is exactly the room a Task handle gives you and gather does not.")
