# Sprint 01: FRED data workflow

## Goal

Create a runnable `uv` command that retrieves the FRED `PERMIT` series, preserves the raw response as evidence, and produces normalized records for later project use.

## User story

As a learner exploring supply-chain planning, I want to collect and normalize a real construction-market indicator so that later sprints can study how external signals might inform a fictional manufacturer's planning process.

## In scope

- Read `FRED_API_KEY` from the environment or a local `.env` file.
- Request the FRED `PERMIT` observations endpoint as JSON.
- Accept a validated ISO start date.
- Use an HTTP timeout and produce safe, understandable errors.
- Save the exact response text to a timestamped file in `data/raw/`.
- Convert valid observation dates and numeric values into normalized records.
- Skip FRED's `.` missing-value marker and count skipped observations.
- Save processed records as timestamped CSV in `data/processed/`.
- Print record counts, date coverage, and output paths.
- Report setup state without exposing the key or calling the API.
- Test transformation and output behavior using a committed fixture.

## Out of scope

- Treating building permits as customer demand
- Forecasting or trend classification
- Inventory and safety-stock calculations
- Bills of materials or procurement requirements
- Capacity planning or production scheduling
- Database storage, automation, CI, dashboard, or package publishing

## Acceptance criteria

1. `uv run planning-lab --help` succeeds.
2. `uv run planning-lab project-info` reports whether the key is configured without displaying it.
3. `uv run planning-lab fetch --start-date 2020-01-01` makes one documented FRED request when a valid key is configured.
4. A successful fetch writes one raw JSON response and one processed CSV file.
5. The processed CSV contains `series_id`, `period`, `value`, and `unit` columns.
6. Missing values are skipped and reported rather than causing invalid numeric output.
7. `uv run pytest` passes without a key or network access.
8. `.env`, `.venv/`, and `data/` are ignored by Git.
9. The README lets a new user install, configure, run, and test the project.
