# HEC dashboard system architecture

## Purpose and scope

This document defines the technical and functional baseline for the ENSIA617 HEC role-based decision-support dashboard. The product is an academic proof of concept that transforms public DEIS establishment reference data and simulated operational data into deterministic, role-specific aggregate views.

The prototype is a business-intelligence and data-extraction layer. It is not an HIS, EHR, ERP, CDSS, interface engine, production authentication system, real-time monitoring system, or source of official HEC performance results.

## System boundaries

| In scope | Out of scope |
|---|---|
| Streamlit application shell and role selector | Production identity, authentication, authorization, or user provisioning |
| Plotly aggregate charts and maps | Live HIS/EHR/LIS/RIS/ERP integration |
| Standardized Excel template, upload, validation, and explicit activation | Database, durable uploaded-data storage, or background processing |
| Simulated operational and professional profiles | Real patient or employee identifiers, patient addresses, or patient-level drill-down |
| Public DEIS establishment codes and coordinates | Changes to or runtime dependency on the frozen DEIS project |
| Deterministic indicators, findings, and narratives | Predictive AI, external LLMs, clinical orders, or diagnoses |
| Session-only active dataset | Public professional ranking or punitive composite scores |
| Academic-prototype evidence and aggregate export boundary | Institutional endorsement or official target certification |

Chilean Law 21.719 is a cross-cutting design constraint. Session state reduces persistence but does not itself provide privacy, access control, encryption guarantees, or durable security storage.

## Component architecture

~~~mermaid
flowchart LR
    U[Evaluator] --> SH[Streamlit application shell]
    SH --> RN[Role and navigation controller]
    SH --> SM[Session-state manager]
    X[Standardized Excel workbook] --> IV[Excel ingestion and schema validation]
    IV --> DN[Data normalization]
    D[Public DEIS establishment reference] --> DJ[DEIS establishment reference join]
    DN --> DJ
    DJ --> SM
    SM --> IC[Deterministic indicator calculation]
    IC --> FG[Deterministic finding generation]
    RN --> RP[Role-based presentation]
    IC --> RP
    FG --> RP
    RP --> PC[Plotly chart and map rendering]
    RP --> DQ[Data-quality reporting]
    RP -. future aggregate-only boundary .-> EX[Aggregate export/download]
~~~

The source contracts in config/services.json, config/indicators.json, config/role_matrix.json, and config/ui_contract.json configure selection, calculation references, role scope, map behavior, and presentation. Presentation code must not duplicate catalog definitions.

## Logical components

| Layer | Responsibility | Safe boundary |
|---|---|---|
| Streamlit application shell | Page composition, persistent prototype disclaimer, context bar, routing | Does not authenticate users |
| Role/navigation controller | Applies ADR-001 navigation and compatible role/service paths | Personalization only; not authorization |
| Session-state manager | Holds current selections, validation report, candidate dataset, and active validated dataset | Session state is ephemeral and not durable security storage |
| Excel ingestion and schema validation | Reads the standardized workbook and validates sheets, columns, types, codes, dates, duplicates, and critical fields | Does not activate a candidate implicitly |
| Data normalization | Produces canonical types, periods, codes, and null semantics | Missing, inapplicable, and denominator-zero states remain distinct from zero |
| DEIS establishment reference join | Matches origin establishment codes to the approved public reference snapshot | Uses establishment coordinates only; never patient addresses |
| Indicator calculation | Applies approved formulas, applicability, denominator, sample, and completeness rules | Deterministic; no generated calculations |
| Finding generation | Applies approved rule expressions and suppression conditions | Produces observation, interpretation boundary, and bounded review action |
| Role-based presentation | Restricts indicators, questions, selectors, and detail to the selected contract | Mixed professionals receive separate clinical and surgical lenses |
| Plotly rendering | Produces accessible charts and aggregate maps | No color-only meaning; maps have tabular equivalents |
| Data-quality reporting | Exposes acceptance, completeness, rejection reasons, timestamp, and active status | Quality limitations remain visible beside interpretations |
| Aggregate export boundary | May later export filtered aggregate results | Disabled until disclosure, provenance, and output contracts are approved |

## Session-state architecture

The session manager maintains separate objects:

- active_dataset: the last explicitly activated valid simulated dataset.
- candidate_dataset: the most recent uploaded and normalized candidate.
- validation_report: structural and row-level results for the candidate.
- reference_snapshot: the packaged public DEIS establishment reference.
- selection_context: role, service, specialty, filters, and period.
- derived_view: recalculable indicators and findings for the current selection.

The candidate and active datasets must never alias before activation. A failed upload updates only the validation report and candidate status. Closing or expiring the Streamlit session removes uploaded operational data; the design makes no claim that session memory is a secure vault or that infrastructure-level logs and caches are automatically safe.

## Data flow

1. The evaluator starts with the packaged simulated demonstration dataset or downloads the standardized template.
2. An uploaded workbook becomes a candidate, never the active dataset.
3. Structural validation checks file type, expected sheets, schema, required columns, and types.
4. Semantic validation checks critical fields, dates, allowed codes, duplicates, and DEIS origin-code matches.
5. Normalization creates canonical values and an explicit rejection set.
6. The quality report records accepted and rejected rows, reasons, validation timestamp, and candidate status.
7. Only a valid candidate can be explicitly activated.
8. Role, service, specialty, and other filters are applied to the active dataset.
9. The indicator engine calculates values and unavailable states; the finding engine evaluates only eligible results.
10. Role-based charts, findings, maps, tables, provenance, and accessible summaries are rendered from the same filtered result.

## Validation and dataset activation

~~~mermaid
sequenceDiagram
    actor E as Evaluator
    participant UI as Streamlit upload view
    participant V as Validator
    participant S as Session-state manager
    participant A as Active dataset

    E->>UI: Upload standardized Excel candidate
    UI->>V: Validate schema, values, codes, dates, duplicates
    V-->>UI: Validation report and candidate status
    alt Candidate invalid
        UI-->>E: Show rejection/quarantine summary
        S->>A: Preserve prior active dataset
    else Candidate valid
        UI-->>E: Offer explicit activation
        E->>UI: Confirm activation
        UI->>S: Atomically replace active dataset
        S->>A: Store candidate for this session only
        UI-->>E: Show active status and validation timestamp
    end
~~~

Activation is an explicit, atomic session transition. There is no partial activation and no fallback that silently substitutes rejected data.

## Deterministic indicator engine

The engine resolves indicator IDs from the approved indicator catalog and applies the catalog formula, profile applicability, minimum valid sample, required completeness, supported dimensions, and target class. Percentage denominators are filtered using documented semantics. A zero denominator returns an unavailable value, never numeric zero. Target comparison runs only after target applicability is valid for HEC and the selected service.

## Deterministic finding engine

The engine evaluates only rules from config/role_matrix.json. Before evaluation it applies all suppression conditions, including inapplicability, missing required target, insufficient sample, and insufficient completeness. Every displayed finding contains:

1. A factual observation.
2. An interpretation boundary that prevents unsupported causal or official-performance claims.
3. A bounded management review action.

At most five findings are displayed, using deterministic severity and tie-breaking rules to be specified during implementation. No LLM is needed to calculate or narrate a finding.

## Role and service filtering

ADR-001 and the service catalog control the navigation hierarchy. Directivo selects Director or Director Médico. Jefe de Servicio selects Clínico or Quirúrgico, an MVP-enabled compatible organizational unit, and an optional analytical specialty only when the unit has one. Profesional selects a simulated clinical, surgical, or mixed profile.

Filters synchronize cards, findings, charts, maps, accessible tables, denominators, and provenance. They must not silently alter denominator meaning. The mixed profile composes the clinical and surgical role contracts as separate lenses and prohibits a combined performance score.

## Georeferencing

The ingestion layer retains a simulated origin-establishment code. The reference join matches that code to the packaged, authoritative DEIS establishment snapshot and adds establishment name and coordinates. Unmatched codes remain visible in the quality report and do not receive invented coordinates.

The packaged reference must come from an independently controlled public DEIS distribution. It must not be copied from, generated by, or linked at runtime to the separate frozen DEIS project.

Maps aggregate by allowed role detail, apply a minimum geographic cell size of 10, and use only establishment coordinates. Suppressed cells are labeled as suppressed in accessible summaries and are not recoverable through tooltips, filters, tables, or exports. Each map has a synchronized tabular alternative.

## Data-quality controls

| Control | Required behavior |
|---|---|
| Schema | Reject unexpected or missing required structures with actionable messages |
| Critical fields | Report field-level missingness and critical_field_completeness_pct |
| Row acceptance | Report accepted percentage and rejected row count |
| Codes | Report invalid service/specialty codes and unmatched DEIS origins |
| Dates | Reject invalid or out-of-contract dates |
| Duplicates | Report duplicate simulated identifiers without exposing real identifiers |
| Activation | Require a valid candidate and explicit activation |
| Status | Show validation timestamp and active-dataset status |
| Nulls | Preserve missing, inapplicable, insufficient, and denominator-zero states |

## Privacy and security controls

- Use simulated operational and professional data only; do not ingest real patient or employee identifiers.
- Prohibit patient addresses and patient-level detail.
- Suppress geographic cells below 10 in every representation and later export.
- Prohibit public professional ranking and punitive composite scores.
- Keep uploaded data within the Streamlit session and do not intentionally persist workbooks.
- Avoid logging row payloads or uploaded contents; log only aggregate technical evidence if enabled.
- Validate file type, size limits, structure, and values before processing.
- Keep prototype and simulation badges persistent.
- Treat the public URL as accessible to anyone; no confidential data is suitable for upload.
- Review privacy controls against Law 21.719 before public demonstration and again before any future institutional pilot.

These controls reduce risk but do not make free public hosting appropriate for sensitive data.

## Deployment model

The MVP is a single Streamlit process with Plotly, packaged configuration, a packaged public DEIS reference snapshot, and a simulated demonstration dataset on free public proof-of-concept hosting. There is no database, production authentication, live integration, durable queue, or external LLM dependency. A cold restart may discard all session data, which is safe and expected.

## Observability and academic audit evidence

The prototype should expose or capture non-sensitive evidence appropriate to an academic demonstration:

- application version and contract versions;
- active dataset source mode and validation timestamp;
- aggregate accepted/rejected counts and validation reason categories;
- deterministic test results for formulas, contracts, upload scenarios, and privacy invariants;
- snapshot date and selected period;
- reproducible demonstration steps and screenshots if needed;
- deployment reachability checks without uploaded content.

No patient-level or row-level payload belongs in logs, screenshots, repository history, or evaluation evidence.

## Failure modes and safe behavior

| Failure | Safe behavior |
|---|---|
| Invalid workbook or schema | Reject/quarantine candidate; preserve active dataset |
| Invalid code or date | Report actionable row count/category; do not invent a correction |
| Unmatched DEIS code | Exclude from mapped geography, retain aggregate quality warning |
| Missing/inapplicable metric | Display “No disponible” with reason, not zero |
| Denominator zero | Suppress value and dependent finding |
| Sample or completeness below threshold | Suppress finding and display limitation |
| Reference applicability unknown | Show descriptive value without target judgment |
| Geographic cell below 10 | Suppress consistently in map, table, tooltip, and export |
| Mixed-profile lens failure | Keep lenses independent; do not synthesize a combined score |
| Session loss or host restart | Return to packaged simulation; do not imply persistence |
| Rendering failure | Retain accessible summary/table and a clear error state |

## Deferred capabilities

Live interoperability, production identity and role authorization, a database, durable audit logs, confidential-data processing, real-time refresh, predictive analytics, external LLM narratives, patient-level workflows, institutional target governance, and aggregate export are deferred. Each requires a new security, privacy, governance, operational, and technical decision.

## Traceability

| Concern | Source of truth |
|---|---|
| Organizational units and specialties | config/services.json; docs/architecture/service-catalog.md |
| Indicator definitions and target classes | config/indicators.json; docs/architecture/indicator-catalog.md |
| Role questions, primary cards, findings, maps, guardrails | config/role_matrix.json; docs/architecture/role-decision-matrix.md |
| Navigation and decision scope | docs/decisions/ADR-001-role-navigation.md |
| Session architecture decision | docs/decisions/ADR-002-streamlit-session-architecture.md |
| Page composition and accessible UI behavior | config/ui_contract.json; docs/wireframes/role-based-wireframes.md |
| Evaluation protocol | docs/evaluation/hot-fit-baseline.md |

## Acceptance criteria

- All contract files pass scripts/validate_contracts.py and the automated tests.
- The three navigation branches and seven approved role IDs are traceable without redefining indicators.
- Every non-mixed role view contains no more than six primary KPI cards and five findings.
- The mixed professional view renders separate clinical and surgical lenses without a combined score.
- Upload failure cannot replace the active validated dataset.
- Session data is explicitly non-durable, and the limitations of session state are documented.
- Missing, inapplicable, insufficient, and denominator-zero values are never rendered as zero.
- Maps use public establishment coordinates, suppress cells below 10, and provide accessible tables.
- Privacy, provenance, simulation, target applicability, and interpretation boundaries remain visible.
- The prototype is accurately positioned as academic BI decision support, not a production health information system.
