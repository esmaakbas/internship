"""
Unit tests for the decision engine.

Tests the classification logic for treatment effects based on Tau and CI_High values.
"""

import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.decision_engine import classify_treatments


def test_standard_case():
    """Test with standard mock data: BB and RAS significant, SP and LD suggestive."""
    data = [
        {"Drug": "BB", "Tau_Point": -0.123, "CI_Low": -0.234, "CI_High": -0.012},
        {"Drug": "RAS", "Tau_Point": -0.098, "CI_Low": -0.187, "CI_High": -0.009},
        {"Drug": "SP", "Tau_Point": -0.056, "CI_Low": -0.145, "CI_High": 0.033},
        {"Drug": "LD", "Tau_Point": -0.023, "CI_Low": -0.112, "CI_High": 0.066},
    ]

    result = classify_treatments(data)

    # Check structure - new fields
    assert "primary_recommendation" in result
    assert "decision_confidence" in result
    assert "decision_status" in result
    assert "decision_reason" in result
    assert "clinical_message" in result
    assert "tier_1_significant" in result
    assert "tier_2_suggestive" in result
    assert "tier_3_no_benefit" in result
    assert "tier_unknown" in result

    # Check classifications
    assert len(result["tier_1_significant"]) == 2  # BB and RAS
    assert len(result["tier_2_suggestive"]) == 2   # SP and LD
    assert len(result["tier_3_no_benefit"]) == 0
    assert len(result["tier_unknown"]) == 0

    # Check primary recommendation
    assert result["primary_recommendation"]["Drug"] == "BB"
    assert result["decision_confidence"] == "high"
    assert result["decision_status"] == "significant_benefit"
    assert "Tau" in result["decision_reason"]  # Reason always mentions Tau

    # Check tier 1 is sorted by Tau
    tier_1_drugs = [d["Drug"] for d in result["tier_1_significant"]]
    assert tier_1_drugs == ["BB", "RAS"]  # BB has more negative Tau

    print("[PASS] test_standard_case passed")
    print(f"  Primary: {result['primary_recommendation']['Drug']}")
    print(f"  Confidence: {result['decision_confidence']}")
    print(f"  Status: {result['decision_status']}")
    print(f"  Reason: {result['decision_reason']}")
    print(f"  Message: {result['clinical_message']}")


def test_no_significant_benefit():
    """Test where no drug has CI_High < 0."""
    data = [
        {"Drug": "BB", "Tau_Point": -0.05, "CI_Low": -0.15, "CI_High": 0.05},
        {"Drug": "RAS", "Tau_Point": -0.03, "CI_Low": -0.12, "CI_High": 0.06},
        {"Drug": "SP", "Tau_Point": -0.02, "CI_Low": -0.10, "CI_High": 0.06},
        {"Drug": "LD", "Tau_Point": 0.01, "CI_Low": -0.08, "CI_High": 0.10},
    ]

    result = classify_treatments(data)

    assert len(result["tier_1_significant"]) == 0
    assert len(result["tier_2_suggestive"]) == 3   # BB, RAS, SP (Tau < 0)
    assert len(result["tier_3_no_benefit"]) == 1   # LD (Tau >= 0)
    assert len(result["tier_unknown"]) == 0

    assert result["decision_confidence"] == "moderate"
    assert result["decision_status"] == "suggestive_benefit"
    assert result["primary_recommendation"]["Drug"] == "BB"

    print("[PASS] test_no_significant_benefit passed")
    print(f"  Primary: {result['primary_recommendation']['Drug']}")
    print(f"  Confidence: {result['decision_confidence']}")
    print(f"  Status: {result['decision_status']}")


def test_no_benefit_at_all():
    """Test where all drugs have Tau >= 0."""
    data = [
        {"Drug": "BB", "Tau_Point": 0.02, "CI_Low": -0.05, "CI_High": 0.09},
        {"Drug": "RAS", "Tau_Point": 0.03, "CI_Low": -0.04, "CI_High": 0.10},
        {"Drug": "SP", "Tau_Point": 0.01, "CI_Low": -0.06, "CI_High": 0.08},
        {"Drug": "LD", "Tau_Point": 0.04, "CI_Low": -0.03, "CI_High": 0.11},
    ]

    result = classify_treatments(data)

    assert len(result["tier_1_significant"]) == 0
    assert len(result["tier_2_suggestive"]) == 0
    assert len(result["tier_3_no_benefit"]) == 4
    assert len(result["tier_unknown"]) == 0

    assert result["decision_confidence"] == "low"
    assert result["decision_status"] == "no_supported_benefit"
    assert result["primary_recommendation"] is None

    print("[PASS] test_no_benefit_at_all passed")
    print(f"  Confidence: {result['decision_confidence']}")
    print(f"  Status: {result['decision_status']}")
    print(f"  Message: {result['clinical_message']}")


def test_missing_data():
    """Test handling of None values - now goes to tier_unknown."""
    data = [
        {"Drug": "BB", "Tau_Point": -0.123, "CI_Low": -0.234, "CI_High": -0.012},
        {"Drug": "RAS", "Tau_Point": None, "CI_Low": None, "CI_High": None},
        {"Drug": "SP", "Tau_Point": -0.056, "CI_Low": -0.145, "CI_High": None},
        {"Drug": "LD", "Tau_Point": -0.023, "CI_Low": -0.112, "CI_High": 0.066},
    ]

    result = classify_treatments(data)

    # BB should be tier 1
    # RAS should be tier_unknown (missing data)
    # SP should be tier 2 (Tau < 0 but CI_High is None, treated as >= 0)
    # LD should be tier 2
    assert len(result["tier_1_significant"]) == 1  # BB
    assert len(result["tier_2_suggestive"]) == 2   # SP and LD
    assert len(result["tier_3_no_benefit"]) == 0
    assert len(result["tier_unknown"]) == 1        # RAS (missing data)

    # Check RAS is in tier_unknown with correct status
    ras_entry = result["tier_unknown"][0]
    assert ras_entry["Drug"] == "RAS"
    assert ras_entry["status"] == "insufficient_data"

    print("[PASS] test_missing_data passed")
    print(f"  Tier Unknown: {[d['Drug'] for d in result['tier_unknown']]}")


def test_empty_data():
    """Test handling of empty data list - should return confidence=none."""
    data = []

    result = classify_treatments(data)

    assert len(result["tier_1_significant"]) == 0
    assert len(result["tier_2_suggestive"]) == 0
    assert len(result["tier_3_no_benefit"]) == 0
    assert len(result["tier_unknown"]) == 0

    assert result["primary_recommendation"] is None
    assert result["decision_confidence"] == "none"
    assert result["decision_status"] == "insufficient_data"

    print("[PASS] test_empty_data passed")
    print(f"  Confidence: {result['decision_confidence']}")
    print(f"  Status: {result['decision_status']}")


def test_all_missing_data():
    """Test where all drugs have missing Tau - confidence should be none."""
    data = [
        {"Drug": "BB", "Tau_Point": None, "CI_Low": None, "CI_High": None},
        {"Drug": "RAS", "Tau_Point": None, "CI_Low": None, "CI_High": None},
    ]

    result = classify_treatments(data)

    assert len(result["tier_unknown"]) == 2
    assert result["decision_confidence"] == "none"
    assert result["decision_status"] == "insufficient_data"

    print("[PASS] test_all_missing_data passed")
    print(f"  Confidence: {result['decision_confidence']}")
    print(f"  Message: {result['clinical_message']}")


def test_single_significant_drug():
    """Test with exactly one drug having significant benefit."""
    data = [
        {"Drug": "BB", "Tau_Point": -0.123, "CI_Low": -0.234, "CI_High": -0.012},
        {"Drug": "RAS", "Tau_Point": -0.098, "CI_Low": -0.187, "CI_High": 0.009},
        {"Drug": "SP", "Tau_Point": -0.056, "CI_Low": -0.145, "CI_High": 0.033},
        {"Drug": "LD", "Tau_Point": 0.023, "CI_Low": -0.112, "CI_High": 0.066},
    ]

    result = classify_treatments(data)

    assert len(result["tier_1_significant"]) == 1
    assert result["tier_1_significant"][0]["Drug"] == "BB"
    assert result["decision_confidence"] == "high"
    assert result["decision_status"] == "significant_benefit"
    assert "statistically significant" in result["clinical_message"]

    print("[PASS] test_single_significant_drug passed")
    print(f"  Message: {result['clinical_message']}")


if __name__ == "__main__":
    print("=" * 60)
    print("Decision Engine Tests")
    print("=" * 60)
    print()

    test_standard_case()
    print()
    test_no_significant_benefit()
    print()
    test_no_benefit_at_all()
    print()
    test_missing_data()
    print()
    test_empty_data()
    print()
    test_all_missing_data()
    print()
    test_single_significant_drug()
    print()

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
