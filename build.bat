@echo off
rem Rebuilds index.html from content\*.md and screenshots\*.
rem Requires Python 3 plus:  pip install markdown-it-py pygments
cd /d "%~dp0"
python tools\build.py
if errorlevel 1 (
  echo.
  echo Build failed. Make sure Python is installed and run:  pip install markdown-it-py pygments
  pause
  exit /b 1
)
echo.
echo Done. Open index.html in your browser.
pause
