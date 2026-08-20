"""Малюємо часовий ряд і зберігаємо PNG.

Shared by sync.py and async_ex.py: the chart is identical whichever way the data
was fetched, so those two files differ only in how they make the requests.
"""
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render to a file, no GUI needed
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


def save_chart(rates: dict[str, float], path: Path, title: str) -> Path | None:
    """Draw the rate as a line chart and write it to a PNG."""
    if not rates:
        print("   no data to plot (is the network up?)")
        return None

    days = sorted(date.fromisoformat(day) for day in rates)
    values = [rates[day.isoformat()] for day in days]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(days, values)
    ax.set_title(title)
    ax.grid(axis="y")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))  # 21.07, not 2026-07-21
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"   chart saved to {path.name}")
    return path
