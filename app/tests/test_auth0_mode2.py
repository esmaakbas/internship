"""Auth0 Mode 2 validation script.

Run this after configuring real Auth0 credentials to verify the setup
before manual testing in the browser.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("=" * 80)
print("AUTH0 MODE 2 VALIDATION")
print("=" * 80)

try:
    # Test configuration loading
    import config
    print(f"\n[CONFIG] Auth0 enabled: {config.AUTH0_ENABLED}")

    if not config.AUTH0_ENABLED:
        print("[ERROR] Auth0 still disabled - check your .env file")
        print("Required variables:")
        print("  - AUTH0_DOMAIN=your-tenant.auth0.com")
        print("  - AUTH0_CLIENT_ID=your_client_id")
        print("  - AUTH0_CLIENT_SECRET=your_client_secret")
        sys.exit(1)

    print(f"[OK] Auth0 Domain: {config.AUTH0_DOMAIN}")
    print(f"[OK] Auth0 Client ID: {config.AUTH0_CLIENT_ID[:8]}...")
    print(f"[OK] Auth0 Client Secret: {'*' * len(config.AUTH0_CLIENT_SECRET)}")

    # Test Auth0 URLs construction
    import auth
    print(f"\n[URLS] Auth0 Base: {auth.AUTH0_BASE_URL}")
    print(f"[URLS] Authorize: {auth.AUTH0_AUTHORIZE_URL}")
    print(f"[URLS] Token: {auth.AUTH0_TOKEN_URL}")
    print(f"[URLS] JWKS: {auth.AUTH0_JWKS_URL}")

    # Test JWKS endpoint accessibility
    print(f"\n[TEST] Testing Auth0 JWKS endpoint...")
    try:
        jwks = auth.get_jwks()
        if 'keys' in jwks and len(jwks['keys']) > 0:
            print(f"[OK] JWKS endpoint accessible, {len(jwks['keys'])} keys found")
        else:
            print(f"[WARN] JWKS endpoint accessible but no keys found")
    except Exception as e:
        print(f"[ERROR] JWKS endpoint test failed: {e}")
        print("This might indicate:")
        print("  - Incorrect AUTH0_DOMAIN")
        print("  - Network connectivity issues")
        print("  - Auth0 service unavailable")

    # Test database connectivity
    print(f"\n[TEST] Testing database connectivity...")
    from database import check_connection, count_users
    try:
        check_connection()
        user_count = count_users()
        print(f"[OK] Database accessible, {user_count} users currently")
    except Exception as e:
        print(f"[ERROR] Database test failed: {e}")
        sys.exit(1)

    # Test Flask app creation with Auth0 enabled
    print(f"\n[TEST] Testing Flask app creation with Auth0...")
    os.chdir(os.path.join(os.path.dirname(__file__), '..', 'app_ui'))
    sys.path.insert(0, os.getcwd())

    from app import app
    print(f"[OK] Flask app created with Auth0 enabled")

    # Check routes
    auth_routes = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint and 'auth' in rule.endpoint:
            auth_routes.append(f"{rule.rule} -> {rule.endpoint}")

    print(f"\n[ROUTES] Auth routes registered:")
    for route in auth_routes:
        print(f"  {route}")

    # Test protected route behavior
    with app.test_client() as client:
        print(f"\n[TEST] Testing protected route behavior...")

        # Should redirect to login when not authenticated
        response = client.get('/profile', follow_redirects=False)
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            if '/auth/login' in location:
                print("[OK] /profile redirects to login when not authenticated")
            else:
                print(f"[WARN] /profile redirects to {location}, expected auth/login")
        else:
            print(f"[ERROR] /profile returned {response.status_code}, expected 302 redirect")

        # Test login route exists
        response = client.get('/auth/login', follow_redirects=False)
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            if config.AUTH0_DOMAIN in location:
                print("[OK] /auth/login redirects to Auth0")
            else:
                print(f"[WARN] /auth/login redirects to {location}")
        else:
            print(f"[ERROR] /auth/login returned {response.status_code}, expected 302")

except Exception as e:
    print(f"[ERROR] Validation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"\n" + "=" * 80)
print("AUTH0 TECHNICAL VALIDATION COMPLETE")
print("=" * 80)
print()
print("Next steps for full validation:")
print("1. Start Flask app: cd app_ui && python app.py")
print("2. Open browser to http://127.0.0.1:8080")
print("3. Follow the manual testing checklist in AUTH0_SETUP_GUIDE.md")
print("4. Test login, logout, and role-based access")
print()
print("The authentication foundation is COMPLETE when ALL manual tests pass.")