"""
Patient form parser and validator for the /predict route.

Responsibilities:
- Read raw string values from request.form
- Normalise input (strip whitespace, convert decimal commas to dots)
- Safely parse each field to its correct Python type
- Validate values against clinical plausibility rules
- Return a clean dict of parsed overrides and a list of human-readable errors

Design:
- Empty fields are skipped entirely (no override applied → baseline default is kept)
- Parsing and validation errors are collected and returned together so all
  problems are shown to the user at once, not one at a time
- No exceptions are raised to the caller; all error handling is internal
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Field schema
# Each entry: (field_name, type, min, max, allowed_values)
# min/max are None where not applicable; allowed_values is None for numeric fields.
# ---------------------------------------------------------------------------

_INT_FIELDS: list[tuple[str, int | None, int | None, list[str] | None]] = [
    # (name,        min,  max,  allowed)
    ("age",          18,   110,  None),
    ("sex",           0,     1,  ["0", "1"]),
    ("lvef",          5,    80,  None),
    ("baseline_nyha", 1,     4,  ["1", "2", "3", "4"]),
    ("mh_af",         0,     1,  ["0", "1"]),
    ("mh_ckd",        0,     1,  ["0", "1"]),
    ("mh_dm",         0,     1,  ["0", "1"]),
    ("bb_dose",        0,  None,  None),
    ("arni_dose",      0,  None,  None),
    ("sglt_dose",      0,  None,  None),
    ("mra_dose",       0,  None,  None),
    ("loopd_dose",     0,  None,  None),
]

_FLOAT_FIELDS: list[tuple[str, float | None, float | None]] = [
    # (name,          min,   max)
    ("baseline_bmi",  10.0,  60.0),
    ("baseline_sbp",  60.0, 260.0),
    ("baseline_hr",   30.0, 220.0),
    ("baseline_k",     2.0,   7.5),
]

# Human-readable labels for error messages
_LABELS: dict[str, str] = {
    "age":            "Age",
    "sex":            "Sex",
    "baseline_bmi":   "BMI",
    "baseline_sbp":   "Systolic BP",
    "baseline_hr":    "Heart Rate",
    "baseline_k":     "Potassium",
    "lvef":           "LVEF",
    "baseline_nyha":  "NYHA Class",
    "mh_af":          "Atrial Fibrillation",
    "mh_ckd":         "Chronic Kidney Disease",
    "mh_dm":          "Diabetes Mellitus",
    "bb_dose":        "Beta-Blocker Dose",
    "arni_dose":      "ARNI Dose",
    "sglt_dose":      "SGLT2i Dose",
    "mra_dose":       "MRA Dose",
    "loopd_dose":     "Loop Diuretic Dose",
}


def _normalise(raw: str) -> str:
    """Strip whitespace and convert decimal commas to dots."""
    return raw.strip().replace(",", ".")


def parse_patient_form(form) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    """
    Parse and validate a patient form submission.

    Args:
        form: Flask request.form (ImmutableMultiDict or any mapping of str→str)

    Returns:
        overrides  – dict of successfully parsed field values ready to apply to
                     BASE_PATIENT_PAYLOAD.  Only fields that were non-empty AND
                     valid are included.
        raw_values – dict of raw (string) form values for all supported fields,
                     used to re-populate the form on a failed submission so the
                     user does not lose their input.
        errors     – dict mapping field_name → human-readable error message.
                     Empty dict means the submission is valid.
    """
    overrides: dict[str, Any] = {}
    errors: dict[str, str] = {}

    # --- Collect raw values for all supported fields (for form re-population) ---
    raw_values: dict[str, str] = {}

    # patientid (string, no numeric parsing needed)
    pid_raw = form.get("patientid", "").strip()
    raw_values["patientid"] = pid_raw
    if pid_raw:
        overrides["patientid"] = pid_raw

    # --- Integer fields ---
    for name, vmin, vmax, allowed in _INT_FIELDS:
        raw = form.get(name, "")
        normalised = _normalise(raw)
        raw_values[name] = normalised  # store normalised for re-population

        if not normalised:
            continue  # empty → keep baseline default, no error

        label = _LABELS.get(name, name)

        # Select fields: validate against explicit allowed set
        if allowed is not None:
            if normalised not in allowed:
                errors[name] = f"{label}: invalid selection '{normalised}'."
                continue
            overrides[name] = int(normalised)
            continue

        # Numeric integer fields: must parse cleanly
        try:
            # Accept "5.0" style floats from CSV prefill, truncate to int
            value = int(float(normalised))
        except ValueError:
            errors[name] = f"{label}: must be a whole number (got '{normalised}')."
            continue

        if vmin is not None and value < vmin:
            errors[name] = f"{label}: must be at least {vmin} (got {value})."
            continue
        if vmax is not None and value > vmax:
            errors[name] = f"{label}: must be at most {vmax} (got {value})."
            continue

        overrides[name] = value

    # --- Float fields ---
    for name, vmin, vmax in _FLOAT_FIELDS:
        raw = form.get(name, "")
        normalised = _normalise(raw)
        raw_values[name] = normalised

        if not normalised:
            continue

        label = _LABELS.get(name, name)

        try:
            value = float(normalised)
        except ValueError:
            errors[name] = f"{label}: must be a number (got '{normalised}')."
            continue

        if vmin is not None and value < vmin:
            errors[name] = f"{label}: must be at least {vmin} (got {value})."
            continue
        if vmax is not None and value > vmax:
            errors[name] = f"{label}: must be at most {vmax} (got {value})."
            continue

        overrides[name] = value

    return overrides, raw_values, errors
