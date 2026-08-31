# HEC Role-Based Decision-Support Dashboard

Academic proof of concept for ENSIA617 - Information Technologies in Health.

Hospital El Carmen Dr. Luis Valentín Ferrada, Maipú.

## Current phase

The Day 1 architecture and design baseline is complete. The approved scope is a
role-personalized Streamlit and Plotly proof of concept with standardized Excel
upload, session-only activation, deterministic indicators and findings, and
aggregate maps based on public DEIS establishment coordinates.

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

## Contract validation

Run the standard-library validator with:

    ./.venv/bin/python scripts/validate_contracts.py

Run the test suite with:

    ./.venv/bin/python -m pytest -q
