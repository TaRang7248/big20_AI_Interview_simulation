import requests
import time
import os
import uuid

BASE_URL = "http://localhost:5000/api"
TEST_ID = f"test_tts_{uuid.uuid4().hex[:8]}"
TEST_PW = "1234"

def verify_tts():
    print(f"Starting verification for User: {TEST_ID}")
    
    # 1. Register User
    try:
        data = {
            "id_name": TEST_ID,
            "pw": TEST_PW,
            "name": "TTS_Tester",
            "type": "applicant"
        }
        resp = requests.post(f"{BASE_URL}/register", json=data)
        if resp.status_code == 200 and resp.json().get("success"):
            print("1. Registration Success")
        else:
            print(f"1. Registration Failed: {resp.text}")
            return
    except Exception as e:
        print(f"Connection Error: {e}")
        return

    # 2. Login
    try:
        data = {"id_name": TEST_ID, "pw": TEST_PW}
        resp = requests.post(f"{BASE_URL}/login", json=data)
        if resp.status_code == 200 and resp.json().get("success"):
             print("2. Login Success")
        else:
             print(f"2. Login Failed: {resp.text}")
             return
    except Exception as e:
        print(f"Connection Error: {e}")
        return

    # 3. Create Job (Need logic or just pick first job)
    # Actually let's just pick any job. If no jobs, we create one.
    try:
        resp = requests.get(f"{BASE_URL}/jobs")
        jobs = resp.json().get("jobs", [])
        if not jobs:
             print("3. No jobs found. Creating a test job...")
             # Need to login as admin? Or just standard user can create? server.py allows anyone currently (based on quick look)
             # Wait, server.py create_job takes JobCreate.
             job_data = {
                 "title": "TTS Test Job",
                 "job": "Tester",
                 "id_name": TEST_ID,
                 "deadline": "2025-12-31",
                 "content": "Test"
             }
             resp = requests.post(f"{BASE_URL}/jobs", json=job_data)
             job_title = "TTS Test Job"
        else:
             job_title = jobs[0]["title"]
             print(f"3. Using Job: {job_title}")
    except Exception as e:
        print(f"Job Error: {e}")
        return

    # 4. Upload Resume (Mock)
    # Need a PDF file. I'll create a dummy empty pdf if needed, or check if one exists.
    # I'll just skip upload if I can? start_interview requires resume in DB.
    # I will try to upload a dummy file.
    dummy_pdf_path = "test_resume.pdf"
    if not os.path.exists(dummy_pdf_path):
        with open(dummy_pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 ... dummy content ...") 
    
    try:
        files = {'resume': ('test_resume.pdf', open(dummy_pdf_path, 'rb'), 'application/pdf')}
        data = {'id_name': TEST_ID, 'job_title': job_title} # server code expects job_title (which matches job.job usually, but let's check server.py:535)
        # server.py line 535: job_title: str = Form(...) 
        # And start_interview line 563 accepts StartInterviewRequest with job_title.
        # Wait, finding resume uses job_title too? Yes.
        
        # We need to make sure job_title matches what we pass to start_interview.
        # Job create uses 'job' field as job_title mostly in logic? 
        # Let's use "Tester" as job_title if we created it.
        # Or if we picked existing, verify what 'job' field is.
        # jobs[0]['job']
        
        target_job_title = "Tester" # fallback
        if jobs:
            target_job_title = jobs[0]['job'] if jobs[0]['job'] else "Tester"
            
        # Upload
        print(f"4. Uploading Resume for job: {target_job_title}")
        req_data = {'id_name': TEST_ID, 'job_title': target_job_title}
        resp = requests.post(f"{BASE_URL}/upload/resume", files=files, data=req_data)
        if not resp.json().get("success"):
            print(f"Upload Failed: {resp.text}")
            return
        print("4. Upload Success")
        
        # 5. Start Interview & Check TTS
        print("5. Starting Interview...")
        start_data = {
            "id_name": TEST_ID,
            "job_title": target_job_title
        }
        resp = requests.post(f"{BASE_URL}/interview/start", json=start_data)
        result = resp.json()
        
        if result.get("success"):
            audio_url = result.get("audio_url")
            print(f"Start Interview Success. Audio URL: {audio_url}")
            
            if audio_url and audio_url.endswith(".mp3"):
                # Check if file exists on disk
                # URL is /uploads/tts_audio/filename.mp3
                # Local path is C:\big20\big20_AI_Interview_simulation\LDW\text09\uploads\tts_audio\filename.mp3
                filename = os.path.basename(audio_url)
                local_path = os.path.join(os.getcwd(), "uploads", "tts_audio", filename)
                
                # Give a moment for async file write if needed (await in python should handle it but file sys might lag slightly?)
                time.sleep(2) 
                
                if os.path.exists(local_path):
                    print(f"✅ Verified: Audio file exists at {local_path}")
                    print(f"File size: {os.path.getsize(local_path)} bytes")
                else:
                    print(f"❌ Failed: Audio file not found at {local_path}")
            else:
                 print("❌ Failed: No audio_url returned or invalid format")
        else:
            print(f"Start Interview Failed: {result}")

    except Exception as e:
        print(f"Interview Error: {e}")

if __name__ == "__main__":
    # Wait for server to start
    print("Waiting for server...")
    time.sleep(1) 
    verify_tts()
