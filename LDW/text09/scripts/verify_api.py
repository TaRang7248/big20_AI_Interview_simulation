import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import json
import uuid

BASE_URL = "http://localhost:5000"

def test_password_verification():
    # 1. Register a new user
    unique_id = f"test_user_{uuid.uuid4().hex[:8]}"
    password = "secure_password"
    
    register_data = {
        "id_name": unique_id,
        "pw": password,
        "name": "Test User",
        "dob": "1990-01-01",
        "gender": "male",
        "email": "test@example.com",
        "address": "Test City",
        "phone": "010-0000-0000",
        "type": "applicant"
    }
    
    print(f"1. Registering user: {unique_id}")
    resp = requests.post(f"{BASE_URL}/api/register", json=register_data)
    if resp.status_code != 200:
        print(f"Registration failed: {resp.text}")
        return
    print("Registration successful.")

    # 2. Login (to verify account works)
    login_data = {
        "id_name": unique_id,
        "pw": password
    }
    print("2. Logging in...")
    resp = requests.post(f"{BASE_URL}/api/login", json=login_data)
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        return
    print("Login successful.")

    # 3. Verify Wrong Password
    print("3. Testing WRONG password verification...")
    wrong_pw_data = {
        "id_name": unique_id,
        "pw": "wrong_password"
    }
    resp = requests.post(f"{BASE_URL}/api/verify-password", json=wrong_pw_data)
    if resp.status_code == 401:
        print("SUCCESS: Wrong password correctly rejected.")
    else:
        print(f"FAILURE: Wrong password not rejected properly. Status: {resp.status_code}, Body: {resp.text}")

    # 4. Verify Correct Password
    print("4. Testing CORRECT password verification...")
    correct_pw_data = {
        "id_name": unique_id,
        "pw": password
    }
    resp = requests.post(f"{BASE_URL}/api/verify-password", json=correct_pw_data)
    if resp.status_code == 200:
        result = resp.json()
        if result.get("success"):
            print("SUCCESS: Correct password verified.")
        else:
            print(f"FAILURE: Correct password returned success=False. Body: {resp.text}")
    else:
        print(f"FAILURE: Correct password request failed. Status: {resp.status_code}, Body: {resp.text}")

if __name__ == "__main__":
    try:
        test_password_verification()
    except Exception as e:
        print(f"An error occurred: {e}")
