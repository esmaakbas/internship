"""
Client for communicating with Alex's LLM Guidance API.

Provides a simple interface to request guidance/explanations from the external LLM service.
"""

import uuid
import logging
import requests
from typing import Dict, Any, Optional

from config import ALEX_GUIDANCE_URL, ALEX_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


def request_guidance(
    question: str,
    patient_variables: Dict[str, Any],
    request_id: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Request guidance from Alex's LLM API.

    Args:
        question: The question/prompt to send to the LLM
        patient_variables: Dictionary containing patient data (patient_id, age, lvef, baseline_nyha, etc.)
        request_id: Optional request identifier. Generated if not provided.
        options: Optional dictionary of LLM options (use_retrieval, temperature, max_tokens, etc.)

    Returns:
        Normalized response dictionary:
        {
            "ok": bool,              # True if request succeeded
            "request_id": str,       # The request identifier
            "status": str,           # Response status ("ok", "error", etc.)
            "answer": str,           # LLM response text (or None)
            "model": str,            # Model used (or None)
            "warnings": list,        # Any warnings from the API
            "metadata": dict,        # Additional metadata
            "error": dict or None,   # Error details if request failed
            "raw": dict              # Full raw response
        }
    """
    # Generate request_id if not provided
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:12]}"

    # Build default options
    default_options = {
        "use_retrieval": False,
        "use_example_response": False,
        "temperature": 0.2,
        "max_tokens": 260
    }
    if options:
        default_options.update(options)

    # Build request payload
    payload = {
        "request_id": request_id,
        "question": question,
        "patient_variables": patient_variables,
        "options": default_options
    }

    # Initialize normalized response structure
    normalized = {
        "ok": False,
        "request_id": request_id,
        "status": "error",
        "answer": None,
        "model": None,
        "warnings": [],
        "metadata": {},
        "error": None,
        "raw": {}
    }

    try:
        logger.info(f"Requesting guidance from {ALEX_GUIDANCE_URL} (request_id={request_id})")

        # Send POST request
        response = requests.post(
            ALEX_GUIDANCE_URL,
            json=payload,
            timeout=ALEX_TIMEOUT_SECONDS,
            headers={"Content-Type": "application/json"}
        )

        # Try to parse JSON response
        try:
            response_data = response.json()
            normalized["raw"] = response_data
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            normalized["error"] = {
                "code": "INVALID_JSON",
                "message": "Response is not valid JSON",
                "details": {"response_text": response.text[:500]}
            }
            return normalized

        # Handle HTTP errors
        if response.status_code != 200:
            logger.warning(f"Guidance API returned status {response.status_code}")

            # Check if response has error envelope
            if "error" in response_data:
                normalized["error"] = response_data["error"]
            else:
                normalized["error"] = {
                    "code": "HTTP_ERROR",
                    "message": f"HTTP {response.status_code}",
                    "details": response_data
                }
            return normalized

        # HTTP 200 - extract fields
        normalized["status"] = response_data.get("status", "unknown")
        normalized["answer"] = response_data.get("answer")
        normalized["model"] = response_data.get("model")
        normalized["warnings"] = response_data.get("warnings", [])
        normalized["metadata"] = response_data.get("metadata", {})

        # Check if API returned error status despite HTTP 200
        if normalized["status"] != "ok":
            logger.warning(f"API returned HTTP 200 but status={normalized['status']}")
            # Check if response has error envelope
            if "error" in response_data:
                normalized["error"] = response_data["error"]
            else:
                normalized["error"] = {
                    "code": "API_ERROR",
                    "message": f"API returned status: {normalized['status']}",
                    "details": response_data
                }
            return normalized

        # True success - HTTP 200 AND status="ok"
        normalized["ok"] = True

        # Log warnings if present
        if normalized["warnings"]:
            logger.warning(f"Guidance API warnings: {normalized['warnings']}")

        logger.info(f"Guidance request successful (request_id={request_id})")
        return normalized

    except requests.Timeout:
        logger.error(f"Guidance API request timed out after {ALEX_TIMEOUT_SECONDS}s")
        normalized["error"] = {
            "code": "TIMEOUT",
            "message": f"Request timed out after {ALEX_TIMEOUT_SECONDS} seconds",
            "details": {}
        }
        return normalized

    except requests.ConnectionError as e:
        logger.error(f"Failed to connect to guidance API: {e}")
        normalized["error"] = {
            "code": "CONNECTION_ERROR",
            "message": "Failed to connect to guidance API",
            "details": {"exception": str(e)}
        }
        return normalized

    except requests.RequestException as e:
        logger.error(f"Guidance API request failed: {e}")
        normalized["error"] = {
            "code": "REQUEST_ERROR",
            "message": "Request failed",
            "details": {"exception": str(e)}
        }
        return normalized

    except Exception as e:
        logger.exception(f"Unexpected error in request_guidance: {e}")
        normalized["error"] = {
            "code": "UNKNOWN_ERROR",
            "message": "An unexpected error occurred",
            "details": {"exception": str(e)}
        }
        return normalized
