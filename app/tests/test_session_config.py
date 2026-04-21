"""Session debugging test.

Visit this route to test session persistence and configuration.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("=" * 60)
print("SESSION CONFIGURATION TEST")
print("=" * 60)

# Test Flask app session config
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'app_ui'))
sys.path.insert(0, os.getcwd())

from app import app

print(f"[CONFIG] Flask Debug: {app.debug}")
print(f"[CONFIG] Secret Key: {'Set' if app.secret_key else 'NOT SET'}")

# Check session configuration
session_config = {
    'SESSION_TYPE': app.config.get('SESSION_TYPE'),
    'SESSION_PERMANENT': app.config.get('SESSION_PERMANENT'),
    'SESSION_COOKIE_SECURE': app.config.get('SESSION_COOKIE_SECURE'),
    'SESSION_COOKIE_HTTPONLY': app.config.get('SESSION_COOKIE_HTTPONLY'),
    'SESSION_COOKIE_SAMESITE': app.config.get('SESSION_COOKIE_SAMESITE'),
    'SESSION_COOKIE_NAME': app.config.get('SESSION_COOKIE_NAME'),
    'SESSION_USE_SIGNER': app.config.get('SESSION_USE_SIGNER'),
}

print(f"\n[SESSION CONFIG]:")
for key, value in session_config.items():
    print(f"  {key}: {value}")

# Test session with a simple route
with app.test_client() as client:
    print(f"\n[TEST] Testing session persistence...")

    # First request - set a value
    with client.session_transaction() as sess:
        sess['test_value'] = 'hello_world'
        print(f"[SET] Session value: {sess.get('test_value')}")

    # Second request - check if value persists
    response = client.get('/')
    print(f"[GET] Home page status: {response.status_code}")

    # Check if we can retrieve the session value
    with client.session_transaction() as sess:
        retrieved = sess.get('test_value')
        print(f"[GET] Retrieved session value: {retrieved}")
        if retrieved == 'hello_world':
            print("[OK] Session persistence works in test client")
        else:
            print("[FAIL] Session persistence failed in test client")

print(f"\n[NEXT] Test login flow manually:")
print(f"1. Go to: http://127.0.0.1:8080/auth/login")
print(f"2. Check Flask terminal for detailed session logs")
print(f"3. Complete Auth0 login process")
print(f"4. Check if state parameter is preserved")

print(f"\n" + "=" * 60)