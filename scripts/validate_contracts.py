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
    }
    contracts = {name: load_json(path) for name, path in paths.items()}
    services = contracts["services"]
    indicators = contracts["indicators"]
    roles = contracts["roles"]
    ui = contracts["ui"]

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
        (indicators["indicators"], "indicator_id", "indicators.indicators"),
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
    indicator_ids = namespaces["indicators.indicators"]
    role_ids = namespaces["role_matrix.role_views"]
    rule_ids = namespaces["role_matrix.finding_rules"]
    map_role_ids = namespaces["role_matrix.map_contracts"]
    ui_role_ids = namespaces["ui.view_contracts"]

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
        "roles": len(role_ids),
        "units": len(unit_ids),
        "specialties": len(specialty_ids),
        "maps": len(map_role_ids),
        "finding_rules": len(rule_ids),
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
        f"{counts['roles']} roles; "
        f"{counts['units']} units; "
        f"{counts['specialties']} specialties; "
        f"{counts['maps']} maps; "
        f"{counts['finding_rules']} finding rules"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
