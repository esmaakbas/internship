"""Debug template context for authentication state.

This script tests what values are actually being passed to templates.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("=" * 60)
print("TEMPLATE CONTEXT DEBUG")
print("=" * 60)

# Test config loading
import config
print(f"[CONFIG] AUTH0_ENABLED from config: {config.AUTH0_ENABLED}")

# Test Flask app
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'app_ui'))
sys.path.insert(0, os.getcwd())

from app import app

print(f"[APP] AUTH0_ENABLED import in app.py: {app.config.get('AUTH0_ENABLED', 'NOT_SET')}")

# Test template context processor
with app.app_context():
    # Get the context processor functions
    context_processors = app.template_context_processors[None]
    print(f"[CONTEXT] Number of context processors: {len(context_processors)}")

    for i, processor in enumerate(context_processors):
        try:
            context_data = processor()
            if 'auth_enabled' in context_data:
                print(f"[CONTEXT] Context processor {i}: auth_enabled = {context_data['auth_enabled']}")
            else:
                print(f"[CONTEXT] Context processor {i}: no auth_enabled")
        except Exception as e:
            print(f"[CONTEXT] Context processor {i} error: {e}")

# Test a template render to see actual value
with app.test_client() as client:
    print(f"\n[TEST] Testing home page template context...")
    response = client.get('/')
    if response.status_code == 200:
        # Check if "Auth Disabled" appears in the response
        response_text = response.get_data(as_text=True)
        if "Auth Disabled" in response_text:
            print("[FOUND] 'Auth Disabled' found in rendered template")
        else:
            print("[NOT FOUND] 'Auth Disabled' not found in rendered template")

        if "Login" in response_text:
            print("[FOUND] 'Login' found in rendered template")
        else:
            print("[NOT FOUND] 'Login' not found in rendered template")
    else:
        print(f"[ERROR] Home page returned status {response.status_code}")

print(f"\n" + "=" * 60)