
import os
import uuid
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def test_resume_upload():
    # 0. Create a unique user
    random_id = f"test_user_{uuid.uuid4().hex[:8]}"
    user_data = {
        "id_name": random_id,
        "pw": "password123",
        "name": "Test User",
        "dob": "1990-01-01",
        "gender": "male",
        "email": "test@example.com",
        "address": "Seoul",
        "phone": "010-0000-0000",
        "type": "applicant"
    }
    
    print(f"Registering user: {random_id}...")
    reg_response = client.post("/api/register", json=user_data)
    print(f"Register Response: {reg_response.json()}")
    assert reg_response.status_code == 200
    assert reg_response.json()["success"] == True

    # 1. Prepare dummy PDF file
    file_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Resources <<\n/Font <<\n/F1 4 0 R\n>>\n>>\n/Contents 5 0 R\n>>\nendobj\n4 0 obj\n<<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\nendobj\n5 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 24 Tf\n100 100 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f\n0000000010 00000 n\n0000000079 00000 n\n0000000173 00000 n\n0000000301 00000 n\n0000000389 00000 n\ntrailer\n<<\n/Size 6\n/Root 1 0 R\n>>\nstartxref\n492\n%%EOF"
    
    files = {'resume': ('test_resume.pdf', file_content, 'application/pdf')}
    data = {'id_name': random_id, 'job_title': 'Software Engineer'}
    
    # Check if upload directory exists
    if not os.path.exists("uploads/resumes"):
        os.makedirs("uploads/resumes")

    print("Sending request to /api/upload/resume...")
    response = client.post("/api/upload/resume", files=files, data=data)
    
    print(f"Response Status Code: {response.status_code}")
    print(f"Response JSON: {response.json()}")

    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "filepath" in response.json()
    
    uploaded_path = response.json()["filepath"]
    if os.path.exists(uploaded_path):
        print(f"✅ File uploaded successfully to {uploaded_path}")
        # Clean up
        try:
            os.remove(uploaded_path)
            print("Cleaned up uploaded file.")
        except Exception as e:
            print(f"Error cleaning up: {e}")
    else:
        print(f"❌ File not found at {uploaded_path}")

if __name__ == "__main__":
    test_resume_upload()
