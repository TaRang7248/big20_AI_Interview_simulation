import requests
import json
import uuid

BASE_URL = "http://localhost:5000"

def test_register_duplicate():
    print("Testing Registration with Duplicate ID...")
    
    # 1. Create a unique ID first
    unique_id = f"user_{uuid.uuid4().hex[:8]}"
    print(f"Using ID: {unique_id}")
    
    user_data = {
        "id_name": unique_id,
        "pw": "password123",
        "name": "Test User",
        "dob": "1990-01-01",
        "gender": "male",
        "email": "test@example.com",
        "address": "Test Address",
        "phone": "010-1234-5678",
        "type": "applicant"
    }
    
    # 2. First Registration (Should Succeed)
    print("1. First Registration (Expect Success)")
    try:
        resp = requests.post(f"{BASE_URL}/api/register", json=user_data)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        
        if resp.status_code == 200 and resp.json().get("success") == True:
            print("PASS: First registration successful.")
        else:
            print("FAIL: First registration failed.")
            return
            
    except Exception as e:
        print(f"FAIL: Request Error {e}")
        return

    # 3. Second Registration (Should Fail with Message)
    print("\n2. Second Registration (Expect Failure with Message)")
    try:
        resp = requests.post(f"{BASE_URL}/api/register", json=user_data)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        
        # Note: server.py modification returns a JSON directly, usually with 200 OK if we just returned a dict, 
        # but let's see how FastAPI handles it. 
        # If I returned a dict, FastAPI converts to JSON 200 OK by default unless response_model says otherwise or I used JSONResponse.
        # My code: `return {"success": False, "message": "..."}`
        # So status code should be 200 (default) with success=False.
        
        data = resp.json()
        if resp.status_code == 200:
            if data.get("success") == False and "이미 존재하는 아이디입니다." in data.get("message", ""):
                 print("PASS: Duplicate registration returned correct message.")
            else:
                 print(f"FAIL: Unexpected response content. Success={data.get('success')}, Message={data.get('message')}")
        else:
             # If it raised exception it would be 400 or 500
             print(f"FAIL: Status code {resp.status_code}. Content: {resp.text}")

    except Exception as e:
        print(f"FAIL: Request Error {e}")

if __name__ == "__main__":
    test_register_duplicate()
