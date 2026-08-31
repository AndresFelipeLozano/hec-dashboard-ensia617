# Role-based wireframes

## Purpose and design principles

These structured wireframes translate the approved role matrix and UI contract into ordered page sections. They are implementation contracts, not visual styling specifications.

- Lead with current status, change, and required review.
- Keep role, service/specialty scope, period, provenance, record count, validation status, and simulation status visible.
- Limit each view to six primary KPI cards and five prioritized findings.
- Use progressive aggregate detail; never expose patient-level detail.
- Use reference targets only after applicability is validated and explain their status.
- Preserve missing, inapplicable, insufficient, and denominator-zero states as “No disponible,” never zero.
- Do not encode meaning through red/green color alone.
- Give every chart and map a textual summary; give every map a synchronized accessible table.
- Keep professional feedback simulated, contextual, non-punitive, and free of public ranking.
- Render mixed professional activity as separate clinical and surgical lenses.

## 1. Landing and role selection

| Order | Region | Contract |
|---:|---|---|
| 1 | Header | “Tablero de apoyo a decisiones por rol — Hospital El Carmen” |
| 2 | Status banner | “Prototipo académico. Datos operacionales y profesionales simulados.” State that the product is not an HIS/EHR/CDSS or official HEC system. |
| 3 | Purpose | Briefly explain role-specific aggregate decision support and public DEIS establishment georeferencing. |
| 4 | Role selection | “Directivo”, “Jefe de Servicio”, “Profesional” |
| 5 | Conditional next step | Directivo: “Director” or “Director Médico”. Jefe: “Clínico” or “Quirúrgico”, compatible unit, optional specialty. Profesional: “Clínico”, “Quirúrgico” or “Mixto”. |
| 6 | Data entry points | “Explorar datos simulados”, “Cargar archivo Excel”, “Descargar plantilla” |
| 7 | Privacy note | No real identifiers, patient addresses, patient-level detail, or confidential operational data. |
| 8 | Unavailable/error state | Preserve the current selection and explain incompatible or unavailable options without silently changing role. |

## Shared dashboard regions

Every dashboard below uses this order: header; role/service context; filters; KPI row; prioritized findings; main chart; secondary chart; map; accessible map table; interpretation note; provenance; empty/unavailable/error state. Findings contain an observation, interpretation boundary, and review action.

## 2. Director

| Order | Region | Contract |
|---:|---|---|
| 1 | Header | “Visión institucional — Director”; persistent simulated-data badge |
| 2 | Role/service context | “Directivo — Director”; institutional scope; active period and snapshot |
| 3 | Filters | Period required; service, specialty, and prestation optional |
| 4 | KPI card row | referrals_total; wait_p75_days; ges_compliance_pct; new_no_show_pct; elective_surgery_suspension_pct; accepted_record_pct |
| 5 | Prioritized findings | Up to five institutional access, guarantee, surgery, network, and data-confidence findings |
| 6 | Main chart | Time trend for referrals_total and wait_p75_days with comparable-period context |
| 7 | Secondary chart | Service comparison using ges_compliance_pct and elective_surgery_suspension_pct; no individual ranking |
| 8 | Georeferenced map | Director map contract: aggregate demand and territorial change |
| 9 | Accessible map table | Origin establishment, aggregate count, selected color measure, suppression status |
| 10 | Interpretation note | “Las señales simuladas orientan revisión; no establecen desempeño oficial ni causalidad.” Explain target applicability. |
| 11 | Data provenance | Simulated operational source, public DEIS reference, snapshot, record count, validation status |
| 12 | Empty/unavailable/error | Show “No disponible” and reason; failed upload does not replace active data |

## 3. Director Médico

| Order | Region | Contract |
|---:|---|---|
| 1 | Header | “Visión clínico-operacional — Director Médico”; persistent simulated-data badge |
| 2 | Role/service context | “Directivo — Director Médico”; institutional clinical scope, period, snapshot |
| 3 | Filters | Period required; service, specialty, prestation, and GES status optional |
| 4 | KPI card row | referral_growth_pct; wait_p75_days; discharge_rate_pct; referral_pertinence_pct; ges_compliance_pct; surgical_waitlist_resolution_pct |
| 5 | Prioritized findings | Up to five pressure, resolution, pertinence, GES, and surgical-resolution findings |
| 6 | Main chart | Specialty pressure trend using referral_growth_pct and wait_p75_days |
| 7 | Secondary chart | Service/specialty comparison using discharge_rate_pct and referral_pertinence_pct |
| 8 | Georeferenced map | Medical Director map contract: origins by specialty, prestation, diagnostic group, or GES filter |
| 9 | Accessible map table | Origin, specialty/prestation context, aggregate measures, suppression status |
| 10 | Interpretation note | Separate descriptive signal from causal interpretation; label references as conditional |
| 11 | Data provenance | Simulated source, public DEIS reference, period, timestamp, validation status |
| 12 | Empty/unavailable/error | State failed applicability, minimum sample, completeness, or denominator condition |

## 4. Jefe de Servicio Clínico

| Order | Region | Contract |
|---:|---|---|
| 1 | Header | “Gestión del servicio clínico”; persistent simulated-data badge |
| 2 | Role/service context | “Jefe de Servicio — Clínico”; selected MVP-enabled clinical unit and optional analytical specialty |
| 3 | Filters | Period and clinical unit required; specialty, prestation, and origin optional |
| 4 | KPI card row | referrals_total; wait_p75_days; new_no_show_pct; followup_no_show_pct; discharge_rate_pct; referral_pertinence_pct |
| 5 | Prioritized findings | Up to five demand, access, resolution, referral, and teleconsult review findings |
| 6 | Main chart | Access trend using referrals_total, wait_p75_days, and new_no_show_pct |
| 7 | Secondary chart | Referral/resolution comparison using referral_pertinence_pct and discharge_rate_pct |
| 8 | Georeferenced map | Clinical chief map contract: referring origins, wait, and pertinence |
| 9 | Accessible map table | Origin, prestation, aggregate count/measure, suppression status |
| 10 | Interpretation note | Keep denominator and selected scope visible; do not infer cause from association |
| 11 | Data provenance | Active simulated dataset, public DEIS reference, period, validation and record counts |
| 12 | Empty/unavailable/error | Preserve service context and explain missing contract, sample, completeness, or denominator |

## 5. Jefe de Servicio Quirúrgico

| Order | Region | Contract |
|---:|---|---|
| 1 | Header | “Gestión del servicio quirúrgico”; persistent simulated-data badge |
| 2 | Role/service context | “Jefe de Servicio — Quirúrgico”; selected MVP-enabled surgical unit and optional specialty |
| 3 | Filters | Period and surgical unit required; specialty, procedure, and origin optional |
| 4 | KPI card row | surgical_waitlist_open_count; surgery_wait_p75_days; elective_major_surgery_count; ambulatory_major_surgery_pct; elective_surgery_suspension_pct; surgical_waitlist_resolution_pct |
| 5 | Prioritized findings | Up to five waitlist, wait, output, suspension, and resolution findings |
| 6 | Main chart | Waitlist size and surgery_wait_p75_days over comparable periods |
| 7 | Secondary chart | Output mix using elective_major_surgery_count, ambulatory_major_surgery_pct, and elective_surgery_suspension_pct |
| 8 | Georeferenced map | Surgical chief map contract: aggregate origins, procedures, list size, and wait |
| 9 | Accessible map table | Origin, procedure, aggregate measures, suppression status |
| 10 | Interpretation note | Explain eligibility/complexity; do not attribute suspension responsibility |
| 11 | Data provenance | Active simulated dataset, public DEIS reference, period, validation and record counts |
| 12 | Empty/unavailable/error | Identify missing hours, target, sample, completeness, or denominator; never substitute zero |

## 6. Profesional Clínico

| Order | Region | Contract |
|---:|---|---|
| 1 | Header | “Retroalimentación clínica del perfil simulado”; persistent simulated-data badge |
| 2 | Role/service context | “Profesional — Clínico”; simulated profile, service/specialty context, period |
| 3 | Filters | Period and simulated profile required; service, specialty, and prestation optional |
| 4 | KPI card row | clinical_activity_completed; clinical_schedule_completion_pct; new_consultation_share_pct; discharge_rate_pct; professional_documentation_completeness_pct; professional_no_show_context_pct |
| 5 | Prioritized findings | Up to five non-punitive scheduling or documentation findings and contextual observations |
| 6 | Main chart | Clinical activity and schedule completion trend |
| 7 | Secondary chart | New consultation and discharge mix |
| 8 | Georeferenced map | Professional clinical map contract: aggregate origins and prestations |
| 9 | Accessible map table | Origin, prestation, activity, no-show context, suppression status |
| 10 | Interpretation note | “Perfil simulado. No usar para ranking, sanción ni inferencia causal individual.” |
| 11 | Data provenance | Simulated-profile source, public DEIS reference, period and validation status |
| 12 | Empty/unavailable/error | Keep non-punitive context and explain unavailable data |

## 7. Profesional Quirúrgico

| Order | Region | Contract |
|---:|---|---|
| 1 | Header | “Retroalimentación quirúrgica del perfil simulado”; persistent simulated-data badge |
| 2 | Role/service context | “Profesional — Quirúrgico”; simulated profile, service/specialty context, period |
| 3 | Filters | Period and simulated profile required; service, specialty, and procedure optional |
| 4 | KPI card row | surgical_activity_completed; surgical_schedule_completion_pct; professional_ambulatory_surgery_pct; professional_documentation_completeness_pct; professional_suspension_context_pct |
| 5 | Prioritized findings | Up to five non-punitive scheduling or documentation findings and contextual observations |
| 6 | Main chart | Surgical activity and schedule completion trend |
| 7 | Secondary chart | Ambulatory and suspension context by procedure |
| 8 | Georeferenced map | Professional surgical map contract: aggregate origins and procedures |
| 9 | Accessible map table | Origin, procedure, activity, suspension context, suppression status |
| 10 | Interpretation note | “Perfil simulado. No atribuir responsabilidad individual ni comparar profesionales.” |
| 11 | Data provenance | Simulated-profile source, public DEIS reference, period and validation status |
| 12 | Empty/unavailable/error | Keep non-punitive context and explain unavailable data |

## 8. Profesional Mixto

| Order | Region | Contract |
|---:|---|---|
| 1 | Header | “Retroalimentación mixta del perfil simulado”; persistent simulated-data badge |
| 2 | Role/service context | “Profesional — Mixto”; period and simulated profile |
| 3 | Filters | Shared period/profile selector; lens-specific compatible filters |
| 4 | KPI card row | No combined KPI row. Clinical lens uses the six professional_clinical IDs; surgical lens separately uses the five professional_surgical IDs. |
| 5 | Prioritized findings | Separate lists per lens, each capped at five; no combined severity or performance result |
| 6 | Main chart | Clinical lens trend, using the professional_clinical chart contract |
| 7 | Secondary chart | Surgical lens trend, using the professional_surgical chart contract |
| 8 | Georeferenced map | Separate clinical and surgical maps; never merge incompatible measures |
| 9 | Accessible map table | Separate synchronized tables with independent suppression and denominators |
| 10 | Interpretation note | “Los lentes clínico y quirúrgico no forman un puntaje combinado.” |
| 11 | Data provenance | Shared dataset provenance plus independent lens scope and quality status |
| 12 | Empty/unavailable/error | Report each lens independently; an unavailable lens does not hide or alter the other |

## 9. Upload and validation

| Order | Region | Contract |
|---:|---|---|
| 1 | Header | “Carga y validación de datos”; public-prototype and simulated-data warning |
| 2 | Template | “Descargar plantilla Excel” with schema/version note |
| 3 | Upload | “Seleccionar archivo .xlsx”; state that confidential or identifiable data are prohibited |
| 4 | Candidate state | Show filename, candidate status, and that it is not active |
| 5 | Validation summary | Accepted/rejected rows, missing critical fields, invalid codes/dates, duplicates, unmatched DEIS codes |
| 6 | Rejection/quarantine | Invalid candidate stays outside active data; show actionable grouped reasons |
| 7 | Activation | Enable “Activar conjunto validado” only for a valid candidate; require explicit action |
| 8 | Active status | Show active source, validation timestamp, record count, and period |
| 9 | Persistence note | “Los datos cargados no se conservan al terminar la sesión.” |
| 10 | Error behavior | A failed upload preserves the prior active validated dataset and visibly confirms that preservation |

## 10. Data-quality view

| Order | Region | Contract |
|---:|---|---|
| 1 | Header | “Calidad y estado del conjunto de datos” |
| 2 | Dataset context | Active/candidate status, source mode, validation timestamp, period, row count |
| 3 | Primary quality indicators | accepted_record_pct; critical_field_completeness_pct |
| 4 | Validation summary | Rejected row count and reason categories |
| 5 | Critical-field detail | Missing critical fields without row payloads or identifiers |
| 6 | Code/date detail | Invalid codes, invalid dates, duplicates, unmatched DEIS origin codes |
| 7 | Interpretation | Explain how each issue limits indicators, findings, filters, or maps |
| 8 | Accessible status | Text labels and table summaries; no color-only pass/fail |
| 9 | Empty state | “Aún no hay un archivo candidato. El conjunto simulado permanece activo.” |
| 10 | Error state | Preserve prior report where useful, identify the current validation failure, and never expose uploaded row content |

## Cross-view acceptance checks

| Check | Expected result |
|---|---|
| Cards | No view exceeds six; mixed view has no combined row |
| Findings | No list exceeds five |
| Map disclosure | Cells below 10 are suppressed in map and table |
| Accessibility | Charts/maps have text summaries; maps have tables; status is not color-only |
| Context | Role, scope, period, provenance, simulation, snapshot, record count, and validation remain visible |
| Targets | Current, prior comparable, and applicable reference are distinguished |
| Errors | Failed upload preserves the active dataset; unavailable values never become zero |
