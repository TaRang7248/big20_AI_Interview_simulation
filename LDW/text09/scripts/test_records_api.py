import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import json

BASE_URL = "http://localhost:5000"

def test_interview_results_api():
    # We need a user ID that has interview results.
    # Since this is a test, let's just check if the endpoint returns success: True (even if empty list).
    user_id = "test_user" # Assuming any ID works as long as DB is up
    
    try:
        print(f"Testing API: {BASE_URL}/api/interview-results/{user_id}")
        response = requests.get(f"{BASE_URL}/api/interview-results/{user_id}")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response JSON: {json.dumps(result, indent=2, ensure_ascii=False)}")
            if result.get("success") is True:
                print("SUCCESS: API returned success flag.")
            else:
                print("FAILED: API did not return success flag.")
        else:
            print(f"FAILED: Status code {response.status_code}")
            
    except Exception as e:
        print(f"Error during API test: {e}")

if __name__ == "__main__":
    # Make sure server is running before this
    test_interview_results_api()
