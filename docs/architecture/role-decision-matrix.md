# HEC role–decision matrix

- Version: 1.0.0
- Status: Functional baseline
- Review date: 2026-08-31
- Scope: Hospital El Carmen role-based academic proof of concept
- Operational data: Clearly simulated

## Purpose

This contract limits each dashboard to the questions and indicators needed for a decision. It also defines deterministic findings, review actions and georeferencing behavior.

## Role summary

| Role view | Indicator profile | Primary cards | Decision questions | Cadence |
|---|---|---:|---:|---|
| Directivo — Director | `institutional` | 6 | 4 | `monthly_quarterly` |
| Directivo — Director Médico | `institutional` | 6 | 4 | `weekly_monthly` |
| Jefe de Servicio — Clínico | `clinical_outpatient` | 6 | 5 | `weekly_monthly` |
| Jefe de Servicio — Quirúrgico | `surgical` | 6 | 5 | `weekly_monthly` |
| Profesional — Clínico | `professional_clinical` | 6 | 4 | `bounded_simulated_snapshot` |
| Profesional — Quirúrgico | `professional_surgical` | 5 | 4 | `bounded_simulated_snapshot` |
| Profesional — Mixto | `professional_mixed` | 0 | 0 | `bounded_simulated_snapshot` |

## Primary cards

| Role view | Primary indicators |
|---|---|
| Directivo — Director | Derivaciones recibidas<br>Percentil 75 de espera<br>Cumplimiento GES<br>Inasistencia de consultas nuevas<br>Suspensión de cirugía electiva<br>Registros aceptados |
| Directivo — Director Médico | Variación de derivaciones<br>Percentil 75 de espera<br>Tasa de altas<br>Pertinencia de derivación<br>Cumplimiento GES<br>Resolución de lista quirúrgica |
| Jefe de Servicio — Clínico | Derivaciones recibidas<br>Percentil 75 de espera<br>Inasistencia de consultas nuevas<br>Inasistencia de controles<br>Tasa de altas<br>Pertinencia de derivación |
| Jefe de Servicio — Quirúrgico | Lista de espera quirúrgica activa<br>Percentil 75 de espera quirúrgica<br>Cirugías mayores electivas<br>Cirugía mayor ambulatoria<br>Suspensión de cirugía electiva<br>Resolución de lista quirúrgica |
| Profesional — Clínico | Actividad clínica completada<br>Cumplimiento de actividad clínica programada<br>Proporción de consultas nuevas<br>Tasa de altas<br>Completitud de documentación<br>Contexto de inasistencia |
| Profesional — Quirúrgico | Actividad quirúrgica completada<br>Cumplimiento de actividad quirúrgica programada<br>Cirugía ambulatoria del perfil<br>Completitud de documentación<br>Contexto de suspensiones |
| Profesional — Mixto | No combined cards; render separate clinical and surgical lenses. |

## Decision questions and review actions

| Role | Decision question | Indicators | Finding rules | Review action |
|---|---|---|---|---|
| Directivo — Director | ¿Dónde se concentran las mayores desviaciones de acceso? | Percentil 75 de espera<br>Inasistencia de consultas nuevas<br>Inasistencia de controles | `wait_worsening`<br>`new_no_show_above_reference`<br>`followup_no_show_above_reference` | Priorizar revisión institucional y servicios afectados. |
| Directivo — Director | ¿Existen señales de riesgo en garantías y cirugía? | Cumplimiento GES<br>Suspensión de cirugía electiva<br>Cirugía mayor ambulatoria | `ges_below_reference`<br>`surgery_suspension_above_reference`<br>`ambulatory_surgery_below_reference` | Solicitar verificación y plan de gestión al responsable correspondiente. |
| Directivo — Director | ¿Qué territorios y derivadores concentran la demanda? | Derivaciones recibidas<br>Variación de derivaciones<br>Concentración en tres derivadores | `referral_growth` | Coordinar prioridades de red y capacidad institucional. |
| Directivo — Director | ¿La evidencia permite tomar una decisión? | Registros aceptados<br>Completitud de campos críticos | `upload_acceptance_low`<br>`critical_completeness_low` | Corregir la fuente antes de interpretar hallazgos. |
| Directivo — Director Médico | ¿Qué especialidades presentan mayor presión asistencial? | Variación de derivaciones<br>Percentil 75 de espera | `referral_growth`<br>`wait_worsening` | Priorizar revisión clínico-operacional por especialidad. |
| Directivo — Director Médico | ¿Los servicios resuelven y dan altas? | Tasa de altas | `discharge_below_local_target` | Revisar mezcla de casos y criterios documentados de alta. |
| Directivo — Director Médico | ¿Dónde disminuye la pertinencia de derivación? | Pertinencia de derivación | `pertinence_drop` | Auditar motivos agregados y retroalimentar a la red. |
| Directivo — Director Médico | ¿Dónde se concentran señales GES o de lista quirúrgica? | Cumplimiento GES<br>Resolución de lista quirúrgica | `ges_below_reference`<br>`waitlist_resolution_below_local_target` | Activar revisión con el servicio responsable. |
| Jefe de Servicio — Clínico | ¿Cómo cambia la demanda del servicio? | Derivaciones recibidas<br>Variación de derivaciones | `referral_growth` | Revisar origen, prestación y capacidad del servicio. |
| Jefe de Servicio — Clínico | ¿Cómo evolucionan la espera y la inasistencia? | Percentil 75 de espera<br>Inasistencia de consultas nuevas<br>Inasistencia de controles | `wait_worsening`<br>`new_no_show_above_reference`<br>`followup_no_show_above_reference` | Revisar agenda, priorización, confirmación y accesibilidad. |
| Jefe de Servicio — Clínico | ¿El servicio resuelve y documenta continuidad? | Tasa de altas<br>Contrarreferencia documentada | `discharge_below_local_target` | Revisar altas elegibles y contrarreferencia. |
| Jefe de Servicio — Clínico | ¿Las derivaciones son pertinentes y de dónde provienen? | Pertinencia de derivación<br>Concentración en tres derivadores | `pertinence_drop` | Coordinar retroalimentación con principales derivadores. |
| Jefe de Servicio — Clínico | ¿Las teleconsultas elegibles se cierran oportunamente? | Cierre oportuno de teleconsultas | `teleconsult_below_reference` | Revisar pendientes y flujo de respuesta. |
| Jefe de Servicio — Quirúrgico | ¿Cómo evolucionan el tamaño y la antigüedad de la lista? | Lista de espera quirúrgica activa<br>Percentil 75 de espera quirúrgica | `waitlist_growth`<br>`surgery_wait_worsening` | Revisar ingresos, antigüedad, prioridad y capacidad. |
| Jefe de Servicio — Quirúrgico | ¿Qué volumen y mezcla de cirugías se completan? | Cirugías mayores electivas<br>Cirugía mayor ambulatoria | `ambulatory_surgery_below_reference` | Revisar procedimientos elegibles y barreras. |
| Jefe de Servicio — Quirúrgico | ¿Qué magnitud tienen las suspensiones? | Suspensión de cirugía electiva | `surgery_suspension_above_reference` | Revisar causas, evitabilidad y proceso responsable. |
| Jefe de Servicio — Quirúrgico | ¿La resolución compensa el ingreso de nuevos casos? | Resolución de lista quirúrgica | `waitlist_resolution_below_local_target` | Revisar balance por procedimiento y origen. |
| Jefe de Servicio — Quirúrgico | ¿Existe información válida de utilización de pabellón? | Utilización de pabellón | — | Mostrar solo cuando el contrato de horas esté validado. |
| Profesional — Clínico | ¿Qué actividad clínica fue programada y completada? | Actividad clínica completada<br>Cumplimiento de actividad clínica programada | `professional_schedule_drop` | Revisar contexto de programación y soporte sin ranking. |
| Profesional — Clínico | ¿Cuál es la mezcla de consultas nuevas, controles y altas? | Proporción de consultas nuevas<br>Tasa de altas | — | Interpretar con mezcla de casos y contexto del servicio. |
| Profesional — Clínico | ¿La documentación simulada está completa? | Completitud de documentación | `professional_documentation_low` | Completar campos obligatorios. |
| Profesional — Clínico | ¿Qué inasistencia, prestaciones y orígenes contextualizan la actividad? | Contexto de inasistencia<br>Actividad clínica completada | — | Usar contexto agregado; no atribuir causalidad individual. |
| Profesional — Quirúrgico | ¿Qué actividad quirúrgica fue programada y completada? | Actividad quirúrgica completada<br>Cumplimiento de actividad quirúrgica programada | `professional_surgical_schedule_drop` | Revisar programación y causas sistémicas sin ranking. |
| Profesional — Quirúrgico | ¿Cuál es la mezcla de procedimientos y ambulatorización? | Cirugía ambulatoria del perfil | — | Interpretar según elegibilidad y complejidad. |
| Profesional — Quirúrgico | ¿La documentación simulada está completa? | Completitud de documentación | `professional_documentation_low` | Completar campos obligatorios. |
| Profesional — Quirúrgico | ¿Qué suspensiones, orígenes y procedimientos contextualizan la actividad? | Contexto de suspensiones | — | Mostrar como contexto; no atribuir responsabilidad individual. |

## Deterministic finding rules

A finding is suppressed when the indicator is inapplicable, a required target is not configured, the minimum valid sample is not met, or completeness is insufficient.

| Rule | Indicator | Condition | Authority | Status | Severity | Review action |
|---|---|---|---|---|---|---|
| `wait_worsening` | Percentil 75 de espera | `current > previous * 1.10` | `simulated_demonstration` | `active` | `high` | Revisar demanda, capacidad, priorización y calidad del dato. |
| `referral_growth` | Variación de derivaciones | `value > 15` | `simulated_demonstration` | `active` | `medium` | Revisar origen, prestación, estacionalidad y capacidad disponible. |
| `ges_below_reference` | Cumplimiento GES | `value < configured_applicable_target` | `ministerial_reference` | `conditional` | `critical` | Revisar garantías afectadas y plan de recuperación; no inferir incumplimiento oficial con datos simulados. |
| `new_no_show_above_reference` | Inasistencia de consultas nuevas | `value > configured_applicable_target` | `ministerial_reference` | `conditional` | `high` | Revisar confirmación, recordatorios, accesibilidad y programación. |
| `followup_no_show_above_reference` | Inasistencia de controles | `value > configured_applicable_target` | `ministerial_reference` | `conditional` | `high` | Revisar continuidad, recordatorios y necesidad del control. |
| `surgery_suspension_above_reference` | Suspensión de cirugía electiva | `value > configured_applicable_target` | `ministerial_reference` | `conditional` | `critical` | Revisar causas, evitabilidad y proceso responsable. |
| `ambulatory_surgery_below_reference` | Cirugía mayor ambulatoria | `value < configured_applicable_target` | `ministerial_reference` | `conditional` | `high` | Revisar procedimientos elegibles y barreras de ambulatorización. |
| `emergency_bed_below_reference` | Acceso a cama antes de 12 horas | `value < configured_applicable_target` | `ministerial_reference` | `deferred` | `critical` | Revisar flujo de camas; regla diferida hasta contar con fuente válida. |
| `upload_acceptance_low` | Registros aceptados | `value < 95` | `project_quality` | `active` | `critical` | Corregir el archivo de origen antes de interpretar indicadores. |
| `critical_completeness_low` | Completitud de campos críticos | `value < 95` | `project_quality` | `active` | `high` | Corregir campos críticos y recalcular el tablero. |
| `pertinence_drop` | Pertinencia de derivación | `current < previous - 5 percentage_points` | `simulated_demonstration` | `active` | `medium` | Auditar motivos agregados y coordinar retroalimentación con derivadores. |
| `discharge_below_local_target` | Tasa de altas | `value < configured_local_target` | `local_target_required` | `conditional` | `medium` | Revisar mezcla de casos, criterios y documentación de altas. |
| `teleconsult_below_reference` | Cierre oportuno de teleconsultas | `value < configured_applicable_target` | `ministerial_reference` | `conditional` | `high` | Revisar flujo de pendientes y tiempos de respuesta. |
| `waitlist_growth` | Lista de espera quirúrgica activa | `current > previous * 1.10` | `simulated_demonstration` | `active` | `high` | Revisar entradas, resolución, antigüedad y capacidad quirúrgica. |
| `surgery_wait_worsening` | Percentil 75 de espera quirúrgica | `current > previous * 1.10` | `simulated_demonstration` | `active` | `high` | Revisar antigüedad, prioridad, procedimiento y capacidad quirúrgica. |
| `waitlist_resolution_below_local_target` | Resolución de lista quirúrgica | `value < configured_local_target` | `local_target_required` | `conditional` | `high` | Revisar balance entre ingresos y resolución por procedimiento. |
| `professional_schedule_drop` | Cumplimiento de actividad clínica programada | `current < previous - 10 percentage_points` | `simulated_non_punitive` | `non_punitive` | `medium` | Revisar programación, ausencias, soporte y contexto; no atribuir desempeño individual automáticamente. |
| `professional_surgical_schedule_drop` | Cumplimiento de actividad quirúrgica programada | `current < previous - 10 percentage_points` | `simulated_non_punitive` | `non_punitive` | `medium` | Revisar programación y causas sistémicas; no atribuir responsabilidad automáticamente. |
| `professional_documentation_low` | Completitud de documentación | `value < 95` | `project_quality_non_punitive` | `non_punitive` | `medium` | Completar o corregir campos obligatorios del perfil simulado. |

## Georeferencing contracts

| Role | Decision use | Bubble size | Color options | Required filters | Allowed aggregate detail |
|---|---|---|---|---|---|
| Directivo — Director | Priorización institucional y coordinación de red. | Derivaciones recibidas | Variación de derivaciones<br>Percentil 75 de espera | `period`<br>`service`<br>`specialty`<br>`prestation` | `origin_establishment`<br>`service`<br>`specialty` |
| Directivo — Director Médico | Gobernanza clínica y vigilancia epidemiológica agregada. | Derivaciones recibidas | Pertinencia de derivación<br>Cumplimiento GES<br>Percentil 75 de espera | `period`<br>`service`<br>`specialty`<br>`prestation`<br>`ges_status` | `origin_establishment`<br>`specialty`<br>`prestation`<br>`diagnostic_group` |
| Jefe de Servicio — Clínico | Retroalimentación a derivadores y planificación del servicio. | Derivaciones recibidas | Percentil 75 de espera<br>Pertinencia de derivación | `period`<br>`service`<br>`specialty`<br>`prestation` | `origin_establishment`<br>`prestation` |
| Jefe de Servicio — Quirúrgico | Gestión de lista, priorización y capacidad quirúrgica. | Lista de espera quirúrgica activa | Percentil 75 de espera quirúrgica | `period`<br>`service`<br>`specialty`<br>`procedure` | `origin_establishment`<br>`procedure` |
| Profesional — Clínico | Retroalimentación contextual no punitiva. | Actividad clínica completada | Contexto de inasistencia | `period`<br>`simulated_profile`<br>`prestation` | `origin_establishment`<br>`prestation` |
| Profesional — Quirúrgico | Retroalimentación contextual no punitiva. | Actividad quirúrgica completada | Contexto de suspensiones | `period`<br>`simulated_profile`<br>`procedure` | `origin_establishment`<br>`procedure` |

## Safety and interpretation guardrails

- Maps use official DEIS establishment coordinates; patient addresses are prohibited.
- Geographic cells with fewer than 10 records are suppressed.
- No patient-level drill-down is permitted in the public prototype.
- Professional views use simulated profiles, contextual interpretation and no public ranking.
- Mixed professionals receive separate clinical and surgical lenses, never a combined score.
- Ministerial values remain references until institutional and service applicability is validated.
- A failed upload never replaces the active validated dataset.
- A missing, inapplicable or denominator-zero result is displayed as unavailable, never as zero.

## Contract totals

- Role views: 7
- Decision questions: 26
- Finding rules: 19
- Active rules: 7
- Conditional rules: 8
- Deferred rules: 1
- Non-punitive professional rules: 3
- Map contracts: 6

## Sources

Hospital El Carmen Dr. Luis Valentín Ferrada. (2026). *Cuenta Pública Participativa 2026*.

Ministerio de Salud de Chile. (2026). *Orientaciones técnicas de Compromisos de Gestión 2026*.

See also `config/indicators.json`, `config/services.json` and ADR-001.
