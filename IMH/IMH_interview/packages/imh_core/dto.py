from pydantic import BaseModel, ConfigDict

class BaseDTO(BaseModel):
    """
    IMH 프로젝트의 모든 DTO(Data Transfer Object)의 기반 클래스.
    
    Features:
        - from_attributes=True (ORM 객체 변환 지원)
        - str_strip_whitespace=True (문자열 공백 자동 제거)
    """
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        populate_by_name=True
    )
