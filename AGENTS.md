# Project Guidance

## Purpose

Build an educational supply-chain planning tool in small, reviewable increments. The learner owns business and planning decisions; Codex may implement approved decisions but must keep important assumptions visible and explainable.

## Current milestone boundary

Milestone 4 is implemented as defined in
`docs/specs/milestone-04-baseline-forecasting.md`. Do not begin Milestone 5
until the FRED forecast horizon, information available at each forecast
origin, baseline method, and treatment of revised observations have been
reviewed and approved. Do not add inventory, production planning,
optimization, a database, or deployment.

## Architecture

- `api.py` owns HTTP requests, response validation, and safe API errors.
- `transform.py` converts FRED observations into project records.
- `output.py` owns generated raw and processed files.
- `metadata.py` reports setup state without making an API call or exposing secrets.
- `models.py` validates data received from FRED before transformation.
- `inspection.py` validates, filters, and describes processed observations.
- `demand.py` converts the fixed FRED snapshot into a transparent demand scenario.
- `forecasting.py` calculates and evaluates explainable demand baselines.
- `workflow.py` coordinates shared fetch and transformation logic for both interfaces.
- `logging_config.py` owns optional console and file logging.
- `cli.py` defines the user-facing command and coordinates the workflow.
- `dashboard.py` renders the local Streamlit interface without duplicating project logic.

Keep API, transformation, persistence, and presentation responsibilities separate.

## Commands

```shell
uv sync
uv run planning-lab --help
uv run planning-lab project-info
uv run planning-lab fetch --start-date 2020-01-01
uv run planning-lab inspect data/processed/fred_permit_<timestamp>.csv
uv run planning-lab --verbose --log-file logs/planning-lab.log fetch
uv run streamlit run src/supply_chain_planning_lab/dashboard.py
uv run pytest
```

## Verification

- Tests must not call FRED or require an API key.
- Use fixture responses for transformation and output tests.
- Use controlled mocks for successful and failed FRED behavior.
- Preserve a raw response before validating or transforming it.
- Keep descriptive measures separate from forecasts and planning assumptions.
- Never print, log, fixture, or commit an API key.
- Keep `.env`, `.venv/`, and generated `data/` files ignored.
- Before adding planning logic, document the concept, assumptions, and a manually verifiable example.
