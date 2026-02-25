import os
import fitz  # PyMuPDF
import easyocr
import torch
import numpy as np
from ..config import logger

# --- CUDA 확인 및 EasyOCR 초기화 ---
USE_CUDA = torch.cuda.is_available()
device = "cuda" if USE_CUDA else "cpu"

if USE_CUDA:
    logger.info(f"✅ PyTorch CUDA 사용 가능! 버전: {torch.version.cuda}")
    logger.info(f"✅ 현재 장치: {torch.cuda.get_device_name(0)}")
else:
    logger.warning("⚠️ CUDA를 사용할 수 없습니다. OCR/ML 작업에 CPU를 사용합니다. 성능이 느려질 수 있습니다.")

# EasyOCR 초기화 (모델을 한 번만 로드)
logger.info("EasyOCR 초기화 중... (잠시 시간이 걸릴 수 있습니다)")
ocr_reader = easyocr.Reader(['ko', 'en'], gpu=USE_CUDA)
logger.info("EasyOCR 초기화 완료.")

def extract_text_from_pdf(filepath):
    """
    내부 페이지를 이미지로 변환하고 EasyOCR을 사용하여 PDF에서 텍스트를 추출합니다.
    """
    logger.info(f"PDF에서 텍스트 추출 중: {filepath}")
    extracted_text = ""
    try:
        # PyMuPDF로 PDF 열기
        doc = fitz.open(filepath)
        
        for i, page in enumerate(doc):
            # 페이지를 이미지(pixmap)로 렌더링
            # matrix=fitz.Matrix(2, 2)를 사용하여 고해상도로 설정 (OCR에 유리)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            
            # EasyOCR을 위한 이미지 준비
            # pixmap 샘플을 numpy 배열로 변환
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            
            # 알파 채널(RGBA)이 포함된 경우 RGB로 변환
            if pix.n == 4:
                img_array = img_array[..., :3]
                
            # OCR 수행
            result = ocr_reader.readtext(img_array, detail=0) # detail=0 -> 텍스트 문자열 리스트 반환
            page_text = " ".join(result)
            extracted_text += f"\n[Page {i+1}]\n{page_text}"

        logger.info(f"OCR 추출 완료. 길이: {len(extracted_text)}")
        return extracted_text

    except Exception as e:
        logger.error(f"PDF 추출 오류 (OCR): {e}")
        return ""

def convert_pdf_to_images(pdf_path, output_folder):
    """
    PDF 페이지를 이미지로 변환하여 output_folder에 저장합니다.
    상대 이미지 경로 리스트를 반환합니다.
    """
    image_paths = []
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            # 화면 표시용 고해상도 설정
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            image_filename = f"page_{i+1}.png"
            image_path = os.path.join(output_folder, image_filename)
            pix.save(image_path)
            
            # 프론트엔드용 상대 경로
            relative_path = f"/uploads/resume_images/{os.path.basename(output_folder)}/{image_filename}"
            image_paths.append(relative_path)
            
        return image_paths
    except Exception as e:
        logger.error(f"PDF 이미지 변환 오류: {e}")
        return []
