# Sprint 02: Practicum hardening and dashboard

## Goal

Strengthen the existing FRED data workflow with controlled automated tests,
runtime validation, diagnostic logging, and a local browser dashboard while
keeping one shared set of project logic.

## User story

As a learner reviewing construction-market data, I want trustworthy validation,
repeatable evidence, and both command-line and browser interfaces so that I can
inspect the same normalized observations in the way that fits my task.

## In scope

- Validate incoming FRED observations with Pydantic before transformation.
- Preserve the raw response before validation so malformed outside data remains
  available for inspection.
- Add fixture-backed and mocked tests for successful and failed API behavior.
- Add optional `--verbose` console logging and `--log-file PATH` file logging.
- Keep secrets and full request parameters out of logs.
- Move fetch and transformation coordination into shared workflow code.
- Add a local Streamlit dashboard that accepts a start date and displays
  validated observations, summary measures, a trend chart, and a detail table.
- Let dashboard users filter the number of displayed observations and choose
  chronological or reverse-chronological order.
- Document setup, tests, CLI commands, logging, and dashboard use.

## Out of scope

- Treating building permits as customer demand
- Forecasting or trend classification
- Inventory, materials, capacity, scheduling, or optimization logic
- Database storage
- Hosted deployment

## Acceptance criteria

1. Tests run without an API key or live FRED request.
2. Mocked tests cover success, timeout, HTTP failure, connection failure,
   invalid JSON, and unexpected response data.
3. Pydantic rejects missing, malformed, or nonnumeric observation fields with a
   clear project error.
4. The CLI writes the exact raw response before attempting validation.
5. `--verbose` writes operational messages to the console without secrets.
6. `--log-file PATH` writes detailed messages to a file without secrets.
7. Both CLI and dashboard call the same workflow function.
8. The dashboard starts locally and provides useful success and error states.
9. `uv run pytest` and a no-network installed-command smoke check pass.
10. The README enables another person to install and run the project.
