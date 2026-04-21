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
# Each entry: (field_name, min, max, allowed_values)
# min/max are None where not applicable; allowed_values is None for numeric fields.
# ---------------------------------------------------------------------------

_INT_FIELDS: list[tuple[str, int | None, int | None, list[str] | None]] = [
    # Patient info
    ("age",                  18,   110,  None),
    ("sex",                   0,     1,  ["0", "1"]),

    # Cardiac function
    ("lvef",                  5,    80,  None),
    ("baseline_nyha",         1,     4,  ["1", "2", "3", "4"]),
    ("baseline_ischaemic",    0,     1,  ["0", "1"]),
    ("baseline_qrs",         60,   250,  None),
    ("PM_Rhythm_ECG",         0,     1,  ["0", "1"]),
    ("EP_HF_encoded",         0,     1,  ["0", "1"]),

    # Physical examination
    ("baseline_orthopnea",    0,     1,  ["0", "1"]),
    ("baseline_rales",        0,     1,  ["0", "1"]),
    ("baseline_jdv",          0,     1,  ["0", "1"]),
    ("baseline_edema",        0,     1,  ["0", "1"]),

    # Medical history (boolean flags)
    ("mh_af",                 0,     1,  ["0", "1"]),
    ("mh_ckd",                0,     1,  ["0", "1"]),
    ("mh_dm",                 0,     1,  ["0", "1"]),
    ("mh_hypertension",       0,     1,  ["0", "1"]),
    ("mh_mi",                 0,     1,  ["0", "1"]),
    ("mh_agina",              0,     1,  ["0", "1"]),
    ("mh_cabg",               0,     1,  ["0", "1"]),
    ("mh_vavhd",              0,     1,  ["0", "1"]),
    ("mh_stroke",             0,     1,  ["0", "1"]),
    ("mh_bbb",                0,     1,  ["0", "1"]),
    ("mh_impl_dev",           0,     1,  ["0", "1"]),
    ("mh_copd",               0,     1,  ["0", "1"]),
    ("mh_hept",               0,     1,  ["0", "1"]),
    ("mh_smoke",              0,     2,  ["0", "1", "2"]),
    ("aspirin",               0,     1,  ["0", "1"]),

    # Lab values (integer)
    ("baseline_na",         110,   170,  None),
    ("baseline_chol",        50,   500,  None),
    ("baseline_urea",         5,   200,  None),
    ("baseline_ntbnp",        0, 50000,  None),
    ("baseline_gdf15",        0, 20000,  None),
    ("baseline_tf",         100,   500,  None),

    # Visit info
    ("visit_time_days",       0,  None,  None),
    ("time_from_last_medication", 0, None, None),

    # Previous medication doses (percentage)
    ("DoseBB_prev",           0,   100,  None),
    ("RASDose_prev",          0,   100,  None),
    ("DoseSpiro_prev",        0,   100,  None),
]

_FLOAT_FIELDS: list[tuple[str, float | None, float | None]] = [
    # Vital signs
    ("baseline_bmi",        10.0,   60.0),
    ("baseline_sbp",        60.0,  260.0),
    ("baseline_dpb",        30.0,  150.0),
    ("baseline_hr",         30.0,  220.0),
    ("baseline_bw",         30.0,  300.0),

    # Lab values (float)
    ("baseline_k",           2.0,    7.5),
    ("baseline_creat",       0.1,   15.0),
    ("baseline_hb",          5.0,   20.0),
    ("baseline_hct",        15.0,   65.0),
    ("baseline_cys",         0.3,    5.0),
    ("baseline_crp",         0.0,  300.0),
    ("baseline_il6",         0.0,  500.0),
    ("baseline_hb_a1c",      3.0,   15.0),
    ("baseline_hscnt",       0.0,  500.0),
    ("baseline_ft",          0.0,  500.0),

    # Current medication doses
    ("bb_dose",              0.0,  None),
    ("arni_dose",            0.0,  None),
    ("sglt_dose",            0.0,  None),
    ("mra_dose",             0.0,  None),
    ("loopd_dose",           0.0,  None),
    ("ace_dose",             0.0,  None),
    ("arb_dose",             0.0,  None),

    # Previous medication doses (mg)
    ("Loop_dose_prev",       0.0,  None),
    ("SGLT2Dose_prev",       0.0,  None),
    ("ARNIDose_prev",        0.0,  None),
]

# Human-readable labels for error messages
_LABELS: dict[str, str] = {
    # Patient info
    "age":                    "Age",
    "sex":                    "Sex",

    # Vital signs
    "baseline_bmi":           "BMI",
    "baseline_sbp":           "Systolic BP",
    "baseline_dpb":           "Diastolic BP",
    "baseline_hr":            "Heart Rate",
    "baseline_bw":            "Body Weight",

    # Cardiac function
    "lvef":                   "LVEF",
    "baseline_nyha":          "NYHA Class",
    "baseline_ischaemic":     "Ischaemic Etiology",
    "baseline_qrs":           "QRS Duration",
    "PM_Rhythm_ECG":          "Pacemaker Rhythm",
    "EP_HF_encoded":          "EP/HF Encoded",

    # Physical examination
    "baseline_orthopnea":     "Orthopnea",
    "baseline_rales":         "Rales",
    "baseline_jdv":           "JVD",
    "baseline_edema":         "Peripheral Edema",

    # Medical history
    "mh_af":                  "Atrial Fibrillation",
    "mh_ckd":                 "Chronic Kidney Disease",
    "mh_dm":                  "Diabetes Mellitus",
    "mh_hypertension":        "Hypertension",
    "mh_mi":                  "Myocardial Infarction",
    "mh_agina":               "Angina",
    "mh_cabg":                "CABG",
    "mh_vavhd":               "Valvular Heart Disease",
    "mh_stroke":              "Stroke",
    "mh_bbb":                 "Bundle Branch Block",
    "mh_impl_dev":            "Implantable Device",
    "mh_copd":                "COPD",
    "mh_hept":                "Hepatic Disease",
    "mh_smoke":               "Smoking Status",
    "aspirin":                "Aspirin Use",

    # Lab values
    "baseline_k":             "Potassium",
    "baseline_na":            "Sodium",
    "baseline_creat":         "Creatinine",
    "baseline_urea":          "Urea",
    "baseline_hb":            "Hemoglobin",
    "baseline_hct":           "Hematocrit",
    "baseline_ntbnp":         "NT-proBNP",
    "baseline_cys":           "Cystatin C",
    "baseline_crp":           "CRP",
    "baseline_gdf15":         "GDF-15",
    "baseline_hscnt":         "hs-cTnT",
    "baseline_il6":           "IL-6",
    "baseline_chol":          "Cholesterol",
    "baseline_hb_a1c":        "HbA1c",
    "baseline_tf":            "Transferrin",
    "baseline_ft":            "Free Testosterone",

    # Current medications
    "bb_dose":                "Beta-Blocker Dose",
    "arni_dose":              "ARNI Dose",
    "sglt_dose":              "SGLT2i Dose",
    "mra_dose":               "MRA Dose",
    "loopd_dose":             "Loop Diuretic Dose",
    "ace_dose":               "ACE Inhibitor Dose",
    "arb_dose":               "ARB Dose",

    # Previous medications
    "DoseBB_prev":            "Previous BB Dose %",
    "RASDose_prev":           "Previous RAS Dose %",
    "DoseSpiro_prev":         "Previous Spiro Dose %",
    "Loop_dose_prev":         "Previous Loop Dose",
    "SGLT2Dose_prev":         "Previous SGLT2i Dose",
    "ARNIDose_prev":          "Previous ARNI Dose",

    # Visit info
    "visit_time_days":        "Days Since Initial Visit",
    "time_from_last_medication": "Days Since Last Med Change",
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
