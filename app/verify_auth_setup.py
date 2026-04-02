"""Quick test script to verify authentication setup is ready.

Run this before starting the Flask app to catch configuration errors early.
"""

import sys
import os

sys.path.append(os.path.dirname(__file__))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    try:
        import flask
        import flask_session
        import jose
        import requests
        import sqlalchemy
        import pymysql
        print("✅ All dependencies installed")
        return True
    except ImportError as exc:
        print(f"❌ Missing dependency: {exc}")
        print("Run: pip install -r requirements.txt")
        return False


def test_config():
    """Test that required configuration is present."""
    print("\nTesting configuration...")
    try:
        import config
        # These should not raise errors if .env is configured correctly
        assert config.DB_NAME, "DB_NAME is empty"
        assert config.DB_USER, "DB_USER is empty"
        assert config.DB_PASS, "DB_PASS is empty"
        assert config.AUTH0_DOMAIN, "AUTH0_DOMAIN is empty"
        assert config.AUTH0_CLIENT_ID, "AUTH0_CLIENT_ID is empty"
        assert config.AUTH0_CLIENT_SECRET, "AUTH0_CLIENT_SECRET is empty"
        print("✅ Configuration loaded successfully")
        print(f"   - Database: {config.DB_NAME}")
        print(f"   - Auth0 Domain: {config.AUTH0_DOMAIN}")
        return True
    except (ValueError, AssertionError) as exc:
        print(f"❌ Configuration error: {exc}")
        print("Check your .env file - see .env.example for required variables")
        return False


def test_database():
    """Test database connection."""
    print("\nTesting database connection...")
    try:
        from database import validate_database, count_users
        validate_database()
        user_count = count_users()
        print(f"✅ Database connection successful")
        print(f"   - Users in database: {user_count}")
        return True
    except Exception as exc:
        print(f"❌ Database connection failed: {exc}")
        print("Ensure Docker is running: docker-compose up -d")
        return False


def test_auth_module():
    """Test that auth module loads correctly."""
    print("\nTesting auth module...")
    try:
        import auth
        print("✅ Auth module loaded successfully")
        print(f"   - Auth0 Base URL: {auth.AUTH0_BASE_URL}")
        print(f"   - JWKS URL: {auth.AUTH0_JWKS_URL}")
        return True
    except Exception as exc:
        print(f"❌ Auth module error: {exc}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Authentication Setup Verification")
    print("=" * 60)

    results = []
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Database", test_database()))
    results.append(("Auth Module", test_auth_module()))

    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 All checks passed! You can now start the Flask app:")
        print("   cd app_ui && python app.py")
        print("\nThen visit: http://127.0.0.1:8080")
        return 0
    else:
        print("\n❌ Some checks failed. Fix the errors above before starting the app.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
