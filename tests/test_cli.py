from supply_chain_planning_lab.cli import main


def test_installed_command_smoke_check_does_not_call_fred(
    monkeypatch, capsys
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr("supply_chain_planning_lab.cli.load_dotenv", lambda: None)

    exit_code = main(["project-info"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Supply Chain Planning Lab 0.2.0" in captured.out
    assert "FRED_API_KEY: not configured" in captured.out


def test_cli_logging_options_produce_console_and_file_output_without_secret(
    monkeypatch, tmp_path, capsys
) -> None:
    secret = "never-write-this-secret"
    log_file = tmp_path / "planning-lab.log"
    monkeypatch.setenv("FRED_API_KEY", secret)

    exit_code = main(
        [
            "--verbose",
            "--log-file",
            str(log_file),
            "project-info",
        ]
    )

    captured = capsys.readouterr()
    log_text = log_file.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "Reporting project setup" in captured.err
    assert "Starting command=project-info" in log_text
    assert secret not in captured.err
    assert secret not in log_text
