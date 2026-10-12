@echo off
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>nul
echo UVR Predictor V6 zaustavljen.
pause
