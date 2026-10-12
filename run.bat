@echo off
setlocal
cd /d "%~dp0"
title Understat Value Predictor V6

echo =============================================
echo   UNDERSTAT VALUE PREDICTOR V6
echo =============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [GRESKA] Python launcher "py" nije pronadjen.
  echo Instaliraj Python 3.11, 3.12 ili 3.13 i ukljuci "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/5] Kreiram virtualno okruzenje...
  py -m venv .venv
  if errorlevel 1 goto :fail
) else (
  echo [1/5] Virtualno okruzenje postoji.
)

set "PY=.venv\Scripts\python.exe"

echo [2/5] Azuriram pip...
"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [3/5] Instaliram FastAPI, Uvicorn i moderni aiohttp...
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [4/5] Instaliram Understat bez njegovog zastarjelog aiohttp pina...
"%PY%" -m pip install --no-deps understat==0.1.14
if errorlevel 1 goto :fail

echo [5/5] Provjeravam instalaciju...
"%PY%" -c "import fastapi,uvicorn,aiohttp,understat; print('OK - dependencies loaded'); print('aiohttp:', aiohttp.__version__)"
if errorlevel 1 goto :fail

echo.
echo Server: http://127.0.0.1:8765
echo Zatvori ovaj prozor da zaustavis server.
echo.
start "" http://127.0.0.1:8765
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo =============================================
echo INSTALACIJA/POKRETANJE NIJE USPJELO.
echo Kopiraj zadnjih 20 redova iz ovog prozora.
echo =============================================
pause
exit /b 1
