# AI 모의면접 시스템 - 전체 서비스 시작 스크립트 (PowerShell)
# 실행: .\start_all.ps1
# 시작 단계: 0) 가상환경 → 1) .env 로드 → 2) Docker(PostgreSQL) → 3) Redis
#            4) Ollama → 5) 미디어 도구 → 6) Celery Worker+Beat → 7) Next.js → 8) FastAPI

$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "AI 모의면접 시스템"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🎯 AI 모의면접 통합 시스템 시작" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 현재 디렉토리를 스크립트 위치로 변경
Set-Location $PSScriptRoot

# ──────────────────────────────────────────────
# 0. 가상환경 활성화
# ──────────────────────────────────────────────
$venvBase = Join-Path $PSScriptRoot "..\interview_env\Scripts"
$venvPath = Join-Path $venvBase "Activate.ps1"
$venvPython = Join-Path $venvBase "python.exe"
if (Test-Path $venvPath) {
    Write-Host "[0/8] 가상환경 활성화 중..." -ForegroundColor Yellow
    & $venvPath
    # 가상환경 Scripts 폴더를 PATH 최우선으로 추가
    $env:PATH = "$venvBase;$env:PATH"
    Write-Host "✅ 가상환경 활성화됨 (interview_env)" -ForegroundColor Green
    Write-Host "   Python: $venvPython" -ForegroundColor DarkGray
} else {
    Write-Host "⚠️  가상환경을 찾을 수 없습니다: $venvPath" -ForegroundColor Red
    Write-Host "    시스템 Python으로 실행합니다." -ForegroundColor Red
    $venvPython = "python"
}

# ──────────────────────────────────────────────
# 0.5 .env 파일 로드 및 환경변수 설정
# ──────────────────────────────────────────────
# Python의 load_dotenv()에만 의존하면 PowerShell 자식 프로세스(Celery 등)에
# 환경변수가 전달되지 않으므로, 여기서도 로딩합니다.
$envFileLocations = @(
    (Join-Path $PSScriptRoot ".env"),           # CSH/.env
    (Join-Path $PSScriptRoot ".." ".env")       # 프로젝트 루트/.env
)
$envFileLoaded = $false
foreach ($envFile in $envFileLocations) {
    if (Test-Path $envFile) {
        Write-Host "[0.5] .env 파일 로드 중: $envFile" -ForegroundColor Yellow
        $envContent = Get-Content $envFile -Encoding UTF8
        foreach ($line in $envContent) {
            # 주석과 빈 줄 무시
            $trimmed = $line.Trim()
            if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
            # KEY=VALUE 파싱
            $eqIdx = $trimmed.IndexOf('=')
            if ($eqIdx -gt 0) {
                $key = $trimmed.Substring(0, $eqIdx).Trim()
                $value = $trimmed.Substring($eqIdx + 1).Trim()
                # 따옴표 제거
                if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
                    ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                    $value = $value.Substring(1, $value.Length - 2)
                }
                [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
            }
        }
        $envFileLoaded = $true
        Write-Host "✅ .env 환경변수 로드 완료" -ForegroundColor Green
        break
    }
}
if (-not $envFileLoaded) {
    Write-Host "⚠️  .env 파일을 찾을 수 없습니다. (CSH/.env 또는 프로젝트루트/.env)" -ForegroundColor Red
    Write-Host "    API 키(DEEPGRAM, HUME, JWT_SECRET 등)가 설정되지 않으면 일부 서비스가 비활성화됩니다." -ForegroundColor Red
    Write-Host "    README의 '환경 변수 설정' 섹션을 참고하여 .env 파일을 생성하세요." -ForegroundColor Red
}

# ──────────────────────────────────────────────
# 1. Docker 컨테이너 확인 (PostgreSQL + Redis)
# ──────────────────────────────────────────────
Write-Host "[1/8] Docker 컨테이너 상태 확인 중..." -ForegroundColor Yellow

$dockerAvailable = $false
try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $dockerAvailable = $true
        Write-Host "   Docker Engine 실행 중" -ForegroundColor DarkGray
    }
} catch {
    Write-Host "⚠️  Docker가 설치되지 않았거나 실행되지 않았습니다." -ForegroundColor Red
    Write-Host "    PostgreSQL(pgvector)과 Redis Docker 컨테이너가 필요합니다." -ForegroundColor Red
}

# PostgreSQL (pgvector) 컨테이너 확인
if ($dockerAvailable) {
    $pgContainer = docker ps --filter "name=interview_db_container" --format "{{.Names}}" 2>$null
    if ($pgContainer) {
        Write-Host "✅ PostgreSQL (pgvector) 컨테이너 실행 중" -ForegroundColor Green
    } else {
        # 중지된 컨테이너가 있는지 확인
        $pgStopped = docker ps -a --filter "name=interview_db_container" --format "{{.Names}}" 2>$null
        if ($pgStopped) {
            Write-Host "🚀 PostgreSQL 컨테이너 재시작 중..." -ForegroundColor Magenta
            docker start interview_db_container 2>$null | Out-Null
            Start-Sleep -Seconds 3
            $pgRecheck = docker ps --filter "name=interview_db_container" --format "{{.Names}}" 2>$null
            if ($pgRecheck) {
                Write-Host "✅ PostgreSQL 컨테이너 재시작 완료" -ForegroundColor Green
            } else {
                Write-Host "⚠️  PostgreSQL 컨테이너 재시작 실패" -ForegroundColor Red
            }
        } else {
            # docker-compose로 생성 시도
            $composeFile = Join-Path $PSScriptRoot "..\docker-compose.yml"
            if (Test-Path $composeFile) {
                Write-Host "🚀 docker-compose로 PostgreSQL 생성 중..." -ForegroundColor Magenta
                Push-Location (Join-Path $PSScriptRoot "..")
                docker compose up -d db 2>$null
                Pop-Location
                Start-Sleep -Seconds 5
                $pgRecheck = docker ps --filter "name=interview_db_container" --format "{{.Names}}" 2>$null
                if ($pgRecheck) {
                    Write-Host "✅ PostgreSQL 컨테이너 생성 및 시작 완료" -ForegroundColor Green
                } else {
                    Write-Host "⚠️  PostgreSQL 생성 실패. 수동 실행: docker compose up -d" -ForegroundColor Red
                }
            } else {
                Write-Host "⚠️  PostgreSQL 컨테이너가 없습니다. docker-compose.yml로 생성하세요." -ForegroundColor Red
            }
        }
    }
}

# pgvector extension 초기화 (쳋 실행 시 필수)
if ($dockerAvailable) {
    $pgRunning = docker ps --filter "name=interview_db_container" --format "{{.Names}}" 2>$null
    if ($pgRunning) {
        Write-Host "   pgvector extension 확인 중..." -ForegroundColor DarkGray
        $pgvectorResult = docker exec interview_db_container psql -U postgres -d interview_db -tAc "SELECT 1 FROM pg_extension WHERE extname='vector'" 2>$null
        if ($pgvectorResult -ne "1") {
            Write-Host "   pgvector extension 생성 중..." -ForegroundColor Magenta
            docker exec interview_db_container psql -U postgres -d interview_db -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>$null | Out-Null
            Write-Host "   ✅ pgvector extension 생성 완료" -ForegroundColor Green
        } else {
            Write-Host "   pgvector extension 확인됨" -ForegroundColor DarkGray
        }
    }
}

# ──────────────────────────────────────────────
# 2. Redis 확인 (Docker 우선, 로컬 fallback)
# ──────────────────────────────────────────────
Write-Host "[2/8] Redis 상태 확인 중..." -ForegroundColor Yellow
$redisRunning = $false

# Redis CLI로 연결 확인
try {
    $redisCheck = redis-cli ping 2>$null
    if ($redisCheck -eq "PONG") {
        $redisRunning = $true
        Write-Host "✅ Redis 연결됨" -ForegroundColor Green
    }
} catch { }

if (-not $redisRunning -and $dockerAvailable) {
    # Docker Redis 컨테이너 확인
    $redisContainer = docker ps --filter "name=interview_redis" --format "{{.Names}}" 2>$null
    if (-not $redisContainer) {
        $redisStopped = docker ps -a --filter "name=interview_redis" --format "{{.Names}}" 2>$null
        if ($redisStopped) {
            Write-Host "🚀 Redis Docker 컨테이너 재시작 중..." -ForegroundColor Magenta
            docker start interview_redis 2>$null | Out-Null
        } else {
            Write-Host "🚀 Redis Docker 컨테이너 생성 중..." -ForegroundColor Magenta
            docker run -d --name interview_redis -p 6379:6379 redis:latest 2>$null | Out-Null
        }
        Start-Sleep -Seconds 2
        try {
            $redisRecheck = redis-cli ping 2>$null
            if ($redisRecheck -eq "PONG") {
                $redisRunning = $true
                Write-Host "✅ Redis Docker 컨테이너 시작 완료" -ForegroundColor Green
            }
        } catch { }
    }
}

if (-not $redisRunning) {
    # 로컬 redis-server.exe fallback
    Write-Host "🚀 로컬 Redis 서버 시작 시도 중..." -ForegroundColor Magenta
    try {
        Start-Process "redis-server.exe" -WindowStyle Minimized -ErrorAction Stop
        Start-Sleep -Seconds 2
        $redisRecheck = redis-cli ping 2>$null
        if ($redisRecheck -eq "PONG") {
            $redisRunning = $true
            Write-Host "✅ 로컬 Redis 서버 시작 완료" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Redis 시작 실패. Celery 및 이벤트 버스에 필요합니다." -ForegroundColor Red
        }
    } catch {
        Write-Host "⚠️  Redis가 설치되지 않았습니다. Docker 또는 redis-server.exe를 설치하세요." -ForegroundColor Red
    }
}

# ──────────────────────────────────────────────
# 3. Ollama 확인 및 자동 시작
# ──────────────────────────────────────────────
Write-Host "[3/8] Ollama LLM 상태 확인 중..." -ForegroundColor Yellow
$ollamaRunning = $false
try {
    $ollamaCheck = ollama list 2>$null
    if ($LASTEXITCODE -eq 0) {
        $ollamaRunning = $true
        Write-Host "✅ Ollama 실행 중" -ForegroundColor Green
    }
} catch { }

# Ollama 미실행 시 자동 시작 시도
if (-not $ollamaRunning) {
    $ollamaCmd = Get-Command "ollama" -ErrorAction SilentlyContinue
    if ($ollamaCmd) {
        Write-Host "🚀 Ollama 자동 시작 중 (ollama serve)..." -ForegroundColor Magenta
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Minimized
        Start-Sleep -Seconds 5
        try {
            $ollamaRecheck = ollama list 2>$null
            if ($LASTEXITCODE -eq 0) {
                $ollamaRunning = $true
                Write-Host "✅ Ollama 자동 시작 완료" -ForegroundColor Green
            } else {
                Write-Host "⚠️  Ollama serve 시작되었으나 응답 없음. 잠시 후 재시도하세요." -ForegroundColor Red
            }
        } catch {
            Write-Host "⚠️  Ollama serve 시작 후 확인 실패" -ForegroundColor Red
        }
    } else {
        Write-Host "⚠️  Ollama가 설치되지 않았습니다. LLM 기능이 비활성화됩니다." -ForegroundColor Red
        Write-Host "    설치: https://ollama.ai/download" -ForegroundColor DarkGray
    }
}

# 모델 확인 및 자동 Pull (Ollama 실행 중일 때만)
if ($ollamaRunning) {
    # qwen3:4b 모델 확인
    $modelCheck = ollama list 2>$null | Select-String "qwen3:4b"
    if ($modelCheck) {
        Write-Host "   qwen3:4b 모델 확인됨" -ForegroundColor DarkGray
    } else {
        Write-Host "⚠️  qwen3:4b 모델이 없습니다. 자동 다운로드 중..." -ForegroundColor Magenta
        ollama pull qwen3:4b
    }
    
    # nomic-embed-text 임베딩 모델 확인 및 자동 Pull (RAG 필수)
    $embedCheck = ollama list 2>$null | Select-String "nomic-embed-text"
    if ($embedCheck) {
        Write-Host "   nomic-embed-text 임베딩 모델 확인됨" -ForegroundColor DarkGray
    } else {
        Write-Host "⚠️  nomic-embed-text 모델이 없습니다. 자동 다운로드 중... (RAG 필수)" -ForegroundColor Magenta
        ollama pull nomic-embed-text
    }
}

# ──────────────────────────────────────────────
# 4. FFmpeg / GStreamer 확인 (미디어 녹화용)
# ──────────────────────────────────────────────
Write-Host "[4/8] 미디어 도구 확인 중..." -ForegroundColor Yellow
$mediaToolFound = $false

$gstCheck = Get-Command "gst-launch-1.0" -ErrorAction SilentlyContinue
if ($gstCheck) {
    Write-Host "✅ GStreamer 설치됨 (녹화 서비스 1순위)" -ForegroundColor Green
    $mediaToolFound = $true
}

$ffmpegCheck = Get-Command "ffmpeg" -ErrorAction SilentlyContinue
if ($ffmpegCheck) {
    if ($mediaToolFound) {
        Write-Host "   FFmpeg도 설치됨 (fallback 사용 가능)" -ForegroundColor DarkGray
    } else {
        Write-Host "✅ FFmpeg 설치됨 (녹화 서비스 활성화)" -ForegroundColor Green
        $mediaToolFound = $true
    }
} 

if (-not $mediaToolFound) {
    Write-Host "⚠️  GStreamer/FFmpeg 미설치 — 면접 녹화 기능 비활성화됨" -ForegroundColor Yellow
    Write-Host "    설치: winget install Gyan.FFmpeg" -ForegroundColor DarkGray
}

# ──────────────────────────────────────────────
# 5. Celery Worker + Beat 스케줄러 시작 (새 창)
# ──────────────────────────────────────────────
Write-Host "[5/8] Celery Worker + Beat 시작 중..." -ForegroundColor Yellow
$activateScript = Join-Path $PSScriptRoot "..\interview_env\Scripts\Activate.ps1"

# Celery Worker (새 창) — 모든 큐 소비
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$activateScript'; `$env:PATH = '$venvBase;' + `$env:PATH; cd '$PSScriptRoot'; & '$venvPython' -m celery -A celery_app worker --pool=solo --loglevel=info" -WindowStyle Normal
Write-Host "✅ Celery Worker 시작됨 (새 창)" -ForegroundColor Green

# Celery Beat 스케줄러 (새 창) — 주기적 태스크 (5분 세션 정리, 1시간 통계 집계)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$activateScript'; `$env:PATH = '$venvBase;' + `$env:PATH; cd '$PSScriptRoot'; & '$venvPython' -m celery -A celery_app beat --loglevel=info" -WindowStyle Normal
Write-Host "✅ Celery Beat 스케줄러 시작됨 (새 창)" -ForegroundColor Green

# 잠시 대기
Start-Sleep -Seconds 3

# ──────────────────────────────────────────────
# 6. Next.js 프론트엔드 시작 (새 창)
# ──────────────────────────────────────────────
$frontendDir = Join-Path $PSScriptRoot "frontend"
Write-Host "[6/8] Next.js 프론트엔드 확인 중..." -ForegroundColor Yellow

if (Test-Path $frontendDir) {
    # Node.js 설치 확인 (npm.cmd 사용 — PowerShell 실행 정책 이슈 회피)
    $npmCmd = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if (-not $npmCmd) {
        # PATH 새로고침 후 재시도
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
        $npmCmd = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    }

    if ($npmCmd) {
        # node_modules 없으면 자동 npm install
        $nodeModulesPath = Join-Path $frontendDir "node_modules"
        if (-not (Test-Path $nodeModulesPath)) {
            Write-Host "📦 node_modules 미설치 감지 → npm install 실행 중..." -ForegroundColor Magenta
            Push-Location $frontendDir
            & npm.cmd install 2>$null
            Pop-Location
            if (Test-Path $nodeModulesPath) {
                Write-Host "✅ npm install 완료" -ForegroundColor Green
            } else {
                Write-Host "⚠️  npm install 실패. 수동으로 CSH\frontend 폴더에서 npm install 하세요." -ForegroundColor Red
            }
        }

        # Next.js dev 서버 시작 (새 창)
        $npmPath = $npmCmd.Source
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendDir'; & '$npmPath' run dev" -WindowStyle Normal
        Write-Host "✅ Next.js 프론트엔드 시작됨 (새 창 → http://localhost:3000)" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Node.js가 설치되지 않았습니다. Next.js 프론트엔드를 시작할 수 없습니다." -ForegroundColor Red
        Write-Host "    설치: winget install OpenJS.NodeJS.LTS" -ForegroundColor DarkGray
    }
} else {
    Write-Host "⚠️  frontend 폴더가 없습니다. Next.js 프론트엔드가 아직 빌드되지 않았습니다." -ForegroundColor Red
}

# 잠시 대기
Start-Sleep -Seconds 2

# ──────────────────────────────────────────────
# 7. 시작 전 요약
# ──────────────────────────────────────────────
Write-Host "" 
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "📋 시작 요약" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
if ($envFileLoaded) {
    Write-Host "   .env 파일:        ✅ 로드됨" -ForegroundColor Green
} else {
    Write-Host "   .env 파일:        ⚠️  없음" -ForegroundColor Red
}
# PostgreSQL 상태 확인
if ($dockerAvailable) {
    $pgFinalCheck = docker ps --filter "name=interview_db_container" --format "{{.Names}}" 2>$null
    if ($pgFinalCheck) {
        Write-Host "   PostgreSQL:       ✅" -ForegroundColor Green
    } else {
        Write-Host "   PostgreSQL:       ⚠️" -ForegroundColor Red
    }
} else {
    Write-Host "   PostgreSQL:       ⚠️  Docker 미실행" -ForegroundColor Red
}
if ($redisRunning) {
    Write-Host "   Redis:            ✅" -ForegroundColor Green
} else {
    Write-Host "   Redis:            ⚠️" -ForegroundColor Red
}
if ($ollamaRunning) {
    Write-Host "   Ollama:           ✅" -ForegroundColor Green
} else {
    Write-Host "   Ollama:           ⚠️" -ForegroundColor Red
}
if ($mediaToolFound) {
    Write-Host "   미디어 도구:       ✅" -ForegroundColor Green
} else {
    Write-Host "   미디어 도구:       ⚠️  선택사항" -ForegroundColor Yellow
}
Write-Host "   Celery Worker:    ✅ (새 창)" -ForegroundColor Green
Write-Host "   Celery Beat:      ✅ (새 창)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

# ──────────────────────────────────────────────
# 8. FastAPI 서버 시작 (현재 창)
# ──────────────────────────────────────────────
Write-Host "[8/8] FastAPI 서버 시작 중..." -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🌐 FastAPI 백엔드:  http://localhost:8000" -ForegroundColor White
Write-Host "🖥️  Next.js 프론트:  http://localhost:3000" -ForegroundColor White
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "📋 대시보드:       http://localhost:3000/dashboard" -ForegroundColor DarkGray
Write-Host "🎤 AI 면접:        http://localhost:3000/interview" -ForegroundColor DarkGray
Write-Host "💻 코딩 테스트:    http://localhost:3000/coding" -ForegroundColor DarkGray
Write-Host "📐 화이트보드:     http://localhost:3000/whiteboard" -ForegroundColor DarkGray
Write-Host "🎯 감정 분석:      http://localhost:3000/emotion" -ForegroundColor DarkGray
Write-Host "👤 프로필:         http://localhost:3000/profile" -ForegroundColor DarkGray
Write-Host "📄 API 문서:       http://localhost:8000/docs" -ForegroundColor DarkGray
Write-Host "⏱️  SLA 모니터링:   http://localhost:8000/api/monitoring/latency" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "종료하려면 Ctrl+C를 누르세요" -ForegroundColor Gray
Write-Host ""

& $venvPython -m uvicorn integrated_interview_server:app --host 0.0.0.0 --port 8000 --reload
