"""
R Pipeline Runner Module

This module executes the R inference script and returns results.
All configuration is centralized in config.py.

Legacy Note:
The input_filename parameter is not currently used because step_inference_mini_both.R
uses hardcoded input paths. This parameter is kept for potential future use when the
R script is updated to accept command-line arguments.
"""

import subprocess
import pandas as pd
import os
import sys

# Import configuration from the central config module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    R_EXECUTABLE,
    R_SCRIPT_PATH,
    BASE_DIR,
    OUTPUT_DIR,
    OUTPUT_CSV_PATH,
    FALLBACK_OUTPUT_PATH
)

# R script execution timeout (5 minutes)
R_SCRIPT_TIMEOUT = 300


def run_inference(input_filename=None):
    """
    Runs the R pipeline and returns results as a Python dictionary.

    Args:
        input_filename: Optional CSV filename in inputs/ folder to process.
                       Currently UNUSED because step_inference_mini_both.R does not
                       accept command-line arguments for input files. The R script
                       uses hardcoded paths internally. This parameter is kept for
                       API compatibility and potential future enhancement.

    Returns:
        dict: {"success": True, "data": [...]} on success
              {"success": False, "error": "..."} on failure
    """

    # Note: input_filename is currently ignored - see docstring
    if input_filename:
        print(f"[R Pipeline] Warning: input_filename '{input_filename}' provided but not used. "
              f"R script uses hardcoded input paths.")

    # Validate configuration
    if not R_EXECUTABLE:
        return {
            "success": False,
            "error": "R executable not found. Please install R or set R_EXECUTABLE environment variable."
        }

    if not os.path.exists(R_EXECUTABLE):
        return {
            "success": False,
            "error": f"R executable not found at: {R_EXECUTABLE}"
        }

    if not R_SCRIPT_PATH:
        return {
            "success": False,
            "error": "R script not found. Please ensure Capsico_mini_v2 directory exists or set R_SCRIPT_PATH environment variable."
        }

    if not os.path.exists(R_SCRIPT_PATH):
        return {
            "success": False,
            "error": f"R script not found at: {R_SCRIPT_PATH}"
        }

    # Build command
    cmd = [R_EXECUTABLE, R_SCRIPT_PATH]

    print(f"[R Pipeline] Running: {' '.join(cmd)}")
    print(f"[R Pipeline] Working directory: {os.path.dirname(R_SCRIPT_PATH)}")
    print(f"[R Pipeline] Timeout: {R_SCRIPT_TIMEOUT}s")

    # Inject PROJECT_ROOT so step_inference_mini_both.R can locate pipeline files.
    # plumber.R sets this via Sys.setenv() itself; the direct subprocess path needs it here.
    subprocess_env = os.environ.copy()
    subprocess_env["PROJECT_ROOT"] = os.path.dirname(R_SCRIPT_PATH)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(R_SCRIPT_PATH),
            env=subprocess_env,
            timeout=R_SCRIPT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"R script execution timed out after {R_SCRIPT_TIMEOUT} seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to execute R script: {str(e)}"
        }

    print(f"[R Pipeline] stdout: {result.stdout}")

    if result.returncode != 0:
        print(f"[R Pipeline] stderr: {result.stderr}")
        return {
            "success": False,
            "error": result.stderr or "R script execution failed"
        }

    # Check for output in App/outputs/ first
    output_path = OUTPUT_CSV_PATH
    if not os.path.exists(output_path):
        # Try fallback path
        output_path = FALLBACK_OUTPUT_PATH
        if not output_path or not os.path.exists(output_path):
            return {
                "success": False,
                "error": f"Output CSV not found in {OUTPUT_CSV_PATH}" +
                        (f" or {FALLBACK_OUTPUT_PATH}" if FALLBACK_OUTPUT_PATH else "")
            }

    print(f"[R Pipeline] Reading results from: {output_path}")

    try:
        df = pd.read_csv(output_path)

        # Copy to App/outputs/ if it was in fallback location
        if output_path == FALLBACK_OUTPUT_PATH:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            df.to_csv(OUTPUT_CSV_PATH, index=False)
            print(f"[R Pipeline] Copied results to {OUTPUT_CSV_PATH}")

        return {
            "success": True,
            "data": df.to_dict(orient="records")
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error reading CSV: {str(e)}"
        }