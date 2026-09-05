# HEC historical inpatient reference

Status: local Director prototype at the visual-review gate

## Boundary

The HEC 2025 inpatient reference is independent from the simulated operational
workbook and its 41 indicators. It is never uploaded, activated, joined to
patient-level data, or compared arithmetically with Q1/Q2 2026 ambulatory data.
`config/inpatient_reference.json` grants access only to `director` and
`medical_director`. All other roles fail closed in the reference loader.

## Curated artifacts

- `data/reference/hec_inpatient_2025.csv` contains exactly one annual row for
  establishment code `111101` and only the minimum approved aggregate fields.
- `data/reference/hec_inpatient_monthly_2025.csv` contains twelve observed
  HEC-only monthly primitive rows. The five primitive column sums must equal
  the annual row before the loader returns data.
- `data/reference/hec_inpatient_2025_manifest.json` records source identity,
  hashes, territorial scope, period evidence, privacy rules, and limitations.

The supplied workbook contains one Maipú record and no Cerrillos record.
Cerrillos is therefore reported as absent from the source, never as zero
capacity or activity. Address, telephone, and source coordinates are excluded.
If geography is needed elsewhere, the application continues to use the
packaged DEIS reference keyed by code `111101`.

The workbook does not encode a performance year. The local teaching HTML
corroborates 2025 because its title and source statement identify 2025 hospital
statistics and its HEC annual primitives match the workbook exactly. The HTML
also declares a 2026-04-16 cutoff. This is documented as secondary curated
academic evidence rather than the original upstream MINSAL dataset.

## Deterministic calculations

`src/hec_dashboard/inpatient_reference.py` recalculates every result from
primitive fields:

- occupancy = occupied bed-days / available bed-days × 100;
- average available beds = available bed-days / calendar days;
- average length of stay = total stay-days / discharges;
- discharges = annual or monthly discharge count;
- crude lethality = death discharges / discharges × 100.

Missing inputs return `unavailable`; a zero denominator returns
`zero_denominator`. Results carry numerator, denominator, status, source class,
period, explanation, and filters. No previous-period value, delta, target, or
traffic-light classification is generated. Crude lethality is explicitly
unadjusted and unsuitable for ranking or causal interpretation.

## Presentation

The Director prototype uses four neutral cards, average available beds as
secondary context, one selectable monthly trend, an accessible aggregate table
and CSV download, and a compact technical source expander. Its period and source
badges remain independent from the operational quarter selector. The same
component is ready for the Medical Director only after approval of the visual
language; it must never be called from Service Chief or Professional views.
