@echo off
cd /d "%~dp0"

:: Create virtual environment if it doesn't exist
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate

:: Install dependencies if needed
pip install -e . >nul 2>&1

:: Create config file if it doesn't exist
if not exist booru.conf (
    echo Creating config file from template...
    copy booru.conf.example booru.conf
    echo.
    echo WARNING: Edit booru.conf with your API keys, then run this script again!
    pause
    exit /b 1
)

:: Start the server
python -m booruswipe --verbose
