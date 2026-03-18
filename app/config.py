"""
Configuration module for the App project.
Centralizes all configuration settings with support for environment variables.

Optional: Install python-dotenv to load settings from a .env file:
    pip install python-dotenv
"""

import os
import glob

# Try to load .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    # Load .env file from the project root
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"[Config] Loaded environment variables from: {env_path}")
except ImportError:
    # python-dotenv not installed, use system environment variables only
    pass


def _find_r_executable():
    """
    Auto-detect R installation on Windows.
    Returns path to Rscript.exe or None if not found.
    """
    r_base_paths = [
        r"C:\Program Files\R",
        r"C:\Program Files (x86)\R",
        os.path.expanduser(r"~\AppData\Local\Programs\R"),
    ]

    for base_path in r_base_paths:
        if os.path.exists(base_path):
            r_versions = glob.glob(os.path.join(base_path, "R-*"))
            if r_versions:
                r_versions.sort(reverse=True)
                for r_version in r_versions:
                    rscript_path = os.path.join(r_version, "bin", "x64", "Rscript.exe")
                    if os.path.exists(rscript_path):
                        return rscript_path
                    rscript_path = os.path.join(r_version, "bin", "Rscript.exe")
                    if os.path.exists(rscript_path):
                        return rscript_path
    return None


def _find_r_script():
    """
    Auto-detect the R script path.
    Searches for Capsico_mini_v2 directory relative to the App directory.
    """
    # config.py is in the App directory
    app_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(app_dir)

    search_paths = [
        os.path.join(parent_dir, "Capsico_mini_v2", "step_inference_mini_both.R"),
        os.path.join(app_dir, "..", "Capsico_mini_v2", "step_inference_mini_both.R"),
    ]

    for path in search_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            return abs_path

    return None


# Project directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "inputs")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# R Configuration
R_EXECUTABLE = os.getenv("R_EXECUTABLE") or _find_r_executable()
R_SCRIPT_PATH = os.getenv("R_SCRIPT_PATH") or _find_r_script()

# Output paths for R pipeline
OUTPUT_CSV_PATH = os.path.join(OUTPUT_DIR, "inference_results_summary.csv")

# Fallback output path (in Capsico_mini_v2/redcap_data/)
if R_SCRIPT_PATH:
    capsico_dir = os.path.dirname(R_SCRIPT_PATH)
    FALLBACK_OUTPUT_PATH = os.path.join(capsico_dir, "redcap_data", "inference_results_summary.csv")
else:
    FALLBACK_OUTPUT_PATH = None

# Plumber API Configuration
PLUMBER_API_URL = os.getenv("PLUMBER_API_URL", "http://localhost:8000")
PLUMBER_PREDICT_URL = f"{PLUMBER_API_URL}/predict"

# Flask Configuration
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "capsico_inference_secret_key_2026")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
FLASK_PORT = int(os.getenv("FLASK_PORT", "8080"))
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")

# Upload Configuration
ALLOWED_EXTENSIONS = {"csv"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB


def print_config():
    """Print current configuration for debugging"""
    print("\n" + "=" * 60)
    print("CONFIGURATION")
    print("=" * 60)
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"R_EXECUTABLE: {R_EXECUTABLE or 'NOT FOUND'}")
    print(f"R_SCRIPT_PATH: {R_SCRIPT_PATH or 'NOT FOUND'}")
    print(f"PLUMBER_API_URL: {PLUMBER_API_URL}")
    print(f"FLASK_PORT: {FLASK_PORT}")
    print(f"FLASK_DEBUG: {FLASK_DEBUG}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    print_config()
