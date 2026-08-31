# ADR-001: Role-based navigation and decision scope

- Status: Accepted
- Decision date: 2026-08-31
- Product: HEC Role-Based Decision-Support Dashboard
- Institution: Hospital El Carmen Dr. Luis Valentín Ferrada
- Context: ENSIA617 academic proof of concept

## Decision

The application will begin with three view choices:

1. Directivo.
2. Jefe de Servicio.
3. Profesional de la Salud.

These choices personalize the information architecture. They are not production authentication or authorization.

## Navigation

### Directivo

The user selects:

- Director.
- Director Médico.

### Jefe de Servicio

The user selects:

1. Clínico or Quirúrgico.
2. A compatible HEC service or specialty.

### Profesional

The user selects a simulated profile:

- Clínico.
- Quirúrgico.
- Mixto.

Mixed profiles must retain separate clinical and surgical lenses. Incompatible denominators must never be merged into one performance score.

## Standard dashboard contract

Every role view must contain:

1. Role, selected scope, active period and data source.
2. Record count, validation status and snapshot date.
3. Four to six primary indicators.
4. Target, baseline or previous-period comparison when valid.
5. No more than five prioritized findings.
6. One temporal explanation.
7. One composition explanation.
8. A role-filtered referral map.
9. A bounded management-review action for each alert.
10. Indicator definition, lineage and data-quality limitations.

The first visible screen must answer:

- What is the current status?
- What changed?
- What requires attention?

## Service-catalog decision

The service selector uses a hierarchical model:

1. Clinical or surgical dashboard type.
2. HEC organizational service or unit.
3. Analytical specialty only when the selected unit contains specialties.

The official HEC 2023 organizational chart is authoritative for departments and organizational units. The HEC Public Accountability 2026 document is used for activity context and analytical specialty names.

The model distinguishes organizational structure from analytical granularity. For example:

- Especialidades Médicas Adulto contains analytical adult specialties.
- Especialidades Pediátricas contains Neurología Infantil and may contain other validated pediatric specialties.
- Cirugía Adulto contains surgical analytical specialties.
- Urología, Otorrinolaringología and Traumatología are selectable organizational services.
- Cirugía Infantil is maintained as a separate surgical service.

Neurología Infantil is supported by team-validated institutional context and must remain marked as such until final team sign-off.

Only units with an approved `clinical_outpatient` or `surgical` indicator profile are enabled in the ten-day MVP. Emergency, critical-care, inpatient and operating-room-support units remain registered but hidden until distinct indicator contracts are validated.

This hierarchy extends the approved navigation without adding unnecessary steps: the specialty selector appears only when applicable.

## Indicator decision

A metric may enter the dashboard only when it has:

- A management question.
- An exact definition.
- Numerator and denominator when applicable.
- Applicable role and service scope.
- Comparison basis.
- Data source and update cadence.
- Minimum-data condition.
- Alert rule.
- Bounded review action.
- Data-quality limitation.

Clinical and surgical services will not use one generic performance score.

## Georeferencing decision

Georeferencing will use DEIS establishment codes and coordinates with simulated aggregate referral data.

The prototype will not use:

- Patient addresses.
- Employee addresses.
- Exact patient coordinates.
- Patient-level map drill-down.
- Geographic cells below the disclosure threshold.

## Safety and representation

The prototype:

- Uses clearly labeled simulated operational data.
- Contains no real patient or employee identifiers.
- Is a BI and data-extraction proof of concept.
- Is not an HIS, EHR, CDSS or production interoperability engine.
- Does not issue clinical orders or diagnoses.
- Does not rank professionals publicly.
- Does not claim real-time operation.
- Does not permanently store uploaded workbooks.

## Consequences

Services, indicators, thresholds, applicability and labels must be configured outside chart code.

An indicator that is unavailable or inapplicable must disappear or be identified as unavailable. It must never be represented as zero.

## Acceptance criteria

This decision is implemented when:

- The three approved roles are available.
- All approved subchoices work.
- Clinical and surgical indicator sets differ.
- Mixed professional views remain separated.
- Filters synchronize cards, charts, maps and tables.
- Simulated-data and academic-prototype labels remain visible.
