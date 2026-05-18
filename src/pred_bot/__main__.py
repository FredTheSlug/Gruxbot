"""`python -m pred_bot` entrypoint."""

from __future__ import annotations

from pred_bot.bot import run as run_bot


def main() -> None:
    run_bot()


if __name__ == "__main__":
    main()
