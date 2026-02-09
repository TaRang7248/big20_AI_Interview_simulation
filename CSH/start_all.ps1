# AI 모의면접 시스템 - 전체 서비스 시작 스크립트 (PowerShell)
# 실행: .\start_all.ps1

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
    Write-Host "[0/5] 가상환경 활성화 중..." -ForegroundColor Yellow
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
# 1. Redis 확인
# ──────────────────────────────────────────────
Write-Host "[1/5] Redis 상태 확인 중..." -ForegroundColor Yellow
try {
    $redisCheck = redis-cli ping 2>$null
    if ($redisCheck -eq "PONG") {
        Write-Host "✅ Redis 연결됨" -ForegroundColor Green
    } else {
        Write-Host "🚀 Redis 자동 시작 중..." -ForegroundColor Magenta
        Start-Process "redis-server.exe" -WindowStyle Minimized
        Start-Sleep -Seconds 2
        $redisRecheck = redis-cli ping 2>$null
        if ($redisRecheck -eq "PONG") {
            Write-Host "✅ Redis 자동 시작 완료" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Redis 자동 시작 실패. 수동으로 시작하세요." -ForegroundColor Red
        }
    }
} catch {
    Write-Host "🚀 Redis 자동 시작 중..." -ForegroundColor Magenta
    try {
        Start-Process "redis-server.exe" -WindowStyle Minimized
        Start-Sleep -Seconds 2
        $redisRecheck = redis-cli ping 2>$null
        if ($redisRecheck -eq "PONG") {
            Write-Host "✅ Redis 자동 시작 완료" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Redis 자동 시작 실패. 수동으로 시작하세요." -ForegroundColor Red
        }
    } catch {
        Write-Host "⚠️  Redis가 설치되지 않았습니다. redis-server.exe를 PATH에 추가하세요." -ForegroundColor Red
    }
}

# ──────────────────────────────────────────────
# 2. Ollama 확인
# ──────────────────────────────────────────────
Write-Host "[2/5] Ollama LLM 상태 확인 중..." -ForegroundColor Yellow
try {
    $ollamaCheck = ollama list 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Ollama 실행 중" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Ollama가 실행되지 않았습니다. ollama serve를 먼저 실행하세요." -ForegroundColor Red
    }
} catch {
    Write-Host "⚠️  Ollama가 설치되지 않았습니다." -ForegroundColor Red
}

# ──────────────────────────────────────────────
# 3. Celery Worker 시작 (새 창)
# ──────────────────────────────────────────────
Write-Host "[3/5] Celery Worker 시작 중..." -ForegroundColor Yellow
$activateScript = Join-Path $PSScriptRoot "..\interview_env\Scripts\Activate.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$activateScript'; `$env:PATH = '$venvBase;' + `$env:PATH; cd '$PSScriptRoot'; & '$venvPython' -m celery -A celery_app worker --pool=solo --loglevel=info" -WindowStyle Normal
Write-Host "✅ Celery Worker 시작됨 (새 창)" -ForegroundColor Green

# 잠시 대기
Start-Sleep -Seconds 3

# ──────────────────────────────────────────────
# 4. Next.js 프론트엔드 시작 (새 창)
# ──────────────────────────────────────────────
$frontendDir = Join-Path $PSScriptRoot "frontend"
Write-Host "[4/5] Next.js 프론트엔드 확인 중..." -ForegroundColor Yellow

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
# 5. FastAPI 서버 시작 (현재 창)
# ──────────────────────────────────────────────
Write-Host "[5/5] FastAPI 서버 시작 중..." -ForegroundColor Yellow
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
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "종료하려면 Ctrl+C를 누르세요" -ForegroundColor Gray
Write-Host ""

& $venvPython -m uvicorn integrated_interview_server:app --host 0.0.0.0 --port 8000 --reload
