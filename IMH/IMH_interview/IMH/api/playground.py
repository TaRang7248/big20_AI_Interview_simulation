import os
import shutil
import uuid
import tempfile
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from packages.imh_core.logging import get_logger
from packages.imh_core.dto import TranscriptDTO, PDFExtractionResultDTO
from packages.imh_providers.stt.base import ISTTProvider
from packages.imh_providers.pdf.base import IPDFProvider
from IMH.api.dependencies import get_stt_provider, get_pdf_provider

router = APIRouter()
logger = get_logger("IMH.api.playground")

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".mp4"}
MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

SUPPORTED_PDF_EXTENSIONS = {".pdf"}
MAX_PDF_SIZE_MB = 10
MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024

@router.post("/stt", response_model=TranscriptDTO)
async def analyze_stt(
    file: UploadFile = File(...),
    stt_provider: ISTTProvider = Depends(get_stt_provider)
):
    """
    Upload an audio/video file and get a transcription (Mock).
    The file is saved temporarily, processed, and then immediately deleted.
    """
    request_id = str(uuid.uuid4())
    logger.info(f"STT Request received. RequestID: {request_id}, Filename: {file.filename}, ContentType: {file.content_type}")

    # 1. Validation
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if file_ext not in SUPPORTED_EXTENSIONS:
        msg = f"Unsupported file extension: {file_ext}. Supported: {SUPPORTED_EXTENSIONS}"
        logger.warning(f"STT Validation Failed: {msg} [RequestID: {request_id}]")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail={"error_code": "INVALID_FILE_FORMAT", "message": msg, "request_id": request_id}
        )

    # 2. Save to Temporary File
    # We use a named temporary file but control the path to ensure we can close and remove it easily.
    # To conform to strict security rules, we use uuid for filename.
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, temp_filename)
    
    try:
        # Check size while reading (Naive approach for now, or just check file.size if available/trusted)
        # Here we write chunks to control memory usage.
        file_size = 0
        with open(temp_file_path, "wb") as buffer:
            while content := await file.read(1024 * 1024): # 1MB chunks
                file_size += len(content)
                if file_size > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"error_code": "FILE_TOO_LARGE", "message": f"File exceeds {MAX_FILE_SIZE_MB}MB limit", "request_id": request_id}
                    )
                buffer.write(content)
        
        logger.info(f"File saved temporarily at {temp_file_path} ({file_size} bytes) [RequestID: {request_id}]")

        # 3. Process with Provider
        # Note: If it's a video file, the provider (or a pre-processor) should ideally extract audio.
        # For this Mock/Phase 1, we pass the file directly to the provider.
        # The provider interface expects a path str.
        result: TranscriptDTO = await stt_provider.transcribe(temp_file_path)
        
        logger.info(f"STT Processing succeeded. [RequestID: {request_id}]")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"STT Processing Failed [RequestID: {request_id}]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "STT_PROCESSING_ERROR", "message": "An error occurred during speech-to-text processing.", "request_id": request_id}
        )
    finally:
        # 4. Cleanup
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Temporary file deleted: {temp_file_path} [RequestID: {request_id}]")
            except Exception as e:
                logger.error(f"Failed to delete temporary file: {temp_file_path}. Error: {e} [RequestID: {request_id}]")

@router.post("/pdf-text", response_model=PDFExtractionResultDTO)
async def analyze_pdf(
    file: UploadFile = File(...),
    pdf_provider: IPDFProvider = Depends(get_pdf_provider)
):
    """
    Upload a PDF file and extract text (Plain Text).
    Enforces 10MB size limit and 50 page limit.
    """
    request_id = str(uuid.uuid4())
    logger.info(f"PDF Request received. RequestID: {request_id}, Filename: {file.filename}, ContentType: {file.content_type}")

    # 1. Validation: Extension
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if file_ext not in SUPPORTED_PDF_EXTENSIONS:
        msg = f"Unsupported file extension: {file_ext}. Supported: {SUPPORTED_PDF_EXTENSIONS}"
        logger.warning(f"PDF Validation Failed: {msg} [RequestID: {request_id}]")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail={"error_code": "INVALID_FILE_FORMAT", "message": msg, "request_id": request_id}
        )

    # 2. Save to Temporary File
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, temp_filename)
    
    try:
        file_size = 0
        with open(temp_file_path, "wb") as buffer:
            while content := await file.read(1024 * 1024): # 1MB chunks
                file_size += len(content)
                if file_size > MAX_PDF_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error_code": "FILE_TOO_LARGE", 
                            "message": f"File exceeds {MAX_PDF_SIZE_MB}MB limit", 
                            "request_id": request_id
                        }
                    )
                buffer.write(content)
        
        logger.info(f"PDF file saved temporarily at {temp_file_path} ({file_size} bytes) [RequestID: {request_id}]")

        # 3. Process with Provider
        # The provider handles page count validation and text extraction
        result: PDFExtractionResultDTO = pdf_provider.extract_text(temp_file_path)
        
        # Add metadata not available to provider if any
        result.metadata["file_size_bytes"] = file_size

        logger.info(f"PDF Processing succeeded. [RequestID: {request_id}]")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"PDF Processing Failed [RequestID: {request_id}]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "PDF_PROCESSING_ERROR", "message": "An error occurred during PDF processing.", "request_id": request_id}
        )
    finally:
        # 4. Cleanup
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Temporary PDF file deleted: {temp_file_path} [RequestID: {request_id}]")
            except Exception as e:
                logger.error(f"Failed to delete temporary PDF file: {temp_file_path}. Error: {e} [RequestID: {request_id}]")

