# HEC hierarchical service catalog

- Version: 1.1.0
- Status: Approved functional baseline
- Review date: 2026-08-31
- Scope: ENSIA617 academic dashboard prototype

## Selector behavior

1. Select Clínico or Quirúrgico.
2. Select an enabled organizational service or unit.
3. Select an analytical specialty only when applicable.

Departments organize the catalog but are not presented as performance units.

## MVP-enabled organizational units

| Type | Department | Service or unit | Level | Indicator profile |
|---|---|---|---|---|
| clinical | Departamento Pediátrico | Especialidades Pediátricas | service | clinical_outpatient |
| clinical | Departamento Pediátrico | Pediatría | service | clinical_outpatient |
| clinical | Departamento de Apoyo Clínico | Medicina Física y Rehabilitación | service | clinical_outpatient |
| clinical | Departamento de Apoyo Clínico | Nefrología y Diálisis | service | clinical_outpatient |
| clinical | Departamento de Atención Ambulatoria | Especialidades Médicas Adulto | service | clinical_outpatient |
| clinical | Departamento de Medicina del Adulto | Alivio del Dolor y Cuidados Paliativos | unit | clinical_outpatient |
| clinical | Departamento de Medicina del Adulto | Geriatría | service | clinical_outpatient |
| clinical | Departamento de Medicina del Adulto | Medicina Interna | service | clinical_outpatient |
| clinical | Departamento de Salud Mental | Hospital de Día | unit | clinical_outpatient |
| clinical | Departamento de Salud Mental | Psiquiatría Adulto | unit | clinical_outpatient |
| clinical | Departamento de Salud Mental | Psiquiatría Infantil | unit | clinical_outpatient |
| surgical | Departamento Pediátrico | Cirugía Infantil | service | surgical |
| surgical | Departamento de Ginecología y Obstetricia | Ginecología | service | surgical |
| surgical | Departamento de Ginecología y Obstetricia | Obstetricia | service | surgical |
| surgical | Departamento de Áreas Quirúrgicas | Cirugía Adulto | service | surgical |
| surgical | Departamento de Áreas Quirúrgicas | Otorrinolaringología | service | surgical |
| surgical | Departamento de Áreas Quirúrgicas | Traumatología | service | surgical |
| surgical | Departamento de Áreas Quirúrgicas | Urología | service | surgical |

## Registered but deferred units

| Type | Department | Service or unit | Deferred profile |
|---|---|---|---|
| clinical | Departamento Pediátrico | Emergencia Infantil | emergency_deferred |
| clinical | Departamento Pediátrico | Neonatología y UPC Neonatal | critical_care_deferred |
| clinical | Departamento Pediátrico | Paciente Crítico Pediátrico (UPC Pediátrica) | critical_care_deferred |
| clinical | Departamento de Medicina del Adulto | Cardiología y Paciente Crítico Cardiovascular (UPCCV) | critical_care_deferred |
| clinical | Departamento de Medicina del Adulto | Cuidado Intensivo Adulto (UCI) | critical_care_deferred |
| clinical | Departamento de Medicina del Adulto | Emergencia Adulto | emergency_deferred |
| clinical | Departamento de Medicina del Adulto | Hospitalización Domiciliaria | inpatient_deferred |
| clinical | Departamento de Medicina del Adulto | Tratamiento Intermedio Adulto (UTI) | critical_care_deferred |
| surgical | Departamento de Ginecología y Obstetricia | Emergencia Gineco-obstétrica | emergency_deferred |
| surgical | Departamento de Pabellón | Anestesia | operating_room_support |
| surgical | Departamento de Pabellón | Pabellón | operating_room_support |
| surgical | Departamento de Áreas Quirúrgicas | Hospitalización Quirúrgica | surgical_inpatient_deferred |

## Analytical specialties

| Type | Parent service or unit | Specialty | Evidence |
|---|---|---|---|
| clinical | Especialidades Médicas Adulto | Broncopulmonar Adulto | Cuenta Pública Participativa 2026 |
| clinical | Especialidades Médicas Adulto | Cardiología Adulto | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| clinical | Especialidades Médicas Adulto | Diabetología | Cuenta Pública Participativa 2026 |
| clinical | Especialidades Médicas Adulto | Endocrinología | Cuenta Pública Participativa 2026 |
| clinical | Especialidades Médicas Adulto | Gastroenterología Adulto | Cuenta Pública Participativa 2026 |
| clinical | Especialidades Médicas Adulto | Neurología Adulto | Cuenta Pública Participativa 2026, HEC team institutional context |
| clinical | Especialidades Médicas Adulto | Oncología | Cuenta Pública Participativa 2026 |
| clinical | Especialidades Pediátricas | Neurología Infantil | HEC team institutional context |
| clinical | Geriatría | Geriatría | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| clinical | Medicina Física y Rehabilitación | Medicina Física y Rehabilitación | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| clinical | Medicina Interna | Medicina Interna | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| clinical | Nefrología y Diálisis | Nefrología | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| clinical | Pediatría | Pediatría | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| clinical | Psiquiatría Adulto | Psiquiatría Adulto | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| clinical | Psiquiatría Infantil | Psiquiatría Infantil | Organigrama HEC 2023 II |
| surgical | Cirugía Adulto | Cirugía Digestiva | Cuenta Pública Participativa 2026 |
| surgical | Cirugía Adulto | Cirugía General | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| surgical | Cirugía Adulto | Cirugía Plástica | Cuenta Pública Participativa 2026 |
| surgical | Cirugía Adulto | Cirugía Vascular Periférica | Cuenta Pública Participativa 2026 |
| surgical | Cirugía Adulto | Coloproctología | Cuenta Pública Participativa 2026 |
| surgical | Cirugía Infantil | Cirugía Pediátrica | Organigrama HEC 2023 II |
| surgical | Ginecología | Ginecología | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| surgical | Obstetricia | Obstetricia | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| surgical | Otorrinolaringología | Otorrinolaringología | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| surgical | Traumatología | Traumatología | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |
| surgical | Urología | Urología | Organigrama HEC 2023 II, Cuenta Pública Participativa 2026 |

## Scope governance

- Only `clinical_outpatient` and `surgical` profiles are enabled in the MVP.
- Emergency, critical-care and inpatient units require separate indicators.
- Cardiología Adulto is analyzed as an ambulatory specialty under Especialidades Médicas Adulto.
- The combined Cardiología-UPCCV organizational unit remains deferred because it requires a distinct critical-care indicator contract.
- Inapplicable indicators must not be displayed as zero.
- The professional mixed profile keeps separate clinical and surgical lenses.
- Neurología Infantil is team-validated institutional context pending final sign-off.

## Privacy rules

- No patient addresses.
- No employee identifiers.
- No patient-level map drill-down.
- Geographic cells below 10 simulated events are suppressed.

## Sources

Hospital El Carmen Dr. Luis Valentín Ferrada. (2023). *Organigrama HEC 2023 II*.

Hospital El Carmen Dr. Luis Valentín Ferrada. (2026). *Cuenta Pública Participativa 2026*.
