# HEC Role-Based Decision-Support Dashboard

Academic proof of concept for ENSIA617 - Information Technologies in Health.

Hospital El Carmen Dr. Luis Valentín Ferrada, Maipú.

## Current phase

The Day 1 architecture baseline, Day 2 data foundation, Day 3 indicator
engine, Day 4 Streamlit shell, and Day 5 ambulatory-waitlist visual layer are complete. The repository now contains the normalized Excel
contract, verified upload template, deterministic simulated operational and
professional data, a traceable public DEIS establishment snapshot, row
quarantine, explicit in-memory candidate activation, and 41 executable or
explicitly unavailable indicator bindings. The role-based shell adds dynamic
navigation, session-only upload validation, explicit activation, data-quality
status, KPI cards, role-aware charts, deterministic findings, MapLibre
georeferencing, specialty and referring-center drill-downs, accessible evidence
tables, and aggregated CSV downloads. A local redesign candidate now adds a
source-isolated HEC 2025 inpatient reference and observed monthly trend for
directorial use; it does not change the 41 operational indicators or their
upload contract.

## Data disclaimer

Operational and professional data are clearly simulated. The directorial
historical inpatient module is a separately labeled curated aggregate reference,
not simulated operational data and not an official live HEC feed. The prototype contains
no real patient or employee identifiers, patient addresses, or patient-level
drill-down. It is an academic BI/data-extraction and decision-support layer, not
an HIS, EHR, ERP, CDSS, production integration engine, or official HEC system.

## Design baseline

- [System architecture](docs/architecture/system-architecture.md)
- [Session architecture decision](docs/decisions/ADR-002-streamlit-session-architecture.md)
- [Normalized UI contract](config/ui_contract.json)
- [Role-based wireframes](docs/wireframes/role-based-wireframes.md)
- [HOT-fit evaluation baseline](docs/evaluation/hot-fit-baseline.md)

## Data foundation

- [Data ingestion contract](docs/architecture/data-ingestion-contract.md)
- [Machine-readable workbook contract](config/data_contract.json)
- [Verified Excel template 1.3](templates/plantilla_carga_hec_1_3.xlsx)
- [Governed simulated referral diagnoses](config/referral_diagnoses.json)
- [DEIS reference provenance](data/reference/deis_snapshot_manifest.json)
- [HEC inpatient reference architecture](docs/architecture/inpatient-historical-reference.md)
- [HEC inpatient source manifest](data/reference/hec_inpatient_2025_manifest.json)
- Deterministic simulated data under `data/simulated/`

The packaged demonstration `hec-sim-day5-v1` contains 3,400
simulated referrals, 2,200 simulated surgical cases, and 3,360 simulated
professional activities plus 6,240 simulated ambulatory-waitlist episodes,
for 15,200 accepted rows. Its deterministic profile
catalog covers all 15 clinical and 11 surgical MVP analytical specialties plus
one mixed Cirugía Pediátrica professional with separate clinical and surgical
lenses under the same identity and specialty. The coverage matrix keeps
applicable default role/service/specialty/profile indicators above their
approved minimum sample sizes in both Q1 and Q2. The DEIS snapshot
contains 55 unique establishments from the validated HEC service context.
Hospital El Carmen (`111101`) remains in that reference catalog as the fixed
destination marker, but the deterministic simulation and all external-network
aggregates exclude it as a referring origin. Compatible uploaded rows with
that origin remain counted in general data-quality totals as internal-origin
records.

Professional selectors use readable specialty/profile labels from
`config/professional_profiles.json`; internal `SIM-*` identifiers are never the
sole primary label. Organizational units without an approved analytical
specialty are intentionally excluded from professional selection while
remaining available to compatible service-chief views.

## Indicator engine

- [Indicator calculation contract](docs/architecture/indicator-engine.md)
- [Machine-readable indicator bindings](config/indicator_bindings.json)
- [Deterministic Q2 versus Q1 snapshot](data/derived/indicator_snapshot.json)

The engine calculates validated values, prior-period comparators, numerators,
denominators, valid sample sizes, target-applicability state, and explanatory
unavailability reasons. It does not use `eval`, generated formulas, AI, or
implicit zero substitution.

## Run the Streamlit shell locally

Install the pinned dependencies into the existing environment and start the app:

    ./.venv/bin/python -m pip install -r requirements.txt
    ./.venv/bin/python -m streamlit run app.py

The role selector personalizes an academic demonstration; it is not production
authentication. Uploaded XLSX candidates remain only in Streamlit session state.

## Contract validation

Run the standard-library validator with:

    ./.venv/bin/python scripts/validate_contracts.py
    ./.venv/bin/python scripts/validate_data_contract.py \
      --workbook templates/plantilla_carga_hec_1_3.xlsx
    ./.venv/bin/python scripts/calculate_indicators.py
    ./.venv/bin/python scripts/audit_day4_coverage.py
    ./.venv/bin/python scripts/audit_day5.py
    ./.venv/bin/python scripts/audit_day5_map.py
    ./.venv/bin/python scripts/audit_territorial_coverage.py

Run the test suite with:

    ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q

The suite includes pure integration, regression, and Streamlit AppTest coverage.
