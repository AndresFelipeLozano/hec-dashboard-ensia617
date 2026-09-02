"""Presentation-only adapter over approved role and indicator contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from .app_config import (
    REPO_ROOT,
    get_professional_profile,
    get_role_definition,
    primary_indicator_ids,
    professional_lens_context,
)
from .data_ingestion import CandidateDataset
from .indicator_engine import IndicatorContext, IndicatorEngine, IndicatorResult


STATUS_LABELS = {
    "available": "Disponible",
    "insufficient_n": "Muestra insuficiente",
    "zero_denominator": "Sin denominador válido",
    "pending_definition": "Definición pendiente",
    "deferred": "Diferido",
    "not_applicable": "No aplica",
}

PROFESSIONAL_LENSES = {
    "professional_clinical": "clinical",
    "professional_surgical": "surgical",
}


@dataclass(frozen=True)
class KpiPresentation:
    indicator_id: str
    label_es: str
    value_text: str
    previous_text: str | None
    delta_text: str | None
    unit: str
    status: str
    status_label_es: str
    explanation_es: str
    target_text: str | None
    numerator: float | int | None
    denominator: float | int | None
    valid_n: int
    minimum_valid_n: int
    filters: dict[str, str]
    is_available: bool


def _number(value: float | int, unit: str) -> str:
    if unit == "count":
        return f"{int(round(value)):,}".replace(",", ".")
    if unit == "percentage":
        return f"{value:.1f}%".replace(".", ",")
    if unit == "days":
        rendered = f"{value:.1f}" if float(value) % 1 else f"{int(value)}"
        return f"{rendered.replace('.', ',')} días"
    return f"{value:.1f}".replace(".", ",")


def _target_text(reference: dict[str, Any]) -> str | None:
    status = reference.get("status")
    if status == "not_applicable":
        return None
    explanation = reference.get("explanation_es")
    if explanation:
        return str(explanation)
    authority = reference.get("authority")
    value = reference.get("value")
    return f"Referencia: {value} ({authority})" if value is not None else None


def present_result(result: IndicatorResult) -> KpiPresentation:
    available = result.status == "available" and result.value is not None
    value_text = _number(result.value, result.unit) if available else STATUS_LABELS[
        result.status
    ]
    previous_text = (
        _number(result.prior_value, result.unit)
        if available and result.prior_value is not None
        else None
    )
    delta_text = None
    if available and result.prior_value is not None:
        delta = float(result.value) - float(result.prior_value)
        delta_text = f"{delta:+.1f}".replace(".", ",")
        if result.unit == "percentage":
            delta_text += " pp"
        elif result.unit == "days":
            delta_text += " días"
    return KpiPresentation(
        indicator_id=result.indicator_id,
        label_es=result.display_name_es,
        value_text=value_text,
        previous_text=previous_text,
        delta_text=delta_text,
        unit=result.unit,
        status=result.status,
        status_label_es=STATUS_LABELS[result.status],
        explanation_es=result.reason_es,
        target_text=_target_text(result.reference),
        numerator=result.numerator,
        denominator=result.denominator,
        valid_n=result.valid_n,
        minimum_valid_n=result.minimum_valid_n,
        filters=dict(result.filters),
        is_available=available,
    )


def _context(
    role_id: str,
    current_period: tuple[date, date],
    previous_period: tuple[date, date],
    *,
    service_id: str | None = None,
    specialty_id: str | None = None,
    simulated_profile_key: str | None = None,
) -> IndicatorContext:
    role = get_role_definition(role_id)
    lens = PROFESSIONAL_LENSES.get(role_id)
    if role_id.startswith("professional_") and role_id != "professional_mixed" and not lens:
        raise ValueError(f"El rol profesional {role_id} no tiene lente explícito")
    return IndicatorContext(
        period_start=current_period[0],
        period_end=current_period[1],
        previous_period_start=previous_period[0],
        previous_period_end=previous_period[1],
        indicator_profile=role["indicator_profile"],
        professional_lens=lens,
        service_id=service_id,
        specialty_id=specialty_id,
        simulated_profile_key=simulated_profile_key,
    )


def _assert_professional_scope(
    dataset: CandidateDataset,
    professional_id: str,
    calculation_lens: str,
    service_id: str | None,
    specialty_id: str | None,
    repo_root: Path = REPO_ROOT,
) -> None:
    """Fail closed if a profile/lens contains rows outside its approved specialty."""

    profile = get_professional_profile(professional_id, repo_root)
    if calculation_lens not in profile["supported_lenses"]:
        raise ValueError("El perfil no admite el lente profesional solicitado")
    expected = professional_lens_context(profile, calculation_lens)
    if (
        service_id != expected["service_id"]
        or specialty_id != expected["specialty_id"]
    ):
        raise ValueError("El filtro profesional no coincide con su especialidad aprobada")
    scoped_rows = [
        row
        for row in dataset.tables.get("ACTIVIDAD_PROF", [])
        if row.get("simulated_profile_key") == professional_id
        and row.get("lens") == calculation_lens
    ]
    if not scoped_rows:
        raise ValueError("El perfil no contiene actividad para el lente seleccionado")
    incompatible = [
        row
        for row in scoped_rows
        if row.get("profile_type") != profile["profile_type"]
        or row.get("service_id") != expected["service_id"]
        or row.get("specialty_id") != expected["specialty_id"]
    ]
    if incompatible:
        raise ValueError(
            "El perfil contiene actividad de otra especialidad o tipo profesional"
        )


def build_indicator_presentations(
    indicator_ids: Iterable[str],
    role_id: str,
    dataset: CandidateDataset,
    current_period: tuple[date, date],
    previous_period: tuple[date, date],
    *,
    service_id: str | None = None,
    specialty_id: str | None = None,
    simulated_profile_key: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> list[KpiPresentation]:
    engine = _cached_engine(str(repo_root.resolve()))
    if role_id.startswith("professional_"):
        if not simulated_profile_key:
            raise ValueError("El perfil profesional simulado es obligatorio")
        calculation_lens = PROFESSIONAL_LENSES.get(role_id)
        if not calculation_lens:
            raise ValueError("El lente de cálculo profesional es obligatorio")
        _assert_professional_scope(
            dataset,
            simulated_profile_key,
            calculation_lens,
            service_id,
            specialty_id,
            repo_root,
        )
    context = _context(
        role_id,
        current_period,
        previous_period,
        service_id=service_id,
        specialty_id=specialty_id,
        simulated_profile_key=simulated_profile_key,
    )
    return [present_result(engine.calculate(i, dataset, context)) for i in indicator_ids]


@lru_cache(maxsize=4)
def _cached_engine(repo_root_text: str) -> IndicatorEngine:
    """Reuse immutable contracts without caching session-specific calculations."""

    return IndicatorEngine.from_repo(Path(repo_root_text))


def build_role_presentation(
    role_id: str,
    dataset: CandidateDataset,
    current_period: tuple[date, date],
    previous_period: tuple[date, date],
    *,
    service_id: str | None = None,
    specialty_id: str | None = None,
    simulated_profile_key: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> list[KpiPresentation]:
    if role_id == "professional_mixed":
        raise ValueError("El rol mixto debe presentarse mediante dos lentes separados")
    ids = primary_indicator_ids(role_id, repo_root)
    return build_indicator_presentations(
        ids,
        role_id,
        dataset,
        current_period,
        previous_period,
        service_id=service_id,
        specialty_id=specialty_id,
        simulated_profile_key=simulated_profile_key,
        repo_root=repo_root,
    )


def build_mixed_presentations(
    dataset: CandidateDataset,
    current_period: tuple[date, date],
    previous_period: tuple[date, date],
    simulated_profile_key: str,
    *,
    lens_contexts: dict[str, dict[str, str]],
    repo_root: Path = REPO_ROOT,
) -> dict[str, list[KpiPresentation]]:
    profile = get_professional_profile(simulated_profile_key, repo_root)
    if profile["profile_type"] != "mixed":
        raise ValueError("La presentación mixta requiere un perfil mixto aprobado")
    expected_contexts = {
        lens: professional_lens_context(profile, lens)
        for lens in ("clinical", "surgical")
    }
    if lens_contexts != expected_contexts:
        raise ValueError("Los contextos por lente no coinciden con el perfil mixto")
    if any(
        expected_contexts[lens][field] != profile[field]
        for lens in ("clinical", "surgical")
        for field in ("service_id", "specialty_id", "specialty_display_name")
    ):
        raise ValueError(
            "Los lentes mixtos deben conservar la misma identidad, unidad y especialidad"
        )
    return {
        "clinical": build_role_presentation(
            "professional_clinical",
            dataset,
            current_period,
            previous_period,
            service_id=lens_contexts["clinical"]["service_id"],
            specialty_id=lens_contexts["clinical"]["specialty_id"],
            simulated_profile_key=simulated_profile_key,
            repo_root=repo_root,
        ),
        "surgical": build_role_presentation(
            "professional_surgical",
            dataset,
            current_period,
            previous_period,
            service_id=lens_contexts["surgical"]["service_id"],
            specialty_id=lens_contexts["surgical"]["specialty_id"],
            simulated_profile_key=simulated_profile_key,
            repo_root=repo_root,
        ),
    }
