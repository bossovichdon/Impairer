@echo off
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH.
    pause
    exit /b 1
)

if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

pip show pyinstaller >nul 2>nul
if %errorlevel% neq 0 (
    echo Installing build dependencies...
    pip install -r requirements.txt pyinstaller
)

echo Building Impairer.exe...
pyinstaller --onefile --noconsole --name Impairer ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    app.py

echo.
echo Done! Executable is at dist\Impairer.exe
pause
