"""Spanish role and context selection workflow."""

from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard.components.common import render_simulation_notice
from hec_dashboard.app_config import (
    professional_profiles,
    professional_specialty_choices,
    role_label,
    service_choices,
    specialty_choices,
)
from hec_dashboard.app_state import Keys, set_role_context


ROLE_VARIANTS = {
    "Directivo": {
        "Director": "director",
        "Director Médico": "medical_director",
    },
    "Jefe de Servicio": {
        "Clínico": "service_chief_clinical",
        "Quirúrgico": "service_chief_surgical",
    },
    "Profesional": {
        "Clínico": "professional_clinical",
        "Quirúrgico": "professional_surgical",
        "Mixto": "professional_mixed",
    },
}


def _clear_widget_keys(*keys: str) -> None:
    for key in keys:
        st.session_state.pop(key, None)


def _clear_widget_prefixes(*prefixes: str) -> None:
    for key in list(st.session_state):
        if any(key.startswith(prefix) for prefix in prefixes):
            st.session_state.pop(key, None)


def _clear_professional_draft() -> None:
    _clear_widget_keys(
        "role_simulated_profile",
        "role_professional_specialty_id",
        "role_professional_profile_id",
        "role_professional_lens",
        "dashboard_mixed_lens",
    )
    _clear_widget_prefixes("role_prof_specialty_", "role_prof_profile_")


def _category_changed() -> None:
    _clear_widget_keys(
        "role_variant",
        "role_service_id",
        "role_specialty_id",
    )
    _clear_professional_draft()


def _variant_changed() -> None:
    _clear_widget_keys("role_service_id", "role_specialty_id")
    _clear_professional_draft()


def _service_changed() -> None:
    _clear_widget_keys("role_specialty_id")


def _professional_specialty_changed() -> None:
    _clear_widget_prefixes("role_prof_profile_")


def _service_context(role_id: str) -> dict[str, Any]:
    dashboard_type = "clinical" if role_id.endswith("clinical") else "surgical"
    services = service_choices(dashboard_type)
    service_ids = [item["unit_id"] for item in services]
    labels = {item["unit_id"]: item["display_name"] for item in services}
    service_id = st.selectbox(
        "3. Unidad organizacional o servicio",
        service_ids,
        format_func=labels.get,
        key="role_service_id",
        on_change=_service_changed,
    )
    specialties = specialty_choices(service_id)
    specialty_id = None
    if specialties:
        specialty_ids: list[str | None] = [
            None,
            *[item["specialty_id"] for item in specialties],
        ]
        specialty_labels = {
            None: "Todas las especialidades aplicables",
            **{item["specialty_id"]: item["display_name"] for item in specialties},
        }
        specialty_id = st.selectbox(
            "4. Especialidad analítica (opcional)",
            specialty_ids,
            format_func=specialty_labels.get,
            key="role_specialty_id",
        )
    return {
        "dashboard_type": dashboard_type,
        "service_id": service_id,
        "specialty_id": specialty_id,
    }


def _professional_context(role_id: str) -> dict[str, Any]:
    profile_type = {
        "professional_clinical": "clinical",
        "professional_surgical": "surgical",
        "professional_mixed": "mixed",
    }[role_id]
    specialties = professional_specialty_choices(profile_type)
    if not specialties:
        st.error("No existen especialidades aprobadas para esta selección profesional.")
        return {}
    specialty_labels = {
        item["specialty_id"]: item["display_name"] for item in specialties
    }
    specialty_id = st.selectbox(
        "3. Especialidad",
        list(specialty_labels),
        index=None,
        placeholder="Seleccione una especialidad",
        format_func=specialty_labels.get,
        key=f"role_prof_specialty_{profile_type}",
        on_change=_professional_specialty_changed,
    )
    if specialty_id is None:
        return {}
    profiles = professional_profiles(profile_type, specialty_id)
    profile_by_id = {item["professional_id"]: item for item in profiles}
    profile_id = st.selectbox(
        "4. Perfil profesional simulado",
        list(profile_by_id),
        index=None,
        placeholder="Seleccione un perfil simulado",
        format_func=lambda value: profile_by_id[value]["display_label_es"],
        help=(
            "Perfil completamente ficticio. El identificador interno no corresponde "
            "a una persona real."
        ),
        key=f"role_prof_profile_{profile_type}_{specialty_id}",
    )
    if profile_id is None:
        return {"profile_type": profile_type, "specialty_id": specialty_id}
    profile = profile_by_id[profile_id]
    context: dict[str, Any] = {
        "simulated_profile_key": profile_id,
        "professional_id": profile_id,
        "professional_display_label": profile["display_label_es"],
        "professional_short_label": profile["short_label_es"],
        "profile_type": profile_type,
        "service_id": profile["service_id"],
        "specialty_id": profile["specialty_id"],
        "specialty_display_name": profile["specialty_display_name"],
        "specialty_context_label": profile.get(
            "specialty_context_label_es", profile["specialty_display_name"]
        ),
    }
    if role_id == "professional_clinical":
        context["professional_lens"] = "clinical"
    elif role_id == "professional_surgical":
        context["professional_lens"] = "surgical"
    else:
        context["professional_lenses"] = ["clinical", "surgical"]
        context["professional_lens_contexts"] = profile["lens_contexts"]
    return context


def render() -> None:
    st.header("Seleccione su vista de trabajo")
    render_simulation_notice()
    st.write(
        "Complete los pasos en orden para personalizar esta demostración. "
        "Esta selección no constituye autenticación ni autorización productiva."
    )
    current = st.session_state.get(Keys.ROLE_CONTEXT)
    if current:
        st.caption(
            f"Vista activa: {role_label(current.get('role_id'))}. "
            "Una nueva selección reemplazará solamente este contexto de vista."
        )

    category = st.selectbox(
        "1. Tipo de usuario",
        list(ROLE_VARIANTS),
        index=None,
        placeholder="Seleccione un tipo de usuario",
        key="role_category",
        on_change=_category_changed,
    )
    if category is None:
        return
    variant = st.selectbox(
        "2. Rol o enfoque",
        list(ROLE_VARIANTS[category]),
        index=None,
        placeholder="Seleccione una opción",
        key="role_variant",
        on_change=_variant_changed,
    )
    if variant is None:
        return
    role_id = ROLE_VARIANTS[category][variant]
    context: dict[str, Any] = {"role_id": role_id, "category": category}
    if role_id.startswith("service_chief"):
        context.update(_service_context(role_id))
    elif role_id.startswith("professional"):
        context.update(_professional_context(role_id))

    complete = bool(context.get("role_id"))
    if role_id.startswith("service_chief"):
        complete = complete and bool(context.get("service_id"))
    if role_id.startswith("professional"):
        complete = complete and bool(
            context.get("specialty_id") and context.get("simulated_profile_key")
        )
    if st.button(
        "Entrar al dashboard",
        type="primary",
        disabled=not complete,
        use_container_width=True,
    ):
        set_role_context(st.session_state, context)
        st.rerun()
