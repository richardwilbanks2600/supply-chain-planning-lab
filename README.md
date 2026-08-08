# Supply Chain Planning Lab

Supply Chain Planning Lab is an educational Python project that translates a
fixed FRED construction-market history into fictional internal demand through
visible business assumptions. It offers both a repeatable command-line
workflow and an interactive local Streamlit dashboard.

The project uses the Federal Reserve Bank of St. Louis FRED API and the
[`PERMIT` series](https://fred.stlouisfed.org/series/PERMIT): new privately
owned housing units authorized in permit-issuing places. The series is monthly
and reported as thousands of units at a seasonally adjusted annual rate.

Building permits are an external market indicator. They are not customer
orders, company demand, or a forecast.

## Features

- Fetch the FRED `PERMIT` series from a chosen start date.
- Preserve the exact raw JSON response before validation.
- Validate outside data with Pydantic before transforming it.
- Normalize valid observations into inspectable CSV records.
- Skip and report FRED's `.` missing-value marker.
- Validate, filter, list, and transparently describe processed CSV records.
- Detect duplicate periods, missing calendar months, and unexpected row order.
- Load a fixed FRED `PERMIT` snapshot covering 2000 through 2025.
- Translate market pace into internal demand with visible fictional assumptions.
- Filter internal demand by month, customer, and product without an API key.
- Compare previous-month, seasonal-naive, and trailing-average demand forecasts.
- Evaluate forecast magnitude and direction with MAE and bias.
- Separate known lagged FRED drivers from future drivers that require forecasts.
- Evaluate 1-12 month FRED-informed demand forecasts with rolling origins.
- Convert a selected forecast into finished-goods inventory and net production
  requirements with an adjustable safety-stock policy.
- Write optional operational logs to the console and detailed logs to a file.
- Explore the same validated records in a local Streamlit dashboard.
- Test success and failure behavior with fixtures and mocks instead of live API
  requests.
- Keep API keys out of source control, output, fixtures, and logs.

## Requirements

- macOS, Windows, or Linux
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- A free [FRED API key](https://fredaccount.stlouisfed.org/apikeys) for live
  fetches

`uv` installs the compatible Python version and project dependencies, so a
separate Python installation is not required.

## Quick start

Clone the repository and enter its folder:

```shell
git clone https://github.com/richardwilbanks2600/supply-chain-planning-lab.git
cd supply-chain-planning-lab
```

Install the project and development dependencies:

```shell
uv sync
```

Create a local environment file:

macOS or Linux:

```shell
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Open `.env` in a text editor and replace the example value with your own key:

```dotenv
FRED_API_KEY=your_key_here
```

The `.env` file is ignored by Git. Do not paste an API key into source code,
tests, screenshots, issue comments, or log messages.

Check the setup without contacting FRED or revealing the key:

```shell
uv run planning-lab project-info
```

## Command-line interface

Fetch observations starting in January 2020:

```shell
uv run planning-lab fetch --start-date 2020-01-01
```

Each successful fetch creates two timestamp-matched files:

- `data/raw/fred_permit_<timestamp>.json` contains the exact FRED response.
- `data/processed/fred_permit_<timestamp>.csv` contains `series_id`, `period`,
  `value`, and `unit` columns.

Choose a different generated-data directory:

```shell
uv run planning-lab fetch \
  --start-date 2020-01-01 \
  --output-dir data
```

Display command help:

```shell
uv run planning-lab --help
uv run planning-lab fetch --help
uv run planning-lab inspect --help
uv run planning-lab demand --help
uv run planning-lab forecast --help
uv run planning-lab fred-forecast --help
uv run planning-lab inventory-plan --help
```

### Processed-data inspection

Inspect a CSV created by the fetch command without an API key or network call:

```shell
uv run planning-lab inspect data/processed/fred_permit_<timestamp>.csv
```

Filter to an inclusive month range and limit the listed rows:

```shell
uv run planning-lab inspect data/processed/fred_permit_<timestamp>.csv \
  --start-period 2024-01 \
  --end-period 2025-12 \
  --limit 12
```

Inspection validates the exact CSV schema, the `PERMIT` series identifier,
canonical `YYYY-MM` periods, finite numeric values, and the
`thousands_of_units_saar` unit. Duplicate periods fail inspection because the
project has no rule for choosing between them. Missing months and
nonchronological source rows are reported as warnings rather than silently
filled or changed.

For the selected records, the command reports minimum, maximum, latest value,
latest change, and the arithmetic mean of up to the latest 12 valid
observations. These measures describe historical values; they are not a trend
classification or forecast. The exact rules and a manual example are in
[`docs/specs/milestone-02-data-inspection.md`](docs/specs/milestone-02-data-inspection.md).

### FRED-driven internal demand

Inspect the default FRED-driven demand scenario without an API key or network
call:

```shell
uv run planning-lab demand --limit 12
```

Filter by requested ship month, customer, and product:

```shell
uv run planning-lab demand \
  --start-period 2024-01 \
  --end-period 2024-12 \
  --customer "Building Houses Company" \
  --product WIN-2436 \
  --limit 12
```

The version-controlled FRED snapshot contains all 312 months from January 2000
through December 2025. A transparent model converts the seasonally adjusted
annual pace into a monthly pace, applies a three-month lag and fictional
company market share, multiplies by product units per home, and allocates whole
units among the three customers. Cancellations are currently zero.

The default scenario uses a `0.10%` company share, product attachment rates of
six small windows, four large windows, and one exterior door per addressable
home, and customer allocations of `50%`, `30%`, and `20%`. Every derived row
retains the FRED source month and calculation assumptions.

The approved meaning, manual example, data-quality rules, and limitations are
in
[`docs/specs/milestone-03-fictional-demand.md`](docs/specs/milestone-03-fictional-demand.md).

### Baseline forecast comparison

Compare all three approved methods and list the primary same-month-last-year
baseline without an API key or network call:

```shell
uv run planning-lab forecast --limit 12
```

Inspect another method or product over a narrower evaluation period:

```shell
uv run planning-lab forecast \
  --method trailing_3_average \
  --product WIN-2436 \
  --start-period 2024-01 \
  --end-period 2025-12 \
  --limit 12
```

Forecasts are calculated at monthly product-total level across customers. The
approved common evaluation period is January 2020 through December 2025. The
command reports mean absolute error (MAE) and bias using
`error = actual - forecast`, so positive bias means underforecasting.

The exact methods, manual example, error definitions, and limitations are in
[`docs/specs/milestone-04-baseline-forecasting.md`](docs/specs/milestone-04-baseline-forecasting.md).

### FRED-informed forecast evaluation

Evaluate the approved 1-12 month rolling-origin forecast without an API key or
network call:

```shell
uv run planning-lab fred-forecast --limit 12
```

Inspect one product and demand horizon:

```shell
uv run planning-lab fred-forecast \
  --product WIN-2436 \
  --horizon 4 \
  --limit 12
```

Because permits lead internal demand by three months, demand horizons 1-3 use
FRED values already known at the forecast origin. Demand horizons 4-12 require
unknown future permit values; the approved baseline carries the origin's most
recent FRED value forward. The command reports MAE and bias by driver status
and horizon, then preserves forecast-origin, driver-period, and product lineage
in each detail row.

This is a revised-history teaching backtest. It uses one fixed current FRED
snapshot and does not reconstruct historical FRED vintages or publication
delays. The full design and manual example are in
[`docs/specs/milestone-05-fred-informed-forecasting.md`](docs/specs/milestone-05-fred-informed-forecasting.md).

### Inventory and net production requirements

Build the default 12-month finished-goods plan from the December 2024 forecast
origin without an API key or network call:

```shell
uv run planning-lab inventory-plan --limit 12
```

Change the safety-stock policy and starting inventory, or list one product:

```shell
uv run planning-lab inventory-plan \
  --origin 2024-12 \
  --safety-stock-percent 25 \
  --starting-win-2436 300 \
  --starting-win-3648 200 \
  --starting-door-3680 50 \
  --product WIN-2436
```

The plan treats the FRED-informed forecast as gross demand, adds a safety-stock
target based on the following month's forecast, and subtracts the inventory
already available. Projected ending inventory becomes the next month's
beginning inventory. Scheduled receipts are currently zero, and planned
production is assumed to be available in the same month.

This is a requirement calculation, not yet a capacity-feasible production
schedule. The policy, formulas, manual example, and limitations are in
[`docs/specs/milestone-06-inventory-planning.md`](docs/specs/milestone-06-inventory-planning.md).

### Logging

Show operational `INFO` messages in the terminal:

```shell
uv run planning-lab --verbose fetch --start-date 2020-01-01
```

Write detailed `DEBUG` messages to a file:

```shell
uv run planning-lab \
  --log-file logs/planning-lab.log \
  fetch \
  --start-date 2020-01-01
```

Use both options to see operational messages while preserving more detail:

```shell
uv run planning-lab \
  --verbose \
  --log-file logs/planning-lab.log \
  fetch \
  --start-date 2020-01-01
```

The global logging options appear before the `fetch` or `project-info`
subcommand. Logs record dates, series identifiers, outcomes, and output paths;
they do not record the API key.

## Streamlit dashboard

Start the local dashboard:

```shell
uv run streamlit run src/supply_chain_planning_lab/dashboard.py
```

Streamlit prints a local URL and normally opens it in the default browser. In
the dashboard:

1. Open **Internal demand** to inspect the fixed FRED history without an API
   key.
2. Adjust company share, customer allocation, or units per home and inspect
   the recalculated monthly totals and lineage rows.
3. Open **Forecast baselines** to compare all methods and explore actual versus
   forecast demand for each product.
4. Open **FRED-informed forecast** to compare known lagged drivers with horizons
   that require a FRED forecast.
5. Select a product and 1-12 month horizon to inspect its rolling-origin chart
   and source lineage.
6. Open **Inventory plan** to choose a forecast origin and adjust starting
   finished-goods inventory and the safety-stock percentage.
7. Inspect monthly forecast demand, net production requirements, projected
   ending inventory, and the displayed calculation.
8. Open **External market indicator** to work with live FRED data separately.
9. Configure `FRED_API_KEY`, choose a first observation date, and select
   **Load validated FRED data** for the external view.
10. Review its descriptive measures, trend chart, trusted rows, and downloads.

The dashboard calls the same FRED-snapshot validation and demand-calculation
logic used by the CLI. Sliders adjust company market share, customer
allocation, and units per home deterministically; no random demand is
generated.

The dashboard runs locally for this project. Deployment is not required.

## Understanding the unit

FRED reports `PERMIT` in thousands of housing units at a seasonally adjusted
annual rate (SAAR). For example, `1,500.0` describes an annualized pace of
approximately 1.5 million units after seasonal adjustment. It does not mean
1.5 million permits were issued in that single month.

Building permits do not identify this project's fictional products, customers,
orders, inventory, suppliers, or production capacity. Milestone 3 applies a
documented fictional translation model for teaching purposes; it does not
establish causation or claim that the resulting demand was observed.

## Tests and verification

Run the automated tests:

```shell
uv run pytest
```

Generate a coverage report that identifies unexecuted source lines:

```shell
uv run pytest \
  --cov=supply_chain_planning_lab \
  --cov-report=term-missing
```

Tests use committed FRED fixtures and controlled mocks. They do not need an API
key and do not contact the live FRED service. The suite covers:

- a successful API request and the expected request values;
- timeout, HTTP, connection, and invalid-JSON failures;
- valid and invalid incoming data;
- raw-response preservation before validation;
- transformation and CSV output;
- processed-CSV validation, quality detection, filtering, and descriptive measures;
- FRED snapshot completeness, demand lineage, allocation, filtering, and summaries;
- baseline forecast calculations, filtering, MAE, bias, and manual examples;
- FRED-driver forecast horizons, lineage, rolling-origin counts, MAE, and bias;
- inventory roll-forward, safety targets, net production, and manual examples;
- console and file logging without secret disclosure;
- a no-network CLI smoke check; and
- a no-network Streamlit startup check.

For a final end-to-end check, use a real key to run one CLI fetch and one
dashboard request, then inspect the raw JSON, processed CSV, console output, log
file, chart, and table.

## Project structure

```text
.
|-- docs/
|   `-- specs/                  # milestone scope and acceptance criteria
|-- src/supply_chain_planning_lab/
|   |-- api.py                 # FRED HTTP boundary
|   |-- cli.py                 # command-line interface
|   |-- dashboard.py           # local Streamlit interface
|   |-- demand.py              # FRED-to-demand assumptions and calculations
|   |-- forecasting.py         # baseline forecasts and performance measures
|   |-- driver_forecasting.py  # rolling-origin FRED-informed forecasts
|   |-- inventory.py           # inventory and net production requirements
|   |-- inspection.py          # processed-data quality and descriptions
|   |-- logging_config.py      # console and file logging setup
|   |-- metadata.py            # safe project setup information
|   |-- models.py              # Pydantic runtime validation
|   |-- output.py              # raw JSON and processed CSV output
|   |-- transform.py           # trusted project-record transformation
|   |-- workflow.py            # logic shared by CLI and dashboard
|   `-- resources/
|       `-- fred_permit_2000_2025.csv # fixed FRED source snapshot
|-- tests/
|   |-- fixtures/              # stable valid and invalid FRED examples
|   `-- test_*.py              # unit, boundary, workflow, and smoke tests
|-- .env.example
|-- pyproject.toml
`-- uv.lock
```

Generated `data/` and `logs/` directories are ignored by Git. Small stable test
examples belong in `tests/fixtures/`.

## Trust boundary

The application calls FRED's
[`fred/series/observations` endpoint](https://fred.stlouisfed.org/docs/api/fred/series_observations.html).
A request includes `series_id`, `observation_start`, `file_type`, and the API
key.

For a CLI fetch, the project:

1. receives the outside response;
2. preserves the exact raw text;
3. validates the response fields it relies on with Pydantic;
4. transforms only trusted observations into project records; and
5. writes the processed CSV and reports the result.

This order keeps the original evidence available if validation fails while
preventing malformed outside data from silently becoming plausible project
records.
