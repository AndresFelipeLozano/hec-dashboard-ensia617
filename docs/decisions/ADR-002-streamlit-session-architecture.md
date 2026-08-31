# ADR-002: Streamlit session architecture

- Status: Accepted
- Decision date: 2026-08-31
- Product: HEC Role-Based Decision-Support Dashboard
- Context: ENSIA617 academic proof of concept

## Context

The ten-day prototype must demonstrate role-specific decision support, standardized Excel ingestion, aggregate georeferencing, deterministic indicators, and safe simulated professional feedback at zero direct software and hosting cost. It must be publicly demonstrable without representing itself as a production HEC system. Uploaded operational data must not be persisted, and a failed upload must not replace the last valid in-session dataset.

The design must remain small enough for academic delivery while preserving a clear migration boundary for any future institutional pilot.

## Decision

The MVP will use:

- Streamlit for the application and navigation shell.
- Plotly for interactive aggregate charts and maps.
- A standardized Excel workbook as the controlled ingestion interface.
- Public DEIS establishment reference data for establishment codes and coordinates.
- Clearly simulated operational and professional data held only in the Streamlit session.
- Deterministic code for indicator calculation, rule evaluation, and findings.
- Free public proof-of-concept hosting.
- No database in the initial MVP.
- No production authentication or authorization.
- No live HIS/EHR integration.

Session state will keep the active validated dataset separate from an uploaded candidate and its validation report. A valid candidate requires explicit activation. Invalid candidates remain rejected or quarantined, and the prior active dataset remains unchanged.

Session state is an application-lifecycle convenience, not durable security storage. The public prototype must reject the use of confidential or identifiable data by policy and design.

## Alternatives considered

| Alternative | Reason not selected for this MVP |
|---|---|
| Database-backed web application | Adds persistence, credentials, schema migration, operations, security, and hosting work that is unnecessary for the academic demonstration |
| Production identity provider and role-based access control | The selector personalizes information; production authorization requires institutional identity, governance, threat modeling, and testing |
| Live HIS/EHR interfaces | Requires vendor, institutional, semantic, security, and operational agreements outside the ten-day scope |
| Desktop BI workbook | Weakens controlled upload behavior, reproducible public demonstration, and explicit session activation |
| Static dashboard | Cannot demonstrate role navigation, safe upload validation, and synchronized exploration |
| External or paid LLM narratives | Introduces cost, availability, privacy, reproducibility, and unsupported-interpretation risks |
| Persist uploaded files on local disk | Conflicts with the session-only privacy boundary and complicates public hosting |

## Consequences

### Positive

- The team can implement and demonstrate the approved journeys with a small, free stack.
- Configuration remains separable from presentation code.
- Deterministic outputs are reproducible and testable.
- Session-only activation limits intentional persistence and makes failed-upload rollback straightforward.
- The architecture clearly distinguishes the prototype from an institutional system.

### Negative

- Sessions can be lost on timeout, refresh, restart, or host recycle.
- Multiple evaluators do not share an authoritative dataset.
- There is no durable audit trail, workflow state, or institutional access control.
- Free hosting may have cold starts, resource limits, and availability variation.
- Excel provides controlled syntactic and semantic exchange, not full interoperability.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Sensitive data uploaded to a public prototype | Persistent warning, strict schema, prohibition of identifiers and addresses, no intentional persistence, public demonstration with simulation only |
| Invalid upload replaces good data | Candidate/active separation, explicit activation, atomic state transition, automated invariant |
| Session loss is mistaken for data durability | Visible session-only notice and packaged simulated fallback |
| Reference target is treated as an official HEC target | Applicability gate and explanatory text beside every reference |
| Professional feedback is used punitively | Simulated profiles, no ranking, no combined score, bounded non-causal interpretation |
| Small geographic cells disclose information | Minimum cell size of 10 across map, table, tooltip, and any future export |
| Deterministic rule is misread as a decision | Findings require an interpretation boundary and human review action |

## Security limitations

The MVP does not provide production authentication, role enforcement, tenant isolation, secure durable storage, institutional audit logging, data-loss prevention, malware scanning, key management, or formal incident response. Streamlit session state is not a security boundary. The prototype is unsuitable for real clinical, employee, or confidential operational data.

Law 21.719 remains a cross-cutting constraint; using simulated data does not remove the need to review purpose limitation, minimization, transparency, security, and accountability before any future real-data use.

## Deployment implications

The application can be deployed as one free public Streamlit service containing code, approved contracts, the simulated dataset, and a packaged public DEIS reference snapshot. Uploaded data lives only for the session and must not be written to a repository, database, or durable host path. Restarts safely return the app to the packaged simulation. Aggregate export remains disabled until separately approved.

## Conditions requiring reconsideration

Revisit this decision before any of the following:

- use of real, identifiable, confidential, or institutionally sensitive data;
- institutional pilot or production use;
- multiple users requiring shared or durable state;
- production authentication, authorization, or audit requirements;
- live HIS/EHR or other system integration;
- scheduled refresh, background jobs, or real-time operation;
- durable exports, workflows, comments, or approvals;
- stronger availability, recovery, monitoring, or performance commitments;
- predictive analytics or an external AI dependency;
- changes in legal, institutional, hosting, or DEIS licensing constraints.
