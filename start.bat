@echo off
:: ============================================================
::  Steel Frame Generator - Web Launcher (Streamlit)
::  Double-click this file to start the application.
::  The browser opens automatically at http://localhost:8501
:: ============================================================
setlocal

:: Script directory (same folder as this .bat)
set "APP_DIR=%~dp0"
set "SCRIPT=%APP_DIR%steel_frame_web.py"

:: ------------------------------------------------------------
:: 1. Python check
:: ------------------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Python was not found in the PATH.
    echo  Install Python from https://www.python.org/downloads/
    echo  and check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: ------------------------------------------------------------
:: 2. Install / update Streamlit and requests
:: ------------------------------------------------------------
echo.
echo  Checking dependencies...
python -m pip install --quiet --upgrade streamlit requests
if errorlevel 1 (
    echo.
    echo  [ERROR] Unable to install the dependencies.
    echo  Check your Internet connection and administrator rights.
    echo.
    pause
    exit /b 1
)
echo  Dependencies OK.

:: ------------------------------------------------------------
:: 3. Python script check
:: ------------------------------------------------------------
if not exist "%SCRIPT%" (
    echo.
    echo  [ERROR] File not found: %SCRIPT%
    echo  Make sure start.bat and steel_frame_web.py
    echo  are in the same folder.
    echo.
    pause
    exit /b 1
)

:: ------------------------------------------------------------
:: 4. Launch Streamlit
::    --server.headless false  -> open the browser automatically
::    --server.port 8501       -> local port (change if needed)
::    --server.address localhost -> accessible only locally
::                                 Replace with 0.0.0.0 for
::                                 local network (LAN) access
:: ------------------------------------------------------------
echo.
echo  Starting Steel Frame Generator...
echo  Opening the browser at http://localhost:8501
echo.
echo  To stop the application: close this window
echo  or press Ctrl+C in this console.
echo.

python -m streamlit run "%SCRIPT%" ^
    --server.port 8501 ^
    --server.address localhost ^
    --server.headless false ^
    --browser.gatherUsageStats false ^
    --theme.base dark ^
    --theme.primaryColor "#1d4ed8" ^
    --theme.backgroundColor "#0f1623" ^
    --theme.secondaryBackgroundColor "#1e2634" ^
    --theme.textColor "#e2e8f0"

:: ------------------------------------------------------------
:: 5. The application has closed
:: ------------------------------------------------------------
echo.
echo  Steel Frame Generator has stopped.
pause
endlocal
