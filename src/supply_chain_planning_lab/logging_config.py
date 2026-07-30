"""Logging setup for optional console and file diagnostics."""

import logging
import sys
from pathlib import Path


class LoggingSetupError(RuntimeError):
    """Raised when a requested log destination cannot be prepared."""


def configure_logging(*, verbose: bool, log_file: Path | None) -> None:
    """Configure quiet defaults, optional INFO console logs, and DEBUG file logs."""

    package_logger = logging.getLogger("supply_chain_planning_lab")
    _remove_handlers(package_logger)
    package_logger.setLevel(logging.DEBUG)
    package_logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if verbose:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        package_logger.addHandler(console_handler)

    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
        except OSError as exc:
            raise LoggingSetupError(f"Could not write log file to {log_file}.") from exc
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        package_logger.addHandler(file_handler)

    if not package_logger.handlers:
        package_logger.addHandler(logging.NullHandler())


def _remove_handlers(logger: logging.Logger) -> None:
    """Close existing handlers so repeated setup does not duplicate messages."""

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
