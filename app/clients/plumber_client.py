"""
This module is responsible for communicating with the Plumber inference service.
It sends patient data as a flat JSON payload to the running Plumber API and
returns the inference results as a Python list.
"""

import os
import requests

# Configuration - Use environment variable with fallback to default
PLUMBER_PREDICT_URL = os.getenv("PLUMBER_API_URL", "http://localhost:8000") + "/predict"


def call_plumber_predict(payload: dict) -> list:
    """
    Send a POST request to the Plumber /predict endpoint and return the results.

    Args:
        payload: A flat dict of patient features. Sent as-is in the request body.
                 Must not be wrapped or modified before calling this function.

    Returns:
        A list of dicts, each representing a drug inference result, e.g.:
        [{"Drug": "BB", "Tau_Point": -0.0032, "CI_Low": -0.0040, "CI_High": 0.0008}]

    Raises:
        RuntimeError: If the HTTP request fails, the server returns a non-200
                      status code, or the response body is not a JSON array.
    """
    try:
        response = requests.post(PLUMBER_PREDICT_URL, json=payload, timeout=300)
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Could not connect to Plumber API at {PLUMBER_PREDICT_URL}. "
            f"Ensure the Plumber service is running. Details: {e}"
        ) from e
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"Request to Plumber API timed out after 300 seconds ({PLUMBER_PREDICT_URL})."
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"HTTP request to Plumber API failed: {e}") from e

    if response.status_code != 200:
        raise RuntimeError(
            f"Plumber API returned status {response.status_code} "
            f"for {PLUMBER_PREDICT_URL}. Response: {response.text!r}"
        )

    try:
        result = response.json()
    except ValueError as e:
        raise RuntimeError(
            f"Plumber API response could not be parsed as JSON. "
            f"Raw response: {response.text!r}. Details: {e}"
        ) from e

    if not isinstance(result, list):
        raise RuntimeError(
            f"Plumber API response is not a JSON array. "
            f"Got type '{type(result).__name__}': {result!r}"
        )

    return result
