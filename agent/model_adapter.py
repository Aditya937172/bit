from __future__ import annotations

import json
import os
import sys
from typing import Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from BackEnd import apply_scaling, load_medical_ranges, load_model  # noqa: E402
from BackEnd.decoder import decode_disease  # noqa: E402


REFERENCE_RANGES = load_medical_ranges()
FEATURE_ORDER = list(REFERENCE_RANGES.keys())


def get_reference_ranges() -> dict[str, list[float]]:
    return REFERENCE_RANGES


def fill_missing_with_midpoints(values: dict[str, float]) -> dict[str, float]:
    completed = dict(values)
    for feature, (low, high) in REFERENCE_RANGES.items():
        if feature not in completed:
            completed[feature] = round((low + high) / 2, 4)
    return completed


def run_existing_model(patient_values: dict[str, float]) -> dict[str, Any]:
    import numpy as np

    model = load_model()
    scaled = apply_scaling(patient_values)
    probabilities = model.predict_proba(scaled)[0]
    predicted_index = int(np.argmax(probabilities))
    predicted_condition = decode_disease(predicted_index)
    confidence = float(probabilities[predicted_index] * 100.0)

    payload: dict[str, Any] = {
        "model_metadata": {
            "estimator_type": type(model).__name__,
            "classes": [int(class_id) for class_id in getattr(model, "classes_", [])],
            "n_features_in": int(getattr(model, "n_features_in_", len(FEATURE_ORDER))),
            "feature_importances": {
                feature: float(importance)
                for feature, importance in zip(
                    FEATURE_ORDER,
                    getattr(model, "feature_importances_", np.zeros(len(FEATURE_ORDER))),
                )
            },
        },
        "inference": {
            "scaled_input": [float(value) for value in scaled[0]],
            "predicted_class_index": predicted_index,
            "predicted_condition": predicted_condition,
            "confidence": confidence,
            "class_probabilities": [
                {
                    "class_index": int(class_index),
                    "condition": decode_disease(int(class_index)),
                    "probability": float(probability),
                    "probability_percent": float(probability * 100.0),
                }
                for class_index, probability in zip(getattr(model, "classes_", []), probabilities)
            ],
        },
    }

    try:
        import shap

        explainer = shap.TreeExplainer(model, feature_names=FEATURE_ORDER)
        shap_values = explainer.shap_values(scaled)

        if isinstance(shap_values, list):
            class_shap = shap_values[predicted_index][0]
        else:
            values_array = np.array(shap_values)
            if values_array.ndim == 3:
                class_shap = values_array[0, :, predicted_index]
            else:
                class_shap = values_array[0]

        shap_map = {feature: float(value) for feature, value in zip(FEATURE_ORDER, class_shap)}
        top_contributors = sorted(shap_map.items(), key=lambda item: abs(item[1]), reverse=True)[:8]
        payload["explainability"] = {
            "shap_values": shap_map,
            "top_contributors": [
                {"feature": feature, "shap_value": float(value)} for feature, value in top_contributors
            ],
        }
    except Exception as exc:
        payload["explainability"] = {"error": f"SHAP generation failed: {exc}"}

    return payload


def dumps_pretty(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)
