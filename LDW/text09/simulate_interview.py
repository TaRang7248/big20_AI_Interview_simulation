import requests
import os
import json

BASE_URL = "http://localhost:5000"

# 1. Register User
user_id = "test_user_sim_01"
user_data = {
    "id_name": user_id,
    "pw": "password",
    "name": "Test User",
    "type": "applicant"
}
try:
    print("1. Registering User...")
    # direct DB insert to avoid server running need if we want, but let's assume server is running.
    # Actually, I can't assume server is running on port 5000 accessible from here easily if I don't start it.
    # But I can import app from server and use test_client.
    pass
except Exception as e:
    print(e)

from server import app, init_db
import io

client = app.test_client()

def run_simulation():
    init_db()
    
    # 1. Register
    print("\n--- 1. Register ---")
    res = client.post('/api/register', json={
        "id_name": "sim_user",
        "pw": "1234",
        "name": "Sim User",
        "type": "applicant"
    })
    print(res.get_json())

    # 2. Create Job (as Admin/User)
    print("\n--- 2. Create Job ---")
    res = client.post('/api/jobs', json={
        "title": "Sim Job",
        "job": "Developer",
        "deadline": "2024-12-31",
        "content": "Job Content",
        "id_name": "sim_user"
    })
    job_data = res.get_json()
    print(job_data)
    job_id = job_data['id']

    # 3. Upload Resume
    print("\n--- 3. Upload Resume ---")
    data = {
        'id_name': 'sim_user',
        'job_title': 'Developer',
        'resume': (io.BytesIO(b"dummy pdf content"), 'resume.pdf')
    }
    res = client.post('/api/upload/resume', data=data, content_type='multipart/form-data')
    print(res.get_json())
    
    # 4. Start Interview
    print("\n--- 4. Start Interview ---")
    res = client.post('/api/interview/start', json={
        "id_name": "sim_user",
        "job_id": job_id
    })
    start_data = res.get_json()
    print(start_data)
    
    if not start_data['success']:
        print("Start Failed!")
        return

    interview_number = start_data['interview_number']
    q_id = start_data['q_id']
    question = start_data['question']
    
    # 5. Loop Replies
    for i in range(1, 7): # Try up to 6 times (should finish at 5)
        print(f"\n--- 5. Reply Round {i} ---")
        res = client.post('/api/interview/reply', json={
            "interview_number": interview_number,
            "q_id": q_id,
            "answer": f"Answer for {question}",
            "time_taken": 30
        })
        reply_data = res.get_json()
        print(reply_data)
        
        if reply_data.get('finished'):
            print("Interview Finished successfully!")
            break
            
        q_id = reply_data['q_id']
        question = reply_data['question']

    # 6. Get Result
    print("\n--- 6. Get Result ---")
    res = client.get(f'/api/interview/result/{interview_number}')
    result_data = res.get_json()
    print(result_data)

if __name__ == "__main__":
    run_simulation()
