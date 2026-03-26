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
            "ok": bool,                 # True if request succeeded with an answer
            "request_id": str,          # The request identifier
            "status": str,              # Response status ("ok", "queued", "failed", etc.)
            "answer": str,              # LLM response text (or None)
            "model": str,               # Model used (or None)
            "warnings": list,           # Any warnings from the API
            "metadata": dict,           # Additional metadata
            "verification": dict|None,  # Optional verification verdict/details
            "rag": list,                # Retrieved context snippets when available
            "error": dict or None,      # Error details if request failed
            "raw": dict                 # Full raw response
        }
    """
    # Generate request_id if not provided
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:12]}"

    # Build default options
    default_options = {
        "use_retrieval": True,
        "retrieval_mode": "hybrid",
        "pipeline_variant": "drug_dosing",
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
        "verification": None,
        "rag": [],
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
        if not (200 <= response.status_code < 300):
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

        # Extract payload from either direct response or nested job result.
        payload = response_data
        job_status = response_data.get("status") if isinstance(response_data, dict) else None
        if isinstance(response_data, dict) and isinstance(response_data.get("result"), dict):
            payload = response_data["result"]

        normalized["request_id"] = (
            payload.get("request_id")
            or response_data.get("request_id")
            or request_id
        )
        normalized["status"] = payload.get("status") or job_status or "unknown"
        normalized["answer"] = payload.get("answer")
        normalized["model"] = payload.get("model")

        warnings = payload.get("warnings") or response_data.get("warnings") or []
        normalized["warnings"] = warnings if isinstance(warnings, list) else [str(warnings)]
        normalized["metadata"] = payload.get("metadata") or response_data.get("metadata") or {}
        normalized["verification"] = payload.get("verification") or response_data.get("verification")

        rag_items = payload.get("retrieved_context")
        if rag_items is None:
            rag_items = payload.get("rag")
        if rag_items is None:
            rag_items = response_data.get("rag", [])
        normalized["rag"] = rag_items if isinstance(rag_items, list) else []

        # Success requires a known success status and an answer payload.
        success_statuses = {"ok", "success", "completed"}
        if normalized["status"] not in success_statuses:
            logger.warning(f"API returned HTTP {response.status_code} but status={normalized['status']}")
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

        if not normalized["answer"]:
            normalized["error"] = {
                "code": "EMPTY_ANSWER",
                "message": "API returned success status but no answer text",
                "details": response_data
            }
            return normalized

        # True success - valid status and answer text.
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
