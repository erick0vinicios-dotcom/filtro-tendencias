import logging
import os
import sys


def setup_logging(level):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", level).upper(),
        format="%(asctime)s %(levelname)-7s %(name)-10s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
