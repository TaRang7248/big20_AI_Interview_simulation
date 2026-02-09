"""
보안 유틸리티 모듈
==================
비밀번호 해싱(bcrypt), JWT 토큰 인증, API 보호 기능 제공

주요 기능:
1. bcrypt 기반 비밀번호 해싱/검증 (SHA-256 대체)
2. JWT 액세스 토큰 발급/검증
3. FastAPI Depends() 기반 인증 미들웨어
4. TLS 인증서 자동 생성 유틸리티
"""

import os
import ssl
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# ========== 환경변수 기반 설정 ==========
# JWT 비밀키 (반드시 .env에서 설정할 것)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_" + os.urandom(16).hex())
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "120"))  # 2시간

# TLS 인증서 경로
TLS_CERTFILE = os.getenv("TLS_CERTFILE", "")
TLS_KEYFILE = os.getenv("TLS_KEYFILE", "")

# 프로덕션 모드 여부
IS_PRODUCTION = os.getenv("APP_ENV", "development").lower() == "production"

# JWT 비밀키 미설정 경고
if "CHANGE_ME_IN_PRODUCTION" in JWT_SECRET_KEY:
    logger.warning("⚠️ JWT_SECRET_KEY가 기본값입니다. .env에 안전한 키를 설정하세요.")

# ========== FastAPI 인증 스킴 ==========
# Bearer 토큰 방식 (Authorization: Bearer <token>)
# auto_error=False: 토큰 없으면 None 반환 (선택적 인증에 사용)
security_scheme = HTTPBearer(auto_error=False)


# ==================== 비밀번호 해싱 ====================

def hash_password(plain_password: str) -> str:
    """
    비밀번호를 bcrypt로 해싱합니다.
    
    Args:
        plain_password: 평문 비밀번호
        
    Returns:
        bcrypt 해시 문자열
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    평문 비밀번호와 bcrypt 해시를 비교 검증합니다.
    기존 SHA-256 해시와의 하위 호환도 지원합니다.
    
    Args:
        plain_password: 사용자가 입력한 평문 비밀번호
        hashed_password: DB에 저장된 해시
        
    Returns:
        일치 여부
    """
    # bcrypt 해시 ($2b$ 로 시작)
    if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    
    # 기존 SHA-256 해시 하위 호환 (마이그레이션 기간용)
    import hashlib
    sha256_hash = hashlib.sha256(plain_password.encode()).hexdigest()
    if sha256_hash == hashed_password:
        logger.info("⚠️ SHA-256 해시 감지 - 로그인 성공 시 bcrypt로 자동 마이그레이션 필요")
        return True
    
    return False


def needs_rehash(hashed_password: str) -> bool:
    """
    기존 SHA-256 해시인지 확인하여 bcrypt 재해싱이 필요한지 판단합니다.
    
    Returns:
        True이면 로그인 성공 후 bcrypt로 재해싱 필요
    """
    return not (hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"))


# ==================== JWT 토큰 ====================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT 액세스 토큰을 생성합니다.
    
    Args:
        data: 토큰에 포함할 페이로드 (sub, email, role 등)
        expires_delta: 만료 시간 (기본: JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
    Returns:
        인코딩된 JWT 문자열
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict]:
    """
    JWT 토큰을 디코딩하고 검증합니다.
    
    Args:
        token: JWT 토큰 문자열
        
    Returns:
        디코딩된 페이로드 dict, 실패 시 None
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.debug(f"JWT 디코딩 실패: {e}")
        return None


# ==================== FastAPI 인증 의존성 ====================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Dict:
    """
    보호된 API 엔드포인트에서 사용하는 인증 의존성.
    Authorization: Bearer <token> 헤더에서 JWT를 검증합니다.
    
    사용법:
        @app.get("/api/protected")
        async def protected_endpoint(user: Dict = Depends(get_current_user)):
            return {"email": user["email"]}
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다. 로그인 후 이용해주세요.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(credentials.credentials)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 만료되었거나 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 토큰에서 사용자 정보 추출
    email = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "email": email,
        "name": payload.get("name", ""),
        "role": payload.get("role", "candidate"),
        "user_id": payload.get("user_id", "")
    }


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Optional[Dict]:
    """
    선택적 인증 — 토큰이 있으면 사용자 정보 반환, 없으면 None.
    공개 API + 인증 시 추가 기능을 제공하는 엔드포인트에서 사용.
    
    사용법:
        @app.get("/api/public-or-auth")
        async def endpoint(user: Optional[Dict] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"안녕하세요, {user['name']}님"}
            return {"message": "게스트 접속"}
    """
    if credentials is None:
        return None
    
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None
    
    email = payload.get("sub")
    if email is None:
        return None
    
    return {
        "email": email,
        "name": payload.get("name", ""),
        "role": payload.get("role", "candidate"),
        "user_id": payload.get("user_id", "")
    }


# ==================== TLS 유틸리티 ====================

def get_ssl_context() -> Optional[ssl.SSLContext]:
    """
    TLS 인증서가 설정되어 있으면 SSL Context를 반환합니다.
    
    환경변수:
        TLS_CERTFILE: 인증서 파일 경로 (.pem)
        TLS_KEYFILE: 개인키 파일 경로 (.pem)
        
    Returns:
        ssl.SSLContext 또는 None (인증서 미설정 시)
    """
    if TLS_CERTFILE and TLS_KEYFILE:
        if os.path.exists(TLS_CERTFILE) and os.path.exists(TLS_KEYFILE):
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(TLS_CERTFILE, TLS_KEYFILE)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            logger.info(f"✅ TLS 활성화: {TLS_CERTFILE}")
            return ctx
        else:
            logger.warning(f"⚠️ TLS 인증서 파일을 찾을 수 없습니다: {TLS_CERTFILE}, {TLS_KEYFILE}")
    return None


def generate_self_signed_cert(cert_dir: str = None) -> tuple:
    """
    개발/테스트용 자체 서명 인증서를 생성합니다.
    
    Args:
        cert_dir: 인증서 저장 디렉토리 (기본: CSH/certs/)
        
    Returns:
        (certfile_path, keyfile_path) 튜플
    """
    if cert_dir is None:
        cert_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs")
    
    os.makedirs(cert_dir, exist_ok=True)
    
    cert_path = os.path.join(cert_dir, "server.crt")
    key_path = os.path.join(cert_dir, "server.key")
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        logger.info("✅ 기존 자체 서명 인증서를 사용합니다.")
        return cert_path, key_path
    
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        
        # RSA 키 생성
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        
        # 인증서 생성
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AI Interview Dev"),
        ])
        
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(
                        __import__("ipaddress").IPv4Address("127.0.0.1")
                    ),
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        
        # 파일 저장
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        logger.info(f"✅ 자체 서명 인증서 생성 완료: {cert_path}")
        return cert_path, key_path
        
    except ImportError:
        logger.error("❌ cryptography 패키지가 필요합니다: pip install cryptography")
        return None, None
    except Exception as e:
        logger.error(f"❌ 인증서 생성 실패: {e}")
        return None, None
