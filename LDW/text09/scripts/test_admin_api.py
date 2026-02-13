import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import json

BASE_URL = "http://localhost:5000/api"

def test_admin_apis():
    print("Testing Admin Applicants API...")
    try:
        resp = requests.get(f"{BASE_URL}/admin/applicants")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Success! Found {len(data.get('applicants', []))} applicants.")
            if data.get('applicants'):
                first_num = data['applicants'][0]['interview_number']
                print(f"Testing Detail API for: {first_num}")
                det_resp = requests.get(f"{BASE_URL}/admin/applicant-details/{first_num}")
                if det_resp.status_code == 200:
                    print("Detail Success!")
                    # print(json.dumps(det_resp.json(), indent=2, ensure_ascii=False))
                else:
                    print(f"Detail Failed: {det_resp.status_code}")
        else:
            print(f"Failed: {resp.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_admin_apis()
