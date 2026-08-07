# Milestone 02: Validate and describe processed data

## Goal

Help a learner decide whether a processed `PERMIT` dataset is structurally
trustworthy and understand its basic values without treating the indicator as
company demand or a forecast.

## Approved descriptive measures

- **Minimum and maximum:** the smallest and largest values in the selected
  records.
- **Latest:** the value belonging to the chronologically latest selected
  record.
- **Latest change:** latest value minus the preceding valid observation. If a
  calendar month is missing, this is not described as a one-month change.
- **Trailing average:** the arithmetic mean of up to the 12 chronologically
  latest valid observations in the selected records. It is a description, not
  a forecast.

All values retain the source unit, `thousands_of_units_saar`. No rounding is
used in calculations; the command rounds only displayed values to one decimal
place.

## Data-quality rules

- The CSV header must be exactly `series_id,period,value,unit`.
- Every row must identify `PERMIT`, use a canonical `YYYY-MM` period, contain a
  finite numeric value, and use `thousands_of_units_saar`.
- Duplicate periods fail inspection because choosing which observation to use
  would require an unsupported business rule.
- Missing calendar months and nonchronological source order produce visible
  warnings. The command does not insert, interpolate, or silently reorder the
  source file.
- Filtering is inclusive. Descriptive measures are calculated after filtering
  and use chronological order.

## Manual example

Given these valid records:

| Period | Value |
| --- | ---: |
| 2026-01 | 100.0 |
| 2026-03 | 120.0 |
| 2026-04 | 140.0 |

The quality report identifies `2026-02` as missing. The minimum is `100.0`,
the maximum and latest value are `140.0`, the latest change is
`140.0 - 120.0 = 20.0`, and the trailing average is
`(100.0 + 120.0 + 140.0) / 3 = 120.0`.

## Meaning and limitations of SAAR

FRED reports `PERMIT` in thousands of housing units at a seasonally adjusted
annual rate (SAAR). A value of `1,500.0` describes an annualized pace of
approximately 1.5 million units after seasonal adjustment; it does not mean
1.5 million permits were issued during that month.

The series does not identify the fictional manufacturer's products, customers,
orders, inventory, suppliers, or capacity. These measures describe the
external indicator only. They do not establish causation, predict future
values, or convert the indicator into company demand.

## In scope

- Runtime validation of previously processed CSV rows
- Detection of duplicates, missing months, and source ordering
- Inclusive month filtering and chronological listing
- The approved descriptive measures
- Offline unit and CLI tests
- User documentation for the command, units, and limitations

## Out of scope

- Filling or interpolating missing values
- Trend labels, forecasts, or causal claims
- Fictional company demand, inventory, materials, capacity, or scheduling
- Database storage or hosted deployment

## Acceptance criteria

1. `planning-lab inspect CSV` does not require an API key or network access.
2. Malformed headers or rows fail with a clear line- or field-specific error.
3. Duplicate months fail quality inspection and suppress descriptive measures.
4. Missing months and nonchronological source order are reported visibly.
5. Start and end filters are inclusive and invalid ranges fail clearly.
6. The command lists selected normalized records and supports an optional row
   limit.
7. Measures match the manual example and handle empty or one-record selections.
8. Tests remain fixture- or temporary-file-based and never contact FRED.

