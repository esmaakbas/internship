#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup Verification Script
Tests all components of the App project to ensure proper installation.
"""
import sys
import os
import subprocess

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def test_python_version():
    """Check Python version"""
    print("=" * 60)
    print("1. Python Version Check")
    print("=" * 60)
    version = sys.version
    print(f"✓ Python version: {version}")
    if sys.version_info >= (3, 8):
        print("✓ Python version is compatible (>= 3.8)")
        return True
    else:
        print("✗ Python version too old (need >= 3.8)")
        return False

def test_imports():
    """Test if all required packages can be imported"""
    print("\n" + "=" * 60)
    print("2. Python Package Imports")
    print("=" * 60)

    packages = {
        'flask': 'flask',
        'pandas': 'pandas',
        'requests': 'requests',
        'werkzeug': 'werkzeug',
    }

    all_ok = True
    for package_name, import_name in packages.items():
        try:
            __import__(import_name)
            print(f"✓ {package_name}: OK")
        except ImportError as e:
            print(f"✗ {package_name}: FAILED - {e}")
            all_ok = False

    return all_ok

def test_r_installation():
    """Check if R is installed and accessible"""
    print("\n" + "=" * 60)
    print("3. R Installation Check")
    print("=" * 60)

    from r_pipeline_link.r_runner import R_EXECUTABLE

    print(f"Expected R path: {R_EXECUTABLE}")

    if not os.path.exists(R_EXECUTABLE):
        print(f"✗ R executable not found at: {R_EXECUTABLE}")
        return False

    print(f"✓ R executable found")

    try:
        result = subprocess.run(
            [R_EXECUTABLE, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        version_line = result.stdout.split('\n')[0]
        print(f"✓ R version: {version_line}")
        return True
    except Exception as e:
        print(f"✗ Failed to run R: {e}")
        return False

def test_r_script_path():
    """Check if the R script exists"""
    print("\n" + "=" * 60)
    print("4. R Script Path Check")
    print("=" * 60)

    from r_pipeline_link.r_runner import R_SCRIPT_PATH

    print(f"R script path: {R_SCRIPT_PATH}")

    if not os.path.exists(R_SCRIPT_PATH):
        print(f"✗ R script not found at: {R_SCRIPT_PATH}")
        return False

    print(f"✓ R script found")
    return True

def test_project_structure():
    """Verify project directory structure"""
    print("\n" + "=" * 60)
    print("5. Project Structure Check")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))

    required_dirs = [
        'inputs',
        'outputs',
        'app_ui',
        'app_ui/templates',
        'app_ui/static',
        'services',
        'clients',
        'r_pipeline_link',
    ]

    all_ok = True
    for dir_name in required_dirs:
        dir_path = os.path.join(base_dir, dir_name)
        if os.path.exists(dir_path):
            print(f"✓ {dir_name}/")
        else:
            print(f"✗ {dir_name}/ - NOT FOUND")
            all_ok = False

    return all_ok

def test_flask_templates():
    """Check if Flask templates exist"""
    print("\n" + "=" * 60)
    print("6. Flask Templates Check")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(base_dir, 'app_ui', 'templates')

    required_templates = ['index.html', 'results.html', 'layout.html']

    all_ok = True
    for template in required_templates:
        template_path = os.path.join(templates_dir, template)
        if os.path.exists(template_path):
            print(f"✓ {template}")
        else:
            print(f"✗ {template} - NOT FOUND")
            all_ok = False

    return all_ok

def test_module_imports():
    """Test if project modules can be imported"""
    print("\n" + "=" * 60)
    print("7. Project Module Imports")
    print("=" * 60)

    modules = [
        'services.inference_service',
        'services.base_payload',
        'clients.plumber_client',
        'r_pipeline_link.r_runner',
    ]

    all_ok = True
    for module in modules:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError as e:
            print(f"✗ {module}: FAILED - {e}")
            all_ok = False

    return all_ok

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("APP PROJECT SETUP VERIFICATION")
    print("=" * 60)

    results = {
        'Python Version': test_python_version(),
        'Python Packages': test_imports(),
        'R Installation': test_r_installation(),
        'R Script Path': test_r_script_path(),
        'Project Structure': test_project_structure(),
        'Flask Templates': test_flask_templates(),
        'Module Imports': test_module_imports(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(results.values())

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED - Setup is complete!")
        print("\nYou can now:")
        print("1. Start the Flask app: python app_ui/app.py")
        print("2. Or test the inference: python run_test.py")
        print("\nNote: For Plumber API mode, ensure the Plumber service")
        print("      is running at http://localhost:8000")
    else:
        print("✗ SOME TESTS FAILED - Please review the errors above")
        return 1
    print("=" * 60)

    return 0

if __name__ == "__main__":
    sys.exit(main())
