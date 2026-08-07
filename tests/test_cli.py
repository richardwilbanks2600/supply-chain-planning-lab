from supply_chain_planning_lab.cli import main
from supply_chain_planning_lab.output import write_processed_csv


def test_installed_command_smoke_check_does_not_call_fred(
    monkeypatch, capsys
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr("supply_chain_planning_lab.cli.load_dotenv", lambda: None)

    exit_code = main(["project-info"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Supply Chain Planning Lab 0.4.0" in captured.out
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


def test_inspect_command_filters_and_describes_without_an_api_key(
    monkeypatch, tmp_path, capsys
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr("supply_chain_planning_lab.cli.load_dotenv", lambda: None)
    csv_path = tmp_path / "processed.csv"
    write_processed_csv(
        csv_path,
        [
            {
                "series_id": "PERMIT",
                "period": "2026-01",
                "value": 100.0,
                "unit": "thousands_of_units_saar",
            },
            {
                "series_id": "PERMIT",
                "period": "2026-02",
                "value": 120.0,
                "unit": "thousands_of_units_saar",
            },
            {
                "series_id": "PERMIT",
                "period": "2026-03",
                "value": 140.0,
                "unit": "thousands_of_units_saar",
            },
        ],
    )

    exit_code = main(
        ["inspect", str(csv_path), "--start-period", "2026-02", "--limit", "1"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Quality status: PASS" in captured.out
    assert "Selected records: 2" in captured.out
    assert "Minimum: 120.0" in captured.out
    assert "Latest change: +20.0" in captured.out
    assert "PERMIT,2026-02,120.0,thousands_of_units_saar" in captured.out
    assert "PERMIT,2026-03,140.0,thousands_of_units_saar" not in captured.out


def test_inspect_command_fails_duplicates_and_suppresses_measures(
    tmp_path, capsys
) -> None:
    csv_path = tmp_path / "duplicates.csv"
    duplicate = {
        "series_id": "PERMIT",
        "period": "2026-01",
        "value": 100.0,
        "unit": "thousands_of_units_saar",
    }
    write_processed_csv(csv_path, [duplicate, duplicate])

    exit_code = main(["inspect", str(csv_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Quality status: FAIL" in captured.out
    assert "Duplicate periods: 2026-01" in captured.out
    assert "Descriptive measures: unavailable" in captured.out
    assert "Minimum:" not in captured.out


def test_demand_command_loads_fixed_data_without_an_api_key(
    monkeypatch, capsys
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr("supply_chain_planning_lab.cli.load_dotenv", lambda: None)

    exit_code = main(
        [
            "demand",
            "--start-period",
            "2024-01",
            "--end-period",
            "2024-01",
            "--customer",
            "Building Houses Company",
            "--product",
            "WIN-2436",
            "--limit",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Source: fixed FRED PERMIT snapshot" in captured.out
    assert "Selected records: 1" in captured.out
    assert "Cancellations: none" in captured.out
    assert "Internal demand units: 381" in captured.out
