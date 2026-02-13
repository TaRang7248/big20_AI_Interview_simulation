import sys
import os
import json
# Remove pytest dependency
# import pytest
from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import get_db_connection

client = TestClient(app)

def test_admin_view_fix():
    print("\n--- Starting Verification Test for Admin View Fix ---")
    
    # 1. Setup Test Data
    admin_id = "test_admin_verif"
    applicant_id = "test_applicant_verif"
    
    # Clean up previous test data
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM interview_result WHERE id_name = %s", (applicant_id,)) 
        c.execute("DELETE FROM interview_progress WHERE id_name = %s", (applicant_id,))
        c.execute("DELETE FROM interview_announcement WHERE id_name = %s", (admin_id,))
        c.execute("DELETE FROM users WHERE id_name IN (%s, %s)", (admin_id, applicant_id))
        conn.commit()
    except Exception as e:
        print(f"Cleanup error (ignored): {e}")
        conn.rollback()
    finally:
        conn.close()

    # Register Admin
    try:
        client.post("/api/register", json={
            "id_name": admin_id, "pw": "1234", "name": "AdminUser", "type": "admin",
            "email": "admin@test.com", "phone": "010-0000-0000", "address": "Seoul"
        })
        
        # Register Applicant
        client.post("/api/register", json={
            "id_name": applicant_id, "pw": "1234", "name": "ApplicantUser", "type": "applicant",
            "email": "app@test.com", "phone": "010-0000-0000", "address": "Seoul"
        })
        
        # 2. Create Job as Admin
        job_payload = {
            "title": "Verif Job Title",
            "job": "Verif Job",
            "content": "Test Content",
            "deadline": "2024-12-31",
            "id_name": admin_id
        }
        resp = client.post("/api/jobs", json=job_payload)
        if resp.status_code != 200:
            print(f"Job creation failed: {resp.text}")
            return

        job_id = resp.json()["id"]
        print(f"Created Job ID: {job_id}")
        
        # 3. Simulate Interview Result (Direct Insert with linkage)
        print("Simulating completed interview result directly into DB...")
        conn = get_db_connection()
        c = conn.cursor()
        interview_number = "verif_interview_no_1"
        # Note: We simulate inserting 'announcement_id' which is key for the fix
        c.execute("""
            INSERT INTO Interview_Result (
                interview_number, tech_score, pass_fail, title, announcement_job, id_name, announcement_id, created_at
            ) VALUES (%s, 80, '합격', %s, %s, %s, %s, NOW())
        """, (interview_number, "Verif Job Title", "Verif Job", applicant_id, job_id))
        conn.commit()
        conn.close()
        
        # 4. Check Admin View
        print(f"Checking Admin Applicants View for admin_id={admin_id}...")
        resp = client.get(f"/api/admin/applicants?admin_id={admin_id}")
        if resp.status_code != 200:
            print(f"Admin view failed: {resp.text}")
            return
        
        data = resp.json()
        applicants = data.get("applicants", [])
        print(f"Found {len(applicants)} applicants.")
        
        found = False
        for app in applicants:
            print(f" - Found applicant: {app.get('applicant_name')} (Interview No: {app.get('interview_number')})")
            if app['interview_number'] == interview_number:
                found = True
                break
                
        if found:
            print("SUCCESS: Applicant found in Admin View using announcement_id linkage.")
        else:
            print("FAILURE: Applicant NOT found in Admin View.")
            
    except Exception as e:
        print(f"Test Error: {e}")

if __name__ == "__main__":
    test_admin_view_fix()
