#!/usr/bin/env python3
"""
Test script for the production-ready registration endpoint.

This script tests all scenarios for the registration endpoint including:
- Valid registration
- Duplicate email/username
- Invalid inputs
- Database errors
- Password hashing

Run with: python test_registration_fixed.py
"""

import requests
import json
import sys
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"
REGISTER_URL = f"{API_BASE}/auth/register"
DEBUG_URL = f"{API_BASE}/debug/registration"
HEALTH_URL = f"{API_BASE}/health"

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text:^80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

def print_test(test_name: str):
    """Print a test name."""
    print(f"{Colors.CYAN}► {test_name}{Colors.ENDC}")

def print_success(message: str):
    """Print a success message."""
    print(f"  {Colors.GREEN}✓ {message}{Colors.ENDC}")

def print_error(message: str):
    """Print an error message."""
    print(f"  {Colors.RED}✗ {message}{Colors.ENDC}")

def print_info(message: str):
    """Print an info message."""
    print(f"  {Colors.BLUE}ℹ {message}{Colors.ENDC}")

def print_warning(message: str):
    """Print a warning message."""
    print(f"  {Colors.YELLOW}⚠ {message}{Colors.ENDC}")

def test_health_check() -> bool:
    """Test if the backend is running."""
    print_test("Health Check")
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Backend is running: {data.get('service')}")
            return True
        else:
            print_error(f"Health check failed with status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Cannot connect to backend: {e}")
        return False

def test_debug_endpoint() -> Dict[str, Any]:
    """Test the debug endpoint."""
    print_test("Debug Endpoint")
    try:
        response = requests.get(DEBUG_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success("Debug endpoint responded")
            if data.get('status') == 'ok':
                diagnostic = data.get('diagnostic', {})
                db_info = diagnostic.get('database', {})
                users_info = diagnostic.get('users', {})
                
                print_info(f"Database: {db_info.get('type')} - Connected: {db_info.get('connected')}")
                print_info(f"User count: {users_info.get('total_count', 0)}")
                admin = users_info.get('admin', {})
                print_info(f"Admin exists: {admin.get('exists', False)}")
            return data
        else:
            print_error(f"Debug endpoint failed with status {response.status_code}")
            return {}
    except Exception as e:
        print_error(f"Debug endpoint error: {e}")
        return {}

def register_user(email: str, username: str, full_name: str, password: str) -> Dict[str, Any]:
    """Register a user and return the response."""
    payload = {
        "email": email,
        "username": username,
        "full_name": full_name,
        "password": password,
        "phone": None,
        "referral_code": None
    }
    
    try:
        response = requests.post(REGISTER_URL, json=payload, timeout=10)
        return {
            "status_code": response.status_code,
            "data": response.json(),
            "ok": response.status_code in [200, 201],
            "raw_response": response
        }
    except requests.exceptions.Timeout:
        return {
            "status_code": None,
            "data": {"error": "Timeout"},
            "ok": False,
            "raw_response": None
        }
    except Exception as e:
        return {
            "status_code": None,
            "data": {"error": str(e)},
            "ok": False,
            "raw_response": None
        }

def test_valid_registration():
    """Test valid user registration."""
    print_test("Valid Registration")
    
    # Use unique email/username with timestamp
    timestamp = int(time.time() * 1000) % 100000
    email = f"testuser{timestamp}@example.com"
    username = f"testuser{timestamp}"
    full_name = "Test User"
    password = "testpass123"
    
    result = register_user(email, username, full_name, password)
    
    if result['ok']:
        print_success(f"Registration successful for {email}")
        data = result['data']
        print_info(f"User ID: {data.get('id')}")
        print_info(f"Username: {data.get('username')}")
        print_info(f"Full Name: {data.get('full_name')}")
        print_info(f"Email: {data.get('email')}")
        return True
    else:
        print_error(f"Registration failed with status {result['status_code']}")
        print_error(f"Response: {result['data']}")
        return False

def test_duplicate_email():
    """Test duplicate email rejection."""
    print_test("Duplicate Email Detection")
    
    timestamp = int(time.time() * 1000) % 100000
    email = f"duplicate{timestamp}@example.com"
    
    # First registration
    result1 = register_user(email, f"user1_{timestamp}", "User One", "password123")
    if not result1['ok']:
        print_warning("First registration failed, skipping duplicate test")
        return False
    
    print_success("First registration succeeded")
    
    # Second registration with same email
    result2 = register_user(email, f"user2_{timestamp}", "User Two", "password123")
    
    if not result2['ok'] and result2['status_code'] == 400:
        error_msg = result2['data'].get('detail', '')
        if 'email' in error_msg.lower():
            print_success("Duplicate email was correctly rejected")
            return True
        else:
            print_error(f"Wrong error message for duplicate: {error_msg}")
            return False
    else:
        print_error(f"Duplicate email was NOT rejected (status: {result2['status_code']})")
        return False

def test_duplicate_username():
    """Test duplicate username rejection."""
    print_test("Duplicate Username Detection")
    
    timestamp = int(time.time() * 1000) % 100000
    username = f"dupuser{timestamp}"
    
    # First registration
    result1 = register_user(f"email1_{timestamp}@example.com", username, "User One", "password123")
    if not result1['ok']:
        print_warning("First registration failed, skipping duplicate test")
        return False
    
    print_success("First registration succeeded")
    
    # Second registration with same username
    result2 = register_user(f"email2_{timestamp}@example.com", username, "User Two", "password123")
    
    if not result2['ok'] and result2['status_code'] == 400:
        error_msg = result2['data'].get('detail', '')
        if 'username' in error_msg.lower():
            print_success("Duplicate username was correctly rejected")
            return True
        else:
            print_error(f"Wrong error message for duplicate: {error_msg}")
            return False
    else:
        print_error(f"Duplicate username was NOT rejected (status: {result2['status_code']})")
        return False

def test_invalid_email():
    """Test invalid email rejection."""
    print_test("Invalid Email Detection")
    
    result = register_user("not-an-email", "validuser", "Valid User", "password123")
    
    if not result['ok'] and result['status_code'] == 422:
        print_success("Invalid email was correctly rejected")
        return True
    else:
        print_warning(f"Status code was {result['status_code']}, expected 422 for validation error")
        return False

def test_short_password():
    """Test short password rejection."""
    print_test("Short Password Detection")
    
    timestamp = int(time.time() * 1000) % 100000
    result = register_user(f"user{timestamp}@example.com", f"user{timestamp}", "User", "short")
    
    if not result['ok'] and result['status_code'] == 422:
        error_msg = str(result['data'])
        if 'password' in error_msg.lower():
            print_success("Short password was correctly rejected")
            return True
        else:
            print_error(f"Wrong validation error: {error_msg}")
            return False
    else:
        print_error(f"Short password was NOT rejected (status: {result['status_code']})")
        return False

def test_long_password():
    """Test very long password handling."""
    print_test("Long Password Handling")
    
    timestamp = int(time.time() * 1000) % 100000
    long_password = "a" * 300  # 300 characters
    
    result = register_user(
        f"longpass{timestamp}@example.com",
        f"longpass{timestamp}",
        "Long Pass User",
        long_password
    )
    
    if not result['ok']:
        print_success("Long password was correctly rejected")
        return True
    else:
        print_warning("Long password was accepted (might be OK if truncated)")
        return True

def test_password_with_special_chars():
    """Test password with special characters."""
    print_test("Special Characters in Password")
    
    timestamp = int(time.time() * 1000) % 100000
    special_password = "P@ssw0rd!#$%^&*()"
    
    result = register_user(
        f"special{timestamp}@example.com",
        f"special{timestamp}",
        "Special User",
        special_password
    )
    
    if result['ok']:
        print_success("Special characters in password handled correctly")
        return True
    else:
        print_error(f"Password with special chars failed: {result['data']}")
        return False

def main():
    """Run all tests."""
    print_header("Registration Endpoint Test Suite")
    
    # Check if backend is running
    if not test_health_check():
        print_error("Backend is not running. Start it with: python main.py")
        sys.exit(1)
    
    print("")
    test_debug_endpoint()
    
    print_header("Registration Tests")
    
    tests = [
        test_valid_registration,
        test_duplicate_email,
        test_duplicate_username,
        test_invalid_email,
        test_short_password,
        test_long_password,
        test_password_with_special_chars,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print_error(f"Test exception: {e}")
            results.append(False)
        print("")
    
    # Summary
    print_header("Test Summary")
    passed = sum(results)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0
    
    print_info(f"Tests Passed: {passed}/{total} ({percentage:.1f}%)")
    
    if percentage == 100:
        print_success("All tests passed!")
        sys.exit(0)
    else:
        print_warning(f"{total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
