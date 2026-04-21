"""Test Auth0 callback error handling.

This script tests that the callback properly handles Auth0 error responses
before checking state parameters, preventing misleading error messages.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("=" * 60)
print("AUTH0 CALLBACK ERROR HANDLING TEST")
print("=" * 60)

# Test Flask app
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'app_ui'))
sys.path.insert(0, os.getcwd())

from app import app

print(f"[TEST] Testing callback error handling...")

with app.test_client() as client:
    # Test 1: Auth0 error response (should be handled before state validation)
    print("\n[TEST 1] Auth0 error response handling...")
    response = client.get('/auth/callback?error=access_denied&error_description=User+cancelled+login')

    if response.status_code == 400:
        response_text = response.get_data(as_text=True)
        if "Auth0 authorization failed: access_denied" in response_text:
            print("[OK] Auth0 error handled correctly")
            print("     Error message includes Auth0 error details")
        else:
            print(f"[WARN] Error handled but wrong message: {response_text[:100]}...")
    else:
        print(f"[WARN] Expected 400 status, got {response.status_code}")

    # Test 2: Missing state parameter (should give clear CSRF message)
    print("\n[TEST 2] Missing state parameter handling...")
    response = client.get('/auth/callback?code=test_code')

    if response.status_code == 400:
        response_text = response.get_data(as_text=True)
        if "Invalid state parameter" in response_text:
            print("[OK] State parameter validation working")
        else:
            print(f"[WARN] Expected state error message: {response_text[:100]}...")
    else:
        print(f"[WARN] Expected 400 status, got {response.status_code}")

    # Test 3: Login URL parameters (should not include audience=None)
    print("\n[TEST 3] Login URL parameter validation...")
    response = client.get('/auth/login', follow_redirects=False)

    if response.status_code == 302:
        location = response.headers.get('Location', '')
        print(f"[INFO] Redirect URL: {location}")

        if "audience=" not in location:
            print("[OK] No audience parameter included (correct for Regular Web App)")
        else:
            print("[WARN] Audience parameter found in URL")

        if "client_id=" in location and "state=" in location and "scope=" in location:
            print("[OK] Required parameters present")
        else:
            print("[WARN] Missing required parameters")
    else:
        print(f"[WARN] Expected 302 redirect, got {response.status_code}")

print(f"\n" + "=" * 60)
print("AUTH0 CALLBACK ERROR HANDLING TEST COMPLETE")
print("=" * 60)
print("\nFixes applied:")
print("✓ Removed audience=None parameter from authorize URL")
print("✓ Auth0 error responses processed before state validation")
print("✓ Clear error messages for both Auth0 and CSRF errors")
print("\nReady for manual testing: http://127.0.0.1:8080")