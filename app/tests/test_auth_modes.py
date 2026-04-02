#!/usr/bin/env python3
"""Test authentication behavior in both modes."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_auth_enabled_mode():
    """Test behavior when Auth0 is enabled (current mode)."""
    print("=" * 60)
    print("TESTING AUTH0-ENABLED MODE")
    print("=" * 60)

    # Change to app_ui directory
    app_ui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app_ui')
    os.chdir(app_ui_path)
    sys.path.insert(0, os.getcwd())

    from app import app

    with app.test_client() as client:
        with app.app_context():
            print("\n[TEST] Home page access:")
            response = client.get('/')
            print(f"  GET / -> {response.status_code} ({'PASS' if response.status_code == 200 else 'FAIL'})")

            print("\n[TEST] Protected route (not logged in):")
            response = client.get('/profile')
            print(f"  GET /profile -> {response.status_code}", end="")
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                if '/auth/login' in location:
                    print(" (redirects to login) [PASS]")
                else:
                    print(f" (redirects to {location}) [UNEXPECTED]")
            else:
                print(" [UNEXPECTED - should redirect to login]")

            print("\n[TEST] Admin route (not logged in):")
            response = client.get('/admin')
            print(f"  GET /admin -> {response.status_code}", end="")
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                if '/auth/login' in location:
                    print(" (redirects to login) [PASS]")
                else:
                    print(f" (redirects to {location}) [UNEXPECTED]")
            else:
                print(" [UNEXPECTED - should redirect to login]")

            print("\n[TEST] Auth routes availability:")
            auth_routes = [rule.rule for rule in app.url_map.iter_rules()
                          if rule.rule.startswith('/auth/')]
            expected_auth_routes = ['/auth/login', '/auth/callback', '/auth/logout', '/auth/user']

            for expected in expected_auth_routes:
                if expected in auth_routes:
                    print(f"  {expected} -> [PRESENT]")
                else:
                    print(f"  {expected} -> [MISSING]")

            print(f"\n  Total auth routes: {len(auth_routes)}")

            print("\n[TEST] Auth login redirect:")
            response = client.get('/auth/login')
            print(f"  GET /auth/login -> {response.status_code}", end="")
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                if 'auth0.com' in location:
                    print(" (redirects to Auth0) [PASS]")
                else:
                    print(f" (redirects to {location}) [UNEXPECTED]")
            else:
                print(" [UNEXPECTED - should redirect to Auth0]")

def test_mode_summary():
    """Print summary of current configuration."""
    print("\n" + "=" * 60)
    print("CONFIGURATION SUMMARY")
    print("=" * 60)

    # Check config
    import config
    print(f"Auth0 Domain: {config.AUTH0_DOMAIN}")
    print(f"Auth0 Enabled: {config.AUTH0_ENABLED}")
    print(f"Database: {config.DB_NAME}")

    if config.AUTH0_ENABLED:
        print("\n✅ AUTH0 MODE: Authentication enabled")
        print("   - Protected routes redirect to Auth0 login")
        print("   - User sessions are managed")
        print("   - Role-based access control active")
    else:
        print("\n⚠️  NO-AUTH MODE: Authentication disabled")
        print("   - Protected routes show informative messages")
        print("   - No login/logout functionality")
        print("   - All users have anonymous access")

if __name__ == "__main__":
    try:
        test_auth_enabled_mode()
        test_mode_summary()

        print("\n" + "=" * 60)
        print("AUTH MODE TESTING COMPLETE")
        print("=" * 60)

    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)