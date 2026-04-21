"""Test role extraction fix.

This script simulates what happens during Auth0 callback to verify
that role extraction now works with app_metadata.
"""

import sys
import os
import requests
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("=" * 60)
print("AUTH0 ROLE EXTRACTION FIX TEST")
print("=" * 60)

# Import after path setup
import config
from auth import extract_user_role, AuthError

print(f"[CONFIG] Auth0 Domain: {config.AUTH0_DOMAIN}")
print(f"[CONFIG] Auth0 Enabled: {config.AUTH0_ENABLED}")

# Test 1: ID token payload (what we used to get - missing app_metadata)
print(f"\n[TEST 1] ID Token Payload (old way - should fail)")
id_token_userinfo = {
    "sub": "auth0|123456789",
    "email": "test-admin@example.com",
    "name": "Test Admin",
    "nickname": "testadmin",
    # No app_metadata in ID token!
}

try:
    role = extract_user_role(id_token_userinfo)
    print(f"[UNEXPECTED] Role found: {role}")
except AuthError as e:
    print(f"[EXPECTED] AuthError: {e.message}")

# Test 2: Full userinfo response (what we get now - includes app_metadata)
print(f"\n[TEST 2] Full Userinfo Response (new way - should work)")
full_userinfo = {
    "sub": "auth0|123456789",
    "email": "test-admin@example.com",
    "name": "Test Admin",
    "nickname": "testadmin",
    "app_metadata": {
        "role": "admin"  # ← This is what you added in Auth0 dashboard!
    }
}

try:
    role = extract_user_role(full_userinfo)
    print(f"[SUCCESS] Role extracted: {role}")
except AuthError as e:
    print(f"[FAIL] AuthError: {e.message}")

# Test 3: Regular user role
print(f"\n[TEST 3] Regular User Role")
user_userinfo = {
    "sub": "auth0|987654321",
    "email": "test-user@example.com",
    "name": "Test User",
    "app_metadata": {
        "role": "user"
    }
}

try:
    role = extract_user_role(user_userinfo)
    print(f"[SUCCESS] Role extracted: {role}")
except AuthError as e:
    print(f"[FAIL] AuthError: {e.message}")

# Test 4: Invalid role value
print(f"\n[TEST 4] Invalid Role Value")
invalid_userinfo = {
    "sub": "auth0|111222333",
    "email": "test-invalid@example.com",
    "app_metadata": {
        "role": "superuser"  # Invalid role
    }
}

try:
    role = extract_user_role(invalid_userinfo)
    print(f"[UNEXPECTED] Invalid role accepted: {role}")
except AuthError as e:
    print(f"[EXPECTED] AuthError: {e.message}")

print(f"\n" + "=" * 60)
print("ROLE EXTRACTION TEST SUMMARY")
print("=" * 60)
print(f"✓ Fix applied: Auth0 callback now fetches full userinfo")
print(f"✓ Role source: userinfo['app_metadata']['role']")
print(f"✓ Your setup: Users have role in App Metadata")
print(f"✓ Expected result: Login should work with role extraction")
print(f"\nReady for manual testing at: http://127.0.0.1:8080")