#!/usr/bin/env python3
"""Simple authentication validation script."""

import sys
import os

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("=" * 60)
print("AUTHENTICATION VALIDATION")
print("=" * 60)

# Test 1: Configuration validation
print("\n[1/4] Configuration Check...")
try:
    import config
    print(f"✅ Auth0 Domain: {config.AUTH0_DOMAIN}")
    print(f"✅ Auth0 Enabled: {config.AUTH0_ENABLED}")
    if config.AUTH0_ENABLED:
        print("   - Real Auth0 credentials configured")
        print(f"   - Client ID: {config.AUTH0_CLIENT_ID[:8]}...")
        print(f"   - Callback URL: {config.AUTH0_CALLBACK_URL}")
    else:
        print("   - Auth0 disabled (placeholder credentials)")
except Exception as e:
    print(f"❌ Config error: {e}")
    sys.exit(1)

# Test 2: Database validation
print("\n[2/4] Database Check...")
try:
    from database import count_users, check_connection
    check_connection()
    user_count = count_users()
    print(f"✅ Database connected")
    print(f"   - Users in database: {user_count}")
except Exception as e:
    print(f"❌ Database error: {e}")
    sys.exit(1)

# Test 3: Auth module validation
print("\n[3/4] Auth Module Check...")
try:
    if config.AUTH0_ENABLED:
        import auth
        print(f"✅ Auth module loaded")
        print(f"   - Auth0 Base URL: {auth.AUTH0_BASE_URL}")
        print(f"   - JWKS URL: {auth.AUTH0_JWKS_URL}")

        # Test JWKS cache
        try:
            jwks = auth.get_jwks()
            print(f"   - JWKS keys available: {len(jwks.get('keys', []))}")
        except Exception as e:
            print(f"   - JWKS fetch error: {e}")
    else:
        print("✅ Auth disabled - no auth module needed")
except Exception as e:
    print(f"❌ Auth module error: {e}")

# Test 4: Flask app validation
print("\n[4/4] Flask App Check...")
try:
    os.chdir(os.path.join(os.path.dirname(__file__), 'app_ui'))
    sys.path.insert(0, os.getcwd())

    from app import app
    print(f"✅ Flask app created successfully")

    # Check routes
    auth_routes = [rule.rule for rule in app.url_map.iter_rules() if rule.rule.startswith('/auth/')]
    if config.AUTH0_ENABLED:
        expected_routes = ['/auth/login', '/auth/callback', '/auth/logout', '/auth/user']
        print(f"   - Auth routes registered: {len(auth_routes)}")
        for route in expected_routes:
            if route in auth_routes:
                print(f"     ✅ {route}")
            else:
                print(f"     ❌ {route} (missing)")
    else:
        print(f"   - Auth routes: {len(auth_routes)} (should be 0)")

except Exception as e:
    print(f"❌ Flask app error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("VALIDATION COMPLETE")
print("=" * 60)

# Summary
if config.AUTH0_ENABLED:
    print("\n🔐 AUTH0 MODE ACTIVE")
    print("   - Login flow: /auth/login → Auth0 → /auth/callback")
    print("   - Protected routes redirect to login when not authenticated")
    print("   - User accounts synced to local database")
    print("   - Role-based access control enabled")
else:
    print("\n🔓 NO-AUTH MODE ACTIVE")
    print("   - Protected routes show informative messages")
    print("   - No user authentication required")
    print("   - Anonymous access to all features")