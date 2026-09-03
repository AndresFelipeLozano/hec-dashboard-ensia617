# Day 3 deterministic indicator engine

## Purpose and boundary

The engine turns the approved 41-indicator catalog into executable,
reviewable calculations over the validated Day 2 candidate dataset. It is a
calculation layer only: it does not add Streamlit views, persistent storage,
production integrations, AI-generated formulas, or patient-level outputs.

The normative components are:

- `config/indicators.json`: approved definitions, units, profiles, dimensions,
  minimum sample sizes, polarity, and target metadata;
- `config/indicator_bindings.json`: one exact implementation binding for every
  catalog indicator;
- `src/hec_dashboard/indicator_engine.py`: deterministic calculation and result
  semantics;
- `data/derived/indicator_snapshot.json`: reproducible Q2 2026 versus Q1 2026
  demonstration output.

Catalog and binding IDs must match exactly. Engine construction fails when an
indicator is missing, duplicated, or added only on one side.

## Executable coverage

| Source | Active | Pending definition | Deferred | Total |
|---|---:|---:|---:|---:|
| `DERIVACIONES` and validation report | 14 | 0 | 0 | 14 |
| `CIRUGIAS` | 5 | 1 | 1 | 7 |
| `ACTIVIDAD_PROF` | 9 | 0 | 0 | 9 |
| `LISTA_ESPERA_AMB` | 10 | 0 | 0 | 10 |
| Not yet packaged | 0 | 0 | 1 | 1 |
| **Total** | **38** | **1** | **2** | **41** |

The three non-active bindings remain explicit rather than receiving invented
proxies:

| Indicator | State | Reason |
|---|---|---|
| `surgical_waitlist_resolution_pct` | `pending_definition` | Local definition of resolvable surgical caseload has not been approved. |
| `operating_room_utilization_pct` | `deferred` | Pavilion-hour inclusions and exclusions require validation. |
| `emergency_bed_lt12h_pct` | `deferred` | The MVP has no validated emergency-bed source. |

The complete one-to-one mapping, including source and implementation key, is in
`config/indicator_bindings.json`.

## Context and filters

`IndicatorContext` accepts a current period and an optional comparable previous
period. If the previous dates are omitted, the engine derives an immediately
preceding interval of equal duration. A reversed interval is rejected.

Filters are applied before calculation and are returned with every result:

- service and analytical specialty;
- DEIS origin establishment;
- referral type, procedure, or professional activity code;
- fictional professional profile key;
- professional clinical or surgical lens;
- approved indicator profile for applicability control.

Professional indicators force their defined lens. Mixed fictional profiles
remain separate clinical and surgical rows; the engine never creates a combined
professional score.

## Result contract

Every indicator returns the same serializable structure:

| Field | Meaning |
|---|---|
| `status` | `available`, `insufficient_n`, `zero_denominator`, `pending_definition`, `deferred`, `unavailable`, or `not_applicable` |
| `value` / `prior_value` | Rounded current and comparable values only when valid |
| `numerator` / `denominator` | Auditable calculation parts where applicable |
| `valid_n` / `minimum_valid_n` | Observed and required sample size |
| `reason_es` | User-facing explanation, including why a value is unavailable |
| `reference` | Target type, value, operator, authority, applicability, and evaluation state |
| dates and `filters` | Exact context used by the calculation |
| `calculation_basis_es` | Prototype-specific qualification when needed |

Missing values, zero denominators, insufficient samples, deferred sources, and
inapplicable indicators always return `value: null`. None is silently converted
to zero.

## Calculation rules

- Percentages are `numerator * 100 / denominator`.
- Counts are distinct contract-grain rows, not people.
- Medians use the validated `wait_days` population.
- P75 uses deterministic linear interpolation at position
  `(n - 1) * 0.75`.
- Referral growth uses the previous comparable referral count as denominator.
- Top-three origin share is computed after the active filters.
- Data-quality indicators use the immutable validation summary attached to the
  candidate.
- Rounding follows `config/indicator_bindings.json`: percentages and days to
  two decimals and counts to integers.

The professional ambulatory-surgery rate has an additional safeguard. Its
denominator contains only surgical-lens rows with
`elective_major_applicable_flag = true`; its numerator is the subset with
`ambulatory_major_flag = true`. The ingestion contract rejects ambulatory rows
without explicit applicability and prohibits clinical-lens rows from entering
that denominator.

## Target and reference semantics

Descriptive indicators return `not_applicable` for performance evaluation.
Approved project-quality targets may return `met` or `not_met`. Local and
ministerial references marked as pending applicability are displayed as
`pending_applicability` and are not scored, even when the numerical indicator is
available. This prevents a published reference from becoming an automatic
service target without validation.

## Reproducible snapshot and verification

The packaged snapshot calculates April–June 2026 against January–March 2026
with a fixed timestamp. Regenerate and verify with:

    ./.venv/bin/python scripts/generate_simulated_data.py
    ./.venv/bin/python scripts/calculate_indicators.py
    ./.venv/bin/python scripts/validate_data_contract.py \
      --workbook templates/plantilla_carga_hec_1_3.xlsx
    ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q

Acceptance requires 41 unique results, finite JSON numbers only, exact catalog
coverage, explicit non-active states, minimum-sample enforcement, no zero
substitution, stable comparable-period behavior, and a fully valid 15,200-row
packaged workbook.
