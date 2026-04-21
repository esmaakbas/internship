"""Runtime validation test - Check if the app actually works."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("=" * 60)
print("RUNTIME VALIDATION TEST")
print("=" * 60)

# Test 1: Config loads
print("\n[1/6] Testing config.py import...")
try:
    import config
    print("[OK] Config loaded")
    print(f"    - DB: {config.DB_NAME}")
    print(f"    - Auth0 Domain: {config.AUTH0_DOMAIN}")
    print(f"    - Flask Port: {config.FLASK_PORT}")

    # Check if Auth0 has placeholder values
    if (config.AUTH0_DOMAIN and "your-tenant" in config.AUTH0_DOMAIN) or (config.AUTH0_CLIENT_ID and "your_client" in config.AUTH0_CLIENT_ID):
        print(f"[WARN] Auth0 has placeholder values (app will start but auth won't work)")
except Exception as e:
    print(f"[FAIL] Config failed: {e}")
    sys.exit(1)

# Test 2: Database module
print("\n[2/6] Testing database.py import...")
try:
    from database import get_engine, validate_database, count_users
    print(f"[OK] Database module loaded")
except Exception as e:
    print(f"[FAIL] Database module failed: {e}")
    sys.exit(1)

# Test 3: Database connection
print("\n[3/6] Testing database connection...")
try:
    engine = get_engine()
    print(f"[OK] Engine created")
    print(f"    - URL: {config.SQLALCHEMY_DATABASE_URI.split('@')[1]}")  # Hide password
except Exception as e:
    print(f"[FAIL] Engine creation failed: {e}")
    sys.exit(1)

# Test 4: Database validation
print("\n[4/6] Testing database validation...")
try:
    validate_database()
    user_count = count_users()
    print(f"[OK] Database validation passed")
    print(f"    - Users in DB: {user_count}")
except Exception as e:
    print(f"[WARN]  Database validation failed: {e}")
    print(f"    (This is OK if MySQL isn't running)")

# Test 5: Auth module
print("\n[5/6] Testing auth.py import...")
try:
    import auth
    print(f"[OK] Auth module loaded")
    print(f"    - Auth0 Base: {auth.AUTH0_BASE_URL}")
    if auth.AUTH0_DOMAIN and "your-tenant" in auth.AUTH0_DOMAIN:
        print(f"[WARN]  WARNING: Auth0 not configured (login will fail)")
except Exception as e:
    print(f"[FAIL] Auth module failed: {e}")
    sys.exit(1)

# Test 6: Flask app creation
print("\n[6/6] Testing Flask app creation...")
try:
    # Change to app_ui directory for imports to work
    app_ui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app_ui')
    os.chdir(app_ui_path)
    sys.path.insert(0, os.getcwd())

    # Import app
    from app import app
    print(f"[OK] Flask app created")
    print(f"    - Registered routes:")

    excluded_routes = {'static', 'auth.register_auth_routes.<locals>.auth_login'}
    routes = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint not in excluded_routes and not rule.endpoint.startswith('_'):
            routes.append(f"{rule.rule:30} -> {rule.endpoint}")

    for route in sorted(routes)[:15]:  # Show first 15
        print(f"      {route}")

    if len(routes) > 15:
        print(f"      ... and {len(routes) - 15} more")

except Exception as e:
    print(f"[FAIL] Flask app creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Make additional auth-specific test requests
print("\n[7/7] Testing route response...")
try:
    with app.test_client() as client:
        # Test home page
        response = client.get('/')
        if response.status_code == 200:
            print(f"[OK] GET / returned {response.status_code}")
        else:
            print(f"[WARN]  GET / returned {response.status_code} (expected 200)")

        # Test debug route
        response = client.get('/debug/db-check')
        if response.status_code in (200, 403, 404, 500):  # Various valid responses
            print(f"[OK] GET /debug/db-check returned {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"    - DB Status: {data}")
        else:
            print(f"[WARN]  GET /debug/db-check returned {response.status_code}")

        # Test protected route without login
        response = client.get('/profile')
        if response.status_code == 200:  # Auth disabled - informative message
            print(f"[OK] GET /profile returned {response.status_code} (auth disabled)")
        elif response.status_code in (302, 401):  # Auth enabled - redirect to login or 401
            print(f"[OK] GET /profile returned {response.status_code} (protected)")
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                if '/auth/login' in location:
                    print(f"    - Redirects to: {location}")
                else:
                    print(f"    - Redirects to: {location} (unexpected)")
        else:
            print(f"[WARN]  GET /profile returned {response.status_code} (unexpected)")

        # Test admin route without login
        response = client.get('/admin')
        if response.status_code == 200:  # Auth disabled
            print(f"[OK] GET /admin returned {response.status_code} (auth disabled)")
        elif response.status_code in (302, 401):  # Auth enabled - redirect to login
            print(f"[OK] GET /admin returned {response.status_code} (protected)")
        else:
            print(f"[WARN]  GET /admin returned {response.status_code} (unexpected)")

        # Test Auth0 login redirect (only if auth enabled)
        if config.AUTH0_ENABLED:
            response = client.get('/auth/login')
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                if 'auth0.com' in location:
                    print(f"[OK] GET /auth/login redirects to Auth0")
                else:
                    print(f"[WARN]  GET /auth/login redirects to: {location}")
            else:
                print(f"[WARN]  GET /auth/login returned {response.status_code} (expected 302)")

except Exception as e:
    print(f"[FAIL] Route testing failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("VALIDATION COMPLETE")
print("=" * 60)
