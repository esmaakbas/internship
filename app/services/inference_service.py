from r_pipeline_link.r_runner import run_inference
from clients.plumber_client import call_plumber_predict


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
            return {"success": True, "data": result_list}
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

    # Legacy path: local R subprocess execution via r_runner
    result = run_inference(input_filename)

    if not result["success"]:
        return result

    # burada istersek post-processing yapabiliriz

    return result