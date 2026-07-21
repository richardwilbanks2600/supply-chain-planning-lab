# Project Guidance

## Purpose

Build an educational supply-chain planning tool in small, reviewable increments. The learner owns business and planning decisions; Codex may implement approved decisions but must keep important assumptions visible and explainable.

## Current sprint boundary

Sprint 1 only retrieves the FRED `PERMIT` series, preserves raw JSON, produces normalized CSV records, and reports generated file paths. Do not add forecasting, production planning, optimization, a database, or a dashboard unless the sprint specification is explicitly changed.

## Architecture

- `api.py` owns HTTP requests, response validation, and safe API errors.
- `transform.py` converts FRED observations into project records.
- `output.py` owns generated raw and processed files.
- `metadata.py` reports setup state without making an API call or exposing secrets.
- `cli.py` defines the user-facing command and coordinates the workflow.

Keep API, transformation, persistence, and presentation responsibilities separate.

## Commands

```shell
uv sync
uv run planning-lab --help
uv run planning-lab project-info
uv run planning-lab fetch --start-date 2020-01-01
uv run pytest
```

## Verification

- Tests must not call FRED or require an API key.
- Use fixture responses for transformation and output tests.
- Never print, log, fixture, or commit an API key.
- Keep `.env`, `.venv/`, and generated `data/` files ignored.
- Before adding planning logic, document the concept, assumptions, and a manually verifiable example.
