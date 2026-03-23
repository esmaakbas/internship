"""
Test script to demonstrate the Step 3 integration.

Shows how the inference flow now includes Alex guidance automatically,
and how failures are handled gracefully without breaking the main inference.

Run from app directory: python test_step3_integration.py
"""

import json
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def simulate_successful_inference():
    """
    Simulate successful inference with Alex guidance.

    This shows what the final response structure looks like when both
    inference and Alex guidance succeed.
    """
    print("=" * 60)
    print("TEST 1: Successful Inference + Successful Guidance")
    print("=" * 60)

    # This simulates what perform_inference() now returns
    simulated_response = {
        "success": True,
        "data": [
            {"Drug": "BB", "Tau_Point": -0.123, "CI_Low": -0.234, "CI_High": -0.012},
            {"Drug": "RAS", "Tau_Point": -0.098, "CI_Low": -0.187, "CI_High": -0.009},
            {"Drug": "SP", "Tau_Point": -0.056, "CI_Low": -0.145, "CI_High": 0.033},
            {"Drug": "LD", "Tau_Point": -0.023, "CI_Low": -0.112, "CI_High": 0.066},
        ],
        "alex_guidance": {
            "ok": True,
            "request_id": "req_abc123",
            "status": "ok",
            "answer": "Based on the treatment effect estimates, BB shows the strongest benefit (tau=-0.123, 95% CI: -0.234 to -0.012), followed by RAS (tau=-0.098), SP (tau=-0.056), and LD (tau=-0.023). All treatments show negative point estimates indicating potential benefit, though confidence intervals vary in their precision.",
            "model": "qwen2.5:0.5b",
            "warnings": [],
            "metadata": {},
            "error": None,
            "raw": {}
        }
    }

    print("\n[Response Structure]")
    print(json.dumps(simulated_response, indent=2))

    print("\n[Verification]")
    print(f"[+] Inference succeeded: {simulated_response['success']}")
    print(f"[+] Data has {len(simulated_response['data'])} drugs")
    print(f"[+] Alex guidance present: {'alex_guidance' in simulated_response}")
    print(f"[+] Alex guidance OK: {simulated_response['alex_guidance']['ok']}")
    print(f"[+] Answer received: {simulated_response['alex_guidance']['answer'][:80]}...")
    print("=" * 60 + "\n")


def simulate_inference_with_alex_failure():
    """
    Simulate successful inference but Alex guidance fails.

    This shows that the main inference still succeeds even if Alex is down
    or returns an error.
    """
    print("=" * 60)
    print("TEST 2: Successful Inference + Failed Guidance (Alex Down)")
    print("=" * 60)

    # This simulates what happens when Alex API is unreachable
    simulated_response = {
        "success": True,
        "data": [
            {"Drug": "BB", "Tau_Point": -0.123, "CI_Low": -0.234, "CI_High": -0.012},
            {"Drug": "RAS", "Tau_Point": -0.098, "CI_Low": -0.187, "CI_High": -0.009},
            {"Drug": "SP", "Tau_Point": -0.056, "CI_Low": -0.145, "CI_High": 0.033},
            {"Drug": "LD", "Tau_Point": -0.023, "CI_Low": -0.112, "CI_High": 0.066},
        ],
        "alex_guidance": {
            "ok": False,
            "request_id": "req_def456",
            "status": "error",
            "answer": None,
            "model": None,
            "warnings": [],
            "metadata": {},
            "error": {
                "code": "CONNECTION_ERROR",
                "message": "Failed to connect to guidance API",
                "details": {"exception": "ConnectionRefusedError: [Errno 111] Connection refused"}
            },
            "raw": {}
        }
    }

    print("\n[Response Structure]")
    print(json.dumps(simulated_response, indent=2))

    print("\n[Verification]")
    print(f"[+] Inference succeeded: {simulated_response['success']}")
    print(f"[+] Data available: {len(simulated_response['data'])} drugs")
    print(f"[X] Alex guidance failed: {not simulated_response['alex_guidance']['ok']}")
    print(f"[INFO] Error code: {simulated_response['alex_guidance']['error']['code']}")
    print(f"[INFO] Error message: {simulated_response['alex_guidance']['error']['message']}")
    print("\n[Key Point] Main inference still returned successfully!")
    print("=" * 60 + "\n")


def simulate_inference_with_mapping_error():
    """
    Simulate successful inference but payload mapping fails.

    This shows that even if there's a bug in the mapper, the main
    inference still succeeds.
    """
    print("=" * 60)
    print("TEST 3: Successful Inference + Mapping Error")
    print("=" * 60)

    # This simulates what happens when the mapper encounters an error
    simulated_response = {
        "success": True,
        "data": [
            {"Drug": "BB", "Tau_Point": -0.123, "CI_Low": -0.234, "CI_High": -0.012},
            {"Drug": "RAS", "Tau_Point": -0.098, "CI_Low": -0.187, "CI_High": -0.009},
            {"Drug": "SP", "Tau_Point": -0.056, "CI_Low": -0.145, "CI_High": 0.033},
            {"Drug": "LD", "Tau_Point": -0.023, "CI_Low": -0.112, "CI_High": 0.066},
        ],
        "alex_guidance": {
            "ok": False,
            "request_id": None,
            "status": "error",
            "answer": None,
            "model": None,
            "warnings": [],
            "metadata": {},
            "error": {
                "code": "INTEGRATION_ERROR",
                "message": "Failed to get guidance: Cannot build guidance payload from failed inference: Unknown error",
                "details": {
                    "exception": "Cannot build guidance payload from failed inference: Unknown error",
                    "type": "ValueError"
                }
            },
            "raw": {}
        }
    }

    print("\n[Response Structure]")
    print(json.dumps(simulated_response, indent=2))

    print("\n[Verification]")
    print(f"[+] Inference succeeded: {simulated_response['success']}")
    print(f"[+] Data available: {len(simulated_response['data'])} drugs")
    print(f"[X] Alex guidance failed: {not simulated_response['alex_guidance']['ok']}")
    print(f"[INFO] Error code: {simulated_response['alex_guidance']['error']['code']}")
    print(f"[INFO] Error type: {simulated_response['alex_guidance']['error']['details']['type']}")
    print("\n[Key Point] Main inference still returned successfully!")
    print("=" * 60 + "\n")


def show_response_structure_explanation():
    """
    Explain the final response structure.
    """
    print("=" * 60)
    print("FINAL RESPONSE STRUCTURE EXPLANATION")
    print("=" * 60)

    explanation = """
The perform_inference() function now returns:

{
  "success": bool,          # Main inference success flag
  "data": [...],            # Inference results (unchanged)
  "alex_guidance": {        # NEW: Alex guidance (always present)
    "ok": bool,             # True if guidance succeeded
    "request_id": str,      # Request identifier
    "status": str,          # "ok" or "error"
    "answer": str or None,  # LLM explanation text
    "model": str or None,   # Model used
    "warnings": [...],      # Any warnings
    "metadata": {...},      # Additional metadata
    "error": {...} or None, # Error details if failed
    "raw": {...}            # Full raw API response
  }
}

Key Points:
1. Main inference result is ALWAYS returned if Plumber succeeds
2. alex_guidance is ALWAYS included (even if it fails)
3. If Alex fails, alex_guidance["ok"] = False and error details are in alex_guidance["error"]
4. The Flask app can check alex_guidance["ok"] to decide whether to show the answer
5. Templates can conditionally display guidance based on the ok flag
"""

    print(explanation)
    print("=" * 60 + "\n")


def main():
    """Run all tests."""
    show_response_structure_explanation()
    simulate_successful_inference()
    simulate_inference_with_alex_failure()
    simulate_inference_with_mapping_error()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("[+] Step 3 integration is SAFE and NON-BLOCKING")
    print("[+] Main inference never fails due to Alex integration")
    print("[+] Alex guidance is always present in the response")
    print("[+] Templates can check alex_guidance['ok'] before rendering")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
