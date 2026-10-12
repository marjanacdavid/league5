@echo off
cd /d "%~dp0"
echo Brisem samo lokalno Python virtualno okruzenje (.venv)...
if exist .venv rmdir /s /q .venv
call run.bat
