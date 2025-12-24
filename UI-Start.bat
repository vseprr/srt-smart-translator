@echo off
cd /d "%~dp0"

echo ============================================
echo   Smart SRT Translator - Starting...
echo ============================================
echo.

REM Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo [!] Virtual environment not found!
    echo.
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Is Python installed?
        pause
        exit /b 1
    )
    echo.
    echo Installing dependencies...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    echo.
    echo [OK] Setup complete!
    echo.
)

REM Activate venv and run
call venv\Scripts\activate.bat >nul 2>&1
echo Starting server at http://localhost:5000
echo Press Ctrl+C to stop
echo.
python app.py
pause
