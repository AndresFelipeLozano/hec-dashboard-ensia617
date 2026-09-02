"""Immutable contract loading and UI lookups for the Streamlit shell."""

from __future__ import annotations

import copy
from functools import lru_cache
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

_CONTRACTS: dict[str, tuple[str, ...]] = {
    "services": ("catalog_version", "organizational_units", "analytical_specialties"),
    "indicators": ("catalog_version", "indicators"),
    "role_matrix": ("matrix_version", "role_views"),
    "ui_contract": ("contract_version", "view_contracts", "navigation_flow"),
    "data_contract": ("contract_version", "workbook", "sheets"),
    "indicator_bindings": ("binding_version", "bindings"),
    "professional_profiles": ("contract_version", "profiles", "simulation_only"),
}

PROFESSIONAL_TYPES = {"clinical", "surgical", "mixed"}


class AppConfigError(RuntimeError):
    """Raised when an approved application contract is missing or malformed."""


@lru_cache(maxsize=None)
def _contract_text(name: str, repo_root_text: str) -> str:
    if name not in _CONTRACTS:
        raise AppConfigError(f"Contrato desconocido: {name}")
    path = Path(repo_root_text) / "config" / f"{name}.json"
    try:
        text = path.read_text(encoding="utf-8")
        value = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise AppConfigError(f"No se pudo cargar {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AppConfigError(f"{path} debe contener un objeto JSON")
    missing = [key for key in _CONTRACTS[name] if key not in value]
    if missing:
        raise AppConfigError(f"{path} no contiene claves requeridas: {missing}")
    return text


def load_contract(name: str, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Return an independent contract copy, resolved without relying on cwd."""

    return json.loads(_contract_text(name, str(repo_root.resolve())))


def get_role_definition(role_id: str, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    for role in load_contract("role_matrix", repo_root)["role_views"]:
        if role["role_id"] == role_id:
            return copy.deepcopy(role)
    raise AppConfigError(f"role_id no aprobado: {role_id}")


def get_indicator_definition(
    indicator_id: str, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    for indicator in load_contract("indicators", repo_root)["indicators"]:
        if indicator["indicator_id"] == indicator_id:
            return copy.deepcopy(indicator)
    raise AppConfigError(f"indicator_id no aprobado: {indicator_id}")


def get_ui_view(role_id: str, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    for view in load_contract("ui_contract", repo_root)["view_contracts"]:
        if view["role_id"] == role_id:
            return copy.deepcopy(view)
    raise AppConfigError(f"Vista no aprobada para role_id: {role_id}")


def service_choices(
    dashboard_type: str, repo_root: Path = REPO_ROOT
) -> list[dict[str, Any]]:
    if dashboard_type not in {"clinical", "surgical"}:
        raise AppConfigError(f"Tipo de servicio no aprobado: {dashboard_type}")
    units = [
        copy.deepcopy(item)
        for item in load_contract("services", repo_root)["organizational_units"]
        if item.get("mvp_enabled") and item.get("dashboard_type") == dashboard_type
    ]
    return sorted(units, key=lambda item: item["display_name"].casefold())


def specialty_choices(
    service_id: str, repo_root: Path = REPO_ROOT
) -> list[dict[str, Any]]:
    services = load_contract("services", repo_root)
    enabled_units = {
        item["unit_id"]
        for item in services["organizational_units"]
        if item.get("mvp_enabled")
    }
    if service_id not in enabled_units:
        raise AppConfigError(f"Unidad no aprobada o diferida: {service_id}")
    specialties = [
        copy.deepcopy(item)
        for item in services["analytical_specialties"]
        if item.get("mvp_enabled") and item.get("parent_unit_id") == service_id
    ]
    return sorted(specialties, key=lambda item: item["display_name"].casefold())


def role_label(role_id: str | None, repo_root: Path = REPO_ROOT) -> str:
    if not role_id:
        return "Rol no seleccionado"
    return get_role_definition(role_id, repo_root)["display_name_es"]


def service_label(service_id: str, repo_root: Path = REPO_ROOT) -> str:
    for item in load_contract("services", repo_root)["organizational_units"]:
        if item["unit_id"] == service_id and item.get("mvp_enabled"):
            return item["display_name"]
    raise AppConfigError(f"Unidad no aprobada o diferida: {service_id}")


def specialty_label(specialty_id: str, repo_root: Path = REPO_ROOT) -> str:
    for item in load_contract("services", repo_root)["analytical_specialties"]:
        if item["specialty_id"] == specialty_id and item.get("mvp_enabled"):
            return item["display_name"]
    raise AppConfigError(f"Especialidad no aprobada o diferida: {specialty_id}")


def professional_profiles(
    profile_type: str,
    specialty_id: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, Any]]:
    """Return enabled simulated profiles compatible with one professional context."""

    if profile_type not in PROFESSIONAL_TYPES:
        raise AppConfigError(f"Tipo profesional no aprobado: {profile_type}")
    profiles = [
        copy.deepcopy(item)
        for item in load_contract("professional_profiles", repo_root)["profiles"]
        if item.get("mvp_enabled")
        and item.get("simulated") is True
        and item.get("profile_type") == profile_type
        and (specialty_id is None or item.get("specialty_id") == specialty_id)
    ]
    return sorted(
        profiles,
        key=lambda item: (item["specialty_display_name"].casefold(), item["professional_id"]),
    )


def professional_specialty_choices(
    profile_type: str, repo_root: Path = REPO_ROOT
) -> list[dict[str, str]]:
    """Return unique, catalog-backed specialties that have compatible profiles."""

    choices: dict[str, dict[str, str]] = {}
    for profile in professional_profiles(profile_type, repo_root=repo_root):
        specialty_id = profile["specialty_id"]
        catalog_name = specialty_label(specialty_id, repo_root)
        if catalog_name != profile["specialty_display_name"]:
            raise AppConfigError(
                f"El perfil {profile['professional_id']} no coincide con services.json"
            )
        choices[specialty_id] = {
            "specialty_id": specialty_id,
            "display_name": profile.get("specialty_context_label_es", catalog_name),
        }
    return sorted(choices.values(), key=lambda item: item["display_name"].casefold())


def get_professional_profile(
    professional_id: str, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    for profile_type in sorted(PROFESSIONAL_TYPES):
        for profile in professional_profiles(profile_type, repo_root=repo_root):
            if profile["professional_id"] == professional_id:
                return profile
    raise AppConfigError(f"Perfil profesional simulado no aprobado: {professional_id}")


def professional_lens_context(
    profile: dict[str, Any], lens: str
) -> dict[str, str]:
    """Resolve the approved service/specialty pair for one profile lens."""

    if lens not in profile.get("supported_lenses", []):
        raise AppConfigError(
            f"El perfil {profile.get('professional_id')} no admite el lente {lens}"
        )
    if profile.get("profile_type") == "mixed":
        context = profile.get("lens_contexts", {}).get(lens)
        if not isinstance(context, dict):
            raise AppConfigError(
                f"El perfil {profile.get('professional_id')} no define contexto para {lens}"
            )
        expected_activity_class = {
            "clinical": "outpatient_clinical",
            "surgical": "surgical_procedural",
        }[lens]
        shared_scope = {
            "service_id": profile.get("service_id"),
            "specialty_id": profile.get("specialty_id"),
            "specialty_display_name": profile.get("specialty_display_name"),
        }
        if any(context.get(key) != value for key, value in shared_scope.items()):
            raise AppConfigError(
                "El perfil mixto debe conservar una sola unidad y especialidad"
            )
        if context.get("professional_id", profile.get("professional_id")) != profile.get(
            "professional_id"
        ):
            raise AppConfigError(
                "El perfil mixto debe conservar una sola identidad profesional"
            )
        if context.get("activity_class") != expected_activity_class:
            raise AppConfigError(
                f"El lente {lens} no define la clase de actividad aprobada"
            )
        return copy.deepcopy(context)
    return {
        "service_id": profile["service_id"],
        "specialty_id": profile["specialty_id"],
        "specialty_display_name": profile["specialty_display_name"],
    }


def primary_indicator_ids(
    role_id: str, repo_root: Path = REPO_ROOT
) -> tuple[str, ...]:
    ids = tuple(get_role_definition(role_id, repo_root)["primary_indicator_ids"])
    if len(ids) > 6:
        raise AppConfigError(f"{role_id} supera el máximo de seis KPI primarios")
    return ids
