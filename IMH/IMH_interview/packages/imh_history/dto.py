from datetime import datetime
from pydantic import BaseModel, Field

class HistoryMetadata(BaseModel):
    """
    Metadata for a stored interview report.
    Used for list views without loading the full report.
    """
    interview_id: str = Field(..., description="Unique identifier for the interview")
    timestamp: datetime = Field(..., description="When the interview/report was saved")
    total_score: float = Field(..., description="Total score from the report header")
    grade: str = Field(..., description="Grade from the report header")
    job_category: str = Field(..., description="Job Category from the report header")
    file_path: str = Field(..., description="Relative path to the storage file")
