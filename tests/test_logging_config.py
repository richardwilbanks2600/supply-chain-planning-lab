import logging

from supply_chain_planning_lab.logging_config import configure_logging


def test_logging_can_write_console_and_file_without_duplicating_handlers(
    tmp_path, capsys
) -> None:
    log_file = tmp_path / "planning-lab.log"
    logger = logging.getLogger("supply_chain_planning_lab.test")

    configure_logging(verbose=True, log_file=log_file)
    logger.info("safe operational message")
    logger.debug("safe diagnostic detail")

    captured = capsys.readouterr()
    log_text = log_file.read_text(encoding="utf-8")
    assert "safe operational message" in captured.err
    assert "safe diagnostic detail" not in captured.err
    assert "safe operational message" in log_text
    assert "safe diagnostic detail" in log_text

    configure_logging(verbose=False, log_file=None)
