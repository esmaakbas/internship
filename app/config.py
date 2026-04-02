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
    # Also attempt to load .env from the same directory as this config (app root)
    env_local = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_local):
        load_dotenv(env_local)
        print(f"[Config] Loaded environment variables from: {env_local}")
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
PLUMBER_API_URL = os.getenv("PLUMBER_API_URL", "http://localhost:8002")
PLUMBER_PREDICT_URL = f"{PLUMBER_API_URL}/predict"

# Alex LLM Guidance API Configuration
ALEX_GUIDANCE_URL = os.getenv("ALEX_GUIDANCE_URL", "http://localhost:8001/guidance/generate")
ALEX_TIMEOUT_SECONDS = int(os.getenv("ALEX_TIMEOUT_SECONDS", "30"))

# Flask Configuration
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "capsico_inference_secret_key_2026")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
FLASK_PORT = int(os.getenv("FLASK_PORT", "8080"))
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")

# Upload Configuration
ALLOWED_EXTENSIONS = {"csv"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

def _require_env(key: str, context: str = "application") -> str:
    """Require environment variable or fail fast with clear error message.

    Args:
        key: Environment variable name
        context: Description for error message (e.g., "database", "Auth0")

    Raises:
        ValueError: If environment variable is missing or empty
    """
    val = os.getenv(key)
    if not val:
        raise ValueError(
            f"Missing required environment variable: {key}\n"
            f"This is required for {context} configuration.\n"
            f"Please set it in your .env file or environment."
        )
    return val


# Database configuration (MySQL via PyMySQL)
# SECURITY: DB credentials are REQUIRED and must be set in .env
# The app will fail to start if these are not configured properly
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")  # OK to default to localhost
DB_PORT = int(os.getenv("DB_PORT", "3306"))  # OK to default to standard MySQL port
DB_NAME = _require_env("DB_NAME", "database")
DB_USER = _require_env("DB_USER", "database")
DB_PASS = _require_env("DB_PASS", "database")

# SQLAlchemy connection string for MySQL using PyMySQL driver
SQLALCHEMY_DATABASE_URI = (
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?charset=utf8mb4"
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "False").lower() in ("true", "1", "yes")

# Database connection pool and timeout settings
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))  # 1 hour
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))  # seconds

# Auth0 Configuration (Optional)
# Authentication will only be enabled if Auth0 credentials are properly configured
# Set these in your .env file with values from your Auth0 application dashboard
def _is_auth0_configured() -> bool:
    """Check if Auth0 is properly configured (not missing or placeholder values)."""
    domain = os.getenv("AUTH0_DOMAIN", "")
    client_id = os.getenv("AUTH0_CLIENT_ID", "")
    client_secret = os.getenv("AUTH0_CLIENT_SECRET", "")

    # Check if any are missing
    if not domain or not client_id or not client_secret:
        return False

    # Check for common placeholder patterns
    placeholders = ["your-", "your_", "example", "placeholder", "CHANGE_ME"]
    if any(p in domain.lower() for p in placeholders):
        return False
    if any(p in client_id for p in placeholders):
        return False
    if any(p in client_secret for p in placeholders):
        return False

    return True


AUTH0_ENABLED = _is_auth0_configured()

if AUTH0_ENABLED:
    # Auth0 is properly configured - load real values
    AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
    AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
    AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
    AUTH0_CALLBACK_URL = os.getenv("AUTH0_CALLBACK_URL", f"http://127.0.0.1:{FLASK_PORT}/auth/callback")
    # AUTH0_AUDIENCE is only needed if you have a custom Auth0 API
    # For Regular Web Applications without custom APIs, this can be None
    # ID tokens use CLIENT_ID as audience, access tokens use API audience
    AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")  # No default - optional
else:
    # Auth0 not configured - set to None to prevent reference errors
    AUTH0_DOMAIN = None
    AUTH0_CLIENT_ID = None
    AUTH0_CLIENT_SECRET = None
    AUTH0_CALLBACK_URL = None
    AUTH0_AUDIENCE = None

# Session Configuration (for secure cookie-based sessions)
# SECURITY: Session secret MUST be changed in production
SESSION_TYPE = "filesystem"  # Store sessions on filesystem (can be changed to Redis later)
SESSION_PERMANENT = False  # Sessions expire when browser closes
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to cookies
SESSION_COOKIE_SECURE = not FLASK_DEBUG  # HTTPS only in production
SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection

# Allowed IPs for debug routes (only in development)
ALLOWED_DEBUG_IPS = os.getenv("ALLOWED_DEBUG_IPS", "127.0.0.1,::1").split(",")


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
