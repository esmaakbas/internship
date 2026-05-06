"""
Client for communicating with Alex's LLM Guidance API.

Provides a simple interface to request guidance/explanations from the external LLM service.
"""

import uuid
import logging
import json
from datetime import datetime, timezone
import requests
from typing import Dict, Any, Optional
import time

from config import (
    ALEX_TIMEOUT_SECONDS,
    LLM_GUIDANCE_AUTH_EXCHANGE_URL,
    LLM_GUIDANCE_JOBS_URL,
    LLM_GUIDANCE_API_URL,
    LLM_GUIDANCE_TIMEOUT_SECONDS,
)
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


def request_guidance(
    question: str,
    patient_variables: Dict[str, Any],
    request_id: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
    user_context: Optional[Dict[str, Any]] = None,
    auth0_id_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Request guidance from Alex's LLM API.

    Args:
        question: The question/prompt to send to the LLM
        patient_variables: Dictionary containing patient data (patient_id, age, lvef, baseline_nyha, etc.)
        request_id: Optional request identifier. Generated if not provided.
        options: Optional dictionary of LLM options (use_retrieval, temperature, max_tokens, etc.)
        user_context: Authenticated user context from Flask request (g.user)

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

    headers = {"Content-Type": "application/json"}

    # New flow: exchange Auth0 ID token for an LLMGuidance access token
    # auth0_id_token MUST be provided (server-side session value)
    if not auth0_id_token:
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
            "error": {
                "code": "MISSING_AUTH0_ID_TOKEN",
                "message": "Auth0 ID token missing for guidance exchange",
                "details": {},
            },
            "raw": {},
        }
        return normalized

    # Initialize normalized response structure early so error handlers can
    # populate it without causing UnboundLocalError.
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
        # Exchange Auth0 ID token for LLMGuidance access token
        exch_resp = requests.post(
            LLM_GUIDANCE_AUTH_EXCHANGE_URL,
            json={"token": auth0_id_token},
            timeout=LLM_GUIDANCE_TIMEOUT_SECONDS,
            headers={"Content-Type": "application/json"},
        )
        exch_resp.raise_for_status()
        exch_data = exch_resp.json()
        access_token = exch_data.get("access_token")
        if not access_token:
            raise ValueError("No access_token in exchange response")

        # Call guidance jobs endpoint with returned bearer token
        headers["Authorization"] = f"Bearer {access_token}"
    except requests.RequestException as e:
        logger.error("LLMGuidance auth exchange failed: %s", e)
        normalized["error"] = {"code": "EXCHANGE_ERROR", "message": "Failed to exchange auth token", "details": {}}
        return normalized
    except Exception as e:
        logger.error("LLMGuidance exchange parsing failed: %s", e)
        normalized["error"] = {"code": "EXCHANGE_PARSE_ERROR", "message": str(e), "details": {}}
        return normalized

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
        logger.info(f"Requesting guidance from LLMGuidance jobs endpoint (request_id={request_id})")

        # Send POST request to jobs API
        response = requests.post(
            LLM_GUIDANCE_JOBS_URL,
            json=payload,
            timeout=LLM_GUIDANCE_TIMEOUT_SECONDS,
            headers=headers,
        )

        # Try to parse JSON response
        try:
            response_data = response.json()
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            normalized["error"] = {
                "code": "INVALID_JSON",
                "message": "Response is not valid JSON",
                "details": {}
            }
            return normalized

        # Handle HTTP errors
        if not (200 <= response.status_code < 300):
            logger.warning(f"Guidance API returned status {response.status_code}")
            api_error = response_data.get("error") if isinstance(response_data, dict) else None
            api_code = None
            api_message = None
            api_details = {}

            if isinstance(api_error, dict):
                api_code = api_error.get("code")
                api_message = api_error.get("message")
                if isinstance(api_error.get("details"), dict):
                    api_details = api_error.get("details")

            if not api_message and isinstance(response_data, dict):
                api_message = response_data.get("message")

            normalized["error"] = {
                "code": api_code or "HTTP_ERROR",
                "message": api_message or f"Guidance API returned HTTP {response.status_code}",
                "details": {
                    "http_status": response.status_code,
                    "request_id": response_data.get("request_id") if isinstance(response_data, dict) else None,
                    **api_details,
                }
            }
            normalized["raw"] = response_data if isinstance(response_data, dict) else {}
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

        # Handle queued/pending job statuses by polling the status endpoint
        queued_statuses = {"queued", "pending", "in_progress", "processing", "running"}
        success_statuses = {"ok", "success", "completed"}

        if normalized["status"] in queued_statuses:
            logger.info(f"Guidance job queued (request_id={normalized['request_id']}). Will poll for completion.")

            # Prefer an explicit status URL provided by the API
            status_url = None
            if isinstance(response_data, dict):
                status_url = response_data.get("status_url") or payload.get("status_url")

            # If status_url not provided, try to derive from job id
            job_id = None
            if not status_url:
                job_id = response_data.get("job_id") or payload.get("job_id") or response_data.get("id") or payload.get("id")
                if job_id and LLM_GUIDANCE_JOBS_URL:
                    status_url = f"{LLM_GUIDANCE_JOBS_URL.rstrip('/')}/{job_id}"
                    logger.info("Built fallback status URL for polling: %s", status_url)

            if status_url:
                # Normalize status_url: if it's relative or missing port, resolve against configured API URL
                try:
                    parsed = urlparse(status_url)
                    if not parsed.scheme:
                        # relative path -> join with API base
                        status_url = LLM_GUIDANCE_API_URL.rstrip('/') + '/' + status_url.lstrip('/')
                    else:
                        # if hostname matches localhost but lacks port, replace netloc with configured API netloc
                        base_parsed = urlparse(LLM_GUIDANCE_API_URL)
                        if parsed.hostname in (None, 'localhost', '127.0.0.1') and (not parsed.port or parsed.port == base_parsed.port):
                            # rebuild with base netloc
                            status_url = urlunparse((base_parsed.scheme, base_parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
                except Exception:
                    # best-effort only; fall back to provided status_url
                    pass

                logger.info(f"Polling started for guidance job (request_id={normalized['request_id']})")
                poll_interval = 2
                poll_timeout = LLM_GUIDANCE_TIMEOUT_SECONDS or 30
                start_ts = time.time()

                while time.time() - start_ts < poll_timeout:
                    try:
                        poll_resp = requests.get(status_url, headers=headers, timeout=LLM_GUIDANCE_TIMEOUT_SECONDS)
                        if poll_resp.status_code >= 400:
                            logger.warning("Polling received HTTP %s for %s", poll_resp.status_code, status_url)
                            normalized["error"] = {"code": "POLL_HTTP_ERROR", "message": f"Polling returned HTTP {poll_resp.status_code}", "details": {"http_status": poll_resp.status_code}}
                            normalized["raw"] = {"poll_response_status": poll_resp.status_code}
                            return normalized

                        try:
                            poll_data = poll_resp.json()
                        except ValueError:
                            logger.warning("Polling returned non-JSON response for %s", status_url)
                            normalized["error"] = {"code": "POLL_INVALID_JSON", "message": "Polling response is not valid JSON", "details": {}}
                            normalized["raw"] = {"poll_response_text": poll_resp.text}
                            return normalized

                        poll_status = poll_data.get("status")
                        poll_result = poll_data.get("result") if isinstance(poll_data.get("result"), dict) else poll_data

                        if poll_status in success_statuses:
                            normalized["status"] = poll_status
                            normalized["answer"] = poll_result.get("answer")
                            normalized["model"] = poll_result.get("model")
                            normalized["warnings"] = poll_result.get("warnings") or []
                            normalized["metadata"] = poll_result.get("metadata") or {}
                            normalized["verification"] = poll_result.get("verification")
                            rag_items = poll_result.get("retrieved_context") or poll_result.get("rag") or []
                            normalized["rag"] = rag_items if isinstance(rag_items, list) else []
                            normalized["ok"] = True if normalized["answer"] else False
                            normalized["raw"] = poll_data
                            logger.info(f"Polling completed successfully for request_id={normalized['request_id']}")
                            if not normalized["ok"]:
                                normalized["error"] = {"code": "EMPTY_ANSWER", "message": "Guidance completed but no answer provided", "details": {}}
                            return normalized

                        failure_statuses = {"failed", "error", "rejected", "cancelled"}
                        if poll_status in failure_statuses:
                            normalized["status"] = poll_status
                            normalized["error"] = {"code": "JOB_FAILED", "message": "Guidance job failed during polling", "details": {}}
                            normalized["raw"] = poll_data
                            logger.warning(f"Polling detected failed job (request_id={normalized['request_id']}, status={poll_status})")
                            return normalized

                        time.sleep(poll_interval)
                        continue

                    except requests.RequestException as e:
                        logger.warning("Polling request exception: %s", e)
                        normalized["error"] = {"code": "POLL_REQUEST_ERROR", "message": "Polling request failed", "details": {}}
                        return normalized

                logger.warning(f"Polling timed out after {poll_timeout}s for request_id={normalized['request_id']}")
                normalized["error"] = {"code": "POLL_TIMEOUT", "message": f"Polling timed out after {poll_timeout} seconds", "details": {}}
                return normalized

            logger.warning("Guidance API returned queued status but no status_url or job id to poll")
            normalized["error"] = {
                "code": "NO_POLL_ENDPOINT",
                "message": "Guidance queued but no status URL or job id provided by API",
                "details": {}
            }
            normalized["raw"] = response_data
            return normalized

        if not normalized["answer"]:
            normalized["error"] = {
                "code": "EMPTY_ANSWER",
                "message": "Guidance API returned success status but no answer text",
                "details": {}
            }
            return normalized

        # True success - valid status and answer text.
        normalized["ok"] = True
        normalized["raw"] = response_data

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
            "details": {}
        }
        return normalized

    except requests.RequestException as e:
        logger.error(f"Guidance API request failed: {e}")
        normalized["error"] = {
            "code": "REQUEST_ERROR",
            "message": "Guidance API request failed",
            "details": {}
        }
        return normalized

    except Exception as e:
        logger.exception(f"Unexpected error in request_guidance: {e}")
        normalized["error"] = {
            "code": "UNKNOWN_ERROR",
            "message": "An unexpected error occurred",
            "details": {}
        }
        return normalized
