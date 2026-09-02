"""Testable, session-only application state for the Day 4 Streamlit shell."""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone
from functools import lru_cache
from io import BytesIO
import json
from pathlib import Path
from typing import Any, MutableMapping
import zipfile
from xml.etree import ElementTree as ET

from .app_config import (
    AppConfigError,
    REPO_ROOT,
    get_professional_profile,
    professional_lens_context,
)
from .data_ingestion import CandidateDataset, ValidationReport, validate_workbook


class Keys:
    INITIALIZED = "initialized"
    ROLE_CONTEXT = "role_context"
    ACTIVE_DATASET = "active_dataset"
    ACTIVE_DATASET_METADATA = "active_dataset_metadata"
    ACTIVE_VALIDATION_SUMMARY = "active_validation_summary"
    CANDIDATE_DATASET = "candidate_dataset"
    CANDIDATE_VALIDATION_SUMMARY = "candidate_validation_summary"
    CANDIDATE_FILE_NAME = "candidate_file_name"
    SELECTED_CURRENT_PERIOD = "selected_current_period"
    SELECTED_PREVIOUS_PERIOD = "selected_previous_period"
    LAST_ACTIVATION_TIMESTAMP = "last_activation_timestamp"
    LAST_ERROR = "last_error"
    ACTIVE_SOURCE_MODE = "active_source_mode"
    PENDING_NAVIGATION = "pending_navigation"
    ROLE_DRAFT_RESET_PENDING = "role_draft_reset_pending"


ROLE_DRAFT_KEYS = (
    "role_category",
    "role_variant",
    "role_service_id",
    "role_specialty_id",
    "role_simulated_profile",
    "role_professional_specialty_id",
    "role_professional_profile_id",
    "role_professional_lens",
    "dashboard_mixed_lens",
)

ROLE_DRAFT_PREFIXES = ("role_prof_specialty_", "role_prof_profile_")

ROLE_IDS = {
    "director",
    "medical_director",
    "service_chief_clinical",
    "service_chief_surgical",
    "professional_clinical",
    "professional_surgical",
    "professional_mixed",
}


class AppInitializationError(RuntimeError):
    """Raised when the approved bundled dataset cannot initialize safely."""


class _WorkbookBytesIO(BytesIO):
    """In-memory workbook accepted by the protected path-oriented reader."""

    suffix = ".xlsx"

    def is_file(self) -> bool:
        return True


def _report_summary(report: ValidationReport) -> dict[str, Any]:
    summary = copy.deepcopy(report.summary())
    sheet_names = sorted(set(report.accepted_rows) | set(report.quarantined_rows))
    summary["per_sheet"] = {
        name: {
            "accepted": len(report.accepted_rows.get(name, [])),
            "quarantined": len(report.quarantined_rows.get(name, [])),
        }
        for name in sheet_names
    }
    summary["issue_counts"] = {
        "missing_critical_fields": sum(i.code == "ROW_INVALID_VALUE" for i in report.issues),
        "invalid_codes": sum(i.code in {"ROW_INVALID_SERVICE", "ROW_INVALID_SPECIALTY"} for i in report.issues),
        "invalid_dates": sum(i.code == "ROW_DATE_OUTSIDE_PERIOD" for i in report.issues),
        "duplicate_identifiers": sum(i.code == "ROW_DUPLICATE_ID" for i in report.issues),
        "unmatched_deis_origin_codes": sum(i.code == "ROW_UNMATCHED_DEIS_CODE" for i in report.issues),
    }
    reasons: dict[str, int] = {}
    for issue in [*report.structural_errors, *report.issues]:
        reasons[issue.code] = reasons.get(issue.code, 0) + 1
    summary["rejection_reasons"] = reasons
    return summary


def _candidate_from_report(report: ValidationReport) -> CandidateDataset:
    return CandidateDataset(
        metadata=copy.deepcopy(report.metadata),
        tables=copy.deepcopy(report.accepted_rows),
        validation_summary=copy.deepcopy(report.summary()),
    )


def _default_periods() -> tuple[tuple[date, date], tuple[date, date]]:
    return (date(2026, 4, 1), date(2026, 6, 30)), (
        date(2026, 1, 1),
        date(2026, 3, 31),
    )


@lru_cache(maxsize=4)
def _load_bundled_cached(
    repo_root_text: str,
    workbook_size: int,
    workbook_mtime_ns: int,
    metadata_size: int,
    metadata_mtime_ns: int,
    profiles_size: int,
    profiles_mtime_ns: int,
) -> tuple[CandidateDataset, dict[str, Any]]:
    del (
        workbook_size,
        workbook_mtime_ns,
        metadata_size,
        metadata_mtime_ns,
        profiles_size,
        profiles_mtime_ns,
    )
    repo_root = Path(repo_root_text)
    workbook = repo_root / "templates" / "plantilla_carga_hec_v1.xlsx"
    packaged_metadata = json.loads(
        (repo_root / "data" / "simulated" / "metadata.json").read_text(
            encoding="utf-8"
        )
    )
    expected_rows = sum(packaged_metadata["row_counts"].values())
    report = validate_workbook(workbook, repo_root)
    if (
        not report.activatable
        or report.accepted_row_count != expected_rows
        or report.accepted_row_count < 6000
        or report.rejected_row_count != 0
        or report.metadata.get("contract_version") != "1.1.0"
        or report.metadata.get("dataset_id") != packaged_metadata.get("dataset_id")
        or report.metadata.get("dataset_id") != "hec-sim-day4r-v2"
    ):
        raise AppInitializationError(
            "El conjunto simulado incluido no satisface el contrato aprobado."
        )
    return _candidate_from_report(report), _report_summary(report)


def _load_bundled(repo_root: Path) -> tuple[CandidateDataset, dict[str, Any]]:
    workbook = repo_root / "templates" / "plantilla_carga_hec_v1.xlsx"
    metadata = repo_root / "data" / "simulated" / "metadata.json"
    profiles = repo_root / "config" / "professional_profiles.json"
    workbook_stat = workbook.stat()
    metadata_stat = metadata.stat()
    profiles_stat = profiles.stat()
    dataset, summary = _load_bundled_cached(
        str(repo_root.resolve()),
        workbook_stat.st_size,
        workbook_stat.st_mtime_ns,
        metadata_stat.st_size,
        metadata_stat.st_mtime_ns,
        profiles_stat.st_size,
        profiles_stat.st_mtime_ns,
    )
    return copy.deepcopy(dataset), copy.deepcopy(summary)


def initialize_session(
    state: MutableMapping[str, Any], repo_root: Path = REPO_ROOT
) -> None:
    if state.get(Keys.INITIALIZED):
        return
    try:
        dataset, summary = _load_bundled(repo_root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        state[Keys.LAST_ERROR] = str(exc)
        raise AppInitializationError(str(exc)) from exc
    current, previous = _default_periods()
    state.update(
        {
            Keys.INITIALIZED: True,
            Keys.ROLE_CONTEXT: None,
            Keys.ACTIVE_DATASET: copy.deepcopy(dataset),
            Keys.ACTIVE_DATASET_METADATA: copy.deepcopy(dataset.metadata),
            Keys.ACTIVE_VALIDATION_SUMMARY: summary,
            Keys.CANDIDATE_DATASET: None,
            Keys.CANDIDATE_VALIDATION_SUMMARY: None,
            Keys.CANDIDATE_FILE_NAME: None,
            Keys.SELECTED_CURRENT_PERIOD: current,
            Keys.SELECTED_PREVIOUS_PERIOD: previous,
            Keys.LAST_ACTIVATION_TIMESTAMP: datetime.now(timezone.utc).isoformat(),
            Keys.LAST_ERROR: None,
            Keys.ACTIVE_SOURCE_MODE: "bundled_validated_simulated_session_only",
            Keys.PENDING_NAVIGATION: None,
            Keys.ROLE_DRAFT_RESET_PENDING: False,
        }
    )


def _normalized_role_context(context: dict[str, Any]) -> dict[str, Any]:
    role_id = context.get("role_id")
    if role_id not in ROLE_IDS:
        raise ValueError("El contexto contiene un rol no aprobado")
    normalized: dict[str, Any] = {
        "role_id": role_id,
        "category": context.get("category"),
    }
    if role_id.startswith("service_chief_"):
        expected_type = "clinical" if role_id.endswith("clinical") else "surgical"
        if context.get("dashboard_type") != expected_type or not context.get(
            "service_id"
        ):
            raise ValueError("El contexto de jefatura está incompleto")
        normalized.update(
            {
                "dashboard_type": expected_type,
                "service_id": context["service_id"],
                "specialty_id": context.get("specialty_id"),
            }
        )
    elif role_id.startswith("professional_"):
        professional_id = context.get("professional_id") or context.get(
            "simulated_profile_key"
        )
        if not isinstance(professional_id, str) or not professional_id.startswith(
            "SIM-"
        ):
            raise ValueError("El perfil profesional simulado está incompleto")
        expected_type = role_id.removeprefix("professional_")
        try:
            profile = get_professional_profile(professional_id)
        except AppConfigError as exc:
            raise ValueError(str(exc)) from exc
        if (
            context.get("profile_type") != expected_type
            or profile.get("profile_type") != expected_type
        ):
            raise ValueError("El tipo de perfil no coincide con el rol")
        if (
            context.get("specialty_id") != profile.get("specialty_id")
            or context.get("service_id") != profile.get("service_id")
        ):
            raise ValueError("La especialidad no coincide con el perfil profesional")
        normalized.update(
            {
                "simulated_profile_key": professional_id,
                "professional_id": professional_id,
                "professional_display_label": profile["display_label_es"],
                "professional_short_label": profile["short_label_es"],
                "profile_type": expected_type,
                "service_id": profile["service_id"],
                "specialty_id": profile["specialty_id"],
                "specialty_display_name": profile["specialty_display_name"],
                "specialty_context_label": profile.get(
                    "specialty_context_label_es",
                    profile["specialty_display_name"],
                ),
            }
        )
        if role_id == "professional_mixed":
            lens_contexts = {
                lens: professional_lens_context(profile, lens)
                for lens in ("clinical", "surgical")
            }
            if any(
                lens_contexts[lens][field] != profile[field]
                for lens in ("clinical", "surgical")
                for field in (
                    "service_id",
                    "specialty_id",
                    "specialty_display_name",
                )
            ):
                raise ValueError(
                    "Los lentes mixtos deben conservar la misma identidad y especialidad"
                )
            normalized["professional_lenses"] = ["clinical", "surgical"]
            normalized["professional_lens_contexts"] = lens_contexts
        else:
            expected_lens = expected_type
            if context.get("professional_lens") != expected_lens:
                raise ValueError("El lente profesional explícito es obligatorio")
            normalized["professional_lens"] = expected_lens
    return normalized


def set_role_context(state: MutableMapping[str, Any], context: dict[str, Any]) -> None:
    normalized = _normalized_role_context(context)
    if normalized["role_id"].startswith("professional_"):
        metadata = state.get(Keys.ACTIVE_DATASET_METADATA) or {}
        normalized.update(
            {
                "current_period": copy.deepcopy(
                    state.get(Keys.SELECTED_CURRENT_PERIOD)
                ),
                "comparison_period": copy.deepcopy(
                    state.get(Keys.SELECTED_PREVIOUS_PERIOD)
                ),
                "active_dataset_id": metadata.get("dataset_id"),
            }
        )
    state[Keys.ROLE_CONTEXT] = normalized
    state[Keys.PENDING_NAVIGATION] = "dashboard"
    state[Keys.ROLE_DRAFT_RESET_PENDING] = True


def reset_role(state: MutableMapping[str, Any]) -> None:
    state[Keys.ROLE_CONTEXT] = None
    state[Keys.PENDING_NAVIGATION] = "landing"
    state[Keys.ROLE_DRAFT_RESET_PENDING] = True


def clear_role_draft_if_requested(state: MutableMapping[str, Any]) -> None:
    if not state.get(Keys.ROLE_DRAFT_RESET_PENDING):
        return
    for key in ROLE_DRAFT_KEYS:
        state.pop(key, None)
    for key in list(state):
        if any(key.startswith(prefix) for prefix in ROLE_DRAFT_PREFIXES):
            state.pop(key, None)
    state[Keys.ROLE_DRAFT_RESET_PENDING] = False


def consume_pending_navigation(state: MutableMapping[str, Any]) -> str | None:
    target = state.get(Keys.PENDING_NAVIGATION)
    state[Keys.PENDING_NAVIGATION] = None
    return target if target in {"dashboard", "landing"} else None


def validate_candidate_bytes(
    state: MutableMapping[str, Any],
    file_name: str,
    workbook_bytes: bytes,
    repo_root: Path = REPO_ROOT,
) -> ValidationReport:
    active_before = state.get(Keys.ACTIVE_DATASET)
    state[Keys.CANDIDATE_FILE_NAME] = file_name
    try:
        report = validate_workbook(
            _WorkbookBytesIO(workbook_bytes), repo_root  # type: ignore[arg-type]
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        zipfile.BadZipFile,
        ET.ParseError,
    ) as exc:
        state[Keys.CANDIDATE_DATASET] = None
        state[Keys.CANDIDATE_VALIDATION_SUMMARY] = {
            "status": "rejected_candidate",
            "activatable": False,
            "structural_error_count": 1,
            "rejection_reasons": {"WORKBOOK_READ_ERROR": 1},
            "error": str(exc),
        }
        state[Keys.LAST_ERROR] = str(exc)
        if state.get(Keys.ACTIVE_DATASET) is not active_before:
            raise AssertionError("La validación alteró el dataset activo")
        raise ValueError("El archivo XLSX no pudo leerse o validar su estructura") from exc
    state[Keys.CANDIDATE_VALIDATION_SUMMARY] = _report_summary(report)
    state[Keys.CANDIDATE_DATASET] = (
        _candidate_from_report(report) if report.activatable else None
    )
    state[Keys.LAST_ERROR] = None if report.activatable else "Candidato rechazado"
    if state.get(Keys.ACTIVE_DATASET) is not active_before:
        raise AssertionError("La validación alteró el dataset activo")
    return report


def activate_candidate(state: MutableMapping[str, Any]) -> CandidateDataset:
    candidate = state.get(Keys.CANDIDATE_DATASET)
    summary = state.get(Keys.CANDIDATE_VALIDATION_SUMMARY)
    if not isinstance(candidate, CandidateDataset) or not summary or not summary.get(
        "activatable"
    ):
        raise RuntimeError("No existe un candidato válido para activar")
    active = copy.deepcopy(candidate)
    state[Keys.ACTIVE_DATASET] = active
    state[Keys.ACTIVE_DATASET_METADATA] = copy.deepcopy(active.metadata)
    state[Keys.ACTIVE_VALIDATION_SUMMARY] = copy.deepcopy(summary)
    state[Keys.ACTIVE_SOURCE_MODE] = "uploaded_validated_simulated_session_only"
    state[Keys.LAST_ACTIVATION_TIMESTAMP] = datetime.now(timezone.utc).isoformat()
    state[Keys.LAST_ERROR] = None
    return copy.deepcopy(active)


def restore_bundled_dataset(
    state: MutableMapping[str, Any], repo_root: Path = REPO_ROOT
) -> CandidateDataset:
    dataset, summary = _load_bundled(repo_root)
    state[Keys.ACTIVE_DATASET] = copy.deepcopy(dataset)
    state[Keys.ACTIVE_DATASET_METADATA] = copy.deepcopy(dataset.metadata)
    state[Keys.ACTIVE_VALIDATION_SUMMARY] = summary
    state[Keys.ACTIVE_SOURCE_MODE] = "bundled_validated_simulated_session_only"
    state[Keys.LAST_ACTIVATION_TIMESTAMP] = datetime.now(timezone.utc).isoformat()
    state[Keys.LAST_ERROR] = None
    return copy.deepcopy(dataset)


def role_context_complete(state: MutableMapping[str, Any]) -> bool:
    context = state.get(Keys.ROLE_CONTEXT)
    if not isinstance(context, dict):
        return False
    role_id = context.get("role_id")
    if role_id not in ROLE_IDS:
        return False
    if role_id.startswith("service_chief_"):
        return bool(context.get("service_id") and context.get("dashboard_type"))
    if role_id.startswith("professional_"):
        return bool(
            context.get("simulated_profile_key")
            and context.get("professional_id")
            and context.get("specialty_id")
            and context.get("specialty_display_name")
            and context.get("active_dataset_id")
        )
    return True
