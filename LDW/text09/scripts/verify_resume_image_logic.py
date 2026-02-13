import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os
import psycopg2
import json
import fitz
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = "5432"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

def test_db_column():
    print("1. Testing DB Column...")
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT resume_image_path FROM Interview_Result LIMIT 1")
        print("   ✅ 'resume_image_path' column exists.")
    except Exception as e:
        print(f"   ❌ Column check failed: {e}")
    finally:
        conn.close()

def test_pdf_conversion():
    print("2. Testing PDF Conversion Logic...")
    # Create a dummy PDF
    dummy_pdf = "test_resume.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hello World! This is a test resume.")
    doc.save(dummy_pdf)
    doc.close()
    
    try:
        # Test function logic (mimic server.py)
        output_folder = "test_uploads/resume_images/test_uuid"
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            
        image_paths = []
        doc = fitz.open(dummy_pdf)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            image_filename = f"page_{i+1}.png"
            image_path = os.path.join(output_folder, image_filename)
            pix.save(image_path)
            relative_path = f"/uploads/resume_images/{os.path.basename(output_folder)}/{image_filename}"
            image_paths.append(relative_path)
            
        print(f"   Generated Images: {image_paths}")
        
        if len(image_paths) > 0 and os.path.exists(os.path.join(output_folder, "page_1.png")):
             print("   ✅ PDF to Image conversion successful.")
        else:
             print("   ❌ Conversion failed.")
             
    except Exception as e:
        print(f"   ❌ Conversion Error: {e}")
    finally:
        # Cleanup
        if os.path.exists(dummy_pdf):
            os.remove(dummy_pdf)
        # shutil.rmtree("test_uploads") # Optional, keep for inspection if needed

if __name__ == "__main__":
    test_db_column()
    test_pdf_conversion()
