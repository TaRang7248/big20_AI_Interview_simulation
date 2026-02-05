import requests
import json

url = "http://127.0.0.1:8000/api/start"
payload = {
    "name": "테스터",
    "job_title": "백엔드 개발자"
}
headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print("Response Body:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
