"""Governed HEC-only historical inpatient reference and deterministic metrics."""

from __future__ import annotations

import calendar
import csv
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .app_config import REPO_ROOT, load_contract


ANNUAL_FIELDS = (
    "establishment_code",
    "establishment_name",
    "commune",
    "performance_year",
    "available_bed_days",
    "occupied_bed_days",
    "total_stay_days",
    "discharges",
    "death_discharges",
)
MONTHLY_FIELDS = (
    "establishment_code",
    "month_start",
    "available_bed_days",
    "occupied_bed_days",
    "total_stay_days",
    "discharges",
    "death_discharges",
)
PRIMITIVE_FIELDS = (
    "available_bed_days",
    "occupied_bed_days",
    "total_stay_days",
    "discharges",
    "death_discharges",
)


class InpatientReferenceError(RuntimeError):
    """Raised when the isolated inpatient reference fails closed."""


class InpatientAccessError(PermissionError):
    """Raised when a role requests a restricted historical reference."""


@dataclass(frozen=True)
class InpatientReferenceDataset:
    annual: Mapping[str, str | int | None]
    monthly: tuple[Mapping[str, str | int | date | None], ...]
    manifest: Mapping[str, Any]
    contract: Mapping[str, Any]


@dataclass(frozen=True)
class InpatientIndicatorResult:
    indicator_id: str
    display_name_es: str
    status: str
    value: float | int | None
    prior_value: None
    unit: str
    numerator: float | int | None
    denominator: float | int | None
    valid_n: int
    minimum_valid_n: int
    reason_es: str
    reference: Mapping[str, Any]
    period_start: date
    period_end: date
    previous_period_start: None
    previous_period_end: None
    filters: Mapping[str, str]
    calculation_basis_es: str
    source_class: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "indicator_id": self.indicator_id,
            "display_name_es": self.display_name_es,
            "status": self.status,
            "value": self.value,
            "prior_value": None,
            "unit": self.unit,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "valid_n": self.valid_n,
            "minimum_valid_n": self.minimum_valid_n,
            "reason_es": self.reason_es,
            "reference": dict(self.reference),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "previous_period_start": None,
            "previous_period_end": None,
            "filters": dict(self.filters),
            "calculation_basis_es": self.calculation_basis_es,
            "source_class": self.source_class,
        }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InpatientReferenceError(f"No se pudo cargar {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InpatientReferenceError(f"{path} debe contener un objeto JSON")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(65536), b""):
                digest.update(block)
    except OSError as exc:
        raise InpatientReferenceError(f"No se pudo verificar {path}: {exc}") from exc
    return digest.hexdigest()


def _read_csv(path: Path, expected_fields: tuple[str, ...]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != expected_fields:
                raise InpatientReferenceError(
                    f"{path}: esquema inesperado; se requieren {expected_fields}"
                )
            return list(reader)
    except OSError as exc:
        raise InpatientReferenceError(f"No se pudo cargar {path}: {exc}") from exc


def _nonnegative_integer(value: str, *, field: str, row_label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise InpatientReferenceError(
            f"{row_label}: {field} debe ser un entero"
        ) from exc
    if parsed < 0:
        raise InpatientReferenceError(f"{row_label}: {field} no puede ser negativo")
    return parsed


def _artifact_path(repo_root: Path, contract: Mapping[str, Any], key: str) -> Path:
    relative = contract.get(key)
    if not isinstance(relative, str) or not relative:
        raise InpatientReferenceError(f"Contrato hospitalario sin {key}")
    path = (repo_root / relative).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise InpatientReferenceError(f"{key} sale del repositorio") from exc
    return path


def role_can_access_inpatient_reference(
    role_id: str, *, repo_root: Path = REPO_ROOT
) -> bool:
    contract = load_contract("inpatient_reference", repo_root)
    return role_id in contract["allowed_role_ids"]


def load_inpatient_reference(
    role_id: str, *, repo_root: Path = REPO_ROOT
) -> InpatientReferenceDataset:
    """Load the isolated reference after integrity, period, and role checks."""

    contract = load_contract("inpatient_reference", repo_root)
    allowed_roles = set(contract["allowed_role_ids"])
    if role_id not in allowed_roles:
        raise InpatientAccessError(
            f"El rol {role_id!r} no puede acceder a la referencia hospitalaria"
        )

    annual_path = _artifact_path(repo_root, contract, "annual_file")
    monthly_path = _artifact_path(repo_root, contract, "monthly_file")
    manifest_path = _artifact_path(repo_root, contract, "manifest_file")
    manifest = _load_json(manifest_path)

    expected_links = {
        "dataset_id": contract["dataset_id"],
        "reference_contract_version": contract["reference_contract_version"],
        "selected_establishment_code": contract["establishment_code"],
        "performance_year": contract["observation_period"]["performance_year"],
        "annual_reference_file": contract["annual_file"],
        "monthly_reference_file": contract["monthly_file"],
    }
    for key, expected in expected_links.items():
        if manifest.get(key) != expected:
            raise InpatientReferenceError(
                f"Manifest hospitalario inconsistente en {key}: {manifest.get(key)!r}"
            )
    for path, manifest_key in (
        (annual_path, "annual_reference_sha256"),
        (monthly_path, "monthly_reference_sha256"),
    ):
        if _sha256(path) != manifest.get(manifest_key):
            raise InpatientReferenceError(
                f"Fallo de integridad para {path.name}: hash distinto del manifest"
            )

    annual_rows = _read_csv(annual_path, ANNUAL_FIELDS)
    if len(annual_rows) != 1:
        raise InpatientReferenceError(
            "La referencia anual debe contener exactamente un registro HEC"
        )
    annual_raw = annual_rows[0]
    code = contract["establishment_code"]
    year = contract["observation_period"]["performance_year"]
    if annual_raw["establishment_code"] != code:
        raise InpatientReferenceError("La referencia anual contiene un establecimiento no autorizado")
    if annual_raw["commune"] != "Maipú":
        raise InpatientReferenceError("La referencia HEC debe conservar la comuna Maipú")
    annual: dict[str, str | int | None] = dict(annual_raw)
    annual["performance_year"] = _nonnegative_integer(
        annual_raw["performance_year"], field="performance_year", row_label="HEC anual"
    )
    if annual["performance_year"] != year:
        raise InpatientReferenceError("El año anual no coincide con el contrato")
    for field in PRIMITIVE_FIELDS:
        annual[field] = _nonnegative_integer(
            annual_raw[field], field=field, row_label="HEC anual"
        )

    monthly_rows = _read_csv(monthly_path, MONTHLY_FIELDS)
    parsed_monthly: list[dict[str, str | int | date | None]] = []
    for index, row in enumerate(monthly_rows, start=1):
        label = f"HEC mensual fila {index}"
        if row["establishment_code"] != code:
            raise InpatientReferenceError(f"{label}: establecimiento no autorizado")
        try:
            month_start = date.fromisoformat(row["month_start"])
        except ValueError as exc:
            raise InpatientReferenceError(f"{label}: month_start inválido") from exc
        if month_start.year != year or month_start.day != 1:
            raise InpatientReferenceError(f"{label}: mes fuera del período aprobado")
        parsed: dict[str, str | int | date | None] = dict(row)
        parsed["month_start"] = month_start
        for field in PRIMITIVE_FIELDS:
            parsed[field] = _nonnegative_integer(row[field], field=field, row_label=label)
        parsed_monthly.append(parsed)

    expected_months = {date(year, month, 1) for month in range(1, 13)}
    actual_months = {row["month_start"] for row in parsed_monthly}
    if len(parsed_monthly) != 12 or actual_months != expected_months:
        raise InpatientReferenceError(
            "La referencia mensual debe contener los doce meses de 2025 una sola vez"
        )
    for field in PRIMITIVE_FIELDS:
        monthly_total = sum(int(row[field]) for row in parsed_monthly)
        if monthly_total != annual[field]:
            raise InpatientReferenceError(
                f"La suma mensual de {field} no reconcilia con el total anual"
            )
    if manifest.get("monthly_reference_active") is not True:
        raise InpatientReferenceError("La serie mensual no está autorizada en el manifest")
    if manifest.get("records_after_filter") != 1 or manifest.get("cerrillos_records") != 0:
        raise InpatientReferenceError("El alcance territorial del manifest es inconsistente")

    return InpatientReferenceDataset(
        annual=annual,
        monthly=tuple(sorted(parsed_monthly, key=lambda row: row["month_start"])),
        manifest=manifest,
        contract=contract,
    )


class InpatientIndicatorEngine:
    """Calculate descriptive inpatient metrics without touching operational uploads."""

    def __init__(self, dataset: InpatientReferenceDataset) -> None:
        self.dataset = dataset
        indicators = dataset.contract["indicators"]
        self.indicators = {item["indicator_id"]: item for item in indicators}
        if len(self.indicators) != len(indicators):
            raise InpatientReferenceError("Los indicadores hospitalarios deben ser únicos")

    @classmethod
    def from_repo(
        cls, role_id: str, *, repo_root: Path = REPO_ROOT
    ) -> "InpatientIndicatorEngine":
        return cls(load_inpatient_reference(role_id, repo_root=repo_root))

    def calculate(
        self,
        indicator_id: str,
        row: Mapping[str, str | int | date | None] | None = None,
    ) -> InpatientIndicatorResult:
        if indicator_id not in self.indicators:
            raise InpatientReferenceError(
                f"Indicador hospitalario no aprobado: {indicator_id}"
            )
        definition = self.indicators[indicator_id]
        values = row or self.dataset.annual
        month_start = values.get("month_start")
        if isinstance(month_start, date):
            period_start = month_start
            period_end = date(
                month_start.year,
                month_start.month,
                calendar.monthrange(month_start.year, month_start.month)[1],
            )
        else:
            period_start = date.fromisoformat(
                self.dataset.contract["observation_period"]["period_start"]
            )
            period_end = date.fromisoformat(
                self.dataset.contract["observation_period"]["period_end"]
            )

        numerator_value = values.get(definition["numerator_field"])
        denominator_field = definition.get("denominator_field")
        if denominator_field == "calendar_days":
            denominator_value: int | None = (period_end - period_start).days + 1
        elif denominator_field:
            raw_denominator = values.get(denominator_field)
            denominator_value = (
                int(raw_denominator) if raw_denominator is not None else None
            )
        else:
            denominator_value = None

        status = "available"
        value: float | int | None
        if numerator_value is None or (denominator_field and denominator_value is None):
            status = "unavailable"
            value = None
        elif denominator_field and denominator_value == 0:
            status = "zero_denominator"
            value = None
        elif definition["calculation"] == "count":
            value = int(numerator_value)
        else:
            value = round(
                int(numerator_value)
                * float(definition["scale"])
                / int(denominator_value),
                int(self.dataset.contract["calculation_policy"]["rounding_decimals"]),
            )

        basis = (
            f"{definition['numerator_field']}"
            if denominator_field is None
            else f"{definition['numerator_field']} / {denominator_field}"
        )
        return InpatientIndicatorResult(
            indicator_id=indicator_id,
            display_name_es=definition["display_name_es"],
            status=status,
            value=value,
            prior_value=None,
            unit=definition["unit"],
            numerator=(int(numerator_value) if numerator_value is not None else None),
            denominator=denominator_value,
            valid_n=1 if status == "available" else 0,
            minimum_valid_n=1,
            reason_es=definition["explanation_es"],
            reference={
                "type": "none",
                "value": None,
                "status": "not_applicable",
                "classification": definition["classification"],
            },
            period_start=period_start,
            period_end=period_end,
            previous_period_start=None,
            previous_period_end=None,
            filters={"establishment_code": str(values["establishment_code"])},
            calculation_basis_es=basis,
            source_class=self.dataset.contract["source_class"],
        )

    def calculate_all(self) -> list[InpatientIndicatorResult]:
        return [self.calculate(indicator_id) for indicator_id in self.indicators]

    def monthly_series(self, indicator_id: str) -> list[InpatientIndicatorResult]:
        return [self.calculate(indicator_id, row) for row in self.dataset.monthly]
