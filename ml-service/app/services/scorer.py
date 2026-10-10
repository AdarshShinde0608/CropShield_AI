from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from math import isfinite
from typing import Any

import numpy as np
from fastapi import HTTPException

from packages.cropshield_core import (
    PIPELINE_CONFIG,
    assess_data_quality,
    build_baseline_evidence,
    build_crop_type_features,
    rain_context_from_z,
)

from app.core.model import ModelRuntime
from app.schemas.scoring import (
    BaselineObservation,
    Evidence,
    ScoreRequest,
    ScoreResponse,
)

_ALLOWED_RISKS = {"normal", "watch", "alert"}
_ALLOWED_SEVERITIES = {"moderate", "high"}


def _to_mapping(model: ModelRuntime) -> tuple[dict[str, Any], Any]:
    if not model.ready or model.card is None:
        raise HTTPException(
            status_code=503,
            detail={"detail": "No verified model is ready", "code": "MODEL_NOT_LOADED"},
        )
    task = model.card.get("task")
    if not isinstance(task, str) or task.strip().lower().replace("_", "-") not in {
        "field-level crop-stress",
        "field-level crop stress",
    }:
        raise HTTPException(
            status_code=503,
            detail={
                "detail": "The active model is not approved for field-level risk scoring",
                "code": "MODEL_MAPPING_UNSUPPORTED",
            },
        )

    input_specification = model.card.get("input_specification")
    feature_names = (
        input_specification.get("feature_names")
        if isinstance(input_specification, Mapping)
        else None
    )
    if (
        not isinstance(feature_names, list)
        or not feature_names
        or any(not isinstance(name, str) for name in feature_names)
        or len(set(feature_names)) != len(feature_names)
    ):
        raise _mapping_error()

    risk_mapping = model.card.get("risk_mapping")
    if not isinstance(risk_mapping, dict):
        raise _mapping_error()
    class_to_risk = risk_mapping.get("class_to_risk")
    confidence = risk_mapping.get("confidence")
    if (
        not isinstance(class_to_risk, dict)
        or not class_to_risk
        or any(
            not isinstance(risk, str) or risk not in _ALLOWED_RISKS
            for risk in class_to_risk.values()
        )
        or not isinstance(confidence, dict)
        or confidence.get("source") != "predict_proba"
        or confidence.get("calibrated") is not True
    ):
        raise _mapping_error()
    cutoffs = confidence.get("cutoffs")
    if (
        not isinstance(cutoffs, dict)
        or not _finite_unit_interval(cutoffs.get("medium"))
        or not _finite_unit_interval(cutoffs.get("high"))
        or cutoffs["medium"] > cutoffs["high"]
    ):
        raise _mapping_error()

    artifact_name = model.card.get("inference_artifact")
    estimator = model.artifacts.get(artifact_name) if isinstance(artifact_name, str) else None
    if estimator is None or not callable(getattr(estimator, "predict", None)):
        raise _mapping_error()
    return risk_mapping, (feature_names, estimator)


def _mapping_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "detail": "The active model card does not define a supported risk mapping",
            "code": "MODEL_MAPPING_UNSUPPORTED",
        },
    )


def _finite_unit_interval(value: object) -> bool:
    return (
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _active_observation_row(observation: Mapping[str, Any]) -> dict[str, object]:
    return {
        "Season": observation["season"],
        **observation["indices"],
        **observation["bands"],
    }


def _verified_baseline_rows(
    rows: Sequence[BaselineObservation],
) -> list[dict[str, object]]:
    return [
        {
            "dos": row.dos,
            "baseline_median": row.baseline_median,
            "baseline_sigma": row.baseline_sigma,
            "baseline_lower": row.baseline_lower,
            "baseline_upper": row.baseline_upper,
        }
        for row in rows
    ]


def _predict(
    estimator: Any,
    features: dict[str, float | int],
    feature_names: list[str],
) -> tuple[str, float, dict[str, float], list[str] | dict[str, float] | None]:
    missing = [name for name in feature_names if name not in features]
    if missing:
        raise _mapping_error()

    matrix = np.asarray([[features[name] for name in feature_names]], dtype=np.float64)
    try:
        prediction = estimator.predict(matrix)
        predicted_class = prediction[0]
        predict_proba = getattr(estimator, "predict_proba", None)
        if not callable(predict_proba):
            raise ValueError("calibrated probability output is unavailable")
        probability_values = np.asarray(predict_proba(matrix), dtype=np.float64)
        classes = getattr(estimator, "classes_", None)
        if probability_values.ndim != 2 or probability_values.shape[0] != 1:
            raise ValueError("model returned an invalid probability shape")
        if classes is None or len(classes) != probability_values.shape[1]:
            raise ValueError("model classes do not match probability output")
        probabilities = {
            str(label): float(probability)
            for label, probability in zip(classes, probability_values[0], strict=True)
        }
        if (
            not probabilities
            or any(not isfinite(value) or not 0.0 <= value <= 1.0 for value in probabilities.values())
            or not np.isclose(sum(probabilities.values()), 1.0, rtol=1e-5, atol=1e-6)
        ):
            raise ValueError("model returned invalid probabilities")
        score = max(probabilities.values())
        if not isfinite(score):
            raise ValueError("model returned an invalid score")
        top_factors: list[str] | dict[str, float] | None = None
        explanation_method = getattr(estimator, "predict_with_explanations", None)
        if callable(explanation_method):
            explanation = explanation_method(matrix)
            if isinstance(explanation, Sequence) and not isinstance(explanation, (str, bytes)):
                explanation = explanation[0] if explanation else None
            if isinstance(explanation, Mapping):
                factors = explanation.get("top_factors")
                if isinstance(factors, dict) and all(
                    isinstance(name, str)
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and isfinite(float(value))
                    for name, value in factors.items()
                ):
                    top_factors = {
                        name: float(value) for name, value in factors.items()
                    }
                elif isinstance(factors, list) and all(
                    isinstance(name, str) for name in factors
                ):
                    top_factors = factors
        return str(predicted_class), score, probabilities, top_factors
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={"detail": "Model inference failed", "code": "INFERENCE_FAILED"},
        ) from error


def _threshold_configuration(risk_mapping: dict[str, Any]) -> dict[str, Any] | None:
    threshold = risk_mapping.get("decision_threshold")
    if threshold is None:
        return None
    if not isinstance(threshold, dict):
        raise _mapping_error()
    required = (
        "score_class",
        "minimum",
        "maximum",
        "default",
        "risk_on_met",
        "risk_on_unmet",
    )
    if any(key not in threshold for key in required):
        raise _mapping_error()
    if (
        not _finite_unit_interval(threshold["minimum"])
        or not _finite_unit_interval(threshold["maximum"])
        or not _finite_unit_interval(threshold["default"])
        or threshold["minimum"] > threshold["maximum"]
        or not float(threshold["minimum"])
        <= float(threshold["default"])
        <= float(threshold["maximum"])
        or not isinstance(threshold["risk_on_met"], str)
        or threshold["risk_on_met"] not in _ALLOWED_RISKS
        or not isinstance(threshold["risk_on_unmet"], str)
        or threshold["risk_on_unmet"] not in _ALLOWED_RISKS
    ):
        raise _mapping_error()
    return threshold


def _is_clear_observation(observation: Mapping[str, Any]) -> bool:
    ndvi = observation["ndvi"]
    valid_frac = observation["valid_frac"]
    return (
        observation["date"] <= date.today()
        and PIPELINE_CONFIG.min_valid_ndvi <= ndvi <= PIPELINE_CONFIG.max_valid_ndvi
        and valid_frac >= PIPELINE_CONFIG.min_valid_frac
        and not observation["low_quality"]
        and not observation["is_interpolated"]
    )


def score_field(
    request: ScoreRequest,
    model: ModelRuntime,
    *,
    model_ready: bool | None = None,
    model_error_code: str | None = None,
) -> ScoreResponse:
    """Gate first, then score one field and attach only observed evidence."""
    observations = [item.model_dump(mode="python") for item in request.observations]
    gate = assess_data_quality(observations, config=PIPELINE_CONFIG)
    baseline_rows = _verified_baseline_rows(request.baseline_observations)
    evidence_result = build_baseline_evidence(
        observations,
        baseline_rows,
        config=PIPELINE_CONFIG,
    )
    evidence = Evidence.model_validate(evidence_result)

    if not gate.assessable:
        latest = max(observations, key=lambda item: item["date"])
        return ScoreResponse(
            field_id=request.field_id,
            risk="cannot_assess",
            severity=None,
            confidence=None,
            confidence_label=None,
            model_score=None,
            top_factors=None,
            evidence=evidence,
            drop_start=evidence_result["drop_start"],
            rain_context=rain_context_from_z(
                latest["rain_z"],
                config=PIPELINE_CONFIG,
            ),
            model_version=None,
            decision_threshold=None,
            cannot_assess_reason=gate.reason,
        )

    if model_ready is False:
        code = model_error_code or "MODEL_NOT_LOADED"
        raise HTTPException(
            status_code=503,
            detail={
                "detail": "No verified active model is ready",
                "code": code,
            },
        )

    latest = max(
        (item for item in observations if _is_clear_observation(item)),
        key=lambda item: item["date"],
    )
    risk_mapping, (feature_names, estimator) = _to_mapping(model)
    feature_values = build_crop_type_features(_active_observation_row(latest))
    predicted_class, model_score, probabilities, top_factors = _predict(
        estimator,
        feature_values,
        feature_names,
    )
    class_to_risk: dict[str, str] = risk_mapping["class_to_risk"]
    if predicted_class not in class_to_risk:
        raise _mapping_error()
    risk = class_to_risk[predicted_class]

    severity_by_risk = risk_mapping.get("severity_by_risk", {})
    severity: str | None = None
    if risk == "alert":
        severity = (
            severity_by_risk.get("alert")
            if isinstance(severity_by_risk, dict)
            else None
        )
        if severity not in _ALLOWED_SEVERITIES:
            raise _mapping_error()

    threshold_configuration = _threshold_configuration(risk_mapping)
    applied_threshold: float | None = None
    if request.decision_threshold is not None:
        if threshold_configuration is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "This model does not support decision-threshold overrides",
                    "code": "VALIDATION_ERROR",
                },
            )
        applied_threshold = min(
            max(
                request.decision_threshold,
                float(threshold_configuration["minimum"]),
            ),
            float(threshold_configuration["maximum"]),
        )
    elif threshold_configuration is not None:
        applied_threshold = float(threshold_configuration["default"])

    if applied_threshold is not None and threshold_configuration is not None:
        score_class = str(threshold_configuration["score_class"])
        score_for_class = probabilities.get(score_class)
        if score_for_class is None:
            raise _mapping_error()
        risk = (
            threshold_configuration["risk_on_met"]
            if score_for_class >= applied_threshold
            else threshold_configuration["risk_on_unmet"]
        )
        severity = None
        if risk == "alert":
            severity = severity_by_risk.get("alert")
            if severity not in _ALLOWED_SEVERITIES:
                raise _mapping_error()

    confidence_config = risk_mapping["confidence"]
    medium_cutoff = float(confidence_config["cutoffs"]["medium"])
    high_cutoff = float(confidence_config["cutoffs"]["high"])
    confidence_label = (
        "high"
        if model_score >= high_cutoff
        else "medium"
        if model_score >= medium_cutoff
        else "low"
    )
    return ScoreResponse(
        field_id=request.field_id,
        risk=risk,
        severity=severity,
        confidence=model_score,
        confidence_label=confidence_label,
        model_score=model_score,
        top_factors=top_factors,
        evidence=evidence,
        drop_start=evidence_result["drop_start"],
        rain_context=rain_context_from_z(
            latest["rain_z"],
            config=PIPELINE_CONFIG,
        ),
        model_version=model.version,
        decision_threshold=applied_threshold,
        cannot_assess_reason=None,
    )
