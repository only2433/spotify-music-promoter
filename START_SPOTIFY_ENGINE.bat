@echo off
chcp 65001 > nul
echo ============================================
echo  Spotify Music Promoter - PC Engine
echo ============================================
echo.

echo [1/2] Killing old backend processes (and freeing Port 8000)...
taskkill /F /FI "WINDOWTITLE eq Spotify_Backend*" /T > nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do taskkill /F /PID %%a > nul 2>&1
timeout /t 2 /nobreak > nul

echo [2/2] Starting Spotify Backend (FastAPI + Firestore)...
start "Spotify_Backend" cmd /k "chcp 65001 > nul && title Spotify_Backend && python backend\main.py"

echo.
echo ============================================
echo  Backend engine has been started!
echo   - FastAPI Web Server (Port 8000)
echo   - Firestore Task Listener
echo.
echo  !! DO NOT CLOSE THIS CMD WINDOW !!
echo ============================================
pause
