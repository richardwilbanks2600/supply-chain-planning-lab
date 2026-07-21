# Supply Chain Planning Lab

Supply Chain Planning Lab is an educational command-line project that prepares real economic data for future supply-chain planning exercises. The current command retrieves a construction-market indicator, preserves the raw API response, and produces an inspectable CSV dataset. Future versions will combine external signals with fictional demand, inventory, supplier, BOM, and capacity data to explain how production plans are built.

## Data source

The project uses the Federal Reserve Bank of St. Louis [FRED API](https://fred.stlouisfed.org/docs/api/fred/) and the [`PERMIT` series](https://fred.stlouisfed.org/series/PERMIT): new privately owned housing units authorized in permit-issuing places. The series is monthly and reported as thousands of units at a seasonally adjusted annual rate.

Building permits are treated here only as an external construction-market indicator. They are not customer orders or a company forecast.

The application calls the [`fred/series/observations` endpoint](https://fred.stlouisfed.org/docs/api/fred/series_observations.html). An example request is:

```text
GET https://api.stlouisfed.org/fred/series/observations
    ?series_id=PERMIT
    &observation_start=2020-01-01
    &file_type=json
    &api_key=<YOUR_FRED_API_KEY>
```

The response contains request metadata and an `observations` list. Each observation includes a date, a value represented as text, and FRED real-time dates. Missing observation values may be represented by `.`.

## What the command produces

Each successful fetch creates two timestamped files:

- `data/raw/fred_permit_<timestamp>.json` preserves the response body returned by FRED.
- `data/processed/fred_permit_<timestamp>.csv` contains normalized `series_id`, `period`, `value`, and `unit` fields.

Generated data is intentionally ignored by Git. The small response in `tests/fixtures/` is committed so tests remain stable and do not require a network connection or API key.

## Install

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and clone the repository. From the repository directory, install the project and development dependencies:

```shell
uv sync
```

Create a local environment file.

PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS or Linux:

```shell
cp .env.example .env
```

Open `.env` and add your own FRED key:

```dotenv
FRED_API_KEY=your_key_here
```

Do not commit `.env`. FRED API keys are available from the [FRED API key page](https://fredaccount.stlouisfed.org/apikeys).

## Run

Inspect the local setup without calling FRED or revealing the key:

```shell
uv run planning-lab project-info
```

Fetch all observations starting in January 2020:

```shell
uv run planning-lab fetch --start-date 2020-01-01
```

Use `--output-dir` to choose another generated-data directory:

```shell
uv run planning-lab fetch --start-date 2020-01-01 --output-dir data
```

Display command help:

```shell
uv run planning-lab --help
uv run planning-lab fetch --help
```

## Test

Tests operate on committed fixtures and never call the live API:

```shell
uv run pytest
```
