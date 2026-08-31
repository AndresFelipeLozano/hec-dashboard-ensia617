# HEC Role-Based Decision-Support Dashboard

Academic proof of concept for ENSIA617 - Information Technologies in Health.

Hospital El Carmen Dr. Luis Valentín Ferrada, Maipú.

## Current phase

The Day 1 architecture baseline and the Day 2 data foundation are complete.
The repository now contains the normalized Excel contract, verified upload
template, deterministic simulated operational and professional data, a
traceable public DEIS establishment snapshot, row quarantine, and explicit
in-memory candidate activation.

The Streamlit application implementation has not started yet.

## Data disclaimer

Operational and professional data are clearly simulated. The prototype contains
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
- [Verified Excel template](templates/plantilla_carga_hec_v1.xlsx)
- [DEIS reference provenance](data/reference/deis_snapshot_manifest.json)
- Deterministic simulated data under `data/simulated/`

The packaged demonstration contains 240 simulated referrals, 144 simulated
surgical cases, and 216 simulated professional activities. The DEIS snapshot
contains 55 unique establishments from the validated HEC service context.

## Contract validation

Run the standard-library validator with:

    ./.venv/bin/python scripts/validate_contracts.py
    ./.venv/bin/python scripts/validate_data_contract.py \
      --workbook templates/plantilla_carga_hec_v1.xlsx

Run the test suite with:

    ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
