"""3. asyncio.Task: помилка у fire-and-forget задачі нікуди не приходить.

A task nobody awaits keeps its exception to itself. Registration reports success,
the email never went out, and the traceback surfaces -- if at all -- as a warning
from the garbage collector, at a point where no code of yours can catch it.

The fix is two lines: keep the handle, and attach a done-callback that reads the
result. The callback runs the moment the task ends, and it is the only place a
background failure is guaranteed to arrive.

    poetry run python 04_task_lost_exception.py
"""
import asyncio

from libs import async_timed

DB_WRITE = 0.05
SMTP_SEND = 0.4


async def create_user(name: str) -> dict:
    await asyncio.sleep(DB_WRITE)
    return {"id": 1, "name": name}


async def send_welcome_email(user: dict) -> str:
    await asyncio.sleep(SMTP_SEND)
    raise ConnectionRefusedError(f"550 mailbox unavailable: {user['name']}")


@async_timed("register, task unowned")
async def register_silently(name: str) -> dict:
    user = await create_user(name)
    # No variable, no await, nobody reads the outcome. Note also that this is the
    # only reference to a running task -- asyncio.all_tasks() is a *weak* set, so
    # the loop will not keep the task alive for you. The docs say to save it.
    asyncio.create_task(send_welcome_email(user))
    return {"status": "created"}


def report(task: asyncio.Task) -> None:
    """Called by the loop the instant the task finishes, ordinary sync function."""
    if error := task.exception():  # returns the exception instead of raising it
        print(f"   [{task.get_name()}] FAILED {type(error).__name__}: {error}")


@async_timed("register, task owned")
async def register_reporting(name: str) -> dict:
    user = await create_user(name)
    task = asyncio.create_task(send_welcome_email(user), name=f"email:{name}")
    task.add_done_callback(report)  # <- the whole fix
    return {"status": "created"}


async def main() -> None:
    print(f"-> 200 {await register_silently('olena')}")
    await asyncio.sleep(SMTP_SEND + 0.1)
    print("   ^ that traceback is asyncio's destructor complaining on stderr when the\n"
          "     Task object is collected. It is not your logger, you cannot except it,\n"
          "     and it appears only if nothing else holds a reference. Meanwhile the\n"
          "     handler returned 200 half a second ago.\n")

    print(f"-> 200 {await register_reporting('petro')}")
    await asyncio.sleep(SMTP_SEND + 0.1)


if __name__ == "__main__":
    asyncio.run(main())
    print("\nThe response is the same in both cases -- 200, instantly. The")
    print("difference is whether the failure has somewhere to go. A done-callback")
    print("is where you log it, retry it, or write it to a dead-letter table.")
