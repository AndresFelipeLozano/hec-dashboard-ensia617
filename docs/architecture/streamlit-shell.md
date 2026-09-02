# Streamlit shell and role-based navigation

Status: Day 4 remediation candidate for renewed visual acceptance
Implementation date: 2026-09-01

## Scope

Day 4 introduces the first executable Streamlit shell. It integrates the
approved Day 2 ingestion layer and Day 3 deterministic indicator engine without
copying their parsing, validation, or KPI formulas.

Included:

- application entry point and dynamic multipage routing;
- Spanish role/context selection;
- bundled simulated dataset initialization;
- session-only Excel candidate validation and explicit activation;
- role-specific primary KPI cards and data-quality status;
- separate clinical and surgical mixed-professional lenses;
- unit, regression, AppTest, and headless smoke coverage.

Statistical charts, MapLibre establishment georeferencing, deterministic
prioritized findings, and the accessible map table are deferred to Day 5. No
placeholder chart, map, alert, finding, or substitute KPI is generated.

## Entry point and routing

`app.py` calls `st.navigation` exactly once per rerun and uses callable
`st.Page` objects with unique paths for Inicio, Dashboard, Carga de datos, and
Calidad de datos. Dashboard appears only after role confirmation; quality
appears only with an active dataset. The selected page executes with
`page.run()`; legacy `pages/` auto-discovery is not used.

Role confirmation now performs an atomic two-rerun Streamlit transition. The
submission normalizes and stores the role, schedules the dashboard route, and
clears incompatible draft widget keys. On the immediately following rerun,
Dashboard is registered in the single `st.navigation` call and `st.switch_page`
receives that registered callable `Page`. The browser therefore changes to
`/dashboard` without a second sidebar action. Reset schedules the inverse
transition to Inicio. An incomplete direct dashboard request cannot register
the protected page and falls back to Inicio.

Every page inherits the academic-demonstration, fully simulated-data, active
dataset, current role, and period context frame.

## Role-selection flow

- Directivo → Director or Director Médico.
- Jefe de Servicio → Clínico/Quirúrgico → MVP organizational unit → optional
  analytical specialty.
- Profesional → Clínico/Quirúrgico/Mixto → fictional `SIM-*` profile.

Canonical IDs are stored in session state. Services remain organizational
units from `services.json`; specialties remain children of their actual unit.
“Entrar al dashboard” is an explicit confirmation. This workflow personalizes
an academic demonstration and is not production authentication.

## Session state and bundled activation

`src/hec_dashboard/app_state.py` owns these explicit concepts:

- initialized and role context;
- active dataset, metadata, validation summary, source mode, and activation
  timestamp;
- candidate dataset, validation summary, and filename;
- current/comparison periods and last internal error.

There is no module-level active dataset. Each session receives independent
copies; reset-role preserves the active data.

First-session initialization reads
`templates/plantilla_carga_hec_v1.xlsx` through the protected XLSX reader and
`validate_workbook`. Activation requires contract `1.1.0`, dataset
`hec-sim-day4r-v2`, 8,960 accepted rows, zero quarantined rows, and 100%
acceptance. Failure stops safely; there is no raw-CSV fallback.

The immutable validated workbook parse is cached by repository path, workbook
size/mtime, metadata size/mtime, and professional-profile contract size/mtime.
Every session still receives deep copies;
candidate validation and activation are never cached as shared mutable state.

Streamlit session state is convenience state, not durable secure storage.

## Candidate validation and activation

The upload page provides the approved template download and an XLSX-only,
20-MB-limited uploader. Uploaded bytes are wrapped as an in-memory workbook;
they are never written to the repository or another persistent project path.

Validation records candidate metadata, structural outcome, total and per-sheet
accepted/quarantined rows, and aggregate issue categories. Candidate and active
datasets remain separate. Only a contract-valid candidate can be activated
explicitly. A rejected candidate preserves the active object. Restore
revalidates and activates the bundled simulation atomically.

## Configuration loading

`src/hec_dashboard/app_config.py` derives the repository root from its module
location. It caches immutable JSON text and returns an independently decoded
structure on each public load. Helpers validate top-level keys and look up
roles, indicators, UI views, organizational units, specialties, and labels.
There is no Streamlit dependency or sole reliance on the current directory.

## KPI presentation adapter

`src/hec_dashboard/presentation.py` reads exact `primary_indicator_ids` from
`role_matrix.json`, enforces the six-card limit, constructs
`IndicatorContext`, and calls the approved `IndicatorEngine`. It never
reimplements formulas.

Presentation objects preserve status, explanation, current/prior values,
numerator, denominator, valid sample size, reference metadata, and filters.
Formatting happens only at this boundary. Unavailable states use textual labels
and never render as zero.

Available cards retain primary visual weight. Required but unavailable
indicators appear in one compact table with Spanish state, valid `n`, required
`n`, and an accessible detail expander. The former stack of repeated warning
banners is not used.

## Mandatory professional-lens safeguard

The integration maps:

- `professional_clinical` → `professional_lens="clinical"`;
- `professional_surgical` → `professional_lens="surgical"`;
- `professional_mixed` → two independent calls using the same fictional
  Cirugía Pediátrica profile, specialty, and parent unit; only the activity
  class changes by lens.

No public professional role adapter can omit its lens. The unfiltered bundled
documentation references remain approximately 94.44% clinical and 98.15%
surgical. Mixed views use an explicit lens selector, render separate cards,
and never create a combined performance score.

## Data-quality view

The quality page exposes dataset provenance, contract, simulation status,
period coverage, activation time, accepted/quarantined totals, acceptance,
per-sheet counts, critical-field issues, invalid codes/dates, duplicates, and
unmatched DEIS origins. The approved quality KPIs are calculated through the
same adapter and engine. A last rejected candidate is explicitly shown as not
having replaced the active dataset.

## Tests

Python `unittest` covers configuration, state isolation, explicit activation,
all presentation statuses and filters, missing/invalid elective applicability,
clinical-row exclusion, deterministic median, denominator safety, lens-specific
documentation, and absence of a mixed combined score.

Streamlit 1.62 AppTest covers entry, disclaimers, all seven role workflows,
automatic callable-page transition, reset, template download, failed-upload
preservation, and the active quality page. Browser acceptance remains the
authoritative check for the visible URL transition.

## Day 4 remediation coverage design

The rejected 600-row simulation distributed 240 referrals and 144 surgeries
randomly across services, specialties, and two quarters. It did not reserve
indicator denominators, so a valid service filter could leave only 1–12
observations against a required minimum of 30. The engine was correct; the
simulation design was underpowered.

The replacement uses seed `617` and deterministic coverage strata:

- 17 clinical service/specialty leaves;
- 11 surgical service/specialty leaves;
- 40 scheduled new consultations and 40 scheduled follow-ups per clinical
  leaf and quarter;
- 40 completed elective surgeries per surgical leaf and quarter;
- 60 independently varied activities per profile/lens and quarter;
- one clinical simulated profile for each of 15 approved clinical analytical
  specialties;
- one surgical simulated profile for each of 11 approved surgical analytical
  specialties;
- one mixed Cirugía Pediátrica profile with outpatient/clinical and
  surgical/procedural lenses under the same identity, specialty, and service,
  without combining denominators or scores.

The resulting `hec-sim-day4r-v2` contains 3,400 referrals, 2,200 surgeries,
and 3,360 professional activities: 8,960 accepted records. Q1 and Q2 retain
direct comparability while service-level patterns rotate deterministically
through improvement, deterioration, and stability. Values are not uniformly
perfect.

The professional flow is `Tipo de usuario` → `Rol o enfoque` → `Especialidad`
→ readable simulated profile → dashboard. Variant-specific Streamlit widget
keys and immediate callbacks clear incompatible downstream specialty/profile
state before options are rebuilt. The submitted context stores role, type,
specialty ID/name, simulated profile ID/label, lens information, periods, and
dataset ID atomically. `config/professional_profiles.json` is the single mapping
source; UI code does not hard-code specialty/profile pairs.

Only approved analytical specialties are offered to professionals. Enabled
organizational units without an analytical specialty, such as Alivio del Dolor
y Cuidados Paliativos and Hospital de Día, remain valid service-chief contexts
but are excluded from professional selection because units and specialties are
not interchangeable.

`scripts/audit_day4_coverage.py` enumerates institutional roles, every
selectable service aggregate and specialty, professional profiles, both mixed
lenses, and both comparison periods. Active applicable primary indicators
fail the audit when they produce `insufficient_n`, `zero_denominator`, or
unexpected `not_applicable`. It also fails on missing specialty mappings,
profile/lens incompatibility, cross-specialty rows, mixed identity/scope
changes, incorrect per-period counts, or mixed-lens contamination.
Pending-definition and deferred bindings remain visible and explicitly exempt.

Responsive implementation uses Streamlit's automatic sidebar collapse,
container-width primary/reset actions, wrapping text, full-width selectors,
and KPI rows of at most three columns. This code review is not a substitute for
the user's authoritative 390 × 844 visual inspection.

## Performance observations

Local measurements on the development Mac after expansion:

- warm Streamlit health response: 0.0009 seconds;
- uncached bundled workbook load and validation: 0.3989 seconds;
- independent workbook validation: 0.2679 seconds;
- representative six-indicator professional calculation: 0.0043 seconds;
- complete AppTest Director selection and route flow: 0.5551 seconds;
- measured validation-and-calculation process peak RSS: 119,668,736 bytes.

Packaged sizes are 560,216 bytes for the XLSX, 434,453 bytes for referrals,
236,256 bytes for surgeries, and 519,872 bytes for professional activity.
The simulation generator is not invoked during ordinary application reruns.

## Security and privacy limitations

- Operational and professional records are completely simulated.
- Fictional profiles use `SIM-*`; no real patient or employee identifiers,
  patient addresses, or patient-level drill-down are accepted.
- No database, persistent upload store, production authentication, live
  HIS/EHR integration, predictive AI, external LLM, or internet data retrieval
  exists.
- No public professional ranking or composite score is produced.
- Ministerial references with pending applicability are not official HEC
  targets.

## DEIS provenance clarification

Day 2 asset generation consumed validated external DEIS ETL outputs in
authorized read-only mode. The committed runtime asset is
`data/reference/deis_establishments_ssmc_snapshot.csv`. The application reads
only that packaged snapshot through the approved ingestion contract and has no
runtime dependency on the external project.

## Remaining Day 5 limitations

Statistical charts, MapLibre georeferencing, accessible map table, and
deterministic prioritized findings remain outside this remediation. The
expanded workbook preserves the approved six sheets and column order, and its
styles and validation lists extend through row 15,000.
