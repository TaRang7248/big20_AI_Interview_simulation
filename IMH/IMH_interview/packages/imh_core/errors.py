from typing import Optional, Dict, Any

class IMHBaseError(Exception):
    """
    IMH 프로젝트의 최상위 예외 클래스.
    모든 커스텀 예외는 이 클래스를 상속받아야 합니다.
    
    Attributes:
        code (str): 에러 식별 코드 (예: 'CONF_001')
        message (str): 사람용 에러 메시지
        details (Optional[Dict[str, Any]]): 추가 디버깅 정보
    """
    def __init__(
        self, 
        code: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{code}] {message}")

class ConfigurationError(IMHBaseError):
    """환경 설정 로딩/검증 실패 시 발생하는 예외"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(code="CONF_Error", message=message, details=details)
