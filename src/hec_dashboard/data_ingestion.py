"""Standard-library ingestion, quarantine, and session activation for Day 2."""

from __future__ import annotations

import copy
import csv
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_REF = re.compile(r"^([A-Z]+)([0-9]+)$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    message: str
    sheet: str | None = None
    row: int | None = None
    field: str | None = None
    value: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sheet": self.sheet,
            "row": self.row,
            "field": self.field,
            "value": self.value,
        }


@dataclass
class ValidationReport:
    validation_timestamp_utc: str
    metadata: dict[str, Any]
    accepted_rows: dict[str, list[dict[str, Any]]]
    quarantined_rows: dict[str, list[dict[str, Any]]]
    issues: list[ValidationIssue] = field(default_factory=list)
    structural_errors: list[ValidationIssue] = field(default_factory=list)
    minimum_accepted_record_pct: float = 95.0
    minimum_rows_per_sheet: int = 1

    @property
    def submitted_rows(self) -> int:
        return sum(
            len(self.accepted_rows.get(name, []))
            + len(self.quarantined_rows.get(name, []))
            for name in self.accepted_rows
        )

    @property
    def accepted_row_count(self) -> int:
        return sum(len(rows) for rows in self.accepted_rows.values())

    @property
    def rejected_row_count(self) -> int:
        return sum(len(rows) for rows in self.quarantined_rows.values())

    @property
    def accepted_record_pct(self) -> float | None:
        if self.submitted_rows == 0:
            return None
        return round(self.accepted_row_count * 100 / self.submitted_rows, 2)

    @property
    def critical_field_completeness_pct(self) -> float | None:
        if self.accepted_row_count == 0:
            return None
        return 100.0

    @property
    def activatable(self) -> bool:
        if self.structural_errors:
            return False
        if self.accepted_record_pct is None:
            return False
        if self.accepted_record_pct < self.minimum_accepted_record_pct:
            return False
        return all(
            len(rows) >= self.minimum_rows_per_sheet
            for rows in self.accepted_rows.values()
        )

    def summary(self) -> dict[str, Any]:
        return {
            "status": "valid_candidate" if self.activatable else "rejected_candidate",
            "activatable": self.activatable,
            "submitted_rows": self.submitted_rows,
            "accepted_rows": self.accepted_row_count,
            "rejected_rows": self.rejected_row_count,
            "accepted_record_pct": self.accepted_record_pct,
            "critical_field_completeness_pct": self.critical_field_completeness_pct,
            "structural_error_count": len(self.structural_errors),
            "issue_count": len(self.issues),
            "validation_timestamp_utc": self.validation_timestamp_utc,
        }


@dataclass(frozen=True)
class CandidateDataset:
    metadata: dict[str, Any]
    tables: dict[str, list[dict[str, Any]]]
    validation_summary: dict[str, Any]


class SessionDatasetStore:
    """Keep candidate and active datasets separate until explicit activation."""

    def __init__(self, active_dataset: CandidateDataset | None = None) -> None:
        self.active_dataset = copy.deepcopy(active_dataset)
        self.candidate_dataset: CandidateDataset | None = None
        self.last_validation_report: ValidationReport | None = None

    def submit_tables(
        self, tables: dict[str, list[list[Any]]], repo_root: Path
    ) -> ValidationReport:
        report = validate_tables(tables, repo_root)
        self.last_validation_report = report
        self.candidate_dataset = (
            CandidateDataset(
                metadata=copy.deepcopy(report.metadata),
                tables=copy.deepcopy(report.accepted_rows),
                validation_summary=report.summary(),
            )
            if report.activatable
            else None
        )
        return report

    def submit_workbook(self, workbook_path: Path, repo_root: Path) -> ValidationReport:
        report = validate_workbook(workbook_path, repo_root)
        self.last_validation_report = report
        self.candidate_dataset = (
            CandidateDataset(
                metadata=copy.deepcopy(report.metadata),
                tables=copy.deepcopy(report.accepted_rows),
                validation_summary=report.summary(),
            )
            if report.activatable
            else None
        )
        return report

    def activate_candidate(self) -> CandidateDataset:
        if self.candidate_dataset is None:
            raise RuntimeError("No valid candidate is available for activation")
        self.active_dataset = copy.deepcopy(self.candidate_dataset)
        return copy.deepcopy(self.active_dataset)


def _column_index(reference: str) -> int:
    match = CELL_REF.match(reference)
    if not match:
        raise ValueError(f"Invalid XLSX cell reference: {reference!r}")
    value = 0
    for char in match.group(1):
        value = value * 26 + ord(char) - 64
    return value - 1


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(node.text or "" for node in item.findall(f".//{{{MAIN_NS}}}t"))
        for item in root.findall(f"{{{MAIN_NS}}}si")
    ]


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(
            node.text or "" for node in cell.findall(f".//{{{MAIN_NS}}}t")
        )
    value_node = cell.find(f"{{{MAIN_NS}}}v")
    if value_node is None or value_node.text is None:
        return ""
    raw = value_node.text
    if cell_type == "s":
        return shared_strings[int(raw)]
    if cell_type == "b":
        return raw == "1"
    if cell_type in {"str", "e"}:
        return raw
    try:
        number = float(raw)
    except ValueError:
        return raw
    return int(number) if number.is_integer() else number


def load_workbook_tables(workbook_path: Path) -> dict[str, list[list[Any]]]:
    """Read values from a non-encrypted XLSX without third-party dependencies."""
    if workbook_path.suffix.lower() != ".xlsx":
        raise ValueError("Only .xlsx workbooks are accepted")
    if not workbook_path.is_file():
        raise FileNotFoundError(workbook_path)

    tables: dict[str, list[list[Any]]] = {}
    with zipfile.ZipFile(workbook_path) as archive:
        shared_strings = _read_shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
        targets = {
            item.attrib["Id"]: item.attrib["Target"].lstrip("/")
            for item in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
        }
        for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
            name = sheet.attrib["name"]
            relation_id = sheet.attrib[f"{{{DOC_REL_NS}}}id"]
            target = targets[relation_id]
            path = target if target.startswith("xl/") else f"xl/{target}"
            root = ET.fromstring(archive.read(path))
            rows: list[list[Any]] = []
            for row in root.findall(f".//{{{MAIN_NS}}}row"):
                values: list[Any] = []
                for cell in row.findall(f"{{{MAIN_NS}}}c"):
                    index = _column_index(cell.attrib["r"])
                    while len(values) <= index:
                        values.append("")
                    values[index] = _cell_value(cell, shared_strings)
                while values and values[-1] == "":
                    values.pop()
                rows.append(values)
            tables[name] = rows
    return tables


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"{path}: top-level JSON must be an object")
    return value


def _parse_metadata(
    rows: list[list[Any]],
    rules: list[dict[str, Any]],
    structural_errors: list[ValidationIssue],
) -> dict[str, Any]:
    if not rows or [str(value).strip().lower() for value in rows[0][:2]] != [
        "clave",
        "valor",
    ]:
        structural_errors.append(
            ValidationIssue(
                "STRUCT_METADATA_HEADER",
                "error",
                "METADATOS must start with headers 'clave' and 'valor'",
                "METADATOS",
                1,
            )
        )
        return {}
    metadata: dict[str, Any] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        key = str(row[0]).strip() if row else ""
        value = row[1] if len(row) > 1 else ""
        if not key and (value == "" or value is None):
            continue
        if key in metadata:
            structural_errors.append(
                ValidationIssue(
                    "STRUCT_METADATA_DUPLICATE",
                    "error",
                    f"Duplicate metadata key '{key}'",
                    "METADATOS",
                    row_number,
                    "clave",
                    key,
                )
            )
        metadata[key] = value
    rule_map = {item["key"]: item for item in rules}
    unknown = sorted(set(metadata) - set(rule_map))
    for key in unknown:
        structural_errors.append(
            ValidationIssue(
                "STRUCT_METADATA_UNKNOWN",
                "error",
                f"Unknown metadata key '{key}'",
                "METADATOS",
                field="clave",
                value=key,
            )
        )
    for key, rule in rule_map.items():
        value = metadata.get(key)
        if rule.get("required") and (value is None or str(value).strip() == ""):
            structural_errors.append(
                ValidationIssue(
                    "STRUCT_METADATA_MISSING",
                    "error",
                    f"Required metadata key '{key}' is missing",
                    "METADATOS",
                    field=key,
                )
            )
            continue
        if value is None:
            continue
        if "expected_value" in rule and str(value).strip() != rule["expected_value"]:
            structural_errors.append(
                ValidationIssue(
                    "STRUCT_METADATA_VALUE",
                    "error",
                    f"Metadata '{key}' must equal {rule['expected_value']!r}",
                    "METADATOS",
                    field=key,
                    value=value,
                )
            )
        if "allowed_values" in rule and str(value).strip() not in rule["allowed_values"]:
            structural_errors.append(
                ValidationIssue(
                    "STRUCT_METADATA_VALUE",
                    "error",
                    f"Metadata '{key}' has an unsupported value",
                    "METADATOS",
                    field=key,
                    value=value,
                )
            )
        try:
            if rule.get("type") == "date":
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    metadata[key] = (
                        datetime(1899, 12, 30) + timedelta(days=float(value))
                    ).date()
                else:
                    metadata[key] = date.fromisoformat(str(value).strip())
            elif rule.get("type") == "datetime":
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    metadata[key] = datetime(
                        1899, 12, 30, tzinfo=timezone.utc
                    ) + timedelta(days=float(value))
                else:
                    metadata[key] = datetime.fromisoformat(
                        str(value).strip().replace("Z", "+00:00")
                    )
            elif rule.get("type") == "identifier" and not IDENTIFIER.fullmatch(
                str(value).strip()
            ):
                raise ValueError("invalid identifier")
            else:
                metadata[key] = str(value).strip()
        except ValueError:
            structural_errors.append(
                ValidationIssue(
                    "STRUCT_METADATA_TYPE",
                    "error",
                    f"Metadata '{key}' has an invalid {rule.get('type', 'value')}",
                    "METADATOS",
                    field=key,
                    value=value,
                )
            )
    if isinstance(metadata.get("period_start"), date) and isinstance(
        metadata.get("period_end"), date
    ):
        if metadata["period_start"] > metadata["period_end"]:
            structural_errors.append(
                ValidationIssue(
                    "STRUCT_METADATA_PERIOD",
                    "error",
                    "period_start cannot be after period_end",
                    "METADATOS",
                )
            )
    return metadata


def _normalize_value(value: Any, rule: dict[str, Any]) -> Any:
    value_type = rule["type"]
    if value is None or (isinstance(value, str) and not value.strip()):
        if rule.get("required"):
            raise ValueError("required value is blank")
        return None
    if isinstance(value, str):
        value = value.strip()

    if value_type in {"identifier", "service_id", "specialty_id", "deis_code"}:
        text = str(value)
        if value_type == "deis_code" and not re.fullmatch(r"[0-9]{6}", text):
            raise ValueError("must be a six-digit DEIS code")
        if value_type != "deis_code" and not IDENTIFIER.fullmatch(text):
            raise ValueError("contains unsupported identifier characters")
        return text
    if value_type == "date":
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))
    if value_type == "boolean":
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().casefold()
        values = {"si": True, "sí": True, "true": True, "1": True,
                  "no": False, "false": False, "0": False}
        if normalized not in values:
            raise ValueError("must be SI or NO")
        return values[normalized]
    if value_type == "integer":
        if isinstance(value, bool):
            raise ValueError("must be an integer")
        number = float(value)
        if not number.is_integer():
            raise ValueError("must be an integer")
        result: int | float = int(number)
    elif value_type == "number":
        if isinstance(value, bool):
            raise ValueError("must be numeric")
        result = float(value)
    elif value_type == "enum":
        result = str(value)
        if result not in rule["allowed_values"]:
            raise ValueError(
                "must be one of: " + ", ".join(rule["allowed_values"])
            )
    else:
        result = str(value)
    if isinstance(result, (int, float)) and "minimum" in rule:
        if result < rule["minimum"]:
            raise ValueError(f"must be >= {rule['minimum']}")
    return result


def _sheet_dict_rows(
    sheet_name: str,
    rows: list[list[Any]],
    rules: dict[str, Any],
    structural_errors: list[ValidationIssue],
    *,
    allowed_missing_columns: set[str] | None = None,
) -> list[tuple[int, dict[str, Any]]]:
    expected = [column["name"] for column in rules["columns"]]
    allowed_missing_columns = allowed_missing_columns or set()
    legacy_expected = [
        name for name in expected if name not in allowed_missing_columns
    ]
    if not rows:
        structural_errors.append(
            ValidationIssue(
                "STRUCT_EMPTY_SHEET",
                "error",
                f"Required sheet '{sheet_name}' is empty",
                sheet_name,
            )
        )
        return []
    headers = [str(value).strip() for value in rows[0]]
    if headers not in (expected, legacy_expected):
        missing = [name for name in expected if name not in headers]
        unknown = [name for name in headers if name not in expected]
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unknown:
            details.append("unknown: " + ", ".join(unknown))
        if not missing and not unknown:
            details.append("columns are out of order")
        structural_errors.append(
            ValidationIssue(
                "STRUCT_COLUMNS",
                "error",
                f"{sheet_name} columns do not match contract ({'; '.join(details)})",
                sheet_name,
                1,
            )
        )
        return []
    result: list[tuple[int, dict[str, Any]]] = []
    for row_number, values in enumerate(rows[1:], start=2):
        padded = values + [""] * (len(headers) - len(values))
        if all(value == "" or value is None for value in padded[: len(headers)]):
            continue
        result.append((row_number, dict(zip(headers, padded[: len(headers)]))))
    return result


def validate_tables(
    tables: dict[str, list[list[Any]]],
    repo_root: Path,
    *,
    validation_timestamp_utc: str | None = None,
) -> ValidationReport:
    contract = _load_json(repo_root / "config" / "data_contract.json")
    services = _load_json(repo_root / "config" / "services.json")
    professional_profiles = _load_json(
        repo_root / "config" / "professional_profiles.json"
    )
    referral_diagnoses = _load_json(
        repo_root / "config" / "referral_diagnoses.json"
    )
    structural_errors: list[ValidationIssue] = []
    issues: list[ValidationIssue] = []
    metadata = _parse_metadata(
        tables.get("METADATOS", []),
        contract["metadata_keys"],
        structural_errors,
    )
    contract_version = str(metadata.get("contract_version", ""))
    required_by_version = contract["workbook"].get(
        "required_sheets_by_contract_version", {}
    )
    required_sheets = set(
        required_by_version.get(
            contract_version, contract["workbook"]["required_sheets"]
        )
    )
    allowed_sheets = set(contract["workbook"]["required_sheets"]) | set(
        contract["workbook"]["informational_sheets"]
    )
    for sheet in sorted(set(tables) - allowed_sheets):
        issues.append(
            ValidationIssue(
                "STRUCT_UNKNOWN_SHEET",
                "warning",
                f"Unknown sheet '{sheet}' was ignored",
                sheet,
            )
        )
    missing_sheets = sorted(required_sheets - set(tables))
    for sheet in missing_sheets:
        structural_errors.append(
            ValidationIssue(
                "STRUCT_MISSING_SHEET",
                "error",
                f"Required sheet '{sheet}' is missing",
                sheet,
            )
        )

    unit_by_id = {
        item["unit_id"]: item
        for item in services["organizational_units"]
        if item.get("mvp_enabled")
    }
    specialty_by_id = {
        item["specialty_id"]: item
        for item in services["analytical_specialties"]
        if item.get("mvp_enabled")
    }
    professional_profile_by_id = {
        item["professional_id"]: item
        for item in professional_profiles["profiles"]
        if item.get("mvp_enabled") and item.get("simulated") is True
    }
    referral_diagnosis_by_id = {
        item["diagnosis_group_id"]: item
        for item in referral_diagnoses["diagnoses"]
        if item.get("status") == "active_mvp"
        and item.get("classification") == "simulated_demo"
    }
    mixed_outpatient_scopes = {
        (profile.get("service_id"), profile.get("specialty_id"))
        for profile in professional_profile_by_id.values()
        if profile.get("profile_type") == "mixed"
        and profile.get("lens_contexts", {})
        .get("clinical", {})
        .get("activity_class")
        == "outpatient_clinical"
    }
    for profile in professional_profile_by_id.values():
        if profile.get("profile_type") != "mixed":
            continue
        lens_contexts = profile.get("lens_contexts")
        valid_mixed_scope = isinstance(lens_contexts, dict)
        if valid_mixed_scope:
            valid_mixed_scope = all(
                isinstance(lens_contexts.get(lens), dict)
                and all(
                    lens_contexts[lens].get(field) == profile.get(field)
                    for field in (
                        "service_id",
                        "specialty_id",
                        "specialty_display_name",
                    )
                )
                and lens_contexts[lens].get("activity_class") == activity_class
                for lens, activity_class in (
                    ("clinical", "outpatient_clinical"),
                    ("surgical", "surgical_procedural"),
                )
            )
        if not valid_mixed_scope:
            structural_errors.append(
                ValidationIssue(
                    "STRUCT_MIXED_PROFILE_SCOPE_MISMATCH",
                    "error",
                    "Mixed profile lenses must preserve one professional specialty and service",
                    "ACTIVIDAD_PROF",
                )
            )
    reference_path = repo_root / contract["reference_data"]["deis_snapshot_file"]
    with reference_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reference_codes = {
            row["establishment_code"] for row in csv.DictReader(handle)
        }

    applicable_sheets = [
        sheet for sheet in contract["sheets"] if sheet in required_sheets
    ]
    accepted: dict[str, list[dict[str, Any]]] = {
        sheet: [] for sheet in applicable_sheets
    }
    quarantined: dict[str, list[dict[str, Any]]] = {
        sheet: [] for sheet in applicable_sheets
    }
    seen_keys: dict[str, set[str]] = {sheet: set() for sheet in applicable_sheets}

    for sheet_name in applicable_sheets:
        sheet_rules = copy.deepcopy(contract["sheets"][sheet_name])
        legacy_diagnosis_missing = (
            sheet_name == "LISTA_ESPERA_AMB"
            and contract_version in {"1.1.0", "1.2.0"}
        )
        if legacy_diagnosis_missing:
            for column in sheet_rules["columns"]:
                if column["name"] == "referral_diagnosis_id":
                    column["required"] = False
                    column["critical"] = False
        source_rows = _sheet_dict_rows(
            sheet_name,
            tables.get(sheet_name, []),
            sheet_rules,
            structural_errors,
            allowed_missing_columns=(
                {"referral_diagnosis_id"} if legacy_diagnosis_missing else set()
            ),
        )
        columns = {column["name"]: column for column in sheet_rules["columns"]}
        for row_number, raw_row in source_rows:
            row_issues: list[ValidationIssue] = []
            normalized: dict[str, Any] = {}
            for field_name, rule in columns.items():
                try:
                    normalized[field_name] = _normalize_value(
                        raw_row.get(field_name), rule
                    )
                except (TypeError, ValueError) as exc:
                    row_issues.append(
                        ValidationIssue(
                            "ROW_INVALID_VALUE",
                            "error",
                            f"{field_name}: {exc}",
                            sheet_name,
                            row_number,
                            field_name,
                            raw_row.get(field_name),
                        )
                    )

            if not row_issues:
                primary_key = sheet_rules["primary_key"]
                key = normalized[primary_key]
                if key in seen_keys[sheet_name]:
                    row_issues.append(
                        ValidationIssue(
                            "ROW_DUPLICATE_ID",
                            "error",
                            f"Duplicate {primary_key} '{key}'",
                            sheet_name,
                            row_number,
                            primary_key,
                            key,
                        )
                    )
                else:
                    seen_keys[sheet_name].add(key)

            if not row_issues:
                service_id = normalized["service_id"]
                unit = unit_by_id.get(service_id)
                if unit is None:
                    row_issues.append(
                        ValidationIssue(
                            "ROW_INVALID_SERVICE",
                            "error",
                            f"Unknown or deferred service_id '{service_id}'",
                            sheet_name,
                            row_number,
                            "service_id",
                            service_id,
                        )
                    )
                else:
                    expected_type = sheet_rules.get("service_dashboard_type")
                    if sheet_name == "ACTIVIDAD_PROF":
                        expected_type = normalized["lens"]
                    professional_profile = professional_profile_by_id.get(
                        normalized.get("simulated_profile_key")
                    )
                    mixed_shared_service = (
                        sheet_name == "ACTIVIDAD_PROF"
                        and professional_profile is not None
                        and professional_profile.get("profile_type") == "mixed"
                        and normalized["service_id"]
                        == professional_profile.get("service_id")
                        and normalized["lens"]
                        in professional_profile.get("supported_lenses", [])
                    )
                    mixed_outpatient_referral = (
                        sheet_name == "DERIVACIONES"
                        and (
                            normalized["service_id"],
                            normalized.get("specialty_id"),
                        )
                        in mixed_outpatient_scopes
                    )
                    if (
                        expected_type is not None
                        and unit["dashboard_type"] != expected_type
                        and not mixed_shared_service
                        and not mixed_outpatient_referral
                    ):
                        row_issues.append(
                            ValidationIssue(
                                "ROW_SERVICE_LENS_MISMATCH",
                                "error",
                                f"Service '{service_id}' is not {expected_type}",
                                sheet_name,
                                row_number,
                                "service_id",
                                service_id,
                            )
                        )
                specialty_id = normalized.get("specialty_id")
                if specialty_id:
                    specialty = specialty_by_id.get(specialty_id)
                    if specialty is None:
                        row_issues.append(
                            ValidationIssue(
                                "ROW_INVALID_SPECIALTY",
                                "error",
                                f"Unknown specialty_id '{specialty_id}'",
                                sheet_name,
                                row_number,
                                "specialty_id",
                                specialty_id,
                            )
                        )
                    elif specialty["parent_unit_id"] != service_id:
                        row_issues.append(
                            ValidationIssue(
                                "ROW_SPECIALTY_PARENT_MISMATCH",
                                "error",
                                f"Specialty '{specialty_id}' does not belong to '{service_id}'",
                                sheet_name,
                                row_number,
                                "specialty_id",
                                specialty_id,
                            )
                        )
                origin_field = (
                    "origin_deis_code"
                    if sheet_name == "LISTA_ESPERA_AMB"
                    else "origin_establishment_code"
                )
                origin = normalized[origin_field]
                if origin not in reference_codes:
                    row_issues.append(
                        ValidationIssue(
                            "ROW_UNMATCHED_DEIS_CODE",
                            "error",
                            f"DEIS origin code '{origin}' is not in the packaged snapshot",
                            sheet_name,
                            row_number,
                            origin_field,
                            origin,
                        )
                    )
                period_field = (
                    "snapshot_date"
                    if sheet_name == "LISTA_ESPERA_AMB"
                    else "period_date"
                )
                period = normalized[period_field]
                if isinstance(metadata.get("period_start"), date) and (
                    period < metadata["period_start"]
                    or period > metadata.get("period_end", period)
                ):
                    row_issues.append(
                        ValidationIssue(
                            "ROW_DATE_OUTSIDE_PERIOD",
                            "error",
                            f"{period_field} is outside the metadata period",
                            sheet_name,
                            row_number,
                            period_field,
                            period.isoformat(),
                        )
                    )

            if not row_issues:
                if sheet_name == "DERIVACIONES":
                    if normalized["no_show_flag"] and not normalized["scheduled_flag"]:
                        row_issues.append(
                            ValidationIssue(
                                "ROW_FLAG_CONTRADICTION",
                                "error",
                                "no_show_flag requires scheduled_flag",
                                sheet_name,
                                row_number,
                                "no_show_flag",
                            )
                        )
                    if normalized["ges_met_flag"] and not normalized["ges_due_flag"]:
                        row_issues.append(
                            ValidationIssue(
                                "ROW_FLAG_CONTRADICTION",
                                "error",
                                "ges_met_flag requires ges_due_flag",
                                sheet_name,
                                row_number,
                                "ges_met_flag",
                            )
                        )
                elif sheet_name == "CIRUGIAS":
                    if normalized["ambulatory_flag"] and not normalized["elective_major_flag"]:
                        row_issues.append(
                            ValidationIssue(
                                "ROW_FLAG_CONTRADICTION",
                                "error",
                                "ambulatory_flag requires elective_major_flag",
                                sheet_name,
                                row_number,
                                "ambulatory_flag",
                            )
                        )
                    if normalized["or_hours_used"] > normalized["or_hours_available"]:
                        row_issues.append(
                            ValidationIssue(
                                "ROW_HOURS_CONTRADICTION",
                                "error",
                                "or_hours_used cannot exceed or_hours_available",
                                sheet_name,
                                row_number,
                                "or_hours_used",
                            )
                        )
                elif sheet_name == "ACTIVIDAD_PROF":
                    profile_type = normalized["profile_type"]
                    lens = normalized["lens"]
                    professional_id = normalized["simulated_profile_key"]
                    professional_profile = professional_profile_by_id.get(
                        professional_id
                    )
                    if professional_profile is None:
                        row_issues.append(
                            ValidationIssue(
                                "ROW_UNKNOWN_PROFESSIONAL_PROFILE",
                                "error",
                                f"Unknown simulated profile '{professional_id}'",
                                sheet_name,
                                row_number,
                                "simulated_profile_key",
                                professional_id,
                            )
                        )
                    else:
                        if (
                            professional_profile["profile_type"] != profile_type
                            or lens
                            not in professional_profile["supported_lenses"]
                        ):
                            row_issues.append(
                                ValidationIssue(
                                    "ROW_PROFILE_CONTRACT_MISMATCH",
                                    "error",
                                    "Profile type or lens is incompatible with the approved profile",
                                    sheet_name,
                                    row_number,
                                    "simulated_profile_key",
                                    professional_id,
                                )
                            )
                        if profile_type == "mixed":
                            expected_scope = professional_profile[
                                "lens_contexts"
                            ][lens]
                        else:
                            expected_scope = professional_profile
                        if (
                            normalized["service_id"]
                            != expected_scope["service_id"]
                            or normalized.get("specialty_id")
                            != expected_scope["specialty_id"]
                        ):
                            row_issues.append(
                                ValidationIssue(
                                    "ROW_PROFILE_SCOPE_MISMATCH",
                                    "error",
                                    "Professional row belongs to another approved specialty",
                                    sheet_name,
                                    row_number,
                                    "specialty_id",
                                    normalized.get("specialty_id"),
                                )
                            )
                    if profile_type != "mixed" and profile_type != lens:
                        row_issues.append(
                            ValidationIssue(
                                "ROW_PROFILE_LENS_MISMATCH",
                                "error",
                                "Non-mixed profile_type must equal lens",
                                sheet_name,
                                row_number,
                                "lens",
                                lens,
                            )
                        )
                    if profile_type == "mixed":
                        activity_code = normalized["activity_code"]
                        valid_activity_class = (
                            lens == "clinical"
                            and activity_code
                            in {"CONS-NUEVA", "CONS-CONTROL", "TELECONS"}
                        ) or (
                            lens == "surgical"
                            and activity_code
                            in {"PROC-CMA", "PROC-CIR", "PROC-TRA"}
                        )
                        if not valid_activity_class:
                            row_issues.append(
                                ValidationIssue(
                                    "ROW_MIXED_ACTIVITY_CLASS_MISMATCH",
                                    "error",
                                    "Mixed professional activity_code is incompatible with its lens",
                                    sheet_name,
                                    row_number,
                                    "activity_code",
                                    activity_code,
                                )
                            )
                    if normalized["ambulatory_major_flag"] and not normalized[
                        "elective_major_applicable_flag"
                    ]:
                        row_issues.append(
                            ValidationIssue(
                                "ROW_FLAG_CONTRADICTION",
                                "error",
                                "ambulatory_major_flag requires elective_major_applicable_flag",
                                sheet_name,
                                row_number,
                                "ambulatory_major_flag",
                            )
                        )
                    if lens == "clinical" and (
                        normalized["suspended_flag"]
                        or normalized["elective_major_applicable_flag"]
                        or normalized["ambulatory_major_flag"]
                    ):
                        row_issues.append(
                            ValidationIssue(
                                "ROW_CLINICAL_FLAG_CONTRADICTION",
                                "error",
                                "Clinical rows cannot be suspended, elective-major applicable, or ambulatory-major",
                                sheet_name,
                                row_number,
                            )
                        )
                    if lens == "surgical" and (
                        normalized["no_show_flag"]
                        or normalized["new_consultation_flag"]
                        or normalized["discharge_flag"]
                    ):
                        row_issues.append(
                            ValidationIssue(
                                "ROW_SURGICAL_FLAG_CONTRADICTION",
                                "error",
                                "Surgical rows cannot use clinical context flags",
                                sheet_name,
                                row_number,
                            )
                        )
                elif sheet_name == "LISTA_ESPERA_AMB":
                    queue_type = normalized["queue_type"]
                    status = normalized["episode_status"]
                    snapshot = normalized["snapshot_date"]
                    queue_entry = normalized["queue_entry_date"]
                    due = normalized["control_due_date"]
                    scheduled = normalized["scheduled_date"]
                    completion = normalized["completion_date"]
                    exit_reason = normalized["exit_reason"]
                    profile_id = normalized["professional_profile_id"]
                    referral_diagnosis_id = normalized.get("referral_diagnosis_id")
                    expected_period_id = (
                        f"{snapshot.year}-Q{((snapshot.month - 1) // 3) + 1}"
                    )
                    contradictions: list[tuple[str, str]] = []
                    if normalized["period_id"] != expected_period_id:
                        contradictions.append(
                            ("period_id", "period_id must match snapshot_date")
                        )
                    if queue_type == "new_consultation":
                        if queue_entry is None or due is not None:
                            contradictions.append(
                                (
                                    "queue_entry_date",
                                    "New-consultation episodes require queue_entry_date and cannot use control_due_date",
                                )
                            )
                        if normalized["requested_prestation"] != "consulta_nueva":
                            contradictions.append(
                                (
                                    "requested_prestation",
                                    "New-consultation episodes must request consulta_nueva",
                                )
                            )
                    else:
                        if due is None or queue_entry is not None:
                            contradictions.append(
                                (
                                    "control_due_date",
                                    "Follow-up episodes require control_due_date and cannot use queue_entry_date",
                                )
                            )
                        if normalized["requested_prestation"] == "consulta_nueva":
                            contradictions.append(
                                (
                                    "requested_prestation",
                                    "Follow-up episodes cannot request consulta_nueva",
                                )
                            )
                    index_date = queue_entry if queue_type == "new_consultation" else due
                    if index_date is not None and index_date > snapshot:
                        contradictions.append(
                            (
                                "queue_entry_date" if queue_type == "new_consultation" else "control_due_date",
                                "Queue entry or control due date cannot be after snapshot_date",
                            )
                        )
                    if status == "completed":
                        if completion is None:
                            contradictions.append(
                                ("completion_date", "Completed episodes require completion_date")
                            )
                        elif completion > snapshot or (
                            index_date is not None and completion < index_date
                        ):
                            contradictions.append(
                                (
                                    "completion_date",
                                    "completion_date must be between the episode index date and snapshot_date",
                                )
                            )
                    elif completion is not None:
                        contradictions.append(
                            ("completion_date", "Only completed episodes may have completion_date")
                        )
                    if status == "open_scheduled":
                        if scheduled is None:
                            contradictions.append(
                                ("scheduled_date", "open_scheduled requires scheduled_date")
                            )
                    elif scheduled is not None:
                        contradictions.append(
                            ("scheduled_date", "scheduled_date is only valid for open_scheduled episodes")
                        )
                    if status == "exited":
                        if exit_reason is None:
                            contradictions.append(
                                ("exit_reason", "Exited episodes require exit_reason")
                            )
                    elif exit_reason is not None:
                        contradictions.append(
                            ("exit_reason", "Only exited episodes may have exit_reason")
                        )
                    if profile_id is not None:
                        profile = professional_profile_by_id.get(profile_id)
                        if profile is None:
                            contradictions.append(
                                (
                                    "professional_profile_id",
                                    "Unknown simulated professional profile",
                                )
                            )
                        elif (
                            profile.get("service_id") != normalized["service_id"]
                            or profile.get("specialty_id")
                            != normalized["specialty_id"]
                        ):
                            contradictions.append(
                                (
                                    "professional_profile_id",
                                    "Professional profile does not match service and specialty",
                                )
                            )
                    if referral_diagnosis_id is not None:
                        diagnosis = referral_diagnosis_by_id.get(
                            referral_diagnosis_id
                        )
                        if diagnosis is None:
                            row_issues.append(
                                ValidationIssue(
                                    "ROW_INVALID_REFERRAL_DIAGNOSIS",
                                    "error",
                                    "Unknown or inactive simulated referral diagnosis",
                                    sheet_name,
                                    row_number,
                                    "referral_diagnosis_id",
                                    referral_diagnosis_id,
                                )
                            )
                        elif diagnosis["specialty_id"] != normalized["specialty_id"]:
                            row_issues.append(
                                ValidationIssue(
                                    "ROW_DIAGNOSIS_SPECIALTY_MISMATCH",
                                    "error",
                                    "Referral diagnosis is incompatible with specialty_id",
                                    sheet_name,
                                    row_number,
                                    "referral_diagnosis_id",
                                    referral_diagnosis_id,
                                )
                            )
                    if normalized["simulated_flag"] is not True:
                        contradictions.append(
                            ("simulated_flag", "All waitlist rows must be simulated")
                        )
                    for field_name, message in contradictions:
                        row_issues.append(
                            ValidationIssue(
                                "ROW_WAITLIST_SEMANTIC_CONTRADICTION",
                                "error",
                                message,
                                sheet_name,
                                row_number,
                                field_name,
                                normalized.get(field_name),
                            )
                        )

            if row_issues:
                issues.extend(row_issues)
                quarantined[sheet_name].append(
                    {
                        "_source_row": row_number,
                        "_issues": [issue.as_dict() for issue in row_issues],
                        **raw_row,
                    }
                )
            else:
                accepted[sheet_name].append(normalized)

    timestamp = validation_timestamp_utc or datetime.now().astimezone().isoformat()
    policy = contract["validation_policy"]
    return ValidationReport(
        validation_timestamp_utc=timestamp,
        metadata=metadata,
        accepted_rows=accepted,
        quarantined_rows=quarantined,
        issues=issues,
        structural_errors=structural_errors,
        minimum_accepted_record_pct=float(
            policy["minimum_accepted_record_pct_for_activation"]
        ),
        minimum_rows_per_sheet=int(
            policy["minimum_accepted_rows_per_data_sheet"]
        ),
    )


def validate_workbook(workbook_path: Path, repo_root: Path) -> ValidationReport:
    return validate_tables(load_workbook_tables(workbook_path), repo_root)
