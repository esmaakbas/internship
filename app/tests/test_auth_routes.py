"""Test Auth0 routes with invalid config."""
import sys
import os

os.chdir(os.path.join(os.path.dirname(__file__), 'app_ui'))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.dirname(os.getcwd()))

from app import app

print("Testing Auth0 routes with placeholder config...")
print("=" * 60)

with app.test_client() as client:
    # Test 1: Try to login
    print("\n[Test 1] GET /auth/login")
    response = client.get('/auth/login', follow_redirects=False)
    print(f"  Status: {response.status_code}")
    if response.status_code == 302:
        print(f"  Redirect to: {response.location}")
        if "your-tenant.auth0.com" in response.location:
            print("[RESULT] Redirects to invalid Auth0 domain (will fail)")

    # Test 2: Try callback without proper state
    print("\n[Test 2] GET /auth/callback (no params)")
    response = client.get('/auth/callback')
    print(f"  Status: {response.status_code}")
    if response.status_code >= 400:
        print(f"[RESULT] Properly rejects invalid callback")

    # Test 3: Access /auth/user without login
    print("\n[Test 3] GET /auth/user (no login)")
    response = client.get('/auth/user')
    print(f"  Status: {response.status_code}")
    if response.status_code in (302, 401):
        print(f"[RESULT] Properly requires authentication")

print("\n" + "=" * 60)
print("Auth route tests complete")
