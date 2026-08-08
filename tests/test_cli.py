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
    assert "Supply Chain Planning Lab 0.10.0" in captured.out
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


def test_forecast_command_compares_baselines_without_an_api_key(
    monkeypatch, capsys
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr("supply_chain_planning_lab.cli.load_dotenv", lambda: None)

    exit_code = main(
        [
            "forecast",
            "--method",
            "seasonal_naive",
            "--product",
            "WIN-2436",
            "--start-period",
            "2025-01",
            "--end-period",
            "2025-01",
            "--limit",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Forecast grain: monthly product demand" in captured.out
    assert "previous_month,3," in captured.out
    assert "seasonal_naive,3," in captured.out
    assert "trailing_3_average,3," in captured.out
    assert "Detailed forecasts: 1" in captured.out
    assert "2025-01,WIN-2436" in captured.out


def test_fred_forecast_command_evaluates_driver_without_an_api_key(
    monkeypatch, capsys
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr("supply_chain_planning_lab.cli.load_dotenv", lambda: None)

    exit_code = main(
        [
            "fred-forecast",
            "--product",
            "WIN-2436",
            "--horizon",
            "4",
            "--limit",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Forecast origins: 2019-12 through 2024-12" in captured.out
    assert "known,549,0.0,+0.0" in captured.out
    assert "forecasted,1647," in captured.out
    assert "Selected forecasts: 61" in captured.out
    assert "2019-12,4,2020-04,2020-01,forecasted,WIN-2436" in captured.out


def test_inventory_plan_command_calculates_requirements_without_an_api_key(
    monkeypatch, capsys
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr("supply_chain_planning_lab.cli.load_dotenv", lambda: None)

    exit_code = main(
        [
            "inventory-plan",
            "--origin",
            "2024-12",
            "--product",
            "WIN-2436",
            "--limit",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Plan grain: monthly finished-goods product requirements" in captured.out
    assert "Forecast origin: 2024-12" in captured.out
    assert "Safety stock: 25% of following-month forecast" in captured.out
    assert "Selected records: 12" in captured.out
    assert "2025-01,WIN-2436,718,300,0,300,2025-02,756,189,607,189" in captured.out


def test_procurement_command_calculates_bom_and_supplier_risk_without_api_key(
    monkeypatch, capsys
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr("supply_chain_planning_lab.cli.load_dotenv", lambda: None)

    exit_code = main(
        [
            "procurement-plan",
            "--origin",
            "2024-12",
            "--safety-method",
            "statistical",
            "--receipt-treatment",
            "risk_adjusted",
            "--component",
            "GLASS-SQFT",
            "--limit",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Plan grain: monthly purchased-component requirements" in captured.out
    assert "Material safety-stock method: statistical" in captured.out
    assert "Scheduled-receipt treatment: risk_adjusted" in captured.out
    assert "GLASS-SQFT,6,0.667,0.981,0.500" in captured.out
    assert "GLASS-SQFT,0,2536,14285" in captured.out
    assert "2025-01,GLASS-SQFT,8490,5000,4000,2000,14285" in captured.out


def test_capacity_command_allocates_shared_work_center_without_api_key(
    monkeypatch, capsys
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr("supply_chain_planning_lab.cli.load_dotenv", lambda: None)

    exit_code = main(
        [
            "capacity-plan",
            "--origin",
            "2024-12",
            "--work-center",
            "WINDOW-ASSEMBLY",
            "--limit",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Plan grain: monthly product and work-center capacity" in captured.out
    assert "Calendar: 20 days x 1 shifts x 8 hours" in captured.out
    assert "Overloaded work-center months: 12" in captured.out
    assert "2025-01,WINDOW-ASSEMBLY,144.0,151.2,105.0,-7.2,yes,959,52" in captured.out
    assert "2025-01,WINDOW-ASSEMBLY,WIN-2436,607,0,607,8,576,31" in captured.out
