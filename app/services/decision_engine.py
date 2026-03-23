"""
Decision engine for treatment effect classification.

Classifies drugs into decision tiers based on GRF treatment effect estimates
and one-sided confidence intervals.

Decision Rules:
- Tier 1 (Significant Benefit): Tau < 0 AND CI_High < 0
- Tier 2 (Suggestive Benefit): Tau < 0 AND CI_High >= 0
- Tier 3 (No Supported Benefit): Tau >= 0
- Tier Unknown: Missing or invalid Tau data
"""

from typing import List, Dict, Any, Optional, Tuple


def classify_treatments(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Classify treatments into decision tiers based on Tau and CI_High.

    Args:
        data: List of inference result dicts. Each dict must have:
              - Drug: str (e.g., "BB", "RAS", "SP", "LD")
              - Tau_Point: float or None
              - CI_High: float or None

    Returns:
        Decision summary dict with all classification information.
    """
    tier_1 = []  # Tau < 0 AND CI_High < 0 (statistically significant)
    tier_2 = []  # Tau < 0 AND CI_High >= 0 (suggestive but inconclusive)
    tier_3 = []  # Tau >= 0 (no supported benefit)
    tier_unknown = []  # Missing or invalid data

    for drug_row in data:
        drug = drug_row.get("Drug")
        tau = drug_row.get("Tau_Point")
        ci_high = drug_row.get("CI_High")

        entry = {
            "Drug": drug,
            "Tau_Point": tau,
            "CI_High": ci_high,
        }

        # Classification logic - explicit separation of missing data
        if tau is None:
            entry["tier"] = "unknown"
            entry["status"] = "insufficient_data"
            tier_unknown.append(entry)
        elif tau < 0 and ci_high is not None and ci_high < 0:
            entry["tier"] = 1
            entry["status"] = "significant_benefit"
            tier_1.append(entry)
        elif tau < 0:
            entry["tier"] = 2
            entry["status"] = "suggestive_benefit"
            tier_2.append(entry)
        else:
            entry["tier"] = 3
            entry["status"] = "no_supported_benefit"
            tier_3.append(entry)

    # Sort tiers by Tau (most negative = strongest effect = first)
    tier_1.sort(key=lambda x: x.get("Tau_Point") or 0)
    tier_2.sort(key=lambda x: x.get("Tau_Point") or 0)

    # Determine primary recommendation and all decision fields
    decision = _determine_recommendation(tier_1, tier_2, tier_3, tier_unknown)

    return {
        "primary_recommendation": decision["primary"],
        "decision_confidence": decision["confidence"],
        "decision_status": decision["status"],
        "decision_reason": decision["reason"],
        "clinical_message": decision["message"],
        "tier_1_significant": tier_1,
        "tier_2_suggestive": tier_2,
        "tier_3_no_benefit": tier_3,
        "tier_unknown": tier_unknown,
    }


def _determine_recommendation(
    tier_1: List[Dict],
    tier_2: List[Dict],
    tier_3: List[Dict],
    tier_unknown: List[Dict]
) -> Dict[str, Any]:
    """
    Determine primary recommendation, confidence, status, reason, and message.

    Confidence levels:
    - high: at least one drug in Tier 1
    - moderate: no Tier 1, at least one drug in Tier 2
    - low: only Tier 3 drugs (no benefit detected)
    - none: no usable treatment effect data
    """
    total_usable = len(tier_1) + len(tier_2) + len(tier_3)

    # Case: No usable data at all
    if total_usable == 0:
        return {
            "primary": None,
            "confidence": "none",
            "status": "insufficient_data",
            "reason": "No valid treatment effect data available for any drug.",
            "message": "Treatment recommendation cannot be made due to incomplete data.",
        }

    # Case: At least one significant benefit (Tier 1)
    if len(tier_1) >= 1:
        primary = tier_1[0]
        tau_str = f"{primary['Tau_Point']:.4f}"
        ci_str = f"{primary['CI_High']:.4f}"

        if len(tier_1) == 1:
            reason = f"Tau ({tau_str}) is negative and CI_High ({ci_str}) excludes zero."
            message = f"{primary['Drug']} shows statistically significant benefit for this patient."
        else:
            others = ", ".join(d["Drug"] for d in tier_1[1:])
            reason = f"Tau ({tau_str}) is the most negative among significant treatments."
            message = f"{primary['Drug']} shows the strongest significant benefit. {others} also show significant benefit."

        return {
            "primary": primary,
            "confidence": "high",
            "status": "significant_benefit",
            "reason": reason,
            "message": message,
        }

    # Case: No Tier 1, but at least one suggestive benefit (Tier 2)
    if len(tier_2) >= 1:
        primary = tier_2[0]
        tau_str = f"{primary['Tau_Point']:.4f}"
        ci_str = f"{primary['CI_High']:.4f}" if primary['CI_High'] is not None else "N/A"

        reason = f"Tau ({tau_str}) is negative, but CI_High ({ci_str}) includes zero."
        message = f"{primary['Drug']} shows suggestive benefit, but evidence is inconclusive at 90% confidence."

        return {
            "primary": primary,
            "confidence": "moderate",
            "status": "suggestive_benefit",
            "reason": reason,
            "message": message,
        }

    # Case: Only Tier 3 drugs (no benefit detected)
    return {
        "primary": None,
        "confidence": "low",
        "status": "no_supported_benefit",
        "reason": "All drugs have non-negative Tau estimates.",
        "message": "No treatment shows supported benefit based on current estimates.",
    }
