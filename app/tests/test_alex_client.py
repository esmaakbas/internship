"""
Minimal test script for Alex's LLM guidance client.
Run from app directory: python test_alex_client.py
"""

import json
from clients.alex_client import request_guidance


def test_guidance_request():
    """Test a basic guidance request."""
    print("=" * 60)
    print("Testing Alex's Guidance API Client")
    print("=" * 60)

    # Test parameters
    question = "Explain the treatment effect estimates briefly in 3 parts."
    patient_variables = {
        "patient_id": "Esma001",
        "age": 69,
        "lvef": 35,
        "baseline_nyha": 2
    }
    options = {
        "use_retrieval": False,
        "use_example_response": True,
        "temperature": 0.2,
        "max_tokens": 220
    }

    print(f"\nQuestion: {question}")
    print(f"Patient: {patient_variables['patient_id']} (age={patient_variables['age']}, LVEF={patient_variables['lvef']}%)")
    print(f"\nSending request to Alex's API...\n")

    # Make request
    result = request_guidance(
        question=question,
        patient_variables=patient_variables,
        options=options
    )

    # Print results
    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"✓ OK: {result['ok']}")
    print(f"✓ Request ID: {result['request_id']}")
    print(f"✓ Status: {result['status']}")
    print(f"✓ Model: {result['model']}")
    print(f"✓ Error: {result['error']}")
    print(f"✓ Warnings: {result['warnings']}")

    if result['ok'] and result['answer']:
        print(f"\n{'─' * 60}")
        print("ANSWER:")
        print(f"{'─' * 60}")
        print(result['answer'])
        print(f"{'─' * 60}")
    elif result['error']:
        print(f"\n{'─' * 60}")
        print("ERROR DETAILS:")
        print(f"{'─' * 60}")
        print(json.dumps(result['error'], indent=2))
        print(f"{'─' * 60}")

    print(f"\n{'=' * 60}")
    print("VERIFICATION")
    print(f"{'=' * 60}")

    checks = [
        ("✓ result['ok'] is True", result['ok'] is True),
        ("✓ result['answer'] contains text", result['answer'] and len(result['answer']) > 0),
        ("✓ result['error'] is None", result['error'] is None),
    ]

    for check_desc, check_result in checks:
        status = "PASS" if check_result else "FAIL"
        symbol = "✓" if check_result else "✗"
        print(f"{symbol} {check_desc}: {status}")

    all_passed = all(check for _, check in checks)
    print(f"\n{'=' * 60}")
    if all_passed:
        print("✓ ALL CHECKS PASSED")
    else:
        print("✗ SOME CHECKS FAILED")
    print(f"{'=' * 60}\n")

    return result


if __name__ == "__main__":
    test_guidance_request()
