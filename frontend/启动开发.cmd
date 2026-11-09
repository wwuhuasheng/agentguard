@echo off
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Please install Node.js 22.12+ or 24.x first.
  pause
  exit /b 1
)
if not exist node_modules (
  call npm ci --no-audit --no-fund --cache .npm-cache
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
call npm run dev -- --open
pause
