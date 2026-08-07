# Supply Chain Planning Lab

Supply Chain Planning Lab is an educational Python project that retrieves,
validates, and displays a real construction-market indicator. It offers both a
repeatable command-line workflow and a local Streamlit dashboard backed by the
same project logic.

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

Start the local dashboard after configuring `FRED_API_KEY`:

```shell
uv run streamlit run src/supply_chain_planning_lab/dashboard.py
```

Streamlit prints a local URL and normally opens it in the default browser. In
the dashboard:

1. Choose the first observation date.
2. Select **Load validated FRED data**.
3. Review the valid and skipped record counts plus the approved descriptive
   measures.
4. Choose how many recent observations to display and their table order.
5. Inspect the trend chart and trusted detail rows.
6. Download the raw JSON evidence or validated CSV records if useful.

The dashboard calls the same `fetch_planning_data` workflow as the CLI. It does
not copy API requests, validation rules, or transformation logic into the user
interface.

The dashboard runs locally for this project. Deployment is not required.

## Understanding the unit

FRED reports `PERMIT` in thousands of housing units at a seasonally adjusted
annual rate (SAAR). For example, `1,500.0` describes an annualized pace of
approximately 1.5 million units after seasonal adjustment. It does not mean
1.5 million permits were issued in that single month.

Building permits do not identify this project's future fictional products,
customers, orders, inventory, suppliers, or production capacity. The indicator
and its summaries cannot establish causation, predict future values, or be used
as company demand without a separately documented and approved model.

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
|   |-- inspection.py          # processed-data quality and descriptions
|   |-- logging_config.py      # console and file logging setup
|   |-- metadata.py            # safe project setup information
|   |-- models.py              # Pydantic runtime validation
|   |-- output.py              # raw JSON and processed CSV output
|   |-- transform.py           # trusted project-record transformation
|   `-- workflow.py            # logic shared by CLI and dashboard
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
