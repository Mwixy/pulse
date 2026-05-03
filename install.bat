@echo off
:: This line moves the terminal to the folder where the script is located
cd /d "%~dp0"
setlocal

echo ====================================
echo      Pulse Installation Setup
echo ====================================
echo.

echo Checking for required installation files...
if not exist "setup.py" (
    echo [X] ERROR: setup.py not found!
    echo     Please make sure you are running this script from the main Pulse folder.
    echo     Or if you are running this script as an administator, please close this window and do this instead:
    echo     Run a new command prompt as admin then:
    echo         cd {Your Pulse Folder's Path}
    echo         python install.bat
    pause
    exit /b 1
)
if not exist "pulse\" (
    echo [X] ERROR: pulse folder not found!
    echo     Please make sure you are running this script from the main Pulse folder.
    pause
    exit /b 1
)
echo [OK] All required setup files found!
echo.

echo Checking for Python installation...

:: 1. Check if python command exists
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python is not installed or not added to PATH.
    echo     Pulse requires Python 3.8 or higher.
    echo.
    echo Redirecting you to the Python download page...
    start https://www.python.org/downloads/windows/
    echo.
    echo IMPORTANT: When installing Python, make sure to check the box
    echo "Add Python to PATH" at the bottom of the installer window!
    echo.
    echo After installing, press any key to exit and try running this setup again.
    pause
    exit /b 1
)

:: 2. Check if Python version is >= 3.8
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"
if %errorlevel% neq 0 (
    echo [X] Your Python version is too old!
    echo     Pulse requires Python 3.8 or higher.
    echo.
    echo Redirecting you to the Python download page...
    start https://www.python.org/downloads/windows/
    echo.
    echo Please download and install a newer version, then run this setup again.
    pause
    exit /b 1
)

echo [OK] A compatible Python version was found!

:: 3. Launch the interactive installer menu
python setup_menu.py

