# HEC indicator catalog

- Version: 1.1.0
- Status: Day 5 candidate
- Review date: 2026-09-02
- Indicators: 41

## Governance rules

- Ministerial values are references until their applicability to HEC and the selected service is validated.
- Local targets remain null until an accountable institutional decision configures them.
- A percentage returns null when its validated denominator is zero.
- An inapplicable or unavailable indicator is never displayed as zero.
- Professional indicators are contextual and must not produce public rankings or punitive composite scores.

## Indicator dictionary

| ID | Display name | Unit | Profiles | Target class | Status |
|---|---|---|---|---|---|
| `referrals_total` | Derivaciones recibidas | count | institutional, clinical_outpatient, surgical | No target | MVP core |
| `referral_growth_pct` | Variación de derivaciones | percentage | institutional, clinical_outpatient, surgical | No target | MVP core |
| `wait_median_days` | Mediana de espera | days | institutional, clinical_outpatient, surgical | Local target pending | MVP core |
| `wait_p75_days` | Percentil 75 de espera | days | institutional, clinical_outpatient, surgical | Local target pending | MVP core |
| `new_no_show_pct` | Inasistencia de consultas nuevas | percentage | institutional, clinical_outpatient | Ministerial reference | MVP core |
| `followup_no_show_pct` | Inasistencia de controles | percentage | institutional, clinical_outpatient | Ministerial reference | MVP core |
| `discharge_rate_pct` | Tasa de altas | percentage | institutional, clinical_outpatient, professional_clinical | Local target pending | Conditional |
| `referral_pertinence_pct` | Pertinencia de derivación | percentage | institutional, clinical_outpatient | Local target pending | Conditional |
| `contrareference_pct` | Contrarreferencia documentada | percentage | clinical_outpatient | Local target pending | Conditional |
| `ges_compliance_pct` | Cumplimiento GES | percentage | institutional, clinical_outpatient, surgical | Ministerial reference | Conditional |
| `teleconsult_timely_closure_pct` | Cierre oportuno de teleconsultas | percentage | institutional, clinical_outpatient | Ministerial reference | Conditional |
| `accepted_record_pct` | Registros aceptados | percentage | data_quality, institutional | Project quality | MVP core |
| `critical_field_completeness_pct` | Completitud de campos críticos | percentage | data_quality, institutional, clinical_outpatient, surgical | Project quality | MVP core |
| `top3_referrer_share_pct` | Concentración en tres derivadores | percentage | institutional, clinical_outpatient, surgical | No target | MVP core |
| `surgical_waitlist_open_count` | Lista de espera quirúrgica activa | count | institutional, surgical | Local target pending | MVP core |
| `surgery_wait_p75_days` | Percentil 75 de espera quirúrgica | days | institutional, surgical | Local target pending | MVP core |
| `elective_major_surgery_count` | Cirugías mayores electivas | count | institutional, surgical | No target | MVP core |
| `ambulatory_major_surgery_pct` | Cirugía mayor ambulatoria | percentage | institutional, surgical | Ministerial reference | MVP core |
| `elective_surgery_suspension_pct` | Suspensión de cirugía electiva | percentage | institutional, surgical | Ministerial reference | MVP core |
| `surgical_waitlist_resolution_pct` | Resolución de lista quirúrgica | percentage | institutional, surgical | Local target pending | Conditional |
| `operating_room_utilization_pct` | Utilización de pabellón | percentage | surgical | Local target pending | Deferred |
| `emergency_bed_lt12h_pct` | Acceso a cama antes de 12 horas | percentage | institutional | Ministerial reference | Deferred |
| `clinical_activity_completed` | Actividad clínica completada | count | professional_clinical | No target | MVP simulated |
| `clinical_schedule_completion_pct` | Cumplimiento de actividad clínica programada | percentage | professional_clinical | No target | MVP simulated |
| `new_consultation_share_pct` | Proporción de consultas nuevas | percentage | professional_clinical | Local target pending | MVP simulated |
| `professional_documentation_completeness_pct` | Completitud de documentación | percentage | professional_clinical, professional_surgical | Project quality | MVP simulated |
| `professional_no_show_context_pct` | Contexto de inasistencia | percentage | professional_clinical | No target | MVP simulated |
| `surgical_activity_completed` | Actividad quirúrgica completada | count | professional_surgical | No target | MVP simulated |
| `surgical_schedule_completion_pct` | Cumplimiento de actividad quirúrgica programada | percentage | professional_surgical | No target | MVP simulated |
| `professional_ambulatory_surgery_pct` | Cirugía ambulatoria del perfil | percentage | professional_surgical | No target | MVP simulated |
| `professional_suspension_context_pct` | Contexto de suspensiones | percentage | professional_surgical | No target | MVP simulated |
| `new_waitlist_open_count` | Consultas nuevas pendientes | count | approved decision profiles | No target | MVP simulated |
| `new_wait_median_days` | Mediana de espera de consultas nuevas | days | approved decision profiles | No target | MVP simulated |
| `new_wait_p75_days` | P75 de espera de consultas nuevas | days | approved decision profiles | No target | MVP simulated |
| `new_wait_over_90_pct` | Consultas nuevas sobre 90 días | percentage | approved decision profiles | No target | MVP simulated |
| `new_waitlist_resolution_pct` | Resolución de consultas nuevas | percentage | approved decision profiles | No target | MVP simulated |
| `followup_overdue_open_count` | Controles vencidos pendientes | count | approved decision profiles | No target | MVP simulated |
| `followup_overdue_median_days` | Mediana de atraso de controles | days | approved decision profiles | No target | MVP simulated |
| `followup_overdue_p75_days` | P75 de atraso de controles | days | approved decision profiles | No target | MVP simulated |
| `followup_unscheduled_pct` | Controles vencidos sin programación | percentage | approved decision profiles | No target | MVP simulated |
| `followup_resolution_pct` | Resolución de controles debidos | percentage | approved decision profiles | No target | MVP simulated |

## Status summary

| Status | Count | Meaning |
|---|---:|---|
| MVP core | 14 | Available in the primary simulated operational contract. |
| Conditional | 6 | Displayed only when the required fields and applicability are valid. |
| Deferred | 2 | Requires a separate validated data contract outside the initial MVP. |
| MVP simulated | 19 | Nine professional-context indicators and ten Day 5 waitlist indicators. |

## Target interpretation

A ministerial reference is not automatically an official HEC service target. The interface must show its source, year, applicability and exclusions.

Local targets for waiting time, discharge, contrareference, pertinence, surgical-list resolution and operating-room utilization remain unconfigured.

## Sources

Hospital El Carmen Dr. Luis Valentín Ferrada. (2026). *Cuenta Pública Participativa 2026*.

Ministerio de Salud de Chile. (2026). *Orientaciones técnicas de Compromisos de Gestión 2026*.
