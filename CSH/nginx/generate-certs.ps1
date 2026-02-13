<# 
.SYNOPSIS
    개발용 자체서명(Self-signed) SSL 인증서를 생성합니다.
    
.DESCRIPTION
    NGINX API Gateway에서 SSL 종단(Termination)에 사용할 인증서를 생성합니다.
    ⚠️ 프로덕션 환경에서는 Let's Encrypt 또는 신뢰할 수 있는 CA 인증서를 사용하세요.
    
    생성되는 파일:
      - ssl/server.key  : RSA 2048비트 개인키
      - ssl/server.crt  : 자체서명 인증서 (유효기간 365일)
    
.EXAMPLE
    .\generate-certs.ps1
    
.NOTES
    필수 요구사항: OpenSSL이 설치되어 있어야 합니다.
    - Windows: choco install openssl  또는  winget install OpenSSL
    - Docker 환경에서는 컨테이너 내부에서 자동 생성됩니다.
#>

# 인증서 저장 디렉토리
$CERT_DIR = Join-Path $PSScriptRoot "ssl"

# 인증서 유효 기간 (일)
$VALID_DAYS = 365

# 인증서 Subject (개발용)
$SUBJECT = "/C=KR/ST=Seoul/L=Gangnam/O=AI-Interview-Dev/CN=localhost"

# ──────────────────── 디렉토리 생성 ────────────────────
if (-not (Test-Path $CERT_DIR)) {
    New-Item -ItemType Directory -Path $CERT_DIR -Force | Out-Null
    Write-Host "[1/3] SSL 디렉토리 생성: $CERT_DIR" -ForegroundColor Green
} else {
    Write-Host "[1/3] SSL 디렉토리 이미 존재: $CERT_DIR" -ForegroundColor Yellow
}

$KEY_FILE = Join-Path $CERT_DIR "server.key"
$CRT_FILE = Join-Path $CERT_DIR "server.crt"

# ──────────────────── 기존 인증서 확인 ────────────────────
if ((Test-Path $KEY_FILE) -and (Test-Path $CRT_FILE)) {
    Write-Host "[INFO] 기존 인증서가 발견되었습니다." -ForegroundColor Yellow
    
    # 인증서 만료일 확인
    try {
        $certInfo = openssl x509 -in $CRT_FILE -noout -enddate 2>$null
        Write-Host "       만료일: $certInfo" -ForegroundColor Cyan
    } catch {
        Write-Host "       (만료일 확인 불가)" -ForegroundColor Gray
    }
    
    $overwrite = Read-Host "       덮어쓰시겠습니까? (y/N)"
    if ($overwrite -ne 'y' -and $overwrite -ne 'Y') {
        Write-Host "[SKIP] 기존 인증서를 유지합니다." -ForegroundColor Cyan
        exit 0
    }
}

# ──────────────────── OpenSSL 확인 ────────────────────
Write-Host "[2/3] OpenSSL 확인 중..." -ForegroundColor Cyan
try {
    $opensslVersion = openssl version 2>$null
    if ($LASTEXITCODE -ne 0) { throw "OpenSSL not found" }
    Write-Host "       $opensslVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] OpenSSL이 설치되어 있지 않습니다." -ForegroundColor Red
    Write-Host "        설치 방법:" -ForegroundColor Yellow
    Write-Host "          choco install openssl" -ForegroundColor White
    Write-Host "          또는" -ForegroundColor Gray
    Write-Host "          winget install ShiningLight.OpenSSL" -ForegroundColor White
    exit 1
}

# ──────────────────── 인증서 생성 ────────────────────
Write-Host "[3/3] 자체서명 SSL 인증서 생성 중..." -ForegroundColor Cyan

# SAN (Subject Alternative Name) 설정 파일 임시 생성
# localhost, 127.0.0.1, Docker 내부 도메인 등 모두 포함
$SAN_CONFIG = @"
[req]
default_bits       = 2048
distinguished_name = req_distinguished_name
req_extensions     = v3_req
prompt             = no

[req_distinguished_name]
C  = KR
ST = Seoul
L  = Gangnam
O  = AI-Interview-Dev
CN = localhost

[v3_req]
basicConstraints     = CA:FALSE
keyUsage             = digitalSignature, keyEncipherment
extendedKeyUsage     = serverAuth
subjectAltName       = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
DNS.3 = nginx
DNS.4 = fastapi
DNS.5 = nextjs
IP.1  = 127.0.0.1
IP.2  = 0.0.0.0
"@

$SAN_FILE = Join-Path $CERT_DIR "san.cnf"
$SAN_CONFIG | Out-File -FilePath $SAN_FILE -Encoding UTF8 -Force

try {
    # RSA 2048비트 키 + 자체서명 인증서 동시 생성
    openssl req `
        -x509 `
        -nodes `
        -days $VALID_DAYS `
        -newkey rsa:2048 `
        -keyout $KEY_FILE `
        -out $CRT_FILE `
        -config $SAN_FILE `
        -extensions v3_req `
        2>$null

    if ($LASTEXITCODE -ne 0) {
        throw "OpenSSL 인증서 생성 실패"
    }

    # 임시 설정 파일 삭제
    Remove-Item $SAN_FILE -Force -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host " SSL 인증서 생성 완료!" -ForegroundColor Green
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host "  개인키:   $KEY_FILE" -ForegroundColor White
    Write-Host "  인증서:   $CRT_FILE" -ForegroundColor White
    Write-Host "  유효기간: $VALID_DAYS 일" -ForegroundColor White
    Write-Host ""
    Write-Host "  NGINX에서 자동으로 마운트됩니다:" -ForegroundColor Cyan
    Write-Host "    ssl_certificate     /etc/nginx/ssl/server.crt" -ForegroundColor Gray
    Write-Host "    ssl_certificate_key /etc/nginx/ssl/server.key" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  [!] 브라우저에서 'NET::ERR_CERT_AUTHORITY_INVALID' 경고가" -ForegroundColor Yellow
    Write-Host "      나타날 수 있습니다. 개발 환경에서는 정상입니다." -ForegroundColor Yellow
    Write-Host "=============================================" -ForegroundColor Green

} catch {
    Write-Host "[ERROR] 인증서 생성 실패: $_" -ForegroundColor Red
    # 임시 파일 정리
    Remove-Item $SAN_FILE -Force -ErrorAction SilentlyContinue
    exit 1
}
