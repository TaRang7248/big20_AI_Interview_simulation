import sys
import os
import fitz  # PyMuPDF
import easyocr
import torch
import numpy as np

# Set logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OCR_TEST")

def test_ocr(filepath):
    print(f"Testing OCR on: {filepath}")
    
    # Check CUDA
    use_cuda = torch.cuda.is_available()
    print(f"CUDA Available: {use_cuda}")
    if use_cuda:
        print(f"Device: {torch.cuda.get_device_name(0)}")
    
    # Init EasyOCR
    print("Initializing EasyOCR...")
    reader = easyocr.Reader(['ko', 'en'], gpu=use_cuda)
    
    # Process PDF
    try:
        doc = fitz.open(filepath)
        print(f"PDF Opened. Pages: {len(doc)}")
        
        full_text = ""
        for i, page in enumerate(doc):
            print(f"Processing Page {i+1}...")
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            
            # Convert to numpy
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            if pix.n == 4:
                img_array = img_array[..., :3]
            
            # OCR
            result = reader.readtext(img_array, detail=0)
            text = " ".join(result)
            print(f"Page {i+1} Text Sample: {text[:100]}...")
            
            full_text += text + "\n"
            
        print("-" * 30)
        print("Final Extracted Text Sample:")
        print(full_text[:500])
        print("-" * 30)
        print("✅ OCR Test Completed Successfully.")
        
    except Exception as e:
        print(f"❌ Error during OCR: {e}")

if __name__ == "__main__":
    # Use the test resume file existing in the directory
    test_file = "테스트 이력서.pdf"
    if os.path.exists(test_file):
        test_ocr(test_file)
    else:
        print(f"Test file '{test_file}' not found.")
