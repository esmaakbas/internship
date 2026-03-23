import logging
from r_pipeline_link.r_runner import run_inference
from clients.plumber_client import call_plumber_predict
from services.decision_engine import classify_treatments

logger = logging.getLogger(__name__)


def _sanitise_result_list(result_list: list) -> list:
    """
    Normalise numeric fields in the Plumber response before passing to the UI.

    jsonlite serialises R's -Inf / +Inf as JSON null, which Python's json parser
    maps to None. Jinja2's "%.4f"|format filter raises a TypeError on None, which
    would crash results.html. Replace None with the corresponding Python infinity
    float so the template can always format every cell safely.

    Fields covered: Tau_Point, CI_Low, CI_High.
    Any field not present in a row is left untouched.
    """
    _numeric_fields = ("Tau_Point", "CI_Low", "CI_High")

    sanitised = []
    for row in result_list:
        clean = dict(row)
        # None values (from JSON null / R's -Inf or +Inf) are left as None.
        # The template guards against None with an "is not none" check and
        # renders a readable fallback instead of calling the format filter.
        sanitised.append(clean)
    return sanitised


def _rank_result_list(result_list: list) -> list:
    """
    Order the inference results to match the biostat report ranking logic.

    Rule:
    - BB, RAS, SP are the ranked drugs: sort ascending by Tau_Point
      (most negative = strongest beneficial effect = first).
    - LD is always displayed last, outside the ranking.
    - Any drug not in either group is appended after LD in original order.
    - None Tau_Point values sort to the end of the ranked group.
    """
    _RANKED = {"BB", "RAS", "SP"}
    _LAST = {"LD"}

    ranked = [r for r in result_list if r.get("Drug") in _RANKED]
    last = [r for r in result_list if r.get("Drug") in _LAST]
    other = [r for r in result_list if r.get("Drug") not in _RANKED | _LAST]

    ranked.sort(key=lambda r: (r.get("Tau_Point") is None, r.get("Tau_Point") or 0))

    return ranked + other + last


def _get_alex_guidance(patient_payload: dict, inference_result: dict) -> dict:
    """
    Try to get LLM guidance from Alex's API.

    This function is fail-safe and never raises exceptions. If any error occurs
    (payload mapping, network, API error, etc.), it returns an error structure
    instead of crashing the main inference flow.

    Args:
        patient_payload: The original patient data dict sent to Plumber.
        inference_result: The successful inference result dict with structure:
                          {"success": True, "data": [...]}

    Returns:
        Dict with guidance response or error. Structure matches the normalized
        response from request_guidance():
        {
            "ok": bool,              # True only if guidance succeeded
            "request_id": str,       # Request identifier (or None on error)
            "status": str,           # "ok", "error", etc.
            "answer": str or None,   # LLM response text
            "model": str or None,    # Model name
            "warnings": list,        # API warnings
            "metadata": dict,        # Additional metadata
            "error": dict or None,   # Error details if failed
            "raw": dict              # Full raw response from API
        }
    """
    try:
        # Lazy imports to avoid issues if these modules have problems
        from services.alex_payload_mapper import build_alex_guidance_payload
        from clients.alex_client import request_guidance

        logger.info("Requesting Alex LLM guidance for inference result")

        # Build Alex payload from patient data and inference result
        alex_payload = build_alex_guidance_payload(patient_payload, inference_result)

        # Request guidance from Alex's API
        guidance_response = request_guidance(
            question=alex_payload["question"],
            patient_variables=alex_payload["patient_variables"],
            request_id=alex_payload["request_id"],
            options=alex_payload["options"]
        )

        if guidance_response["ok"]:
            logger.info(f"Alex guidance succeeded (request_id={guidance_response['request_id']})")
        else:
            logger.warning(f"Alex guidance failed: {guidance_response.get('error', {}).get('message', 'Unknown error')}")

        return guidance_response

    except Exception as e:
        # Catch ALL errors (mapping, import, network, etc.) and return error structure
        # This ensures the main inference never fails due to Alex integration
        logger.exception(f"Failed to get Alex guidance: {e}")
        return {
            "ok": False,
            "request_id": None,
            "status": "error",
            "answer": None,
            "model": None,
            "warnings": [],
            "metadata": {},
            "error": {
                "code": "INTEGRATION_ERROR",
                "message": f"Failed to get guidance: {str(e)}",
                "details": {
                    "exception": str(e),
                    "type": type(e).__name__
                }
            },
            "raw": {}
        }


def perform_inference(input_filename=None, input_data=None):
    """
    Business layer for inference.
    Supports two execution paths temporarily:

    - Plumber API path (new): if input_data is a dict, forwards it to the
      running Plumber API via call_plumber_predict and returns the result list.
    - Local R subprocess path (legacy): if input_data is not provided, falls
      back to the old r_runner flow for backward compatibility.

    Args:
        input_filename: Optional CSV filename in inputs/ folder (legacy path).
        input_data: Flat dict of patient features to send to the Plumber API
                    (new path). When provided, the Plumber path takes priority.

    Returns:
        {"success": True, "data": [...]} on success.
        {"success": False, "error": "..."} on failure.
    """

    # New path: forward flat dict payload to the Plumber API
    if isinstance(input_data, dict):
        try:
            result_list = call_plumber_predict(input_data)
            result_list = _sanitise_result_list(result_list)
            result_list = _rank_result_list(result_list)

            # Build the main inference result
            inference_result = {"success": True, "data": result_list}

            # Classify treatments into decision tiers
            decision_summary = classify_treatments(result_list)
            inference_result["decision_summary"] = decision_summary

            # Try to get Alex LLM guidance (non-blocking)
            # If this fails, we still return the successful inference result
            alex_guidance = _get_alex_guidance(input_data, inference_result)
            inference_result["alex_guidance"] = alex_guidance

            return inference_result
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

    # Legacy path: local R subprocess execution via r_runner
    result = run_inference(input_filename)

    if not result["success"]:
        return result

    # burada istersek post-processing yapabiliriz

    return result