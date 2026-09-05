# Day 5 referral-network map remediation

## Decision and root cause

The rejected map aggregated only by `origin_establishment_code` over a
simulation that cycled origins uniformly. Role and specialty selections often
therefore produced the same 12 positive bubbles and identical rankings.
Changing the color control changed only the encoding, not the scoped rows. The
cache was not the primary defect, but its key did not make the full analytical
context independently auditable.

The remediation keeps one aggregate bubble per public DEIS establishment and
introduces deterministic heterogeneous origin, specialty, diagnosis, and
period affinities. It does not add patient coordinates or personal referral
attribution.

A final semantic audit identified DEIS code `111101` as Hospital Clínico
Metropolitano El Carmen, the destination institution. Before correction it
appeared as an origin in 282 `DERIVACIONES`, 183 `CIRUGIAS`, 280
`ACTIVIDAD_PROF`, and 720 `LISTA_ESPERA_AMB` records. The deterministic origin
pool now excludes that code. The external-network scope also filters it
defensively for compatible uploads while retaining every accepted row in
general quality totals. HEC remains exactly once as a fixed-size, distinctive
destination marker and can never enter bubbles, rankings, center selectors,
accessible tables, or CSV exports.

## Analytical modes

1. **Red institucional** — directors see total referral volume, calculated
   dominant specialty, institutional share, top three specialties, principal
   prestation, and Q1–Q2 variation.
2. **Especialidad seleccionada** — directors choose a specialty; service
   chiefs choose only specialties compatible with their service; professionals
   inherit the simulated profile specialty. Bubble size is the selected scope,
   while color can encode dominant simulated diagnosis, center share, or trend.
3. **Centro derivador** — a mandatory selector drives ranked center-to-specialty,
   specialty-to-diagnosis, prestation, and ambulatory new/control views.

Every chart has an accessible aggregate table and simulated CSV download.
Displayed totals derive from the same filtered rows as the map.

## Simulated referral-diagnosis governance

`config/referral_diagnoses.json` is the single catalog. Its user-facing concept
is **Diagnóstico o motivo de derivación simulado**: it is not a confirmed
hospital diagnosis and has no asserted ICD-10 coding. Operational rows store
only the stable diagnosis-group ID. Ingestion rejects unknown IDs and IDs whose
declared specialty differs from the row specialty. Legacy 1.2 data without the
field remains valid and exposes the dimension as unavailable rather than zero.

## Cache and reconciliation

`map_cache_key` includes dataset identity/version, periods, role, service,
specialty, simulated professional context, lens, prestation, diagnosis,
selected center, map mode, and color mode. `map_signature` hashes that context
plus the sorted aggregate rows so repeated outputs are detectable.

`scripts/audit_day5_map.py` evaluates directors, all supported specialties,
clinical and surgical professionals, and both mixed lenses. It fails on
identical materially different specialty signatures, ignored role filters,
zero/non-finite bubbles, invalid coordinates, incompatible diagnoses, or any
map/table/center reconciliation mismatch. It also fails if `111101` appears in
any packaged origin field, external aggregate, accessible table, or external
CSV.

## Territorial coverage closure

The territorial source is governed by role instead of reusing the institutional
ambulatory map everywhere. Director, Medical Director, configured clinical
specialties, clinical professionals, and the clinical mixed lens use the
external ambulatory waiting-list network. Surgical chiefs, surgical
professionals, and the surgical mixed lens use `CIRUGIAS`, with optional
procedure filtering and no individual attribution. Clinical services without
an analytical specialty use service-level `DERIVACIONES`; this is the only
valid scope for Palliative Care and Hospital de Día.

The seed-617 generator concentrates a controlled share of simulated service
referrals among valid public DEIS establishments without increasing total
volume. Surgical origins are also allocated deterministically so each supported
procedure has a publishable cell in both Q1 and Q2. The rule n < 10 remains
strict for current cells, comparison values, and geographic drill-downs.

`scripts/audit_territorial_coverage.py` exhaustively evaluates all 74 default
role contexts in Q1 and Q2, plus every surgical procedure-period combination.
It verifies source and scope, public coordinates, suppression, absence of
professional attribution, map/table/CSV reconciliation, meaningful signature
changes, mixed-lens independence, Palliative Care without a fabricated
specialty, and deterministic generation.

## Interpretation limits

- All operational, profile, and referral-diagnosis data are simulated.
- Coordinates identify public establishments only.
- Counts below the governed minimum of 10 are suppressed.
- Professional views describe their specialty network; they do not attribute
  referrals to the selected fictional professional or rank professionals.
- The map is descriptive and non-causal. It is not an official HEC or DEIS
  operational product.
