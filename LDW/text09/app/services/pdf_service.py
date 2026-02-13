import os
import fitz  # PyMuPDF
import easyocr
import torch
import numpy as np
from ..config import logger

# --- CUDA Check & EasyOCR Init ---
USE_CUDA = torch.cuda.is_available()
device = "cuda" if USE_CUDA else "cpu"

if USE_CUDA:
    logger.info(f"✅ PyTorch CUDA Available! Version: {torch.version.cuda}")
    logger.info(f"✅ Current Device: {torch.cuda.get_device_name(0)}")
else:
    logger.warning("⚠️ CUDA not available. Using CPU for OCR/ML tasks. Performance may be slow.")

# Initialize EasyOCR (Load model once)
logger.info("Initializing EasyOCR... (This may take a moment)")
ocr_reader = easyocr.Reader(['ko', 'en'], gpu=USE_CUDA)
logger.info("EasyOCR Initialized.")

def extract_text_from_pdf(filepath):
    """
    Extracts text from PDF by converting pages to images and using EasyOCR.
    """
    logger.info(f"Extracting text from PDF: {filepath}")
    extracted_text = ""
    try:
        # Open PDF with PyMuPDF
        doc = fitz.open(filepath)
        
        for i, page in enumerate(doc):
            # Render page to image (pixmap)
            # matrix=fitz.Matrix(2, 2) makes it higher resolution (good for OCR)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            
            # Prepare image for EasyOCR
            # We can save to temp file or convert to numpy array.
            # EasyOCR supports bytes from memory if we use readtext(bytes) but it expects file path or numpy array mostly.
            # Best way: Convert pixmap samples to numpy array
            
            # Convert bytes to numpy array
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            
            # If default implies alpha (RGBA), drop alpha channel (RGB) for EasyOCR if needed
            if pix.n == 4:
                img_array = img_array[..., :3]
                
            # Perform OCR
            result = ocr_reader.readtext(img_array, detail=0) # detail=0 -> list of text strings
            page_text = " ".join(result)
            extracted_text += f"\n[Page {i+1}]\n{page_text}"

        logger.info(f"OCR Extraction Complete. Length: {len(extracted_text)}")
        return extracted_text

    except Exception as e:
        logger.error(f"PDF Extraction Error (OCR): {e}")
        return ""

def convert_pdf_to_images(pdf_path, output_folder):
    """
    Converts PDF pages to images and saves them to the output_folder.
    Returns a list of relative image paths.
    """
    image_paths = []
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            # Higher resolution for display
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            image_filename = f"page_{i+1}.png"
            image_path = os.path.join(output_folder, image_filename)
            pix.save(image_path)
            
            # Relative path for frontend
            relative_path = f"/uploads/resume_images/{os.path.basename(output_folder)}/{image_filename}"
            image_paths.append(relative_path)
            
        return image_paths
    except Exception as e:
        logger.error(f"PDF to Image Conversion Error: {e}")
        return []
