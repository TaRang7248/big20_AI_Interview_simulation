import requests
import json

BASE_URL = "http://localhost:5000/api/jobs"

def test_create_job():
    print("Testing Create Job...")
    payload = {
        "title": "Test Job Announcement",
        "deadline": "2026-12-31",
        "content" : "This is a test content"
    }
    try:
        response = requests.post(BASE_URL, json=payload)
        if response.status_code == 200:
            print("Create Job Success:", response.json())
        else:
            print("Create Job Failed:", response.status_code, response.text)
    except Exception as e:
        print("Create Job Error:", e)

def test_get_jobs():
    print("\nTesting Get Jobs...")
    try:
        response = requests.get(BASE_URL)
        if response.status_code == 200:
            jobs = response.json().get('jobs', [])
            print(f"Get Jobs Success: retrieved {len(jobs)} jobs")
            for job in jobs:
                print(f"- [{job['id']}] {job['title']} (Deadline: {job['deadline']})")
        else:
            print("Get Jobs Failed:", response.status_code, response.text)
    except Exception as e:
        print("Get Jobs Error:", e)

if __name__ == "__main__":
    # Ensure server is running before running this
    test_create_job()
    test_get_jobs()
