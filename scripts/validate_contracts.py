#!/usr/bin/env python3
"""Validate cross-contract references and safety invariants."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable


class ContractValidationError(Exception):
    """Raised when one or more actionable contract violations are found."""


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object; malformed JSON and structural errors remain visible."""
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"{path}: top-level JSON value must be an object")
    return value


def validate_unique_ids(
    items: Iterable[dict[str, Any]], key: str, context: str
) -> tuple[set[str], list[str]]:
    """Return IDs and actionable duplicate/missing-ID errors."""
    seen: set[str] = set()
    errors: list[str] = []
    for index, item in enumerate(items):
        value = item.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"{context}[{index}] requires a non-empty {key}")
            continue
        if value in seen:
            errors.append(f"{context}: duplicate {key} '{value}'")
        seen.add(value)
    return seen, errors


def validate_references(
    references: Iterable[Any], allowed: set[str], context: str
) -> tuple[int, list[str]]:
    """Validate a reference sequence against its allowed ID namespace."""
    errors: list[str] = []
    count = 0
    for value in references:
        count += 1
        if not isinstance(value, str) or not value:
            errors.append(f"{context}: reference must be a non-empty string")
        elif value not in allowed:
            errors.append(f"{context}: unknown reference '{value}'")
    return count, errors


def check_limit(value: Any, maximum: int, context: str) -> list[str]:
    if not isinstance(value, int):
        return [f"{context}: expected integer, found {type(value).__name__}"]
    if value < 0 or value > maximum:
        return [f"{context}: {value} exceeds allowed range 0..{maximum}"]
    return []


def require_value(actual: Any, expected: Any, context: str) -> list[str]:
    if actual != expected:
        return [f"{context}: expected {expected!r}, found {actual!r}"]
    return []


def collect_ui_references(
    value: Any,
    key: str | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Collect explicitly named service/unit and specialty references if added."""
    services: list[str] = []
    specialties: list[str] = []
    roles: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            child_services, child_specialties, child_roles = collect_ui_references(
                child, child_key
            )
            services.extend(child_services)
            specialties.extend(child_specialties)
            roles.extend(child_roles)
    elif isinstance(value, list):
        if key in {"service_ids", "unit_ids", "allowed_service_ids", "allowed_unit_ids"}:
            services.extend(value)
        elif key in {"specialty_ids", "allowed_specialty_ids"}:
            specialties.extend(value)
        elif key in {"role_ids", "separate_lens_role_ids"}:
            roles.extend(value)
        else:
            for child in value:
                child_services, child_specialties, child_roles = collect_ui_references(
                    child, key
                )
                services.extend(child_services)
                specialties.extend(child_specialties)
                roles.extend(child_roles)
    return services, specialties, roles


def validate_contracts(repo_root: Path) -> dict[str, int]:
    config_dir = repo_root / "config"
    paths = {
        "services": config_dir / "services.json",
        "indicators": config_dir / "indicators.json",
        "roles": config_dir / "role_matrix.json",
        "ui": config_dir / "ui_contract.json",
        "professional_profiles": config_dir / "professional_profiles.json",
        "referral_diagnoses": config_dir / "referral_diagnoses.json",
        "inpatient_reference": config_dir / "inpatient_reference.json",
    }
    contracts = {name: load_json(path) for name, path in paths.items()}
    services = contracts["services"]
    indicators = contracts["indicators"]
    roles = contracts["roles"]
    ui = contracts["ui"]
    professional_profiles = contracts["professional_profiles"]
    referral_diagnoses = contracts["referral_diagnoses"]
    inpatient_reference = contracts["inpatient_reference"]

    errors: list[str] = []
    unique_count = 0
    reference_count = 0

    id_specs = [
        (services["departments"], "department_id", "services.departments"),
        (
            services["organizational_units"],
            "unit_id",
            "services.organizational_units",
        ),
        (
            services["analytical_specialties"],
            "specialty_id",
            "services.analytical_specialties",
        ),
        (
            services["professional_profiles"],
            "profile_id",
            "services.professional_profiles",
        ),
        (
            professional_profiles["profiles"],
            "professional_id",
            "professional_profiles.profiles",
        ),
        (
            referral_diagnoses["diagnoses"],
            "diagnosis_group_id",
            "referral_diagnoses.diagnoses",
        ),
        (indicators["indicators"], "indicator_id", "indicators.indicators"),
        (
            inpatient_reference["indicators"],
            "indicator_id",
            "inpatient_reference.indicators",
        ),
        (roles["role_views"], "role_id", "role_matrix.role_views"),
        (roles["finding_rules"], "rule_id", "role_matrix.finding_rules"),
        (roles["map_contracts"], "role_id", "role_matrix.map_contracts"),
        (ui["view_contracts"], "role_id", "ui.view_contracts"),
    ]
    namespaces: dict[str, set[str]] = {}
    for items, key, context in id_specs:
        ids, id_errors = validate_unique_ids(items, key, context)
        namespaces[context] = ids
        unique_count += len(ids)
        errors.extend(id_errors)

    department_ids = namespaces["services.departments"]
    unit_ids = namespaces["services.organizational_units"]
    specialty_ids = namespaces["services.analytical_specialties"]
    profile_ids = namespaces["services.professional_profiles"]
    simulated_professional_ids = namespaces["professional_profiles.profiles"]
    diagnosis_ids = namespaces["referral_diagnoses.diagnoses"]
    indicator_ids = namespaces["indicators.indicators"]
    inpatient_indicator_ids = namespaces["inpatient_reference.indicators"]
    role_ids = namespaces["role_matrix.role_views"]
    rule_ids = namespaces["role_matrix.finding_rules"]
    map_role_ids = namespaces["role_matrix.map_contracts"]
    ui_role_ids = namespaces["ui.view_contracts"]

    expected_inpatient_indicators = {
        "inpatient_occupancy_pct",
        "inpatient_average_beds",
        "inpatient_average_length_of_stay_days",
        "inpatient_discharges_total",
        "inpatient_crude_lethality_pct",
    }
    errors.extend(
        require_value(
            inpatient_indicator_ids,
            expected_inpatient_indicators,
            "inpatient_reference indicator coverage",
        )
    )
    inpatient_roles = set(inpatient_reference.get("allowed_role_ids", []))
    checked, found_errors = validate_references(
        inpatient_roles, role_ids, "inpatient_reference allowed roles"
    )
    reference_count += checked
    errors.extend(found_errors)
    errors.extend(
        require_value(
            inpatient_roles,
            {"director", "medical_director"},
            "inpatient_reference role isolation",
        )
    )
    errors.extend(
        require_value(
            inpatient_reference.get("establishment_code"),
            "111101",
            "inpatient_reference HEC code",
        )
    )
    errors.extend(
        require_value(
            inpatient_reference.get("observation_period", {}).get("performance_year"),
            2025,
            "inpatient_reference performance year",
        )
    )
    errors.extend(
        require_value(
            inpatient_reference.get("observation_period", {}).get("comparison_period"),
            None,
            "inpatient_reference comparison period",
        )
    )
    errors.extend(
        require_value(
            inpatient_reference.get("calculation_policy", {}).get(
                "cross_source_comparison_allowed"
            ),
            False,
            "inpatient_reference cross-source comparison",
        )
    )
    errors.extend(
        require_value(
            inpatient_reference.get("calculation_policy", {}).get(
                "traffic_light_without_validated_target_allowed"
            ),
            False,
            "inpatient_reference traffic-light policy",
        )
    )
    for indicator in inpatient_reference["indicators"]:
        errors.extend(
            require_value(
                indicator.get("classification"),
                "descriptive_context",
                f"{indicator.get('indicator_id')} classification",
            )
        )
        errors.extend(
            require_value(
                indicator.get("target"),
                None,
                f"{indicator.get('indicator_id')} target",
            )
        )

    reference_sets = [
        (
            [item["parent_department_id"] for item in services["organizational_units"]],
            department_ids,
            "services.organizational_units.parent_department_id",
        ),
        (
            [item["parent_unit_id"] for item in services["analytical_specialties"]],
            unit_ids,
            "services.analytical_specialties.parent_unit_id",
        ),
        (
            [
                item["indicator_profile"]
                for item in services["organizational_units"]
                if item["mvp_enabled"]
            ],
            {
                "clinical_outpatient",
                "surgical",
            },
            "services.mvp_units.indicator_profile",
        ),
    ]
    for references, allowed, context in reference_sets:
        checked, found_errors = validate_references(references, allowed, context)
        reference_count += checked
        errors.extend(found_errors)

    checked, found_errors = validate_references(
        [item.get("specialty_id") for item in referral_diagnoses["diagnoses"]],
        specialty_ids,
        "referral_diagnoses.diagnoses.specialty_id",
    )
    reference_count += checked
    errors.extend(found_errors)
    diagnosis_counts: dict[str, int] = {}
    for item in referral_diagnoses["diagnoses"]:
        diagnosis_counts[item.get("specialty_id", "")] = (
            diagnosis_counts.get(item.get("specialty_id", ""), 0) + 1
        )
        for field in ("label_es", "diagnostic_family_es"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{item.get('diagnosis_group_id')}: {field} must be non-empty")
        errors.extend(
            require_value(
                item.get("status"), "active_mvp", f"{item.get('diagnosis_group_id')} status"
            )
        )
        errors.extend(
            require_value(
                item.get("classification"),
                "simulated_demo",
                f"{item.get('diagnosis_group_id')} classification",
            )
        )
    for specialty_id in specialty_ids:
        if diagnosis_counts.get(specialty_id, 0) < 4:
            errors.append(f"{specialty_id}: requires at least four referral diagnoses")

    errors.extend(
        require_value(
            professional_profiles.get("simulation_only"),
            True,
            "professional_profiles simulation marker",
        )
    )
    errors.extend(
        require_value(
            professional_profiles.get("dataset_id"),
            "hec-sim-day5-v1",
            "professional_profiles dataset",
        )
    )
    unit_by_id = {
        item["unit_id"]: item for item in services["organizational_units"]
    }
    specialty_by_id = {
        item["specialty_id"]: item for item in services["analytical_specialties"]
    }
    covered_specialties: dict[str, set[str]] = {
        "clinical": set(),
        "surgical": set(),
    }
    mixed_profile_count = 0
    for profile in professional_profiles["profiles"]:
        profile_id = profile.get("professional_id")
        profile_type = profile.get("profile_type")
        specialty_id = profile.get("specialty_id")
        service_id = profile.get("service_id")
        specialty = specialty_by_id.get(specialty_id)
        if profile.get("mvp_enabled") is not True or profile.get("simulated") is not True:
            errors.append(f"{profile_id}: simulated MVP markers must be true")
        for field in (
            "display_label_es",
            "short_label_es",
            "specialty_display_name",
        ):
            if not isinstance(profile.get(field), str) or not profile[field].strip():
                errors.append(f"{profile_id}: {field} must be a non-empty string")
        if profile.get("display_label_es") == profile_id:
            errors.append(f"{profile_id}: internal ID cannot be the display label")
        if specialty is None:
            errors.append(f"{profile_id}: unknown specialty_id '{specialty_id}'")
            continue
        if specialty.get("display_name") != profile.get("specialty_display_name"):
            errors.append(f"{profile_id}: specialty display name does not match services.json")
        if service_id not in unit_by_id or not unit_by_id[service_id].get("mvp_enabled"):
            errors.append(f"{profile_id}: unknown or deferred service_id '{service_id}'")
        if profile_type in {"clinical", "surgical"}:
            covered_specialties[profile_type].add(specialty_id)
            if specialty.get("dashboard_type") != profile_type:
                errors.append(f"{profile_id}: profile and specialty types are incompatible")
            if specialty.get("parent_unit_id") != service_id:
                errors.append(f"{profile_id}: service is not the specialty parent")
            if profile.get("supported_lenses") != [profile_type]:
                errors.append(f"{profile_id}: non-mixed lens must equal profile type")
        elif profile_type == "mixed":
            mixed_profile_count += 1
            if profile.get("supported_lenses") != ["clinical", "surgical"]:
                errors.append(f"{profile_id}: mixed lenses must remain separate")
            if specialty_id != "cirugia_pediatrica":
                errors.append(
                    f"{profile_id}: mixed specialty must be 'cirugia_pediatrica'"
                )
            if service_id != "cirugia_infantil":
                errors.append(
                    f"{profile_id}: mixed service must be 'cirugia_infantil'"
                )
            if specialty.get("parent_unit_id") != service_id:
                errors.append(f"{profile_id}: mixed service is not the specialty parent")
            lens_contexts = profile.get("lens_contexts")
            if not isinstance(lens_contexts, dict):
                errors.append(f"{profile_id}: mixed lens_contexts are required")
                continue
            expected_activity_classes = {
                "clinical": "outpatient_clinical",
                "surgical": "surgical_procedural",
            }
            for lens in ("clinical", "surgical"):
                lens_context = lens_contexts.get(lens, {})
                lens_specialty = specialty_by_id.get(lens_context.get("specialty_id"))
                if lens_specialty is None:
                    errors.append(f"{profile_id}: unknown {lens} lens specialty")
                    continue
                for field, expected in (
                    ("service_id", service_id),
                    ("specialty_id", specialty_id),
                    ("specialty_display_name", profile.get("specialty_display_name")),
                ):
                    if lens_context.get(field) != expected:
                        errors.append(
                            f"{profile_id}: {lens} lens must preserve mixed {field}"
                        )
                if lens_context.get("professional_id", profile_id) != profile_id:
                    errors.append(
                        f"{profile_id}: {lens} lens must preserve professional identity"
                    )
                if (
                    lens_context.get("activity_class")
                    != expected_activity_classes[lens]
                ):
                    errors.append(
                        f"{profile_id}: {lens} lens activity_class is incompatible"
                    )
        else:
            errors.append(f"{profile_id}: unsupported profile_type '{profile_type}'")

    for dashboard_type in ("clinical", "surgical"):
        expected = {
            item["specialty_id"]
            for item in services["analytical_specialties"]
            if item.get("mvp_enabled") and item.get("dashboard_type") == dashboard_type
        }
        missing = sorted(expected - covered_specialties[dashboard_type])
        extra = sorted(covered_specialties[dashboard_type] - expected)
        if missing or extra:
            errors.append(
                f"professional_profiles {dashboard_type} coverage mismatch; "
                f"missing={missing}; extra={extra}"
            )
    if mixed_profile_count < 1:
        errors.append("professional_profiles requires an approved mixed arrangement")

    role_by_id = {item["role_id"]: item for item in roles["role_views"]}
    ui_by_id = {item["role_id"]: item for item in ui["view_contracts"]}
    indicator_by_id = {
        item["indicator_id"]: item for item in indicators["indicators"]
    }

    checked, found_errors = validate_references(
        ui_role_ids, role_ids, "ui.view_contracts.role_id"
    )
    reference_count += checked
    errors.extend(found_errors)
    errors.extend(
        require_value(
            ui_role_ids,
            role_ids,
            "ui.view_contracts must cover every approved role exactly once",
        )
    )

    ui_service_refs, ui_specialty_refs, ui_role_refs = collect_ui_references(ui)
    for references, allowed, context in [
        (ui_service_refs, unit_ids, "ui service/unit references"),
        (ui_specialty_refs, specialty_ids, "ui specialty references"),
        (ui_role_refs, role_ids, "ui role references"),
    ]:
        checked, found_errors = validate_references(references, allowed, context)
        reference_count += checked
        errors.extend(found_errors)

    max_cards = roles["global_constraints"]["maximum_primary_cards"]
    max_findings = roles["global_constraints"]["maximum_prioritized_findings"]
    errors.extend(check_limit(max_cards, 6, "role_matrix.maximum_primary_cards"))
    errors.extend(
        check_limit(max_findings, 5, "role_matrix.maximum_prioritized_findings")
    )
    errors.extend(
        require_value(
            ui["global_layout"]["maximum_primary_cards"],
            max_cards,
            "ui.global_layout.maximum_primary_cards",
        )
    )
    errors.extend(
        require_value(
            ui["global_layout"]["maximum_prioritized_findings"],
            max_findings,
            "ui.global_layout.maximum_prioritized_findings",
        )
    )

    for role_id, view in ui_by_id.items():
        primary_ids = view["primary_indicator_ids"]
        checked, found_errors = validate_references(
            primary_ids, indicator_ids, f"ui view '{role_id}' primary indicators"
        )
        reference_count += checked
        errors.extend(found_errors)
        errors.extend(
            check_limit(
                len(primary_ids), max_cards, f"ui view '{role_id}' primary cards"
            )
        )
        errors.extend(
            check_limit(
                view["prioritized_findings_limit"],
                max_findings,
                f"ui view '{role_id}' prioritized findings",
            )
        )
        if role_id in role_by_id:
            errors.extend(
                require_value(
                    primary_ids,
                    role_by_id[role_id]["primary_indicator_ids"],
                    f"ui view '{role_id}' primary indicators",
                )
            )
        for chart in view["chart_contracts"]:
            chart_ids = chart.get("indicator_ids", [])
            checked, found_errors = validate_references(
                chart_ids,
                indicator_ids,
                f"ui view '{role_id}' chart '{chart['chart_id']}' indicators",
            )
            reference_count += checked
            errors.extend(found_errors)
            if "role_reference" in chart:
                checked, found_errors = validate_references(
                    [chart["role_reference"]],
                    role_ids,
                    f"ui view '{role_id}' chart role_reference",
                )
                reference_count += checked
                errors.extend(found_errors)

    quality_ids = ui["data_quality_view"]["indicator_ids"]
    checked, found_errors = validate_references(
        quality_ids, indicator_ids, "ui.data_quality_view.indicator_ids"
    )
    reference_count += checked
    errors.extend(found_errors)
    errors.extend(
        require_value(
            set(quality_ids),
            {"accepted_record_pct", "critical_field_completeness_pct"},
            "ui.data_quality_view required indicators",
        )
    )

    for rule in roles["finding_rules"]:
        checked, found_errors = validate_references(
            [rule["indicator_id"]],
            indicator_ids,
            f"finding rule '{rule['rule_id']}' indicator",
        )
        reference_count += checked
        errors.extend(found_errors)

    for role in roles["role_views"]:
        question_ids, question_errors = validate_unique_ids(
            role["questions"], "question_id", f"role '{role['role_id']}' questions"
        )
        unique_count += len(question_ids)
        errors.extend(question_errors)
        for question in role["questions"]:
            checked, found_errors = validate_references(
                question["indicator_ids"],
                indicator_ids,
                f"question '{question['question_id']}' indicators",
            )
            reference_count += checked
            errors.extend(found_errors)
            checked, found_errors = validate_references(
                question["finding_rule_ids"],
                rule_ids,
                f"question '{question['question_id']}' finding rules",
            )
            reference_count += checked
            errors.extend(found_errors)

    errors.extend(
        require_value(
            map_role_ids,
            role_ids - {"professional_mixed"},
            "role_matrix.map_contracts role coverage",
        )
    )
    for map_contract in roles["map_contracts"]:
        role_id = map_contract["role_id"]
        checked, found_errors = validate_references(
            [role_id], role_ids, f"map contract '{role_id}' role"
        )
        reference_count += checked
        errors.extend(found_errors)
        map_indicator_refs = [
            map_contract["bubble_size"],
            *map_contract["bubble_color_options"],
        ]
        checked, found_errors = validate_references(
            map_indicator_refs,
            indicator_ids,
            f"map contract '{role_id}' indicators",
        )
        reference_count += checked
        errors.extend(found_errors)
        if role_id in ui_by_id:
            ui_map_ref = ui_by_id[role_id]["map_role_reference"]
            errors.extend(
                require_value(
                    ui_map_ref,
                    role_id,
                    f"ui view '{role_id}' map_role_reference",
                )
            )

    expected_lenses = {"professional_clinical", "professional_surgical"}
    mixed = ui_by_id.get("professional_mixed")
    if mixed is None:
        errors.append("ui.view_contracts requires role_id 'professional_mixed'")
    else:
        errors.extend(
            require_value(
                set(mixed["required_selectors"]),
                {"period", "specialty", "simulated_profile", "professional_lens"},
                "professional_mixed required selectors",
            )
        )
        errors.extend(
            require_value(
                set(mixed["separate_lens_role_ids"]),
                expected_lenses,
                "professional_mixed separate lenses",
            )
        )
        errors.extend(
            require_value(
                mixed["primary_indicator_ids"],
                [],
                "professional_mixed primary indicators",
            )
        )
        errors.extend(
            require_value(
                mixed["combined_performance_score_allowed"],
                False,
                "professional_mixed combined score",
            )
        )
        errors.extend(
            require_value(
                mixed["map_role_reference"],
                None,
                "professional_mixed combined map",
            )
        )
    professional_branch = next(
        (
            item
            for item in ui["navigation_flow"]["branches"]
            if item.get("selection_es") == "Profesional"
        ),
        None,
    )
    if professional_branch is None:
        errors.append("ui.navigation requires the professional branch")
    else:
        mixed_behavior = professional_branch.get("mixed_profile_behavior", {})
        errors.extend(
            require_value(
                mixed_behavior.get("single_specialty_across_lenses"),
                True,
                "professional navigation mixed single specialty",
            )
        )
        errors.extend(
            require_value(
                mixed_behavior.get("same_professional_identity_across_lenses"),
                True,
                "professional navigation mixed shared identity",
            )
        )
    errors.extend(
        require_value(
            roles["global_constraints"]["combined_mixed_profile_score_allowed"],
            False,
            "role_matrix mixed-profile combined score",
        )
    )
    mixed_profile = next(
        (
            item
            for item in services["professional_profiles"]
            if item["profile_id"] == "mixed"
        ),
        None,
    )
    if mixed_profile is None:
        errors.append("services.professional_profiles requires profile_id 'mixed'")
    else:
        errors.extend(
            require_value(
                mixed_profile["requires_separate_lenses"],
                True,
                "services mixed profile separate lenses",
            )
        )
        errors.extend(
            require_value(
                mixed_profile["combined_score_allowed"],
                False,
                "services mixed profile combined score",
            )
        )
    checked, found_errors = validate_references(
        services["scope_rules"]["mvp_profiles"],
        {"clinical_outpatient", "surgical"},
        "services.scope_rules.mvp_profiles",
    )
    reference_count += checked
    errors.extend(found_errors)
    checked, found_errors = validate_references(
        [profile["profile_id"] for profile in services["professional_profiles"]],
        profile_ids,
        "services.professional_profiles self-check",
    )
    reference_count += checked
    errors.extend(found_errors)

    minimum_geo_n = roles["global_constraints"]["minimum_geographic_cell_n"]
    errors.extend(require_value(minimum_geo_n, 10, "role_matrix geographic cell size"))
    errors.extend(
        require_value(
            services["privacy_rules"]["minimum_geographic_cell_n"],
            minimum_geo_n,
            "services geographic cell size",
        )
    )
    errors.extend(
        require_value(
            ui["privacy_requirements"]["minimum_geographic_cell_n"],
            minimum_geo_n,
            "ui privacy geographic cell size",
        )
    )
    errors.extend(
        require_value(
            ui["shared_components"]["map"]["minimum_geographic_cell_n"],
            minimum_geo_n,
            "ui map geographic cell size",
        )
    )

    false_invariants = [
        (
            roles["global_constraints"]["public_professional_ranking_allowed"],
            "role_matrix public professional ranking",
        ),
        (
            ui["privacy_requirements"]["public_professional_ranking_allowed"],
            "ui public professional ranking",
        ),
        (
            roles["global_constraints"]["patient_level_drilldown_allowed"],
            "role_matrix patient-level drill-down",
        ),
        (
            services["privacy_rules"]["patient_level_map_drilldown_allowed"],
            "services patient-level map drill-down",
        ),
        (
            ui["privacy_requirements"]["patient_level_drilldown_allowed"],
            "ui patient-level drill-down",
        ),
        (
            roles["global_constraints"]["failed_upload_replaces_active_dataset"],
            "role_matrix failed-upload replacement",
        ),
        (
            ui["upload_view"]["failed_upload_replaces_active_dataset"],
            "ui failed-upload replacement",
        ),
        (
            ui["upload_view"]["persistence_after_session_termination"],
            "ui post-session persistence",
        ),
        (
            ui["privacy_requirements"]["patient_identifiers_allowed"],
            "ui patient identifiers",
        ),
        (
            ui["privacy_requirements"]["employee_identifiers_allowed"],
            "ui employee identifiers",
        ),
        (
            ui["privacy_requirements"]["patient_addresses_allowed"],
            "ui patient addresses",
        ),
        (
            ui["privacy_requirements"]["punitive_professional_composite_score_allowed"],
            "ui punitive professional score",
        ),
        (
            ui["privacy_requirements"]["session_data_persistence_allowed"],
            "ui session-data persistence",
        ),
        (
            services["privacy_rules"]["patient_addresses_allowed"],
            "services patient addresses",
        ),
        (
            services["privacy_rules"]["employee_identifiers_allowed"],
            "services employee identifiers",
        ),
    ]
    for actual, context in false_invariants:
        errors.extend(require_value(actual, False, context))

    true_invariants = [
        (
            ui["upload_view"]["downloadable_template_entry_point"],
            "downloadable template entry point",
        ),
        (ui["upload_view"]["excel_file_upload"], "Excel file upload"),
        (ui["upload_view"]["schema_validation_required"], "schema validation"),
        (
            ui["upload_view"]["validation_summary_required"],
            "upload validation summary",
        ),
        (
            ui["upload_view"]["explicit_valid_dataset_activation_required"],
            "explicit valid-dataset activation",
        ),
        (
            ui["upload_view"]["prior_valid_session_dataset_preserved_after_failure"],
            "prior valid dataset preservation",
        ),
        (
            ui["privacy_requirements"]["law_21719_cross_cutting_constraint"],
            "Law 21.719 constraint",
        ),
        (
            ui["accessibility_requirements"]["chart_textual_equivalent_required"],
            "chart textual equivalent",
        ),
        (
            ui["accessibility_requirements"]["map_accessible_table_required"],
            "map accessible table",
        ),
        (
            ui["interpretation_requirements"]["unavailable_values_must_not_render_as_zero"],
            "unavailable values remain non-zero",
        ),
        (
            ui["shared_components"]["map"]["suppress_geographic_cells_below_minimum"],
            "geographic cells below the minimum are suppressed",
        ),
    ]
    for actual, context in true_invariants:
        errors.extend(require_value(actual, True, f"ui required control: {context}"))
    if not ui["upload_view"]["quarantine_or_rejection_behavior"].strip():
        errors.append("ui.upload_view.quarantine_or_rejection_behavior must be non-empty")

    required_quality_fields = {
        "rejected_row_count",
        "missing_critical_fields",
        "invalid_codes",
        "invalid_dates",
        "duplicate_identifiers",
        "unmatched_deis_origin_codes",
        "validation_timestamp",
        "active_dataset_status",
    }
    errors.extend(
        require_value(
            set(ui["data_quality_view"]["validation_summary_fields"]),
            required_quality_fields,
            "ui.data_quality_view validation summary fields",
        )
    )

    if errors:
        message = "Contract validation failed:\n" + "\n".join(
            f"- {error}" for error in errors
        )
        raise ContractValidationError(message)

    return {
        "contract_files": len(paths),
        "unique_ids": unique_count,
        "references": reference_count,
        "view_limits": len(ui["view_contracts"]),
        "safety_controls": len(false_invariants) + len(true_invariants) + 4,
        "indicators": len(indicator_ids),
        "inpatient_indicators": len(inpatient_indicator_ids),
        "roles": len(role_ids),
        "units": len(unit_ids),
        "specialties": len(specialty_ids),
        "maps": len(map_role_ids),
        "finding_rules": len(rule_ids),
        "simulated_professional_profiles": len(simulated_professional_ids),
        "referral_diagnoses": len(diagnosis_ids),
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        counts = validate_contracts(repo_root)
    except ContractValidationError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"PASS unique IDs: {counts['unique_ids']}")
    print(f"PASS references: {counts['references']}")
    print(f"PASS UI view limits: {counts['view_limits']}")
    print(f"PASS safety controls: {counts['safety_controls']}")
    print(
        "PASS contracts: "
        f"{counts['contract_files']} files; "
        f"{counts['indicators']} indicators; "
        f"{counts['inpatient_indicators']} inpatient reference indicators; "
        f"{counts['roles']} roles; "
        f"{counts['units']} units; "
        f"{counts['specialties']} specialties; "
        f"{counts['simulated_professional_profiles']} simulated professional profiles; "
        f"{counts['referral_diagnoses']} simulated referral diagnoses; "
        f"{counts['maps']} maps; "
        f"{counts['finding_rules']} finding rules"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
