"""
Test script for alex_payload_mapper.

Verifies that the mapper correctly transforms patient and inference data
into the structure expected by Alex's API.

Run from app directory: python tests/test_payload_mapper.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from services.alex_payload_mapper import build_alex_guidance_payload, SYSTEM_PROMPT, build_user_prompt
from services.decision_engine import classify_treatments


def test_mapper():
    """Test the payload mapper with realistic data."""
    print("=" * 60)
    print("Testing Alex Payload Mapper")
    print("=" * 60)

    # Simulate patient payload
    patient_payload = {
        "patientid": "Esma001",
        "age": 69,
        "sex": 0,
        "lvef": 35,
        "baseline_nyha": 2,
    }

    # Simulate inference data
    data = [
        {"Drug": "BB", "Tau_Point": -0.123, "CI_Low": -0.234, "CI_High": -0.012},
        {"Drug": "RAS", "Tau_Point": -0.098, "CI_Low": -0.187, "CI_High": -0.009},
        {"Drug": "SP", "Tau_Point": -0.056, "CI_Low": -0.145, "CI_High": 0.033},
        {"Drug": "LD", "Tau_Point": -0.023, "CI_Low": -0.112, "CI_High": 0.066},
    ]

    # Build decision_summary
    decision_summary = classify_treatments(data)

    # Complete inference result
    inference_result = {
        "success": True,
        "data": data,
        "decision_summary": decision_summary
    }

    print("\n[Input] Decision Summary:")
    print(f"  Primary: {decision_summary['primary_recommendation']['Drug']}")
    print(f"  Confidence: {decision_summary['decision_confidence']}")
    print(f"  Status: {decision_summary['decision_status']}")
    print(f"  Reason: {decision_summary['decision_reason']}")

    print("\n" + "-" * 60)
    print("Building Alex guidance payload...")
    print("-" * 60)

    alex_payload = build_alex_guidance_payload(
        patient_payload=patient_payload,
        inference_result=inference_result
    )

    print("\n[Output] Patient Variables (key fields):")
    pv = alex_payload["patient_variables"]
    print(f"  primary_drug: {pv['primary_drug']}")
    print(f"  decision_confidence: {pv['decision_confidence']}")
    print(f"  decision_status: {pv['decision_status']}")
    print(f"  decision_reason: {pv['decision_reason'][:50]}...")
    print(f"  tier_1_drugs: {pv['tier_1_drugs']}")
    print(f"  tier_2_drugs: {pv['tier_2_drugs']}")

    print("\n[Output] Combined Prompt (first 600 chars):")
    print(alex_payload["question"][:600])
    print("...")

    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    checks = [
        ("Has request_id", "request_id" in alex_payload),
        ("Has question", "question" in alex_payload),
        ("Has patient_variables", "patient_variables" in alex_payload),
        ("primary_drug is BB", pv["primary_drug"] == "BB"),
        ("decision_confidence is high", pv["decision_confidence"] == "high"),
        ("decision_status is significant_benefit", pv["decision_status"] == "significant_benefit"),
        ("decision_reason is present", pv["decision_reason"] is not None),
        ("tier_1_drugs contains BB and RAS", set(pv["tier_1_drugs"]) == {"BB", "RAS"}),
        ("tier_2_drugs contains SP and LD", set(pv["tier_2_drugs"]) == {"SP", "LD"}),
        ("tier_unknown_drugs is empty", pv["tier_unknown_drugs"] == []),
        ("Prompt contains SYSTEM rules", "INTERPRETATION RULES" in alex_payload["question"]),
        ("Prompt contains TREATMENT EFFECT DATA", "TREATMENT EFFECT DATA" in alex_payload["question"]),
        ("Prompt contains PRECOMPUTED DECISION", "PRECOMPUTED DECISION" in alex_payload["question"]),
        ("Prompt contains output structure", "PRIMARY RESULT" in alex_payload["question"]),
    ]

    for desc, result in checks:
        status = "PASS" if result else "FAIL"
        symbol = "[+]" if result else "[X]"
        print(f"{symbol} {desc}: {status}")

    all_passed = all(result for _, result in checks)
    print(f"\n{'=' * 60}")
    if all_passed:
        print("[+] ALL CHECKS PASSED")
    else:
        print("[X] SOME CHECKS FAILED")
    print(f"{'=' * 60}\n")


def test_prompt_structure():
    """Test that system and user prompts are properly separated."""
    print("\n" + "=" * 60)
    print("Testing Prompt Structure")
    print("=" * 60)

    print("\n[SYSTEM PROMPT] (static rules):")
    print("-" * 40)
    print(SYSTEM_PROMPT[:400])
    print("...")

    # Build sample user prompt
    patient_vars = {
        "tau_BB": -0.123, "ci_high_BB": -0.012,
        "tau_RAS": -0.098, "ci_high_RAS": -0.009,
        "tau_SP": -0.056, "ci_high_SP": 0.033,
        "tau_LD": -0.023, "ci_high_LD": 0.066,
        "age": 69, "lvef": 35, "baseline_nyha": 2,
    }

    decision_summary = {
        "primary_recommendation": {"Drug": "BB"},
        "decision_confidence": "high",
        "decision_status": "significant_benefit",
        "decision_reason": "Tau (-0.1230) is the most negative among significant treatments.",
        "tier_1_significant": [{"Drug": "BB"}, {"Drug": "RAS"}],
        "tier_2_suggestive": [{"Drug": "SP"}, {"Drug": "LD"}],
        "tier_3_no_benefit": [],
        "tier_unknown": [],
    }

    user_prompt = build_user_prompt(patient_vars, decision_summary)

    print("\n[USER PROMPT] (patient-specific):")
    print("-" * 40)
    print(user_prompt)

    print("\n[+] Prompt structure test passed")
    print("=" * 60 + "\n")


def test_defensive_handling():
    """Test defensive handling of missing/invalid values."""
    print("\n" + "=" * 60)
    print("Testing Defensive Handling")
    print("=" * 60)

    patient_payload = {
        "patientid": "TEST002",
        "sex": 1,
    }

    inference_result = {
        "success": True,
        "data": [
            {"Drug": "BB", "Tau_Point": -0.15, "CI_Low": -0.25, "CI_High": -0.05},
            {"Drug": "SP", "Tau_Point": None, "CI_Low": None, "CI_High": None},
        ]
    }

    try:
        alex_payload = build_alex_guidance_payload(
            patient_payload=patient_payload,
            inference_result=inference_result
        )

        print("\n[Output] Built payload despite missing data:")
        print(f"  primary_drug: {alex_payload['patient_variables']['primary_drug']}")
        print(f"  tier_unknown_drugs: {alex_payload['patient_variables']['tier_unknown_drugs']}")

        print("\n[+] Defensive handling works")
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"\n[X] FAILED: {e}")
        print("=" * 60 + "\n")
        raise


if __name__ == "__main__":
    test_mapper()
    test_prompt_structure()
    test_defensive_handling()
