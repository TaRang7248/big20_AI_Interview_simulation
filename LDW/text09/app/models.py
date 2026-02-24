from pydantic import BaseModel
from typing import Optional

# --- User Models ---
class UserRegister(BaseModel):
    id_name: str
    pw: str
    name: str
    dob: Optional[str] = None
    gender: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    type: str = 'applicant'

class UserLogin(BaseModel):
    id_name: str
    pw: str

class PasswordVerify(BaseModel):
    id_name: str
    pw: str

class PasswordChange(BaseModel):
    id_name: str
    new_pw: str

class UserUpdate(BaseModel):
    pw: Optional[str] = None
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    
class IdCheckRequest(BaseModel):
    id_name: str

# --- Job Models ---
class JobCreate(BaseModel):
    title: str
    job: Optional[str] = ''
    deadline: Optional[str] = ''
    content: Optional[str] = ''
    qualifications: Optional[str] = ''
    preferred_qualifications: Optional[str] = ''
    benefits: Optional[str] = ''
    hiring_process: Optional[str] = ''
    number_of_hires: Optional[str] = ''
    id_name: Optional[str] = None

class JobUpdate(BaseModel):
    title: str
    job: Optional[str] = ''
    deadline: Optional[str] = ''
    content: Optional[str] = ''
    qualifications: Optional[str] = ''
    preferred_qualifications: Optional[str] = ''
    benefits: Optional[str] = ''
    hiring_process: Optional[str] = ''
    number_of_hires: Optional[str] = ''
    id_name: Optional[str] = None

# --- Interview Models ---
class StartInterviewRequest(BaseModel):
    id_name: str
    job_title: str
    announcement_id: Optional[int] = None

# --- ID/PW Recovery Models ---
class FindIdRequest(BaseModel):
    name: str
    email: str

class FindPwStep1Request(BaseModel):
    id_name: str

class FindPwStep2Request(BaseModel):
    id_name: str
    verification_code: str
