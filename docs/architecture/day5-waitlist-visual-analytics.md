# Day 5 ambulatory waitlist and visual analytics

## Delivered boundary

Day 5 adds a backward-compatible contract 1.3 extension, deterministic
ambulatory-waitlist data, ten executable indicators, governed role views,
accessible Plotly charts, and a token-free MapLibre origin map. The feature
remains session-only, simulated, aggregated, and non-clinical. It does not add
patient identity, production authentication, durable uploads, or external
runtime dependencies.

## Queue semantics

`LISTA_ESPERA_AMB` has exactly 18 ordered fields and one row per simulated
episode at a quarterly snapshot. `new_consultation` requires
`queue_entry_date`; `followup_control` requires `control_due_date`. These dates
are mutually exclusive. Completion, scheduling, and exit dates or reasons are
validated against `episode_status` and `snapshot_date`.

The packaged `hec-sim-day5-v1` dataset uses seed 617 and contains 6,240 rows:
26 specialties × 2 queue types × 2 quarters × 60 episodes. Combined with the
unchanged Day 4 tables, the workbook contains 15,200 accepted rows at 100%
acceptance. Every row has `simulated_flag = SI`.

Contract 1.1 uploads remain activatable without `LISTA_ESPERA_AMB`. Contract
1.2 uploads remain activatable without `referral_diagnosis_id`. In those cases,
the affected indicator or diagnosis controls return `unavailable` with an
explanatory reason. They never infer a true zero from a missing dimension.

## Indicator formulas

All percentages are multiplied by 100. `open` means `open_unscheduled` or
`open_scheduled`; P75 uses deterministic linear interpolation.

| Indicator | Exact governed calculation |
|---|---|
| `new_waitlist_open_count` | Distinct open `new_consultation` episodes at `snapshot_date`. |
| `new_wait_median_days` | Median of `snapshot_date - queue_entry_date` among open new-consultation episodes. |
| `new_wait_p75_days` | P75 of `snapshot_date - queue_entry_date` among open new-consultation episodes. |
| `new_wait_over_90_pct` | Open new-consultation episodes with elapsed days `> 90` / all open new-consultation episodes. The band is analytical, not an official target. |
| `new_waitlist_resolution_pct` | New-consultation episodes with `completed` or valid `exited` status / all new-consultation episodes observed at the period snapshot. |
| `followup_overdue_open_count` | Distinct open `followup_control` episodes with `control_due_date <= snapshot_date`. |
| `followup_overdue_median_days` | Median of `snapshot_date - control_due_date` among open overdue controls. |
| `followup_overdue_p75_days` | P75 of `snapshot_date - control_due_date` among open overdue controls. |
| `followup_unscheduled_pct` | `open_unscheduled` overdue controls / all open overdue controls. |
| `followup_resolution_pct` | Completed controls / all controls with `control_due_date <= snapshot_date`. |

Counts allow a true zero only when the sheet and governed scope are present.
Distribution and rate indicators require n ≥ 30. A zero denominator, an
insufficient sample, or a missing legacy sheet remains explicitly unavailable.

Professional views use specialty-level new demand and restrict follow-up rows
to `professional_profile_id`. The one specialty with two simulated profiles
allocates 30 follow-up episodes per profile and period. Mixed profiles still
render clinical and surgical lenses independently with no combined score.

## Visual governance

Every role dashboard uses five tabs: Resumen, Acceso y listas de espera,
Origen territorial, Actividad y calidad, and Datos y definiciones. Charts are built
from governed aggregates and include an accessible table plus CSV download.
Prioritized findings are deterministic descriptions with an explicit
non-causal interpretation boundary and review action.

The reusable activity layer changes its governed aggregates by role:

| Role | Trend and composition shown |
|---|---|
| Director / Director Médico | Ambulatory referrals versus registered surgical demand, plus current referral mix by specialty. |
| Clinical service chief | New and follow-up referrals with their no-show counts, plus current ambulatory outcomes. |
| Surgical service chief | Waiting, completed and suspended surgical events, plus procedure mix. |
| Clinical professional | Scheduled, completed and no-show activity, plus new-consultation, control and teleconsultation mix for the selected simulated profile. |
| Surgical professional | Scheduled, completed and suspended activity, plus procedural mix for the selected simulated profile. |
| Mixed professional | The same Pediatric Surgery identity is retained, while clinical and surgical activity rows are filtered and rendered under separate lenses. |

The access tab also plots two-period open-count and P75 trends from the
governed indicator engine; the Streamlit rendering layer does not recalculate
those formulas.

The origin map uses Plotly `scatter_map` with the `carto-positron` MapLibre
style and requires no token. It exposes three linked modes: institutional
network, selected specialty, and referring-center drill-down. Bubble size is
calculated from filtered episodes. Color represents the dominant destination
specialty, dominant simulated referral diagnosis, selected-specialty share, or
period trend according to the active mode. Every center drill-down reconciles
specialty, diagnosis, prestation, and new/control context with the same scoped
rows. Cells with n < 10 and invalid coordinates are omitted. Hospital El
Carmen (`111101`) is the destination and appears once as a constant-size
context marker; it is excluded from the external-origin universe even when a
compatible upload contains internal-origin rows. Those rows remain visible in
general acceptance and quality totals under an explicit internal-origin
classification. The accessible table remains available if map tiles cannot
render. See
`docs/architecture/day5-map-network-remediation.md` for the analytical model.

## Data quality and performance

The quality page reports rows by table, waitlist-sheet presence, counts by
queue and quarter, chronology and status consistency, DEIS coordinate
completeness, profile-specialty compatibility, and the number of indicators
made unavailable by a legacy 1.1 workbook. It also reports internal HEC-origin
records excluded from external-network analyses and the resulting external
network row count.

Closure measurements on the local reference environment (15,200 rows) were:
data load 0.0159 s; full validation 0.1006 s; 41-indicator calculation 0.0257 s;
map aggregation 0.0017 s; representative role-chart preparation 0.0149 s;
workbook regeneration plus validation round-trip 0.7367 s; and peak
benchmark-process memory 172.73 MB. The headless server became ready in about 1.2 s, and the
first real-browser Director dashboard rerun completed in 3.090 s. These are
development-machine observations, not production service-level guarantees.

## Verification

Run the closure checks with:

    ./.venv/bin/python scripts/validate_contracts.py
    ./.venv/bin/python scripts/validate_data_contract.py \
      --workbook templates/plantilla_carga_hec_1_3.xlsx
    ./.venv/bin/python scripts/calculate_indicators.py
    ./.venv/bin/python scripts/audit_day4_coverage.py
    ./.venv/bin/python scripts/audit_day5.py
    ./.venv/bin/python scripts/audit_day5_map.py
    ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q

`audit_day5.py` verifies 52 specialty-period contexts, 54
professional-period contexts, 520 specialty-indicator calculations, 270
professional follow-up calculations, map reconciliation, deterministic
generation, privacy fields, workbook validity, and runtime.
