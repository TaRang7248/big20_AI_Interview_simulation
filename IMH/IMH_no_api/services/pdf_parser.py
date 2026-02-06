from __future__ import annotations

import fitz  # PyMuPDF
from IMH.IMH_no_api.IMH_no_api.core.exceptions import IMHError

class PDFParser:
    """이력서 PDF 분석을 위한 파서 서비스."""

    @staticmethod
    def extract_text(file_path: str) -> str:
        """PDF 파일에서 텍스트를 추출합니다.

        Args:
            file_path: PDF 파일 경로.

        Returns:
            str: 추출된 텍스트 내용.

        Raises:
            IMHError: 파일 읽기 또는 파싱 중 오류 발생 시.
        """
        try:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            raise IMHError(f"PDF 파싱 실패: {str(e)}")

# 싱글톤 인스턴스 또는 팩토리 함수 제공 가능
pdf_parser = PDFParser()
