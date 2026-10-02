"""Backend logger: writes to the console and to logs/app.log (rotating)."""
import logging
from logging.handlers import RotatingFileHandler
from .config import LOG_DIR

LOG_FILE = LOG_DIR / "app.log"


def get_logger(name: str = "chatbot") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(console)
    logger.propagate = False
    return logger


def read_last_lines(n: int = 200) -> list[str]:
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
        return [line.rstrip("\n") for line in f.readlines()[-n:]]


log = get_logger()
