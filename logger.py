"""
logger.py — centralised, coloured logging for Tiny-OpenClaw.

Every module calls `get_logger(__name__)` to get a child logger that
inherits level and handlers from the root "tiny_openclaw" logger.
"""

import logging
import sys

# ANSI colour codes (gracefully stripped on Windows if not supported)
_GREY   = "\x1b[38;5;240m"
_CYAN   = "\x1b[36m"
_YELLOW = "\x1b[33m"
_RED    = "\x1b[31m"
_BOLD   = "\x1b[1m"
_RESET  = "\x1b[0m"

_LEVEL_COLOURS = {
    logging.DEBUG:    _GREY,
    logging.INFO:     _CYAN,
    logging.WARNING:  _YELLOW,
    logging.ERROR:    _RED,
    logging.CRITICAL: _BOLD + _RED,
}


class _ColourFormatter(logging.Formatter):
    FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    DATE   = "%H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        colour = _LEVEL_COLOURS.get(record.levelno, "")
        fmt = colour + self.FORMAT + _RESET
        formatter = logging.Formatter(fmt, datefmt=self.DATE)
        return formatter.format(record)


def _configure_root(level: int = logging.INFO) -> None:
    root = logging.getLogger("tiny_openclaw")
    if root.handlers:
        return  # already configured

    root.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ColourFormatter())
    root.addHandler(handler)
    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'tiny_openclaw' namespace."""
    _configure_root()
    # Strip leading package path if present so names stay short
    short = name.replace("tiny_openclaw.", "")
    return logging.getLogger(f"tiny_openclaw.{short}")
