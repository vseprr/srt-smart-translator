@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat >nul 2>&1
python app.py
pause
