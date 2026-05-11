import os

from .web import run_web_app


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Set it in your environment before running this script."
        )

    run_web_app()
