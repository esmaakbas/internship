"""
Payload mapper for Alex's LLM Guidance API.

Transforms our internal patient payload and inference results into the request
structure expected by Alex's /guidance/generate endpoint.
"""

import uuid
from typing import Dict, Any, Optional, List


# System prompt - LLM role and rules (static)
SYSTEM_PROMPT = """You are a clinical decision support assistant. Your role is to EXPLAIN treatment effect estimates that have already been analyzed. You do NOT make new decisions - you explain the precomputed decision.

INTERPRETATION RULES:
- Tau < 0: beneficial effect (negative is good)
- Tau >= 0: no supported benefit
- CI_High < 0: statistically significant at 90% confidence
- CI_High >= 0: inconclusive (confidence interval includes zero)

YOUR TASK:
1. Explain the PRIMARY RESULT (which drug is recommended and why)
2. COMPARE other treatments briefly
3. State UNCERTAINTY clearly for any inconclusive findings

OUTPUT RULES:
- Use the exact numeric values provided
- NEVER claim data is missing if values are shown
- Use hedged language ("suggests", "indicates")
- Stay under 120 words
- Do NOT make clinical recommendations beyond the data"""


def build_user_prompt(
    patient_vars: Dict[str, Any],
    decision_summary: Optional[Dict[str, Any]]
) -> str:
    """
    Build the user prompt with patient-specific data.

    This is separate from the system prompt to maintain clean separation.
    """
    lines = []

    # Section 1: Treatment Effect Data
    lines.append("TREATMENT EFFECT DATA:")
    for drug in ["BB", "RAS", "SP", "LD"]:
        tau = patient_vars.get(f"tau_{drug}")
        ci_high = patient_vars.get(f"ci_high_{drug}")

        if tau is not None:
            tau_str = f"{tau:.4f}"
            ci_str = f"{ci_high:.4f}" if ci_high is not None else "N/A"

            # Get status label from tiers
            status = _get_drug_status(drug, decision_summary)
            lines.append(f"  {drug}: Tau={tau_str}, CI_High={ci_str} [{status}]")
        else:
            lines.append(f"  {drug}: [INSUFFICIENT DATA]")

    lines.append("")

    # Section 2: Precomputed Decision (source of truth)
    lines.append("PRECOMPUTED DECISION (explain this):")
    if decision_summary:
        primary = decision_summary.get("primary_recommendation")
        confidence = decision_summary.get("decision_confidence", "unknown")
        status = decision_summary.get("decision_status", "unknown")
        reason = decision_summary.get("decision_reason", "")

        if primary:
            lines.append(f"  Recommended: {primary.get('Drug')}")
        else:
            lines.append("  Recommended: None")

        lines.append(f"  Confidence: {confidence}")
        lines.append(f"  Status: {status}")
        lines.append(f"  Reason: {reason}")
    else:
        lines.append("  No decision summary available")

    lines.append("")

    # Section 3: Patient Context
    age = patient_vars.get("age")
    lvef = patient_vars.get("lvef")
    nyha = patient_vars.get("baseline_nyha")

    context_parts = []
    if age is not None:
        context_parts.append(f"Age={int(age)}")
    if lvef is not None:
        context_parts.append(f"LVEF={int(lvef)}%")
    if nyha is not None:
        context_parts.append(f"NYHA={int(nyha)}")

    if context_parts:
        lines.append(f"PATIENT: {', '.join(context_parts)}")
        lines.append("")

    # Section 4: Output Instructions
    lines.append("Please explain these results in three parts:")
    lines.append("1. PRIMARY RESULT: State the recommendation and why")
    lines.append("2. COMPARISON: Brief comparison with other drugs")
    lines.append("3. UNCERTAINTY: Note any inconclusive findings")

    return "\n".join(lines)


def _get_drug_status(drug: str, decision_summary: Optional[Dict[str, Any]]) -> str:
    """Get status label for a drug from decision_summary tiers."""
    if not decision_summary:
        return "unknown"

    tier_mapping = [
        ("SIGNIFICANT", "tier_1_significant"),
        ("SUGGESTIVE", "tier_2_suggestive"),
        ("NO BENEFIT", "tier_3_no_benefit"),
        ("INSUFFICIENT DATA", "tier_unknown"),
    ]

    for label, tier_key in tier_mapping:
        tier_list = decision_summary.get(tier_key, [])
        if any(d.get("Drug") == drug for d in tier_list):
            return label

    return "unknown"


def build_alex_guidance_payload(
    patient_payload: Dict[str, Any],
    inference_result: Dict[str, Any],
    request_id: Optional[str] = None,
    question: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build a guidance request payload for Alex's LLM API.

    Args:
        patient_payload: The original patient data dict (as sent to R/Plumber).
        inference_result: The inference result dict returned by perform_inference().
        request_id: Optional request identifier. Auto-generated if not provided.
        question: Optional custom question. If not provided, builds structured prompt.
        options: Optional dict of LLM options (temperature, max_tokens, etc.).

    Returns:
        Dict ready to send to Alex's /guidance/generate endpoint.
    """
    # Validate inference result
    if not inference_result:
        raise ValueError("inference_result cannot be None or empty")

    if not inference_result.get("success"):
        error_msg = inference_result.get("error", "Unknown error")
        raise ValueError(f"Cannot build guidance payload from failed inference: {error_msg}")

    data_list = inference_result.get("data")
    if not isinstance(data_list, list):
        raise ValueError("inference_result['data'] must be a list")

    # Extract decision_summary (may be None for legacy calls)
    decision_summary = inference_result.get("decision_summary")

    # Generate request_id if not provided
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:12]}"

    # Build patient_variables dict
    patient_variables = _build_patient_variables(patient_payload, data_list, decision_summary)

    # Build combined prompt if not provided
    if not question:
        user_prompt = build_user_prompt(patient_variables, decision_summary)
        question = SYSTEM_PROMPT + "\n\n---\n\n" + user_prompt

    # Build default options
    default_options = {
        "use_retrieval": False,
        "use_example_response": False,
        "temperature": 0.2,
        "max_tokens": 260
    }
    if options:
        default_options.update(options)

    return {
        "request_id": request_id,
        "question": question,
        "patient_variables": patient_variables,
        "options": default_options
    }


def _build_patient_variables(
    patient_payload: Dict[str, Any],
    data_list: List[Dict[str, Any]],
    decision_summary: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Extract and transform relevant patient and inference data for Alex's API.
    """
    patient_vars = {}

    # Core patient fields
    patient_vars["patient_id"] = str(patient_payload.get("patientid", "UNKNOWN"))
    patient_vars["age"] = _safe_numeric(patient_payload.get("age"))
    patient_vars["sex"] = _safe_numeric(patient_payload.get("sex"))
    patient_vars["lvef"] = _safe_numeric(patient_payload.get("lvef"))
    patient_vars["baseline_nyha"] = _safe_numeric(patient_payload.get("baseline_nyha"))

    # Treatment effect estimates
    drug_data = {item["Drug"]: item for item in data_list if "Drug" in item}

    for drug_code in ["BB", "RAS", "SP", "LD"]:
        if drug_code in drug_data:
            drug_item = drug_data[drug_code]
            patient_vars[f"tau_{drug_code}"] = _safe_numeric(drug_item.get("Tau_Point"))
            patient_vars[f"ci_low_{drug_code}"] = _safe_numeric(drug_item.get("CI_Low"))
            patient_vars[f"ci_high_{drug_code}"] = _safe_numeric(drug_item.get("CI_High"))
        else:
            patient_vars[f"tau_{drug_code}"] = None
            patient_vars[f"ci_low_{drug_code}"] = None
            patient_vars[f"ci_high_{drug_code}"] = None

    # Decision fields from decision_summary
    if decision_summary:
        primary = decision_summary.get("primary_recommendation")
        patient_vars["primary_drug"] = primary.get("Drug") if primary else None
        patient_vars["decision_confidence"] = decision_summary.get("decision_confidence")
        patient_vars["decision_status"] = decision_summary.get("decision_status")
        patient_vars["decision_reason"] = decision_summary.get("decision_reason")
        patient_vars["clinical_message"] = decision_summary.get("clinical_message")
        patient_vars["tier_1_drugs"] = [d.get("Drug") for d in decision_summary.get("tier_1_significant", [])]
        patient_vars["tier_2_drugs"] = [d.get("Drug") for d in decision_summary.get("tier_2_suggestive", [])]
        patient_vars["tier_3_drugs"] = [d.get("Drug") for d in decision_summary.get("tier_3_no_benefit", [])]
        patient_vars["tier_unknown_drugs"] = [d.get("Drug") for d in decision_summary.get("tier_unknown", [])]
    else:
        # Legacy fallback
        best_drug = None
        for idx, item in enumerate(data_list):
            drug = item.get("Drug")
            if idx == 0 and drug in ["BB", "RAS", "SP"]:
                best_drug = drug
                break
        patient_vars["primary_drug"] = best_drug
        patient_vars["decision_confidence"] = None
        patient_vars["decision_status"] = None
        patient_vars["decision_reason"] = None
        patient_vars["clinical_message"] = None
        patient_vars["tier_1_drugs"] = []
        patient_vars["tier_2_drugs"] = []
        patient_vars["tier_3_drugs"] = []
        patient_vars["tier_unknown_drugs"] = []

    return patient_vars


def _safe_numeric(value: Any) -> Optional[float]:
    """Convert a value to float, handling None, NaN, inf gracefully."""
    if value is None:
        return None

    try:
        num = float(value)
        if not (-float('inf') < num < float('inf')):
            return None
        if num != num:  # NaN check
            return None
        return num
    except (ValueError, TypeError):
        return None
