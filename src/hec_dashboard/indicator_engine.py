"""Deterministic indicator calculations for the approved HEC catalog."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Callable

from .data_ingestion import CandidateDataset


@dataclass(frozen=True)
class IndicatorContext:
    period_start: date | None = None
    period_end: date | None = None
    previous_period_start: date | None = None
    previous_period_end: date | None = None
    indicator_profile: str | None = None
    professional_lens: str | None = None
    service_id: str | None = None
    specialty_id: str | None = None
    origin_establishment_code: str | None = None
    activity_code: str | None = None
    simulated_profile_key: str | None = None

    def filters_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "indicator_profile": self.indicator_profile,
                "professional_lens": self.professional_lens,
                "service_id": self.service_id,
                "specialty_id": self.specialty_id,
                "origin_establishment_code": self.origin_establishment_code,
                "activity_code": self.activity_code,
                "simulated_profile_key": self.simulated_profile_key,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class CalculationParts:
    value: float | int | None
    numerator: float | int | None
    denominator: float | int | None
    valid_n: int


@dataclass(frozen=True)
class IndicatorResult:
    indicator_id: str
    display_name_es: str
    status: str
    value: float | int | None
    prior_value: float | int | None
    unit: str
    numerator: float | int | None
    denominator: float | int | None
    valid_n: int
    minimum_valid_n: int
    reason_es: str
    reference: dict[str, Any]
    period_start: date
    period_end: date
    previous_period_start: date
    previous_period_end: date
    filters: dict[str, str]
    calculation_basis_es: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "indicator_id": self.indicator_id,
            "display_name_es": self.display_name_es,
            "status": self.status,
            "value": self.value,
            "prior_value": self.prior_value,
            "unit": self.unit,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "valid_n": self.valid_n,
            "minimum_valid_n": self.minimum_valid_n,
            "reason_es": self.reason_es,
            "reference": self.reference,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "previous_period_start": self.previous_period_start.isoformat(),
            "previous_period_end": self.previous_period_end.isoformat(),
            "filters": self.filters,
            "calculation_basis_es": self.calculation_basis_es,
        }


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"{path}: top-level JSON must be an object")
    return value


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _ratio(numerator: float | int, denominator: float | int) -> CalculationParts:
    value = None if denominator == 0 else numerator * 100 / denominator
    return CalculationParts(value, numerator, denominator, int(denominator))


class IndicatorEngine:
    """Calculate catalog indicators without eval, dynamic formulas, or AI."""

    def __init__(
        self,
        indicator_catalog: dict[str, Any],
        binding_contract: dict[str, Any],
    ) -> None:
        self.catalog = indicator_catalog
        self.binding_contract = binding_contract
        self.indicators = {
            item["indicator_id"]: item for item in indicator_catalog["indicators"]
        }
        self.bindings = {
            item["indicator_id"]: item for item in binding_contract["bindings"]
        }
        if set(self.indicators) != set(self.bindings):
            missing = sorted(set(self.indicators) - set(self.bindings))
            extra = sorted(set(self.bindings) - set(self.indicators))
            raise ValueError(
                f"Indicator binding mismatch; missing={missing}; extra={extra}"
            )
        self._calculators: dict[
            str,
            Callable[
                [CandidateDataset, list[dict[str, Any]], list[dict[str, Any]]],
                CalculationParts,
            ],
        ] = {
            "referrals_count": self._referrals_count,
            "referral_growth": self._referral_growth,
            "referral_wait_median": self._referral_wait_median,
            "referral_wait_p75": self._referral_wait_p75,
            "referral_no_show_new": self._referral_no_show_new,
            "referral_no_show_followup": self._referral_no_show_followup,
            "referral_discharge": self._referral_discharge,
            "referral_pertinence": self._referral_pertinence,
            "referral_contrareference": self._referral_contrareference,
            "referral_ges": self._referral_ges,
            "referral_teleconsult": self._referral_teleconsult,
            "quality_accepted": self._quality_accepted,
            "quality_completeness": self._quality_completeness,
            "referral_top3_origins": self._referral_top3_origins,
            "surgery_waitlist_open": self._surgery_waitlist_open,
            "surgery_wait_p75": self._surgery_wait_p75,
            "surgery_elective_completed": self._surgery_elective_completed,
            "surgery_ambulatory": self._surgery_ambulatory,
            "surgery_suspension": self._surgery_suspension,
            "prof_clinical_completed": self._prof_clinical_completed,
            "prof_clinical_schedule": self._prof_clinical_schedule,
            "prof_clinical_new_share": self._prof_clinical_new_share,
            "prof_documentation": self._prof_documentation,
            "prof_clinical_no_show": self._prof_clinical_no_show,
            "prof_surgical_completed": self._prof_surgical_completed,
            "prof_surgical_schedule": self._prof_surgical_schedule,
            "prof_surgical_ambulatory": self._prof_surgical_ambulatory,
            "prof_surgical_suspension": self._prof_surgical_suspension,
            "wait_new_open_count": self._wait_new_open_count,
            "wait_new_median": self._wait_new_median,
            "wait_new_p75": self._wait_new_p75,
            "wait_new_over90": self._wait_new_over90,
            "wait_new_resolution": self._wait_new_resolution,
            "wait_followup_open_count": self._wait_followup_open_count,
            "wait_followup_median": self._wait_followup_median,
            "wait_followup_p75": self._wait_followup_p75,
            "wait_followup_unscheduled": self._wait_followup_unscheduled,
            "wait_followup_resolution": self._wait_followup_resolution,
        }

    @classmethod
    def from_repo(cls, repo_root: Path) -> "IndicatorEngine":
        return cls(
            _load_json(repo_root / "config" / "indicators.json"),
            _load_json(repo_root / "config" / "indicator_bindings.json"),
        )

    def _periods(
        self, dataset: CandidateDataset, context: IndicatorContext
    ) -> tuple[date, date, date, date]:
        metadata_start = dataset.metadata["period_start"]
        metadata_end = dataset.metadata["period_end"]
        if not isinstance(metadata_start, date) or not isinstance(metadata_end, date):
            raise TypeError("Dataset metadata periods must be normalized dates")
        current_start = context.period_start or metadata_start
        current_end = context.period_end or metadata_end
        if current_start > current_end:
            raise ValueError("period_start cannot be after period_end")
        duration = current_end - current_start
        previous_end = context.previous_period_end or current_start - timedelta(days=1)
        previous_start = context.previous_period_start or previous_end - duration
        if previous_start > previous_end:
            raise ValueError("previous_period_start cannot be after previous_period_end")
        return current_start, current_end, previous_start, previous_end

    def _filter_rows(
        self,
        rows: list[dict[str, Any]],
        sheet: str,
        context: IndicatorContext,
        period_start: date,
        period_end: date,
        *,
        forced_lens: str | None = None,
        waitlist_queue_type: str | None = None,
        filter_waitlist_professional: bool = False,
    ) -> list[dict[str, Any]]:
        activity_field = {
            "DERIVACIONES": "referral_type",
            "CIRUGIAS": "procedure_code",
            "ACTIVIDAD_PROF": "activity_code",
            "LISTA_ESPERA_AMB": "requested_prestation",
        }.get(sheet)
        filtered = []
        for row in rows:
            period = row[
                "snapshot_date" if sheet == "LISTA_ESPERA_AMB" else "period_date"
            ]
            if not period_start <= period <= period_end:
                continue
            if context.service_id and row.get("service_id") != context.service_id:
                continue
            if context.specialty_id and row.get("specialty_id") != context.specialty_id:
                continue
            if (
                context.origin_establishment_code
                and row.get(
                    "origin_deis_code"
                    if sheet == "LISTA_ESPERA_AMB"
                    else "origin_establishment_code"
                )
                != context.origin_establishment_code
            ):
                continue
            if (
                context.activity_code
                and activity_field
                and row.get(activity_field) != context.activity_code
            ):
                continue
            if (
                sheet == "ACTIVIDAD_PROF"
                and context.simulated_profile_key
                and row.get("simulated_profile_key")
                != context.simulated_profile_key
            ):
                continue
            if (
                sheet == "LISTA_ESPERA_AMB"
                and waitlist_queue_type
                and row.get("queue_type") != waitlist_queue_type
            ):
                continue
            if (
                sheet == "LISTA_ESPERA_AMB"
                and filter_waitlist_professional
                and context.simulated_profile_key
                and row.get("professional_profile_id")
                != context.simulated_profile_key
            ):
                continue
            lens = forced_lens or context.professional_lens
            if sheet == "ACTIVIDAD_PROF" and lens and row.get("lens") != lens:
                continue
            filtered.append(row)
        return filtered

    def calculate(
        self,
        indicator_id: str,
        dataset: CandidateDataset,
        context: IndicatorContext | None = None,
    ) -> IndicatorResult:
        context = context or IndicatorContext()
        if indicator_id not in self.indicators:
            raise KeyError(f"Unknown indicator_id '{indicator_id}'")
        indicator = self.indicators[indicator_id]
        binding = self.bindings[indicator_id]
        current_start, current_end, previous_start, previous_end = self._periods(
            dataset, context
        )
        base = {
            "indicator_id": indicator_id,
            "display_name_es": indicator["display_name_es"],
            "unit": indicator["unit"],
            "minimum_valid_n": int(indicator["minimum_valid_n"]),
            "period_start": current_start,
            "period_end": current_end,
            "previous_period_start": previous_start,
            "previous_period_end": previous_end,
            "filters": context.filters_dict(),
            "calculation_basis_es": binding.get("prototype_basis_es"),
        }
        if (
            context.indicator_profile
            and context.indicator_profile
            not in indicator["applicable_indicator_profiles"]
        ):
            return IndicatorResult(
                status="not_applicable",
                value=None,
                prior_value=None,
                numerator=None,
                denominator=None,
                valid_n=0,
                reason_es="No aplica al perfil de indicador seleccionado.",
                reference=self._reference(indicator, None, "not_applicable"),
                **base,
            )
        if binding["availability"] != "active":
            status = binding["availability"]
            return IndicatorResult(
                status=status,
                value=None,
                prior_value=None,
                numerator=None,
                denominator=None,
                valid_n=0,
                reason_es=binding["reason_es"],
                reference=self._reference(indicator, None, status),
                **base,
            )

        sheet = binding["source"]
        if sheet != "VALIDATION_REPORT" and sheet not in dataset.tables:
            return IndicatorResult(
                status="unavailable",
                value=None,
                prior_value=None,
                numerator=None,
                denominator=None,
                valid_n=0,
                reason_es=(
                    "No disponible: la carga compatible 1.1 no contiene "
                    "LISTA_ESPERA_AMB; no se interpreta la ausencia como cero."
                ),
                reference=self._reference(indicator, None, "unavailable"),
                **base,
            )
        source_rows = dataset.tables.get(sheet, []) if sheet != "VALIDATION_REPORT" else []
        forced_lens = self._forced_lens(binding["implementation"])
        waitlist_queue_type = self._waitlist_queue_type(binding["implementation"])
        filter_waitlist_professional = binding["implementation"].startswith(
            "wait_followup"
        )
        current_rows = self._filter_rows(
            source_rows,
            sheet,
            context,
            current_start,
            current_end,
            forced_lens=forced_lens,
            waitlist_queue_type=waitlist_queue_type,
            filter_waitlist_professional=filter_waitlist_professional,
        ) if sheet != "VALIDATION_REPORT" else []
        previous_rows = self._filter_rows(
            source_rows,
            sheet,
            context,
            previous_start,
            previous_end,
            forced_lens=forced_lens,
            waitlist_queue_type=waitlist_queue_type,
            filter_waitlist_professional=filter_waitlist_professional,
        ) if sheet != "VALIDATION_REPORT" else []
        calculator = self._calculators[binding["implementation"]]
        parts = calculator(dataset, current_rows, previous_rows)
        status = self._parts_status(parts, int(indicator["minimum_valid_n"]))
        value = self._display_value(parts.value, indicator["unit"]) if status == "available" else None

        prior_value = None
        if (
            status == "available"
            and binding["implementation"]
            not in {"referral_growth", "quality_accepted", "quality_completeness"}
            and previous_rows
        ):
            prior_parts = calculator(dataset, previous_rows, [])
            if self._parts_status(
                prior_parts, int(indicator["minimum_valid_n"])
            ) == "available":
                prior_value = self._display_value(
                    prior_parts.value, indicator["unit"]
                )
        reason = self._reason(status, parts.valid_n, int(indicator["minimum_valid_n"]))
        return IndicatorResult(
            status=status,
            value=value,
            prior_value=prior_value,
            numerator=parts.numerator,
            denominator=parts.denominator,
            valid_n=parts.valid_n,
            reason_es=reason,
            reference=self._reference(indicator, parts.value, status),
            **base,
        )

    def calculate_all(
        self,
        dataset: CandidateDataset,
        context: IndicatorContext | None = None,
    ) -> list[IndicatorResult]:
        return [
            self.calculate(item["indicator_id"], dataset, context)
            for item in self.catalog["indicators"]
        ]

    @staticmethod
    def _forced_lens(implementation: str) -> str | None:
        if implementation.startswith("prof_clinical"):
            return "clinical"
        if implementation.startswith("prof_surgical"):
            return "surgical"
        return None

    @staticmethod
    def _waitlist_queue_type(implementation: str) -> str | None:
        if implementation.startswith("wait_new"):
            return "new_consultation"
        if implementation.startswith("wait_followup"):
            return "followup_control"
        return None

    @staticmethod
    def _parts_status(parts: CalculationParts, minimum_n: int) -> str:
        if parts.denominator == 0:
            return "zero_denominator"
        if parts.valid_n < minimum_n:
            return "insufficient_n"
        if parts.value is None:
            return "pending_definition"
        return "available"

    def _display_value(self, value: float | int | None, unit: str) -> float | int | None:
        if value is None:
            return None
        rounding = self.binding_contract["rounding"]
        if unit == "count":
            return int(round(value))
        if unit == "percentage":
            return round(float(value), rounding["percentage_decimals"])
        if unit == "days":
            return round(float(value), rounding["days_decimals"])
        return round(float(value), 2)

    @staticmethod
    def _reason(status: str, valid_n: int, minimum_n: int) -> str:
        if status == "available":
            return "Calculado con datos validados del período seleccionado."
        if status == "insufficient_n":
            return (
                f"No disponible: n válido {valid_n} menor que el mínimo "
                f"requerido {minimum_n}."
            )
        if status == "zero_denominator":
            return "No disponible: el denominador validado es cero."
        if status == "pending_definition":
            return "No disponible: falta una definición o insumo aprobado."
        return "No disponible para el contexto seleccionado."

    @staticmethod
    def _reference(
        indicator: dict[str, Any],
        raw_value: float | int | None,
        result_status: str,
    ) -> dict[str, Any]:
        target = indicator["target"]
        applicability = target["applicability"]
        reference_status = "not_evaluated"
        explanation_es = "La referencia no se evalúa mientras el indicador no esté disponible."
        if result_status == "available":
            if target["type"] == "none" or applicability == "not_applicable":
                reference_status = "not_applicable"
                explanation_es = "Indicador descriptivo sin meta de desempeño."
            elif (
                target["value"] is None
                or applicability.startswith("pending")
                or applicability.startswith("deferred")
            ):
                reference_status = "pending_applicability"
                explanation_es = (
                    "Referencia pendiente de validar para HEC y el alcance seleccionado."
                )
            else:
                operator = target["operator"]
                threshold = target["value"]
                comparisons = {
                    ">=": raw_value >= threshold,
                    "<=": raw_value <= threshold,
                    ">": raw_value > threshold,
                    "<": raw_value < threshold,
                    "==": raw_value == threshold,
                }
                if operator not in comparisons:
                    raise ValueError(f"Unsupported target operator '{operator}'")
                reference_status = "met" if comparisons[operator] else "not_met"
                explanation_es = (
                    "Comparación determinística con la referencia aplicable; "
                    "no implica causalidad ni evaluación individual."
                )
        return {
            "type": target["type"],
            "value": target["value"],
            "operator": target["operator"],
            "authority": target["authority"],
            "applicability": applicability,
            "status": reference_status,
            "explanation_es": explanation_es,
        }

    @staticmethod
    def _referrals_count(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        value = len({row["referral_id"] for row in rows})
        return CalculationParts(value, value, None, value)

    @staticmethod
    def _referral_growth(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        previous: list[dict[str, Any]],
    ) -> CalculationParts:
        current = len({row["referral_id"] for row in rows})
        prior = len({row["referral_id"] for row in previous})
        return CalculationParts(
            None if prior == 0 else (current - prior) * 100 / prior,
            current - prior,
            prior,
            current,
        )

    @staticmethod
    def _referral_wait_median(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        values = [float(row["wait_days"]) for row in rows]
        return CalculationParts(
            median(values) if values else None, None, None, len(values)
        )

    @staticmethod
    def _referral_wait_p75(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        values = [float(row["wait_days"]) for row in rows]
        return CalculationParts(
            _percentile(values, 0.75) if values else None,
            None,
            None,
            len(values),
        )

    @staticmethod
    def _referral_no_show_new(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = [
            row for row in rows if row["referral_type"] == "new" and row["scheduled_flag"]
        ]
        return _ratio(sum(row["no_show_flag"] for row in eligible), len(eligible))

    @staticmethod
    def _referral_no_show_followup(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = [
            row
            for row in rows
            if row["referral_type"] == "followup" and row["scheduled_flag"]
        ]
        return _ratio(sum(row["no_show_flag"] for row in eligible), len(eligible))

    @staticmethod
    def _referral_discharge(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = [
            row
            for row in rows
            if row["referral_type"] in {"new", "followup"}
            and row["status"] in {"completed", "discharged"}
        ]
        numerator = sum(
            row["status"] == "discharged" and row["documentation_complete_flag"]
            for row in eligible
        )
        return _ratio(numerator, len(eligible))

    @staticmethod
    def _referral_pertinence(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        assessed = [
            row for row in rows if row["pertinence_assessment"] != "not_assessed"
        ]
        return _ratio(
            sum(row["pertinence_assessment"] == "pertinent" for row in assessed),
            len(assessed),
        )

    @staticmethod
    def _referral_contrareference(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = [row for row in rows if row["status"] == "discharged"]
        return _ratio(
            sum(row["contrareference_flag"] for row in eligible), len(eligible)
        )

    @staticmethod
    def _referral_ges(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        due = [row for row in rows if row["ges_due_flag"]]
        return _ratio(sum(row["ges_met_flag"] for row in due), len(due))

    @staticmethod
    def _referral_teleconsult(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = [row for row in rows if row["referral_type"] == "teleconsult"]
        return _ratio(
            sum(row["teleconsult_timely_closed_flag"] for row in eligible),
            len(eligible),
        )

    @staticmethod
    def _quality_accepted(
        dataset: CandidateDataset,
        _rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        summary = dataset.validation_summary
        return _ratio(summary["accepted_rows"], summary["submitted_rows"])

    @staticmethod
    def _quality_completeness(
        dataset: CandidateDataset,
        _rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        summary = dataset.validation_summary
        accepted = summary["accepted_rows"]
        percentage = summary["critical_field_completeness_pct"]
        numerator = 0 if percentage is None else round(accepted * percentage / 100)
        return _ratio(numerator, accepted)

    @staticmethod
    def _referral_top3_origins(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        counts = Counter(row["origin_establishment_code"] for row in rows)
        numerator = sum(value for _, value in counts.most_common(3))
        return _ratio(numerator, len(rows))

    @staticmethod
    def _surgery_waitlist_open(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        value = len(
            {
                row["surgery_case_id"]
                for row in rows
                if row["status"] == "waitlisted"
            }
        )
        return CalculationParts(value, value, None, value)

    @staticmethod
    def _surgery_wait_p75(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        values = [float(row["wait_days"]) for row in rows]
        return CalculationParts(
            _percentile(values, 0.75) if values else None,
            None,
            None,
            len(values),
        )

    @staticmethod
    def _surgery_elective_completed(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        value = len(
            {
                row["surgery_case_id"]
                for row in rows
                if row["status"] == "completed" and row["elective_major_flag"]
            }
        )
        return CalculationParts(value, value, None, value)

    @staticmethod
    def _surgery_ambulatory(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = [
            row
            for row in rows
            if row["status"] == "completed" and row["elective_major_flag"]
        ]
        return _ratio(sum(row["ambulatory_flag"] for row in eligible), len(eligible))

    @staticmethod
    def _surgery_suspension(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = [
            row
            for row in rows
            if row["scheduled_flag"] and row["elective_major_flag"]
        ]
        return _ratio(sum(row["status"] == "suspended" for row in eligible), len(eligible))

    @staticmethod
    def _prof_clinical_completed(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        value = len(
            {row["activity_id"] for row in rows if row["completed_flag"]}
        )
        return CalculationParts(value, value, None, value)

    @staticmethod
    def _prof_clinical_schedule(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = [row for row in rows if row["scheduled_flag"]]
        return _ratio(sum(row["completed_flag"] for row in eligible), len(eligible))

    @staticmethod
    def _prof_clinical_new_share(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        completed = [row for row in rows if row["completed_flag"]]
        return _ratio(
            sum(row["new_consultation_flag"] for row in completed), len(completed)
        )

    @staticmethod
    def _prof_documentation(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        return _ratio(
            sum(row["documentation_complete_flag"] for row in rows), len(rows)
        )

    @staticmethod
    def _prof_clinical_no_show(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        scheduled = [row for row in rows if row["scheduled_flag"]]
        return _ratio(sum(row["no_show_flag"] for row in scheduled), len(scheduled))

    @staticmethod
    def _prof_surgical_completed(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        value = len(
            {row["activity_id"] for row in rows if row["completed_flag"]}
        )
        return CalculationParts(value, value, None, value)

    @staticmethod
    def _prof_surgical_schedule(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        scheduled = [row for row in rows if row["scheduled_flag"]]
        return _ratio(sum(row["completed_flag"] for row in scheduled), len(scheduled))

    @staticmethod
    def _prof_surgical_ambulatory(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = [
            row for row in rows if row["elective_major_applicable_flag"]
        ]
        return _ratio(
            sum(row["ambulatory_major_flag"] for row in eligible), len(eligible)
        )

    @staticmethod
    def _prof_surgical_suspension(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        scheduled = [row for row in rows if row["scheduled_flag"]]
        return _ratio(sum(row["suspended_flag"] for row in scheduled), len(scheduled))

    @staticmethod
    def _wait_new_open_count(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        value = len(
            {
                row["wait_episode_id"]
                for row in rows
                if row["episode_status"] in {"open_unscheduled", "open_scheduled"}
            }
        )
        return CalculationParts(value, value, None, value)

    @staticmethod
    def _new_open_wait_days(rows: list[dict[str, Any]]) -> list[float]:
        return [
            float((row["snapshot_date"] - row["queue_entry_date"]).days)
            for row in rows
            if row["episode_status"] in {"open_unscheduled", "open_scheduled"}
        ]

    @classmethod
    def _wait_new_median(
        cls,
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        values = cls._new_open_wait_days(rows)
        return CalculationParts(
            median(values) if values else None, None, None, len(values)
        )

    @classmethod
    def _wait_new_p75(
        cls,
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        values = cls._new_open_wait_days(rows)
        return CalculationParts(
            _percentile(values, 0.75) if values else None,
            None,
            None,
            len(values),
        )

    @classmethod
    def _wait_new_over90(
        cls,
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        values = cls._new_open_wait_days(rows)
        return _ratio(sum(value > 90 for value in values), len(values))

    @staticmethod
    def _wait_new_resolution(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        return _ratio(
            sum(row["episode_status"] in {"completed", "exited"} for row in rows),
            len(rows),
        )

    @staticmethod
    def _followup_overdue_open_rows(
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            row
            for row in rows
            if row["control_due_date"] <= row["snapshot_date"]
            and row["episode_status"] in {"open_unscheduled", "open_scheduled"}
        ]

    @classmethod
    def _wait_followup_open_count(
        cls,
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = cls._followup_overdue_open_rows(rows)
        value = len({row["wait_episode_id"] for row in eligible})
        return CalculationParts(value, value, None, value)

    @classmethod
    def _followup_overdue_days(cls, rows: list[dict[str, Any]]) -> list[float]:
        return [
            float((row["snapshot_date"] - row["control_due_date"]).days)
            for row in cls._followup_overdue_open_rows(rows)
        ]

    @classmethod
    def _wait_followup_median(
        cls,
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        values = cls._followup_overdue_days(rows)
        return CalculationParts(
            median(values) if values else None, None, None, len(values)
        )

    @classmethod
    def _wait_followup_p75(
        cls,
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        values = cls._followup_overdue_days(rows)
        return CalculationParts(
            _percentile(values, 0.75) if values else None,
            None,
            None,
            len(values),
        )

    @classmethod
    def _wait_followup_unscheduled(
        cls,
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = cls._followup_overdue_open_rows(rows)
        return _ratio(
            sum(row["episode_status"] == "open_unscheduled" for row in eligible),
            len(eligible),
        )

    @staticmethod
    def _wait_followup_resolution(
        _dataset: CandidateDataset,
        rows: list[dict[str, Any]],
        _previous: list[dict[str, Any]],
    ) -> CalculationParts:
        eligible = [
            row for row in rows if row["control_due_date"] <= row["snapshot_date"]
        ]
        return _ratio(
            sum(row["episode_status"] == "completed" for row in eligible),
            len(eligible),
        )
