"""Configures the process-wide Loguru logger from LoggingConfig.

Called once, early, by the CLI entry point and by the test suite's
fixtures. Every layer imports ``from loguru import logger`` directly
(Loguru's logger is a singleton) rather than receiving a logger via
dependency injection -- this is the one deliberate exception to "avoid
global mutable state," justified because Loguru's own design centers on
a single global sink configuration.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.config.settings import LoggingConfig

_TEXT_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)


def configure_logging(config: LoggingConfig) -> None:
    """Reset and reconfigure every Loguru sink from ``config``."""
    logger.remove()

    logger.add(
        sys.stderr,
        level=config.level,
        format=_TEXT_FORMAT,
        serialize=config.json_logs,
        backtrace=False,
        diagnose=False,
    )

    if config.log_file:
        log_path = Path(config.log_file)
        if log_path.parent != Path():
            log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_path,
            level=config.level,
            rotation=config.rotation,
            retention=config.retention,
            serialize=config.json_logs,
            backtrace=False,
            diagnose=False,
        )
