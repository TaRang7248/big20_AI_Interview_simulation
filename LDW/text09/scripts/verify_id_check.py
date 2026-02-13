import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import json
import sys

BASE_URL = "http://localhost:5000"

def test_id_check():
    print("Testing ID Duplicate Check API...")
    
    # 1. Test with existing ID (should be unavailable)
    # We need to know an existing ID. Let's assume 'admin' or create one if possible, 
    # but based on common sense 'test' or similar might exist. 
    # Actually, we can check logic by trying to register one first or just checking a known one.
    # Let's try to find a user first via login or just assume we can create one.
    # Safe bet: use 'admin' if it exists, or register a temp user.
    
    # Let's register a temp user first to be sure
    temp_id = "duplicate_test_user"
    
    register_data = {
        "id_name": temp_id,
        "pw": "1234",
        "name": "Test User",
        "type": "applicant"
    }
    
    # Try register (might fail if exists, which is fine)
    try:
        requests.post(f"{BASE_URL}/api/register", json=register_data)
    except:
        pass

    # Now check this ID (Should be unavailable)
    print(f"Checking existing ID: {temp_id}")
    resp = requests.post(f"{BASE_URL}/api/check-id", json={"id_name": temp_id})
    if resp.status_code == 200:
        data = resp.json()
        print(f"Response: {data}")
        if data['available'] == False:
            print("PASS: Existing ID recognized as unavailable.")
        else:
            print("FAIL: Existing ID reported as available.")
    else:
        print(f"FAIL: API Error {resp.status_code}")

    # 2. Test with new ID (should be available)
    new_id = "new_unique_id_12345"
    print(f"Checking new ID: {new_id}")
    resp = requests.post(f"{BASE_URL}/api/check-id", json={"id_name": new_id})
    if resp.status_code == 200:
        data = resp.json()
        print(f"Response: {data}")
        if data['available'] == True:
            print("PASS: New ID recognized as available.")
        else:
            print("FAIL: New ID reported as unavailable.")
    else:
        print(f"FAIL: API Error {resp.status_code}")

if __name__ == "__main__":
    try:
        test_id_check()
    except Exception as e:
        print(f"Test Failed: {e}")
