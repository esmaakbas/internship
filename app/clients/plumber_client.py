"""
This module is responsible for communicating with the Plumber inference service.
It sends patient data as a flat JSON payload to the running Plumber API and
returns the inference results as a Python list.
"""

import requests
import logging
import json
from copy import deepcopy
from config import PLUMBER_PREDICT_URL, FLASK_DEBUG

logger = logging.getLogger(__name__)


def _to_primitive(obj):
    """Convert numpy / pandas scalar types to native Python types for JSON."""
    try:
        import numpy as _np
        if isinstance(obj, _np.generic):
            return obj.item()
    except Exception:
        pass
    return obj


def normalize_medication_pairs(payload: dict) -> dict:
    """Return a copy of payload with medication ATC/dose pairs normalized.

    Rules (compat adapter for Plumber input):
    - For each pair (atccode, dose):
      * If ATC is None/empty/"NA"/missing -> set ATC to "" and dose to None.
      * If dose is None/empty/missing -> set ATC to "" and dose to None.
      * If dose present but ATC missing -> clear both and log a warning.
      * Otherwise keep both unchanged.

    This is intentionally conservative and only affects the outgoing Plumber payload.
    """
    med_pairs = [
        ("ace_atccode", "ace_dose"),
        ("arb_atccode", "arb_dose"),
        ("arni_atccode", "arni_dose"),
        ("bb_atccode", "bb_dose"),
        ("mra_atccode", "mra_dose"),
        ("sglt_atccode", "sglt_dose"),
        ("loopd_atccode", "loopd_dose"),
    ]

    out = deepcopy(payload)

    def is_valid_atc(v):
        if v is None:
            return False
        try:
            s = str(v).strip()
        except Exception:
            return False
        if s == "" or s.upper() == "NA":
            return False
        return True

    def is_valid_dose(v):
        if v is None:
            return False
        try:
            s = str(v).strip()
        except Exception:
            return False
        if s == "":
            return False
        return True

    for atc_key, dose_key in med_pairs:
        atc_val = out.get(atc_key)
        dose_val = out.get(dose_key)

        atc_ok = is_valid_atc(atc_val)
        dose_ok = is_valid_dose(dose_val)

        if atc_ok and dose_ok:
            # Normalize numpy types for dose
            out[dose_key] = _to_primitive(dose_val)
            out[atc_key] = _to_primitive(atc_val)
            continue

        # Any invalid component -> clear both and (if dose was provided) warn
        if not atc_ok and dose_ok:
            logger.warning(
                "Incompatible medication pair: %s present without %s; clearing both.",
                dose_key,
                atc_key,
            )

        out[atc_key] = ""
        out[dose_key] = None

    # Ensure remaining values are primitives where possible
    for k, v in list(out.items()):
        out[k] = _to_primitive(v)

    return out


def call_plumber_predict(payload: dict) -> list:
    """
    Send a POST request to the Plumber /predict endpoint and return the results.

    Args:
        payload: A flat dict of patient features. Sent as-is in the request body.
                 Must not be wrapped or modified before calling this function.

    Returns:
        A list of dicts, each representing a drug inference result, e.g.:
        [{"Drug": "BB", "Tau_Point": -0.0032, "CI_Low": -0.0040, "CI_High": 0.0008}]

    Raises:
        RuntimeError: If the HTTP request fails, the server returns a non-200
                      status code, or the response body is not a JSON array.
    """
    # Apply medication-pair compatibility adapter before sending
    adapted_payload = normalize_medication_pairs(payload)

    # Log the exact JSON payload being sent to Plumber for audit/debugging.
    if FLASK_DEBUG:
        try:
            logger.info("Plumber request payload (adapted): %s", json.dumps(adapted_payload, indent=2, ensure_ascii=False))
        except Exception:
            logger.info("Plumber request payload: <unserializable payload>")

    try:
        response = requests.post(PLUMBER_PREDICT_URL, json=adapted_payload, timeout=300)
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Could not connect to Plumber API at {PLUMBER_PREDICT_URL}. "
            f"Ensure the Plumber service is running. Details: {e}"
        ) from e
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"Request to Plumber API timed out after 300 seconds ({PLUMBER_PREDICT_URL})."
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"HTTP request to Plumber API failed: {e}") from e

    if response.status_code != 200:
        raise RuntimeError(
            f"Plumber API returned status {response.status_code} "
            f"for {PLUMBER_PREDICT_URL}. Response: {response.text!r}"
        )

    try:
        result = response.json()
    except ValueError as e:
        raise RuntimeError(
            f"Plumber API response could not be parsed as JSON. "
            f"Raw response: {response.text!r}. Details: {e}"
        ) from e

    # Return the parsed JSON as-is. The caller (inference_service) will
    # defensively handle whether this is a list (expected) or an error dict/string.
    return result
